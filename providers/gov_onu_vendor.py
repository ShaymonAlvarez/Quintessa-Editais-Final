# -*- coding: utf-8 -*-
# providers/gov_onu_vendor.py

# ============================================================
# 1. IMPORTS COM FALLBACK (Para rodar Standalone)
# ============================================================
try:
    # Importação normal quando executado via sistema (backend)
    from .common import normalize, parse_date_any
except ImportError:
    # Fallback para rodar direto do terminal: python providers/gov_onu_vendor.py
    import os, sys
    # Adiciona o diretório pai ao path para encontrar o pacote 'providers'
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, parse_date_any # type: ignore

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ============================================================
# 2. METADADOS DO PROVIDER
# ============================================================
PROVIDER = {
    "name": "ONU Vendor Portal (Brasil)",
    "group": "Governo/Multilaterais"
}

# URL alvo
BASE_URL = "https://vendor.un.org.br"
START_URL = "https://vendor.un.org.br/processes"

# Header padrão para evitar bloqueios simples
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ============================================================
# 3. FUNÇÃO PRINCIPAL (FETCH)
# ============================================================
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta editais do portal Vendor ONU (Brasil).
    
    Args:
        regex: Objeto re.Pattern para filtrar títulos.
        cfg: Dicionário de configuração (pode conter flags de debug).
        _debug: Flag manual para forçar modo verboso (usado no teste standalone).
    """
    
    # Verifica se o debug está ativo via config ou flag manual
    is_debug = _debug or str(cfg.get("ONU_VENDOR_DEBUG", "0")) in ("1", "true", "yes")

    def log(*args):
        if is_debug:
            print("[ONU_VENDOR]", *args)

    log(f"Iniciando coleta em: {START_URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(START_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro ao acessar a página: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen_links = set()

    # Estratégia: Buscar todas as linhas de tabelas (tr)
    rows = soup.find_all("tr")
    
    log(f"Encontradas {len(rows)} linhas na tabela (bruto).")

    for row in rows:
        # Pula cabeçalhos (procura por th ou se não tem td)
        if row.find("th") or not row.find("td"):
            continue
        
        cols = row.find_all("td")
        if not cols:
            continue

        # Tenta achar o link principal dentro da linha
        anchor = row.find("a", href=True)
        if not anchor:
            continue

        link_rel = anchor["href"]
        full_link = urljoin(BASE_URL, link_rel)
        
        # O título geralmente é o texto do link
        raw_title = anchor.get_text(strip=True) or "Edital ONU Vendor"
        title = normalize(raw_title)

        # Filtro de REGEX
        if regex and not regex.search(title):
            log(f"Ignorado pelo regex: {title[:30]}...")
            continue

        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # Tentativa de extrair Data e Valor do texto da linha inteira
        row_text = row.get_text(" | ", strip=True)
        
        # Data: Procura padrões DD/MM/AAAA
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", row_text)
        
        deadline = None
        published = None
        
        if dates:
            # Se tiver mais de uma data, assume: primeira = publicação, última = deadline
            if len(dates) >= 2:
                published = parse_date_any(dates[0])
                deadline = parse_date_any(dates[-1])
            else:
                deadline = parse_date_any(dates[0])

        # Valor: Tenta achar padrão de moeda (R$ ou USD)
        raw_metadata = {"row_text": row_text}
        money_match = re.search(r"(?:R\$|USD)\s?[\d\.,]+", row_text)
        if money_match:
            raw_metadata["price_string"] = money_match.group(0)

        # Monta o objeto final
        item = {
            "source": PROVIDER["name"],
            "title": title,
            "link": full_link,
            "deadline": deadline,
            "published": published,
            "agency": "ONU / Vendor",
            "region": "Brasil",
            "raw": raw_metadata
        }
        
        out.append(item)
        log(f"Capturado: {title[:40]}... | Deadline: {deadline}")

    log(f"Total coletado: {len(out)} itens.")
    return out

# ============================================================
# 4. MODO STANDALONE (TESTE)
# ============================================================
if __name__ == "__main__":
    # Comando para teste: python providers/gov_onu_vendor.py
    import re
    
    print("\n--- RODANDO EM MODO TESTE (STANDALONE) ---\n")
    
    # Regex "pega-tudo" para teste
    dummy_regex = re.compile(r".*", re.I)
    dummy_cfg = {}

    try:
        results = fetch(dummy_regex, dummy_cfg, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        for i, item in enumerate(results):
            print(f"#{i+1} Título: {item['title']}")
            print(f"    Link:   {item['link']}")
            print(f"    Prazo:  {item['deadline']}")
            print(f"    Preço?: {item['raw'].get('price_string', 'N/A')}")
            print("-" * 30)

    except Exception as e:
        print(f"ERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()