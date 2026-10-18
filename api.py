# ==========================================
# TCC - API REST DEFINITIVA (PENTE FINO)
# ==========================================

import threading
import random
from mqtt_handler import iniciar_mqtt
from ia_scheduler import iniciar_ia

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import supabase
from datetime import datetime, timedelta, timezone


app = FastAPI(title="API Monitoramento de Água", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# ⚙️ CONFIGURAÇÕES E FUNÇÕES AUXILIARES
# =====================================================
PULSOS_POR_LITRO = 450
REFERENCIA_ONU_PESSOA = 110
FUSO_BR = timezone(timedelta(hours=-3))

def to_litros(pulsos):
    return round(pulsos / PULSOS_POR_LITRO, 2)

def calcular_meta_automatica(tipo="dia"):
    if tipo == "hora": return int((REFERENCIA_ONU_PESSOA / 24) * PULSOS_POR_LITRO)
    elif tipo == "dia": return int(REFERENCIA_ONU_PESSOA * PULSOS_POR_LITRO)
    else: return int(REFERENCIA_ONU_PESSOA * 30 * PULSOS_POR_LITRO)

def obter_dados_br():
    """Puxa os dados do banco e converte tudo para o horário de Brasília."""
    agora_br = datetime.now(FUSO_BR)
    inicio_busca = (agora_br - timedelta(days=40)).astimezone(timezone.utc)
    
    resposta = supabase.table("leituras").select("pulsos, timestamp")\
        .gte("timestamp", inicio_busca.isoformat()).execute()
    
    dados_limpos = []
    for l in resposta.data:
        try:
            dt_utc = datetime.fromisoformat(l["timestamp"].replace("Z", "+00:00"))
            dados_limpos.append({"dt_br": dt_utc.astimezone(FUSO_BR), "pulsos": l["pulsos"]})
        except Exception:
            pass
            
    return dados_limpos, agora_br

# =====================================================
# 1. ROTAS DE STATUS E SUPORTE
# =====================================================

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(FUSO_BR).isoformat()}

@app.get("/api/dados/ultimos/{quantidade}")
def get_ultimos(quantidade: int = 10):
    resposta = supabase.table("leituras").select("*").order("timestamp", desc=True).limit(quantidade).execute()
    dados = []
    for d in resposta.data:
        dt_utc = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
        dados.append({"id": d["id"], "timestamp": dt_utc.astimezone(FUSO_BR).isoformat(), "pulsos": to_litros(d["pulsos"])})
    return {"dados": dados}

@app.get("/api/alertas")
def get_alertas():
    resposta = supabase.table("alertas").select("*").order("timestamp", desc=True).limit(20).execute()
    
    alertas_limpos = []
    for a in resposta.data:
        # Extrai o número que está dentro da string da mensagem
        import re
        match = re.search(r'de ([\d.]+)', a["mensagem"])
        valor_numerico = float(match.group(1)) if match else 0.0
        
        alertas_limpos.append({
            "id": a["id"],
            "timestamp": a["timestamp"],
            "tipo": a["tipo"],
            "mensagem": a["mensagem"], 
            "pulsos": valor_numerico, # <-- AQUI! Ele recebe o valor em litros na chave "pulsos"
            "gravidade": a["gravidade"]
        })
        
    return {"alertas": alertas_limpos}
@app.post("/api/ia/analisar")
def executar_ia():
    from ia import analisar_leituras
    return analisar_leituras()

# =====================================================
# 2. ROTAS DE CARDS (HORA / DIA / MÊS)
# =====================================================

@app.get("/api/media/hora")
def get_media_hora():
    dados, agora = obter_dados_br()
    atual = sum(d["pulsos"] for d in dados if d["dt_br"].date() == agora.date() and d["dt_br"].hour == agora.hour)
    
    dias_decorridos = max(1, (agora - (agora - timedelta(days=30))).days)
    media = sum(d["pulsos"] for d in dados) / (dias_decorridos * 24) if dados else 0
    meta = calcular_meta_automatica("hora")
    variacao = ((atual - media) / media * 100) if media > 0 else 0

    return {
        "consumo_atual": to_litros(atual),
        "media_historica": to_litros(media),
        "meta_automatica": to_litros(meta),
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round((atual / meta * 100) if meta > 0 else 0, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }

@app.get("/api/media/dia")
def get_media_dia():
    dados, agora = obter_dados_br()
    atual = sum(d["pulsos"] for d in dados if d["dt_br"].date() == agora.date())
    
    dias_com_dados = set(d["dt_br"].date() for d in dados)
    media = (sum(d["pulsos"] for d in dados) / len(dias_com_dados)) if dias_com_dados else 0
    meta = calcular_meta_automatica("dia")
    variacao = ((atual - media) / media * 100) if media > 0 else 0

    return {
        "consumo_atual": to_litros(atual),
        "media_historica": to_litros(media),
        "meta_automatica": to_litros(meta),
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round((atual / meta * 100) if meta > 0 else 0, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }

@app.get("/api/media/mes")
def get_media_mes():
    dados, agora = obter_dados_br()
    atual = sum(d["pulsos"] for d in dados if d["dt_br"].month == agora.month and d["dt_br"].year == agora.year)
    
    meses_com_dados = set((d["dt_br"].month, d["dt_br"].year) for d in dados)
    media = (sum(d["pulsos"] for d in dados) / len(meses_com_dados)) if meses_com_dados else 0
    meta = calcular_meta_automatica("mes")
    variacao = ((atual - media) / media * 100) if media > 0 else 0

    return {
        "consumo_atual": to_litros(atual),
        "media_historica": to_litros(media),
        "meta_automatica": to_litros(meta),
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round((atual / meta * 100) if meta > 0 else 0, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }

# =====================================================
# 3. ROTAS DE GRÁFICOS (LISTAS)
# =====================================================

@app.get("/api/lista/horas")
def get_lista_horas():
    dados, agora = obter_dados_br()
    dados_hoje = [d for d in dados if d["dt_br"].date() == agora.date()]
    
    horas_dict = {f"{i:02d}:00": 0 for i in range(24)}
    for d in dados_hoje:
        horas_dict[f"{d['dt_br'].hour:02d}:00"] += d["pulsos"]
        
    return {"dados": [{"hora": h, "pulsos": to_litros(p)} for h, p in horas_dict.items()]}

@app.get("/api/lista/dias")
def get_lista_dias():
    dados, agora = obter_dados_br()
    dias_dict = {}
    for d in dados:
        if d["dt_br"].month == agora.month and d["dt_br"].year == agora.year:
            dias_dict[d["dt_br"].strftime("%Y-%m-%d")] = dias_dict.get(d["dt_br"].strftime("%Y-%m-%d"), 0) + d["pulsos"]
            
    return {"dados": [{"data": dt, "pulsos": to_litros(p)} for dt, p in sorted(dias_dict.items())]}

@app.get("/api/lista/meses")
def get_lista_meses():
    dados, agora = obter_dados_br()
    meses_dict = {}
    for d in dados:
        meses_dict[d["dt_br"].strftime("%m/%Y")] = meses_dict.get(d["dt_br"].strftime("%m/%Y"), 0) + d["pulsos"]
        
    return {"dados": [{"mes": m, "pulsos": to_litros(p)} for m, p in sorted(meses_dict.items())]}

# =====================================================
# 4. ROTAS DE FEATURES (DICAS E ALERTAS)
# =====================================================

DICAS_CLICHES = [
    "Feche a torneira enquanto escova os dentes. Economia de até 12 litros.",
    "Tome banhos de até 5 minutos. Economize 8 litros por minuto.",
    "Verifique vazamentos. Um pinga-pinga gasta 45 litros por dia.",
    "Use a máquina de lavar cheia. Economia de 80 litros.",
    "Instale arejadores. Reduz o consumo em 30%.",
]

@app.get("/api/dicas")
def get_dicas():
    cliches = random.sample(DICAS_CLICHES, 3)
    return {"total_dicas": len(cliches), "dicas": [{"tipo": "geral", "mensagem": c} for c in cliches]}

@app.get("/api/alerta-consumo")
def get_alerta_consumo():
    dados, agora = obter_dados_br()
    consumo_hoje = sum(d["pulsos"] for d in dados if d["dt_br"].date() == agora.date())

    pulsos_por_dia = {d["dt_br"].strftime("%Y-%m-%d"): 0 for d in dados if d["dt_br"].date() != agora.date()}
    for d in dados:
        if d["dt_br"].date() != agora.date():
            pulsos_por_dia[d["dt_br"].strftime("%Y-%m-%d")] += d["pulsos"]

    media_diaria = sum(pulsos_por_dia.values()) / len(pulsos_por_dia) if pulsos_por_dia else 0
    variacao = ((consumo_hoje - media_diaria) / media_diaria * 100) if media_diaria > 0 else 0

    if variacao > 50:
        alerta = {"nivel": "excessivo", "mensagem": f"⚠️ Consumo {round(variacao, 1)}% acima da média.", "recomendacao": "Verifique vazamentos."}
    elif variacao > 25:
        alerta = {"nivel": "atencao", "mensagem": f"Consumo {round(variacao, 1)}% acima da média.", "recomendacao": "Evite banhos longos."}
    elif variacao < -25:
        alerta = {"nivel": "positivo", "mensagem": f"Parabéns! Consumo {round(abs(variacao), 1)}% abaixo da média.", "recomendacao": "Continue assim!"}
    else:
        alerta = {"nivel": "normal", "mensagem": "Consumo dentro do padrão.", "recomendacao": "Mantenha os hábitos."}

    return {
        "consumo_hoje": to_litros(consumo_hoje),
        "media_diaria": to_litros(media_diaria),
        "variacao_percentual": round(variacao, 2),
        "alerta": alerta
    }

# =====================================================
# INICIALIZAÇÃO
# =====================================================
threading.Thread(target=iniciar_mqtt, daemon=True).start()
threading.Thread(target=iniciar_ia, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    print("API rodando em http://localhost:8000")
    print("Documentacao: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)