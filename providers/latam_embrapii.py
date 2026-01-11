# -*- coding: utf-8 -*-
# providers/latam_embrapii.py

try:
    from .common import normalize, scrape_deadline_from_page
except ImportError:
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from providers.common import normalize, scrape_deadline_from_page

import requests
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

PROVIDER = {
    "name": "EMBRAPII Chamadas",
    "group": "América Latina / Brasil"
}

START_URL = "https://embrapii.org.br/transparencia/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DENY_LIST = {"home", "contato", "sobre", "trabalhe conosco", "política", "mapa", "blog", "notícias", "imprensa", "facebook", "linkedin", "instagram", "youtube"}
GENERIC_BUTTONS = {"ver documentos", "saiba mais", "acesse aqui", "veja mais", "confira", "clique aqui", "ver edital", "link", "baixe aqui"}

# Função auxiliar para coletar deadline em paralelo
def _enrich_deadline(item):
    try:
        # Tenta pegar o deadline; se falhar, fica None
        item["deadline"] = scrape_deadline_from_page(item["link"])
    except:
        item["deadline"] = None
    return item

def fetch(regex, cfg) -> List[Dict[str, Any]]:
    debug = str(cfg.get("EMBRAPII_DEBUG", "0")).lower() in ("1", "true", "yes")
    
    try:
        r = requests.get(START_URL, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        if debug: print(f"[EMBRAPII] Erro request: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []
    seen = set()

    links = soup.find_all("a", href=True)
    if debug: print(f"[EMBRAPII] Links brutos: {len(links)}")

    # 1ª PASSADA: Identifica os links relevantes (muito rápido, processamento local)
    for a in links:
        href = a["href"].strip()
        raw_text = normalize(a.get_text())
        
        if not href or href.startswith("#") or href.lower().startswith("javascript"):
            continue
        
        full_link = urljoin(START_URL, href)
        title = raw_text
        
        # Recuperação de título
        if raw_text.lower() in GENERIC_BUTTONS or len(raw_text) < 3:
            curr = a
            found_new_title = False
            for _ in range(4):
                if not curr: break
                prev = curr.find_previous(['h3', 'h4', 'h5', 'strong', 'p', 'span'])
                if prev:
                    cand = normalize(prev.get_text())
                    if len(cand) > 5 and cand.lower() not in GENERIC_BUTTONS:
                        title = cand
                        found_new_title = True
                        break
                curr = curr.parent
            
            if not found_new_title:
                if any(x in full_link for x in ("chamada", "edital", "selecao")):
                    title = "Chamada EMBRAPII (Título não detectado)"
                else:
                    continue

        # Filtragem
        title_lower = title.lower()
        if any(ignore in title_lower for ignore in DENY_LIST):
            continue
        
        keywords_edital = ["chamada", "edital", "seleção", "fluxo", "fomento", "parceria", "processo", "resultado", "publica", "pública", "01/"]
        looks_like_edital = any(k in title_lower for k in keywords_edital)
        
        # Injeta palavras-chave para passar no regex do grupo
        text_for_regex = f"{title} {full_link} embrapii inovação tecnologia industrial pesquisa"
        matches_user_regex = regex and regex.search(text_for_regex)
        
        if not looks_like_edital and not matches_user_regex:
            continue

        if full_link in seen: continue
        seen.add(full_link)
        
        # Se já existe título idêntico, pula
        if any(x['title'] == title for x in candidates): continue

        # Adiciona à lista de candidatos SEM data por enquanto
        candidates.append({
            "source": PROVIDER["name"],
            "title": title[:180],
            "link": full_link,
            "deadline": None, # Será preenchido depois
            "published": None,
            "agency": "EMBRAPII",
            "region": "Brasil",
            "raw": {}
        })

    # 2ª PASSADA: Busca as datas em paralelo (ThreadPool)
    # Usa até 10 conexões simultâneas para ser rápido
    out = []
    if candidates:
        if debug: print(f"[EMBRAPII] Buscando deadlines para {len(candidates)} itens...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {executor.submit(_enrich_deadline, item): item for item in candidates}
            for future in as_completed(future_to_item):
                try:
                    res = future.result()
                    out.append(res)
                except Exception as exc:
                    if debug: print(f"[EMBRAPII] Erro ao processar item: {exc}")
                    # Adiciona mesmo sem data em caso de erro
                    item = future_to_item[future]
                    out.append(item)
    
    if debug: print(f"[EMBRAPII] Final: {len(out)} itens coletados.")
    return out

if __name__ == "__main__":
    import json
    import time
    dummy_re = re.compile(r".*", re.I)
    
    start = time.time()
    data = fetch(dummy_re, {"EMBRAPII_DEBUG": "1"})
    end = time.time()
    
    print(f"\nResumo: {len(data)} itens encontrados em {end - start:.2f} segundos.")
    if data:
        print(json.dumps(data[0], indent=2, default=str, ensure_ascii=False))