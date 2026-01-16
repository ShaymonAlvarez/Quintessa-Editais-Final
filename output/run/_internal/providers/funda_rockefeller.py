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
        import re
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return None

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

PROVIDER = {
    "name": "Rockefeller Foundation (RFPs)",
    "group": "Fundações e Prêmios"
}

START_URL = "https://www.rockefellerfoundation.org/rfps/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.rockefellerfoundation.org/",
}

def fetch(regex, cfg, _debug: bool = False):
    is_debug = _debug or str(cfg.get("ROCKEFELLER_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[ROCKEFELLER]", *args)

    log(f"Iniciando coleta focada em: {START_URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(START_URL, timeout=45)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro de conexão: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen_links = set()

    candidate_links = soup.find_all("a", href=True)
    
    log(f"Links totais na página: {len(candidate_links)}")

    for a in candidate_links:
        href = a["href"].strip()
        text = a.get_text(" ", strip=True).lower()
        full_link = urljoin(START_URL, href)
        
        # 1. FILTRO: Apenas botões "DOWNLOAD PDF" ou links diretos para .pdf
        is_pdf_download = "download pdf" in text or href.lower().endswith(".pdf")
        
        if not is_pdf_download:
            continue

        # 2. EXTRAÇÃO DO TÍTULO VIA URL (Slug)
        # Ex: .../uploads/2025/12/Africa-Regional-Office-ARO-Power-and-Climate-Contractor.pdf
        # Vira: Africa Regional Office ARO Power and Climate Contractor
        
        try:
            # Pega a última parte da URL (o arquivo)
            filename = full_link.split("/")[-1]
            
            # Remove extensão e decodifica caracteres (%20 vira espaço, etc)
            clean_name = unquote(filename).replace(".pdf", "").replace(".PDF", "")
            
            # Substitui traços e underlines por espaços
            title_from_url = clean_name.replace("-", " ").replace("_", " ")
            
            # Normaliza (remove espaços duplos e trims)
            title = normalize(title_from_url)
        except:
            title = "Edital Rockefeller (Erro ao extrair título)"

        if len(title) < 5:
            title = "Edital Rockefeller Foundation"

        if regex and not regex.search(title):
            log(f"Ignorado por regex: {title}")
            continue

        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # 3. Contexto visual para Data/Valor
        # Ainda usamos o contexto HTML para tentar achar a data e o valor no texto descritivo
        context_text = ""
        # Tenta pegar o container pai ou avô para ler a descrição
        if a.parent:
            grandparent = a.parent.parent
            if grandparent:
                context_text = grandparent.get_text(" ", strip=True)
            else:
                context_text = a.parent.get_text(" ", strip=True)
        
        deadline = parse_date_any(context_text)
        
        raw_data = {}
        price_match = re.search(r"\$[\d,]+(\.\d{2})?\s*(?:million|billion|k)?", context_text, re.IGNORECASE)
        if price_match:
            raw_data["estimated_value"] = price_match.group(0)

        out.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": full_link,
            "deadline": deadline,
            "published": None,
            "agency": "Rockefeller Foundation",
            "region": "Global",
            "raw": raw_data
        })
        
        log(f"✅ EDITAL: {title[:50]}...")
        log(f"   Link: {full_link}")

    log(f"Total de editais válidos: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    CYAN = "\033[96m"
    RESET = "\033[0m"

    print(f"\n{CYAN}>>> TESTE: ROCKEFELLER FOUNDATION (TÍTULOS VIA URL) <<<{RESET}")
    print(f"Alvo: {START_URL}\n")

    mock_regex = re.compile(r".*", re.I)

    try:
        results = fetch(mock_regex, cfg={}, _debug=True)
        
        print(f"\n{CYAN}=== RESULTADOS ({len(results)}) ==={RESET}")
        for i, item in enumerate(results):
            print(f"{i+1}. TÍTULO: {item['title']}")
            print(f"   LINK:   {item['link']}")
            if item['deadline']:
                print(f"   DATA:   {item['deadline']}")
            if item.get('raw', {}).get('estimated_value'):
                print(f"   VALOR:  {item['raw']['estimated_value']}")
            print("-" * 50)

    except Exception as e:
        print(f"Erro: {e}")