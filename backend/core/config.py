# -*- coding: utf-8 -*-
"""
Módulo de configuração.

Suporta dois modos de autenticação Google (em ordem de prioridade):
1. Service Account (RECOMENDADO) - arquivo service_account.json
2. OAuth Pessoal (legado) - variáveis no .env

Para distribuição, use sempre Service Account.
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# =============================================================================
# DETECÇÃO DE DIRETÓRIOS
# =============================================================================

def get_base_dir() -> Path:
    """
    Retorna o diretório base da aplicação.
    - Se executável (PyInstaller): pasta onde está o .exe
    - Se script: pasta raiz do projeto
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_internal_dir() -> Path:
    """
    Retorna o diretório interno (onde ficam os arquivos embutidos no exe).
    - Se executável: sys._MEIPASS
    - Se script: pasta raiz do projeto
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


# Diretórios principais
BASE_DIR = get_base_dir()
INTERNAL_DIR = get_internal_dir()

# Carrega .env se existir (para compatibilidade com modo legado)
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Tenta carregar do diretório interno também
    internal_env = INTERNAL_DIR / ".env"
    if internal_env.exists():
        load_dotenv(internal_env)

# =============================================================================
# CONSTANTES
# =============================================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Nomes possíveis para o arquivo de Service Account
SERVICE_ACCOUNT_NAMES = [
    "service_account.json",
    "credentials.json",  # fallback para compatibilidade
]


# =============================================================================
# FUNÇÕES DE CONFIGURAÇÃO
# =============================================================================

def get_service_account_path() -> Optional[Path]:
    """
    Procura o arquivo de Service Account em locais conhecidos.
    Retorna o caminho se encontrado, None caso contrário.
    """
    search_dirs = [BASE_DIR, INTERNAL_DIR]
    
    for directory in search_dirs:
        for filename in SERVICE_ACCOUNT_NAMES:
            path = directory / filename
            if path.exists():
                # Valida se é um Service Account válido
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Service Account tem 'type' = 'service_account'
                    if data.get('type') == 'service_account':
                        return path
                except (json.JSONDecodeError, KeyError):
                    continue
    return None


def has_service_account() -> bool:
    """Verifica se existe um arquivo de Service Account válido."""
    return get_service_account_path() is not None


def get_service_account_info() -> Dict[str, Any]:
    """
    Retorna informações do Service Account para autenticação.
    Levanta erro se não encontrado.
    """
    path = get_service_account_path()
    if not path:
        raise RuntimeError(
            f"Arquivo service_account.json não encontrado.\n"
            f"Procurado em: {BASE_DIR}\n\n"
            f"Para gerar, execute: python setup_service_account.py\n"
            f"Ou baixe do Google Cloud Console e coloque na pasta do executável."
        )
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_sheet_url() -> str:
    """
    Retorna a URL da planilha Google Sheets.
    Busca em ordem: variável de ambiente, .env, ou levanta erro.
    """
    url = os.getenv("SHEET_URL")
    if not url:
        raise RuntimeError(
            "SHEET_URL não definido.\n"
            "Defina no arquivo .env na pasta do executável:\n"
            'SHEET_URL="https://docs.google.com/spreadsheets/d/SEU_ID_AQUI"'
        )
    return url


def get_google_oauth() -> Dict[str, Any]:
    """
    [LEGADO] Retorna credenciais OAuth pessoal do .env.
    
    DEPRECATED: Use Service Account em vez de OAuth pessoal.
    Mantido para compatibilidade com instalações antigas.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    token_uri = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")

    missing = []
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not refresh_token:
        missing.append("GOOGLE_REFRESH_TOKEN")

    if missing:
        raise RuntimeError(
            "Faltam variáveis de ambiente para Google OAuth: " + ", ".join(missing)
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token_uri": token_uri,
    }


def has_oauth_env() -> bool:
    """Verifica se as variáveis OAuth estão definidas no ambiente."""
    return all([
        os.getenv("GOOGLE_CLIENT_ID"),
        os.getenv("GOOGLE_CLIENT_SECRET"),
        os.getenv("GOOGLE_REFRESH_TOKEN"),
    ])


def get_auth_method() -> str:
    """
    Retorna o método de autenticação disponível.
    Prioridade: service_account > oauth > none
    """
    if has_service_account():
        return "service_account"
    if has_oauth_env():
        return "oauth"
    return "none"


def get_perplexity_api_key() -> Optional[str]:
    """Retorna a chave da API Perplexity, se configurada."""
    return os.getenv("PERPLEXITY_API_KEY")


# =============================================================================
# DIAGNÓSTICO
# =============================================================================

def get_config_status() -> Dict[str, Any]:
    """
    Retorna status completo da configuração para diagnóstico.
    Útil para debug e para o frontend mostrar status.
    """
    sa_path = get_service_account_path()
    
    return {
        "base_dir": str(BASE_DIR),
        "internal_dir": str(INTERNAL_DIR),
        "is_frozen": getattr(sys, 'frozen', False),
        "auth_method": get_auth_method(),
        "service_account": {
            "found": sa_path is not None,
            "path": str(sa_path) if sa_path else None,
        },
        "oauth": {
            "configured": has_oauth_env(),
        },
        "sheet_url": {
            "configured": bool(os.getenv("SHEET_URL")),
        },
        "perplexity": {
            "configured": bool(os.getenv("PERPLEXITY_API_KEY")),
        },
        "env_file": {
            "found": env_path.exists(),
            "path": str(env_path),
        },
    }
