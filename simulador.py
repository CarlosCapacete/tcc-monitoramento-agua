# ==========================================
# TCC - SIMULADOR DE DADOS (Modo Teste Completo)
# Gera pulsos de todas as gravidades para testar
# ==========================================

import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

# ---------- CONFIGURAÇÕES ----------
BROKER = "broker.emqx.io"
PORTA = 1883
TOPICO = "tcc/agua/pulsos"

# ---------- CONEXÃO ----------
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[SIMULADOR] Conectado ao broker {BROKER}")
    else:
        print(f"[SIMULADOR] Falha na conexao: {rc}")

client.on_connect = on_connect
client.connect(BROKER, PORTA, 60)
client.loop_start()

# ---------- FUNÇÃO PARA GERAR PULSOS REALISTAS ----------
def gerar_pulsos(hora):
    """Gera pulsos cobrindo TODAS as gravidades para teste."""
    
    # Sorteia uma faixa para testar todas as gravidades
    faixa = random.choices(
        ["zero", "baixa", "media", "alta", "critica"],
        weights=[20, 15, 25, 25, 15]  # Probabilidades
    )[0]

    if faixa == "zero":
        return 0
    elif faixa == "baixa":
        return random.randint(1, 299)      # Não gera alerta
    elif faixa == "media":
        return random.randint(300, 999)    # Média
    elif faixa == "alta":
        return random.randint(1000, 2999)  # Alta
    else:  # critica
        return random.randint(3000, 8000)  # Crítica

# ---------- LOOP DE PUBLICAÇÃO ----------
print("--- SIMULADOR MODO TESTE INICIADO ---")
print("Gerando pulsos de todas as gravidades...")
print("Pressione Ctrl+C para parar.\n")

try:
    while True:
        agora = datetime.now()
        hora = agora.hour
        timestamp = agora.strftime("%Y-%m-%dT%H:%M:%S")
        pulsos = gerar_pulsos(hora)

        # Monta o JSON
        mensagem = json.dumps({
            "timestamp": timestamp,
            "pulsos": pulsos
        })

        # Publica no MQTT
        client.publish(TOPICO, mensagem)

        # Classifica para mostrar no terminal
        if pulsos == 0:
            tag = "SEM CONSUMO"
        elif pulsos < 300:
            tag = "BAIXO (sem alerta)"
        elif pulsos < 1000:
            tag = "MEDIA"
        elif pulsos < 3000:
            tag = "ALTA"
        else:
            tag = "CRITICA"

        print(f"[{tag}] {timestamp} | Pulsos: {pulsos}")

        # Espera 1 segundo
        time.sleep(1)

except KeyboardInterrupt:
    print("\n[SIMULADOR] Parado pelo usuário.")
    client.loop_stop()
    client.disconnect()