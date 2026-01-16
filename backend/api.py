from __future__ import annotations
import sys
import requests
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from passlib.context import CryptContext

# Importações existentes do seu projeto
from .core.errors import init_error_bus, get_errors
from .core.domain import (
    get_app_config, update_config_pairs, update_group_regex,
    run_collect, get_items_for_group, update_items,
    delete_items_by_uids, clear_all_items, get_diag_providers,
)
from .core.perplexity_core import call_perplexity_chat, count_tokens_from_url

# --- CONFIGURAÇÃO DE SEGURANÇA ---
# URL do seu JSON (Gist RAW)
USERS_DB_URL = "https://gist.githubusercontent.com/amandarosab/32a9b4bf6b2f523d78962667fd63759e/raw/users.json"
SECRET_COOKIE_NAME = "quintessa_session"
# Contexto de criptografia para verificar as senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- AJUSTE DE CAMINHOS PARA EXECUTÁVEL (PyInstaller) ---
if getattr(sys, 'frozen', False):
    # Se estiver rodando como EXE, a pasta temporária é sys._MEIPASS
    ROOT_DIR = Path(sys._MEIPASS)
else:
    # Se estiver rodando como script normal
    ROOT_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="Automação de editais", version="1.0.0")

# Servir arquivos estáticos (CSS/JS)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

# --- LÓGICA DE AUTENTICAÇÃO ---

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_remote_users():
    """Baixa o JSON de usuários atualizado."""
    try:
        resp = requests.get(USERS_DB_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("users", [])
    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
        return []

@app.post("/api/login")
async def login(email: str = Form(...), password: str = Form(...)):
    """Recebe email/senha, busca no JSON remoto e valida."""
    users = get_remote_users()
    
    user_found = next((u for u in users if u["email"] == email), None)
    
    if not user_found or not verify_password(password, user_found["password_hash"]):
        return JSONResponse(
            status_code=401, 
            content={"detail": "E-mail ou senha incorretos."}
        )
    
    # Login sucesso: Define cookie
    response = JSONResponse(content={"message": "Sucesso", "redirect": "/app"})
    response.set_cookie(key=SECRET_COOKIE_NAME, value="authenticated", httponly=True)
    return response

@app.get("/api/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(SECRET_COOKIE_NAME)
    return response

# --- ROTAS DE PÁGINA (Protegidas) ---

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Tela de Login (antiga home, mas agora dedicada a login)."""
    # Se já estiver logado, manda pro app direto
    if request.cookies.get(SECRET_COOKIE_NAME) == "authenticated":
         return RedirectResponse(url="/app")

    login_path = FRONTEND_DIR / "login.html"
    if not login_path.exists():
        return HTMLResponse("<h1>Erro: login.html não encontrado.</h1>", status_code=500)
    return login_path.read_text(encoding="utf-8")

@app.get("/app", response_class=HTMLResponse)
async def app_shell(request: Request):
    """Aplicação Principal (Protegida)."""
    # Verificação de segurança simples para app local
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        return RedirectResponse(url="/")

    index_path = FRONTEND_DIR / "index.html" # A antiga tela principal vira index.html ou home.html interna
    # NOTA: O arquivo que o usuário chamou de 'frontend/home.html' parecia ser a landing page.
    # Vou assumir que o sistema principal é o 'index.html' mencionado no seu código original.
    
    if not index_path.exists():
        # Fallback se não existir index, tenta home
        index_path = FRONTEND_DIR / "home.html"
        
    return index_path.read_text(encoding="utf-8")

# ... (MANTENHA AQUI PARA BAIXO TODOS OS SEUS MODELOS PYDANTIC E OUTROS ENDPOINTS /api/config, etc.) ...
# ... (O restante do código do api.py original deve ser mantido para o sistema funcionar) ...

# Cole aqui as classes Pydantic (ConfigUpdateItem, etc) e os endpoints api_get_config, api_collect...
# Certifique-se apenas de importar BaseModel e List no topo.