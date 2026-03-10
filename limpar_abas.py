# -*- coding: utf-8 -*-
"""
Script: deleta aba 'sources' (legado) e adiciona titulo explicativo nas abas restantes.
"""

import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from backend.core.sheets import get_gspread_client, open_sheet


def limpar_abas():
    print("Conectando ao Google Sheets...")
    try:
        sh, *_ = open_sheet()
    except Exception as e:
        print("ERRO ao abrir planilha: %s" % e)
        return

    # 1. Deletar aba 'sources' se existir
    try:
        ws_sources = sh.worksheet("sources")
        sh.del_worksheet(ws_sources)
        print("Aba 'sources' deletada (era legado, nao usada mais).")
    except Exception:
        print("Aba 'sources' nao encontrada (ja foi removida ou nao existia).")

    # 2. Renomear abas com nomes mais claros e adicionar titulo na linha 1
    #    Para 'config', 'items' e 'logs', vamos adicionar uma nota na celula A1
    #    que explique o proposito da aba.

    # --- ABA CONFIG ---
    try:
        ws_cfg = sh.worksheet("config")
        # Nao mexemos no header (key | value), mas adicionamos uma nota
        ws_cfg.update_note("A1", "SISTEMA: Configuracoes internas da automacao (prazo minimo, cotacao, etc). NAO EDITAR.")
        print("Nota adicionada na aba 'config'.")
    except Exception as e:
        print("Nao foi possivel adicionar nota em 'config': %s" % e)

    # --- ABA ITEMS ---
    try:
        ws_items = sh.worksheet("items")
        ws_items.update_note("A1", "SISTEMA: Editais extraidos automaticamente pela IA. Os dados sao preenchidos pela automacao.")
        print("Nota adicionada na aba 'items'.")
    except Exception as e:
        print("Nao foi possivel adicionar nota em 'items': %s" % e)

    # --- ABA LOGS ---
    try:
        ws_log = sh.worksheet("logs")
        ws_log.update_note("A1", "SISTEMA: Registro de execucoes e erros. Usado para debug. NAO EDITAR.")
        print("Nota adicionada na aba 'logs'.")
    except Exception as e:
        print("Nao foi possivel adicionar nota em 'logs': %s" % e)

    # --- ABA PERPLEXITY ---
    try:
        ws_pplx = sh.worksheet("perplexity")
        ws_pplx.update_note("A1", "SISTEMA: Historico de consultas a IA e custos. NAO EDITAR.")
        print("Nota adicionada na aba 'perplexity'.")
    except Exception as e:
        print("Nao foi possivel adicionar nota em 'perplexity': %s" % e)

    # --- ABA INCLUIR AQUI ---
    try:
        ws_links = sh.worksheet("INCLUIR AQUI")
        ws_links.update_note("A1", "Coluna A: Nome da empresa/instituicao. Coluna B: Link do site de editais.")
        print("Nota adicionada na aba 'INCLUIR AQUI'.")
    except Exception as e:
        print("Nao foi possivel adicionar nota em 'INCLUIR AQUI': %s" % e)

    print("\nConcluido! Abas finais da planilha:")
    for ws in sh.worksheets():
        print("   - %s" % ws.title)


if __name__ == "__main__":
    limpar_abas()
