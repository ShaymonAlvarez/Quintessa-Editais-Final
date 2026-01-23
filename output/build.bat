@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================================
:: QUINTESSA EDITAIS - Build do Executavel
:: ============================================================================

echo.
echo ============================================================
echo    QUINTESSA EDITAIS - Build do Executavel
echo ============================================================
echo.

:: Define diretórios
set "OUTPUT_DIR=%~dp0"
set "PROJECT_DIR=%OUTPUT_DIR%.."
cd /d "%PROJECT_DIR%"

echo Diretorio do projeto: %PROJECT_DIR%
echo.

:: ============================================================================
:: DETECTA O PYTHON
:: ============================================================================
echo [0/5] Detectando Python...

set "PYTHON_CMD="
set "VENV_DIR=%PROJECT_DIR%\venv"

:: Primeiro tenta o venv local
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
    echo    Usando venv local: !PYTHON_CMD!
    goto :python_found
)

:: Tenta python no PATH
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%i in ('where python') do (
        set "PYTHON_CMD=%%i"
        goto :check_python
    )
)

:: Tenta py launcher
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py"
    echo    Usando py launcher
    goto :python_found
)

:: Tenta caminhos comuns
for %%P in (
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        goto :check_python
    )
)

echo.
echo ERRO: Python nao encontrado!
echo Instale Python 3.10+ de https://www.python.org/downloads/
pause
exit /b 1

:check_python
:: Verifica se o Python encontrado funciona
"!PYTHON_CMD!" --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo    Python em !PYTHON_CMD! nao funciona, tentando outro...
    set "PYTHON_CMD="
    goto :python_found
)

:python_found
if "!PYTHON_CMD!"=="" (
    echo ERRO: Nenhum Python valido encontrado!
    pause
    exit /b 1
)

echo    Python: !PYTHON_CMD!
"!PYTHON_CMD!" --version
echo.

:: ============================================================================
:: INSTALA PYINSTALLER
:: ============================================================================
echo [1/5] Verificando PyInstaller...

"!PYTHON_CMD!" -m pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo    Instalando PyInstaller...
    "!PYTHON_CMD!" -m pip install --user pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo    Tentando sem --user...
        "!PYTHON_CMD!" -m pip install pyinstaller
    )
)

:: Verifica se PyInstaller está disponível
"!PYTHON_CMD!" -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERRO: PyInstaller nao foi instalado corretamente!
    echo Tente manualmente: python -m pip install pyinstaller
    pause
    exit /b 1
)

echo    PyInstaller OK!
echo.

:: ============================================================================
:: LIMPA BUILDS ANTERIORES
:: ============================================================================
echo [2/5] Limpando builds anteriores...
if exist "%OUTPUT_DIR%build" rmdir /s /q "%OUTPUT_DIR%build"
if exist "%OUTPUT_DIR%dist" rmdir /s /q "%OUTPUT_DIR%dist"

:: ============================================================================
:: GERA O EXECUTAVEL
:: ============================================================================
echo [3/5] Gerando executavel (aguarde alguns minutos)...
echo.

"!PYTHON_CMD!" -m PyInstaller --clean --distpath "%OUTPUT_DIR%dist" --workpath "%OUTPUT_DIR%build" "%OUTPUT_DIR%QuintessaEditais.spec"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo    ERRO: Falha na geracao do executavel!
    echo ============================================================
    echo.
    echo Verifique se todas as dependencias estao instaladas:
    echo    python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo [4/5] Organizando arquivos para distribuicao...

if not exist "%OUTPUT_DIR%distribuicao" mkdir "%OUTPUT_DIR%distribuicao"

:: Copia executável
copy "%OUTPUT_DIR%dist\QuintessaEditais.exe" "%OUTPUT_DIR%distribuicao\" >nul
echo    + QuintessaEditais.exe

:: Copia configurações da raiz do projeto
if exist "%PROJECT_DIR%\config.json" (
    copy "%PROJECT_DIR%\config.json" "%OUTPUT_DIR%distribuicao\" >nul
    echo    + config.json
)
if exist "%PROJECT_DIR%\service_account.json" (
    copy "%PROJECT_DIR%\service_account.json" "%OUTPUT_DIR%distribuicao\" >nul
    echo    + service_account.json
)
if exist "%PROJECT_DIR%\.env" (
    copy "%PROJECT_DIR%\.env" "%OUTPUT_DIR%distribuicao\" >nul
    echo    + .env
)

echo.
echo [5/5] Concluido!
echo.
echo ============================================================
echo    BUILD CONCLUIDO COM SUCESSO!
echo ============================================================
echo.
echo Pasta de saida: %OUTPUT_DIR%distribuicao\
echo.
echo Para distribuir, envie TODA a pasta com:
echo    - QuintessaEditais.exe
echo    - config.json
echo    - service_account.json
echo    - .env
echo.
echo ============================================================

explorer "%OUTPUT_DIR%distribuicao"

endlocal
pause
