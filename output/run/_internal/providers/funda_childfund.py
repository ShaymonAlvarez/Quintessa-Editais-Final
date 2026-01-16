import re
import time
from urllib.parse import urljoin
try:
    from .common import normalize, scrape_deadline_from_page
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright não instalado. Rode 'pip install playwright' e 'playwright install chromium'")
    raise

PROVIDER = {
    "name": "ChildFund Brasil",
    "group": "Fundações e Prêmios"
}

START_URL = "https://childfundbrasil.org.br/editais/"

def fetch(regex, cfg, _debug: bool = False):
    is_debug = _debug or str(cfg.get("CHILDFUND_DEBUG", "0")).lower() in ("1", "true")
    
    def log(*args):
        if is_debug: print("[CHILDFUND]", *args)

    out = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            log(f"Acessando: {START_URL}")
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
            log("Verificando banner de cookies...")
            try:
                # Procura botões com texto comum de aceite
                cookie_btn = page.locator("a, button").filter(has_text=re.compile(r"Aceitar|Concordo|Entendi", re.I)).first
                if cookie_btn.is_visible():
                    cookie_btn.click(timeout=3000)
                    log("Cookies aceitos.")
                    time.sleep(1) # Espera o banner sumir
            except:
                log("Nenhum banner de cookie impeditivo encontrado ou erro ao clicar.")

            # LOCALIZAR ÁREA DE CONTEÚDO
            try:
                page.wait_for_selector("main a, div.elementor-widget-container a", timeout=10000)
            except:
                log("Timeout aguardando seletores específicos. Tentando ler a página assim mesmo.")

            raw_items = page.evaluate(r'''() => {
                const items = [];
                const anchors = Array.from(document.querySelectorAll('a'));
                
                anchors.forEach(a => {
                    // FILTRO 1: Ignora se estiver no Header ou Footer ou Nav
                    if (a.closest('header') || a.closest('footer') || a.closest('nav')) return;

                    const href = a.getAttribute('href');
                    if (!href || href.startsWith('#') || href.startsWith('javascript')) return;

                    const text = a.innerText.trim();
                    const titleAttr = a.getAttribute('title') || "";
                    
                    let finalTitle = text || titleAttr;

                    // Se o link for um botão genérico "Baixar" ou "Inscreva-se", pega o título do elemento pai (H2, H3, etc)
                    const genericWords = ["baixar", "clique", "aqui", "inscreva", "acessar", "download", "leia mais"];
                    const isGeneric = genericWords.some(w => finalTitle.toLowerCase().includes(w));
                    
                    if (isGeneric || finalTitle.length < 3) {
                        let sibling = a.parentElement;
                        let foundHeader = null;
                        
                        for (let i = 0; i < 3; i++) {
                            if (!sibling) break;
                            const header = sibling.querySelector('h1, h2, h3, h4, h5, strong');
                            if (header && header.innerText.trim().length > 5) {
                                foundHeader = header.innerText.trim();
                                break;
                            }
                            if (sibling.previousElementSibling) {
                                const prevHeader = sibling.previousElementSibling.querySelector('h1, h2, h3, h4, h5') || 
                                                   (sibling.previousElementSibling.tagName.match(/^H\d$/) ? sibling.previousElementSibling : null);
                                if (prevHeader) {
                                    foundHeader = prevHeader.innerText.trim();
                                    break;
                                }
                            }
                            sibling = sibling.parentElement;
                        }
                        if (foundHeader) finalTitle = foundHeader;
                    }

                    if (href.toLowerCase().endsWith('.pdf') && finalTitle.length < 5) {
                        const parts = href.split('/');
                        finalTitle = parts[parts.length - 1];
                    }

                    items.push({
                        title: finalTitle,
                        link: href
                    });
                });
                return items;
            }''')

            log(f"Links extraídos da área principal: {len(raw_items)}")

            keywords_permitidas = ["edital", "seleção", "termo", "referência", "chamada", "tdr", "consultoria", "parceria", "organização", 
            "aceleração", "inovação", "clima", "sustentabilidade", "desenvolvimento", "social", "empreendedorismo", "impacto", "tecnologia",
            "banco de fomento",
            ]
            
            keywords_proibidas = [
                "missão", "visão", "governança", "certificações", "facebook", "instagram", "youtube", "linkedin", 
                "doação", "histórias", "conteúdos", "política", "privacidade", "confidencialidade", "termos de uso"
            ]

            for item in raw_items:
                title = normalize(item['title'])
                link = urljoin(START_URL, item['link'])
                
                if len(title) < 4: continue

                t_lower = title.lower()
                l_lower = link.lower()

                # Filtro Negativo (Remove lixo restante)
                if any(bad in t_lower for bad in keywords_proibidas):
                    continue
                if any(bad in l_lower for bad in keywords_proibidas):
                    continue

                # Filtro Positivo (Garante que é edital)
                is_edital = False
                if any(good in t_lower for good in keywords_permitidas):
                    is_edital = True
                elif ".pdf" in l_lower and any(good in l_lower for good in keywords_permitidas):
                    is_edital = True
                
                if regex and regex.search(title):
                    is_edital = True

                if not is_edital:
                    continue

                if link in seen: continue
                seen.add(link)

                dl = scrape_deadline_from_page(link)

                out.append({
                    "source": PROVIDER["name"],
                    "title": title[:180],
                    "link": link,
                    "deadline": dl,
                    "published": None,
                    "agency": "ChildFund",
                    "region": "Brasil",
                    "raw": {}
                })
                log(f"✅ Item validado: {title}")

        except Exception as e:
            log(f"Erro Playwright: {e}")
        finally:
            browser.close()

    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    dummy_re = re.compile(r".*", re.I)
    
    print("\n>>> TESTE CHILDFUND (PLAYWRIGHT - FINAL) <<<\n")
    try:
        res = fetch(dummy_re, {"CHILDFUND_DEBUG": "1"}, _debug=True)
        print("-" * 50)
        print(f"Total encontrado: {len(res)}")
        for r in res:
            print(f"Título: {r['title']}")
            print(f"Link:   {r['link']}")
            print(f"Data:   {r['deadline']}")
            print("---")
    except Exception as err:
        print(f"Erro fatal: {err}")