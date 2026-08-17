# Procedência de relatos — todo relato é hipótese até ser verificado

**Criado em:** 2026-08-14 · **Aplica a:** documentação, docstrings, comentários, relatórios de agente.

## A regra

> **Todo relato — documentação, docstring, comentário, relatório de agente — é hipótese
> até ser verificado contra código, git ou banco.**

É a regra **C-04** aplicada a qualquer texto, não só ao `CLAUDE.md`. Não é filosofia: custou
dinheiro e retrabalho medidos.

## Por que existe — seis relatos falsos numa única semana

| # | O que o relato afirmou | O que o repo/git/banco mostrava |
|---|---|---|
| 1 | `CLAUDE.md` descrevia `backend/`, `frontend/` e 13 microserviços | não existem desde mai/2026 (ADR-0014) |
| 2 | `CLAUDE.md`: evidência **cloud-first (ADR-0028)** | superseded por **ADR-0045** (recorder-first) em 14/07 |
| 3 | docstring de `runpod_runner.py`: pods RunPod não reiniciam | o log mostrava dezenas de reinícios |
| 4 | um PR relatado como **pronto** | tinha **zero commits** |
| 5 | doc listava **`Sem Capacete`** como classe ativa | **nunca existiu no banco** (D-103) |
| 6 | existiam **duas ADR-0043** e a **0057 não existia** (0058 a referenciava) | a 0058 de fato referenciava um número vazio |

Custo real: **US$ 21,54** num pod órfão, **um prompt inteiro** escrito sobre um risco
inexistente (item 3), e uma **classe fantasma em três rodadas de planeamento** (item 5).

## O item mais caro é o 2

O `CLAUDE.md` é lido por **todo agente no início de sessão**. Um erro ali entra em **todo
trabalho que começa** depois. Foi assim que a taxonomia errada (item 5) se propagou.

## Esta própria rodada herdou relatos furados — a prova viva da regra

O prompt que originou este documento foi escrito a partir de **leitura de um checkout
desatualizado** (218 commits atrás de `origin/develop`). Verificado contra o git:

- A **dupla ADR-0043 já estava resolvida** em `origin/develop` — não havia o que renumerar.
- O buraco de numeração não era só 0057: **0059 também** era um número ausente (o prompt não citou).
- "**12 ADRs sem Status**": em `origin/develop` **todos** os ADRs numerados (0001–0062) têm Status;
  só o `0000-template` e o arquivo de reconciliação não têm — e nenhum dos dois é decisão.

Ou seja: o próprio prompt que pregava "não confie em leitura" **foi escrito a partir de leitura**.
Isso não é ironia — é a demonstração de por que o gate precisa existir.

## O gate

`scripts/ci/check_docs_gate.py` (stdlib only, sem AGPL — ADR-0043 vale para a ferramenta) falha o
CI em seis condições: número de ADR duplicado · Status ausente/inválido · buraco na sequência (um
número reservado precisa de placeholder `Status: Reservado`, para o buraco ser **declarado**) ·
`CLAUDE.md` citando ADR **Superseded** · título interno ≠ número do arquivo · **taxonomia RVB
divergindo entre documentos**. Corrigir os seis à mão sem o gate garante o sétimo.

**Recomendação (não implementada — exigiria banco no CI):** a regra 6 poderia comparar também
contra as classes **não-arquivadas do banco**, pegando classe fantasma na origem (o caso do
`Sem Capacete`). Fica como recomendação porque forçar conexão de banco no CI é custo desproporcional
para esta guarda; o gate atual compara documento-contra-documento, que já teria pego o item 5.
