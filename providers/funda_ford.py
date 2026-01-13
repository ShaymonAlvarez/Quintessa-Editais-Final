import requests
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

try:
    from . import common
except ImportError:
    import common

PROVIDER = {
    "name": "Ford Foundation",
    "group": "Governo/Multilaterais",
    "url": "https://www.fordfoundation.org/work/our-grants/grant-opportunities/"
}

# Cabeçalhos para simular um navegador real e evitar bloqueios de bot/cookies
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
    "Referer": "https://www.google.com/"
}

# Palavras-chave obrigatórias para funcionamento do código
KEYWORDS = [
    'EDITAL', 'EDITAIS', 'CHAMADA', 'CHAMAMENTO', 
    'PROGRAMA', 'PRÉMIO', 'CREDENCIAMENTO','FELLOWSHIP','REQUEST', 'GRANT']

def fetch(regex=None, cfg=None, _debug: bool = False):
    """
    Função principal chamada pelo orquestrador.
    Retorna uma lista de dicionários com os editais encontrados.
    """
    url = PROVIDER["url"]
    results = []
    seen_links = set()

    if _debug:
        print(f"--- [Ford Foundation] Acessando: {url} ---")

    try:
        # 1. Requisição com tratamento de sessão e cookies automáticos
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            if _debug: print(f"Erro ao acessar página: Status {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # 2. Encontrar links de oportunidades
        # A estratégia aqui é pegar todos os links da área de conteúdo principal
        # Evitar menus de navegação
        main_content = soup.find('main') or soup.find('body')
        links = main_content.find_all('a', href=True)

        for link_tag in links:
            href = link_tag['href']
            title = common.normalize(link_tag.get_text())

            # Limpeza e validação básica do link
            full_url = urljoin(url, href)
            
            # Remove duplicatas e links vazios
            if not title or len(title) < 5 or full_url in seen_links:
                continue
            
            # Remove links internos irrelevantes (contato, home, login etc.)
            if any(x in full_url.lower() for x in ['/contact', '/login', 'javascript:', 'mailto:']):
                continue

            # 3. Filtragem por Palavras-chave
            title_upper = title.upper()
            
            # Verifica se contém alguma das palavras chaves permitidas
            # Nota: O site é em inglês, então termos em PT podem ser raros.
            has_keyword = any(k in title_upper for k in KEYWORDS)
            
            if not has_keyword:
                continue

            seen_links.add(full_url)
            
            if _debug:
                print(f" -> Encontrado candidato: {title}")

            # 4. Extração de Detalhes (Data e Valor)
            # Acessamos a página interna do edital para tentar achar datas e valores
            deadline = None
            amount_info = "Não identificado"
            
            try:
                # Usa a função do common para achar data no HTML da página de destino
                deadline = common.scrape_deadline_from_page(full_url)
                
                # Tenta achar menção a dinheiro no título (ex: $50,000)
                # (Para scraping profundo de valor, seria necessário analisar o texto da pág interna)
                if '$' in title or 'USD' in title:
                    amount_info = "Verificar no título"
                    
            except Exception as e:
                if _debug: print(f"    Erro ao ler detalhes de {full_url}: {e}")

            # Formata a saída
            item = {
                "title": title,
                "link": full_url,
                "source": PROVIDER["name"],
                "deadline": deadline.strftime("%Y-%m-%d") if deadline else None,
                "value_obs": amount_info
            }
            results.append(item)

    except Exception as e:
        logging.error(f"Erro no provider Ford Foundation: {e}")
        if _debug: print(f"Erro crítico: {e}")

    return results

# MODO STANDALONE (TESTE DE RODAGEM)
if __name__ == "__main__":
    print("\n>>> INICIANDO TESTE DO PROVIDER FORD FOUNDATION <<<\n")
    
    # Roda a função com debug ativado
    itens = fetch(_debug=True)

    print("\n" + "="*60)
    print(f"RESUMO: {len(itens)} OPORTUNIDADES ENCONTRADAS")
    print("="*60 + "\n")

    if not itens:
        print("AVISO: Nenhum item encontrado com as palavras-chave em PORTUGUÊS.")
        print("O site da Ford Foundation é em inglês. Considere adicionar termos")
        print("como 'GRANT', 'FELLOWSHIP', 'PROPOSAL' na lista 'KEYWORDS' do código.")
    
    for i, item in enumerate(itens, 1):
        print(f"{i}. Título: {item['title']}")
        print(f"   Link:   {item['link']}")
        print(f"   Data:   {item['deadline'] or 'Não detectada'}")
        print(f"   Valor:  {item.get('value_obs', '')}")
        print("-" * 60)