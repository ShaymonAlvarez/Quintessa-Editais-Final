# -*- coding: utf-8 -*-
# providers/latam_bnb.py

# ============================================================
# 1. IMPORTS COM FALLBACK
# ============================================================
try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from providers.common import normalize, scrape_deadline_from_page, parse_date_any

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib3

# Desabilita avisos de certificado SSL (comum em .gov.br)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 2. METADADOS DO PROVIDER
# ============================================================
PROVIDER = {
    "name": "Banco do Nordeste (BNB) - Convênios",
    "group": "América Latina / Brasil"
}

BASE_URL = "https://www.bnb.gov.br/conveniosweb/Convenente.ProgramaConvenio.Lista.aspx"

# ============================================================
# 3. LÓGICA DE COLETA (FETCH)
# ============================================================
def fetch(regex, cfg, _debug=False):
    # Verifica debug
    debug_mode = _debug or str(cfg.get("BNB_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if debug_mode:
            print("[BNB]", *args)

    log(f"Iniciando coleta em: {BASE_URL}")

    session = requests.Session()
    # Headers simulando navegador real
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    })

    try:
        # verify=False ajuda a evitar erros de SSL em redes corporativas/gov
        response = session.get(BASE_URL, timeout=45, verify=False)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro na requisição: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # --- LÓGICA DE SELEÇÃO DE TABELA ---
    # Encontra TODAS as tabelas e escolhe a que tem mais linhas (>2)
    tables = soup.find_all("table")
    log(f"Total de tabelas encontradas no HTML: {len(tables)}")
    
    target_table = None
    max_rows = 0

    for i, t in enumerate(tables):
        rows_in_t = t.find_all("tr")
        count = len(rows_in_t)
        # Loga para debug (apenas se tiver linhas)
        if count > 0:
            log(f" -> Tabela {i}: {count} linhas")
        
        # Critério: Pega a maior tabela
        if count > max_rows:
            max_rows = count
            target_table = t

    if not target_table or max_rows < 2:
        log("Nenhuma tabela de dados relevante encontrada (todas vazias ou só cabeçalho).")
        return []

    log(f"Tabela selecionada tem {max_rows} linhas.")
    
    # Processa as linhas da tabela escolhida
    rows = target_table.find_all("tr")
    out = []
    seen_links = set()

    for i, row in enumerate(rows):
        # Ignora cabeçalhos explícitos
        if row.find('th'):
            continue

        cols = row.find_all("td")
        if not cols:
            continue

        # Procura link na linha
        anchor = row.find("a", href=True)
        if not anchor:
            continue

        # Limpeza do título
        title_raw = anchor.get_text(strip=True) or row.get_text(" ", strip=True)
        title = normalize(title_raw)
        
        # Link absoluto
        href = anchor["href"]
        link_abs = urljoin(BASE_URL, href)

        # Filtra javascript puro se não houver URL real
        if "javascript:" in link_abs.lower():
            continue

        if regex and not regex.search(title):
            log(f"Ignorado por Regex: {title[:30]}...")
            continue
            
        if link_abs in seen_links:
            continue
        seen_links.add(link_abs)

        # Tenta extrair data da linha (texto completo)
        row_text = normalize(row.get_text(" | "))
        deadline = parse_date_any(row_text)
        
        # Se não achou na linha, tenta na página de destino (lento, mas preciso)
        if not deadline:
            deadline = scrape_deadline_from_page(link_abs)

        log(f"Capturado: {title[:40]}... | Data: {deadline}")

        out.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": link_abs,
            "deadline": deadline,
            "published": None,
            "agency": "Banco do Nordeste",
            "region": "Nordeste/Brasil",
            "raw": {"row_content": row_text}
        })

    log(f"Total final coletado: {len(out)}")
    return out

# ============================================================
# 4. EXECUÇÃO STANDALONE
# ============================================================
if __name__ == "__main__":
    import json
    import re

    print("\n--- TESTE STANDALONE (BNB) ---")
    # Regex que aceita tudo para teste
    dummy_regex = re.compile(r".*", re.I)
    
    # Roda com debug ativado
    dummy_cfg = {"BNB_DEBUG": "1"}

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        print("-" * 40)
        print(f"Resultados: {len(results)}")
        
        if results:
            print("\nPrimeiro item:")
            print(json.dumps(results[0], indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"Erro fatal no teste: {e}")