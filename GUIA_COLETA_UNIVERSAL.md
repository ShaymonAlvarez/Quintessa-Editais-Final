# 🚀 Guia de Operação - Coleta Universal de Editais

Este guia explica como usar a **Coleta Universal via IA** do sistema Quintessa Editais.

> **⚠️ ATUALIZAÇÃO:** A coleta tradicional (providers fixos) foi descontinuada. Todo o sistema agora opera **exclusivamente** através da coleta inteligente via IA. Os links dos providers originais foram pré-cadastrados automaticamente.

## 📋 Visão Geral

A Coleta Universal permite extrair editais de **qualquer site** automaticamente usando Inteligência Artificial (Perplexity API), sem necessidade de criar scrapers específicos para cada fonte.

### Antes vs Depois

| Aspecto | Coleta Tradicional (Providers) | Coleta Universal (IA) |
|---------|-------------------------------|----------------------|
| Novos sites | Requer código novo | Só cadastrar o link |
| Manutenção | Alta (sites mudam) | Baixa (IA se adapta) |
| Custo | Gratuito | ~R$ 0,002 por extração |
| Flexibilidade | Baixa | Alta |

## 🔧 Como Usar

### 1. Cadastrar Links

1. Na página de **Coleta e gestão**, localize a seção **"🔗 LINKS CADASTRADOS PARA COLETA"**
2. Clique em **"+ Adicionar Link"**
3. Preencha:
   - **URL do site**: Link da página que lista os editais (não o edital individual!)
   - **Grupo**: Selecione o grupo de classificação
   - **Nome/Apelido**: Opcional, para identificar melhor
4. Clique em **"Salvar Link"**

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

Cada link cadastrado mostra:
- 🟢 **Verde**: Link ativo (será coletado)
- 🔴 **Vermelho**: Link inativo (ignorado na coleta)
- **Status da última execução**: ✅ ok ou ❌ erro
- **Data e quantidade** de itens encontrados

**Ações disponíveis:**
- **Ativar/Desativar**: Pause temporariamente um link
- **🗑️ Excluir**: Remove o link permanentemente

### 3. Executar Coleta

1. Configure os **filtros** desejados (prazo, valor)
2. Selecione os **grupos** a coletar (checkbox)
3. Clique em **"RODAR COLETA"**

O sistema executará:
1. **Fase 1**: Coleta tradicional (providers fixos)
2. **Fase 2**: Coleta universal (links cadastrados via IA)

### 4. Usar Filtros

Os filtros funcionam "de verdade" na coleta universal:

- **Prazo mínimo**: A IA só retornará editais com deadline >= X dias no futuro
- **Valor máximo**: A IA filtrará editais acima do valor especificado
- **Regex por grupo**: Palavras-chave são passadas para a IA

## 💰 Custos

A coleta universal usa a API da Perplexity. Custos estimados:

| Modelo | Custo por extração | Uso recomendado |
|--------|-------------------|-----------------|
| Sonar | ~R$ 0,002 | Coleta normal (padrão) |
| Sonar Pro | ~R$ 0,02 | Páginas complexas |
| Sonar Reasoning | ~R$ 0,01 | Análise mais profunda |

**Exemplo prático:**
- 50 links cadastrados × R$ 0,002 = R$ 0,10 por coleta completa
- Executando 3x por dia × 30 dias = R$ 9,00/mês

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
- Configure a variável `PERPLEXITY_API_KEY` no `.env`
- Ou adicione em `config.json`

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
