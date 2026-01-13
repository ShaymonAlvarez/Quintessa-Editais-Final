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
        def parse_date_any(x): return None

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PROVIDER = {
    "name": "UK International Development Funding",
    "group": "Governo/Multilaterais"
}

START_URL = "https://www.gov.uk/international-development-funding"

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_FILTER = [
    "Edital", "Editais", "Chamada", "Chamamento", "Programa", "Prémio", "Prêmio", "Credenciamento",
    "Programme", "Grant", "Fund", "Call", "Prize", "Award", "Opportunity"
]

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta oportunidades do GOV.UK International Development Funding.
    """
    # Verifica debug via config ou argumento
    is_debug = _debug or str(cfg.get("UK_DEV_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[UK_DEV]", *args)

    log(f"Acessando: {START_URL}")

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
    
    # Tenta focar na lista de documentos (padrão GOV.UK)
    items = soup.select(".gem-c-document-list__item") or soup.select(".gem-c-document-list__item-title")
    
    # Se não achar seletores específicos, pega todos os links da área main
    if not items:
        main_content = soup.find("main") or soup.find(id="content") or soup
        items = main_content.find_all("a", href=True)

    log(f"Elementos candidatos encontrados: {len(items)}")

    for item in items:
        # Se for um item da lista estruturada, o link está dentro
        if item.name == 'li' or 'gem-c-document-list__item' in item.get('class', []):
            anchor = item.find('a', href=True)
            description_tag = item.find('p') or item.find(class_='gem-c-document-list__item-description')
            raw_desc = description_tag.get_text(" ", strip=True) if description_tag else ""
        else:
            # É o próprio link direto
            anchor = item
            raw_desc = ""

        if not anchor:
            continue

        title = normalize(anchor.get_text())
        href = anchor['href']
        
        # Ignora links de navegação interna irrelevantes
        if not title or len(title) < 5: continue
        if any(x in href for x in ["/search", "/browse", "/help", "cookie", "accessibility"]): continue

        link_abs = urljoin(START_URL, href)

        # Palavras-chave obrigatórias para funcionamento do código
        has_keyword = any(k.lower() in title.lower() for k in KEYWORDS_FILTER)
        
        if not has_keyword:
            # log(f"Ignorado (sem palavra-chave): {title}")
            continue

        if regex and not regex.search(title):
            continue

        if link_abs in seen:
            continue
        seen.add(link_abs)

        # Data e Preço, tenta extrair data da descrição ou rodar o scraper de deadline
        deadline = None
        
        # O GOV.UK costuma pôr datas no texto descritivo ou atributo 'time'
        if raw_desc:
            # Tenta achar data no texto do resumo
            deadline = parse_date_any(raw_desc)
        
        # Se não achou data no resumo, usa o scraper profundo na página de destino
        if not deadline:
            deadline = scrape_deadline_from_page(link_abs)

        out.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": link_abs,
            "deadline": deadline,
            "published": None, # GOV.UK nem sempre expõe a data de publicação na listagem simples
            "agency": "UK Gov / FCDO",
            "region": "Global/UK",
            "raw": {"summary": raw_desc[:200]}
        })
        
        log(f"Capturado: {title[:50]}... | Deadline: {deadline}")

    log(f"Total de itens coletados: {len(out)}")
    return out

# MODO STANDALONE (TESTE)
if __name__ == "__main__":
    # Para rodar: python providers/gov_uk_dev.py
    import re
    import json
    
    print("\n--- TESTE STANDALONE: GOV.UK Funding ---\n")
    
    # Regex que aceita tudo (".*") para testar a captura sem filtros
    dummy_regex = re.compile(r".*", re.I)
    
    try:
        # Ativa o debug manualmente
        results = fetch(dummy_regex, {}, _debug=True)
        
        print("\n" + "="*50)
        print(f"RESULTADO: {len(results)} itens encontrados")
        print("="*50)
        
        if results:
            print("\nPrimeiro Item (JSON Completo):")
            print(json.dumps(results[0], indent=2, default=str, ensure_ascii=False))
            
            print("\nLista Resumida:")
            for it in results[:5]: # Mostra os 5 primeiros
                print(f"- {it['title']}")
                print(f"  Link: {it['link']}")
                print(f"  Deadline: {it['deadline']}")
                print("-" * 20)
    except Exception as e:
        print(f"ERRO FATAL: {e}")