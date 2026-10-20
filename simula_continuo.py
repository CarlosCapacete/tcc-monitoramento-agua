import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

BROKER = "broker.emqx.io"
TOPICO = "tcc/agua/pulsos"

client = mqtt.Client()
client.connect(BROKER, 1883, 60)
client.loop_start()

print("--- SIMULANDO VAZAMENTO LENTO (Gotejando) ---")
print("Enviando entre 50 e 150 pulsos por segundo sem parar.")

try:
    while True:
        agora = datetime.now()
        timestamp = agora.strftime("%Y-%m-%dT%H:%M:%S")
        # Gera um valor baixo, entre 50 e 150
        pulsos = random.randint(50, 150)
        
        mensagem = json.dumps({"timestamp": timestamp, "pulsos": pulsos})
        client.publish(TOPICO, mensagem)
        print(f"[GOTEJANDO] {timestamp} | Pulsos: {pulsos}")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nSimulador parado.")
    client.loop_stop()
    client.disconnect()