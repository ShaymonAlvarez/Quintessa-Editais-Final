import re
import time
from urllib.parse import urljoin
try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page, parse_date_any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright não instalado. Rode 'pip install playwright && playwright install chromium'")
    raise

PROVIDER = {
    "name": "Plan International (Tenders)",
    "group": "Governo/Multilaterais"
}

START_URL = "https://plan-international.org/calls-tender/"

# Requisito 3: Palavras-chave obrigatórias para filtragem
KEYWORDS_FILTER = [
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento",
    "Tender", "Call", "RFP", "Proposal", "Consultancy"
]

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta editais da Plan International.
    Lida com cookies e renderização dinâmica via Playwright.
    """
    is_debug = _debug or str(cfg.get("PLAN_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[PLAN_INTERNATIONAL]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen = set()

    with sync_playwright() as p:
        # Requisito 2: Bypass de automação e headers reais
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            # 1. Acesso e Aceite de Cookies (Requisito 2)
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            log("Verificando banners de cookies...")
            try:
                # Localiza botões de aceitar (comuns em sites internacionais)
                cookie_btn = page.locator("button, a").filter(has_text=re.compile(r"Accept|Agree|Allow|Aceitar", re.I)).first
                if cookie_btn.is_visible(timeout=5000):
                    cookie_btn.click()
                    log("Banner de cookies aceito.")
                    time.sleep(1)
            except:
                log("Nenhum banner de cookie detectado.")

            # Aguarda a renderização dos elementos de lista
            page.wait_for_selector("article, .card, .entry-title, a", timeout=15000)
            
            # 2. Extração de links e títulos
            # A Plan International costuma listar itens em tabelas ou blocos de 'article'
            elements = page.locator("a").all()
            log(f"Analisando {len(elements)} links encontrados...")

            for el in elements:
                try:
                    raw_title = el.inner_text().strip()
                    href = el.get_attribute("href")

                    if not href or len(raw_title) < 5:
                        continue

                    full_link = urljoin(START_URL, href)
                    if full_link in seen or "plan-international.org" not in full_link:
                        continue

                    title = normalize(raw_title)
                    title_lower = title.lower()

                    # Requisito 3: Filtro de Palavras-Chave
                    if not any(k.lower() in title_lower for k in KEYWORDS_FILTER):
                        continue

                    # Filtro de Regex do Usuário (Integração com o sistema)
                    if regex and not regex.search(title):
                        continue

                    seen.add(full_link)

                    # 3. Extração de Metadados (Data e Valor)
                    # Tenta extrair data do texto ao redor (parent)
                    parent_text = el.locator("..").inner_text()
                    deadline = parse_date_any(parent_text)
                    
                    # Se não achou data na listagem, faz o scrape profundo (Requisito 1)
                    if not deadline:
                        deadline = scrape_deadline_from_page(full_link)

                    # Busca menções a valores monetários
                    raw_data = {}
                    price_match = re.search(r"(?:USD|GBP|EUR|£|\$)\s?[\d\.,]+", parent_text)
                    if price_match:
                        raw_data["estimated_value"] = price_match.group(0)

                    out.append({
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": full_link,
                        "deadline": deadline,
                        "published": None,
                        "agency": "Plan International",
                        "region": "Global",
                        "raw": raw_data
                    })
                    log(f"✅ Capturado: {title[:50]}... | Data: {deadline}")

                except Exception:
                    continue

        except Exception as e:
            log(f"Erro durante a execução: {e}")
        finally:
            browser.close()

    log(f"Total coletado: {len(out)}")
    return out

# Requisito 1: Modo de Teste Standalone
if __name__ == "__main__":
    import re
    print("\n--- TESTE STANDALONE: PLAN INTERNATIONAL ---\n")
    
    # Simula o regex "passa-tudo" do sistema
    dummy_regex = re.compile(r".*", re.IGNORECASE)
    
    # Executa com a flag de debug ativa
    try:
        results = fetch(dummy_regex, {}, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS DA CAPTURA ({len(results)} itens):")
        print("="*60)
        
        for i, item in enumerate(results):
            print(f"#{i+1}")
            print(f"  Título:   {item['title']}")
            print(f"  Link:     {item['link']}")
            print(f"  Deadline: {item['deadline']}")
            print(f"  Metadados: {item['raw']}")
            print("-" * 30)

    except Exception as e:
        print(f"ERRO FATAL NO TESTE: {e}")