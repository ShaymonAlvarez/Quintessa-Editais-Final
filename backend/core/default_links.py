# -*- coding: utf-8 -*-
"""
Lista de links pré-configurados extraídos dos providers originais.
Estes links serão inseridos automaticamente na aba 'links_cadastrados'.
"""

# Lista de todos os links extraídos dos providers
# Formato: (nome, url, grupo)
LINKS_PROVIDERS = [
    # =================== FUNDAÇÕES E PRÊMIOS ===================
    ("ActionAid", "https://actionaid.org.br/trabalhe-conosco/", "Fundações e Prêmios"),
    ("Fundación Avina", "https://www.avina.net/pt/consultoria/", "Fundações e Prêmios"),
    ("ChildFund Brasil", "https://childfundbrasil.org.br/editais/", "Fundações e Prêmios"),
    ("Freedom Fund", "https://www.freedomfund.org/careers/", "Fundações e Prêmios"),
    ("Rockefeller Foundation", "https://www.rockefellerfoundation.org/rfps/", "Fundações e Prêmios"),
    ("Girl Effect", "https://boards.greenhouse.io/girleffect", "Fundações e Prêmios"),
    ("Ford Foundation", "https://www.fordfoundation.org/work/our-grants/grant-opportunities/", "Fundações e Prêmios"),
    
    # =================== GOVERNO / MULTILATERAIS ===================
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", "Governo/Multilaterais"),
    ("Grants.gov", "https://www.grants.gov/search-results", "Governo/Multilaterais"),
    ("SAM.gov", "https://sam.gov/search/", "Governo/Multilaterais"),
    ("Find a Grant UK", "https://www.find-government-grants.service.gov.uk/grants", "Governo/Multilaterais"),
    ("Green Climate Fund", "https://www.greenclimate.fund/work-with-us/opportunities", "Governo/Multilaterais"),
    ("EIB Procurement", "https://www.eib.org/en/about/procurement/index.htm", "Governo/Multilaterais"),
    ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement", "Governo/Multilaterais"),
    ("ADB Tenders", "https://www.adb.org/projects/tenders", "Governo/Multilaterais"),
    ("IDB Invest", "https://idbinvest.org/en/procurement", "Governo/Multilaterais"),
    ("IDB Procurement", "https://projectprocurement.iadb.org/en", "Governo/Multilaterais"),
    ("IDB Calls for Proposals", "https://www.iadb.org/en/how-we-can-work-together/calls-proposals", "Governo/Multilaterais"),
    ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/", "Governo/Multilaterais"),
    ("UKRI Funding", "https://www.ukri.org/opportunity/", "Governo/Multilaterais"),
    ("Contracts Finder UK", "https://www.contractsfinder.service.gov.uk/", "Governo/Multilaterais"),
    ("UK Dev Funding", "https://www.gov.uk/international-development-funding", "Governo/Multilaterais"),
    ("UNICEF Brasil", "https://www.unicef.org/brazil/oportunidade-para-fornecedores-e-parceiros", "Governo/Multilaterais"),
    ("UNGM Awards", "https://www.ungm.org/Public/ContractAward", "Governo/Multilaterais"),
    ("UNESCO Brasília", "https://roster.brasilia.unesco.org/app/selection-process-list", "Governo/Multilaterais"),
    ("UNDP Procurement", "https://procurement-notices.undp.org/", "Governo/Multilaterais"),
    ("PNCP Editais", "https://pncp.gov.br/app/editais", "Governo/Multilaterais"),
    ("Plan International", "https://plan-international.org/calls-tender/", "Governo/Multilaterais"),
    ("ONU Vendor Brasil", "https://vendor.un.org.br/processes", "Governo/Multilaterais"),
    ("LuxDev Tenders", "https://luxdev.lu/en/tenders/call-tenders", "Governo/Multilaterais"),
    ("DevInfo RFPs", "https://devinfo.in/request-for-proposals/", "Governo/Multilaterais"),
    ("CAF Calls", "https://www.caf.com/en/work-with-us/calls", "Governo/Multilaterais"),
    ("Bond UK Funding", "https://www.bond.org.uk/funding-opportunities/", "Governo/Multilaterais"),
    ("AFD Calls", "https://www.afd.fr/en/calls-for-projects/list", "Governo/Multilaterais"),
    ("OGP Opportunities", "https://www.opengovpartnership.org/opportunities/", "Governo/Multilaterais"),
    
    # =================== AMÉRICA LATINA / BRASIL ===================
    ("FINEP Chamadas", "https://www.finep.gov.br/chamadas-publicas/chamadaspublicas?situacao=aberta", "América Latina / Brasil"),
    ("FAPESP Chamadas", "https://fapesp.br/chamadas/", "América Latina / Brasil"),
    ("BNDES Chamadas", "https://www.bndes.gov.br/wps/portal/site/home/mercado-de-capitais/fundos-de-investimentos/chamadas-publicas-para-selecao-de-fundos", "América Latina / Brasil"),
    ("FUNBIO Chamadas", "https://preprod-chamadas.funbio.org.br/", "América Latina / Brasil"),
    ("Fundo Vale", "https://www.fundovale.org/", "América Latina / Brasil"),
    ("Fundo Socioambiental CAIXA", "https://www.caixa.gov.br/sustentabilidade/fundo-socioambiental-caixa/chamadas-abertas/Paginas/default.aspx", "América Latina / Brasil"),
    ("EMBRAPII", "https://embrapii.org.br/transparencia/#chamadas", "América Latina / Brasil"),
    ("BNB Convênios", "https://www.bnb.gov.br/conveniosweb/Convenente.ProgramaConvenio.Lista.aspx", "América Latina / Brasil"),
    ("Prosas Editais", "https://prosas.com.br/editais", "América Latina / Brasil"),
    ("IIEB Notícias", "https://iieb.org.br/noticias/", "América Latina / Brasil"),
    ("Reparação Rio Doce", "https://www.reparacaobaciariodoce.com/editais/", "América Latina / Brasil"),
    ("Alterna Careers", "https://carreras.alterna.pro/jobs/Careers", "América Latina / Brasil"),
]


def get_all_provider_links():
    """Retorna lista de dicts com todos os links dos providers."""
    return [
        {"nome": nome, "url": url, "grupo": grupo}
        for nome, url, grupo in LINKS_PROVIDERS
    ]


def get_links_by_group(grupo: str):
    """Retorna links filtrados por grupo."""
    return [
        {"nome": nome, "url": url, "grupo": g}
        for nome, url, g in LINKS_PROVIDERS
        if g == grupo
    ]
