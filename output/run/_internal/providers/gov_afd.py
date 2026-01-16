# -*- coding: utf-8 -*-
# providers/gov_afd.py

import re
import time
from urllib.parse import urljoin

try:
    from .common import normalize, parse_date_any, scrape_deadline_from_page
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from providers.common import normalize, parse_date_any, scrape_deadline_from_page
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def parse_date_any(x): return x
        def scrape_deadline_from_page(x): return None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO CRÍTICO: Playwright não instalado. Instale com 'pip install playwright'.")
    raise

PROVIDER = {
    "name": "AFD (Agence Française de Développement)",
    "group": "Governo/Multilaterais"
}

START_URL = "https://www.afd.fr/en/calls-for-projects/list"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_FILTER = [
    "Edital", "Chamada", "Programa", "Prêmio", "Credenciamento", "Call for projects", "Call for expressions of interest", 
    "Call for proposals", "Program", "Award", "Prize", "Grant", "Fund", "Tender", "Water", "Sustainability",
    "Climate", "Environment", "Development", "Social", "Entrepreneurship", "Impact", "Technology", "Development Bank",
]
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta chamadas de projetos do site da AFD.
    Aceita cookies automaticamente e extrai metadados.
    """
    is_debug = _debug or str(cfg.get("AFD_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[AFD]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    out = []
    seen = set()

    with sync_playwright() as p:
        # headless=False se estiver debugando para ver o navegador abrindo
        browser = p.chromium.launch(
            headless=not is_debug, 
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Contexto com User-Agent real para evitar bloqueios
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            # 1. ACESSAR PÁGINA
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
            # A AFD usa "tarteaucitron" ou banners genéricos. Tenta clicar em "Aceitar".
            log("Verificando banner de cookies...")
            try:
                # Tenta seletores comuns de "Accept All" ou "Agree"
                cookie_btn = page.locator("button:has-text('Accept all'), button:has-text('Tout accepter'), #tarteaucitronPersonalize2").first
                if cookie_btn.is_visible():
                    cookie_btn.click()
                    log("Cookies aceitos com sucesso.")
                    time.sleep(2) # Espera banner sumir
            except Exception as e:
                log(f"Nenhum banner de cookie bloqueante detectado ou erro: {e}")

            # 3. CARREGAMENTO DA LISTA
            log("Aguardando carregamento da lista...")
            try:
                # Espera pelos cartões de projeto (.card ou .views-row)
                page.wait_for_selector(".view-content, article, .card", timeout=15000)
            except:
                log("Timeout aguardando seletor específico. Tentando extrair do DOM atual...")

            # Scroll para garantir renderização (lazy loading)
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

            # 4. EXTRAÇÃO (Via JavaScript no Browser)
            # Coleta dados brutos diretamente do DOM para robustez
            raw_items = page.evaluate(r"""() => {
                const results = [];
                // Seleciona cards de artigos/projetos
                const cards = Array.from(document.querySelectorAll('article, .views-row, .card'));
                
                cards.forEach(card => {
                    // Tenta encontrar o título (geralmente h2, h3 ou links dentro do card)
                    const titleEl = card.querySelector('h2, h3, h4, .card-title a, h2 a');
                    
                    // Se não achou título, ignora
                    if (!titleEl) return;

                    const title = titleEl.innerText.trim();
                    let href = titleEl.getAttribute('href');
                    
                    // Se o link não estiver no título, procura no card inteiro
                    if (!href) {
                        const linkEl = card.querySelector('a');
                        if (linkEl) href = linkEl.getAttribute('href');
                    }

                    // Tenta extrair data ou status (texto solto no card)
                    const textContent = card.innerText;
                    
                    results.push({
                        title: title,
                        href: href,
                        full_text: textContent
                    });
                });
                return results;
            }""")

            log(f"Itens brutos encontrados: {len(raw_items)}")

            # 5. PROCESSAMENTO E FILTRAGEM (Python)
            for item in raw_items:
                title = normalize(item['title'])
                href = item['href']
                full_text = item['full_text']

                if not title or len(title) < 5:
                    continue

                # Normaliza URL (absoluta)
                if href:
                    full_link = urljoin(START_URL, href)
                else:
                    full_link = START_URL

                # FILTRO DE PALAVRAS-CHAVE 
                # Verifica se o título contém algum dos termos exigidos (PT ou EN)
                has_keyword = any(k.lower() in title.lower() for k in KEYWORDS_FILTER)
                
                if not has_keyword:
                    # Se falhar no keyword, verifica se passa no Regex do Usuário (se houver)
                    # Caso contrário, descarta.
                    if not (regex and regex.search(title)):
                        # log(f"Ignorado (sem palavra-chave): {title}")
                        continue

                # FILTRO DE DUPLICATAS
                if full_link in seen:
                    continue
                seen.add(full_link)

                # EXTRAÇÃO DE DATA E PREÇO
                deadline = None
                
                # Procura padrões de data no texto do card (ex: "Deadline: 15/05/2025" ou "Closing date: ...")
                # Regex para datas comuns (DD/MM/YYYY ou YYYY-MM-DD)
                date_match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", full_text)
                if date_match:
                    deadline = parse_date_any(date_match.group(1))
                
                # Se não achou no card, usa scraper profundo (visita a página)
                if not deadline:
                    # log(f"Data não encontrada no card, visitando: {title[:20]}...")
                    deadline = scrape_deadline_from_page(full_link)

                # Tentativa de extrair valor (EUR/€)
                raw_data = {}
                price_match = re.search(r"(€|EUR)\s?([\d,.]+(?:M|k)?)", full_text, re.IGNORECASE)
                if price_match:
                    raw_data["estimated_value"] = price_match.group(0)

                # Monta objeto final
                out.append({
                    "source": PROVIDER["name"],
                    "title": title[:180],
                    "link": full_link,
                    "deadline": deadline,
                    "published": None, # Sites da AFD variam muito onde mostram a publicação
                    "agency": "AFD",
                    "region": "Global/França",
                    "raw": raw_data
                })

                log(f"✅ Capturado: {title[:50]}... | Dead: {deadline}")

        except Exception as e:
            log(f"Erro durante a navegação: {e}")
        finally:
            browser.close()

    log(f"Total coletado: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    # Para rodar este teste: python providers/gov_afd.py
    # Isso simula a execução isolada com a flag de teste.
    
    print("\n--- TESTE STANDALONE: AFD CALLS ---\n")
    
    # Regex "pega-tudo" para validar se a captura básica funciona
    dummy_regex = re.compile(r".*", re.IGNORECASE)
    
    # Configuração dummy com debug ativado
    cfg_teste = {"AFD_DEBUG": "1"}

    try:
        # Chama a função principal com a flag de debug ligada
        resultados = fetch(dummy_regex, cfg_teste, _debug=True)
        
        print("\n" + "="*50)
        print(f"RELATÓRIO DE TESTE: {len(resultados)} itens encontrados")
        print("="*50)
        
        if resultados:
            for i, item in enumerate(resultados[:5]): # Mostra os 5 primeiros
                print(f"#{i+1}")
                print(f"Título:   {item['title']}")
                print(f"Link:     {item['link']}")
                print(f"Deadline: {item['deadline']}")
                print(f"Infos:    {item['raw']}")
                print("-" * 30)
        else:
            print("Nenhum item encontrado. Verifique se o site mudou o layout ou se os termos de busca estão corretos.")

    except Exception as e:
        print(f"ERRO FATAL NO TESTE: {e}")