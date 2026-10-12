# ==========================================
# TCC - CONEXÃO COM O SUPABASE
# ==========================================

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis do arquivo .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Usa a service_role para escrita

# Cria o cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def salvar_leitura(timestamp, pulsos):
    """Salva uma leitura no banco de dados."""
    try:
        dados = {
            "timestamp": timestamp,
            "pulsos": pulsos
        }
        resposta = supabase.table("leituras").insert(dados).execute()
        return resposta
    except Exception as e:
        print(f"[ERRO] Falha ao salvar no Supabase: {e}")
        return None