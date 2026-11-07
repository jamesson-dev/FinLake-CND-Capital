"""Verificacao da camada raw (bronze).

Criterio de pronto da Semana 1:
- contagens da CVM fazem sentido (centenas de empresas por ano);
- todas as 5 series do BCB aparecem.

Rodar da raiz do repositorio:  uv run python check_raw.py
"""

from __future__ import annotations

import duckdb


def _existe(glob: str) -> bool:
    try:
        duckdb.sql(f"SELECT 1 FROM read_parquet('{glob}') LIMIT 1").fetchall()
        return True
    except duckdb.IOException:
        # Nenhum arquivo casou com o glob (ainda nao ingerido).
        return False


def main() -> None:
    print("=== CVM: DRE consolidado por ano (linhas e empresas distintas) ===")
    dre_glob = "data/raw/cvm/DFP/*/*DRE_con*.parquet"
    if _existe(dre_glob):
        print(
            duckdb.sql(
                f"""
                SELECT split_part(_source_file, '_', 5)        AS ano_arquivo,
                       count(*)                                 AS linhas,
                       count(DISTINCT CNPJ_CIA)                 AS empresas
                FROM read_parquet('{dre_glob}')
                GROUP BY 1 ORDER BY 1
                """
            )
        )
    else:
        print(f"(sem dados em {dre_glob} — rode a ingestao da CVM primeiro)")

    print("\n=== CVM: cadastro (companhias) ===")
    cad_glob = "data/raw/cvm/cadastro/*.parquet"
    if _existe(cad_glob):
        print(
            duckdb.sql(
                f"SELECT count(*) AS companhias FROM read_parquet('{cad_glob}')"
            )
        )
    else:
        print(f"(sem dados em {cad_glob})")

    print("\n=== BCB: series e registros por janela ===")
    bcb_glob = "data/raw/bcb/*/*.json"
    try:
        print(
            duckdb.sql(
                f"""
                SELECT regexp_extract(filename, 'bcb/([^/]+)/', 1) AS serie,
                       count(*)                                    AS registros
                FROM read_json('{bcb_glob}', filename=true)
                GROUP BY 1 ORDER BY 1
                """
            )
        )
    except Exception as e:
        print(f"(sem dados do BCB ou erro ao ler: {e})")


if __name__ == "__main__":
    main()
