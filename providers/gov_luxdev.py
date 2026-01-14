import re
import time
from urllib.parse import urljoin

try:
    from .common import normalize, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, parse_date_any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("ERRO: Playwright não instalado.")

PROVIDER = {
    "name": "LuxDev Tenders",
    "group": "Governo/Multilaterais"
}

START_URL = "https://luxdev.lu/en/tenders/call-tenders"

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
KEYWORDS_FILTER = [
    "edital", "editais", "chamada", "chamamento", "programa", "prémio", "premio", "credenciamento",
    "call", "tender", "request", "appel", "offre", "procurement", "consulting", "acceleration", 
    "grant","water", "sustainability", "climate", "environment", "development", "social", "entrepreneurship", 
    "impact", "technology", "development bank", "innovation", "consultancy"
]

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
DENY_LIST = [
    "search tenders",
    "call for tenders",
    "calls for proposals",
    "procurement",
    "current page",
    "search",
    "next page",
    "previous page"
]

RE_DEADLINE_TEXT = re.compile(r"Deadline:?\s*(\d{2}[./-]\d{2}[./-]\d{4})", re.IGNORECASE)

def fetch(regex, cfg, _debug: bool = False):
    if not sync_playwright:
        return []

    is_debug = _debug or str(cfg.get("LUXDEV_DEBUG", "0")).lower() in ("1", "true")

    def log(*args):
        if is_debug:
            print("[LUXDEV]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Aceite de cookies (rápido)
            try:
                page.locator("button, a").filter(has_text=re.compile(r"accept|agree|j'accepte", re.I)).first.click(timeout=3000)
                time.sleep(1)
            except:
                pass

            # Aguarda a lista carregar um pouco
            time.sleep(3)

            # Pega todos os links da área de conteúdo
            all_links = page.locator("a[href]").all()
            log(f"Links brutos analisados: {len(all_links)}")

            for a in all_links:
                try:
                    href_raw = a.get_attribute("href")
                    # inner_text pega o texto visível e limpa espaços
                    text_raw = (a.inner_text() or "").strip()
                    
                    if not href_raw or not text_raw:
                        continue
                    
                    # FILTRO 1: Remover URLs de sistema
                    # Ignora links de filtro do Drupal (?f%5B0...)
                    if "?" in href_raw or "%" in href_raw:
                        continue
                    
                    # Ignora links estáticos irrelevantes
                    if any(x in href_raw for x in ["/contact", "/about", "linkedin", "twitter"]):
                        continue

                    # FILTRO 2: Tratamento do Título 
                    title = normalize(text_raw)
                    title_lower = title.lower()

                    # >>> BLOQUEIO EXPLÍCITO <<<
                    # Se o título contiver qualquer termo da lista proibida, pula.
                    if any(bad in title_lower for bad in DENY_LIST):
                        # log(f"Ignorado (Deny List): {title}")
                        continue

                    # Filtro de tamanho mínimo (Reforço: editais reais são frases longas)
                    if len(title) < 15:
                        continue

                    # --- FILTRO 3: Palavras-Chave Obrigatórias ---
                    if not any(k in title_lower for k in KEYWORDS_FILTER):
                        continue

                    full_link = urljoin(START_URL, href_raw)
                    
                    # Evita capturar a própria página de listagem como se fosse um edital
                    if full_link.rstrip('/') == START_URL.rstrip('/'):
                        continue

                    if full_link in seen_links: continue
                    seen_links.add(full_link)

                    # --- FILTRO 4: Regex do Usuário ---
                    if regex and not regex.search(title):
                        continue

                    # --- EXTRAÇÃO DE DATA ---
                    deadline = None
                    m_date = RE_DEADLINE_TEXT.search(title)
                    if m_date:
                        deadline = parse_date_any(m_date.group(1))

                    out.append({
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": full_link,
                        "deadline": deadline,
                        "published": None,
                        "agency": "LuxDev",
                        "region": "Global",
                        "raw": {}
                    })
                    
                    log(f"✅ Capturado: {title[:60]}... | Prazo: {deadline}")

                except Exception:
                    continue

        except Exception as e:
            log(f"Erro: {e}")
        finally:
            browser.close()

    log(f"Total final coletado: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    print("\n--- RODANDO EM MODO TESTE (LUXDEV V5 - BLOCKLIST) ---\n")
    dummy_regex = re.compile(r".*", re.I)
    try:
        results = fetch(dummy_regex, {"LUXDEV_DEBUG": "1"}, _debug=True)
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        for item in results:
            print(f"Titulo: {item['title']}")
            print(f"Link:   {item['link']}")
            print(f"Data:   {item['deadline']}")
            print("-" * 20)
    except Exception as e:
        print(f"ERRO: {e}")