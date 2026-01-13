import re
import time
from urllib.parse import urljoin

try:
    from .common import normalize, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path: sys.path.insert(0, ROOT)
    from providers.common import normalize, parse_date_any

try:
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup
except ImportError:
    print("ERRO: Execute 'pip install playwright beautifulsoup4 && playwright install chromium'")
    raise

PROVIDER = {
    "name": "Portal Nacional de Contratações Públicas (PNCP)",
    "group": "Governo/Multilaterais"
}

START_URL = "https://pncp.gov.br/app/editais?q=&pagina=1"
KEYWORDS = ["Edital", "Editais", "Chamada", "Chamamento", "Programa", "Prêmio", "Prémio", "Credenciamento", 
"Sustentabilidade", "Aceleração", "Inovação", "Tecnologia", "Pesquisa", "Desenvolvimento", 
"Água", "Clima", "Floresta", "Banco"]

def fetch(regex, cfg, _debug: bool = False):
    is_debug = _debug or str(cfg.get("PNCP_DEBUG", "0")).lower() in ("1", "true", "yes")
    
    def log(*args):
        if is_debug: print("[PNCP]", *args)

    out = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not is_debug)
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        page = context.new_page()

        try:
            log(f"Acedendo listagem: {START_URL}")
            page.goto(START_URL, wait_until="load", timeout=60000)
            page.wait_for_selector(".br-card", timeout=30000)
            
            # Coleta links de detalhes
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a'))
                    .map(a => a.href)
                    .filter(href => href.includes('/editais/') && !href.includes('pagina='));
            }""")
            
            links = list(set(links))
            log(f"Encontrados {len(links)} editais potenciais.")

            for link in links:
                try:
                    log(f"--- Lendo link: {link} ---")
                    page.goto(link, wait_until="domcontentloaded", timeout=45000)
                    
                    # Espera o carregamento de qualquer elemento de dado
                    page.wait_for_selector(".br-main-content", timeout=20000)
                    time.sleep(2) # Pausa técnica para o JS preencher os campos

                    # EXTRAÇÃO ROBUSTA: Pegamos o HTML renderizado e convertemos em texto limpo
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Remove scripts e estilos para o texto ficar limpo
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Texto limpo com quebras de linha preservadas para as labels
                    clean_text = soup.get_text(separator="\n")
                    
                    # Se em debug, salva o que foi lido para conferência
                    if is_debug:
                        with open("debug_pncp_content.txt", "a", encoding="utf-8") as f:
                            f.write(f"\n\n--- LINK: {link} ---\n{clean_text}")

                    # 1. Filtro de Elegibilidade (Requisito 3)
                    if not any(k.lower() in clean_text.lower() for k in KEYWORDS):
                        log("   [Ignorado] Palavras-chave não encontradas.")
                        continue

                    # 2. Extração de Dados via Regex no Texto Limpo
                    # Procura o valor que vem após a palavra chave e a quebra de linha
                    def find_in_text(label):
                        match = re.search(fr"{label}\n\s*(.+)", clean_text, re.IGNORECASE)
                        return match.group(1).strip() if match else ""

                    objeto = find_in_text("Objeto")
                    orgao = find_in_text("Órgão") or find_in_text("Unidade Compradora") or "PNCP"
                    valor = find_in_text("Valor Estimado") or find_in_text("Valor Total") or "Sob consulta"
                    
                    # 3. Extração de Datas
                    deadline = None
                    # Tenta achar a data final explícita
                    data_match = re.search(r"(Data Final|Vigência Fim)\n\s*(\d{2}/\d{2}/\d{4})", clean_text, re.IGNORECASE)
                    if data_match:
                        deadline = parse_date_any(data_match.group(2))
                    else:
                        # Fallback: Todas as datas do texto, pega a última
                        all_dates = re.findall(r"(\d{2}/\d{2}/\d{4})", clean_text)
                        if all_dates:
                            deadline = parse_date_any(all_dates[-1])

                    out.append({
                        "source": PROVIDER["name"],
                        "title": normalize((objeto or "Edital PNCP")[:180]),
                        "link": link,
                        "deadline": deadline,
                        "agency": orgao,
                        "region": "Brasil",
                        "raw": {"valor": valor}
                    })
                    log(f"   [OK] Elegível e Capturado: {orgao}")

                except Exception as e:
                    log(f"   [Erro] Falha no link: {e}")
                    continue

        except Exception as e:
            log(f"Erro Geral: {e}")
        finally:
            browser.close()

    return out

if __name__ == "__main__":
    print("\n=== TESTE STANDALONE PNCP: EXTRAÇÃO DE TEXTO COMPLETO ===\n")
    if os.path.exists("debug_pncp_content.txt"): os.remove("debug_pncp_content.txt")
    
    resultados = fetch(None, {}, _debug=True)
    
    print(f"\nFinalizado! {len(resultados)} editais capturados.")
    print("Verifique o arquivo 'debug_pncp_content.txt' para ver o texto bruto extraído.")