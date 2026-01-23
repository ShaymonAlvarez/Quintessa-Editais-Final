# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File - Quintessa Editais

Localização: output/QuintessaEditais.spec
Uso: pyinstaller --clean QuintessaEditais.spec
"""

import os
import sys
from pathlib import Path

# Diretório do .spec (output/)
SPEC_DIR = Path(SPECPATH)

# Diretório do projeto (pasta pai)
PROJECT_DIR = SPEC_DIR.parent

# Detecta o ícone se existir
icon_path = PROJECT_DIR / 'editais.ico'
ICON = str(icon_path) if icon_path.exists() else None

# Lista completa de Hidden Imports
hidden_imports = [
    # ===== Servidor & API =====
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'engineio.async_drivers.asgi',
    'fastapi',
    'fastapi.applications',
    'fastapi.routing',
    'fastapi.middleware',
    'fastapi.staticfiles',
    'fastapi.responses',
    'starlette',
    'starlette.applications',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.middleware.errors',
    'starlette.staticfiles',
    'python-multipart',
    'multipart',
    
    # ===== Login & Segurança =====
    'passlib',
    'passlib.context',
    'passlib.handlers',
    'passlib.handlers.argon2',
    'passlib.handlers.bcrypt',
    'argon2',
    'argon2._password_hasher',
    'argon2.low_level',
    'argon2_cffi',
    'argon2_cffi_bindings',
    'argon2_cffi_bindings._ffi',
    
    # ===== Google Sheets & Auth (Service Account + OAuth) =====
    'gspread',
    'gspread.auth',
    'gspread.client',
    'gspread.spreadsheet',
    'gspread.worksheet',
    'gspread.utils',
    'gspread.exceptions',
    'google',
    'google.auth',
    'google.auth.credentials',
    'google.auth.exceptions',
    'google.auth.transport',
    'google.auth.transport.requests',
    'google.auth.transport._http_client',
    'google.oauth2',
    'google.oauth2.credentials',
    'google.oauth2.service_account',
    'google.oauth2._client',
    'googleapiclient',
    'googleapiclient.discovery',
    'googleapiclient.http',
    'googleapiclient.errors',
    'rsa',
    'rsa.key',
    'pyasn1',
    'pyasn1.codec',
    'pyasn1.codec.der',
    'pyasn1.type',
    'pyasn1_modules',
    'pyasn1_modules.rfc2459',
    'cachetools',
    
    # ===== Web Scraping & Data =====
    'requests',
    'requests.adapters',
    'requests.auth',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'certifi',
    'charset_normalizer',
    'idna',
    'dateparser',
    'dateparser.data',
    'dateparser.languages',
    'dateparser.search',
    'dateparser.date',
    'dateparser.conf',
    'regex',
    'regex._regex',
    'bs4',
    'bs4.builder',
    'bs4.element',
    'lxml',
    'lxml.etree',
    'lxml.html',
    'lxml._elementpath',
    'playwright',
    'playwright.sync_api',
    'playwright.async_api',
    'playwright._impl',
    'playwright._impl._api_types',
    
    # ===== Processamento & Utilidades =====
    'pandas',
    'pandas.io',
    'pandas.io.json',
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
    'tzdata',
    'tzlocal',
    'zoneinfo',
    'encodings',
    'encodings.utf_8',
    'encodings.latin_1',
    'encodings.cp1252',
    'json',
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.message',
    'email.parser',
    
    # ===== Dotenv =====
    'dotenv',
    'python-dotenv',
    
    # ===== Pydantic (FastAPI) =====
    'pydantic',
    'pydantic.fields',
    'pydantic.main',
    'pydantic.types',
    'pydantic_core',
    'pydantic_core._pydantic_core',
    
    # ===== Async =====
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    'h11',
    'httpcore',
    'httpx',
]

# Arquivos de dados a incluir (caminhos relativos ao PROJECT_DIR)
datas = [
    (str(PROJECT_DIR / 'backend'), 'backend'),
    (str(PROJECT_DIR / 'frontend'), 'frontend'),
    (str(PROJECT_DIR / 'providers'), 'providers'),
    (str(PROJECT_DIR / 'setup_oauth_env.py'), '.'),
]

# Dados adicionais de pacotes
collect_data = [
    'dateparser',
    'tzdata',
    'certifi',
    'gspread',
]

# Configuração da análise
a = Analysis(
    [str(PROJECT_DIR / 'run.py')],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
    ],
    noarchive=False,
    optimize=0,
)

# Coleta dados adicionais dos pacotes
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

for pkg in collect_data:
    try:
        a.datas += collect_data_files(pkg)
    except Exception as e:
        print(f"[AVISO] Não foi possível coletar dados de {pkg}: {e}")

# Adiciona submódulos do dateparser (tem muitos)
try:
    a.hiddenimports += collect_submodules('dateparser')
except:
    pass

# Empacotamento
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QuintessaEditais',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compressão (reduz tamanho)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Window Based (sem console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

# Informações do build
print("\n" + "=" * 60)
print("  QUINTESSA EDITAIS - BUILD")
print("=" * 60)
print(f"  Spec: {SPEC_DIR}")
print(f"  Projeto: {PROJECT_DIR}")
print(f"  Icone: {ICON if ICON else 'Nenhum'}")
print(f"  Hidden Imports: {len(hidden_imports)}")
print(f"  Arquivos de Dados: {len(datas)}")
print("=" * 60 + "\n")
