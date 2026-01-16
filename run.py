import sys
import os
import webbrowser
import uvicorn
from threading import Timer

# Importamos a interface de linha de comando do Playwright
# (Certifique-se de que 'playwright' continua nos hidden imports)
try:
    from playwright.__main__ import main as playwright_cli
except ImportError:
    playwright_cli = None

# --- CONFIGURAÇÃO DE CAMINHOS ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define o caminho do log para ficar AO LADO do executável
LOG_PATH = os.path.join(BASE_DIR, "api_debug.log")

# --- REDIRECIONAMENTO DE LOGS ---
# buffering=1 garante escrita imediata
log_file = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

# Adiciona caminho ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.api import app
except Exception as e:
    print(f"ERRO CRÍTICO NO IMPORT DO APP: {e}")
    app = None

def install_playwright_browsers():
    """
    Verifica e instala o navegador Chromium automaticamente na primeira execução.
    Isso evita que o usuário final precise rodar comandos no terminal.
    """
    if playwright_cli is None:
        print("AVISO: Playwright não encontrado nos imports. Pule a instalação.")
        return

    print("--- [AUTO-SETUP] Verificando navegadores Playwright (Chromium) ---")
    print("Isso pode levar alguns minutos na primeira execução...")
    
    # Salva os argumentos originais do sistema (para não confundir o Uvicorn depois)
    old_argv = sys.argv
    try:
        # Simulamos o comando: "playwright install chromium"
        sys.argv = ["playwright", "install", "chromium"]
        playwright_cli()
    except SystemExit:
        # O Playwright tenta fechar o programa ao terminar a instalação.
        # Capturamos esse erro para o programa CONTINUAR rodando.
        pass
    except Exception as e:
        print(f"ERRO na instalação automática do Playwright: {e}")
    finally:
        # Restaura os argumentos originais
        sys.argv = old_argv
        print("--- [AUTO-SETUP] Verificação concluída ---")

def open_browser():
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except:
        pass

if __name__ == "__main__":
    print(f"--- Iniciando API ---")
    print(f"Diretório Base: {BASE_DIR}")
    
    # 1. Tenta instalar/verificar os navegadores ANTES de subir o servidor
    install_playwright_browsers()

    if app is None:
        print("Abortando devido a falha no import do backend.")
    else:
        # 2. Agenda a abertura do navegador
        Timer(1.5, open_browser).start()
        try:
            # 3. Inicia o servidor
            uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
        except Exception as e:
            print(f"ERRO FATAL NO SERVIDOR: {e}")
    
    log_file.close()