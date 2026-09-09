# LLM Gateway Observatory

Depois de configurar acesso a um gateway multi-LLM (109 modelos de 15+ provedores atrás de uma única API OpenAI-compatible), a primeira pergunta técnica que apareceu não foi "como eu chamo o modelo" — foi **"como eu sei quanto isso está custando, e como eu evito descobrir isso tarde demais?"**

Este projeto é um logger + dashboard de observabilidade para chamadas feitas através de um gateway LLM (usando [AIsa](https://aisa.one) como backend, mas o client é desacoplado o suficiente para trocar de provedor). Cada chamada é registrada com modelo, provedor, tokens, latência e custo — e o custo é calculado a partir de uma tabela de preços local, versionada e auditável.

## Por que isso importa (a decisão de engenharia central)

A API de modelos do gateway **não devolve preço por chamada nem por modelo** — só `usage.prompt_tokens` / `usage.completion_tokens`, como a maioria das APIs OpenAI-compatible. A página de pricing pública, por sua vez, publica preço por **família** de modelo em vários casos (faixa min–max), não por modelo individual — e cheguei a encontrar um modelo (`Claude Opus-4-1`) citado na página de preços que **não existe mais** na resposta atual de `GET /v1/models`. Ou seja: catálogo de modelos e documentação de preço já divergiram.

A decisão de design foi: **nunca estimar um custo que eu não consigo confirmar**. `pricing.json` marca cada entrada com `verified: true/false`; o client (`aisa_client.py`) só calcula custo quando tem os dois lados do par (preço de input E de output) e a entrada está `verified`. Qualquer outra chamada é logada com `cost_status="unknown_price"` e aparece destacada no dashboard — em vez de silenciosamente subestimar o gasto real.

## O que tem aqui

- `aisa_client.py` — client instrumentado: mede latência, extrai uso de tokens, calcula custo (ou marca como desconhecido), loga tudo em SQLite.
- `db.py` — schema e helpers do log (SQLite, sem dependência externa).
- `pricing.json` — tabela de preços versionada, com fonte e data de verificação, e uma seção explícita para as faixas por família que não dá pra mapear com segurança.
- `demo/compare_models.py` — script de comparação entre modelos com **cost-gating obrigatório**: sempre imprime a exposição máxima em USD antes de executar, e só chama a API de verdade com a flag `--yes`.
- `dashboard/app.py` — dashboard Streamlit: custo por modelo, latência (box plot), tokens por chamada, custo acumulado ao longo do tempo, e um alerta visível quando há chamadas com preço desconhecido.

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha AISA_API_KEY

# 1. Veja o custo estimado ANTES de gastar qualquer coisa
python demo/compare_models.py --prompt "Explique CAP theorem em 2 linhas" \
    --models gpt-5-nano deepseek-v4-flash gemini-3.5-flash

# 2. Só depois de revisar o print acima, execute de fato
python demo/compare_models.py --prompt "Explique CAP theorem em 2 linhas" \
    --models gpt-5-nano deepseek-v4-flash gemini-3.5-flash --yes

# 3. Veja os resultados
streamlit run dashboard/app.py
```

## Próximos passos

- Persistir preços via *pull* automático da página de pricing (hoje é atualização manual — deliberadamente, até existir uma fonte machine-readable confiável).
- Orçamento por `run_tag` com corte automático (parar de chamar modelos assim que um teto de USD é atingido no meio de uma comparação).
- Exportar o log para Parquet e comparar tendência de custo/latência entre múltiplas sessões de comparação.
