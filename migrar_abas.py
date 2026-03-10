# -*- coding: utf-8 -*-
"""
Migra as abas config, items e logs para o layout formatado:
  Linha 1: vazia
  Linha 2: titulo (coluna B)
  Linha 3: vazia
  Linha 4: header (coluna B)
  Linha 5+: dados (coluna B)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.sheets import open_sheet


TABS_CONFIG = {
    "config": {
        "titulo": "SISTEMA: Configuracoes internas da automacao (prazo minimo, cotacao, etc). NAO EDITAR.",
        "header": ["key", "value"],
    },
    "items": {
        "titulo": "SISTEMA: Editais extraidos automaticamente pela IA. Os dados sao preenchidos pela automacao.",
        # header lido dinamicamente da propria aba
    },
    "logs": {
        "titulo": "SISTEMA: Registro de execucoes e erros. NAO EDITAR.",
        "header": ["ts", "level", "msg"],
    },
}


def migrar_aba(sh, nome_aba, cfg):
    print("\n--- Migrando aba '%s' ---" % nome_aba)
    try:
        ws = sh.worksheet(nome_aba)
    except Exception:
        print("   Aba '%s' nao encontrada, pulando." % nome_aba)
        return

    rows = ws.get_all_values()
    if not rows:
        print("   Aba vazia, pulando.")
        return

    # Detecta se ja esta no formato novo (linha 2 tem titulo, linha 4 tem header)
    # Checa se a linha 1 (indice 0) esta vazia e linha 4 (indice 3) tem dados
    if len(rows) >= 4:
        row1_empty = not any(cell.strip() for cell in rows[0])
        row2_has_title = any("SISTEMA" in cell for cell in rows[1])
        if row1_empty and row2_has_title:
            print("   Aba ja esta no formato novo. Pulando.")
            return

    # Pega header e dados atuais (formato antigo: row 0 = header, row 1+ = dados)
    old_header = rows[0]
    old_data = rows[1:]

    # Filtra linhas totalmente vazias
    old_data = [r for r in old_data if any(cell.strip() for cell in r)]

    header = cfg.get("header", old_header)
    titulo = cfg.get("titulo", "")

    print("   Header: %s" % header)
    print("   Dados: %d linhas" % len(old_data))

    # Limpa a aba
    ws.clear()

    # Monta o novo conteudo
    # Linha 1: vazia
    # Linha 2: [vazia, titulo]
    # Linha 3: vazia
    # Linha 4: [vazia, header...]
    # Linha 5+: [vazia, dados...]
    new_rows = []
    new_rows.append([""])                              # Linha 1
    new_rows.append(["", titulo])                      # Linha 2
    new_rows.append([""])                              # Linha 3
    new_rows.append([""] + header)                     # Linha 4

    for r in old_data:
        # Alinha os dados com o header
        # Os dados antigos estao alinhados com old_header
        if old_header == header:
            new_rows.append([""] + r)
        else:
            # Mapeia colunas antigas para novas
            aligned = []
            for h in header:
                if h in old_header:
                    idx = old_header.index(h)
                    aligned.append(r[idx] if idx < len(r) else "")
                else:
                    aligned.append("")
            new_rows.append([""] + aligned)

    # Escreve tudo de uma vez
    try:
        ws.update(new_rows, "A1", value_input_option="RAW")
        print("   OK! Migrada com sucesso (%d linhas)." % len(old_data))
    except Exception as e:
        print("   ERRO ao escrever: %s" % e)


def main():
    print("Conectando ao Google Sheets...")
    try:
        sh, *_ = open_sheet()
    except Exception as e:
        print("ERRO: %s" % e)
        return

    for nome, cfg in TABS_CONFIG.items():
        migrar_aba(sh, nome, cfg)

    print("\nTodas as abas foram migradas!")


if __name__ == "__main__":
    main()
