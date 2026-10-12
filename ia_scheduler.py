# ==========================================
# TCC - AGENDADOR DA IA (Roda a cada 5 min)
# ==========================================

import time
from ia import analisar_leituras

def iniciar_ia():
    print("[IA] Agendador iniciado. Rodando a cada 5 minutos.")
    while True:
        try:
            resultado = analisar_leituras()
            print(f"[IA] Analise concluida: {resultado.get('total_alertas', 0)} alertas gerados")
        except Exception as e:
            print(f"[IA] Erro na analise: {e}")
        time.sleep(300)  # 300 segundos = 5 minutos