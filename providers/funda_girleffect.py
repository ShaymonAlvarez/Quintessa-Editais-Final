# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
import os
from bs4 import BeautifulSoup

# --- 1. CONFIGURAÇÃO DE IMPORTAÇÃO ROBUSTA ---
try:
    from .common import normalize, try_fetch, scrape_deadline_from_page
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.append(parent_dir)
    try:
        from providers.common import normalize, try_fetch, scrape_deadline_from_page
    except ImportError:
        print("ERRO: Não foi possível importar 'common.py'.")
        sys.exit(1)

# --- 2. CONFIGURAÇÃO DO PROVIDER ---
PROVIDER = {
    "name": "Girl Effect",
    "group": "Fundações e Prêmios"
}

URL_BASE = "https://boards.greenhouse.io/girleffect"

# ADICIONEI TERMOS EM INGLÊS BASEADO NO SEU PRINT
KEYWORDS = [
    # Português (Padrão)
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento",
    # Inglês (Necessário para este site)
    "Request for Proposal", "RFP", 
    "Terms of Reference", "ToR", 
    "Consultancy", "Consultant",
    "Expression of Interest"
]

def check_keywords(text: str) -> bool:
    """Verifica se alguma das palavras-chave está presente no texto."""
    text_lower = text.lower()
    for k in KEYWORDS:
        if k.lower() in text_lower:
            return True
    return False

def fetch(regex, cfg):
    """
    Função principal. Retorna lista de editais.
    """
    is_debug = __name__ == "__main__"

    if is_debug:
        print(f"--- Iniciando Coleta: {PROVIDER['name']} ---")
        print(f"URL: {URL_BASE}")

    html = try_fetch(URL_BASE)
    if not html:
        if is_debug: print("ERRO: Conteúdo HTML vazio.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    out = []

    # Busca links na estrutura do Greenhouse
    links_found = soup.select("div.opening a")
    if not links_found:
        main_content = soup.find(id="main") or soup.find(id="content") or soup.body
        links_found = main_content.find_all("a") if main_content else []

    unique_links = set()

    for a in links_found:
        raw_title = normalize(a.get_text())
        href = a.get("href", "")

        if not raw_title or not href or href.startswith("#") or "javascript" in href:
            continue
        
        if href.startswith("/"):
            href = "https://boards.greenhouse.io" + href
        
        if href in unique_links:
            continue
        unique_links.add(href)

        # 1. FILTRAGEM
        passed_filter = check_keywords(raw_title)

        if is_debug:
            if passed_filter:
                print(f"[APROVADO] {raw_title}")
            else:
                # Opcional: comentar esta linha se quiser limpar o log
                print(f"[IGNORADO] {raw_title}")

        if not passed_filter:
            continue

        # 2. DETALHES
        try:
            deadline = scrape_deadline_from_page(href)
        except Exception:
            deadline = None

        out.append({
            "source": PROVIDER["name"],
            "title": raw_title[:180],
            "link": href,
            "deadline": deadline,
            "published": None,
            "agency": "Girl Effect",
            "region": "Global",
            "raw": {}
        })

    return out

# --- 3. EXECUÇÃO DE TESTE ---
if __name__ == "__main__":
    res = fetch(None, None)
    print("\n" + "="*40)
    print(f"ITENS CAPTURADOS: {len(res)}")
    print("="*40)
    for i in res:
        print(f"Título: {i['title']}")
        print(f"Link:   {i['link']}")
        print("-" * 20)