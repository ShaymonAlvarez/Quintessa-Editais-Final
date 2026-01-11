@echo off
cd /d "%~dp0"
title Quintessa Editais Watcher - Automacao

echo ==========================================
echo      INICIANDO EDITAIS WATCHER
echo ==========================================
echo.

:: 1. Verificacao do Python
echo [1/6] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 goto ERROR_PYTHON

:: 2. Criacao do VENV
echo [2/6] Verificando Ambiente Virtual (venv)...
if not exist venv (
    echo       Criando pasta venv...
    python -m venv venv
)

:: 3. Ativacao do VENV
echo [3/6] Ativando Ambiente Virtual...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 goto ERROR_VENV

:: 4. Instalacao das Bibliotecas
echo [4/6] Instalando dependencias (aguarde, pode demorar)...
pip install --upgrade pip >nul 2>&1
pip install fastapi uvicorn gspread google-auth google-auth-oauthlib requests feedparser beautifulsoup4 dateparser pytz python-dateutil pandas python-dotenv google-api-python-client cloudscraper curl_cffi playwright
if %errorlevel% neq 0 goto ERROR_PIP

:: 5. Instalacao do Navegador (Playwright)
echo [5/6] Instalando navegador Chromium...
playwright install chromium
if %errorlevel% neq 0 goto ERROR_PLAYWRIGHT

:: 6. Setup de Credenciais (.env)
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado.
    echo         Iniciando assistente de configuracao...
    python setup_oauth_env.py
)

:: 7. Execucao do Servidor
echo.
echo ==========================================
echo    SERVIDOR ONLINE: http://localhost:8000
echo    (Nao feche esta janela enquanto usar)
echo ==========================================
echo.
uvicorn backend.api:app --host 0.0.0.0 --port 8000

echo.
echo [INFO] Servidor finalizado pelo usuario.
pause
exit /b

:: --- BLOCOS DE ERRO (Para voce saber o que aconteceu) ---

:ERROR_PYTHON
echo.
echo [ERRO FATAL] O Python nao foi encontrado.
echo Solucao: Instale o Python (python.org) e marque a opcao 'Add to PATH'.
pause
exit /b

:ERROR_VENV
echo.
echo [ERRO FATAL] Falha ao ativar o ambiente virtual.
echo Solucao: Apague a pasta 'venv' existente e rode este arquivo novamente.
pause
exit /b

:ERROR_PIP
echo.
echo [ERRO FATAL] Falha ao instalar bibliotecas.
echo Solucao: Verifique sua internet e se nao ha bloqueio de firewall.
pause
exit /b

:ERROR_PLAYWRIGHT
echo.
echo [ERRO FATAL] Falha ao instalar o navegador do robo.
echo Tente rodar manualmente: pip install playwright && playwright install chromium
pause
exit /b