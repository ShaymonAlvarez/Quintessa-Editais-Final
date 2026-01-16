try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from providers.common import normalize, scrape_deadline_from_page, parse_date_any
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return x

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PROVIDER = {
    "name": "Bond UK Funding",
    "group": "Governo/Multilaterais"
}

START_URL = "https://www.bond.org.uk/funding-opportunities/"

# Headers simulando um Chrome real para evitar bloqueios WAF (Web Application Firewall)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8", # Importante para sites UK
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
KEYWORDS_PT_EN = [
    "edital", "chamada", "programa", "premio", "credenciamento",
    "grant", "fund", "opportunity", "award", "programme", "call", "trust", "foundation", "challenge", "fellowship", "water", 
    "sustainability", "climate", "environment", "development", "social", "entrepreneurship", "impact", 
    "technology", "development bank", "acceleration", "innovation", "tender", "consultancy"
]

GENERIC_LABELS = ["read more", "find out more", "apply", "view", "click here", "visit website", "more info", "details"]

def fetch(regex, cfg, _debug: bool = False):
    is_debug = _debug or str(cfg.get("BOND_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[BOND_UK]", *args)

    log(f"Acessando: {START_URL}")

    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get(START_URL, timeout=45)
        r.raise_for_status()
    except Exception as e:
        log(f"Erro request: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    seen = set()

    # Tenta focar na área principal para evitar links de rodapé/menu
    main_content = soup.find('main') or soup.find('div', id='content') or soup.body

    # Busca elementos que costumam ser títulos de cards (h3, h4 com links dentro)
    candidates = main_content.find_all("a", href=True)
    log(f"Links encontrados na área principal: {len(candidates)}")

    for a in candidates:
        href = a["href"].strip()
        raw_text = a.get_text(" ", strip=True)
        
        # Filtros preliminares
        if not href or href.startswith("#") or len(href) < 5: continue
        if "javascript:" in href.lower() or "mailto:" in href.lower(): continue
        
        full_link = urljoin(START_URL, href)

        # Remove links internos de navegação do site
        if any(x in full_link.lower() for x in ["/policy", "/jobs", "/events", "/news", "/about-us", "/groups", "/join", "/advertise"]):
            continue

        # --- ESTRATÉGIA DE TÍTULO ---
        title = normalize(raw_text)

        if not title or len(title) < 4 or title.lower() in GENERIC_LABELS:
            # Isso garante que pegamos o CARD inteiro, não apenas o botão
            card = a.find_parent(lambda tag: tag.name in ['div', 'article', 'li'] and tag.find(['h2', 'h3', 'h4']))
            
            if card:
                heading = card.find(['h2', 'h3', 'h4'])
                if heading:
                    title = normalize(heading.get_text())

        # Se mesmo assim não tiver título válido, pula
        if not title or len(title) < 5:
            continue

        # Palavras-chave obrigatórias para funcionamento do código
        title_lower = title.lower()
        
        has_keyword = any(k in title_lower for k in KEYWORDS_PT_EN)
        
        if not has_keyword:
            if regex and regex.search(title):
                pass # Passou pelo regex manual do usuário, então aceita
            else:
                continue

        if full_link in seen: continue
        seen.add(full_link)

        # EXTRAÇÃO DE DADOS EXTRAS (DATA/VALOR) 
        deadline = None
        raw_info = {}
        
        # Tenta achar contexto no elemento pai (o card da oportunidade)
        context_container = a.find_parent('article') or a.find_parent('div', class_=re.compile(r'post|card|entry'))
        
        if context_container:
            text_blob = context_container.get_text(" | ", strip=True)
            
            deadline = parse_date_any(text_blob)
            
            # Tenta extrair valor (Libras, Dólar, Euro)
            price_match = re.search(r"(?:£|GBP|€|USD|\$)\s?[\d,.]+(?:k|m|bn)?", text_blob, re.I)
            if price_match:
                raw_info["valor_estimado"] = price_match.group(0)

        # Fallback de data: entra na página se não achou fora
        if not deadline:
            deadline = scrape_deadline_from_page(full_link)

        item = {
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": full_link,
            "deadline": deadline,
            "published": None,
            "agency": "Bond UK / Various",
            "region": "Global/UK",
            "raw": raw_info
        }
        
        out.append(item)
        log(f"✅ Capturado: {title[:50]}... | {deadline}")

    log(f"Total final: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    print("\n--- TESTE STANDALONE: BOND UK ---")
    
    dummy_re = re.compile(r".*")
    
    try:
        results = fetch(dummy_re, {"BOND_DEBUG": "1"}, _debug=True)
        print(f"\nResultados encontrados: {len(results)}")
        
        if len(results) == 0:
            print("\n⚠️ Nenhum resultado? Verifique:")
            print("1. Se o site está bloqueando (tente abrir no navegador).")
            print("2. Se as palavras-chave em inglês (Grant, Fund...) estão na lista.")
        else:
            for r in results[:5]: 
                print(f" > {r['title']}")
                print(f"   Link: {r['link']}")
                print(f"   Data: {r['deadline']}")
                print(f"   Info: {r['raw']}")
                print("---")
    except Exception as e:
        print(f"Erro fatal: {e}")