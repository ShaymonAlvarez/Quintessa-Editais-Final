@echo off
chcp 65001 >nul

:: ============================================================================
:: QUINTESSA EDITAIS - Build do Executavel
:: ============================================================================
:: Localização: output\build.bat
:: Uso: Executar este arquivo para gerar o QuintessaEditais.exe
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

echo [1/4] Verificando PyInstaller...
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

echo [2/4] Limpando builds anteriores...
if exist "%OUTPUT_DIR%build" rmdir /s /q "%OUTPUT_DIR%build"
if exist "%OUTPUT_DIR%dist" rmdir /s /q "%OUTPUT_DIR%dist"

echo [3/4] Gerando executavel (aguarde alguns minutos)...
echo.

pyinstaller --clean --distpath "%OUTPUT_DIR%dist" --workpath "%OUTPUT_DIR%build" "%OUTPUT_DIR%QuintessaEditais.spec"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERRO: Falha na geracao do executavel!
    pause
    exit /b 1
)

echo.
echo [4/4] Organizando arquivos para distribuicao...

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
echo ============================================================
echo    BUILD CONCLUIDO!
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
pause
