# Dicionário de Dados — Camada Bronze (raw)

A camada **bronze** é a cópia fiel e imutável das fontes públicas, em Parquet.
Regra de ouro: **nada do dado original é alterado**. Todas as colunas de origem entram
como **texto** (`all_varchar=true`); a tipagem e as regras de negócio ficam para a
camada prata (staging/marts) na Semana 2.

Toda tabela bronze recebe três **colunas de rastreio** (procedência), que permitem
auditar qualquer número até o arquivo de origem:

| Coluna | Tipo | Significado |
|---|---|---|
| `_source_file` | varchar | Nome do arquivo de origem dentro do pacote (ex.: `dfp_cia_aberta_DRE_con_2025.csv`). |
| `_source_sha` | varchar | SHA-256 (12 primeiros dígitos) do **pacote** baixado (ZIP da CVM ou JSON do BCB). Muda se a fonte mudar → base da idempotência. |
| `_ingested_at` | timestamp | Momento (UTC) em que a linha foi ingerida. |

---

## 1. CVM — Demonstrações financeiras (DFP e ITR)

Local: `data/raw/cvm/{DFP,ITR}/<ANO>/<arquivo>.parquet`
Origem: ZIP anual em `dados.cvm.gov.br` (licença ODbL). Encoding original **latin-1**,
delimitador `;`. Cada ZIP traz as demonstrações em variantes **consolidado** (`_con`)
e **individual** (`_ind`).

Demonstrações relevantes para o MVP (as demais — DMPL, DRA, DVA, composição de capital,
parecer — são ingeridas mas ficam fora dos marts):

| Arquivo (padrão) | Conteúdo |
|---|---|
| `*_DRE_con_*` / `*_DRE_ind_*` | Demonstração do Resultado (receita, EBIT, lucro). |
| `*_BPA_con_*` / `*_BPA_ind_*` | Balanço Patrimonial Ativo. |
| `*_BPP_con_*` / `*_BPP_ind_*` | Balanço Patrimonial Passivo (inclui PL). |
| `*_DFC_MD_con_*` / `*_DFC_MD_ind_*` | Fluxo de Caixa, método **direto** (usado p/ D&A). |
| `*_DFC_MI_con_*` / `*_DFC_MI_ind_*` | Fluxo de Caixa, método indireto (fora do MVP). |

Colunas de origem (comuns a DRE/BPA/BPP/DFC), todas como texto:

| Coluna | Significado | Observação / armadilha |
|---|---|---|
| `CNPJ_CIA` | CNPJ da companhia | Vem formatado (`00.000.000/0001-91`). No staging vira só dígitos. |
| `DT_REFER` | Data de referência do balanço | `YYYY-MM-DD`. |
| `VERSAO` | Versão do documento | **Reapresentações**: a válida é a última (`max(versao)`) por documento inteiro. |
| `DENOM_CIA` | Razão social | |
| `CD_CVM` | Código CVM da companhia | |
| `GRUPO_DFP` | Grupo/descrição da demonstração | ex.: "DF Consolidado - Demonstração do Resultado". |
| `MOEDA` | Moeda | normalmente `REAL`. |
| `ESCALA_MOEDA` | Escala do valor | `MIL` ou `UNIDADE` → normalizar p/ reais (×1000 se MIL). |
| `ORDEM_EXERC` | Exercício | `ÚLTIMO` ou `PENÚLTIMO`; o PENÚLTIMO repete o ano anterior (filtrar). |
| `DT_INI_EXERC` | Início do exercício | |
| `DT_FIM_EXERC` | Fim do exercício | |
| `CD_CONTA` | Código da conta (hierárquico) | ex.: `3.01` receita, `3.05` EBIT, `1` ativo, `2` passivo. Bancos/seguradoras usam plano diferente. |
| `DS_CONTA` | Descrição da conta | usada p/ localizar D&A via `ilike`. |
| `VL_CONTA` | Valor da conta | texto; vira `double` no staging, aplicando a escala. |
| `ST_CONTA_FIXA` | Conta fixa (S/N) | |

Contagens verificadas (2025, DRE_con): **30.980 linhas**, **440 empresas distintas**.

## 2. CVM — Cadastro de companhias

Local: `data/raw/cvm/cadastro/cad_cia_aberta.parquet`
Origem: `cad_cia_aberta.csv`. Verificado: **2.679 companhias**.

Colunas úteis (entre muitas de endereço/responsável):

| Coluna | Significado |
|---|---|
| `CNPJ_CIA` | CNPJ (chave de junção com as demonstrações). |
| `DENOM_SOCIAL` / `DENOM_COMERC` | Razão social / nome comercial. |
| `SIT` | Situação do registro (ativo, cancelado, etc.). |
| `SETOR_ATIV` | Setor de atividade (usado p/ excluir bancos/seguradoras). |
| `CD_CVM` | Código CVM. |
| `DT_REG`, `DT_CANCEL` | Datas de registro e cancelamento. |

> Na Semana 3 o cadastro vira um **snapshot SCD2** (`SETOR_ATIV` e `SIT` mudam ao longo do tempo).

## 3. Banco Central — Séries SGS

Local: `data/raw/bcb/<serie>/<ini>_<fim>.json`
Origem: API SGS. Guardamos o **JSON original** (dado semiestruturado); o parse fica no staging.
Formato: `[{"data":"dd/mm/aaaa","valor":"10.65"}, ...]`.
Janelas de **5 anos** (a API corta séries diárias acima de 10 anos — verificado).

| Pasta (série) | Código SGS | Conteúdo | Periodicidade |
|---|---|---|---|
| `selic_meta` | 432 | Selic meta | diária (dias corridos) |
| `selic_diaria` | 11 | Selic diária efetiva | dias úteis |
| `cdi` | 12 | CDI | dias úteis |
| `ipca_mensal` | 433 | IPCA | mensal |
| `dolar_venda` | 1 | Dólar PTAX venda | dias úteis |

Campos do JSON: `data` (`dd/mm/aaaa`, vira `date` no staging via `strptime`), `valor`
(texto, vira `double`). Contagens verificadas (2025): selic_meta 365, selic_diaria 252,
cdi 252, ipca_mensal 12, dolar_venda 252.

---

## Como auditar um número até a origem

1. No mart, todo registro carrega `cnpj`, `ano` e (via staging) `_source_file` + `_source_sha`.
2. `_source_file` diz o CSV exato; `_source_sha` identifica o pacote baixado.
3. `CD_CONTA` + `DT_REFER` + `VERSAO` localizam a linha contábil original no Parquet bronze.
