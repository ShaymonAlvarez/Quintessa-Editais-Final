try:
    from .common import normalize, parse_date_any
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, parse_date_any  # type: ignore

import requests
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

PROVIDER = {
    "name": "FAPESP Chamadas",
    "group": "América Latina / Brasil"
}

URL_HINT = "https://fapesp.br/chamadas/"

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS_REGEX = re.compile(
    r"(Edital|Editais|Chamada|Chamamento|Programa|Pr[êe]mio|Credenciamento)",
    re.I
)

# Regex Específicos para encontrar datas no texto da FAPESP
FAPESP_DATE_PATTERNS = [
    re.compile(r"data-limite\s+(?:para|de)\s+(?:submissão|envio|recebimento).*?(\d{1,2}º?[\/\s]+de\s+[A-Za-zç]+\s*(?:de\s+\d{4})?)", re.I),
    re.compile(r"recebimento\s+de\s+propostas\s+até\s+(\d{1,2}º?[\/\s]+de\s+[A-Za-zç]+\s*(?:de\s+\d{4})?)", re.I),
    re.compile(r"prazo\s+para\s+(?:submissão|envio).*?(\d{1,2}º?[\/\s]+de\s+[A-Za-zç]+\s*(?:de\s+\d{4})?)", re.I),
    re.compile(r"encerramento:?\s*(\d{1,2}º?[\/\s]+de\s+[A-Za-zç]+\s*(?:de\s+\d{4})?)", re.I),
]
def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return s

def _absolutize(href: Optional[str], base: str) -> Optional[str]:
    if not href: return None
    h = href.strip()
    if not h or h.startswith("#") or h.lower().startswith("javascript:"): return None
    if urlparse(h).scheme in ("http", "https"): return h
    return urljoin(base, h)

def _clean_date_str(date_str: str) -> str:
    """Trata '1º' para '1' e remove sujeiras para o dateparser entender."""
    ds = date_str.lower().replace("º", "").replace("1o ", "1 ").strip()
    # Se não tiver ano, tenta inferir (opcional, mas o dateparser geralmente assume ano atual)
    return ds

def _scrape_fapesp_deadline(session: requests.Session, url: str) -> Optional[str]:
    """
    Entra na página do edital e busca a data usando padrões específicos da FAPESP.
    """
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200: return None
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        
        # Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
        main_text = soup.get_text(" ", strip=True)
        
        # 1. Tenta Regex Específico FAPESP
        for pat in FAPESP_DATE_PATTERNS:
            match = pat.search(main_text)
            if match:
                raw_date = match.group(1) # Ex: "1º de julho" ou "30 de abril de 2025"
                clean_date = _clean_date_str(raw_date)
                dt = parse_date_any(clean_date)
                if dt:
                    return dt.isoformat()

        # 2. Se falhar, tenta procurar tabelas comuns
        # Muitas vezes a FAPESP põe uma tabela com "Data Limite" na primeira coluna        
    except Exception:
        pass
    return None

def fetch(regex: re.Pattern, cfg: Dict[str, Any], _debug: bool = False) -> List[Dict[str, Any]]:
    debug = _debug or str(cfg.get("FAPESP_DEBUG", "0")).lower() in ("1", "true")
    def log(*args):
        if debug: print("[FAPESP]", *args)

    session = _make_session()
    base_url = "https://fapesp.br/chamadas/"
    
    log(f"Acessando: {base_url}")
    try:
        resp = session.get(base_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log(f"Erro no request principal: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    # Tenta focar na área de conteúdo
    content_area = soup.find("div", {"id": "content"}) or soup.find("main") or soup.body
    
    items = []
    seen_links = set()

    if not content_area:
        return []
    for a in content_area.find_all("a", href=True):
        raw_title = normalize(a.get_text())
        link = _absolutize(a["href"], base_url)

        if not link or not raw_title: continue
        if link in seen_links: continue
        
        # Filtros iniciais
        if not KEYWORDS_REGEX.search(raw_title): continue
        if regex and not regex.search(raw_title):
            log(f"Ignorado por regex usuario: {raw_title}")
            continue

        seen_links.add(link)

        # AGORA: Entra na página para buscar a deadline com precisão
        deadline_iso = _scrape_fapesp_deadline(session, link)
        
        log(f"Item: {raw_title} | Deadline: {deadline_iso}")

        items.append({
            "source": PROVIDER["name"],
            "title": raw_title,
            "link": link,
            "deadline": deadline_iso, # ISO format string ou None
            "published": None,
            "agency": "FAPESP",
            "region": "Brasil",
            "raw": {}
        })

    return items

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    print("=== TESTE FAPESP (Busca profunda de Deadline) ===")
    res = fetch(re.compile(".*"), {}, _debug=True)
    print(f"\nEncontrados: {len(res)}")
    for i in res:
        if i["deadline"]:
            print(f"[DATA OK] {i['deadline']} - {i['title']}")
        else:
            print(f"[SEM DATA] {i['title']}")