# 1. IMPORTS COM FALLBACK (Para rodar Standalone)
# ============================================================
try:
    # Importação normal quando executado via sistema (backend)
    from .common import normalize, scrape_deadline_from_page, parse_date_any
except ImportError:
    # Fallback para rodar direto do terminal
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # Mock simples caso common não seja encontrado no teste isolado
    try:
        from providers.common import normalize, scrape_deadline_from_page, parse_date_any
    except ImportError:
        def normalize(x): return " ".join(x.split()) if x else ""
        def scrape_deadline_from_page(x): return None
        def parse_date_any(x): return None

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ============================================================
# 2. METADADOS DO PROVIDER
# ============================================================
PROVIDER = {
    "name": "Alterna",
    "group": "Corporativo/Aceleradoras"  # Ajuste para o grupo que preferir
}

START_URL = "https://alterna.pro/trabaja-en-alterna/"

# Headers para simular um navegador real e evitar bloqueios simples
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ============================================================
# 3. FUNÇÃO PRINCIPAL (FETCH)
# ============================================================
def fetch(regex, cfg, _debug: bool = False):
    """
    Coleta oportunidades do site Alterna.
    Args:
        regex: Objeto re.Pattern para filtrar títulos.
        cfg: Configuração global (opcional).
        _debug: Flag para imprimir logs no terminal durante testes.
    """
    
    # Verifica debug (seja por argumento ou config)
    is_debug = _debug or str(cfg.get("ALTERNA_DEBUG", "0")).lower() in ("1", "true")

    def log(*args):
        if is_debug:
            print("[ALTERNA]", *args)

    log(f"Iniciando coleta em: {START_URL}")

    try:
        response = requests.get(START_URL, headers=HEADERS, timeout=45)
        response.raise_for_status()
    except Exception as e:
        log(f"Erro ao acessar a página: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    seen_links = set()

    # ESTRATÉGIA DE SELEÇÃO:
    # O site pode mudar, então buscamos todos os links e filtramos
    # aqueles que parecem relevantes ou estão dentro de listas/artigos.
    # Você pode refinar o 'select' abaixo se quiser ser mais específico (ex: soup.select(".job-list a"))
    anchors = soup.find_all("a", href=True)

    log(f"Total de links encontrados (bruto): {len(anchors)}")

    for anchor in anchors:
        href = anchor["href"].strip()
        raw_title = anchor.get_text(" ", strip=True)

        # 1. Limpeza básica
        if not href or not raw_title:
            continue
        
        # Ignora links internos irrelevantes (contato, home, login, etc)
        if any(x in href.lower() for x in ["#", "javascript", "mailto", "facebook", "linkedin"]):
            continue
        
        # 2. Monta link absoluto
        full_link = urljoin(START_URL, href)

        # 3. Filtro de duplicatas
        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # 4. Normaliza título
        title = normalize(raw_title)

        # Filtro de qualidade do título (evita "Click here", "Read more", etc sozinhos)
        if len(title) < 5:
            continue

        # 5. Filtro REGEX (obrigatório para manter coerência com o sistema)
        # Se o usuário configurou uma regex para esse grupo, usamos aqui.
        if regex and not regex.search(title):
            # Opcional: logar o que foi ignorado se estiver em debug
            # log(f"Ignorado pelo regex: {title}")
            continue

        # 6. Extração de Metadados (Data/Preço)
        # Como a lista principal geralmente só tem o título, usamos a função helper
        # scrape_deadline_from_page que visita a página do edital para tentar achar datas.
        # Isso deixa o processo um pouco mais lento, mas muito mais preciso.
        deadline = scrape_deadline_from_page(full_link)
        
        # Tenta achar menção de valor no título (opcional)
        # raw_metadata = {}
        # if "$" in title or "USD" in title: ...

        item = {
            "source": PROVIDER["name"],
            "title": title[:180], # Limite seguro de caracteres
            "link": full_link,
            "deadline": deadline,
            "published": None,    # Difícil extrair sem seletor específico
            "agency": "Alterna",
            "region": "América Latina", # Ou 'Global' dependendo do foco
            "raw": {}
        }

        out.append(item)
        log(f"✅ Capturado: {title[:50]}... | Deadline: {deadline}")

    log(f"Coleta finalizada. Total de itens: {len(out)}")
    return out

# ============================================================
# 4. MODO STANDALONE (TESTE)
# ============================================================
if __name__ == "__main__":
    # Este bloco só roda se você chamar: python providers/corp_alterna.py
    import re
    import json
    
    print("\n--- TESTE STANDALONE: ALTERNA ---\n")
    
    # Regex "pega-tudo" para ver se o scraper está funcionando
    dummy_regex = re.compile(r".*", re.I)
    
    try:
        # Chama a função fetch com _debug=True para ver os prints
        results = fetch(dummy_regex, {}, _debug=True)
        
        print("\n" + "="*60)
        print(f"RESULTADOS ({len(results)} itens):")
        print("="*60)
        
        if not results:
            print("Nenhum item encontrado. Verifique se o site mudou ou se os seletores estão corretos.")
        
        for i, item in enumerate(results):
            print(f"#{i+1}")
            print(f"  Título:   {item['title']}")
            print(f"  Link:     {item['link']}")
            print(f"  Deadline: {item['deadline']}") # Será None se não achar data no texto
            print("-" * 30)

    except Exception as e:
        print(f"ERRO NO TESTE: {e}")