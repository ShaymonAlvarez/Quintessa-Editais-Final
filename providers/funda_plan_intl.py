import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup, Tag
import dateparser

try:
    from .common import normalize
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from providers.common import normalize

PROVIDER = {
    "group": "Fundações e Prêmios",
    "name": "Plan International"
}

# Palavras-chave obrigatórias para funcionamento do código
SECTION_HEADERS = [
    "Concurso", "Concursos", "Tender", "Tenders","Pesquisa", "Research", "Chamadas", "Calls", "Mentorship", "Mentoria", 
    "Open Calls", "Requests for proposal", "Current opportunities"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def extract_date_from_line(text: str) -> Optional[object]:
    """
    Remove ruído e tenta extrair data de uma linha de texto.
    """
    # Pesquisa de data, ex: 15 Jan 2024, January 15 2024, 15/01/2024
    patterns = [
        r'\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}',
        r'\d{2}/\d{2}/\d{4}',
        r'\d{4}-\d{2}-\d{2}'
    ]
    
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            date_str = match.group(0)
            return dateparser.parse(date_str, settings={'DATE_ORDER': 'DMY', 'STRICT_PARSING': False})
    return None

def fetch(regex: str = "", cfg: dict = None) -> List[dict]:
    url = "https://plan-international.org/calls-tender/"
    import requests
    
    items = []

    try:
        logging.info(f"Acessando {url} para varredura de seções de texto...")
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. Encontrar os títulos de seção (H2, H3, H4, H5, Strong)
        # Onde o texto contenha "Tender", "Concurso", etc.
        candidates = soup.find_all(['h2', 'h3', 'h4', 'h5', 'strong'])
        
        target_sections = []
        for tag in candidates:
            txt = normalize(tag.get_text(" ", strip=True))
            # Verifica se é um cabeçalho alvo (ex: "Open Tenders")
            if any(h.lower() in txt.lower() for h in SECTION_HEADERS):
                target_sections.append(tag)
        
        if not target_sections:
            logging.warning("Nenhum cabeçalho de 'Concursos/Tenders' encontrado. O site pode ter mudado o layout.")

        # 2. Para cada seção encontrada, pegar os irmãos seguintes (Next Siblings)
        for section in target_sections:
            logging.info(f"Lendo itens abaixo de: {section.get_text()}")
            
            # Itera pelos elementos irmãos até encontrar outro cabeçalho
            for sibling in section.next_siblings:
                if not isinstance(sibling, Tag):
                    continue
                
                # Se encontrar outro cabeçalho grande, paramos (fim da seção)
                if sibling.name in ['h1', 'h2', 'h3']: 
                    break
                
                # Processa Listas (ul/ol) ou Parágrafos (p) ou Divs de texto
                elements_to_check = []
                if sibling.name in ['ul', 'ol']:
                    elements_to_check = sibling.find_all('li')
                elif sibling.name in ['p', 'div']:
                    elements_to_check = [sibling]
                
                for el in elements_to_check:
                    text_content = normalize(el.get_text(" ", strip=True))
                    
                    # Ignora linhas vazias ou muito curtas
                    if len(text_content) < 10:
                        continue
                    
                    # Procura link dentro desse elemento
                    a_tag = el.find('a', href=True)
                    link = ""
                    if a_tag:
                        link = a_tag['href']
                        if link.startswith("/"):
                            link = "https://plan-international.org" + link
                    
                    # Se não tem link, mas o texto parece um edital, pode ser um aviso
                    # Mas geralmente queremos itens com link/download
                    if not link:
                        continue

                    # Extrai data do texto completo da linha (ex: "Consultancy for X - Deadline 12 Jan 2024")
                    dt_obj = extract_date_from_line(text_content)
                    
                    # Título: removemos a data do texto para ficar limpo, ou usamos o texto todo
                    title = text_content
                    # Opcional: Limpar prefixos comuns como "Download", "Link"
                    title = re.sub(r'^(Download|Link|Click here)[:\s-]*', '', title, flags=re.IGNORECASE)

                    items.append({
                        "source": PROVIDER["name"],
                        "title": title[:200], # Limita tamanho do título
                        "link": link,
                        "deadline": dt_obj.date() if dt_obj else None,
                    })

    except Exception as e:
        logging.error(f"Erro no provider Plan Intl: {e}")
        return []

    # Remove duplicatas exatas de Link
    unique_items = []
    seen = set()
    for i in items:
        if i["link"] not in seen:
            seen.add(i["link"])
            unique_items.append(i)

    return unique_items

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    print(">>> TESTE PLAN INT'L: VARREDURA DE SEÇÃO DE TEXTO <<<")
    print("-" * 60)
    
    results = fetch()
    
    print("-" * 60)
    print(f"Total encontrado: {len(results)}")
    
    for item in results:
        d = item['deadline'] if item['deadline'] else "[SEM DATA]"
        print(f"DATA: {d}")
        print(f"Titulo: {item['title']}")
        print(f"Link:   {item['link']}")
        print("." * 40)