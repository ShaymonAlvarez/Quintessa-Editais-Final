import sys
import os
import webbrowser
import uvicorn
from threading import Timer
from pathlib import Path

# Importamos a interface de linha de comando do Playwright
# (Certifique-se de que 'playwright' continua nos hidden imports)
try:
    from playwright.__main__ import main as playwright_cli
except ImportError:
    playwright_cli = None

# --- CONFIGURAÇÃO DE CAMINHOS ---
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    INTERNAL_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
    INTERNAL_DIR = BASE_DIR

# Define o caminho do log para ficar AO LADO do executável
LOG_PATH = BASE_DIR / "api_debug.log"

# --- REDIRECIONAMENTO DE LOGS ---
# buffering=1 garante escrita imediata
log_file = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

# Adiciona caminho ao path
sys.path.append(str(BASE_DIR))


def check_configuration():
    """
    Verifica se a configuração necessária está presente.
    Retorna (ok, mensagem_erro).
    """
    errors = []
    
    # Verifica service_account.json OU variáveis OAuth no .env
    sa_path = BASE_DIR / "service_account.json"
    env_path = BASE_DIR / ".env"
    
    has_service_account = False
    has_oauth_env = False
    
    if sa_path.exists():
        try:
            import json
            with open(sa_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('type') == 'service_account':
                has_service_account = True
                print(f"[CONFIG] Service Account encontrado: {sa_path}")
        except Exception as e:
            errors.append(f"service_account.json inválido: {e}")
    
    if env_path.exists():
        # Verifica se tem variáveis OAuth
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'GOOGLE_REFRESH_TOKEN' in content:
            has_oauth_env = True
            print("[CONFIG] OAuth via .env encontrado")
    
    if not has_service_account and not has_oauth_env:
        errors.append(
            "Nenhum método de autenticação Google configurado.\n"
            "Coloque o arquivo 'service_account.json' na pasta do executável.\n"
            "Para gerar, execute: python setup_oauth_env.py"
        )
    
    # Verifica SHEET_URL no .env
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'SHEET_URL' not in content:
            errors.append(
                "SHEET_URL não encontrado no arquivo .env\n"
                "Adicione a linha: SHEET_URL=\"sua_url_aqui\""
            )
    else:
        errors.append(
            f"Arquivo .env não encontrado em: {env_path}\n"
            "Crie o arquivo com: SHEET_URL=\"sua_url_aqui\""
        )
    
    # Verifica config.json
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        errors.append(
            f"config.json não encontrado em: {config_path}\n"
            "Este arquivo é necessário para o sistema de login."
        )
    
    if errors:
        return False, "\n\n".join(errors)
    
    return True, ""


try:
    from backend.api import app
except Exception as e:
    print(f"ERRO CRÍTICO NO IMPORT DO APP: {e}")
    import traceback
    traceback.print_exc()
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
    print(f"Diretório Interno: {INTERNAL_DIR}")
    
    # 0. Verifica configuração antes de continuar
    print("\n--- [CONFIG] Verificando configuração ---")
    config_ok, config_error = check_configuration()
    
    if not config_ok:
        print("\n" + "=" * 60)
        print("ERRO DE CONFIGURAÇÃO")
        print("=" * 60)
        print(config_error)
        print("=" * 60)
        print("\nO programa não pode iniciar sem a configuração correta.")
        print("Consulte a documentação ou execute: python setup_oauth_env.py")
        # Mantém o log aberto por um tempo para o usuário ver
        import time
        time.sleep(30)
        log_file.close()
        sys.exit(1)
    
    print("[CONFIG] ✓ Configuração OK!")
    
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
            import traceback
            traceback.print_exc()
    
    log_file.close()