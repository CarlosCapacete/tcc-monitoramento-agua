# ==========================================
# TCC - INTELIGÊNCIA ARTIFICIAL (HÍBRIDA AVANÇADA)
# ML é o porteiro, regras classificam gravidade
# ==========================================

import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from db import supabase


# ---------- FUNÇÃO AUXILIAR: Período do dia ----------
def classificar_periodo(hora):
    """Classifica a hora em um período do dia (0-3)."""
    if 0 <= hora <= 5:
        return 0  # Madrugada
    elif 6 <= hora <= 11:
        return 1  # Manhã
    elif 12 <= hora <= 17:
        return 2  # Tarde
    else:
        return 3  # Noite


# ---------- 1. TREINAMENTO DO MODELO ----------
def treinar_modelo_anomalias():
    resposta = supabase.table("leituras").select("timestamp, pulsos").execute()
    df = pd.DataFrame(resposta.data)

    if len(df) < 50:
        print(f"[IA] Dados insuficientes para treinar: {len(df)} leituras")
        return None, None

    # Converte timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], format='ISO8601', utc=True, errors='coerce')
    df = df.dropna(subset=["timestamp"])

    # Extrai features temporais
    df["hora"] = df["timestamp"].dt.hour
    df["dia"] = df["timestamp"].dt.day
    df["dia_semana"] = df["timestamp"].dt.dayofweek
    df["mes"] = df["timestamp"].dt.month
    df["ano"] = df["timestamp"].dt.year
    df["periodo"] = df["hora"].apply(classificar_periodo)

    # Adiciona média móvel (tendência das últimas 10 leituras)
    df["media_movel"] = df["pulsos"].rolling(window=10, min_periods=1).mean()

    # Features para o modelo
    X = df[["hora", "dia", "dia_semana", "mes", "ano", "periodo", "media_movel", "pulsos"]].values

    # Treina o modelo (mais rigoroso: 2% em vez de 5%)
    modelo = IsolationForest(contamination=0.02, random_state=42)
    modelo.fit(X)

    print(f"[IA] Modelo treinado com {len(df)} leituras")
    return modelo, df


# ---------- 2. DETECÇÃO DE ANOMALIA (ML como PORTEIRO) ----------
def detectar_anomalia_ml(modelo, hora, dia, dia_semana, mes, ano, pulsos, media_movel):
    """Retorna True se o ML considerar uma anomalia, False caso contrário."""
    if modelo is None:
        return False

    periodo = classificar_periodo(hora)
    resultado = modelo.predict([[hora, dia, dia_semana, mes, ano, periodo, media_movel, pulsos]])

    # -1 = anomalia, 1 = normal
    return resultado[0] == -1


# ---------- 3. CLASSIFICAÇÃO DE GRAVIDADE (REGRAS) ----------
def classificar_gravidade(hora, pulsos):
    """Classifica a gravidade de uma anomalia já confirmada pelo ML."""

    # Pulsos abaixo de 300 não geram alerta (vão só para leituras)
    if pulsos < 300:
        return None

    # Define a gravidade base
    if pulsos >= 3000:
        gravidade = "critica"
        descricao = "Consumo extremamente alto"
    elif pulsos >= 1000:
        gravidade = "alta"
        descricao = "Consumo muito alto"
    else:  # 300 a 999
        gravidade = "media"
        descricao = "Consumo anormal"

    # Horário de madrugada eleva a gravidade
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


# ---------- 4. RECOMENDAÇÕES PERSONALIZADAS ----------
def gerar_recomendacao(hora, pulsos):
    if 0 <= hora <= 5:
        return {
            "local": "possível vazamento",
            "dica": "Verifique torneiras, descargas e a boia da caixa d'água.",
            "pulsos": pulsos,
            "hora": hora
        }
    elif 6 <= hora <= 9:
        return {
            "local": "banheiro (banho matinal)",
            "dica": "Reduza o tempo de banho em 2 minutos. Economia de ~10 L por banho.",
            "pulsos": pulsos,
            "hora": hora
        }
    elif 12 <= hora <= 14:
        return {
            "local": "cozinha (almoço)",
            "dica": "Feche a torneira ao ensaboar a louça. Economia de ~15 L por lavagem.",
            "pulsos": pulsos,
            "hora": hora
        }
    elif 18 <= hora <= 21:
        return {
            "local": "banheiro (banho noturno)",
            "dica": "Instale um arejador na torneira. Reduz o consumo em até 30%.",
            "pulsos": pulsos,
            "hora": hora
        }
    else:
        return {
            "local": "uso geral",
            "dica": "Monitore o consumo para identificar padrões.",
            "pulsos": pulsos,
            "hora": hora
        }


# ---------- 5. PREVISÃO DE CONSUMO MENSAL ----------
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
    """Analisa as últimas leituras e gera alertas."""
    resposta = supabase.table("leituras").select("*").order("timestamp", desc=True).limit(100).execute()
    leituras = resposta.data

    if not leituras:
        return {"erro": "Sem dados"}

    modelo, df_historico = treinar_modelo_anomalias()

    if modelo is None:
        return {"erro": "Modelo não pôde ser treinado"}

    # Cria um dicionário de média móvel por timestamp para consulta rápida
    df_historico["timestamp_str"] = df_historico["timestamp"].astype(str)
    mapa_media_movel = dict(zip(df_historico["timestamp_str"], df_historico["media_movel"]))

    # Calcula a média móvel das últimas leituras para usar como fallback
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

        # Pega a média móvel do histórico, ou usa o fallback
        media_movel = mapa_media_movel.get(str(dt), media_movel_fallback)

        # ---------- ML COMO PORTEIRO ----------
        # Só considera anomalia se o ML disser que é
        if not detectar_anomalia_ml(modelo, hora, dia, dia_semana, mes, ano, pulsos, media_movel):
            continue  # Se o ML diz que é normal, ignora

        # ---------- REGRAS CLASSIFICAM GRAVIDADE ----------
        classificacao = classificar_gravidade(hora, pulsos)

        if classificacao is None:
            continue  # Pulsos muito baixos, não gera alerta

        # Adiciona o timestamp formatado ao alerta
        nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        classificacao["mensagem"] = f"{classificacao['mensagem']}: {pulsos} pulsos em {nomes_dias[dia_semana]}, {dia:02d}/{mes:02d}/{ano} às {hora}h."
        classificacao["timestamp"] = timestamp_str

        alertas_gerados.append(classificacao)

    # Salva os alertas no Supabase
    for alerta in alertas_gerados:
        try:
            supabase.table("alertas").insert(alerta).execute()
        except Exception as e:
            print(f"[ERRO] Falha ao salvar alerta: {e}")

    return {"total_alertas": len(alertas_gerados), "alertas": alertas_gerados}


# ---------- 7. EXECUÇÃO DIRETA (para testes) ----------
if __name__ == "__main__":
    resultado = analisar_leituras()
    print(f"Alertas gerados: {resultado.get('total_alertas', 0)}")
    for a in resultado.get("alertas", []):
        print(f"  - [{a['gravidade'].upper()}] {a['mensagem']}")