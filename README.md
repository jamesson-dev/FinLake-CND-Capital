# FinLake CND Capital

Camada de dados confiável, rápida e padronizada sobre dados públicos da **CVM**
(demonstrações financeiras) e do **Banco Central** (séries macroeconômicas), para que
cada métrica financeira seja definida uma só vez, protegida por testes e rastreável até
a origem.

Ver a motivação completa em [`docs/pergunta-de-negocio.md`](docs/pergunta-de-negocio.md).

## Arquitetura (resumo)

```
CVM (ZIP/CSV)   BCB SGS (JSON)
     |                |
     v                v
 [Python: httpx + tenacity]  -> ingestao idempotente, com retry e hash
     |
     v
 data/raw/*.parquet   (RAW / bronze: tudo texto, imutavel, rastreavel)
     |
     v
 DuckDB + dbt (staging -> intermediate -> marts)   [Semana 2+]
```

## Ambiente

- Python 3.12 (gerenciado por **uv**), DuckDB, httpx, tenacity, dbt-core + dbt-duckdb.
- Dev: ruff, pytest, pre-commit, sqlfluff.
- No Windows, trabalhar dentro do **WSL2/Ubuntu**.

Setup:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Semana 1 — Ingestão (camada bronze)

```sh
# Ingerir apenas 2025 (rapido, para validar o pipeline)
FINLAKE_ANO_INICIAL=2025 FINLAKE_ANO_FINAL=2025 uv run python -m ingestion.cvm
FINLAKE_ANO_INICIAL=2025 FINLAKE_ANO_FINAL=2025 uv run python -m ingestion.bcb

# Verificar contagens
uv run python check_raw.py

# Testes (retry + idempotencia)
uv run pytest -q
```

Com `make` instalado:

```sh
make ingest                               # anos default (2025)
make ingest FINLAKE_ANO_INICIAL=2020 FINLAKE_ANO_FINAL=2025
make check
make test
```

A ingestão é **idempotente**: rodar de novo pula arquivos já ingeridos (mesmo
`_source_sha`). Cada linha carrega `_source_file`, `_source_sha` e `_ingested_at`.

Dicionário da camada bronze: [`docs/dicionario-dados-bronze.md`](docs/dicionario-dados-bronze.md).
Verificações de premissas das fontes: [`docs/verificacoes.md`](docs/verificacoes.md).
