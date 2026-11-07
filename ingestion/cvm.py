"""Ingestao da CVM (DFP/ITR + cadastro) para a camada raw em Parquet.

Principios da camada raw (bronze):
- Imutavel: o conteudo original NAO e alterado. Tudo entra como texto (all_varchar).
- Idempotente: rodar duas vezes produz o mesmo resultado, sem duplicar.
- Rastreavel: cada linha carrega _source_file, _source_sha e _ingested_at.
- Resiliente: o download tenta de novo (retry com backoff) quando a rede falha.

Rodar:  uv run python -m ingestion.cvm
Config: FINLAKE_ANO_INICIAL (default 2020) e FINLAKE_ANO_FINAL (default 2025).
"""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"
CAD_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
RAW = Path("data/raw/cvm")


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def baixar(url: str) -> bytes:
    """Baixa o conteudo de uma URL com retry exponencial."""
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return r.content


def _sha12(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()[:12]


def _ja_ingerido(parquet: Path, sha: str) -> bool:
    """Idempotencia: Parquet existe e foi gerado do mesmo pacote de origem (_source_sha)."""
    if not parquet.exists():
        return False
    try:
        linhas = duckdb.sql(
            f"SELECT DISTINCT _source_sha FROM read_parquet('{parquet.as_posix()}') LIMIT 1"
        ).fetchall()
    except Exception:
        return False
    return bool(linhas) and linhas[0][0] == sha


def _csv_para_parquet(csv_bytes: bytes, nome: str, sha: str, parquet: Path) -> None:
    """Grava um CSV (latin-1, delim ';') como Parquet, tudo texto, com colunas de rastreio.

    Decodifica em Python antes de gravar o CSV temporario, para nao depender do
    suporte a encoding do DuckDB (ponto de atencao citado no plano).
    """
    ingested_at = datetime.now(UTC).isoformat()
    tmp_csv = parquet.with_suffix(".tmp.csv")
    # latin-1 -> utf-8; errors='replace' preserva a linha mesmo com byte invalido.
    tmp_csv.write_text(csv_bytes.decode("latin-1", errors="replace"), encoding="utf-8")
    try:
        duckdb.sql(
            f"""
            COPY (
                SELECT *,
                       '{nome}'         AS _source_file,
                       '{sha}'          AS _source_sha,
                       TIMESTAMP '{ingested_at}' AS _ingested_at
                FROM read_csv(
                    '{tmp_csv.as_posix()}',
                    delim=';', header=true, encoding='utf-8', all_varchar=true
                )
            ) TO '{parquet.as_posix()}' (FORMAT parquet)
            """
        )
    finally:
        tmp_csv.unlink(missing_ok=True)


def ingerir_doc(doc: str, ano: int) -> None:
    """Baixa o ZIP de um documento (DFP/ITR) de um ano e grava cada CSV como Parquet."""
    url = f"{BASE}/{doc}/DADOS/{doc.lower()}_cia_aberta_{ano}.zip"
    print(f"[cvm] {doc} {ano}: baixando {url}")
    conteudo = baixar(url)
    sha = _sha12(conteudo)
    destino = RAW / doc / str(ano)
    destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for nome in csvs:
            parquet = destino / Path(nome).with_suffix(".parquet").name
            if _ja_ingerido(parquet, sha):
                print(f"[cvm]   {nome}: ja ingerido (sha {sha}), pulando")
                continue
            _csv_para_parquet(z.read(nome), nome, sha, parquet)
            print(f"[cvm]   {nome} -> {parquet.name}")


def ingerir_cadastro() -> None:
    """Baixa o cadastro de companhias abertas e grava como Parquet (imutavel, rastreavel)."""
    print(f"[cvm] cadastro: baixando {CAD_URL}")
    conteudo = baixar(CAD_URL)
    sha = _sha12(conteudo)
    destino = RAW / "cadastro"
    destino.mkdir(parents=True, exist_ok=True)
    parquet = destino / "cad_cia_aberta.parquet"
    if _ja_ingerido(parquet, sha):
        print(f"[cvm]   cadastro: ja ingerido (sha {sha}), pulando")
        return
    _csv_para_parquet(conteudo, "cad_cia_aberta.csv", sha, parquet)
    print(f"[cvm]   cadastro -> {parquet.name}")


def main() -> None:
    ano_ini = int(os.environ.get("FINLAKE_ANO_INICIAL", "2020"))
    ano_fim = int(os.environ.get("FINLAKE_ANO_FINAL", "2025"))
    print(f"[cvm] intervalo de anos: {ano_ini}..{ano_fim}")
    for doc in ("DFP", "ITR"):
        for ano in range(ano_ini, ano_fim + 1):
            ingerir_doc(doc, ano)
    ingerir_cadastro()
    print("[cvm] concluido.")


if __name__ == "__main__":
    main()
