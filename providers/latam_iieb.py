try:
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page, parse_date_any # type: ignore

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PROVIDER = {
    "name": "IIEB Notícias/Editais",
    "group": "América Latina / Brasil"
}

BASE_URL = "https://iieb.org.br/noticias/"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_REGEX = re.compile(
    r"(Edital|Editais|Chamada|Chamamento|Programa|Pr[eé]mio|Credenciamento)",
    re.IGNORECASE
)

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
DENY_LIST = {
    "programas",
    "edital"
}

# + cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta editais do site do IIEB.
    
    Args:
        regex: Objeto re.Pattern para filtrar títulos (filtro do usuário).
        cfg: Configurações globais.
        _debug: Flag para verbosidade (usada no teste standalone).
    """

    is_debug = _debug or str(cfg.get("IIEB_DEBUG", "0")).lower() in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[IIEB]", *args)

    log(f"Iniciando coleta em: {BASE_URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(BASE_URL, timeout=60)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro crítico ao acessar a página: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen_links = set()
    
    anchors = soup.find_all("a", href=True)
    log(f"Total de links encontrados na página: {len(anchors)}")

    for anchor in anchors:
        link_rel = anchor["href"]
        full_link = urljoin(BASE_URL, link_rel)
        
        # Limpeza do título: pega texto do link ou title attribute
        raw_title = anchor.get_text(" ", strip=True) or anchor.get("title", "")
        title = normalize(raw_title)

        # 1. Filtro Básico: Título muito curto ou vazio
        if len(title) < 5:
            continue

        # 2. Filtro de Bloqueio (Institucional/Menu)
        # Remove APENAS "programas" e "edital" se for o título exato
        if title.lower() in DENY_LIST:
            # log(f"Ignorado por ser menu/institucional: {title}")
            continue

        # 3. Filtro de Palavras-Chave Obrigatórias (Edital, Chamada, etc.)
        if not KEYWORDS_REGEX.search(title):
            # Se não tem as palavras-chave, ignoramos (para não pegar notícias gerais)
            continue

        # 4. Filtro de Regex do Usuário (Configurado no Painel)
        if regex and not regex.search(title):
            log(f"Ignorado pelo regex do usuário: {title[:30]}...")
            continue

        # 5. De duplicação
        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # 6. Extração de Detalhes (Tentativa)
        # Tenta achar Data (Deadline) e Valor (Preço)
        
        # Deadline: Usa a função helper que entra na página e procura datas
        deadline = None
        try:
            deadline = scrape_deadline_from_page(full_link)
        except Exception as e:
            log(f"Erro ao extrair data de {full_link}: {e}")

        # Valor: Tenta achar padrão de moeda (R$) no título (básico)
        raw_metadata = {}
        money_match = re.search(r"(?:R\$|BRL)\s?[\d\.,]+", title)
        if money_match:
            raw_metadata["price_string"] = money_match.group(0)

        # Monta o objeto final
        item = {
            "source": PROVIDER["name"],
            "title": title[:180], # Limita tamanho do título
            "link": full_link,
            "deadline": deadline,
            "published": None, # Site de notícias geralmente mistura data de postagem, difícil extrair padrão único sem entrar na página
            "agency": "IIEB",
            "region": "Brasil",
            "raw": raw_metadata
        }
        
        out.append(item)
        log(f"Capturado: {title[:50]}... | Deadline: {deadline}")

    log(f"Coleta finalizada. Total de itens: {len(out)}")
    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    # Comando para rodar: python providers/latam_iieb.py
    import re
    import json
    
    print("\nRODANDO EM MODO TESTE (STANDALONE)\n")
    
    dummy_regex = re.compile(r".*", re.I)
    dummy_cfg = {"IIEB_DEBUG": "1"} # Força debug

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        for i, item in enumerate(results):
            print(f"#{i+1}")
            print(f"  Título:   {item['title']}")
            print(f"  Link:     {item['link']}")
            print(f"  Deadline: {item['deadline']}")
            print(f"  Infos:    {item['raw']}")
            print("-" * 30)

    except Exception as e:
        print(f"\nERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()