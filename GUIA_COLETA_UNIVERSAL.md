# 🚀 Guia de Operação - Coleta Universal de Editais

Este guia explica como usar a **Coleta Universal via IA** do sistema Quintessa Editais.


## � Configuração Inicial (API Key)

Antes de usar a coleta universal, você precisa configurar a API Key da Perplexity:

### Passo 1: Obter a API Key

1. Acesse: https://www.perplexity.ai/settings/api
2. Faça login ou crie uma conta
3. Clique em "Generate" para criar uma nova API Key
4. Copie a chave (formato: `pplx-xxxxxxxxxxxxxxxxx`)

### Passo 2: Configurar no Sistema

Abra o arquivo `.env` na pasta do projeto e adicione:

```env
PERPLEXITY_API_KEY="pplx-sua-chave-aqui"
```

### Passo 3: Reiniciar o Sistema

Após salvar o `.env`, reinicie o servidor para carregar a nova configuração.

### 💸 Custos da API

| Modelo | Custo aproximado | Uso recomendado |
|--------|------------------|-----------------|
| Sonar | ~$1 por milhão de tokens | Coleta normal (padrão) |
| Sonar Pro | ~$5 por milhão de tokens | Páginas complexas |

**Na prática:** Uma coleta de 50 links custa aproximadamente **R$ 0,10 a R$ 0,50**.

### 📦 Distribuição para Outros PCs

Para rodar em outro computador:

1. Copie toda a pasta do projeto
2. Copie os arquivos de configuração:
   - `.env` (contém SHEET_URL e PERPLEXITY_API_KEY)
   - `service_account.json` (credenciais Google Sheets)
   - `config.json` (configurações gerais)
3. Instale as dependências: `pip install -r requirements.txt`
4. Execute: `python run.py`

> ⚠️ **IMPORTANTE**: Nunca compartilhe sua API Key publicamente!

---

## �📋 Visão Geral

A Coleta Universal permite extrair editais de **qualquer site** automaticamente usando Inteligência Artificial (Perplexity API), sem necessidade de criar scrapers específicos para cada fonte.

## 🔧 Como Usar

### 1. Cadastrar Links

1. Na página de **Coleta e gestão**, clique no botão **"� CADASTRAR LINKS"**
2. Um modal abrirá mostrando todos os links organizados por grupo
3. Use a **barra de pesquisa** para verificar se um link já existe
4. No formulário abaixo, preencha:
   - **URL do site**: Link da página que lista os editais
   - **Grupo**: Selecione o grupo de classificação
   - **Nome/Apelido**: Opcional, para identificar melhor
5. Clique em **"💾 Salvar Link"**

#### Exemplos de URLs bons:
```
✅ https://www.finep.gov.br/chamadas-publicas
✅ https://fapesp.br/auxilios
✅ https://www.gov.br/cgu/pt-br/assuntos/licitacoes-e-contratos
```

#### Exemplos de URLs ruins:
```
❌ https://www.finep.gov.br/chamadas-publicas/edital-123  (edital específico)
❌ https://www.finep.gov.br/  (página inicial genérica)
```

### 2. Gerenciar Links

No modal de links, cada link mostra:
- 🟢 **Verde**: Link ativo (será coletado)
- 🔴 **Vermelho**: Link inativo (ignorado na coleta)
- **Status da última execução**: ✅ ok ou ❌ erro
- **Data e quantidade** de itens encontrados

**Ações disponíveis:**
- **Checkbox**: Selecione múltiplos links para exclusão em lote
- **Expandir/Contrair grupos**: Clique no cabeçalho do grupo
- **🗑️ Excluir Selecionados**: Remove os links marcados

### 3. Executar Coleta

1. Configure os **filtros** desejados (prazo, valor)
2. Selecione os **grupos** a coletar usando os checkboxes (GOV, FUNDA, LATAM)
3. Clique em **"RODAR COLETA"**

O sistema processará apenas os links dos grupos selecionados usando IA.

**Após a coleta:**
- Os resultados aparecem em cards por link
- Cards de erro podem ser fechados clicando no **✕**
- Use **"Limpar Todos"** para fechar todos os cards de uma vez

### 4. Usar Filtros

Os filtros funcionam "de verdade" na coleta universal:

- **Prazo mínimo**: A IA só retornará editais com deadline >= X dias no futuro
- **Valor máximo**: A IA filtrará editais acima do valor especificado
- **Regex por grupo**: Palavras-chave são passadas para a IA

## ⚠️ Limitações

1. **Páginas dinâmicas (JavaScript pesado)**: Alguns sites carregam conteúdo via JavaScript que a API não consegue processar. Para esses casos, os providers tradicionais (com Playwright) são mais eficientes.

2. **PDFs protegidos**: Se o PDF tiver proteção contra cópia, a extração pode falhar.

3. **Rate limiting**: Sites podem bloquear muitas requisições seguidas. Recomendamos não cadastrar muitos links do mesmo domínio.

4. **Precisão**: A IA pode ocasionalmente extrair informações imprecisas. Sempre revise os editais importantes.

## 🔄 Fluxo de Dados

```
Link Cadastrado
      │
      ▼
  Download da página (HTML/PDF)
      │
      ▼
  Envio para Perplexity API
  (com prompt especializado)
      │
      ▼
  Resposta em JSON estruturado
      │
      ▼
  Filtros aplicados (prazo, valor, regex)
      │
      ▼
  Gravação na aba "items" da planilha
      │
      ▼
  Atualização do status do link
```

## 📊 Aba "links_cadastrados" na Planilha

Os links são salvos na aba `links_cadastrados` com as colunas:

| Coluna | Descrição |
|--------|-----------|
| uid | ID único do link |
| url | URL cadastrada |
| grupo | Grupo associado |
| nome | Apelido/nome personalizado |
| ativo | Se está ativo (true/false) |
| created_at | Data de criação |
| last_run | Data da última execução |
| last_status | Resultado (ok/erro) |
| last_items | Quantidade de itens encontrados |

## 🐛 Troubleshooting

### "Erro ao baixar página"
- Verifique se a URL está acessível no navegador
- Alguns sites bloqueiam bots - tente mais tarde

### "Resposta vazia da API"
- A página pode não ter editais ativos
- Tente com um modelo mais potente (sonar-pro)

### "API key não configurada"
- Abra o arquivo `.env` na raiz do projeto
- Adicione a linha: `PERPLEXITY_API_KEY="pplx-sua-chave"`
- Reinicie o servidor
- Obtenha sua chave em: https://www.perplexity.ai/settings/api

### Poucos itens encontrados
- A IA é conservadora - prefere não retornar do que retornar errado
- Verifique se a URL aponta para uma página de listagem

## 📝 Dicas de Uso

1. **Comece com poucos links** para validar que estão funcionando
2. **Cadastre a página de listagem**, não editais individuais
3. **Use nomes descritivos** para identificar os links facilmente
4. **Monitore os custos** na sua conta Perplexity
5. **Revise os resultados** periodicamente para ajustar

---

*Desenvolvido para Quintessa - Automação de Editais*
