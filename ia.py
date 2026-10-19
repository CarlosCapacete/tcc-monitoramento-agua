# ==========================================
# TCC - INTELIGÊNCIA ARTIFICIAL (HÍBRIDA AVANÇADA v2)
# ML é o porteiro, regras classificam gravidade
# ==========================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from db import supabase


# =====================================================
# ⚙️ CONFIGURAÇÕES AJUSTÁVEIS
# =====================================================

# Gravidade mínima para gerar alerta (pulsos)
LIMIAR_MINIMO_ALERTA = 300

# Limiares de gravidade
LIMIAR_ALTA = 1000
LIMIAR_CRITICA = 3000

# Cache do modelo ML (segundos) — evita retreinar a cada 5 min
INTERVALO_RETREINO_MODELO = 3600  # 1 hora

# Mínimo de leituras para treinar
MIN_LEITURAS_TREINO = 50


# =====================================================
# 🧠 CACHE DO MODELO
# =====================================================

_cache_modelo = {
    "modelo": None,
    "df_historico": None,
    "ultimo_treino": None
}


# ---------- FUNÇÃO AUXILIAR: Período do dia ----------
def classificar_periodo(hora):
    if 0 <= hora <= 5:
        return 0
    elif 6 <= hora <= 11:
        return 1
    elif 12 <= hora <= 17:
        return 2
    else:
        return 3


# ---------- FUNÇÃO AUXILIAR: Normaliza timestamp ----------
def normalizar_timestamp(ts):
    """Remove microssegundos para padronizar o formato."""
    try:
        dt = pd.to_datetime(ts, format='ISO8601', utc=True)
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


# ---------- 1. TREINAMENTO DO MODELO (COM CACHE) ----------
def treinar_modelo_anomalias(forcar=False):
    agora = datetime.now()

    # Verifica se pode usar o cache
    if not forcar and _cache_modelo["modelo"] is not None:
        if _cache_modelo["ultimo_treino"] is not None:
            tempo_decorrido = (agora - _cache_modelo["ultimo_treino"]).total_seconds()
            if tempo_decorrido < INTERVALO_RETREINO_MODELO:
                print(f"[IA] Usando modelo em cache ({int(tempo_decorrido)}s desde o último treino)")
                return _cache_modelo["modelo"], _cache_modelo["df_historico"]

    # ---- Retreina do zero ----
    print("[IA] Retreinando modelo...")
    resposta = supabase.table("leituras").select("timestamp, pulsos").execute()
    df = pd.DataFrame(resposta.data)

    if len(df) < MIN_LEITURAS_TREINO:
        print(f"[IA] Dados insuficientes: {len(df)} leituras (mín: {MIN_LEITURAS_TREINO})")
        return None, None

    df["timestamp"] = pd.to_datetime(df["timestamp"], format='ISO8601', utc=True, errors='coerce')
    df = df.dropna(subset=["timestamp"])

    df["hora"] = df["timestamp"].dt.hour
    df["dia"] = df["timestamp"].dt.day
    df["dia_semana"] = df["timestamp"].dt.dayofweek
    df["mes"] = df["timestamp"].dt.month
    df["ano"] = df["timestamp"].dt.year
    df["periodo"] = df["hora"].apply(classificar_periodo)
    df["media_movel"] = df["pulsos"].rolling(window=10, min_periods=1).mean()

    X = df[["hora", "dia", "dia_semana", "mes", "ano", "periodo", "media_movel", "pulsos"]].values

    modelo = IsolationForest(contamination=0.02, random_state=42)
    modelo.fit(X)

    # Salva no cache
    _cache_modelo["modelo"] = modelo
    _cache_modelo["df_historico"] = df
    _cache_modelo["ultimo_treino"] = agora

    print(f"[IA] Modelo treinado com {len(df)} leituras")
    return modelo, df


# ---------- 2. DETECÇÃO DE ANOMALIA ----------
def detectar_anomalia_ml(modelo, hora, dia, dia_semana, mes, ano, pulsos, media_movel):
    if modelo is None:
        return False
    periodo = classificar_periodo(hora)
    resultado = modelo.predict([[hora, dia, dia_semana, mes, ano, periodo, media_movel, pulsos]])
    return resultado[0] == -1


# ---------- 3. CLASSIFICAÇÃO DE GRAVIDADE ----------
def classificar_gravidade(hora, pulsos):
    if pulsos < LIMIAR_MINIMO_ALERTA:
        return None

    if pulsos >= LIMIAR_CRITICA:
        gravidade = "critica"
        descricao = "Consumo extremamente alto"
    elif pulsos >= LIMIAR_ALTA:
        gravidade = "alta"
        descricao = "Consumo muito alto"
    else:
        gravidade = "media"
        descricao = "Consumo anormal"

    if 0 <= hora <= 5:
        if gravidade == "media":
            gravidade = "alta"
        elif gravidade == "alta":
            gravidade = "critica"
        descricao += " na madrugada"

    return {
        "tipo": "comportamento_anormal",
        "mensagem": descricao,
        "gravidade": gravidade
    }


# ---------- 4. RECOMENDAÇÕES ----------
def gerar_recomendacao(hora, pulsos):
    if 0 <= hora <= 5:
        return {"local": "possível vazamento", "dica": "Verifique torneiras, descargas e a boia da caixa d'água.", "pulsos": pulsos, "hora": hora}
    elif 6 <= hora <= 9:
        return {"local": "banheiro (banho matinal)", "dica": "Reduza o tempo de banho em 2 minutos. Economia de ~10 L por banho.", "pulsos": pulsos, "hora": hora}
    elif 12 <= hora <= 14:
        return {"local": "cozinha (almoço)", "dica": "Feche a torneira ao ensaboar a louça. Economia de ~15 L por lavagem.", "pulsos": pulsos, "hora": hora}
    elif 18 <= hora <= 21:
        return {"local": "banheiro (banho noturno)", "dica": "Instale um arejador na torneira. Reduz o consumo em até 30%.", "pulsos": pulsos, "hora": hora}
    else:
        return {"local": "uso geral", "dica": "Monitore o consumo para identificar padrões.", "pulsos": pulsos, "hora": hora}


# ---------- 5. PREVISÃO MENSAL ----------
def prever_consumo_mensal():
    resposta = supabase.table("leituras").select("timestamp, pulsos").execute()
    df = pd.DataFrame(resposta.data)

    if len(df) < 10:
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"], format='ISO8601', utc=True, errors='coerce')
    df = df.dropna(subset=["timestamp"])
    df["data"] = df["timestamp"].dt.date

    consumo_diario = df.groupby("data")["pulsos"].sum().reset_index()

    if len(consumo_diario) < 3:
        return None

    X = np.arange(len(consumo_diario)).reshape(-1, 1)
    y = consumo_diario["pulsos"].values

    modelo = LinearRegression()
    modelo.fit(X, y)

    dias_futuros = np.arange(len(consumo_diario), len(consumo_diario) + 30).reshape(-1, 1)
    previsao = modelo.predict(dias_futuros)

    return {
        "consumo_medio_diario": float(np.mean(y)),
        "previsao_proximo_mes": float(np.sum(previsao)),
        "tendencia": "aumentando" if modelo.coef_[0] > 0 else "diminuindo"
    }


# ---------- 6. FUNÇÃO PRINCIPAL ----------
def analisar_leituras():
    resposta = supabase.table("leituras").select("*").order("timestamp", desc=True).limit(100).execute()
    leituras = resposta.data

    if not leituras:
        return {"erro": "Sem dados"}

    modelo, df_historico = treinar_modelo_anomalias()

    if modelo is None:
        return {"erro": "Modelo não pôde ser treinado"}

    # Mapa de média móvel com timestamp NORMALIZADO
    df_historico["timestamp_norm"] = df_historico["timestamp"].apply(normalizar_timestamp)
    mapa_media_movel = dict(zip(df_historico["timestamp_norm"], df_historico["media_movel"]))

    pulsos_recentes = [l["pulsos"] for l in leituras[:10]]
    media_movel_fallback = sum(pulsos_recentes) / len(pulsos_recentes) if pulsos_recentes else 0

    alertas_gerados = []

    for leitura in leituras:
        timestamp_str = leitura["timestamp"]
        pulsos = leitura["pulsos"]

        try:
            dt = pd.to_datetime(timestamp_str, format='ISO8601', utc=True)
            hora = dt.hour
            dia = dt.day
            dia_semana = dt.dayofweek
            mes = dt.month
            ano = dt.year
        except Exception:
            continue

        # Busca a média móvel usando o timestamp normalizado
        ts_norm = normalizar_timestamp(timestamp_str)
        media_movel = mapa_media_movel.get(ts_norm, media_movel_fallback)

        if not detectar_anomalia_ml(modelo, hora, dia, dia_semana, mes, ano, pulsos, media_movel):
            continue

        classificacao = classificar_gravidade(hora, pulsos)
        if classificacao is None:
            continue

        nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        litros_convertidos = round(pulsos / 450, 2)
        classificacao["mensagem"] = f"{classificacao['mensagem']}: {litros_convertidos} litros em {nomes_dias[dia_semana]}, {dia:02d}/{mes:02d}/{ano} às {hora}h." 
        classificacao["timestamp"] = timestamp_str


        alertas_gerados.append(classificacao)

    for alerta in alertas_gerados:
        try:
            supabase.table("alertas").insert(alerta).execute()
        except Exception as e:
            print(f"[ERRO] Falha ao salvar alerta: {e}")

    return {"total_alertas": len(alertas_gerados), "alertas": alertas_gerados}


# ---------- 7. EXECUÇÃO DIRETA ----------
if __name__ == "__main__":
    resultado = analisar_leituras()
    print(f"Alertas gerados: {resultado.get('total_alertas', 0)}")
    for a in resultado.get("alertas", []):
        print(f"  - [{a['gravidade'].upper()}] {a['mensagem']}")