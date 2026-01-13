import requests
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Tenta importar do common as ferramentas de data e texto.
# Se der erro (modo standalone), cria mocks.
try:
    from .common import normalize, find_deadline_in_text
except ImportError:
    def normalize(x): return (x or "").strip()
    def find_deadline_in_text(x): return None

PROVIDER = {
    "name": "EMBRAPII Transparência",
    "group": "América Latina / Brasil"
}

BASE_URL = "https://embrapii.org.br/transparencia/#chamadas"

KEYWORDS = [
    "Edital", "Editais", "Chamada", "Chamamento", 
    "Programa", "Prémio", "Prêmio", "Credenciamento","Acceleration", 
    "Call for Proposals", "Funding Opportunity", "Request for Proposals", "RFP", 
    "Tender", "Grant", "Water", "Água", "Forest", "Floresta", "Banco", "Climate", "Clima", 
    "Sustainability", "Sustentabilidade",
]

def fetch_inner_deadline(session, url):
    """
    Entra no link do edital e tenta descobrir a data de limite/submissão
    no corpo do texto HTML da página interna.
    """
    try:
        # Reutiliza a sessão para manter cookies/headers
        r = session.get(url, timeout=20)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Pega todo o texto da página interna limpo
        text_content = normalize(soup.get_text(" ", strip=True))
        
        # Usa a função do common.py que já tem regex poderosa para datas (deadline, closing, etc)
        dt = find_deadline_in_text(text_content)
        return dt
    except Exception as e:
        logging.warning(f"Erro ao ler página interna {url}: {e}")
        return None

def fetch(regex, cfg):
    # 1. Configuração da Sessão (Cookies e Headers persistentes)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    })

    try:
        response = session.get(BASE_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Erro ao acessar lista EMBRAPII: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen_links = set()

    anchors = soup.find_all("a", href=True)

    for a in anchors:
        raw_title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        title = normalize(raw_title)
        link = urljoin(BASE_URL, href)

        if not title or not link:
            continue

        # Filtro de Palavras-chave
        if not any(k.lower() in title.lower() for k in KEYWORDS):
            continue

        # Filtro de Regex (Config do Usuário)
        if not regex.search(f"{title} {link}"):
            continue

        if link in seen_links:
            continue
        seen_links.add(link)

        deadline = fetch_inner_deadline(session, link)
        
        # Se não achou data na página interna, tenta ver se estava no título do link da home (fallback)
        if not deadline:
            deadline = find_deadline_in_text(title)

        # Captura valor (R$) do título, se houver
        raw_extra = {}
        price_match = re.search(r"(R\$\s?[\d\.,]+)", title)
        if price_match:
            raw_extra["valor_estimado"] = price_match.group(1)

        items.append({
            "source": PROVIDER["name"],
            "title": title,
            "link": link,
            "deadline": deadline,      # Data extraída de DENTRO da página
            "published": None,
            "agency": "EMBRAPII",
            "region": "Brasil",
            "raw": raw_extra
        })

    return items

# MODO DE TESTE (STANDALONE)
if __name__ == "__main__":
    # Mock necessário para o teste funcionar sem o sistema completo
    # Copiamos uma lógica simplificada do common.py para o teste local funcionar
    import dateparser
    DATE_PAT = re.compile(
        r"(?:deadline|closing|closes|close\s*date|prazo|encerramento|fecha(?:mento)?|fecha\s*em|inscriç(?:ões|ão)\s+até|data\s+limite)"
        r"[^0-9]{0,20}"
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        re.I
    )
    def simple_find_date(text):
        if not text: return None
        # Tenta achar padrão explícito "Prazo: 10/10/2024"
        m = DATE_PAT.search(text)
        if m:
            return dateparser.parse(m.group(1), settings={'DATE_ORDER': 'DMY'})
        # Se não, procura qualquer data solta (arriscado, mas útil pra teste)
        return None

    # Sobrescrevemos o find_deadline_in_text apenas para este teste local
    # No sistema real, ele usará a versão robusta do common.py
    find_deadline_in_text = simple_find_date 

    print(f"--- Iniciando Teste Deep Scraping: {PROVIDER['name']} ---")
    print("Aguarde... acessando cada link individualmente...")

    class MockRegex:
        def search(self, s): return True

    try:
        # Executa
        resultados = fetch(MockRegex(), {})
        
        print(f"\nConcluído! Encontrados {len(resultados)} itens.\n")
        
        for i, item in enumerate(resultados):
            d = item.get('deadline')
            d_str = d.strftime("%d/%m/%Y") if d else "Não encontrada"
            print(f"[{i+1}] {item['title']}")
            print(f"    Link: {item['link']}")
            print(f"    DEADLINE DETECTADO: {d_str}")
            print("-" * 50)
            
    except Exception as e:
        print(f"\nERRO: {e}")