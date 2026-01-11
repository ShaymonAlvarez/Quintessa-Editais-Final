# providers/gov_unicef_br.py

# ============================================================
# IMPORTS (com fallback para rodar como script direto/standalone)
# ============================================================
try:
    # Importação normal quando executado pelo sistema
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    # Fallback para execução direta (debug/teste)
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # Mock simples se parse_date_any não estiver disponível no contexto standalone
    try:
        from providers.common import normalize, scrape_deadline_from_page, parse_date_any
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return x

import requests
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# ============================================================
# CONFIGURAÇÃO DO PROVIDER
# ============================================================
PROVIDER = {
    "name": "UNICEF Brasil - Oportunidades",
    "group": "Governo/Multilaterais"
}

URL_ALVO = "https://www.unicef.org/brazil/oportunidade-para-fornecedores-e-parceiros"

# Regex Específico para o padrão do UNICEF Brasil
RE_CONVITE = re.compile(r"(?:Convite|Edital|Ref)[:\.]?\s*([A-Z0-9\-]+)", re.IGNORECASE)
RE_FINALIDADE = re.compile(r"Finalidade[:\.]?\s*(.+?)(?=\.?\s*Data|$)", re.IGNORECASE)

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================
def fetch(regex, cfg, _debug: bool = False) -> List[Dict[str, Any]]:
    """
    Coleta editais da página do UNICEF Brasil.
    Roda standalone com flag _debug=True para testes.
    """
    
    def log(*args):
        if _debug:
            print("[UNICEF_BR]", *args)

    out = []
    seen_links = set()

    # --- HEADERS REFORÇADOS (Anti-Bloqueio 403) ---
    # Inclui Client Hints (Sec-Ch-Ua) para simular Chrome moderno no Windows
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",  # Simula vinda do Google
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"'
    }

    log(f"Iniciando sessão em: {URL_ALVO}")
    
    session = requests.Session()
    
    try:
        resp = session.get(URL_ALVO, headers=headers, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log(f"ERRO FATAL ao acessar URL: {e}")
        # Se ainda der erro, imprime os headers de resposta para debug
        if hasattr(e, 'response') and e.response is not None:
            log(f"Status Code: {e.response.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # UNICEF costuma colocar cada edital em um parágrafo (<p>) ou item de lista (<li>)
    blocks = soup.find_all(['p', 'li', 'div'])
    
    log(f"Analisando {len(blocks)} blocos de conteúdo...")

    for block in blocks:
        text = block.get_text(" ", strip=True)
        
        # Filtro primário: deve ter palavras-chave de edital
        if not any(k in text for k in ("Convite", "LRPS", "LITB", "RFP", "Finalidade", "Edital")):
            continue

        # Busca link dentro do bloco
        anchor = block.find('a', href=True)
        if not anchor:
            continue
            
        href = anchor['href'].strip()
        if not href.startswith("http"):
            href = requests.compat.urljoin(URL_ALVO, href)

        if href in seen_links:
            continue

        # --- Extração de Título ---
        m_convite = RE_CONVITE.search(text)
        m_finalidade = RE_FINALIDADE.search(text)
        
        parts = []
        if m_convite:
            parts.append(m_convite.group(1))
        if m_finalidade:
            desc = m_finalidade.group(1).split("Data final")[0].strip()
            parts.append(desc)
        
        if parts:
            title = " - ".join(parts)
        else:
            title = normalize(text)
            if len(title) > 200: title = title[:197] + "..."

        # --- Filtro Regex do Usuário ---
        if regex and not regex.search(title):
            log(f"Ignorado por regex: {title[:40]}...")
            continue

        # --- Extração de Data (Deadline) ---
        deadline = None
        m_data = re.search(r"(\d{1,2})\s+de\s+([a-zA-ZçÇ]+)\s+de\s+(\d{4})", text, re.IGNORECASE)
        if m_data:
            date_str = f"{m_data.group(1)} {m_data.group(2)} {m_data.group(3)}"
            try:
                deadline = parse_date_any(date_str)
            except:
                pass
        
        if not deadline:
             deadline = scrape_deadline_from_page(href)

        seen_links.add(href)
        
        out.append({
            "source": PROVIDER["name"],
            "title": normalize(title),
            "link": href,
            "deadline": deadline,
            "published": None,
            "agency": "UNICEF",
            "region": "Brasil",
            "raw": {"full_text": text[:300]}
        })
        
        log(f"CAPTURA OK: {title[:50]}... | Data: {deadline}")

    return out

# ============================================================
# MODO STANDALONE (Teste Local)
# ============================================================
if __name__ == "__main__":
    print("\n>>> RODANDO TESTE STANDALONE: UNICEF BRASIL <<<\n")
    rgx_test = re.compile(r".*")
    
    try:
        items = fetch(rgx_test, {}, _debug=True)
        print(f"\nTotal de itens encontrados: {len(items)}")
        
        if items:
            print("\n--- Exemplo do Item 1 ---")
            for k, v in items[0].items():
                print(f"{k.ljust(10)}: {v}")
        else:
            print("Nenhum item encontrado (mas sem erro 403, acesso OK).")
            
    except Exception as e:
        print(f"\nERRO NO TESTE: {e}")