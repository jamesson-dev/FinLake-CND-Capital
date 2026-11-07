"""Ingestao das series do Banco Central (API SGS) para a camada raw.

Guardamos o JSON ORIGINAL em disco (dado semiestruturado). O parse fica para o
staging na Semana 2 — a camada raw nao interpreta o dado.

A API limita a janela de consulta a 10 anos para series diarias (verificado em
docs/verificacoes.md); por isso baixamos em janelas de 5 anos.

Rodar:  uv run python -m ingestion.bcb
Config: FINLAKE_ANO_INICIAL (default 2020) e FINLAKE_ANO_FINAL (default 2025)
        definem ate onde as janelas vao.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

SERIES = {
    "selic_meta": 432,
    "selic_diaria": 11,
    "cdi": 12,
    "ipca_mensal": 433,
    "dolar_venda": 1,
}
RAW = Path("data/raw/bcb")


def _janelas(ano_ini: int, ano_fim: int) -> list[tuple[str, str]]:
    """Gera janelas de ate 5 anos (01/01 a 31/12) cobrindo [ano_ini, ano_fim]."""
    janelas: list[tuple[str, str]] = []
    inicio = ano_ini
    while inicio <= ano_fim:
        fim = min(inicio + 4, ano_fim)
        janelas.append((f"01/01/{inicio}", f"31/12/{fim}"))
        inicio = fim + 1
    return janelas


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def baixar(codigo: int, ini: str, fim: str) -> list[dict]:
    """Baixa uma serie da API SGS no intervalo informado, com retry."""
    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
        f"?formato=json&dataInicial={ini}&dataFinal={fim}"
    )
    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def ingerir_todas() -> None:
    ano_ini = int(os.environ.get("FINLAKE_ANO_INICIAL", "2020"))
    ano_fim = int(os.environ.get("FINLAKE_ANO_FINAL", "2025"))
    janelas = _janelas(ano_ini, ano_fim)
    print(f"[bcb] intervalo de anos: {ano_ini}..{ano_fim} | janelas: {janelas}")

    for nome, codigo in SERIES.items():
        pasta = RAW / nome
        pasta.mkdir(parents=True, exist_ok=True)
        for ini, fim in janelas:
            dados = baixar(codigo, ini, fim)
            # Serializa de forma estavel para que rodar de novo gere bytes identicos
            # (idempotencia): mesmas chaves, mesma ordem.
            conteudo = json.dumps(dados, ensure_ascii=False, sort_keys=True)
            destino = pasta / f"{ini[-4:]}_{fim[-4:]}.json"
            destino.write_text(conteudo, encoding="utf-8")
            sha = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:12]
            print(
                f"[bcb] {nome} (serie {codigo}) {ini}..{fim}: "
                f"{len(dados)} registros -> {destino.name} (sha {sha})"
            )
    print("[bcb] concluido.")


def main() -> None:
    ingerir_todas()


if __name__ == "__main__":
    main()
