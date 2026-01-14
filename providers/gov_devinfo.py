import re
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
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

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO CRÍTICO: Playwright não instalado. Rode: pip install playwright && playwright install chromium")
    sync_playwright = None

PROVIDER = {
    "name": "DevInfo (RFPs)",
    "group": "Governo/Multilaterais"
}

START_URL = "https://devinfo.in/request-for-proposals/"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_FILTER = [
    "edital", "editais", "chamada", "chamamento", "programa", "prémio", "premio", "credenciamento",
    "request for proposal", "rfp", "call", "grant", "program", "award", "opportunity", "water", "sustainability",
    "climate", "environment", "development", "social", "entrepreneurship", "impact", "technology", "development bank",
    "acceleration", "innovation", "tender", "consultancy",
    ]

# Regex captura data no início (ex: "December 26, 2024 ...")
RE_DATE_START = re.compile(r"^([A-Za-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE)

def fetch(regex, cfg, _debug: bool = False):
    if not sync_playwright:
        return []
    
    is_debug = _debug or str(cfg.get("DEVINFO_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[DEVINFO]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen_links = set()
    
    # Data de corte para otimização (ignora itens vencidos há mais de 60 dias direto no provider)
    # A filtragem fina (7 dias futuros) é feita pelo backend, mas aqui limpamos o lixo grosso.
    cutoff_date = datetime.now() - timedelta(days=60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Aceite de cookies
            try:
                cookie_btn = page.locator("button, a").filter(has_text=re.compile(r"Accept|Agree|Allow|Aceitar", re.I)).first
                if cookie_btn.is_visible(timeout=3000):
                    cookie_btn.click()
                    time.sleep(1)
            except:
                pass

            page.wait_for_selector("article, .post", timeout=15000)
            elements = page.locator("article a").all()
            log(f"Links brutos encontrados: {len(elements)}")

            for el in elements:
                try:
                    title_raw = el.inner_text().strip()
                    href_raw = el.get_attribute("href")

                    if not title_raw or not href_raw:
                        continue
                    
                    # 1. Normaliza Título Inicial
                    title = normalize(title_raw)
                    full_link = href_raw 
                    if "http" not in full_link:
                        full_link = urljoin(START_URL, full_link)

                    if len(title) < 5 or title.lower() in ["read more", "leia mais"]:
                        continue

                    # 2. Filtro de Palavras-Chave
                    title_lower = title.lower()
                    if not any(k in title_lower for k in KEYWORDS_FILTER):
                        continue

                    if full_link in seen_links:
                        continue
                    seen_links.add(full_link)

                    # 3. Extração e REMOÇÃO da Data do Título
                    deadline = None
                    date_match = RE_DATE_START.search(title)
                    
                    if date_match:
                        date_str = date_match.group(1)
                        deadline = parse_date_any(date_str)
                        
                        # OTIMIZAÇÃO: Se a data foi achada e é muito antiga, ignora agora mesmo.
                        if deadline and deadline.replace(tzinfo=None) < cutoff_date:
                            # log(f"Ignorado (Muito antigo): {deadline}")
                            continue

                        # Limpa o título (remove a data)
                        title = title.replace(date_str, "").strip()
                        title = re.sub(r"^[:\-\–\s]+", "", title)

                    # 4. Filtro Regex do Usuário
                    if regex and not regex.search(title):
                        continue
                    
                    # Fallback de data
                    if not deadline:
                        deadline = scrape_deadline_from_page(full_link)

                    item = {
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": full_link,
                        "deadline": deadline,
                        "published": None,
                        "agency": "DevInfo / Various",
                        "region": "Global",
                        "raw": {}
                    }
                    out.append(item)
                    log(f"✅ Capturado: {title[:50]}... | Data: {deadline}")

                except Exception:
                    continue

        except Exception as e:
            log(f"Erro durante a navegação: {e}")
        finally:
            browser.close()

    log(f"Total final coletado: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    from datetime import datetime, timedelta
    
    print("\n--- TESTE STANDALONE: DEVINFO.IN (FILTRANDO VÁLIDOS) ---\n")
    
    # Simula o filtro de "7 dias a partir de hoje"
    MIN_DAYS = 7
    hoje = datetime.now()
    limite = hoje + timedelta(days=MIN_DAYS)
    
    dummy_regex = re.compile(r".*", re.IGNORECASE)
    
    try:
        # Roda a coleta (que traz tudo o que não é "muito antigo")
        raw_results = fetch(dummy_regex, {}, _debug=True)
        
        valid_results = []
        ignored_count = 0
        
        # Aplica a regra de negócio do backend aqui no teste visual
        for item in raw_results:
            dl = item['deadline']
            if dl:
                # Remove timezone para comparação simples
                dl_naive = dl.replace(tzinfo=None) if dl else None
                if dl_naive and dl_naive >= limite:
                    valid_results.append(item)
                else:
                    ignored_count += 1
            else:
                # Se não tem data, geralmente o sistema aceita para verificação manual
                valid_results.append(item)

        print("\n" + "="*60)
        print(f"RELATÓRIO DO TESTE")
        print("="*60)
        print(f"Total bruto coletado: {len(raw_results)}")
        print(f"Ignorados (Prazo < {MIN_DAYS} dias ou vencidos): {ignored_count}")
        print(f"VÁLIDOS PARA O SISTEMA: {len(valid_results)}")
        print("="*60)
        
        if valid_results:
            for i, item in enumerate(valid_results[:5]): # Mostra top 5
                print(f"#{i+1}")
                print(f"  Título:   {item['title']}")
                print(f"  Link:     {item['link']}")
                print(f"  Deadline: {item['deadline']}") 
                print("-" * 30)
        else:
            print("Nenhum item futuro encontrado nesta execução.")
            
    except Exception as e:
        print(f"ERRO FATAL NO TESTE: {e}")