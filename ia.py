# ==========================================
# TCC - INTELIGÊNCIA ARTIFICIAL
# Detecção de anomalias + Recomendações
# ==========================================

import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from db import supabase

# ---------- 1. VAZAMENTO NOTURNO (Regra Simples) ----------
def detectar_vazamento_noturno(hora, pulsos):
    if 0 <= hora <= 5 and pulsos > 0:
        return {
            "tipo": "possivel_vazamento",
            "mensagem": f"Consumo de {pulsos} pulsos às {hora}h da manhã. Possível vazamento.",
            "gravidade": "alta"
        }
    return None

# ---------- 2. DETECÇÃO DE ANOMALIAS (Isolation Forest) ----------
def treinar_modelo_anomalias():
    resposta = supabase.table("leituras").select("timestamp, pulsos").execute()
    df = pd.DataFrame(resposta.data)

    if len(df) < 50:
        return None, None

    dt = pd.to_datetime(df["timestamp"], format='ISO8601')
    df["hora"] = dt.dt.hour
    df["dia"] = dt.dt.day
    df["dia_semana"] = dt.dt.dayofweek  # 0=Segunda, 6=Domingo
    df["mes"] = dt.dt.month
    df["ano"] = dt.dt.year

    X = df[["hora", "dia", "dia_semana", "mes", "ano", "pulsos"]].values

    modelo = IsolationForest(contamination=0.05, random_state=42)
    modelo.fit(X)
    return modelo, df

def detectar_anomalia(modelo, hora, dia, dia_semana, mes, ano, pulsos):
    if modelo is None:
        return None
    resultado = modelo.predict([[hora, dia, dia_semana, mes, ano, pulsos]])
    if resultado[0] == -1:
        nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        return {
            "tipo": "comportamento_anormal",
            "mensagem": f"Consumo atípico de {pulsos} pulsos em {nomes_dias[dia_semana]}, {dia}/{mes}/{ano} às {hora}h.",
            "gravidade": "media"
        }
  
    return None

# ---------- 3. RECOMENDAÇÕES PERSONALIZADAS ----------
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

# ---------- 4. PREVISÃO DE CONSUMO MENSAL ----------
def prever_consumo_mensal():
    resposta = supabase.table("leituras").select("timestamp, pulsos").execute()
    df = pd.DataFrame(resposta.data)

    if len(df) < 10:
        return None

    df["data"] = pd.to_datetime(df["timestamp"],  format='ISO8601').dt.date
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

# ---------- 5. FUNÇÃO PRINCIPAL ----------

def analisar_leituras():
    """Analisa as últimas leituras e gera alertas."""
    resposta = supabase.table("leituras").select("*").order("timestamp", desc=True).limit(100).execute()
    leituras = resposta.data

    if not leituras:
        return {"erro": "Sem dados"}

    modelo, df = treinar_modelo_anomalias()
    alertas_gerados = []

    for leitura in leituras:
        timestamp_str = leitura["timestamp"]
        pulsos = leitura["pulsos"]
        dt = pd.to_datetime(timestamp_str, format='ISO8601')
        hora = dt.hour
        dia = dt.day
        dia_semana = dt.dayofweek
        mes = dt.month
        ano = dt.year

        # Verifica vazamento noturno
        alerta = detectar_vazamento_noturno(hora, pulsos)
        if alerta:
            alerta["timestamp"] = timestamp_str
            alertas_gerados.append(alerta)

        # Verifica anomalia
        alerta = detectar_anomalia(modelo, hora, dia, dia_semana, mes, ano, pulsos)
        if alerta:
            alerta["timestamp"] = timestamp_str
            alertas_gerados.append(alerta)

    # Salva os alertas no Supabase
    for alerta in alertas_gerados:
        try:
            supabase.table("alertas").insert(alerta).execute()
        except Exception as e:
            print(f"[ERRO] Falha ao salvar alerta: {e}")

    return {"total_alertas": len(alertas_gerados), "alertas": alertas_gerados}

if __name__ == "__main__":
    resultado = analisar_leituras()
    print(f"Alertas gerados: {resultado.get('total_alertas', 0)}")
    for a in resultado.get("alertas", []):
        print(f"  - {a['tipo']}: {a['mensagem']}")