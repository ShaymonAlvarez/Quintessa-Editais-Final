import re
import time
import traceback
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

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
    print("ERRO: Playwright não instalado. Instale com: pip install playwright")
    raise

PROVIDER = {
    "name": "UNICEF Brasil",
    "group": "Governo/Multilaterais"
}

BASE_URL = "https://www.unicef.org/brazil/oportunidade-para-fornecedores-e-parceiros"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS = [
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento",
    "Contrato", "Licitação", "Proposta", "Procuramento", "Procurement",
    "Request for Proposal", "RFP", "LRP", "Expression of Interest", "EOI",
    "Termo de Referência", "TdR", "Consultoria","Acceleration", "Call for Proposals", "Funding Opportunity", 
    "Request for Proposals", "RFP", "Tender", "Grant", "Water", "Forest", "Climate", "Sustainability"
]

def fetch(regex, cfg):
    """
    Coleta editais do UNICEF Brasil via Playwright.
    Retorna lista de dicionários no formato padrão do sistema.
    """
    print(f"[{PROVIDER['name']}] Iniciando coleta...")
    out = []

    try:
        with sync_playwright() as p:
            # 1. Configuração do Browser (Headless + Bypass)
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()

            # 2. Navegação
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Pequeno scroll para garantir renderização de lazy load
            page.mouse.wheel(0, 1000)
            time.sleep(4)
            
            html_content = page.content()
            browser.close()

            # 3. Parsing
            soup = BeautifulSoup(html_content, "html.parser")
            main_content = soup.find('main') or soup.body
            links = main_content.find_all("a", href=True)
            
            seen_links = set()

            for a in links:
                href = a['href']
                full_link = urljoin(BASE_URL, href)

                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                # Ignora links de navegação global do UNICEF que não sejam BR ou Procurement
                if "unicef.org" in full_link and "brazil" not in full_link and "procurement" not in full_link:
                    continue

                container = a
                block_text = ""

                found_container = False
                for _ in range(4):
                    if container.parent:
                        container = container.parent
                        # Se achou uma div de view-content ou article, é um bom container
                        if container.name in ['article', 'div', 'li']:
                            block_text = normalize(container.get_text(" ", strip=True))
                            # Se o texto for muito curto, continua subindo
                            if len(block_text) > 50:
                                found_container = True
                                break
                
                if not found_container:
                    continue

                # Validação de Keywords no Bloco
                if not any(k.lower() in block_text.lower() for k in KEYWORDS):
                    continue

                # --- FORMATAÇÃO DO TÍTULO ---
                # Prioridade 1: Encontrar um Header (H2, H3, H4) dentro do bloco
                title = ""
                headers = container.find_all(['h3', 'h4', 'h2', 'h5'])
                
                if headers:
                    # Pega o header que tiver alguma keyword, ou o mais longo
                    for h in headers:
                        h_txt = normalize(h.get_text())
                        if any(k.lower() in h_txt.lower() for k in KEYWORDS):
                            title = h_txt
                            break
                    if not title: # Se nenhum header tem keyword, pega o maior
                        title = max([normalize(h.get_text()) for h in headers], key=len)
                
                # Prioridade 2: Se não achou Header, usa o texto do bloco (truncado)
                if not title:
                    # Tenta limpar o texto do link (remove "clique aqui")
                    link_txt = normalize(a.get_text())
                    if len(link_txt) > 15 and "clique" not in link_txt.lower():
                        title = link_txt
                    else:
                        # Pega o início do parágrafo, mas remove datas do começo se houver
                        title = block_text[:150]

                title = normalize(title)

                # Regex do sistema
                if regex and not regex.search(title):
                    continue

                if full_link in seen_links:
                    continue
                seen_links.add(full_link)

                # --- EXTRAÇÃO DE METADADOS ---
                deadline = parse_date_any(block_text)
                
                # Extração de Preço (Raw Data)
                price_info = {}
                money_match = re.search(r'R\$\s?([\d\.,]+)', block_text)
                if money_match:
                    price_info["estimated_value"] = money_match.group(0)

                # --- MONTAGEM FINAL DO OBJETO (SCHEMA VÁLIDO) ---
                item = {
                    "source": PROVIDER["name"],
                    "title": title,          # Título limpo e formatado
                    "link": full_link,       # Link absoluto
                    "deadline": deadline,    # Objeto datetime ou None
                    "published": None,       # UNICEF não padroniza data de publicação na listagem
                    "agency": "UNICEF",
                    "region": "Brasil",
                    "raw": price_info        # Metadados extras
                }
                out.append(item)

    except Exception as e:
        print(f"[{PROVIDER['name']}] Erro: {traceback.format_exc()}")
        return []

    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import json
    # Hack para serializar datetime no print do JSON
    def date_handler(obj):
        return obj.isoformat() if hasattr(obj, 'isoformat') else obj

    print("\n>>> VALIDANDO FORMATAÇÃO: UNICEF BRASIL <<<\n")
    
    items = fetch(None, {})
    
    print(f"Itens encontrados: {len(items)}\n")
    
    if items:
        # Pega o primeiro item para validar o schema visualmente
        print("EXEMPLO DE SAÍDA (JSON):")
        print(json.dumps(items[0], default=date_handler, indent=4, ensure_ascii=False))
        
        print("\nCHECKLIST DE QUALIDADE:")
        print(f"[ ] Título faz sentido? -> {items[0]['title']}")
        print(f"[ ] Link funciona?      -> {items[0]['link']}")
        print(f"[ ] Data é objeto?      -> {type(items[0]['deadline'])} (Esperado: <class 'datetime.datetime'> ou NoneType)")
    else:
        print("Nenhum item para validar.")