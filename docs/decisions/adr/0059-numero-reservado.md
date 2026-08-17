# ADR-0059 — Número reservado

**Status:** Reservado · **Data:** 2026-08-14 · **Autores:** procedência-de-relatos (gate de docs)
**Relaciona:** ADR-0058, ADR-0060

## Contexto

Em `origin/develop` (a base canônica) o número **0059 é um buraco na sequência**: existe
0058 e 0060, mas nenhum 0059. Um rascunho `0059-video-local-first-e-sessao-unica.md`
chegou a existir na árvore de trabalho de um checkout ancestral, mas **nunca foi commitado
num ref que alcançasse `origin/develop`** — verificado por `git log --all --diff-filter=A`.

## Decisão

O número **0059 fica reservado** (queimado). Este placeholder torna o buraco **declarado**
— o gate de docs exige que todo número 0001..N tenha arquivo, e um buraco silencioso é
exatamente o que derrubou deploy antes (ADR-0021, colisão de numeração). Se o conteúdo
"vídeo local-first / sessão única" precisar de ADR, **crie um número novo**; não reuse 0059.

## Consequências

- Positivas: sequência sem buraco silencioso; decisão de não reaproveitar o número registrada.
- Negativas / trade-offs: nenhuma — é um marcador.
