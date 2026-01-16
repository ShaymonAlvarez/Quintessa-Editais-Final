import time
import re
from urllib.parse import urljoin
from datetime import datetime, timedelta

try:
    from .common import normalize, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from providers.common import normalize, parse_date_any
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def parse_date_any(x): 
            if not x: return None
            # Tenta formatos básicos PT-BR
            match = re.search(r"(\d{2})/(\d{2})/(\d{4})", x)
            if match: return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
            return x

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright não instalado.")
    raise
PROVIDER = {
    "name": "Reparação Bacia Rio Doce",
    "group": "América Latina / Brasil"
}

START_URL = "https://www.reparacaobaciariodoce.com/editais/"

KEYWORDS_PERMITIDAS = [
    "edital", "editais", "chamada", "chamadas", "chamamento", 
    "programa", "prémio", "prêmio", "credenciamento", "aceleração"
]

MIN_DAYS_TO_EXPIRE = 7 

def extrair_data_contextual(texto):
    """
    Busca datas próximas a palavras de encerramento.
    """
    if not texto: return None
    texto_lower = texto.lower()
    
    regex_data = r"(\d{2}[/.-]\d{2}[/.-]\d{2,4}|\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4})"
    gatilhos = ["inscriç", "prazo", "até", "limite", "encerramento", "recebimento", "final", "vigência"]
    
    matches = list(re.finditer(regex_data, texto_lower))
    
    for match in matches:
        data_str = match.group(0)
        start, end = match.span()
        clip_start = max(0, start - 100)
        clip_end = min(len(texto_lower), end + 100)
        contexto = texto_lower[clip_start:clip_end]
        
        # Se tiver palavra chave perto, é a data alvo
        if any(g in contexto for g in gatilhos):
            return parse_date_any(data_str)
            
    return None

def validar_regra_7_dias(data_iso):
    """
    Retorna True se a data for válida (futuro >= hoje + 7 dias).
    Retorna False se for passado ou prazo muito curto.
    Se data_iso for None, retornamos True (benefício da dúvida para revisão manual),
    OU False se preferir ser restritivo. Aqui seremos restritivos conforme pedido.
    """
    if not data_iso:
        return False, "Data não encontrada (Restritivo)"
    
    try:
        # data_iso vem como YYYY-MM-DD
        dt_alvo = datetime.strptime(data_iso, "%Y-%m-%d")
        dt_hoje = datetime.now()
        
        dt_alvo = dt_alvo.replace(hour=23, minute=59, second=59)
        dt_hoje = dt_hoje.replace(hour=0, minute=0, second=0)
        
        dias_restantes = (dt_alvo - dt_hoje).days
        
        if dias_restantes < 0:
            return False, f"Vencido há {abs(dias_restantes)} dias"
        
        if dias_restantes < MIN_DAYS_TO_EXPIRE:
            return False, f"Prazo curto ({dias_restantes} dias < {MIN_DAYS_TO_EXPIRE} dias)"
            
        return True, f"Vigente ({dias_restantes} dias restantes)"
        
    except ValueError:
        return False, "Formato de data inválido"

def fetch(regex, cfg, _debug: bool = False):
    is_debug = _debug or str(cfg.get("RIODOCE_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug: print("[RIO_DOCE]", *args)

    log(f"Iniciando coleta em: {START_URL}")
    log(f"Regra aplicada: Apenas editais com prazo >= {MIN_DAYS_TO_EXPIRE} dias a partir de hoje.")
    
    out = []
    seen_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        
        try:
            # FASE 1: Coleta dos Links na Home 
            page = context.new_page()
            log("Acessando vitrine...")
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
            try:
                page.locator("button, a").filter(has_text=re.compile(r"Aceitar|Concordo", re.I)).first.click(timeout=2000)
            except: pass

            time.sleep(3)

            # Extração Inicial (JS)
            raw_items = page.evaluate(r'''() => {
                const items = [];
                const anchors = Array.from(document.querySelectorAll('a'));
                anchors.forEach(a => {
                    const href = a.getAttribute('href');
                    if (!href || href.length < 5 || href.startsWith('#')) return;
                    
                    let text = a.innerText.trim();
                    let finalTitle = text;
                    const genericWords = ["clique", "aqui", "baixar", "saiba mais", "ver mais"];
                    
                    if (genericWords.some(w => text.toLowerCase().includes(w)) || text.length < 5) {
                        let parent = a.parentElement;
                        for (let i=0; i<3; i++) {
                            if (!parent) break;
                            const header = parent.querySelector('h1, h2, h3, h4, strong');
                            if (header && header.innerText.trim().length > 5) {
                                finalTitle = header.innerText.trim();
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }
                    items.push({ title: finalTitle, link: href });
                });
                return items;
            }''')

            # Pré-filtragem de Links
            items_to_visit = []
            for item in raw_items:
                title = normalize(item['title'])
                link = urljoin(START_URL, item['link'])
                
                if link in seen_links: continue
                if len(title) < 5: continue
                if not any(k in title.lower() for k in KEYWORDS_PERMITIDAS): continue
                if any(x in link.lower() for x in ['facebook', 'twitter', 'policy']): continue
                if regex and not regex.search(title): continue

                seen_links.add(link)
                items_to_visit.append({"title": title, "link": link})

            log(f"Candidatos iniciais: {len(items_to_visit)}")

            # FASE 2: Deep Scraping p/ validação de Datas 
            for i, item in enumerate(items_to_visit):
                title = item['title']
                link = item['link']
                
                log(f"[{i+1}/{len(items_to_visit)}] Verificando: {title[:30]}...")
                
                try:
                    page.goto(link, timeout=40000, wait_until="domcontentloaded")
                    full_text = normalize(page.locator("body").inner_text())
                    
                    # 1. Busca Deadline
                    deadline = extrair_data_contextual(full_text)
                    
                    # 2. VALIDAÇÃO RIGOROSA (Regra dos 7 dias)
                    aprovado, motivo = validar_regra_7_dias(deadline)
                    
                    if not aprovado:
                        log(f"   -> 🚫 IGNORADO: {motivo} (Data: {deadline})")
                        continue # PULA PARA O PRÓXIMO, NÃO SALVA
                    
                    # Se passou, busca valor e salva
                    valor_estimado = None
                    money_match = re.search(r"(?:R\$|BRL)\s?[\d\.,]+", full_text)
                    if money_match: valor_estimado = money_match.group(0)

                    out.append({
                        "source": PROVIDER["name"],
                        "title": title[:180],
                        "link": link,
                        "deadline": deadline,
                        "published": None,
                        "agency": "Fundação Renova",
                        "region": "Brasil (Rio Doce)",
                        "raw": {
                            "valor_estimado": valor_estimado,
                            "validacao": motivo
                        }
                    })
                    log(f"   -> ✅ APROVADO: {motivo}")

                except Exception as e:
                    log(f"   -> Erro ao ler página: {e}")

        except Exception as e:
            log(f"Erro Geral: {e}")
        finally:
            browser.close()

    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    import re
    print(f"\n--- TESTE: REPARAÇÃO RIO DOCE (FILTRO > {MIN_DAYS_TO_EXPIRE} DIAS) ---\n")
    
    def parse_date_any(x):
        meses = {
            "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04",
            "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
            "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
        }
        try:
            x = x.lower()
            # dd/mm/yyyy
            match_barra = re.search(r"(\d{2})/(\d{2})/(\d{4})", x)
            if match_barra: return f"{match_barra.group(3)}-{match_barra.group(2)}-{match_barra.group(1)}"
            
            # dd de mes de yyyy
            for mes_nome, mes_num in meses.items():
                if mes_nome in x:
                    match_ext = re.search(r"(\d{1,2})\s+de", x)
                    match_ano = re.search(r"20\d{2}", x)
                    if match_ext and match_ano:
                        dia = match_ext.group(1).zfill(2)
                        ano = match_ano.group(0)
                        return f"{ano}-{mes_num}-{dia}"
            return None
        except: return None

    dummy_regex = re.compile(r".*", re.I)
    dummy_cfg = {"RIODOCE_DEBUG": "1"}

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        print("\n" + "="*60)
        print(f"RELATÓRIO: {len(results)} editais VIGENTES encontrados")
        print("="*60)
        
        if len(results) == 0:
            print("Nenhum edital passou no filtro de data (todos vencidos ou prazo curto).")
        
        for item in results:
            print(f"[APROVADO] {item['title']}")
            print(f"Prazo: {item['deadline']}")
            print(f"Status: {item['raw']['validacao']}")
            print("-" * 30)

    except Exception as e:
        print(f"ERRO: {e}")