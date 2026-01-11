# providers/gov_idb_consultation.py
import re
import time
from typing import List, Dict, Any
from urllib.parse import urljoin

try:
    from .common import normalize
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PROVIDER = {
    "name": "IDB Public Consultations",
    "group": "Governo/Multilaterais"
}

# Começamos pela HOME para evitar erro de sessão
HOME_URL = "https://iadb.my.site.com/IDBPublicConsultation/s/?language=en_US"

def fetch(regex, cfg, _debug: bool = False) -> List[Dict[str, Any]]:
    if not sync_playwright:
        print("❌ Playwright não instalado.")
        return []

    is_debug = _debug or str(cfg.get("IDB_DEBUG", "0")).lower() in ("1", "true")

    def log(*args):
        if is_debug:
            print("[IDB_CONSULTATION]", *args)

    out = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Mantive visual para você acompanhar
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Acessa a Home
            log(f"🏠 Acessando Home: {HOME_URL}")
            page.goto(HOME_URL, timeout=60000)
            page.wait_for_load_state("networkidle")
            time.sleep(5)

            # 2. Tenta navegar para a página de interesse
            # Procura links ou botões que tenham "What we do" ou "Consultations"
            log("🔎 Procurando botão de navegação 'What we do'...")
            
            # Tenta clicar no link do menu se existir
            clicked = False
            for menu_text in ["What we do", "Public Consultations", "Consultas Públicas"]:
                try:
                    # Busca link visível com esse texto
                    link = page.get_by_role("link", name=re.compile(menu_text, re.I)).first
                    if link.is_visible():
                        log(f"🖱️ Clicando em '{menu_text}'...")
                        link.click()
                        clicked = True
                        break
                    
                    # Fallback: busca qualquer texto clicável
                    elem = page.get_by_text(menu_text, exact=True).first
                    if elem.is_visible():
                        log(f"🖱️ Clicando no texto '{menu_text}'...")
                        elem.click()
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                log("⚠️ Não achei o menu. Tentando ir para URL direta agora que a sessão iniciou...")
                page.goto("https://iadb.my.site.com/IDBPublicConsultation/s/what-we-do?language=en_US")
            
            # 3. Aguarda carregamento da lista
            log("⏳ Aguardando lista carregar...")
            page.wait_for_load_state("networkidle")
            time.sleep(6) # Espera generosa para o Salesforce montar a tabela

            # 4. Extração
            # Salesforce costuma usar artigos ou cards. Vamos pegar tudo que for link.
            anchors = page.locator("a").all()
            log(f"🔍 Links encontrados: {len(anchors)}")

            # Screenshot para debug se falhar
            page.screenshot(path="debug_nav.png")

            for a in anchors:
                try:
                    href = a.get_attribute("href")
                    txt = (a.inner_text() or "").strip().replace("\n", " ")
                    
                    if not href or len(txt) < 5: continue
                    if any(x in href.lower() for x in ["javascript:", "facebook", "twitter", "linkedin", "home", "refresh"]):
                        continue

                    full_link = urljoin(HOME_URL, href)
                    title = normalize(txt)

                    # Filtro de regex
                    if regex and not regex.search(title):
                        continue

                    if full_link in seen: continue
                    seen.add(full_link)

                    out.append({
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": full_link,
                        "deadline": None,
                        "published": None,
                        "agency": "IDB",
                        "region": "LatAm",
                        "raw": {}
                    })
                    log(f"✅ Item: {title[:50]}...")

                except Exception:
                    continue

        except Exception as e:
            log(f"❌ Erro: {e}")
        finally:
            browser.close()

    log(f"🏁 Fim. Total: {len(out)}")
    return out

if __name__ == "__main__":
    import json
    # Regex genérico para teste
    mock_regex = re.compile(r".*", re.I)
    fetch(mock_regex, cfg={}, _debug=True)