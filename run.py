import sys
import os
import webbrowser
import uvicorn
from threading import Timer

# --- CONFIGURAÇÃO DE CAMINHOS ROBUSTA ---
if getattr(sys, 'frozen', False):
    # Se for EXE: A pasta base é onde está o executável .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Se for Script: A pasta base é a pasta do arquivo run.py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define o caminho do log para ficar AO LADO do executável/script
LOG_PATH = os.path.join(BASE_DIR, "api_debug.log")

# --- REDIRECIONAMENTO DE LOGS (Para capturar erros) ---
# O buffering=1 força a escrita linha a linha, vital para ver o erro antes do crash
log_file = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

# Adiciona o caminho atual ao sys.path para imports funcionarem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.api import app
except Exception as e:
    print(f"ERRO CRÍTICO NO IMPORT DO APP: {e}")
    # Não usamos sys.exit aqui para garantir que o log seja salvo
    app = None

def open_browser():
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except:
        pass

if __name__ == "__main__":
    print(f"--- Iniciando API ---")
    print(f"Diretório Base: {BASE_DIR}")
    
    if app is None:
        print("Abortando devido a falha no import do backend.")
    else:
        Timer(1.5, open_browser).start()
        try:
            # log_config=None é essencial para o redirecionamento funcionar no EXE
            uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
        except Exception as e:
            print(f"ERRO FATAL NO SERVIDOR: {e}")
    
    log_file.close()