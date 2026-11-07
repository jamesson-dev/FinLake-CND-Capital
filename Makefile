.PHONY: ingest ingest-cvm ingest-bcb check test lint all

# Anos da ingestao (sobrescreva: make ingest FINLAKE_ANO_INICIAL=2020 FINLAKE_ANO_FINAL=2025)
FINLAKE_ANO_INICIAL ?= 2025
FINLAKE_ANO_FINAL   ?= 2025
export FINLAKE_ANO_INICIAL
export FINLAKE_ANO_FINAL

ingest: ingest-cvm ingest-bcb

ingest-cvm:
	uv run python -m ingestion.cvm

ingest-bcb:
	uv run python -m ingestion.bcb

check:
	uv run python check_raw.py

lint:
	uv run ruff check ingestion check_raw.py tests

test:
	uv run pytest -q

all: ingest check
