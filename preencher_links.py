# -*- coding: utf-8 -*-
"""
Preenche automaticamente os campos faltantes (grupo, uid, ativo, created_at)
dos links novos na aba 'INCLUIR AQUI', usando a IA para categorizar.
"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from backend.core.sheets import ensure_ws_links, _parse_links_rows, _col_letter

# Categorias validas
CATEGORIAS = [
    "Fundações e Prêmios",
    "Governo/Multilaterais",
    "América Latina / Brasil",
    "Geral",
]

def categorizar_com_ia(nome, url):
    """Usa o Perplexity para sugerir a categoria mais adequada."""
    try:
        from backend.core.universal_extractor import _call_perplexity_api
        prompt = (
            f"Classifique este site de editais/oportunidades em UMA das categorias abaixo.\n"
            f"Site: {nome} ({url})\n\n"
            f"Categorias disponíveis:\n"
            f"1. Fundações e Prêmios\n"
            f"2. Governo/Multilaterais\n"
            f"3. América Latina / Brasil\n"
            f"4. Geral\n\n"
            f"Responda SOMENTE com o nome exato da categoria, nada mais."
        )
        resposta = _call_perplexity_api(prompt, max_tokens=30)
        resposta = resposta.strip().strip('"').strip("'")
        for cat in CATEGORIAS:
            if cat.lower() in resposta.lower():
                return cat
    except Exception as e:
        print("   Aviso: IA nao disponivel (%s), usando heuristica." % e)
    return categorizar_heuristica(nome, url)

def categorizar_heuristica(nome, url):
    """Categoriza por palavras-chave no nome e url."""
    texto = (nome + " " + url).lower()
    if any(w in texto for w in ["brasil", "bndes", "finep", "fapesp", "latam",
                                  "latin", "america", "caixa", "funbio", "vale",
                                  "prosas", "iieb", "reparacao", "bnb", "alterna"]):
        return "América Latina / Brasil"
    if any(w in texto for w in ["gov", "un.", "undp", "unicef", "unesco", "world bank",
                                  "worldbank", "adb", "afdb", "eib", "idb", "onu",
                                  "government", "grants.gov", "sam.gov", "pncp",
                                  "procurement", "tender", "contracts", "ukri", "eu.",
                                  "europa", "luxdev", "plan-international", "ogp",
                                  "bond.org", "afd.", "caf.com", "devinfo"]):
        return "Governo/Multilaterais"
    if any(w in texto for w in ["foundation", "fund", "grant", "award", "prize",
                                  "funda", "premio", "opportunity", "fellowship",
                                  "actionaid", "avina", "childfund", "rockefeller",
                                  "girleffect", "ford", "freedomfund", "candid",
                                  "triple", "terra viva", "grantstation", "coordinationsud",
                                  "ogrants", "grantadvisor", "developmentaid"]):
        return "Fundações e Prêmios"
    return "Geral"


def preencher_links_incompletos():
    print("Conectando ao Google Sheets...")
    ws = ensure_ws_links()
    rows = ws.get_all_values()
    hdr_idx, header, data_rows = _parse_links_rows(rows)

    if hdr_idx < 0:
        print("ERRO: header nao encontrado.")
        return

    # Descobre indice 0-based de cada campo no header
    def col_idx(campo):
        try:
            return header.index(campo)
        except ValueError:
            return -1

    idx_nome    = col_idx("nome")
    idx_url     = col_idx("url")
    idx_grupo   = col_idx("grupo")
    idx_uid     = col_idx("uid")
    idx_ativo   = col_idx("ativo")
    idx_created = col_idx("created_at")

    # Descobre col_start (offset da coluna B na planilha)
    # Procura col_start pela posicao do header na linha bruta
    raw_header_row = rows[hdr_idx]
    col_start = 0
    for j, cell in enumerate(raw_header_row):
        if cell.strip():
            col_start = j
            break

    now = datetime.utcnow().isoformat()
    updates = []  # lista de (sheet_row, col_sheet_1indexed, value)

    for i, r in enumerate(data_rows):
        nome  = r[idx_nome].strip()  if idx_nome  >= 0 and idx_nome  < len(r) else ""
        url   = r[idx_url].strip()   if idx_url   >= 0 and idx_url   < len(r) else ""
        uid   = r[idx_uid].strip()   if idx_uid   >= 0 and idx_uid   < len(r) else ""
        ativo = r[idx_ativo].strip() if idx_ativo >= 0 and idx_ativo < len(r) else ""

        if not nome or not url:
            continue  # linha vazia, pula
        if uid:
            continue  # ja preenchido, pula

        sheet_row = hdr_idx + 1 + i + 1  # 1-indexed na planilha

        print(f"\nProcessando: {nome}")
        print(f"  URL: {url}")

        # Categoriza
        grupo = categorizar_heuristica(nome, url)
        print(f"  Grupo: {grupo}")

        # Gera uid
        uid_novo = hashlib.sha256(f"{url}|{grupo}".encode()).hexdigest()[:16]
        print(f"  UID: {uid_novo}")

        # Monta updates
        def cell_update(field_idx, value):
            if field_idx < 0:
                return
            col_1idx = col_start + field_idx + 1  # 1-indexed
            updates.append((sheet_row, col_1idx, value))

        cell_update(idx_grupo,   grupo)
        cell_update(idx_uid,     uid_novo)
        cell_update(idx_ativo,   "true")
        cell_update(idx_created, now)

    if not updates:
        print("\nNenhum link novo encontrado para preencher.")
        return

    print(f"\nAplicando {len(updates)} atualizacoes na planilha...")

    # Batch update via Sheets API
    import gspread
    from backend.core.sheets import open_sheet, values_batch_update

    sh, *_ = open_sheet()
    ws_name = ws.title

    batch = []
    for sheet_row, col_1idx, value in updates:
        col_letter = _col_letter(col_1idx - 1)  # _col_letter e 0-based
        rng = f"'{ws_name}'!{col_letter}{sheet_row}"
        batch.append((rng, [[value]]))

    values_batch_update(ws, batch)
    print("Pronto! Campos preenchidos com sucesso.")
    print(f"\nTotal de links novos processados: {len(set(u[0] for u in updates))}")


if __name__ == "__main__":
    preencher_links_incompletos()
