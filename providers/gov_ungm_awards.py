import time
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

try:
    from .common import normalize, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, parse_date_any

PROVIDER = {
    "name": "UNGM — Contract Awards",
    "group": "Governo/Multilaterais"
}

BASE_URL = "https://www.ungm.org/Public/ContractAward"

def fetch(regex, cfg):
    print(f"[{PROVIDER['name']}] Iniciando coleta...")
    
    # Palavras-chave atualizadas
    keywords = [
        "Edital", "Editais", "Chamada", "Programa", "Prêmio", "Credenciamento", "Aceleração", "Inovação",
        "Acceleration", "Call for Proposals", "Funding Opportunity", "Request for Proposals", "RFP", 
        "Tender", "Grant", "Water", "Forest", "Climate", "Sustainability", "Ambiental", "Sustentabilidade", "Environment",
        "Development", "Social", "Entrepreneurship", "Impact", "Technology", "Development Bank", "Innovation", "Consultancy", 
        "Consulting", "Program",
    ]
    kw_pattern = re.compile(r"|".join(keywords), re.IGNORECASE)
    
    out = []
    
    with sync_playwright() as p:
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
            # Aumentamos o timeout e esperamos a página ficar estável (networkidle)
            page.goto(BASE_URL, timeout=90000, wait_until="networkidle")

            # 1. Aceite de Cookies
            try:
                cookie_button = page.locator("button:has-text('Accept'), button:has-text('Agree')").first
                if cookie_button.is_visible(timeout=5000):
                    cookie_button.click()
            except:
                pass

            # 2. Esperar especificamente pelo conteúdo da tabela (links de contrato)
            # O site da UNGM usa classes específicas ou links que contêm 'ContractAward'
            page.wait_for_selector("a[href*='/ContractAward/']", timeout=30000)
            
            # Scroll para garantir renderização de elementos lazy-load
            page.mouse.wheel(0, 1000)
            time.sleep(2)

            # 3. Extração via JS
            raw_data = page.evaluate("""() => {
                const results = [];
                // Selecionamos as linhas que realmente contêm dados (geralmente dentro do tbody)
                const rows = Array.from(document.querySelectorAll('table tr')).slice(1); 
                
                rows.forEach(row => {
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells.length < 5) return;

                    const anchor = row.querySelector('a[href*="/ContractAward/"]');
                    
                    results.push({
                        title: anchor ? anchor.innerText.trim() : cells[0].innerText.trim(),
                        href: anchor ? anchor.getAttribute('href') : "",
                        date: cells[2] ? cells[2].innerText.trim() : "",
                        agency: cells[3] ? cells[3].innerText.trim() : "",
                        country: cells[5] ? cells[5].innerText.trim() : "Global",
                        value: cells[4] ? cells[4].innerText.trim() : ""
                    });
                });
                return results;
            }""")

            print(f"[{PROVIDER['name']}] Linhas brutas encontradas: {len(raw_data)}")

        except Exception as e:
            print(f"[{PROVIDER['name']}] Erro: {e}")
            browser.close()
            return []
        
        browser.close()

        # 4. Filtragem
        for item in raw_data:
            title = normalize(item['title'])
            
            # Se o título estiver vazio, ignora
            if not title or len(title) < 5:
                continue

            # Filtro de Palavras-chave
            if not kw_pattern.search(title):
                continue

            # Filtro de Regex (vinda do sistema)
            if regex and not regex.search(title):
                continue

            published_date = parse_date_any(item['date'])
            full_link = urljoin(BASE_URL, item['href']) if item['href'] else BASE_URL
            
            out.append({
                "source": PROVIDER["name"],
                "title": title[:200],
                "link": full_link,
                "deadline": None,
                "published": published_date,
                "agency": normalize(item['agency']),
                "region": normalize(item['country']),
                "raw": {"amount": item['value']}
            })

    # Remove duplicatas
    return list({v['link']: v for v in out}.values())

if __name__ == "__main__":
    import re
    print(f"\n--- TESTE STANDALONE: {PROVIDER['name']} ---")
    test_regex = re.compile(r".") 
    
    results = fetch(test_regex, {})
    print(f"\nColeta finalizada! {len(results)} itens passaram pelos filtros de palavras-chave.")
    
    for i, res in enumerate(results[:10]):
        print(f"[{i+1}] {res['title']} | Valor: {res['raw']['amount']}")