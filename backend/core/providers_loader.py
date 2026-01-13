"""
Carregamento dinâmico de providers (providers.*).
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import pathlib
from functools import lru_cache  # IMPORTAÇÃO NECESSÁRIA PARA CORRIGIR O ERRO
from typing import List

from .errors import push_error

@lru_cache(maxsize=1)
def discover_providers():
    """
    Vasculha o pacote 'providers' e retorna uma lista de módulos válidos.
    """
    mods: List[object] = []
    try:
        import providers
    except ImportError as e:
        push_error("discover_providers import providers", e)
        return []

    seen = set()
    # Percorre subpacotes
    for finder, name, ispkg in pkgutil.walk_packages(
        providers.__path__, providers.__name__ + "."
    ):
        if ispkg: continue
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, "PROVIDER") and callable(getattr(mod, "fetch", None)):
                mods.append(mod)
                seen.add(name)
        except Exception as e:
            push_error(f"Import provider {name}", e)

    # Ordena por grupo / nome
    mods.sort(key=lambda x: (x.PROVIDER.get("group", ""), x.PROVIDER.get("name", "")))
    return mods

def load_providers():
    return discover_providers()

@lru_cache(maxsize=1)
def get_available_groups() -> list[str]:
    """
    Retorna estritamente as categorias oficiais permitidas.
    Filtra qualquer grupo vindo de providers que não esteja nesta lista.
    """
    # 1. Definição ÚNICA das categorias permitidas [SOLICITAÇÃO DO USUÁRIO]
    OFFICIAL_GROUPS = [
        "América Latina/Brasil",
        "Corporativo/Aceleradoras",
        "Governo/Multilaterais",
        "Fundações e Prêmios"
    ]
    
    validated_groups = set()

    try:
        mods = load_providers() 
        for m in mods:
            # Pega o grupo e limpa espaços
            raw_group = getattr(m, "PROVIDER", {}).get("group", "").strip()
            if not raw_group:
                continue
            
            # Normaliza: remove espaços em volta da barra (ex: "Brasil / Latam" -> "Brasil/Latam")
            norm_group = raw_group.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
            
            # SÓ adiciona se for exatamente um dos 4 oficiais
            if norm_group in OFFICIAL_GROUPS:
                validated_groups.add(norm_group)
                
    except Exception as e:
        push_error("get_available_groups_critical", e)
    
    # Se a lista validada estiver vazia (devido a erros), retorna a oficial por segurança
    if not validated_groups:
        return sorted(OFFICIAL_GROUPS, key=lambda s: s.lower())
        
    return sorted(list(validated_groups), key=lambda s: s.lower())

def reload_provider_modules() -> None:
    try:
        import providers
        for mname, mobj in list(sys.modules.items()):
            if mname.startswith("providers.") and mobj:
                try:
                    importlib.reload(mobj)
                except Exception:
                    pass
        discover_providers.cache_clear()
        get_available_groups.cache_clear()
    except Exception as e:
        push_error("reload_providers_modules", e)