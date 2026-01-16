try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page, parse_date_any

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PROVIDER = {
    "name": "CAF - Banco de Desenvolvimento da América Latina",
    "group": "Governo/Multilaterais"
}

START_URL = "https://www.caf.com/en/work-with-us/calls"

# Palavras-chave obrigatórias para funcionamento do código
REQUIRED_KEYWORDS = [
    "call", "request", "program", "prize", "award", 
    "tender", "procurement", "consultancy", "proposal", "rfp",
    "edital", "chamada", "convocatoria", "licitación", "designs", "water", "sustainability",
    "climate", "environment", "development", "social", "entrepreneurship", "impact", "technology", "development bank", 
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch(regex, cfg, _debug: bool = False):
    debug_mode = _debug or str(cfg.get("CAF_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if debug_mode:
            print("[CAF]", *args)

    log(f"Iniciando coleta em: {START_URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(START_URL, timeout=60)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro de conexão: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen = set()

    # Pega os cards de editais
    # Baseado no print, parece ser algo como "card" ou "item"
    items = soup.find_all(class_=re.compile(r'(listing|item|card|row|result)', re.I))
    
    # Se a busca por classe falhar, pega todos os blocos que contenham link
    if not items:
        items = soup.find_all('div')

    candidates = []
    
    # Filtra apenas divs que parecem ser um item de lista real (tem link e texto)
    for item in items:
        anchor = item.find('a', href=True)
        if not anchor:
            continue
            
        # Otimização: ignora itens muito pequenos (menus, rodapé)
        if len(item.get_text()) < 50:
            continue
            
        candidates.append(item)

    log(f"Blocos candidatos analisados: {len(candidates)}")

    for item in candidates:
        anchor = item.find('a', href=True)
        full_link = urljoin(START_URL, anchor['href'])
        
        # Título
        raw_title = anchor.get_text(strip=True)
        # Se título do link for genérico, tenta achar h2/h3 no bloco
        if len(raw_title) < 10:
            header = item.find(['h2', 'h3', 'h4'])
            if header:
                raw_title = header.get_text(strip=True)

        title = normalize(raw_title)
        if not title or len(title) < 5:
            continue

        # 1. Filtro Keywords
        title_lower = title.lower()
        if not any(k in title_lower for k in REQUIRED_KEYWORDS):
            continue

        # 2. Filtro Regex Sistema
        if regex and not regex.search(title):
            continue

        if full_link in seen:
            continue
        seen.add(full_link)

        deadline = None
        
        block_text = item.get_text(" ", strip=True)
        
        match = re.search(r"Deadline:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{2}/\d{2}/\d{4})", block_text, re.IGNORECASE)
        
        if match:
            date_str = match.group(1)
            deadline = parse_date_any(date_str)
        else:
            if "Deadline" in block_text:
                deadline = parse_date_any(block_text)

        out.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": full_link,
            "deadline": deadline,
            "published": None, # Data de publicação não aparece clara no print
            "agency": "CAF",
            "region": "LatAm",
            "raw": {}
        })
        
        log(f"✅ {title[:40]}... | Dead: {deadline}")

    log(f"Total final: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    print(">>> TESTE CAF (DEADLINE DA LISTAGEM) <<<")
    # Usa um regex que pega tudo
    r = fetch(re.compile(".*"), {}, _debug=True)
    print(f"Total: {len(r)}")