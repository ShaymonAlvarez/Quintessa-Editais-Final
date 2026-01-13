import re
import time
from urllib.parse import urljoin

try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    # Adiciona o diretório pai ao path para encontrar o pacote 'providers'
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # Mock simples caso common não seja encontrado no teste isolado
    try:
        from providers.common import normalize, scrape_deadline_from_page, parse_date_any
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return None

# Tenta importar Playwright
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright não instalado. Rode 'pip install playwright && playwright install chromium'")
    raise

PROVIDER = {
    "name": "Fundación Avina",
    "group": "Fundações e Prêmios"
}

START_URL = "https://www.avina.net/pt/consultoria/"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_FILTER = [
    "Edital", "Editais", "Chamada", "Consultoria", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento"
]

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta consultorias/editais da Avina.
    """
    is_debug = _debug or str(cfg.get("AVINA_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[AVINA]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen = set()

    with sync_playwright() as p:
        # headless=True para produção, mas pode mudar para False se quiser ver o browser abrindo
        browser = p.chromium.launch(headless=True)
        
        # Cria contexto com User-Agent real para evitar bloqueios simples
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            # 1. Acesso à página
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # 2. Tratamento de Cookies (Requisito 2)
            # Procura botões comuns de aceite de cookie para limpar a tela
            log("Verificando cookies...")
            try:
                # Seletores comuns de plugins de cookie WordPress
                cookie_btn = page.locator("a#cookie_action_close_header, button#onetrust-accept-btn-handler, .cc-btn").first
                if cookie_btn.is_visible():
                    cookie_btn.click()
                    log("Banner de cookies fechado.")
                    time.sleep(1)
            except:
                pass # Se não achar ou falhar, segue o baile

            # Aguarda renderização dos cards/artigos
            # O site usa <article> para listar os itens
            try:
                page.wait_for_selector("article", timeout=15000)
            except:
                log("Timeout aguardando 'article'. Tentando ler HTML mesmo assim.")

            # 3. Extração dos Elementos
            # Pega todos os artigos da página
            articles = page.locator("article").all()
            log(f"Encontrados {len(articles)} artigos na página.")

            for art in articles:
                # Tenta pegar o título (geralmente h2, h3 ou h4 dentro do article)
                title_el = art.locator("h2, h3, h4, .entry-title").first
                link_el = art.locator("a").first
                
                if not title_el.count() or not link_el.count():
                    continue

                raw_title = title_el.inner_text()
                href = link_el.get_attribute("href")
                
                if not href or not raw_title:
                    continue

                title = normalize(raw_title)
                full_link = urljoin(START_URL, href)

                # --- FILTRO 1: Palavras-Chave Obrigatórias (Requisito 3) ---
                if not any(k.lower() in title.lower() for k in KEYWORDS_FILTER):
                    # log(f"Ignorado (Keyword): {title}")
                    continue

                # --- FILTRO 2: Regex do Usuário (Padrão do sistema) ---
                if regex and not regex.search(title):
                    continue

                if full_link in seen:
                    continue
                seen.add(full_link)

                # --- Extração de Metadados (Requisito 1) ---
                # Tenta extrair texto do card para achar datas ou valores
                card_text = art.inner_text()
                
                # Data (Deadline)
                deadline = parse_date_any(card_text)
                
                # Se não achou data no card, tenta scraping profundo na página do edital
                # (Isso deixa o processo mais lento, mas mais preciso)
                if not deadline:
                    try:
                        deadline = scrape_deadline_from_page(full_link)
                    except:
                        pass

                # Preço/Valor (Regex simples para moedas)
                raw_data = {}
                price_match = re.search(r"(?:USD|BRL|R\$|\$)\s?[\d\.,]+", card_text)
                if price_match:
                    raw_data["estimated_value"] = price_match.group(0)

                item = {
                    "source": PROVIDER["name"],
                    "title": title[:180],
                    "link": full_link,
                    "deadline": deadline,
                    "published": None,
                    "agency": "Fundación Avina",
                    "region": "LatAm",
                    "raw": raw_data
                }
                
                out.append(item)
                log(f"✅ Capturado: {title[:50]}... | Data: {deadline}")

        except Exception as e:
            log(f"Erro durante a execução: {e}")
        finally:
            browser.close()

    log(f"Total coletado: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    import json
    
    print("\n--- TESTE STANDALONE: FUNDAÇÃO AVINA ---\n")
    
    # Regex que aceita tudo para validar a captura
    dummy_regex = re.compile(r".*", re.I)
    
    # Executa com debug ativado
    try:
        results = fetch(dummy_regex, {}, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        for i, item in enumerate(results):
            print(f"#{i+1}")
            print(f"  Título:   {item['title']}")
            print(f"  Link:     {item['link']}")
            print(f"  Deadline: {item['deadline']}")
            print(f"  Infos:    {item['raw']}")
            print("-" * 30)

    except Exception as e:
        print(f"ERRO FATAL: {e}")