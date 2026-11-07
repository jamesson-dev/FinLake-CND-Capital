# Verificações de premissas (antes de codar)

> O plano da trilha parte de premissas que podem ter mudado. Aqui registro o que
> confirmei **com dado real**, a data e o comando usado. Reexecutar: `bash _verificacoes.sh`.

Data da verificação: **2026-11-06**

## 1. CVM — URLs e nomes de arquivo dentro dos ZIPs

- URL do ZIP anual (DFP): `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_<ANO>.zip` — **OK** (baixou ~13 MB para 2024).
- Conteúdo do ZIP (confirmado com `zipfile.namelist()`): cada demonstração vem em **duas variantes**, consolidado (`_con`) e individual (`_ind`):
  - `dfp_cia_aberta_<ANO>.csv` (índice)
  - `dfp_cia_aberta_BPA_con_<ANO>.csv` / `_ind_`
  - `dfp_cia_aberta_BPP_con_<ANO>.csv` / `_ind_`
  - `dfp_cia_aberta_DRE_con_<ANO>.csv` / `_ind_`
  - `dfp_cia_aberta_DFC_MD_con_<ANO>.csv` / `_ind_`  ← **método direto** (o que usamos)
  - `dfp_cia_aberta_DFC_MI_con_<ANO>.csv` / `_ind_`  ← método indireto (ignorar no MVP)
  - também: composicao_capital, DMPL, DRA, DVA, parecer (fora do escopo do MVP)
- **Implicação para a ingestão**: ingiro **todos** os CSV do ZIP (a camada raw não escolhe;
  o recorte `_con` vs `_ind` e DFC_MD vs DFC_MI é decisão de staging/marts na Semana 2).

## 2. CVM — Cabeçalho do CSV (DRE consolidado 2024)

```
CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA
```

- Delimitador: `;` — **OK**
- Encoding: **latin-1** (há acentos: "Demonstração", "PENÚLTIMO") — **OK**
- `ESCALA_MOEDA = MIL` observado → normalizar para reais (×1000) no staging — **OK**
- `ORDEM_EXERC` traz `PENÚLTIMO` (e `ÚLTIMO`) → filtro `not like 'PEN%'` do staging é válido — **OK**
- `CD_CONTA` hierárquico (ex.: `3.01` Receita) — **OK**
- Total de linhas no DRE_con 2024: ~32.776.

## 3. CVM — Cadastro de companhias

- URL: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` — **OK**
- Cabeçalho (colunas úteis em **negrito** mental): `CNPJ_CIA; DENOM_SOCIAL; DENOM_COMERC;
  DT_REG; DT_CONST; DT_CANCEL; MOTIVO_CANCEL; SIT; DT_INI_SIT; CD_CVM; SETOR_ATIV;
  TP_MERC; CATEG_REG; ...` (mais dados de endereço/responsável).
  - `SIT` = situação do registro; `SETOR_ATIV` = setor de atividade (usados no snapshot/marts).
- ~2.679 companhias no cadastro atual.

## 4. BCB — Limite de intervalo por consulta (API SGS)

- Confirmado **empiricamente**: para séries de periodicidade **diária**, a API retorna erro
  se a janela for **maior que 10 anos**:
  > "O sistema aceita uma janela de consulta de, no máximo, 10 anos em séries de
  > periodicidade diária."
- Janela de **5 anos** (2015–2019) na série 11 (Selic diária) retornou **1.253 registros** — **OK**.
- **Decisão**: manter janelas de 5 anos (como no plano). Seguro para todas as séries,
  inclusive as diárias (11 e 1).
- Formato do JSON: `[{"data":"dd/mm/aaaa","valor":"0.043739"}, ...]` — **OK** (parse fica no staging).
- Séries a ingerir: `selic_meta=432`, `selic_diaria=11`, `cdi=12`, `ipca_mensal=433`, `dolar_venda=1`.

## 5. Compatibilidade de versões (uv pip list / dbt --version)

- Python: **3.12.16** (gerenciado pelo uv, isolado do sistema que é 3.14).
- `dbt-core`: **1.12.6** (latest da série v1 — "Up to date").
- `dbt-duckdb`: **1.11.1** (compatível com dbt-core 1.12).
- `duckdb`: **2.0.0**; `httpx`: 0.28.1; `tenacity`: 9.2.1.
- dev: `ruff` 0.17.4, `pytest` 9.2.0, `pre-commit` 4.7.0, `sqlfluff` 4.5.0.
- **Nota sobre dbt v2**: o CLI avisa que "dbt v2 is available and is the default for new
  installations". O plano manda **ficar no dbt Core v1** e justificar em ADR na Semana 4.
  Mantemos 1.12.6 de propósito.

## 6. Pendências a confirmar na Semana 2 (não bloqueiam a Semana 1)

- Códigos de conta exatos para dívida bruta e caixa/aplicações (confirmar em amostras de
  empresas diferentes).
- Contas de D&A no DFC_MD (variam por empresa; usar `ilike` na descrição).
- Separação de bancos/seguradoras (plano de contas diferente) via `SETOR_ATIV` do cadastro.
