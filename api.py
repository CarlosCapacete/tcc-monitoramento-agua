# ==========================================
# TCC - API REST COM FASTAPI
# Expõe os dados do Supabase para o React
# ==========================================

import threading
from mqtt_handler import iniciar_mqtt
from ia_scheduler import iniciar_ia

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import supabase
from datetime import datetime, timedelta


app = FastAPI(title="API Monitoramento de Água", version="1.0")

# Permite que o React (em outra porta) acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, troque pelo domínio do React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- ROTA 1: Health Check ----------
@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ---------- ROTA 2: Últimas N leituras ----------
@app.get("/api/dados/ultimos/{quantidade}")
def get_ultimos(quantidade: int = 10):
    resposta = (
        supabase.table("leituras")
        .select("*")
        .order("timestamp", desc=True)
        .limit(quantidade)
        .execute()
    )
    return {"dados": resposta.data}

# ---------- ROTA 3: Estatísticas gerais ----------
@app.get("/api/estatisticas")
def get_estatisticas():
    # Pega todas as leituras
    resposta = supabase.table("leituras").select("pulsos, timestamp").execute()
    dados = resposta.data

    if not dados:
        return {"erro": "Sem dados"}

    pulsos_lista = [d["pulsos"] for d in dados]

    return {
        "total_leituras": len(dados),
        "pulsos_total": sum(pulsos_lista),
        "pulsos_media": round(sum(pulsos_lista) / len(pulsos_lista), 2),
        "pulsos_max": max(pulsos_lista),  "pulsos_min": min(pulsos_lista)
    }

# ---------- ROTA 4: Consumo por hora (últimas 24h) ----------
@app.get("/api/consumo/hora")
def get_consumo_por_hora():
    # Pega leituras das últimas 24 horas
    agora = datetime.now()
    ontem = agora - timedelta(hours=24)

    resposta = (
        supabase.table("leituras")
        .select("pulsos, timestamp")
        .gte("timestamp", ontem.isoformat())
        .execute()
    )

    # Agrupa por hora
    por_hora = {}
    for d in resposta.data:
        hora = d["timestamp"][11:13]  # Pega "HH" do timestamp ISO
        if hora not in por_hora:
            por_hora[hora] = 0
        por_hora[hora] += d["pulsos"]

    return {"consumo_por_hora": por_hora}
# ---------- ROTA 5: Alertas ----------
@app.get("/api/alertas")
def get_alertas():
    resposta = supabase.table("alertas").select("*").order("timestamp", desc=True).limit(20).execute()
    return {"alertas": resposta.data}

# ---------- ROTA 6: Recomendações ----------
@app.get("/api/recomendacoes")
def get_recomendacoes():
    from ia import gerar_recomendacao
    from datetime import datetime

    agora = datetime.now()
    pulsos = 100  # Exemplo
    recomendacao = gerar_recomendacao(agora.hour, pulsos)
    return recomendacao

# ---------- ROTA 7: Previsão Mensal ----------
@app.get("/api/previsao")
def get_previsao():
    from ia import prever_consumo_mensal
    resultado = prever_consumo_mensal()
    if resultado is None:
        return {"erro": "Dados insuficientes"}
    return resultado

# ---------- ROTA 8: Executar Análise da IA ----------
@app.post("/api/ia/analisar")
def executar_ia():
    from ia import analisar_leituras
    return analisar_leituras()


# Inicia o assinante MQTT em background
threading.Thread(target=iniciar_mqtt, daemon=True).start()
print("[API] Assinante MQTT iniciado em background")

# Inicia o agendador da IA em background
threading.Thread(target=iniciar_ia, daemon=True).start()
print("[API] Agendador da IA iniciado em background")

if __name__ == "__main__":
    import uvicorn
    print("API rodando em http://localhost:8000")
    print("Documentacao: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)