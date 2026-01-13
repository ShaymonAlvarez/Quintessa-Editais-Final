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
    print("ERRO: Playwright não instalado. Rode 'pip install playwright && playwright install chromium'")
    raise

PROVIDER = {
    "name": "UNESCO Brasília - Processos Seletivos",
    "group": "Governo/Multilaterais"
}

BASE_URL = "https://roster.brasilia.unesco.org/app/selection-process-list"

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta editais da UNESCO Brasília usando Playwright.
    Aceita a flag _debug para imprimir logs detalhados (usado no modo standalone).
    """
    
    is_debug = _debug or str(cfg.get("UNESCO_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[UNESCO]", *args)

    log(f"Iniciando coleta em: {BASE_URL}")
    out = []
    
    with sync_playwright() as p:
        # headless=False se estiver debugando para ver o navegador
        browser = p.chromium.launch(
            headless=not is_debug, 
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 1. Acessa a página
            page.goto(BASE_URL, timeout=60000)
            
            # 2. Espera a lista carregar
            # O site é Angular/React, precisamos esperar os cards aparecerem
            log("Aguardando carregamento da lista...")
            try:
                # Tenta esperar por um seletor comum de lista ou card
                # Inspecionando visualmente sites desse tipo, costumam ter classes de card ou list-item
                page.wait_for_selector("div.card, mat-card, .list-item", timeout=20000)
                # Pausa extra para garantir renderização completa dos textos
                time.sleep(3)
            except:
                log("Timeout aguardando seletor específico. Tentando extrair assim mesmo...")

            # 3. Extração via JavaScript (Mais robusto para SPAs)
            raw_data = page.evaluate(r"""() => {
                const results = [];
                // Tenta pegar os elementos que parecem ser os cards de edital
                // Ajuste os seletores abaixo conforme a estrutura real do HTML renderizado
                const cards = Array.from(document.querySelectorAll('mat-card, .card, .selection-process-item'));
                
                cards.forEach(card => {
                    // Título geralmente está num h3, h4 ou strong
                    const titleEl = card.querySelector('h3, h4, .title, strong');
                    const title = titleEl ? titleEl.innerText.trim() : "";
                    
                    // Link: às vezes é o próprio card ou um botão 'ver mais'
                    const linkEl = card.querySelector('a[href]');
                    const href = linkEl ? linkEl.getAttribute('href') : "";
                    
                    // Texto completo do card para extração de data/preço
                    const fullText = card.innerText;

                    if (title.length > 3) {
                        results.push({
                            title: title,
                            href: href,
                            full_text: fullText
                        });
                    }
                });
                return results;
            }""")
            
            log(f"Elementos brutos encontrados: {len(raw_data)}")

        except Exception as e:
            log(f"Erro na navegação: {e}")
            browser.close()
            return []
        
        browser.close()
        seen_links = set()
        
        for item in raw_data:
            title = normalize(item['title'])
            full_text = normalize(item['full_text'])
            
            if regex and not regex.search(title) and not regex.search(full_text):
                continue
                
            # Tratamento do Link
            link_rel = item['href']
            if not link_rel:
                full_link = BASE_URL
            else:
                full_link = urljoin(BASE_URL, link_rel)

            if full_link in seen_links and full_link != BASE_URL:
                continue
            seen_links.add(full_link)

            # Extração de Data (Deadline)
            # Procura padrões comuns de data no texto do card: dd/mm/aaaa
            deadline = None
            dates = re.findall(r"\d{2}/\d{2}/\d{4}", full_text)
            if dates:
                # Assume a última data encontrada como prazo (comum em editais: publ... prazo)
                deadline = parse_date_any(dates[-1])

            agency = "UNESCO"
            if "Projeto" in full_text:
                parts = full_text.split("Projeto")
                if len(parts) > 1:
                    proj_code = parts[1].split()[0] 
                    agency = f"UNESCO - Proj {proj_code}"

            item_out = {
                "source": PROVIDER["name"],
                "title": title[:200],
                "link": full_link,
                "deadline": deadline,
                "published": None, 
                "agency": agency,
                "region": "Brasil",
                "raw": {
                    "text_snippet": full_text[:100]
                }
            }
            
            out.append(item_out)
            log(f"Capturado: {title[:40]}... | Deadline: {deadline}")

    log(f"Total final: {len(out)}")
    return out

if __name__ == "__main__":    
    print("\n--- TESTE STANDALONE: UNESCO BRASÍLIA ---\n")
    
    dummy_regex = re.compile(r".*", re.IGNORECASE)
    dummy_cfg = {}

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        
        print("\n" + "="*50)
        print(f"RESUMO DO TESTE: {len(results)} itens encontrados")
        print("="*50)
        
        if results:
            print("Exemplo do primeiro item encontrado:")
            item = results[0]
            print(f"Título:   {item['title']}")
            print(f"Link:     {item['link']}")
            print(f"Deadline: {item['deadline']}")
            print(f"Agência:  {item['agency']}")
            print(f"Raw:      {item['raw']}")
        else:
            print("Nenhum item encontrado. Verifique se o site mudou o layout ou se o Playwright está funcionando.")

    except Exception as e:
        print(f"ERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()