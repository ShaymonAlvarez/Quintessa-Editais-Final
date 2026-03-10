# -*- coding: utf-8 -*-
"""
Script de migracao: renomeia aba para 'INCLUIR AQUI' e oculta colunas do sistema.

Resultado: colaborador ve apenas Nome (A) + URL (B).

Como rodar:
    python reorganizar_planilha.py
"""

import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from backend.core.sheets import get_gspread_client, open_sheet

NOVO_NOME = "INCLUIR AQUI"
NOVA_ORDEM = ["nome", "url", "grupo", "uid", "ativo", "created_at", "last_run", "last_status", "last_items"]


def reorganizar():
    print("Conectando ao Google Sheets...")
    try:
        sh, *_ = open_sheet()
    except Exception as e:
        print("ERRO ao abrir planilha: %s" % e)
        return

    # Encontra a aba (nome antigo ou novo)
    ws = None
    for name in [NOVO_NOME, "links_cadastrados"]:
        try:
            ws = sh.worksheet(name)
            print("Aba encontrada: '%s'" % name)
            break
        except Exception:
            continue

    if not ws:
        print("ERRO: Aba nao encontrada.")
        return

    # 1. Renomeia a aba
    if ws.title != NOVO_NOME:
        print("Renomeando aba '%s' -> '%s'..." % (ws.title, NOVO_NOME))
        ws.update_title(NOVO_NOME)
    else:
        print("Aba ja tem o nome correto: '%s'" % NOVO_NOME)

    # 2. Verifica e reorganiza colunas se necessario
    rows = ws.get_all_values()
    header_atual = rows[0] if rows else []
    body = rows[1:] if len(rows) > 1 else []

    print("Formato atual: %s" % header_atual)
    print("Linhas de dados: %d" % len(body))

    if header_atual[:2] != ["nome", "url"]:
        # Precisa reorganizar
        def get_col(row, col_name):
            if col_name in header_atual:
                idx = header_atual.index(col_name)
                return row[idx] if idx < len(row) else ""
            return ""

        novas_linhas = []
        for r in body:
            if not any(r):
                continue
            nova_linha = [get_col(r, c) for c in NOVA_ORDEM]
            novas_linhas.append(nova_linha)

        print("Reorganizando %d links..." % len(novas_linhas))
        ws.clear()
        todas = [NOVA_ORDEM] + novas_linhas
        ws.update(todas, "A1", value_input_option="RAW")
    else:
        print("Colunas ja estao no formato correto.")

    # 3. Oculta colunas C ate I (indice 2 ate 8) — campos do sistema
    print("Ocultando colunas do sistema (C-I)...")
    try:
        # gspread usa hide_columns(start, end) com indices 0-based
        # C=2, I=8 -> ocultar colunas 2 a 8 (inclusive)
        sheet_id = ws._properties["sheetId"]
        body_req = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 2,   # coluna C (0-based)
                            "endIndex": 9,      # ate coluna I (exclusivo -> 9)
                        },
                        "properties": {"hiddenByUser": True},
                        "fields": "hiddenByUser",
                    }
                }
            ]
        }
        sh.batch_update(body_req)
        print("Colunas C-I ocultadas com sucesso.")
    except Exception as e:
        print("AVISO: Nao foi possivel ocultar colunas: %s" % e)
        print("Voce pode ocultar manualmente: selecione colunas C-I > clique direito > Ocultar")

    print("\nConcluido!")
    print("A aba '%s' agora mostra apenas:" % NOVO_NOME)
    print("   Coluna A: Nome da empresa/instituicao")
    print("   Coluna B: URL do site de editais")


if __name__ == "__main__":
    reorganizar()
