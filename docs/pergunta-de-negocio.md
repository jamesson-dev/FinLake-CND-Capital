# A Pergunta de Negócio — FinLake CND Capital

> Escrito com minhas próprias palavras antes de qualquer linha de código.
> Este documento é o critério que valida cada decisão técnica do projeto.

## Contexto

A CND Capital é uma fintech de crédito para PMEs, com 3 anos de vida e crescimento
rápido. Cada área (Diretoria, Risco, etc.) montou seus próprios painéis direto em
cima de tabelas brutas. Resultado: no comitê de risco, o painel da Diretoria mostra
um EBITDA médio do portfólio e o painel de Risco mostra outro. Ninguém sabe qual é o
certo, e o painel de Risco ainda demora quase um minuto para carregar. A reunião vira
uma discussão sobre a origem dos números, não sobre a decisão em si.

O problema, portanto, não é "falta de dashboard". É que **não existe uma fonte única
de verdade**: a mesma métrica é calculada de formas diferentes, em lugares diferentes,
sem testes e sem rastreabilidade.

## Pergunta principal (com minhas palavras)

Como eu construo **uma única camada de dados** — confiável, rápida e padronizada — onde
cada métrica financeira seja **definida uma só vez**, **protegida por testes** e
**rastreável até o arquivo e a conta contábil de origem**, de modo que Diretoria,
Risco e qualquer outra área cheguem exatamente ao **mesmo número**?

## Perguntas secundárias do stakeholder

Como não tenho a carteira real da CND Capital, uso dados públicos: demonstrações
financeiras de companhias abertas (CVM) e séries macroeconômicas (Banco Central).
O projeto precisa responder, com dado e não com opinião:

| # | Pergunta do stakeholder (minhas palavras) | Onde respondo |
|---|---|---|
| 1 | Em qual valor de EBITDA eu posso confiar, e por que as versões divergem entre si? | Semana 4 (página de divergência) |
| 2 | Quanto o BI fica mais rápido depois de adotar a camada nova? | Semana 4 (benchmark) |
| 3 | Como eu tenho garantia de que os números estão corretos? | Semana 2 (testes contábeis) |
| 4 | Se um balanço for reapresentado, o que muda e quando eu fico sabendo? | Semana 2 (versões) + Semana 3 (snapshot) |
| 5 | Alguém consegue auditar um número do dashboard até a conta contábil de origem? | Semana 1 (rastreio) + Semana 4 (docs) |
| 6 | Se entrar um ano novo ou uma fonte nova, quanto tempo leva para atualizar tudo? | Semana 3 (`make all` + CI) |

## O que a Semana 1 precisa provar

> Pergunta da Semana 1: **Os dados que temos estão completos e dá para rastrear cada
> número até o arquivo de origem?**

Para responder "sim" ao final da semana, preciso ter:

- A camada **raw** (bronze) em Parquet, **imutável** (nada do dado original é alterado;
  tudo entra como texto).
- **Idempotência**: rodar a ingestão duas vezes produz o mesmo resultado, sem duplicar.
- **Rastreabilidade**: cada linha carrega de qual arquivo veio (`_source_file`), o hash
  do pacote original (`_source_sha`) e quando foi ingerida (`_ingested_at`).
- **Resiliência**: o download tenta de novo quando a rede falha (retry com backoff).

Se, ao final da semana, um auditor apontar um número e perguntar "de qual arquivo isso
veio?", eu consigo responder em menos de um minuto.
