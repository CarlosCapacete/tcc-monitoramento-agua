# ==========================================
# TCC - ASSINANTE MQTT (Roda em Background)
# ==========================================

import paho.mqtt.client as mqtt
import json
from db import salvar_leitura

BROKER = "broker.emqx.io"
PORTA = 1883
TOPICO = "tcc/agua/pulsos"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Conectado ao broker {BROKER}")
        client.subscribe(TOPICO)
    else:
        print(f"[MQTT] Falha na conexao: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        dados = json.loads(payload)
        timestamp = dados.get("timestamp")
        pulsos = dados.get("pulsos", 0)
        print(f"[MQTT] Recebido: {timestamp} | Pulsos: {pulsos}")
        salvar_leitura(timestamp, pulsos)
    except Exception as e:
        print(f"[MQTT] Erro: {e}")

def iniciar_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORTA, 60)
    client.loop_forever()