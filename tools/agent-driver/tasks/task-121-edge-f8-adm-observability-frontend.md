---
title: "F8 — ADM + observabilidade no front: site/enrollment/gateway/comandos + config efetiva"
commit_message: "feat(frontend): telas ADM edge + painel de config efetiva/drift (F8)"
eval: default
risk: low
---

# F8 — Superfície de ADM no frontend

## Objetivo
Rotas que existem na API mas não têm cliente no front (CRUD de site, enrollment, gateway, console de
comandos) + painel de config efetiva (o que o Edge realmente roda) e drift banco↔device.

## Critérios de aceitação
- [ ] Telas: CRUD de site, fluxo de enrollment (gerar token, mostrar 1x, revogar), config de gateway, console de comandos + histórico.
- [ ] Painel de **config efetiva**: `config_version` aplicada por site + drift banco↔device.
- [ ] `npx tsc --noEmit` verde; zero `any` implícito.

## Arquivos no escopo
- `apps/frontend/src/**`
