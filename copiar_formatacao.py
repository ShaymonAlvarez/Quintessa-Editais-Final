# -*- coding: utf-8 -*-
"""
Script: copia a formatacao do cabecalho da aba 'items' para as outras abas.
"""

import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from backend.core.sheets import get_gspread_client, open_sheet


def copiar_formatacao():
    print("Conectando ao Google Sheets...")
    try:
        sh, *_ = open_sheet()
    except Exception as e:
        print("ERRO ao abrir planilha: %s" % e)
        return

    # 1. Ler formatacao do cabecalho da aba 'items'
    try:
        ws_items = sh.worksheet("items")
    except Exception as e:
        print("ERRO: aba 'items' nao encontrada: %s" % e)
        return

    items_id = ws_items._properties["sheetId"]

    # Busca formatacao da linha 1 da aba items via API
    resp = sh.fetch_sheet_metadata({
        "includeGridData": True,
        "ranges": ["items!1:1"],
        "fields": "sheets.data.rowData.values.userEnteredFormat,sheets.data.rowData.values.effectiveFormat"
    })

    # Extrai o formato da primeira linha
    try:
        row_data = resp["sheets"][0]["data"][0]["rowData"][0]["values"]
    except (KeyError, IndexError) as e:
        print("ERRO: nao consegui ler formatacao da aba items: %s" % e)
        return

    # Pega o formato da primeira celula como referencia
    fmt_ref = None
    for cell in row_data:
        fmt = cell.get("userEnteredFormat") or cell.get("effectiveFormat")
        if fmt:
            fmt_ref = fmt
            break

    if not fmt_ref:
        print("ERRO: nenhuma formatacao encontrada na aba items.")
        return

    print("Formatacao capturada da aba 'items':")
    bg = fmt_ref.get("backgroundColor", {})
    print("   Cor de fundo: R=%.2f G=%.2f B=%.2f" % (bg.get("red", 0), bg.get("green", 0), bg.get("blue", 0)))
    tf = fmt_ref.get("textFormat", {})
    print("   Negrito: %s" % tf.get("bold", False))
    print("   Tamanho fonte: %s" % tf.get("fontSize", "?"))
    fg = tf.get("foregroundColor", tf.get("foregroundColorStyle", {}).get("rgbColor", {}))
    print("   Cor texto: R=%.2f G=%.2f B=%.2f" % (fg.get("red", 0), fg.get("green", 0), fg.get("blue", 0)))

    # 2. Aplica a mesma formatacao nas outras abas
    abas_alvo = ["config", "logs", "INCLUIR AQUI"]
    requests = []

    for aba_nome in abas_alvo:
        try:
            ws = sh.worksheet(aba_nome)
        except Exception:
            print("Aba '%s' nao encontrada, pulando..." % aba_nome)
            continue

        sheet_id = ws._properties["sheetId"]
        num_cols = ws.col_count

        # Formata toda a linha 1 (cabecalho)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                },
                "cell": {
                    "userEnteredFormat": fmt_ref
                },
                "fields": "userEnteredFormat"
            }
        })

        print("Formatacao sera aplicada na aba '%s' (%d colunas)" % (aba_nome, num_cols))

    if not requests:
        print("Nenhuma aba para formatar.")
        return

    # Executa batch update
    try:
        sh.batch_update({"requests": requests})
        print("\nFormatacao aplicada com sucesso em todas as abas!")
    except Exception as e:
        print("ERRO ao aplicar formatacao: %s" % e)


if __name__ == "__main__":
    copiar_formatacao()
