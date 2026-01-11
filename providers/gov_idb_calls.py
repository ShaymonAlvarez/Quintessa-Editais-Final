# -*- coding: utf-8 -*-
# providers/gov_idb_calls.py

# ============================================================
# BLOCO DE IMPORTAÇÃO
# ============================================================
import re
import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Importar o curl_cffi (solução anti-bloqueio 403)
try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False
    # Fallback para requests padrão (apenas para não quebrar imports, mas não vai funcionar no IDB)
    import requests 

# Fallback para imports locais (modo standalone)
try:
    from .common import normalize, scrape_deadline_from_page
except ImportError:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page

# ============================================================
# METADADOS
# ============================================================
PROVIDER = {"name": "IDB Calls for Proposals", "group": "Governo/Multilaterais"}

START_URL = "https://www.iadb.org/en/how-we-can-work-together/calls-proposals"

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta editais do IDB usando curl_cffi para evitar erro 403.
    """
    debug_cfg = str(cfg.get("IDB_DEBUG", "0")).strip().lower() in ("1", "true", "yes", "sim")
    debug = _debug or debug_cfg

    def log(*args):
        if debug:
            print("[IDB_CALLS]", *args)

    # Verifica se a biblioteca necessária está instalada
    if not HAS_CFFI:
        log("❌ ERRO: Biblioteca 'curl_cffi' não encontrada.")
        log("   O site do IDB bloqueia o Python padrão (Erro 403).")
        log("   SOLUÇÃO: Rode 'pip install curl_cffi' no terminal.")
        return []

    log(f"Acessando: {START_URL} (Simulando Chrome via curl_cffi)...")

    try:
        # impersonate="chrome" é a chave mágica que evita o bloqueio 403
        r = cffi_requests.get(START_URL, impersonate="chrome", timeout=60)
        
        # Verifica se ainda assim deu erro (mas com curl_cffi é raro)
        if r.status_code == 403:
            log("⚠️ Bloqueio 403 persistente mesmo com curl_cffi.")
            return []
        
        r.raise_for_status()
        
    except Exception as e:
        log(f"Erro de conexão: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    seen = set()

    # Palavras-chave de interesse
    KEYWORDS = ["call", "proposal", "opportunity", "grant", "deadline", "convocatoria", "propuesta", "chamada"]

    anchors = soup.find_all("a", href=True)
    log(f"Links encontrados: {len(anchors)}")

    for a in anchors:
        href_raw = a.get("href", "").strip()
        title = normalize(a.get_text()) or normalize(a.get("title", ""))

        if not href_raw or not title:
            continue

        if urlparse(href_raw).scheme in ("http", "https"):
            link = href_raw
        else:
            link = urljoin(START_URL, href_raw)

        # Filtros de limpeza
        if link in seen or link == START_URL:
            continue
        if any(x in link for x in ["/contact", "/about", "linkedin", "twitter", "facebook"]):
            continue

        # Filtro de Relevância
        is_relevant = False
        if regex and regex.search(title):
            is_relevant = True
        elif any(k in title.lower() for k in KEYWORDS):
            is_relevant = True

        if not is_relevant:
            continue

        seen.add(link)

        # Para pegar o deadline, precisamos visitar a página interna.
        # Usamos curl_cffi aqui também para evitar bloqueio na página interna.
        dl = None
        try:
            # Scraper leve na página de destino
            r_inner = cffi_requests.get(link, impersonate="chrome", timeout=30)
            if r_inner.status_code == 200:
                # Usa a função helper do projeto, mas passando o HTML que já baixamos com segurança
                from providers.common import find_deadline_in_text
                # Extrai texto limpo do HTML
                soup_inner = BeautifulSoup(r_inner.text, "html.parser")
                txt_inner = normalize(soup_inner.get_text(" ", strip=True))
                dl = find_deadline_in_text(txt_inner)
        except Exception:
            pass

        log(f"→ Item: {title[:50]}... | Prazo: {dl}")

        out.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": link,
            "deadline": dl,
            "published": None,
            "agency": "IDB",
            "region": "LatAm/Global",
            "raw": {}
        })

    log(f"Finalizado. Total coletado: {len(out)}")
    return out


# ============================================================
# TESTE STANDALONE
# ============================================================
if __name__ == "__main__":
    print("\n>>> TESTE STANDALONE: IDB CALLS (COM CURL_CFFI) <<<\n")
    
    # Regex genérico
    fake_regex = re.compile(r".*", re.I)
    
    try:
        results = fetch(fake_regex, {}, _debug=True)
        
        print("\n" + "="*40)
        print(f"RESULTADO: {len(results)} itens encontrados")
        print("="*40)
        
        for item in results:
            print(f"* {item['title']}")
            print(f"  Url: {item['link']}")
            print(f"  Prazo: {item['deadline']}")
            print("-" * 20)
    except KeyboardInterrupt:
        print("\nTeste interrompido.")