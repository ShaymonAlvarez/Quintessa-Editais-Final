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

from playwright.sync_api import sync_playwright

PROVIDER = {
    "name": "UNGM — Contract Awards",
    "group": "Governo/Multilaterais"
}

BASE_URL = "https://www.ungm.org/Public/ContractAward"

def fetch(regex, cfg):
    print(f"[UNGM] Iniciando coleta V6 (Correção de Sintaxe JS)...")
    out = []
    
    with sync_playwright() as p:
        # headless=True padrão. Se falhar, mude para False para ver a tela.
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(BASE_URL, timeout=90000)
            print("[UNGM] Página acessada.")

            # 1. Cookies (Rápido)
            try:
                page.locator("button:has-text('Accept'), button:has-text('Agree')").first.click(timeout=4000)
                time.sleep(1)
            except:
                pass

            # 2. Espera visual pelos dados
            print("[UNGM] Aguardando dados na tela...")
            # Esperamos aparecer qualquer link de contrato (padrão do site)
            try:
                page.wait_for_selector("a[href*='/ContractAward/']", timeout=30000)
                print("[UNGM] Links de contrato detectados!")
            except:
                print("[UNGM] Aviso: Selector específico demorou. Tentando ler tabela bruta...")
                # Fallback: espera qualquer linha de tabela
                try:
                    page.wait_for_selector("tr", timeout=10000)
                except:
                    pass

            time.sleep(5) # Tempo extra para o grid terminar de desenhar

            # 3. EXTRAÇÃO VIA JAVASCRIPT 
            raw_data = page.evaluate(r"""() => {
                const results = [];
                // Pega TODAS as linhas de tabela da página
                const rows = Array.from(document.querySelectorAll('tr'));
                
                rows.forEach(row => {
                    // Pega todas as células (td) da linha
                    const cells = Array.from(row.querySelectorAll('td'));
                    
                    // Se tiver menos de 3 colunas, ignora (não é dado útil)
                    if (cells.length < 3) return;

                    // Coluna 0: Geralmente Título e Link
                    const col0 = cells[0];
                    const anchor = col0.querySelector('a');
                    const title = anchor ? anchor.innerText.trim() : col0.innerText.trim();
                    const href = anchor ? anchor.getAttribute('href') : "";

                    // Coluna 2: Data (baseado no seu print)
                    const dateTxt = cells[2] ? cells[2].innerText.trim() : "";

                    // Coluna 3: Agência
                    const agencyTxt = cells[3] ? cells[3].innerText.trim() : "";
                    
                    // Coluna 5: País/Região (se existir)
                    const countryTxt = cells[5] ? cells[5].innerText.trim() : "Global";

                    results.push({
                        title: title,
                        href: href,
                        date: dateTxt,
                        agency: agencyTxt,
                        country: countryTxt
                    });
                });
                return results;
            }""")
            
            print(f"[UNGM] Linhas extraídas via JS: {len(raw_data)}")

        except Exception as e:
            print(f"[UNGM] Erro Fatal: {e}")
            browser.close()
            return []
        
        browser.close()

        # 4. Processamento no Python
        count = 0
        for item in raw_data:
            title = normalize(item['title'])
            
            # Validação básica
            if len(title) < 5 or "Title" in title:
                continue

            # Filtro Regex
            if regex and not regex.search(title):
                continue

            # Data
            published_date = parse_date_any(item['date'])
            
            # Link
            full_link = urljoin(BASE_URL, item['href']) if item['href'] else BASE_URL
            
            # Agência
            agency = normalize(item['agency']) or "UN System"

            out.append({
                "source": PROVIDER["name"],
                "title": title[:200],
                "link": full_link,
                "deadline": None,
                "published": published_date,
                "agency": agency,
                "region": normalize(item['country']),
                "raw": {}
            })
            count += 1

    # Remove duplicatas
    unique_out = []
    seen = set()
    for x in out:
        if x['link'] not in seen:
            unique_out.append(x)
            seen.add(x['link'])

    return unique_out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    import json
    
    print("\n--- TESTE V6 (JS FIX): UNGM AWARDS ---")
    regex_teste = re.compile(r".", re.IGNORECASE)
    
    try:
        items = fetch(regex_teste, {})
        print(f"\nSTATUS: {len(items)} itens coletados.")
        
        if items:
            print(f"Exemplo: {items[0]['title']}")
            print(f"Data: {items[0]['published']}")
            print(f"Link: {items[0]['link']}")
    except Exception as e:
        print(f"Erro no teste: {e}")