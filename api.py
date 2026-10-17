# ==========================================
# TCC - API REST COM FASTAPI
# Expõe os dados do Supabase para o React
# ==========================================

import threading
import random
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# ⚙️ CONFIGURAÇÕES AJUSTÁVEIS
# =====================================================

PULSOS_POR_LITRO = 450
DIAS_ANALISE = 30
MESES_ANALISE = 12
REFERENCIA_ONU_PESSOA = 110  # litros/pessoa/dia (ONU/OMS)


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def pulsos_para_litros(pulsos):
    return pulsos / PULSOS_POR_LITRO


def buscar_leituras(dias=30):
    agora = datetime.utcnow()
    inicio = agora - timedelta(days=dias)
    resposta = supabase.table("leituras")\
        .select("pulsos, timestamp")\
        .gte("timestamp", inicio.isoformat())\
        .execute()
    return resposta.data


def calcular_meta_automatica(tipo="dia"):
    """Calcula meta automatica baseada no historico + recomendacao ONU."""
    leituras = buscar_leituras(dias=30)

    if not leituras:
        if tipo == "hora":
            return int((REFERENCIA_ONU_PESSOA / 24) * PULSOS_POR_LITRO)
        elif tipo == "dia":
            return int(REFERENCIA_ONU_PESSOA * PULSOS_POR_LITRO)
        else:
            return int(REFERENCIA_ONU_PESSOA * 30 * PULSOS_POR_LITRO)

    pulsos_por_dia = {}
    for l in leituras:
        data = l["timestamp"][:10]
        pulsos_por_dia[data] = pulsos_por_dia.get(data, 0) + l["pulsos"]

    if not pulsos_por_dia:
        return int(REFERENCIA_ONU_PESSOA * PULSOS_POR_LITRO)

    valores = list(pulsos_por_dia.values())
    media_diaria = sum(valores) / len(valores)
    melhor_dia = min(valores)
    meta_diaria = (media_diaria + melhor_dia) / 2

    if tipo == "hora":
        return int(meta_diaria / 24)
    elif tipo == "dia":
        return int(meta_diaria)
    else:
        return int(meta_diaria * 30)


# =====================================================
# ROTAS BÁSICAS
# =====================================================

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/dados/ultimos/{quantidade}")
def get_ultimos(quantidade: int = 10):
    resposta = supabase.table("leituras")\
        .select("*")\
        .order("timestamp", desc=True)\
        .limit(quantidade)\
        .execute()
    return {"dados": resposta.data}


@app.get("/api/estatisticas")
def get_estatisticas():
    resposta = supabase.table("leituras").select("pulsos, timestamp").execute()
    dados = resposta.data

    if not dados:
        return {"erro": "Sem dados"}

    pulsos_lista = [d["pulsos"] for d in dados]

    return {
        "total_leituras": len(dados),
        "pulsos_total": sum(pulsos_lista),
        "pulsos_media": round(sum(pulsos_lista) / len(pulsos_lista), 2),
        "pulsos_max": max(pulsos_lista),
        "pulsos_min": min(pulsos_lista)
    }


@app.get("/api/consumo/hora")
def get_consumo_por_hora():
    agora = datetime.now()
    ontem = agora - timedelta(hours=24)

    resposta = supabase.table("leituras")\
        .select("pulsos, timestamp")\
        .gte("timestamp", ontem.isoformat())\
        .execute()

    por_hora = {}
    for d in resposta.data:
        hora = d["timestamp"][11:13]
        if hora not in por_hora:
            por_hora[hora] = 0
        por_hora[hora] += d["pulsos"]

    return {"consumo_por_hora": por_hora}


@app.get("/api/alertas")
def get_alertas():
    resposta = supabase.table("alertas")\
        .select("*")\
        .order("timestamp", desc=True)\
        .limit(20)\
        .execute()
    return {"alertas": resposta.data}


@app.get("/api/recomendacoes")
def get_recomendacoes():
    from ia import gerar_recomendacao
    agora = datetime.now()
    pulsos = 100
    return gerar_recomendacao(agora.hour, pulsos)


@app.get("/api/previsao")
def get_previsao():
    from ia import prever_consumo_mensal
    resultado = prever_consumo_mensal()
    if resultado is None:
        return {"erro": "Dados insuficientes"}
    return resultado


@app.post("/api/ia/analisar")
def executar_ia():
    from ia import analisar_leituras
    return analisar_leituras()


# =====================================================
# ROTAS DE MÉDIAS (HORA / DIA / MÊS)
# =====================================================

@app.get("/api/media/hora")
def get_media_hora():
    agora = datetime.utcnow()
    leituras = buscar_leituras(dias=DIAS_ANALISE)

    if not leituras:
        return {"erro": "Sem dados no período"}

    total = sum(l["pulsos"] for l in leituras)
    media = total / (DIAS_ANALISE * 24)

    uma_hora_atras = agora - timedelta(hours=1)
    resposta = supabase.table("leituras").select("pulsos")\
        .gte("timestamp", uma_hora_atras.isoformat()).execute()
    atual = sum(l["pulsos"] for l in resposta.data)

    variacao = ((atual - media) / media * 100) if media > 0 else 0
    meta = calcular_meta_automatica("hora")
    percentual_meta = (atual / meta * 100) if meta > 0 else 0

    return {
        "periodo_analise_dias": DIAS_ANALISE,
        "consumo_atual": {"pulsos": atual, "litros": round(pulsos_para_litros(atual), 2)},
        "media_historica": {"pulsos": round(media, 2), "litros": round(pulsos_para_litros(media), 2)},
        "meta_automatica": {"pulsos": meta, "litros": round(pulsos_para_litros(meta), 2)},
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round(percentual_meta, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }


@app.get("/api/media/dia")
def get_media_dia():
    agora = datetime.utcnow()
    leituras = buscar_leituras(dias=DIAS_ANALISE)

    if not leituras:
        return {"erro": "Sem dados no período"}

    total = sum(l["pulsos"] for l in leituras)
    media = total / DIAS_ANALISE

    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    resposta = supabase.table("leituras").select("pulsos")\
        .gte("timestamp", hoje.isoformat()).execute()
    atual = sum(l["pulsos"] for l in resposta.data)

    variacao = ((atual - media) / media * 100) if media > 0 else 0
    meta = calcular_meta_automatica("dia")
    percentual_meta = (atual / meta * 100) if meta > 0 else 0

    return {
        "periodo_analise_dias": DIAS_ANALISE,
        "consumo_atual": {"pulsos": atual, "litros": round(pulsos_para_litros(atual), 2)},
        "media_historica": {"pulsos": round(media, 2), "litros": round(pulsos_para_litros(media), 2)},
        "meta_automatica": {"pulsos": meta, "litros": round(pulsos_para_litros(meta), 2)},
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round(percentual_meta, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }


@app.get("/api/media/mes")
def get_media_mes():
    agora = datetime.utcnow()
    inicio = agora - timedelta(days=365)

    resposta = supabase.table("leituras").select("pulsos, timestamp")\
        .gte("timestamp", inicio.isoformat()).execute()
    dados = resposta.data

    if not dados:
        return {"erro": "Sem dados no período"}

    total = sum(l["pulsos"] for l in dados)
    media = total / MESES_ANALISE

    primeiro_dia = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resposta_atual = supabase.table("leituras").select("pulsos")\
        .gte("timestamp", primeiro_dia.isoformat()).execute()
    atual = sum(l["pulsos"] for l in resposta_atual.data)

    variacao = ((atual - media) / media * 100) if media > 0 else 0
    meta = calcular_meta_automatica("mes")
    percentual_meta = (atual / meta * 100) if meta > 0 else 0

    return {
        "periodo_analise_meses": MESES_ANALISE,
        "consumo_atual": {"pulsos": atual, "litros": round(pulsos_para_litros(atual), 2)},
        "media_historica": {"pulsos": round(media, 2), "litros": round(pulsos_para_litros(media), 2)},
        "meta_automatica": {"pulsos": meta, "litros": round(pulsos_para_litros(meta), 2)},
        "variacao_percentual": round(variacao, 2),
        "percentual_da_meta": round(percentual_meta, 2),
        "status": "acima da media" if variacao > 5 else "abaixo da media" if variacao < -5 else "na media"
    }


# =====================================================
# ROTAS DE DICAS INTELIGENTES
# =====================================================

DICAS_CLICHES = [
    "Feche a torneira enquanto escova os dentes. Economia de até 12 litros por escovação.",
    "Tome banhos de até 5 minutos. Cada minuto a menos economiza cerca de 8 litros.",
    "Verifique se há vazamentos em torneiras, descargas e canos. Um pinga-pinga pode desperdiçar 45 litros por dia.",
    "Use a máquina de lavar apenas com a carga cheia. Cada lavagem economiza até 80 litros.",
    "Reutilize a água da máquina de lavar para limpar o quintal ou calçadas.",
    "Instale arejadores nas torneiras. Reduzem o consumo em até 30%.",
    "Regue as plantas pela manhã ou à noite, evitando a evaporação.",
    "Feche o registro quando for viajar. Evita vazamentos silenciosos.",
    "Prefira vassoura à mangueira para limpar a calçada. Economia de até 200 litros por vez.",
    "Ensaboe toda a louça antes de abrir a torneira para enxaguar.",
]


@app.get("/api/dicas")
def get_dicas():
    agora = datetime.utcnow()
    inicio = agora - timedelta(days=60)

    resposta = supabase.table("leituras").select("pulsos, timestamp")\
        .gte("timestamp", inicio.isoformat()).execute()
    dados = resposta.data

    dicas = []

    # Dicas comparativas
    if dados:
        inicio_mes_atual = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pulsos_mes_atual = sum(l["pulsos"] for l in dados if l["timestamp"] >= inicio_mes_atual.isoformat())

        inicio_mes_anterior = (inicio_mes_atual - timedelta(days=1)).replace(day=1)
        pulsos_mes_anterior = sum(l["pulsos"] for l in dados
                                  if inicio_mes_anterior.isoformat() <= l["timestamp"] < inicio_mes_atual.isoformat())

        if pulsos_mes_anterior > 0:
            variacao = ((pulsos_mes_atual - pulsos_mes_anterior) / pulsos_mes_anterior) * 100

            if variacao > 5:
                dicas.append({
                    "tipo": "comparativa",
                    "mensagem": f"Este mês você consumiu {round(variacao, 1)}% MAIS água que no mês passado. Tente identificar o que mudou na rotina."
                })
            elif variacao < -5:
                dicas.append({
                    "tipo": "comparativa",
                    "mensagem": f"Parabéns! Este mês você consumiu {round(abs(variacao), 1)}% MENOS água que no mês passado. Continue assim!"
                })
            else:
                dicas.append({
                    "tipo": "comparativa",
                    "mensagem": "Seu consumo está estável em relação ao mês passado. Bom trabalho!"
                })

    # Dicas baseadas em alertas
    resposta_alertas = supabase.table("alertas").select("*")\
        .gte("timestamp", (agora - timedelta(days=7)).isoformat())\
        .order("timestamp", desc=True).limit(5).execute()

    alertas_recentes = resposta_alertas.data

    if alertas_recentes:
        criticos = sum(1 for a in alertas_recentes if a["gravidade"] == "critica")
        altos = sum(1 for a in alertas_recentes if a["gravidade"] == "alta")

        if criticos > 0:
            dicas.append({
                "tipo": "alerta",
                "mensagem": f"Foram detectados {criticos} alertas CRÍTICOS nos últimos 7 dias. Verifique urgentemente possíveis vazamentos."
            })
        if altos > 0:
            dicas.append({
                "tipo": "alerta",
                "mensagem": f"Foram detectados {altos} alertas de gravidade alta nos últimos 7 dias. Revise o uso de água."
            })

    # Dicas clichês
    cliches_selecionados = random.sample(DICAS_CLICHES, min(3, len(DICAS_CLICHES)))
    for cliche in cliches_selecionados:
        dicas.append({"tipo": "geral", "mensagem": cliche})

    return {"total_dicas": len(dicas), "dicas": dicas}


# =====================================================
# ROTA DE ALERTA DE CONSUMO EXCESSIVO
# =====================================================

@app.get("/api/alerta-consumo")
def get_alerta_consumo():
    agora = datetime.utcnow()
    leituras = buscar_leituras(dias=30)

    if not leituras:
        return {"erro": "Sem dados suficientes"}

    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    resposta = supabase.table("leituras").select("pulsos")\
        .gte("timestamp", hoje.isoformat()).execute()
    consumo_hoje = sum(l["pulsos"] for l in resposta.data)

    pulsos_por_dia = {}
    for l in leituras:
        data = l["timestamp"][:10]
        if data != hoje.strftime("%Y-%m-%d"):
            pulsos_por_dia[data] = pulsos_por_dia.get(data, 0) + l["pulsos"]

    if not pulsos_por_dia:
        return {"erro": "Sem histórico suficiente"}

    media_diaria = sum(pulsos_por_dia.values()) / len(pulsos_por_dia)

    variacao = ((consumo_hoje - media_diaria) / media_diaria * 100) if media_diaria > 0 else 0

    if variacao > 50:
        alerta = {"nivel": "excessivo", "mensagem": f"⚠️ Você consumiu {round(variacao, 1)}% acima da média. Reduza o consumo.", "recomendacao": "Verifique se há torneiras abertas ou vazamentos."}
    elif variacao > 25:
        alerta = {"nivel": "atencao", "mensagem": f"Você consumiu {round(variacao, 1)}% acima da média. Fique atento.", "recomendacao": "Evite banhos longos e verifique a descarga."}
    elif variacao < -25:
        alerta = {"nivel": "positivo", "mensagem": f"Parabéns! Consumo {round(abs(variacao), 1)}% abaixo da média.", "recomendacao": "Continue com os bons hábitos!"}
    else:
        alerta = {"nivel": "normal", "mensagem": "Seu consumo está dentro do padrão esperado.", "recomendacao": "Mantenha os hábitos conscientes."}

    return {
        "consumo_hoje": {"pulsos": consumo_hoje, "litros": round(pulsos_para_litros(consumo_hoje), 2)},
        "media_diaria": {"pulsos": round(media_diaria, 2), "litros": round(pulsos_para_litros(media_diaria), 2)},
        "variacao_percentual": round(variacao, 2),
        "alerta": alerta
    }


# =====================================================
# INICIALIZAÇÃO
# =====================================================

# Inicia o assinante MQTT em background
threading.Thread(target=iniciar_mqtt, daemon=True).start()
print("[API] Assinante MQTT iniciado em background")

# Inicia o agendador da IA em background
threading.Thread(target=iniciar_ia, daemon=True).start()
print("[API] Agendador da IA iniciado em background")

# =====================================================
# ROTAS DE LISTAS INDIVIDUAIS (PARA GRÁFICOS)
# =====================================================

@app.get("/api/lista/horas")
def get_lista_horas():
    """
    Retorna o consumo de CADA HORA do dia atual.
    Ideal para gráfico de barras de 24 horas.
    """
    from datetime import datetime
    agora = datetime.utcnow()
    inicio_do_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    resposta = supabase.table("leituras")\
        .select("pulsos, timestamp")\
        .gte("timestamp", inicio_do_dia.isoformat())\
        .execute()

    # Inicializa todas as 24 horas com 0
    horas_dict = {f"{i:02d}:00": 0 for i in range(24)}

    # Agrupa os dados reais
    for l in resposta.data:
        # Pega a hora do timestamp (ex: "13")
        hora_str = l["timestamp"][11:13] 
        chave = f"{hora_str}:00"
        if chave in horas_dict:
            horas_dict[chave] += l["pulsos"]

    # Converte para lista (formato que o React adora)
    lista_final = [{"hora": hora, "pulsos": pulsos} for hora, pulsos in horas_dict.items()]
    
    return {"dados": lista_final}


@app.get("/api/lista/dias")
def get_lista_dias():
    """
    Retorna o consumo de CADA DIA do mês atual.
    Ideal para gráfico de linha de acompanhamento diário.
    """
    from datetime import datetime
    agora = datetime.utcnow()
    inicio_do_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    resposta = supabase.table("leituras")\
        .select("pulsos, timestamp")\
        .gte("timestamp", inicio_do_mes.isoformat())\
        .execute()

    # Agrupa por dia (YYYY-MM-DD)
    dias_dict = {}
    for l in resposta.data:
        data_str = l["timestamp"][:10] # Pega "2026-10-17"
        dias_dict[data_str] = dias_dict.get(data_str, 0) + l["pulsos"]

    # Ordena do dia 1 até o dia atual
    lista_final = [{"data": data, "pulsos": pulsos} for data, pulsos in sorted(dias_dict.items())]
    
    return {"dados": lista_final}


if __name__ == "__main__":
    import uvicorn
    print("API rodando em http://localhost:8000")
    print("Documentacao: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)