"""
Acesso ao Google Sheets (gspread).

Aqui ficam:
- criação/garantia de abas (config, sources, items, logs, perplexity)
- leitura e escrita com cache simples
- helpers para log em planilha

Suporta dois modos de autenticação (em ordem de prioridade):
1. Service Account (RECOMENDADO) - arquivo service_account.json
2. OAuth Pessoal (legado) - variáveis no .env
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Tuple

import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request

from . import config
from .errors import push_error
from datetime import datetime
import time

# Cabeçalho padrão da aba 'items'
ITEMS_HEADER: List[str] = [
    "uid",
    "group",
    "source",
    "title",
    "link",
    "deadline_iso",
    "published_iso",
    "agency",
    "region",
    "raw_json",
    "created_at",
    "seen",
    "status",
    "notes",
    "do_not_show",
]

# Status possíveis, iguais ao Streamlit
STATUS_CHOICES = ["pendente", "verificando", "submetido", "não submetido"]

# Cores de fundo por status (para o frontend)
STATUS_BG = {
    "pendente": "#111111",
    "verificando": "#6d82c2",
    "submetido": "#599e6f",
    "não submetido": "#a77578",
}

# Cores de texto por status (se o frontend quiser usar)
STATUS_COLORS = {
    "pendente": "#FFD166",
    "verificando": "#118AB2",
    "submetido": "#06D6A0",
    "não submetido": "#EF476F",
}


@lru_cache(maxsize=1)
def get_gspread_client() -> gspread.Client:
    """
    Cria um cliente gspread autorizado.
    
    Prioridade de autenticação:
    1. Service Account (arquivo service_account.json) - RECOMENDADO
    2. OAuth pessoal (variáveis no .env) - LEGADO
    
    Service Account é preferível para distribuição pois:
    - Não expira
    - Não requer configuração do usuário final
    - Mais seguro e profissional
    """
    auth_method = config.get_auth_method()
    
    if auth_method == "service_account":
        # Método 1: Service Account (RECOMENDADO)
        try:
            sa_path = config.get_service_account_path()
            creds = ServiceAccountCredentials.from_service_account_file(
                str(sa_path),
                scopes=config.SCOPES
            )
            print(f"[AUTH] Usando Service Account: {sa_path.name}")
            return gspread.authorize(creds)
        except Exception as e:
            push_error("Service Account auth", e)
            raise RuntimeError(
                f"Erro ao autenticar com Service Account: {e}\n"
                "Verifique se o arquivo service_account.json é válido."
            )
    
    elif auth_method == "oauth":
        # Método 2: OAuth pessoal (LEGADO - mantido para compatibilidade)
        try:
            oauth = config.get_google_oauth()
            creds = OAuthCredentials(
                token=None,
                refresh_token=oauth["refresh_token"],
                token_uri=oauth["token_uri"],
                client_id=oauth["client_id"],
                client_secret=oauth["client_secret"],
                scopes=config.SCOPES,
            )
            if not creds.valid:
                creds.refresh(Request())
            print("[AUTH] Usando OAuth pessoal (modo legado)")
            return gspread.authorize(creds)
        except Exception as e:
            push_error("OAuth refresh", e)
            raise
    
    else:
        # Nenhum método configurado
        raise RuntimeError(
            "Nenhum método de autenticação Google configurado.\n\n"
            "OPÇÃO RECOMENDADA (Service Account):\n"
            "  1. Execute: python setup_service_account.py\n"
            "  2. Coloque o arquivo service_account.json na pasta do executável\n\n"
            "OPÇÃO LEGADA (OAuth pessoal):\n"
            "  1. Execute: python setup_oauth_env.py\n"
            "  2. Configure as variáveis no arquivo .env"
        )


@lru_cache(maxsize=1)
def open_sheet():
    """
    Abre a planilha principal por URL e garante que as abas necessarias existam.
    NAO mexe em headers existentes — o layout e gerenciado manualmente.
    Retorna: (sh, ws_cfg, ws_items, ws_log)
    """
    gc = get_gspread_client()
    sh = gc.open_by_url(config.get_sheet_url())

    def ensure(wsname: str, header: List[str], titulo: str = ""):
        try:
            ws = sh.worksheet(wsname)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(wsname, rows=1000, cols=max(20, len(header) + 2))
            # Cria com layout formatado
            ws.update_cell(2, 2, titulo or f"SISTEMA: Aba {wsname}")
            ws.update([header], "B4", value_input_option="RAW")
        return ws

    ws_cfg = ensure("config", ["key", "value"],
                    "SISTEMA: Configuracoes internas da automacao. NAO EDITAR.")
    ws_items = ensure("items", ITEMS_HEADER,
                      "SISTEMA: Editais extraidos automaticamente pela IA.")
    ws_log = ensure("logs", ["ts", "level", "msg"],
                    "SISTEMA: Registro de execucoes e erros. NAO EDITAR.")
    return sh, ws_cfg, ws_items, ws_log


def values_batch_update(ws, updates: List[Tuple[str, List[List[str]]]]) -> None:
    """
    Aplica um batch_update de valores em ranges arbitrários de uma worksheet.

    'updates' é uma lista de tuplas (range_A1, [[val1, val2, ...]]).
    """
    if not updates:
        return
    body = {
        "valueInputOption": "RAW",
        "data": [{"range": r, "values": vals} for r, vals in updates],
    }
    try:
        ws.spreadsheet.values_batch_update(body)
    except Exception as e:
        push_error("values_batch_update", e)
        raise


def _find_data_in_tab(rows: List[List[str]], header_marker: str = ""):
    """
    Encontra header e dados em qualquer aba com layout formatado.
    Procura a linha do header (primeira linha com conteudo apos linhas vazias/titulo).
    Retorna: (hdr_idx, col_start, header, data_rows)
    - hdr_idx: indice 0-based da linha do header (-1 se nao encontrado)
    - col_start: indice 0-based da primeira coluna com dados
    - header: lista de nomes de coluna
    - data_rows: linhas de dados alinhadas com header
    """
    hdr_idx = -1
    for i, row in enumerate(rows[:10]):
        # Procura uma linha com pelo menos 2 celulas preenchidas
        filled = [c for c in row if c.strip()]
        if len(filled) >= 2:
            # Checa se nao e o titulo (titulo tem 1 celula longa)
            non_empty = [c.strip() for c in row if c.strip()]
            # Se tem marker, usa ele
            if header_marker:
                if any(c.strip().lower() == header_marker.lower() for c in row):
                    hdr_idx = i
                    break
            else:
                # Heuristica: uma linha com 2+ celulas curtas e provavelmente header
                if len(non_empty) >= 2 and all(len(c) < 50 for c in non_empty):
                    hdr_idx = i
                    break

    if hdr_idx < 0:
        return -1, 0, [], []

    raw_header = rows[hdr_idx]
    col_start = 0
    for j, cell in enumerate(raw_header):
        if cell.strip():
            col_start = j
            break

    header = [c.strip() for c in raw_header[col_start:]]
    while header and not header[-1]:
        header.pop()

    data_rows = []
    for r in rows[hdr_idx + 1:]:
        aligned = r[col_start:] if len(r) > col_start else []
        data_rows.append(aligned)

    return hdr_idx, col_start, header, data_rows


def sheet_log(ws_log, level: str, msg: str) -> None:
    """Registra uma linha na aba 'logs' no layout formatado (coluna B)."""
    try:
        rows = ws_log.get_all_values()
        hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "ts")
        if hdr_idx < 0:
            # Fallback: appende normalmente
            ws_log.append_row([datetime.utcnow().isoformat(), level, msg])
            return
        # Encontra proxima linha livre
        last_data_row = hdr_idx + 1  # 1-indexed
        for i, r in enumerate(data_rows):
            if any(cell.strip() for cell in r):
                last_data_row = hdr_idx + 1 + i + 1
        next_row = last_data_row + 1
        col_letter = _col_letter(col_start)
        end_col = _col_letter(col_start + 2)  # ts, level, msg = 3 colunas
        rng = f"{col_letter}{next_row}:{end_col}{next_row}"
        ws_log.update([[datetime.utcnow().isoformat(), level, msg]], rng, value_input_option="RAW")
    except Exception as e:
        push_error("sheet_log", e)


@lru_cache(maxsize=1)
def read_items_cached():
    """
    Le todas as linhas da aba 'items' com cache in-memory.
    Suporta layout formatado (header na linha 4, coluna B).
    Retorna: (header, body)
    """
    try:
        _, _, ws_items, _ = open_sheet()
        rows = ws_items.get_all_values()
    except Exception as e:
        push_error("read_items_cached", e)
        rows = []

    if not rows:
        return ITEMS_HEADER, []

    hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "uid")
    if hdr_idx < 0:
        # Fallback: formato antigo
        header = rows[0]
        data_rows = rows[1:]

    body = [r + [""] * max(0, len(header) - len(r)) for r in data_rows
            if any(cell.strip() for cell in r)]
    return header, body


def invalidate_items_cache() -> None:
    """Limpa o cache da leitura da aba 'items'."""
    try:
        read_items_cached.cache_clear()
    except Exception:
        pass


def append_items_dedup(
    ws_items, header: List[str], body: List[List[str]], new_rows: List[List[str]]
) -> None:
    """
    Adiciona novas linhas em 'items', sem duplicados por uid.
    Escreve a partir da coluna B no layout formatado.
    """
    seen = set(r[0] for r in body if r)
    to_add = []
    for r in new_rows:
        if len(r) < len(header):
            r += [""] * (len(header) - len(r))
        if r[0] not in seen:
            to_add.append(r)

    if to_add:
        try:
            # Encontra onde inserir
            rows = ws_items.get_all_values()
            hdr_idx, col_start, _, data_rows = _find_data_in_tab(rows, "uid")
            if hdr_idx < 0:
                ws_items.append_rows(to_add, value_input_option="RAW")
            else:
                # Encontra ultima linha com dados
                last_data_row = hdr_idx + 1
                for i, r in enumerate(data_rows):
                    if any(cell.strip() for cell in r):
                        last_data_row = hdr_idx + 1 + i + 1
                start_row = last_data_row + 1
                col_letter = _col_letter(col_start)
                end_col = _col_letter(col_start + len(header) - 1)
                end_row = start_row + len(to_add) - 1
                rng = f"{col_letter}{start_row}:{end_col}{end_row}"
                ws_items.update(to_add, rng, value_input_option="RAW")
        except Exception as e:
            push_error("append_items_dedup", e)
            return
        invalidate_items_cache()


def read_config() -> Dict[str, str]:
    """
    Le a aba 'config' e devolve um dicionario key->value.
    Suporta layout formatado.
    """
    _, ws_cfg, _, _ = open_sheet()
    rows = ws_cfg.get_all_values()
    hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "key")

    data: Dict[str, str] = {}
    if hdr_idx < 0:
        # Fallback: formato antigo
        for r in rows[1:]:
            if len(r) >= 2 and r[0]:
                data[r[0]] = r[1]
    else:
        for r in data_rows:
            if len(r) >= 2 and r[0].strip():
                data[r[0].strip()] = r[1].strip() if len(r) > 1 else ""
    return data


def upsert_config(key: str, value: str) -> None:
    """
    Atualiza (ou cria) uma linha na aba 'config'.
    Suporta layout formatado.
    """
    _, ws_cfg, _, _ = open_sheet()
    rows = ws_cfg.get_all_values()
    hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "key")

    if hdr_idx < 0:
        # Fallback
        ws_cfg.append_row([key, value])
        return

    # Procura a chave existente
    for i, r in enumerate(data_rows):
        cell_key = r[0].strip() if r else ""
        if cell_key == key:
            sheet_row = hdr_idx + 1 + i + 1  # 1-indexed
            val_col = col_start + 2  # coluna 'value' = col_start + 1 + 1 (1-indexed)
            ws_cfg.update_cell(sheet_row, val_col, value)
            return

    # Nao encontrou — insere nova linha
    last_data_row = hdr_idx + 1
    for i, r in enumerate(data_rows):
        if any(cell.strip() for cell in r):
            last_data_row = hdr_idx + 1 + i + 1
    next_row = last_data_row + 1
    col_letter = _col_letter(col_start)
    end_col = _col_letter(col_start + 1)
    rng = f"{col_letter}{next_row}:{end_col}{next_row}"
    ws_cfg.update([[key, value]], rng, value_input_option="RAW")


def clear_items_sheet() -> None:
    """
    Limpa os dados da aba 'items' mas preserva o layout formatado.
    """
    _, _, ws_items, _ = open_sheet()
    rows = ws_items.get_all_values()
    hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "uid")

    if hdr_idx < 0:
        # Fallback
        ws_items.clear()
        ws_items.append_row(ITEMS_HEADER)
    else:
        # Limpa apenas as linhas de dados (preserva linhas 1-4)
        data_start = hdr_idx + 2  # 1-indexed, primeira linha de dados
        total_rows = ws_items.row_count
        if total_rows >= data_start:
            # Limpa range de dados
            col_letter = _col_letter(col_start)
            end_col = _col_letter(col_start + len(header) - 1)
            rng = f"{col_letter}{data_start}:{end_col}{total_rows}"
            try:
                ws_items.batch_clear([rng])
            except Exception:
                pass
    invalidate_items_cache()


def get_logs_tail(limit: int = 200) -> List[List[str]]:
    """
    Retorna as ultimas 'limit' linhas da aba 'logs'.
    Suporta layout formatado.
    """
    try:
        _, _, _, ws_log = open_sheet()
        rows = ws_log.get_all_values()
    except Exception as e:
        push_error("get_logs_tail", e)
        return []

    if not rows:
        return []

    hdr_idx, col_start, header, data_rows = _find_data_in_tab(rows, "ts")
    if hdr_idx < 0:
        # Fallback
        if len(rows) <= limit:
            return rows
        return rows[-limit:]

    # Filtra linhas vazias
    filled = [r for r in data_rows if any(cell.strip() for cell in r)]
    result = [header] + filled[-limit:]
    return result


def ensure_ws_perplexity():
    """
    Garante a aba 'perplexity' com o cabeçalho correto e a retorna.
    """
    sh, *_ = open_sheet()
    header = [
        "timestamp_utc",
        "modo",
        "modelo_api",
        "prompt",
        "parametros_json",
        "tokens_in",
        "tokens_out_estimados",
        "custo_usd_estimado",
        "custo_brl_estimado",
        "resumo",
        "links_citados",
        "json_resposta",
        "erro",
    ]
    try:
        try:
            ws = sh.worksheet("perplexity")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet("perplexity", rows=1000, cols=max(20, len(header)))
            ws.append_row(header)
        existing = ws.row_values(1)
        if existing != header:
            new_header = existing[:] + [h for h in header if h not in existing]
            ws.resize(
                rows=max(ws.row_count, 1000),
                cols=max(len(new_header), ws.col_count),
            )
            ws.update("1:1", [new_header])
        return ws
    except Exception as e:
        push_error("ensure_ws_perplexity", e)
        raise


# ============= ABA "INCLUIR AQUI" (LINKS PARA COLETA) =============
# Nome da aba visivel na planilha
LINKS_SHEET_NAME = "INCLUIR AQUI"

# Cabecalho da aba (sem a coluna A que e reservada como espaco)
LINKS_HEADER: List[str] = [
    "nome",          # USUARIO: Nome da empresa / instituicao
    "url",           # USUARIO: Link do site de editais
    "grupo",         # SISTEMA: Categoria
    "uid",           # SISTEMA: ID interno unico
    "ativo",         # SISTEMA: Ativo para coleta (true/false)
    "created_at",    # SISTEMA: Data de cadastro
    "last_run",      # SISTEMA: Ultima execucao
    "last_status",   # SISTEMA: Status (ok/erro)
    "last_items",    # SISTEMA: Editais encontrados
]

# Layout da aba (conforme formatacao manual):
#   Linha 1: vazia (espacamento)
#   Linha 2: titulo descritivo da aba
#   Linha 3: vazia (espacamento)
#   Linha 4: cabecalho (comecando em coluna B)
#   Linha 5+: dados (comecando em coluna B)
# Coluna A e sempre vazia (espaco visual).
LINKS_COL_OFFSET = 1   # Dados comecam na coluna B (indice 1)


def _find_links_header_row(rows: List[List[str]]) -> int:
    """
    Encontra a linha do cabecalho na aba de links.
    Procura 'nome' nas primeiras 10 linhas.
    Retorna o indice 0-based da linha do header, ou -1 se nao encontrar.
    """
    for i, row in enumerate(rows[:10]):
        # Procura 'nome' em qualquer coluna da linha
        for cell in row:
            if cell.strip().lower() == "nome":
                return i
    return -1


def _parse_links_rows(rows: List[List[str]]):
    """
    Dado todo o conteudo da aba, retorna (header_row_idx, header, data_rows).
    header e a lista de nomes de coluna.
    data_rows sao as linhas de dados (ja alinhadas com o header).
    """
    hdr_idx = _find_links_header_row(rows)
    if hdr_idx < 0:
        return -1, [], []

    raw_header = rows[hdr_idx]
    # Encontra onde comeca o header real (pula celulas vazias a esquerda)
    col_start = 0
    for j, cell in enumerate(raw_header):
        if cell.strip():
            col_start = j
            break

    # Extrai header a partir de col_start
    header = [c.strip() for c in raw_header[col_start:]]
    # Remove celulas vazias do final
    while header and not header[-1]:
        header.pop()

    data_rows = []
    for r in rows[hdr_idx + 1:]:
        aligned = r[col_start:] if len(r) > col_start else []
        data_rows.append(aligned)

    return hdr_idx, header, data_rows


def ensure_ws_links():
    """
    Garante a aba 'INCLUIR AQUI' e a retorna.
    NAO mexe no cabecalho — ele e gerenciado manualmente pelo usuario.
    """
    sh, *_ = open_sheet()
    try:
        try:
            ws = sh.worksheet(LINKS_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            try:
                ws = sh.worksheet("links_cadastrados")
                ws.update_title(LINKS_SHEET_NAME)
            except gspread.exceptions.WorksheetNotFound:
                # Cria nova aba com layout formatado
                header = LINKS_HEADER
                ws = sh.add_worksheet(LINKS_SHEET_NAME, rows=500, cols=len(header) + LINKS_COL_OFFSET + 1)
                # Linha 2: titulo
                ws.update_cell(2, 2, "GUIA DO SISTEMA: Incluir o nome e o site de busca padrao aqui")
                # Linha 4: cabecalho a partir da coluna B
                ws.update(f"B4", [header], value_input_option="RAW")
                _seed_default_links(ws)
        return ws
    except Exception as e:
        push_error("ensure_ws_links", e)
        raise


def _seed_default_links(ws) -> int:
    """
    Insere links padrao extraidos dos providers originais.
    Chamado apenas quando a aba e criada pela primeira vez.
    Dados comecam na linha 5, coluna B.
    """
    import hashlib
    from .default_links import get_all_provider_links

    links = get_all_provider_links()
    if not links:
        return 0

    rows_to_add = []
    now = datetime.utcnow().isoformat()

    for link in links:
        nome = link.get("nome", "")
        url = link.get("url", "")
        grupo = link.get("grupo", "Geral")
        uid = hashlib.sha256(f"{url}|{grupo}".encode()).hexdigest()[:16]

        rows_to_add.append([
            nome, url, grupo, uid,
            "true", now, "", "", "",
        ])

    if rows_to_add:
        try:
            # Escreve a partir de B5
            start_row = 5
            end_row = start_row + len(rows_to_add) - 1
            end_col = _col_letter(LINKS_COL_OFFSET + len(LINKS_HEADER) - 1)
            rng = f"B{start_row}:{end_col}{end_row}"
            ws.update(rows_to_add, rng, value_input_option="RAW")
        except Exception as e:
            push_error("seed_default_links", e)
            return 0

    return len(rows_to_add)


def read_links() -> List[Dict[str, str]]:
    """
    Le todos os links cadastrados da aba 'INCLUIR AQUI'.
    Encontra o cabecalho automaticamente (procura 'nome' nas primeiras linhas).
    Retorna lista de dicionarios.
    """
    try:
        ws = ensure_ws_links()
        rows = ws.get_all_values()
    except Exception as e:
        push_error("read_links", e)
        return []

    hdr_idx, header, data_rows = _parse_links_rows(rows)
    if hdr_idx < 0:
        return []

    result = []
    for r in data_rows:
        # Pula linhas vazias
        if not r or not any(cell.strip() for cell in r):
            continue
        item = {}
        for i, col in enumerate(header):
            item[col] = r[i].strip() if i < len(r) else ""
        # Se nao tem uid, gera um a partir de url
        if not item.get("uid") and item.get("url"):
            import hashlib
            grupo = item.get("grupo", "Geral")
            item["uid"] = hashlib.sha256(
                f"{item['url']}|{grupo}".encode()
            ).hexdigest()[:16]
            item.setdefault("ativo", "true")
        result.append(item)
    return result


def add_link(url: str, grupo: str = "Geral", nome: str = "") -> Dict[str, str]:
    """
    Adiciona um novo link cadastrado.
    Escreve a partir da coluna B, na proxima linha livre apos os dados.
    """
    import hashlib

    ws = ensure_ws_links()
    uid = hashlib.sha256(f"{url}|{grupo}".encode()).hexdigest()[:16]
    now = datetime.utcnow().isoformat()

    new_data = [
        nome or "", url, grupo, uid,
        "true", now, "", "", "",
    ]

    try:
        rows = ws.get_all_values()
        hdr_idx, header, data_rows = _parse_links_rows(rows)

        if hdr_idx < 0:
            # Fallback: escreve na linha 5
            next_row = 5
        else:
            # Proxima linha livre apos header + dados
            next_row = hdr_idx + 1 + len(data_rows) + 1  # +1 para 1-indexed
            # Porem precisamos pular linhas vazias no final
            # Encontra a ultima linha com dados
            last_data = hdr_idx + 1  # pelo menos a linha apos o header
            for i, r in enumerate(data_rows):
                if any(cell.strip() for cell in r):
                    last_data = hdr_idx + 1 + i + 1  # 1-indexed
            next_row = last_data + 1

        end_col = _col_letter(LINKS_COL_OFFSET + len(new_data) - 1)
        rng = f"B{next_row}:{end_col}{next_row}"
        ws.update([new_data], rng, value_input_option="RAW")
    except Exception as e:
        push_error("add_link", e)
        raise

    return {
        "uid": uid,
        "url": url,
        "grupo": grupo,
        "nome": nome or "",
        "ativo": "true",
        "created_at": now,
        "last_run": "",
        "last_status": "",
        "last_items": "",
    }


def update_link(uid: str, updates: Dict[str, str]) -> bool:
    """
    Atualiza campos de um link existente por UID.
    Retorna True se encontrou e atualizou.
    """
    ws = ensure_ws_links()
    rows = ws.get_all_values()

    hdr_idx, header, data_rows = _parse_links_rows(rows)
    if hdr_idx < 0 or "uid" not in header:
        return False

    uid_col = header.index("uid")

    for i, r in enumerate(data_rows):
        cell_uid = r[uid_col].strip() if uid_col < len(r) else ""
        if cell_uid == uid:
            sheet_row = hdr_idx + 1 + i + 1  # 1-indexed
            for key, value in updates.items():
                if key in header and key != "uid":
                    col_idx = header.index(key) + LINKS_COL_OFFSET + 1  # 1-indexed
                    ws.update_cell(sheet_row, col_idx, value)
                    time.sleep(0.5)
            return True

    return False


def delete_link(uid: str) -> bool:
    """
    Remove um link por UID.
    Retorna True se encontrou e removeu.
    """
    ws = ensure_ws_links()
    rows = ws.get_all_values()

    hdr_idx, header, data_rows = _parse_links_rows(rows)
    if hdr_idx < 0 or "uid" not in header:
        return False

    uid_col = header.index("uid")

    for i, r in enumerate(data_rows):
        cell_uid = r[uid_col].strip() if uid_col < len(r) else ""
        if cell_uid == uid:
            sheet_row = hdr_idx + 1 + i + 1  # 1-indexed
            ws.delete_rows(sheet_row)
            return True

    return False


def update_link_run_status(uid: str, status: str, items_count: int) -> bool:
    """
    Atualiza o status da ultima execucao de um link.
    """
    return update_link(uid, {
        "last_run": datetime.utcnow().isoformat(),
        "last_status": status,
        "last_items": str(items_count),
    })


def update_link_run_status_batch(statuses: List[Dict]) -> int:
    """
    Atualiza o status de multiplos links em uma unica chamada ao Google Sheets.
    Usa _parse_links_rows para encontrar header e dados corretamente.
    """
    if not statuses:
        return 0

    try:
        ws = ensure_ws_links()
        rows = ws.get_all_values()
    except Exception as e:
        push_error("update_link_run_status_batch.read", e)
        return 0

    hdr_idx, header, data_rows = _parse_links_rows(rows)
    if hdr_idx < 0:
        return 0

    try:
        uid_idx = header.index("uid")
        run_idx = header.index("last_run")
        status_idx = header.index("last_status")
        items_idx = header.index("last_items")
    except ValueError as e:
        push_error("update_link_run_status_batch.header", e)
        return 0

    # Mapeia uid -> numero de linha (1-indexed na planilha)
    uid_to_rownum: Dict[str, int] = {}
    for i, r in enumerate(data_rows):
        cell_uid = r[uid_idx].strip() if uid_idx < len(r) else ""
        if cell_uid:
            sheet_row = hdr_idx + 1 + i + 1  # 1-indexed
            uid_to_rownum[cell_uid] = sheet_row

    now = datetime.utcnow().isoformat()
    batch: List[Tuple[str, List[List[str]]]] = []
    updated = 0

    for item in statuses:
        uid = item.get("uid")
        if not uid:
            continue
        row_num = uid_to_rownum.get(uid)
        if not row_num:
            continue

        status_val = item.get("status", "")
        items_count = str(item.get("items_count", ""))
        run_time = item.get("last_run", now)

        ws_name = ws.title
        # Colunas reais na planilha = indice no header + offset da coluna B
        col_run = _col_letter(run_idx + LINKS_COL_OFFSET)
        col_status = _col_letter(status_idx + LINKS_COL_OFFSET)
        col_items = _col_letter(items_idx + LINKS_COL_OFFSET)

        batch += [
            (f"{ws_name}!{col_run}{row_num}", [[run_time]]),
            (f"{ws_name}!{col_status}{row_num}", [[status_val]]),
            (f"{ws_name}!{col_items}{row_num}", [[items_count]]),
        ]
        updated += 1

    if batch:
        try:
            values_batch_update(ws, batch)
        except Exception as e:
            push_error("update_link_run_status_batch.write", e)
            return 0

    return updated


def _col_letter(zero_idx: int) -> str:
    """Converte indice zero-based de coluna em letra(s) (A, B, ..., AA, AB...)."""
    s = ""
    i = zero_idx
    while True:
        i, r = divmod(i, 26)
        s = chr(65 + r) + s
        if i == 0:
            break
        i -= 1
    return s
