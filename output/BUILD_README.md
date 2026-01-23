# Quintessa Editais - Build e Distribuição

## Arquivos de Build

| Arquivo | Descrição |
|---------|-----------|
| `build.bat` | Script para gerar o executável |
| `QuintessaEditais.spec` | Configuração do PyInstaller |

## Como Gerar o Executável

### Usando o Script

```batch
output\build.bat
```

### Comando Direto

```batch
cd output
pyinstaller --clean QuintessaEditais.spec
```

## Estrutura de Distribuição

Após o build, a pasta `output\distribuicao\` conterá:

```
distribuicao\
├── QuintessaEditais.exe
├── config.json
├── service_account.json
└── .env
```

Todos os 4 arquivos devem ser enviados juntos para o usuário final.

## Configuração Inicial

### 1. Service Account

Na raiz do projeto, executar:

```batch
python setup_oauth_env.py
```

Selecionar a opção 1 (Service Account) e seguir as instruções.

### 2. Arquivos Necessários

Antes de gerar o executável:

- `service_account.json` - Credenciais do Google
- `.env` - URL da planilha e chave Perplexity (opcional)
- `config.json` - Link do Gist com usuários

### 3. Formato do `.env`

```env
SHEET_URL="https://docs.google.com/spreadsheets/d/ID_DA_PLANILHA/edit"
PERPLEXITY_API_KEY="pplx-xxxxxxxxxxxx"
```

### 4. Formato do `config.json`

```json
{
  "users_db_url": "https://gist.githubusercontent.com/USUARIO/ID_GIST/raw/users.json"
}
```

## Requisitos

```batch
pip install pyinstaller
```

## Troubleshooting

### service_account.json não encontrado

Executar `python setup_oauth_env.py` na raiz do projeto.

### SHEET_URL não definido

Criar arquivo `.env` na raiz do projeto com a URL da planilha.

### Planilha não encontrada

Compartilhar a planilha Google Sheets com o email contido no campo `client_email` do arquivo `service_account.json`.

### Playwright não encontrado

```batch
playwright install chromium
```

## Checklist

- [ ] Configurar Service Account via `setup_oauth_env.py`
- [ ] Criar `.env` com SHEET_URL
- [ ] Verificar `config.json` com link do Gist
- [ ] Executar `output\build.bat`
- [ ] Testar o executável
- [ ] Compactar pasta `distribuicao` e enviar

## Logs

Em caso de erro, verificar o arquivo `api_debug.log` gerado na pasta do executável.
