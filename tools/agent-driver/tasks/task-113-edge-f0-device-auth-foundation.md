---
title: "F0 — Fundação: device auth de commands/events (já resolvido; fixar contrato)"
commit_message: "docs(edge): reconciliar API_CONTRACT_MAP com device auth já corrigido (F0)"
eval: default
risk: security
---

# F0 — Fundação do device auth (edge_commands + edge_events)

## NEEDS CLARIFICATION
Nenhuma.

## Objetivo
Garantir que a auth de device dos canais de comando e evento funciona antes de tudo.
**Estado real (C-04, 2026-07-18):** B1/B2 **JÁ RESOLVIDOS** na develop (WS10) — `edge_commands` e
`edge_events` extraem o Bearer corretamente via `get_device_context`/`removeprefix`; `poll_pending`
retorna 401 (não 500) em falha. Resta apenas corrigir o `API_CONTRACT_MAP.md`, que ainda mentia.

## Critérios de aceitação
- [x] `edge_commands`/`edge_events` autenticam device (não passam `request` objeto) — verificado no código.
- [x] `API_CONTRACT_MAP.md` itens #8/linha 233/603 corrigidos (bug marcado RESOLVIDO). *(feito neste PR)*
- [ ] Escopo de device aplicado às rotas — **coberto pela trilha de segurança (S1, PR risk:security separado)**.
- [ ] Eval `default` verde.

## Invariantes de segurança
- Device de outro tenant → 404 (nunca 403). Sem fallback de tenant (ADR-0017).

## Arquivos no escopo
- `docs/API_CONTRACT_MAP.md`

## Notas
B1/B2 obsoletos — evidência em `docs/edge/RECONCILIACAO_EDGE_2026-07-18.md`. Testes de scope estão na
trilha de segurança para não misturar as duas trilhas no mesmo PR.
