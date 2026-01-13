import sys
import os
import re

if __name__ == "__main__":
    # Adiciona o diretório pai ao path para encontrar o módulo 'common'
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from providers.common import list_links, scrape_deadline_from_page, normalize
    except ImportError:
        # Fallback caso a estrutura de pastas esteja diferente
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from common import list_links, scrape_deadline_from_page, normalize
else:
    # Importação normal quando executado pelo sistema principal (loader)
    from .common import list_links, scrape_deadline_from_page, normalize

PROVIDER = {
    "name": "Open Gov Partnership (Challenge)",
    "group": "Governo/Multilaterais"
}

# Palavras-chave obrigatórias para funcionamento do código
REQUIRED_KEYWORDS = [
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento", "Open", "Call", "Award", "Challenge", "Co-creation", "Implement", "Improve", "Submission"
]

def fetch(regex, cfg):
    """
    Coleta links da página de Challenge Submissions da OGP.
    Aplica filtro de regex (do usuário) E filtro de palavras-chave (hardcoded).
    """
    url = "https://www.opengovpartnership.org/challenge-submissions/"
    
    # 1. Coleta todos os links da página (list_links já usa User-Agent no common.py)
    # O seletor "a" pega todos os links. Se precisar ser mais específico, pode-se ajustar.
    pairs = list_links(url, "a")
    
    out = []
    
    for title, href in pairs:
        # Normaliza o título para comparação
        title_norm = normalize(title)
        
        # Ignora links vazios ou curtos demais
        if len(title_norm) < 5:
            continue

        # 2. Verifica se o título passa no Regex do sistema (configuração do usuário)
        if not regex.search(title_norm):
            continue

        # 3. Verifica se contém alguma das palavras-chave obrigatórias
        # Verifica ignorando case (upper/lower)
        has_keyword = any(k.lower() in title_norm.lower() for k in REQUIRED_KEYWORDS)
        
        if has_keyword:
            # Tenta buscar a data de deadline na página de detalhe
            # Nota: OGP muitas vezes não tem "preço" explícito em challenges de política,
            # então 'raw' fica vazio ou com dados parciais se encontrarmos.
            deadline = scrape_deadline_from_page(href)
            
            out.append({
                "source": PROVIDER["name"],
                "title": title_norm[:180], # Corta títulos muito longos
                "link": href,
                "deadline": deadline,
                "published": None, # OGP nem sempre mostra data de publicação na listagem
                "agency": "OGP",
                "region": "Global", # OGP é global
                "raw": {} # Campo para dados extras (preço não é comum neste tipo de edital)
            })

    return out

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    print(f"--- Iniciando Teste Standalone: {PROVIDER['name']} ---")
    print("Verificando importações... OK")
    
    test_regex = re.compile(r".*", re.IGNORECASE)
    
    print("Coletando dados... (isso pode demorar alguns segundos para ler os detalhes)")
    try:
        results = fetch(test_regex, {})
        
        print(f"\nSucesso! Encontrados {len(results)} itens compatíveis.")
        print("-" * 60)
        
        if not results:
            print("AVISO: Nenhum item retornou. Verifique se a página contém as palavras-chave ('Edital', 'Chamada', etc).")
            print("Como o site da OGP é majoritariamente em Inglês/Espanhol, talvez seja necessário")
            print("adicionar termos como 'Call', 'Award', 'Challenge' na lista REQUIRED_KEYWORDS.")
        
        for item in results:
            print(f"Título:   {item['title']}")
            print(f"Link:     {item['link']}")
            print(f"Deadline: {item['deadline']}")
            print("-" * 20)
            
    except Exception as e:
        print(f"\nERRO durante a execução: {e}")
        import traceback
        traceback.print_exc()