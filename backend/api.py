from __future__ import annotations
import sys
import requests
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from passlib.context import CryptContext

# Importações existentes do seu projeto
from .core.errors import init_error_bus, get_errors, push_error
from .core.domain import (
    get_app_config, update_config_pairs, update_group_regex,
    run_collect, get_items_for_group, update_items,
    delete_items_by_uids, clear_all_items, get_diag_providers,
)
from .core.perplexity_core import call_perplexity_chat, count_tokens_from_url
from .core.sheets import read_links, add_link, update_link, delete_link
from .core.universal_extractor import extract_from_url, extract_from_links
from .core.providers_loader import clear_groups_cache
# --- AJUSTE DE CAMINHOS PARA EXECUTÁVEL (PyInstaller) ---
# --- AJUSTE DE CAMINHOS PARA EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    # Se estiver rodando como EXE:
    
    # 1. Arquivos embutidos (Frontend, templates) ficam na pasta temporária (_MEIPASS)
    INTERNAL_DIR = Path(sys._MEIPASS)
    
    # 2. Arquivos externos (config.json) ficam na mesma pasta do arquivo .exe
    EXTERNAL_DIR = Path(sys.executable).parent
else:
    # Se estiver rodando como script normal (python api.py)
    INTERNAL_DIR = Path(__file__).resolve().parent.parent
    EXTERNAL_DIR = INTERNAL_DIR

ROOT_DIR = INTERNAL_DIR # Mantemos compatibilidade se usar ROOT_DIR em outros lugares para coisas internas

# --- CONFIGURAÇÃO DE SEGURANÇA ---
def load_config():
    """Carrega a URL do banco de usuários do config.json (EXTERNO)"""
    try:
        # Agora buscamos no EXTERNAL_DIR (ao lado do executável)
        config_path = EXTERNAL_DIR / "config.json"
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("users_db_url", "")
        else:
            print(f"[AVISO] config.json não encontrado em: {config_path}")
    except Exception as e:
        print(f"Erro ao carregar config.json: {e}")
    return ""

USERS_DB_URL = load_config()
if not USERS_DB_URL:
    print("[AVISO] USERS_DB_URL não configurada em config.json")

SECRET_COOKIE_NAME = "quintessa_session"
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

FRONTEND_DIR = INTERNAL_DIR / "frontend"

app = FastAPI(title="Editais Watcher API", version="1.0.0")

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
        try:
            data = resp.json()
        except ValueError as e:
            print(f"Erro ao parsear JSON de {USERS_DB_URL}: {e}")
            print("Resposta (primeiros 1000 chars):", resp.text[:1000])
            return []
        # Aceita {"users": [...]} ou {"usuarios": [...]} ou lista direta [...]
        if isinstance(data, dict):
            for key in ("users", "usuarios"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Se for um dict com exatamente uma chave cujo valor é lista, retorna essa lista
            list_values = [v for v in data.values() if isinstance(v, list)]
            if len(list_values) == 1:
                return list_values[0]
        if isinstance(data, list):
            return data
        # Formato inesperado — log keys/type para debug
        if isinstance(data, dict):
            print("DEBUG: remote JSON keys:", list(data.keys()))
        else:
            print("DEBUG: remote JSON type:", type(data))
        print("DEBUG: remote JSON preview:", str(data)[:500])
        return []
    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
        return []

@app.post("/api/login")
async def login(email: str = Form(...), password: str = Form(...)):
    users = get_remote_users()
    print("DEBUG: loaded users count:", len(users))  # temporary
    user_found = next((u for u in users if u.get("email","").strip() == email.strip()), None)
    print("DEBUG: user_found keys:", list(user_found.keys()) if user_found else None)
    if not user_found:
        return JSONResponse(status_code=401, content={"detail": "E-mail ou senha incorretos."})

    stored_hash = str(user_found.get("password_hash", "")).strip()
    print("DEBUG: stored_hash preview:", stored_hash[:6], "...")  # do NOT log full hash in production
    scheme = pwd_context.identify(stored_hash)
    print("DEBUG: detected scheme:", scheme)

    try:
        ok = pwd_context.verify(password, stored_hash)
    except Exception as e:
        print("DEBUG: verify raised:", repr(e))
        return JSONResponse(status_code=500, content={"detail": "Erro interno ao verificar senha."})

    if not ok:
        return JSONResponse(status_code=401, content={"detail": "E-mail ou senha incorretos."})

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

# ---------- MODELOS Pydantic (requests) ----------
class ConfigUpdateItem(BaseModel):
    key: str
    value: str


class ConfigUpdateRequest(BaseModel):
    updates: List[ConfigUpdateItem]


class CollectRequest(BaseModel):
    groups: Optional[List[str]] = None
    min_days: Optional[int] = None


class ItemsUpdateItem(BaseModel):
    uid: str
    seen: bool = False
    status: str = "pendente"
    notes: str = ""
    do_not_show: bool = False


class ItemsUpdateRequest(BaseModel):
    updates: List[ItemsUpdateItem]

class ItemsDeleteRequest(BaseModel):
    uids: List[str]


class DiagRequest(BaseModel):
    re_gov: str = ""
    re_funda: str = ""
    re_coorp: str = ""
    re_latam: str = ""


# ============= MODELOS PARA LINKS CADASTRADOS =============

class LinkCreateRequest(BaseModel):
    url: str
    grupo: str
    nome: str = ""


class LinkUpdateRequest(BaseModel):
    url: Optional[str] = None
    grupo: Optional[str] = None
    nome: Optional[str] = None
    ativo: Optional[str] = None


class PerplexityRequest(BaseModel):
    prompt: str
    modelo_api: str
    modo_label: str
    temperature: float
    max_tokens: int
    pricing_in: float
    pricing_out: float
    usd_brl: float
    save: bool = True
    edital_link: Optional[str] = None
    edital_pages: Optional[int] = None
    link_tokens: Optional[int] = 0


class TokenCountRequest(BaseModel):
    url: str


# ============= MODELO PARA COLETA UNIVERSAL =============

class UniversalCollectRequest(BaseModel):
    """Requisição para coleta universal usando links cadastrados."""
    min_days: int = 0
    max_value: Optional[float] = None
    model_id: str = "sonar"
    link_uid: Optional[str] = None  # Se fornecido, coleta só esse link


#---------- ENDPOINTS DE CONFIG ----------
@app.get("/api/config")
async def api_get_config(request: Request):
    """
    Retorna configuração geral (aba config, regex por grupo, grupos disponíveis, status, cores).
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")

    init_error_bus()
    cfg = get_app_config()
    return {
        "config": cfg,
        "errors": get_errors(),
    }


@app.post("/api/config")
async def api_update_config(request: Request, req: ConfigUpdateRequest):
    """
    Atualiza múltiplas chaves na aba 'config'.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")

    init_error_bus()
    cfg = update_config_pairs(
        [{"key": item.key, "value": item.value} for item in req.updates]
    )
    return {
        "config": cfg,
        "errors": get_errors(),
    }


@app.post("/api/group/regex")
async def api_update_group_regex(request: Request, payload: Dict[str, Any]):
    """
    Atualiza o regex de um grupo específico.

    Body esperado: { "group": "...", "regex": "..." }
    """

    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")

    group = payload.get("group")
    regex = payload.get("regex", "")
    if not group:
        raise HTTPException(status_code=400, detail="Campo 'group' é obrigatório.")

    init_error_bus()
    cfg = update_group_regex(group, regex)
    return {
        "config": cfg,
        "errors": get_errors(),
    }


# ---------- ENDPOINTS DE ITENS / COLETA ----------


@app.post("/api/collect")
async def api_collect(request: Request, req: CollectRequest):
    """
    Executa coleta de providers, grava na planilha e retorna estatísticas.

    - groups: lista de grupos a coletar (ou None para todos)
    - min_days: opcional; se None, usa valor salvo em config.MIN_DAYS (ou default)
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")

    init_error_bus()
    cfg = get_app_config()["config"]
    if req.min_days is not None:
        min_days = int(req.min_days)
    else:
        min_days = int(cfg.get("MIN_DAYS", "21"))

    result = run_collect(min_days=min_days, groups_filter=req.groups)
    return {
        "result": result,
        "errors": get_errors(),
    }


# ============= ENDPOINT DE COLETA UNIVERSAL (VIA IA) =============

@app.post("/api/collect/universal")
async def api_collect_universal(request: Request, req: UniversalCollectRequest):
    """
    Executa coleta universal usando IA (Perplexity) nos links cadastrados.
    
    Esta é a coleta inteligente que extrai editais de qualquer site
    usando processamento de linguagem natural.
    
    - min_days: prazo mínimo em dias para filtrar editais
    - max_value: valor máximo em R$ (opcional)
    - model_id: modelo Perplexity (sonar, sonar-pro, etc)
    - link_uid: se fornecido, coleta apenas este link específico
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    init_error_bus()
    
    # Carrega links cadastrados
    links = read_links()
    
    if not links:
        return {
            "result": {
                "all_items": [],
                "stats_by_group": {},
                "errors": [],
                "processed": 0,
                "total": 0,
                "message": "Nenhum link cadastrado para coleta."
            },
            "errors": get_errors(),
        }
    
    # Se link_uid fornecido, filtra para coletar só esse
    if req.link_uid:
        links = [l for l in links if l.get("uid") == req.link_uid]
        if not links:
            raise HTTPException(status_code=404, detail="Link não encontrado")
    
    # Carrega regex por grupo da config
    cfg = get_app_config()
    regex_by_group = cfg.get("regex_by_group", {})
    
    # Executa extração
    result = extract_from_links(
        links=links,
        min_days=req.min_days,
        regex_by_group=regex_by_group,
        max_value=req.max_value,
        model_id=req.model_id,
    )
    
    # Se encontrou itens, grava na planilha
    if result.get("all_items"):
        from .core.domain import add_row, sha_id
        from .core.sheets import open_sheet, append_items_dedup, read_items_cached, invalidate_items_cache
        
        try:
            _, _, _, ws_items, _ = open_sheet()
            header, body = read_items_cached()
            
            new_rows = []
            for item in result["all_items"]:
                row = [
                    sha_id(
                        item.get("group", ""),
                        item.get("source", ""),
                        item.get("title", ""),
                        item.get("link", ""),
                    ),
                    item.get("group", ""),
                    item.get("source", ""),
                    item.get("title", ""),
                    item.get("link", ""),
                    item.get("deadline", ""),
                    item.get("published", ""),
                    item.get("agency", ""),
                    "",  # region
                    "{}",  # raw_json
                    "",  # created_at será preenchido
                    "",  # seen
                    "pendente",  # status
                    item.get("description", ""),  # notes
                    "",  # do_not_show
                ]
                new_rows.append(row)
            
            if new_rows:
                from datetime import datetime
                for row in new_rows:
                    row[10] = datetime.utcnow().isoformat()  # created_at
                
                append_items_dedup(ws_items, header, body, new_rows)
                result["items_saved"] = len(new_rows)
        except Exception as e:
            push_error("api_collect_universal_save", e)
            result["save_error"] = str(e)
    
    return {
        "result": result,
        "errors": get_errors(),
    }


@app.get("/api/items")
async def api_get_items(request: Request, group: str, status: Optional[str] = None):
    """
    Retorna itens de um grupo, agrupados por fonte, com filtro opcional de status.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")

    init_error_bus()
    data = get_items_for_group(group, status_filter=status)
    return {
        "items": data,
        "errors": get_errors(),
    }


@app.post("/api/items/update")
async def api_update_items(request: Request, req: ItemsUpdateRequest):
    """
    Aplica atualizações em itens (seen, status, notes, do_not_show) com base em uid.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    init_error_bus()
    updates_dicts = [item.dict() for item in req.updates]
    result = update_items(updates_dicts)
    return {
        "result": result,
        "errors": get_errors(),
    }


@app.post("/api/items/delete")
async def api_delete_items(request: Request, req: ItemsDeleteRequest):
    """
    Remove itens da planilha a partir de uma lista de uids.
    """

    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    result = delete_items_by_uids(req.uids)
    return {
        "result": result,
        "errors": get_errors(),
    }


@app.post("/api/items/clear")
async def api_clear_items(request: Request):
    """
    Limpa todos os itens (mantém apenas o cabeçalho).
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    result = clear_all_items()
    return {
        "result": result,
        "errors": get_errors(),
    }


# ============= ENDPOINTS DE LINKS CADASTRADOS (COLETA UNIVERSAL) =============

@app.get("/api/links")
async def api_get_links(request: Request):
    """
    Retorna todos os links cadastrados para coleta universal.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    init_error_bus()
    links = read_links()
    return {
        "links": links,
        "errors": get_errors(),
    }


@app.post("/api/links")
async def api_add_link(request: Request, req: LinkCreateRequest):
    """
    Adiciona um novo link para coleta universal.
    
    Body esperado: { "url": "...", "grupo": "...", "nome": "..." }
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    if not req.url:
        raise HTTPException(status_code=400, detail="URL é obrigatório")
    if not req.grupo:
        raise HTTPException(status_code=400, detail="Grupo é obrigatório")
    
    init_error_bus()
    try:
        link = add_link(req.url, req.grupo, req.nome)
        clear_groups_cache()  # Limpa cache para refletir novo grupo
        return {
            "link": link,
            "errors": get_errors(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/links/{uid}")
async def api_update_link(request: Request, uid: str, req: LinkUpdateRequest):
    """
    Atualiza um link existente.
    
    Path: /api/links/{uid}
    Body: campos a atualizar (url, grupo, nome, ativo)
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    init_error_bus()
    
    # Monta dict apenas com campos fornecidos
    updates = {}
    if req.url is not None:
        updates["url"] = req.url
    if req.grupo is not None:
        updates["grupo"] = req.grupo
    if req.nome is not None:
        updates["nome"] = req.nome
    if req.ativo is not None:
        updates["ativo"] = req.ativo
    
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    success = update_link(uid, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Link não encontrado")
    
    clear_groups_cache()  # Limpa cache caso grupo tenha sido alterado
    
    return {
        "success": True,
        "errors": get_errors(),
    }


@app.delete("/api/links/{uid}")
async def api_delete_link(request: Request, uid: str):
    """
    Remove um link cadastrado.
    
    Path: /api/links/{uid}
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    init_error_bus()
    
    success = delete_link(uid)
    if not success:
        raise HTTPException(status_code=404, detail="Link não encontrado")
    
    clear_groups_cache()  # Limpa cache pois grupo pode não ter mais links
    
    return {
        "success": True,
        "errors": get_errors(),
    }


# ---------- ENDPOINTS DE DIAGNÓSTICO ----------


@app.post("/api/diag/providers")
async def api_diag_providers(request: Request, req: DiagRequest):
    """
    Executa diagnóstico dos providers (similar à aba de diagnóstico).

    Permite informar regex customizado para GOVERNO/FUNDA/COORP/LATAM,
    ou usar valores vazios para cair nos defaults.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    data = get_diag_providers(req.re_gov, req.re_funda, req.re_coorp, req.re_latam)
    return {
        "diag": data,
        "errors": get_errors(),
    }


@app.get("/api/diag/logs")
async def api_diag_logs(request: Request):
    """
    Retorna apenas os logs da aba 'logs' (últimas 200 linhas),
    caso o frontend queira exibir separado.
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    data = get_diag_providers("", "", "")  # reaproveita função (já traz logs)
    return {
        "logs": data["logs"],
        "errors": get_errors(),
    }


# ---------- ENDPOINT PERPLEXITY ----------
@app.post("/api/perplexity/count_tokens")
async def api_perplexity_count_tokens(request: Request, req: TokenCountRequest):
    """
    Faz download do conteúdo do link e retorna uma estimativa de tokens.
    Usa a mesma heurística (~4 caracteres por token).
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    tokens, chars, error = count_tokens_from_url(req.url)
    return {
        "ok": error is None,
        "tokens": tokens,
        "characters": chars,
        "error": error,
        "errors": get_errors(),
    }

@app.post("/api/perplexity/search")
async def api_perplexity_search(request: Request, req: PerplexityRequest):
    """
    Chama a Perplexity com os parâmetros enviados pelo frontend.    
    O cálculo de custo é refeito aqui com base em:
    - pricing_in (US$/1M tokens entrada)
    - pricing_out (US$/1M tokens saída)
    - usd_brl (cotação)
    - link_tokens (tokens estimados do conteúdo do link, se fornecido)
    """
    if request.cookies.get(SECRET_COOKIE_NAME) != "authenticated":
        raise HTTPException(status_code=401, detail="Não autenticado")
    init_error_bus()
    result = call_perplexity_chat(
        prompt=req.prompt,
        model_id=req.modelo_api,
        temperature=req.temperature,
        max_out=req.max_tokens,
        pricing_in=req.pricing_in,
        pricing_out=req.pricing_out,
        usd_brl=req.usd_brl,
        modo_label=req.modo_label,
        save=req.save,
        link_tokens=req.link_tokens,
        edital_link=req.edital_link,
    )
    return {
        "result": result,
        "errors": get_errors(),
    }