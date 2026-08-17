# ADR-0057 — Número reservado (autonomia do edge)

**Status:** Reservado · **Data:** 2026-08-14 · **Autores:** procedência-de-relatos (gate de docs)
**Relaciona:** ADR-0055 (plano de controle edge), ADR-0056 (agente edge daemon), ADR-0058

## Contexto

A ADR-0058 (ciclo de vida da câmera) foi escrita **referenciando `ADR-0057 (autonomia do
edge)` e `ADR-0057 / runbook de rotação`** antes de a ADR-0057 existir. O número ficou
citado mas o arquivo nunca foi criado — um dos seis relatos que motivaram o gate de
procedência (ver `docs/decisions/PROCEDENCIA_DE_RELATOS.md`).

## Decisão

O número **0057 fica reservado** (queimado), não reaproveitado. A citação em ADR-0058
resolve-se apontando para as decisões que de fato cobrem "autonomia do edge": **ADR-0055**
(config cloud→edge por pull) e **ADR-0056** (daemon supervisionado), mais o runbook de
rotação de token. Este placeholder existe para (a) tornar o buraco na sequência
**declarado** em vez de silencioso — o gate exige que todo número 0001..N tenha arquivo —
e (b) não perder o rastro da referência pendente.

## Consequências

- Positivas: sequência de ADR sem buraco silencioso; referência pendente rastreada.
- Negativas / trade-offs: nenhuma decisão nova aqui — é um marcador.
- Se a "autonomia do edge" virar uma decisão própria, **crie um número novo** (não reuse 0057).
