# ==========================================
# TCC - ASSINANTE MQTT COM SUPABASE
# ==========================================

import paho.mqtt.client as mqtt
import json
from db import salvar_leitura

# ---------- CONFIGURAÇÕES ----------
BROKER = "broker.emqx.io"
PORTA = 1883
TOPICO = "tcc/agua/pulsos"

# ---------- CALLBACK DE CONEXÃO ----------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[OK] Conectado ao broker {BROKER}")
        print(f"[OK] Assinando o topico: {TOPICO}")
        client.subscribe(TOPICO)
    else:
        print(f"[ERRO] Falha na conexao. Codigo: {rc}")

# ---------- CALLBACK DE MENSAGEM ----------
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        dados = json.loads(payload)

        timestamp = dados.get("timestamp", "0000-00-00T00:00:00")
        pulsos = dados.get("pulsos", 0)

        print(f"[RECEBIDO] {timestamp} | Pulsos: {pulsos}")

        # Salva no Supabase
        salvar_leitura(timestamp, pulsos)
        print(f"[SALVO] Leitura gravada no Supabase")

    except Exception as e:
        print(f"[ERRO] Falha ao processar mensagem: {e}")

# ---------- CONFIGURAÇÃO DO CLIENTE ----------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Conectando ao broker MQTT...")
client.connect(BROKER, PORTA, 60)

print("Aguardando mensagens... (Ctrl+C para parar)")
client.loop_forever()