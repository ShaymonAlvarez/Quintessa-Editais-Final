import re
import time
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("ERRO CRÍTICO: Playwright não instalado. Instale com 'pip install playwright'.")

PROVIDER = {
    "name": "Prosas (Apenas Editais)",
    "group": "Brasil"
}

START_URL = "https://prosas.com.br/editais"

def fetch(regex, cfg, _debug: bool = False):
    if not sync_playwright:
        return []

    out = []
    seen_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            if _debug: print(f"--- Acessando {START_URL} ---")
            page.goto(START_URL, timeout=60000)

            # 1. Espera genérica para garantir que o site carregou
            # Esperamos aparecer qualquer link que leve para um edital
            try:
                page.wait_for_selector("a[href*='/editais/']", timeout=20000)
            except:
                if _debug: print("Aviso: Demora no carregamento, tentando ler mesmo assim...")

            # Scroll para garantir que os itens apareçam (Lazy load)
            page.evaluate("window.scrollBy(0, 3000)")
            time.sleep(3)

            # 2. Coleta Simples (Baseada nos Links e Títulos)
            # Esta estratégia é mais robusta que procurar por "cards"
            items_raw = page.evaluate("""() => {
                const data = [];
                // Pega todos os links que contêm '/editais/' na URL
                const links = Array.from(document.querySelectorAll("a[href*='/editais/']"));
                
                links.forEach(a => {
                    const href = a.getAttribute('href');
                    // Ignora links de navegação geral
                    if (href === '/editais' || href === '/editais/') return;

                    // O texto do link geralmente é o título ou 'Ver mais'. 
                    // Se for curto, tentamos pegar o título de um elemento pai.
                    let title = a.innerText.trim();
                    
                    // Se o link não tiver texto útil, tenta achar um cabeçalho próximo
                    if (title.length < 5 || title.toLowerCase().includes('acessar')) {
                        // Tenta subir 2 níveis para achar o container e procurar um título H1-H5
                        let parent = a.parentElement.parentElement;
                        if (parent) {
                            let h = parent.querySelector('h1, h2, h3, h4, h5, .title');
                            if (h) title = h.innerText.trim();
                        }
                    }

                    data.push({ title: title, href: href });
                });
                return data;
            }""")

            if _debug: print(f"Itens brutos encontrados: {len(items_raw)}")

            # Palavras-chave obrigatórias para funcionamento do código
            palavras_chave_permitidas = ['EDITAL', 'CHAMAMENTO', 'SELEÇÃO', 'CONVOCATÓRIA']
            palavras_chave_proibidas = ['PRÊMIO', 'PROGRAMA', 'CONCURSO', 'CREDENCIAMENTO']

            for item in items_raw:
                title = item['title'].strip()
                link = urljoin(START_URL, item['href'])

                # Remove duplicados
                if link in seen_links: continue
                seen_links.add(link)

                # LÓGICA DE FILTRO 
                title_upper = title.upper()

                # Se tiver palavra proibida (ex: Prêmio), ignora imediatamente
                if any(bad in title_upper for bad in palavras_chave_proibidas):
                    continue

                # Se NÃO tiver nenhuma palavra permitida (ex: Edital), ignora
                if not any(good in title_upper for good in palavras_chave_permitidas):
                    continue

                out.append({
                    "title": title,
                    "link": link,
                    "source": PROVIDER["name"]
                })

        except Exception as e:
            if _debug: print(f"Erro durante execução: {e}")
        finally:
            browser.close()

    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    print("\n>>> INICIANDO FILTRO DE EDITAIS PROSAS <<<\n")
    
    # Chama a função principal
    resultados = fetch(None, {}, _debug=True)

    print("\n" + "="*60)
    print(f"RELATÓRIO FINAL: {len(resultados)} EDITAIS ENCONTRADOS")
    print("="*60 + "\n")

    if len(resultados) == 0:
        print("Nenhum edital encontrado com os filtros atuais.")
        print("Dica: Verifique se o site mudou ou se os termos de busca estão muito restritos.")
    else:
        for i, item in enumerate(resultados, 1):
            print(f"{i}. {item['title']}")
            print(f"   Link: {item['link']}")
            print("-" * 60)