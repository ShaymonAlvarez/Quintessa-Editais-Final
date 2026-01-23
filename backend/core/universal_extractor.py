# -*- coding: utf-8 -*-
"""
Extrator Universal de Editais usando Perplexity API.

Este módulo permite extrair dados de editais de qualquer URL
usando IA (Perplexity), eliminando a necessidade de criar
scrapers específicos para cada site.

Fluxo:
1. Recebe URL do site + grupo associado + filtros (regex, prazo, valor)
2. Baixa conteúdo da página (HTML/PDF)
3. Envia para Perplexity com prompt específico de extração
4. Parseia resposta estruturada em JSON
5. Retorna lista de editais encontrados

Custo estimado: ~$0.0004 por extração (modelo sonar)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from .config import get_perplexity_api_key
from .errors import push_error
from .sheets import update_link_run_status


# Prompt de sistema otimizado para extração estruturada
SYSTEM_PROMPT = """Você é um especialista em análise de páginas de editais e chamadas públicas.
Sua tarefa é extrair TODOS os editais/chamadas/oportunidades encontrados na página fornecida.

REGRAS IMPORTANTES:
1. Extraia SOMENTE editais/chamadas que estejam ATUALMENTE ativos/abertos
2. Retorne os dados em formato JSON válido
3. Se não encontrar editais, retorne uma lista vazia []
4. Seja preciso nas datas - use formato ISO (YYYY-MM-DD)
5. Links devem ser absolutos (com https://)

FORMATO DE SAÍDA (JSON):
[
  {
    "title": "Título do edital",
    "link": "https://link-direto-para-o-edital",
    "deadline": "2025-12-31",
    "published": "2025-01-01",
    "value": "até R$ 500.000",
    "agency": "Órgão/Fundação responsável",
    "description": "Breve descrição do objetivo (max 200 chars)"
  }
]

Retorne APENAS o JSON, sem explicações adicionais."""


def build_extraction_prompt(
    url: str,
    content_preview: str,
    min_days: int = 0,
    regex_filter: str = "",
    max_value: Optional[float] = None,
) -> str:
    """
    Constrói o prompt de extração com filtros aplicados.
    """
    hoje = datetime.now().strftime("%Y-%m-%d")
    prazo_minimo = (datetime.now() + timedelta(days=min_days)).strftime("%Y-%m-%d")
    
    prompt_parts = [
        f"Analise a página: {url}",
        f"Data de hoje: {hoje}",
        "",
        "CONTEÚDO DA PÁGINA (preview):",
        content_preview[:15000],  # Limita para não estourar tokens
        "",
    ]
    
    # Adiciona filtros
    filtros = []
    if min_days > 0:
        filtros.append(f"- Deadline mínimo: {prazo_minimo} (pelo menos {min_days} dias no futuro)")
    if regex_filter:
        filtros.append(f"- Filtrar por palavras-chave: {regex_filter}")
    if max_value:
        filtros.append(f"- Valor máximo: R$ {max_value:,.2f}")
    
    if filtros:
        prompt_parts.append("FILTROS A APLICAR:")
        prompt_parts.extend(filtros)
        prompt_parts.append("")
    
    prompt_parts.append("Extraia todos os editais encontrados e retorne em formato JSON.")
    
    return "\n".join(prompt_parts)


def fetch_page_content(url: str) -> Tuple[str, Optional[str]]:
    """
    Baixa o conteúdo de uma página para análise.
    
    Retorna: (conteúdo_texto, erro_ou_none)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return "", f"Erro ao baixar página: {e}"
    
    content_type = (resp.headers.get("Content-Type") or "").lower()
    
    # PDF: tenta extrair texto
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        try:
            from io import BytesIO
            from pypdf import PdfReader
            
            reader = PdfReader(BytesIO(resp.content))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return " ".join(parts), None
        except Exception as e:
            return "", f"Erro ao ler PDF: {e}"
    
    # HTML: extrai texto limpo
    raw = resp.text or ""
    if "html" in content_type or "<html" in raw.lower():
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw, "html.parser")
            # Remove scripts e styles
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator=" ", strip=True), None
        except Exception as e:
            return raw, None
    
    return raw, None


def call_perplexity_extraction(
    prompt: str,
    model_id: str = "sonar",
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> Tuple[List[Dict], Optional[str]]:
    """
    Chama a API da Perplexity para extração.
    
    Retorna: (lista_de_editais, erro_ou_none)
    """
    api_key = get_perplexity_api_key()
    if not api_key:
        return [], "API key da Perplexity não configurada"
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    body = {
        "model": model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        if resp.status_code >= 400:
            return [], f"Erro API: {resp.status_code} - {resp.text[:500]}"
        data = resp.json()
    except Exception as e:
        return [], f"Exceção na API: {e}"
    
    # Extrai resposta
    try:
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception:
        content = ""
    
    if not content:
        return [], "Resposta vazia da API"
    
    # Tenta parsear JSON da resposta
    try:
        # Remove possíveis marcadores de código
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        items = json.loads(content)
        if not isinstance(items, list):
            items = [items] if items else []
        return items, None
    except json.JSONDecodeError as e:
        # Tenta extrair JSON de dentro do texto
        match = re.search(r'\[[\s\S]*\]', content)
        if match:
            try:
                items = json.loads(match.group())
                return items, None
            except:
                pass
        return [], f"Erro ao parsear JSON: {e}"


def extract_from_url(
    url: str,
    grupo: str,
    link_uid: str = "",
    min_days: int = 0,
    regex_filter: str = "",
    max_value: Optional[float] = None,
    model_id: str = "sonar",
) -> Dict[str, Any]:
    """
    Função principal: extrai editais de uma URL.
    
    Args:
        url: URL do site a analisar
        grupo: Grupo associado (ex: "Governo/Multilaterais")
        link_uid: UID do link cadastrado (para atualizar status)
        min_days: Prazo mínimo em dias
        regex_filter: Regex/palavras-chave para filtrar
        max_value: Valor máximo em R$
        model_id: Modelo Perplexity a usar (sonar, sonar-pro, etc)
    
    Returns:
        Dict com: items, count, error, url, grupo
    """
    result = {
        "url": url,
        "grupo": grupo,
        "items": [],
        "count": 0,
        "error": None,
        "tokens_used": 0,
    }
    
    # 1. Baixa conteúdo da página
    content, error = fetch_page_content(url)
    if error:
        result["error"] = error
        if link_uid:
            update_link_run_status(link_uid, "erro", 0)
        return result
    
    if not content or len(content) < 100:
        result["error"] = "Conteúdo da página muito curto ou vazio"
        if link_uid:
            update_link_run_status(link_uid, "erro", 0)
        return result
    
    # 2. Constrói prompt com filtros
    prompt = build_extraction_prompt(
        url=url,
        content_preview=content,
        min_days=min_days,
        regex_filter=regex_filter,
        max_value=max_value,
    )
    
    # 3. Chama Perplexity
    items, error = call_perplexity_extraction(
        prompt=prompt,
        model_id=model_id,
    )
    
    if error:
        result["error"] = error
        if link_uid:
            update_link_run_status(link_uid, "erro", 0)
        return result
    
    # 4. Processa itens encontrados
    valid_items = []
    for item in items:
        # Normaliza campos
        normalized = {
            "title": str(item.get("title") or item.get("titulo") or ""),
            "link": str(item.get("link") or item.get("url") or ""),
            "deadline": str(item.get("deadline") or item.get("prazo") or ""),
            "published": str(item.get("published") or item.get("publicado") or ""),
            "value": str(item.get("value") or item.get("valor") or ""),
            "agency": str(item.get("agency") or item.get("orgao") or ""),
            "description": str(item.get("description") or item.get("descricao") or ""),
            "source": url,
            "group": grupo,
        }
        
        if normalized["title"]:  # Só inclui se tiver título
            valid_items.append(normalized)
    
    result["items"] = valid_items
    result["count"] = len(valid_items)
    
    # 5. Atualiza status do link
    if link_uid:
        update_link_run_status(link_uid, "ok", len(valid_items))
    
    return result


def extract_from_links(
    links: List[Dict],
    min_days: int = 0,
    regex_by_group: Dict[str, str] = None,
    max_value: Optional[float] = None,
    model_id: str = "sonar",
    callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Extrai editais de múltiplos links cadastrados.
    
    Args:
        links: Lista de dicts com uid, url, grupo, ativo
        min_days: Prazo mínimo em dias
        regex_by_group: Dict de grupo -> regex
        max_value: Valor máximo
        model_id: Modelo Perplexity
        callback: Função chamada após cada link (para progresso)
    
    Returns:
        Dict com: all_items, stats_by_group, errors
    """
    regex_by_group = regex_by_group or {}
    
    results = {
        "all_items": [],
        "stats_by_group": {},
        "errors": [],
        "processed": 0,
        "total": len(links),
    }
    
    active_links = [l for l in links if l.get("ativo", "true") == "true"]
    results["total"] = len(active_links)
    
    for i, link in enumerate(active_links):
        url = link.get("url", "")
        grupo = link.get("grupo", "")
        uid = link.get("uid", "")
        
        # Pega regex do grupo
        regex_filter = regex_by_group.get(grupo, "")
        
        try:
            extracted = extract_from_url(
                url=url,
                grupo=grupo,
                link_uid=uid,
                min_days=min_days,
                regex_filter=regex_filter,
                max_value=max_value,
                model_id=model_id,
            )
            
            if extracted.get("error"):
                results["errors"].append({
                    "url": url,
                    "grupo": grupo,
                    "error": extracted["error"],
                })
            else:
                results["all_items"].extend(extracted.get("items", []))
                
                # Estatísticas por grupo
                if grupo not in results["stats_by_group"]:
                    results["stats_by_group"][grupo] = {"total": 0, "links": 0}
                results["stats_by_group"][grupo]["total"] += extracted.get("count", 0)
                results["stats_by_group"][grupo]["links"] += 1
            
        except Exception as e:
            push_error("extract_from_links", e)
            results["errors"].append({
                "url": url,
                "grupo": grupo,
                "error": str(e),
            })
        
        results["processed"] = i + 1
        
        # Callback para progresso
        if callback:
            try:
                callback(results["processed"], results["total"], url)
            except:
                pass
    
    return results
