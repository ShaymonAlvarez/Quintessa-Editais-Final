import time
import traceback
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
    print("ERRO CRÍTICO: Playwright não instalado. Rode: pip install playwright && playwright install chromium")
    raise

PROVIDER = {
    "name": "UNDP — Procurement Notices (Web)",
    "group": "Governo/Multilaterais"
}

BASE_URL = "https://procurement-notices.undp.org/index.cfm?cur_lang=en"

def fetch(regex, cfg):
    print(f"[UNDP Web] Iniciando coleta V3 (Robust)...")
    out = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, # Mude para False se quiser ver o navegador abrindo
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Viewport grande para garantir que a tabela não fique em modo mobile
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 1. Acessa a página (com timeout generoso de 60s)
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            print("[UNDP Web] Site acessado.")

            # 2. Espera Visual por TEXTO (Mais confiável que esperar tag table)
            # Esperamos aparecer a palavra "Deadline" ou "Title" que são cabeçalhos da tabela
            print("[UNDP Web] Aguardando tabela aparecer...")
            try:
                # Espera até 20s para aparecer o texto 'Deadline'
                page.wait_for_selector("text=Deadline", timeout=20000)
                print("[UNDP Web] Tabela detectada visualmente.")
            except:
                print("[UNDP Web] Aviso: Texto 'Deadline' demorou. Tentando ler HTML mesmo assim...")

            # Pausa de segurança para garantir renderização das linhas
            time.sleep(5)

            # 3. EXTRAÇÃO VIA JS (Varredura Total)
            raw_data = page.evaluate(r"""() => {
                const results = [];
                // Pega TODAS as linhas de tabela da página inteira
                const rows = Array.from(document.querySelectorAll('tr'));
                
                rows.forEach(row => {
                    const cells = Array.from(row.querySelectorAll('td'));
                    
                    // O site do UNDP tem tabelas de layout. 
                    // A tabela de dados reais geralmente tem 4 ou mais colunas preenchidas.
                    if (cells.length < 4) return;

                    // Tenta achar link na primeira célula
                    const col0 = cells[0];
                    const anchor = col0.querySelector('a');
                    
                    // Texto do Título
                    const title = anchor ? anchor.innerText.trim() : col0.innerText.trim();
                    const href = anchor ? anchor.getAttribute('href') : "";
                    
                    // Ignora linhas vazias ou sem título
                    if (!title || title.length < 3) return;

                    // Captura texto das colunas seguintes para tentar achar a data no Python
                    const txtCols = cells.map(c => c.innerText.trim());

                    results.push({
                        title: title,
                        href: href,
                        cols: txtCols // Manda todas as colunas para processar no backend
                    });
                });
                return results;
            }""")
            
            print(f"[UNDP Web] Linhas brutas encontradas: {len(raw_data)}")
            
            # TESTEE DEBUG: Se vier 0, tira um print para vermos o que houve
            if len(raw_data) == 0:
                page.screenshot(path="undp_debug.png")
                print("[UNDP Web] 0 itens. Screenshot salvo em 'undp_debug.png'")

        except Exception as e:
            print(f"[UNDP Web] Erro de navegação: {e}")
            browser.close()
            return []
        
        browser.close()

        # 4. Processamento Python
        for item in raw_data:
            title = normalize(item['title'])
            
            # Filtra cabeçalhos da tabela que foram capturados como linha
            if title.lower() in ["title", "description", "reference"]:
                continue

            if regex and not regex.search(title):
                continue
            
            # Monta link absoluto
            full_link = urljoin(BASE_URL, item['href']) if item['href'] else BASE_URL

            # Tenta achar a data (Deadline) nas colunas capturadas
            deadline = None
            cols = item.get('cols', [])
            
            # Geralmente a data está na coluna índice 2 ou 3
            # Iteramos pelas colunas procurando algo que pareça data
            for c_txt in cols[1:]: # Pula a primeira (título)
                dt = parse_date_any(c_txt)
                if dt:
                    deadline = dt
                    break # Achou a primeira data, assume que é o deadline

            # Tenta achar data de publicação (Posted) na coluna 1
            published = None
            if len(cols) > 1:
                published = parse_date_any(cols[1])

            out.append({
                "source": PROVIDER["name"],
                "title": title[:200],
                "link": full_link,
                "deadline": deadline,
                "published": published,
                "agency": "UNDP",
                "region": "Global",
                "raw": {}
            })

    # Deduplicação
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
    
    print("\n--- TESTE: UNDP WEB (V3 - ROBUST) ---")
    
    try:
        regex_teste = re.compile(r".", re.IGNORECASE)
        items = fetch(regex_teste, {})
        
        print(f"\nSTATUS FINAL: {len(items)} itens coletados.")
        
        if items:
            print("\nExemplo 1:")
            print(json.dumps(items[0], indent=4, default=str, ensure_ascii=False))
        else:
            print("AVISO: 0 itens. Verifique a imagem 'undp_debug.png' gerada na pasta.")
            
    except Exception as err:
        print("\n!!! ERRO FATAL !!!")
        traceback.print_exc()