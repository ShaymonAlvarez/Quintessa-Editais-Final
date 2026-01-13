# 1. IMPORTS COM FALLBACK (Para rodar Standalone e Integrado)
# ============================================================
try:
    # Importação normal quando executado via sistema (backend)
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    # Fallback para rodar direto do terminal (Standalone)
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    
    try:
        from providers.common import normalize, scrape_deadline_from_page, parse_date_any
    except ImportError:
        # Mocks simples caso o common.py não seja encontrado
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return None

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

# ============================================================
# 2. CONFIGURAÇÕES E METADADOS
# ============================================================
PROVIDER = {
    "name": "ActionAid",
    "group": "Fundações e Prêmios"
}

START_URL = "https://actionaid.org.br/trabalhe-conosco/"

# Palavras-chave obrigatórias (Case Insensitive)
KEYWORDS_FILTER = [
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento"
]

# Headers para simular navegador real e evitar bloqueios (Error 403)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://google.com"
}

# ============================================================
# 3. FUNÇÃO PRINCIPAL (FETCH)
# ============================================================
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta oportunidades do site ActionAid com filtro rigoroso.
    """
    is_debug = _debug or str(cfg.get("ACTIONAID_DEBUG", "0")).lower() in ("1", "true")

    def log(*args):
        if is_debug:
            print("[ACTIONAID]", *args)

    log(f"Iniciando coleta em: {START_URL}")

    # Sessão para manter cookies se houver redirecionamentos
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Timeout um pouco maior para garantir carregamento
        response = session.get(START_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro crítico ao acessar página: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen_links = set()

    # Procura todos os links.
    # Nota: Sites Wordpress/Institucionais geralmente colocam os links de vagas dentro de <article> ou listas <li>
    # Vamos pegar todos os 'a' e filtrar, é mais robusto contra mudanças de layout HTML.
    anchors = soup.find_all("a", href=True)
    
    log(f"Total de links brutos encontrados: {len(anchors)}")

    for anchor in anchors:
        raw_title = anchor.get_text(" ", strip=True)
        href = anchor["href"].strip()

        # 1. Limpeza básica
        if not href or len(raw_title) < 5:
            continue

        # Ignora links de navegação comuns
        if any(x in href.lower() for x in ["/contato", "/doacao", "login", "wp-admin", "facebook", "twitter"]):
            continue

        # 2. Normalização do Título
        title = normalize(raw_title)

        # 3. FILTRO RIGOROSO DE PALAVRAS-CHAVE (Solicitado no passo 3)
        # Verifica se alguma das palavras permitidas está no título
        has_keyword = any(k.lower() in title.lower() for k in KEYWORDS_FILTER)
        
        if not has_keyword:
            # log(f"Ignorado (sem palavra-chave): {title}") # Descomente para debugar
            continue

        # 4. Link Absoluto
        full_link = urljoin(START_URL, href)

        # 5. Deduplicação
        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # 6. Filtro Regex do Sistema (Backend)
        if regex and not regex.search(title):
            continue

        # 7. Extração de Detalhes (Data e Metadados)
        # O script common.py vai visitar o link para tentar achar datas no texto da vaga
        log(f"Analisando detalhes de: {title}...")
        deadline = scrape_deadline_from_page(full_link)
        
        item = {
            "source": PROVIDER["name"],
            "title": title,
            "link": full_link,
            "deadline": deadline,
            "published": None, 
            "agency": "ActionAid Brasil",
            "region": "Brasil",
            "raw": {}
        }
        
        out.append(item)
        log(f"✅ Capturado: {title} | Deadline: {deadline}")

    log(f"Coleta finalizada. Total de editais válidos: {len(out)}")
    return out

# ============================================================
# 4. MODO STANDALONE (TESTE)
# ============================================================
if __name__ == "__main__":
    # Para rodar: python providers/funda_actionaid.py
    import re
    
    print("\n--- TESTE STANDALONE: ACTIONAID ---\n")
    
    # Regex permissiva para teste
    dummy_regex = re.compile(r".*", re.I)
    
    try:
        results = fetch(dummy_regex, {}, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        if not results:
            print("Nenhum edital encontrado com as palavras-chave especificadas.")
            print(f"Palavras buscadas: {KEYWORDS_FILTER}")
        
        for i, item in enumerate(results):
            print(f"#{i+1}")
            print(f"  Título:   {item['title']}")
            print(f"  Link:     {item['link']}")
            print(f"  Deadline: {item['deadline']}")
            print("-" * 30)

    except Exception as e:
        print(f"ERRO: {e}")