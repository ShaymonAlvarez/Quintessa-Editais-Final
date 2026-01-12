# -*- coding: utf-8 -*-
# providers/funda_freedomfund.py

import re
import time
from urllib.parse import urljoin

# ============================================================
# 1. IMPORTS HÍBRIDOS (Suporte a Standalone e Sistema)
# ============================================================
try:
    # Importação relativa funciona quando rodado via main.py
    from .common import normalize, parse_date_any, scrape_deadline_from_page
except ImportError:
    # Fallback para rodar direto do terminal (python providers/funda_freedomfund.py)
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # Mock simples caso common não seja encontrado no teste isolado
    try:
        from providers.common import normalize, parse_date_any, scrape_deadline_from_page
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def parse_date_any(x): return None
        def scrape_deadline_from_page(x): return None

# Tenta importar Playwright
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("AVISO: Playwright não instalado. O provider Freedom Fund pode não funcionar corretamente.")

# ============================================================
# 2. CONFIGURAÇÃO
# ============================================================
PROVIDER = {
    "name": "The Freedom Fund",
    "group": "Fundações e Prêmios"
}

START_URL = "https://www.freedomfund.org/careers/"

# Filtros solicitados (PT) + Equivalentes em Inglês (pois o site é EN)
KEYWORDS_FILTER = [
    # Termos solicitados (PT)
    "edital", "propostas", "propostas", "editais", "chamada", "chamamento", "programa", "prémio", "premio", "credenciamento",
    # Termos técnicos equivalentes no site (EN) para garantir que funcione
    "call", "request for proposals", "rfp", "grant", "consultancy", "tender", "opportunity", "program"
]

# Regex para tentar capturar data no texto curto (ex: Deadline: 25 Jan 2025)
RE_DEADLINE_TEXT = re.compile(r"(?:Deadline|Closing date)[:\.]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)

# ============================================================
# 3. FUNÇÃO FETCH
# ============================================================
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta oportunidades do Freedom Fund.
    Usa Playwright para lidar com cookies e renderização dinâmica.
    """
    if not sync_playwright:
        return []

    is_debug = _debug or str(cfg.get("FREEDOM_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[FREEDOM_FUND]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen_links = set()

    with sync_playwright() as p:
        # headless=True para produção, False se quiser ver o navegador abrindo no debug
        browser = p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Contexto com User-Agent real
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # --- TRATAMENTO DE COOKIES / POPUPS ---
            log("Verificando banners de cookies...")
            try:
                # Procura botões comuns de aceite
                cookie_btn = page.locator("button, a").filter(has_text=re.compile(r"accept|agree|allow|cookie|dismiss", re.I)).first
                if cookie_btn.is_visible():
                    log("Clicando no aceite de cookies...")
                    cookie_btn.click(timeout=3000)
                    time.sleep(1) # Espera banner sumir
            except Exception:
                pass # Se não achar ou falhar, segue o jogo

            # Espera carregar a lista de vagas/editais
            time.sleep(3)

            # --- EXTRAÇÃO ---
            # Pega todos os links da área principal (evita header/footer se possível)
            # O site usa classes como 'careers-list' ou similar, mas vamos pegar links genéricos para garantir
            all_links = page.locator("a[href]").all()
            log(f"Links totais analisados: {len(all_links)}")

            for a in all_links:
                try:
                    href_raw = a.get_attribute("href")
                    text_raw = (a.inner_text() or "").strip()
                    
                    if not href_raw or len(text_raw) < 5:
                        continue

                    # Filtra links âncora ou js
                    if href_raw.startswith("#") or "javascript:" in href_raw.lower():
                        continue

                    # Filtro de navegação interna irrelevante
                    if any(x in href_raw for x in ["/contact", "/team", "/donate", "twitter", "facebook", "linkedin"]):
                        continue

                    full_link = urljoin(START_URL, href_raw)
                    title = normalize(text_raw)
                    title_lower = title.lower()

                    # --- FILTRO 1: Palavras-Chave Obrigatórias ---
                    # Verifica se contém algum dos termos (PT ou EN)
                    if not any(k in title_lower for k in KEYWORDS_FILTER):
                        continue

                    # --- FILTRO 2: Regex do Usuário (se houver) ---
                    if regex and not regex.search(title):
                        continue
                    
                    if full_link in seen_links: continue
                    seen_links.add(full_link)

                    # --- EXTRAÇÃO DE METADADOS ---
                    deadline = None
                    
                    # 1. Tenta achar data no texto do link (Ex: "Consultancy - Deadline 20 Jan")
                    m_date = RE_DEADLINE_TEXT.search(title)
                    if m_date:
                        deadline = parse_date_any(m_date.group(1))
                    
                    # 2. Se não achou, tenta achar no texto ao redor (elemento pai)
                    # (Lógica: às vezes a data está numa div <p> ao lado do link)
                    if not deadline:
                        try:
                            parent_text = a.locator("..").inner_text() # Texto do elemento pai
                            m_date_parent = RE_DEADLINE_TEXT.search(parent_text)
                            if m_date_parent:
                                deadline = parse_date_any(m_date_parent.group(1))
                        except:
                            pass

                    # 3. Fallback final: Scraper profundo (entra na página)
                    # Só ativamos se não achou nada, para não ficar lento
                    if not deadline:
                        deadline = scrape_deadline_from_page(full_link)

                    # Tenta achar valor (USD/GBP)
                    raw_data = {}
                    price_match = re.search(r"(?:£|\$|USD|GBP)\s?[\d,]+", title)
                    if price_match:
                        raw_data["value_estimate"] = price_match.group(0)

                    out.append({
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": full_link,
                        "deadline": deadline,
                        "published": None,
                        "agency": "The Freedom Fund",
                        "region": "Global",
                        "raw": raw_data
                    })
                    
                    log(f"✅ Capturado: {title[:50]}... | Prazo: {deadline}")

                except Exception as e:
                    # log(f"Erro ao processar item: {e}")
                    continue

        except Exception as e:
            log(f"Erro crítico no Playwright: {e}")
        finally:
            browser.close()

    log(f"Total final coletado: {len(out)}")
    return out

# ============================================================
# 4. MODO TESTE (STANDALONE)
# ============================================================
if __name__ == "__main__":
    print("\n>>> TESTE STANDALONE: THE FREEDOM FUND <<<\n")
    
    # Regex que aceita tudo para testar a captura bruta
    dummy_regex = re.compile(r".*", re.I)
    
    # Ativa debug forçado via config
    dummy_cfg = {"FREEDOM_DEBUG": "1"}

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        if not results:
            print("Nenhum item encontrado. Verifique se o site mudou ou se os termos em inglês estão cobrindo as vagas atuais.")
            print("Dica: O site Freedom Fund é em inglês, termos como 'Edital' puro podem não existir lá.")
        
        for item in results:
            print(f"Título: {item['title']}")
            print(f"Link:   {item['link']}")
            print(f"Prazo:  {item['deadline']}")
            if item['raw']:
                print(f"Info:   {item['raw']}")
            print("-" * 30)
            
    except Exception as e:
        print(f"ERRO: {e}")
        import traceback
        traceback.print_exc()