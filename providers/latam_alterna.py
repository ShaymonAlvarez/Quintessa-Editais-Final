import re
import time
from urllib.parse import urljoin
try:
    from .common import normalize, parse_date_any, scrape_deadline_from_page
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from providers.common import normalize, parse_date_any, scrape_deadline_from_page
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def parse_date_any(x): return None
        def scrape_deadline_from_page(x): return None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright não instalado. Rode 'pip install playwright'")
    raise

PROVIDER = {
    "name": "Alterna - Carreras",
    "group": "América Latina / Brasil"
}

START_URL = "https://carreras.alterna.pro/jobs/Careers"

# Requisito 3: Palavras-chave obrigatórias
KEYWORDS_FILTER = [
    "Edital", "Editais", "Chamada", "Aceleração","Programa", "Prêmio", "Credenciamento",
    "Água", "Water", "Sustentability", "Clima", "Climate", "Meio Ambiente", "Environment",
    "Desenvolvimento", "Development", "Social", "Empreendedorismo", "Entrepreneurship",
    "Impacto", "Impact", "Tecnologia", "Technology",  "Banco de fomento", "Development Bank",
    "Inovação", "Innovation", "Consultoria", "Consultancy", "Tender", "Call", "Grant"
]

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta oportunidades da Alterna. 
    Lida com cookies e renderização dinâmica via Playwright.
    """
    is_debug = _debug or str(cfg.get("ALTERNA_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug: print("[ALTERNA]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not is_debug)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # Requisito 2: Acesso e tratamento de Cookies/Autorização
            page.goto(START_URL, timeout=60000, wait_until="networkidle")
            
            # Tenta aceitar cookies automaticamente se o banner aparecer
            try:
                cookie_btn = page.locator("button:has-text('Accept'), button:has-text('Aceitar'), button:has-text('Agree')").first
                if cookie_btn.is_visible(timeout=5000):
                    cookie_btn.click()
                    log("Cookies aceitos automaticamente.")
            except:
                pass

            # Aguarda os cards de jobs carregarem (comum em plataformas de recrutamento)
            page.wait_for_selector("a[href*='/jobs/']", timeout=15000)
            
            # Extração via JavaScript para maior robustez
            raw_items = page.evaluate("""() => {
                const results = [];
                const links = Array.from(document.querySelectorAll('a[href*="/jobs/"]'));
                links.forEach(a => {
                    const container = a.closest('div') || a.parentElement;
                    results.push({
                        title: a.innerText.trim(),
                        href: a.getAttribute('href'),
                        context: container ? container.innerText : ""
                    });
                });
                return results;
            }""")

            for item in raw_items:
                title = normalize(item['title'])
                full_link = urljoin(START_URL, item['href'])
                
                if not title or full_link in seen: continue
                
                # Requisito 3: Filtro de Títulos
                has_keyword = any(k.lower() in title.lower() for k in KEYWORDS_FILTER)
                
                # Aplica o filtro de regex do sistema se fornecido
                if regex and not regex.search(title):
                    continue

                if not has_keyword:
                    continue

                seen.add(full_link)

                # Extração de Data e Preço (Scraping profundo)
                deadline = scrape_deadline_from_page(full_link)
                
                # Busca valor monetário no contexto do card ou título
                raw_data = {}
                money_match = re.search(r"(?:USD|R\$|Q|$)[\d\.,]+", item['context'])
                if money_match:
                    raw_data["estimated_value"] = money_match.group(0)

                out.append({
                    "source": PROVIDER["name"],
                    "title": title[:180],
                    "link": full_link,
                    "deadline": deadline,
                    "published": None,
                    "agency": "Alterna",
                    "region": "LatAm",
                    "raw": raw_data
                })
                log(f"✅ Capturado: {title[:50]}... | Deadline: {deadline}")

        except Exception as e:
            log(f"Erro durante a execução: {e}")
        finally:
            browser.close()

    return out

# Requisito 1: Flag de teste standalone
if __name__ == "__main__":
    import re
    print("\n--- MODO TESTE STANDALONE: ALTERNA ---\n")
    test_regex = re.compile(r".*", re.I)
    results = fetch(test_regex, {}, _debug=True)
    
    print(f"\nTotal de itens encontrados: {len(results)}")
    for i, res in enumerate(results):
        print(f"[{i+1}] {res['title']}")
        print(f"    Link: {res['link']}")
        print(f"    Data: {res['deadline']}")
        print(f"    Extra: {res['raw']}")
        print("-" * 30)