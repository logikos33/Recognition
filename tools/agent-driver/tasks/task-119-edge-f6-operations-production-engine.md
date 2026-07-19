---
title: "F6 — Motor de operações em produção: popular operation_results"
commit_message: "feat(operations): loop de avaliação em produção popula operation_results (F6)"
eval: default
risk: security
---

# F6 — Motor de operações em produção

## Objetivo
Hoje a única chamada de `evaluate(` é o `/test` (`operations/routes.py`); `operation_results` não é
populada por nenhum worker — operações não rodam em produção.

## Critérios de aceitação
- [ ] Loop/worker que avalia operações contra o stream de detecções e popula `operation_results`.
- [ ] Escopo tenant/câmera correto; sem vazamento cross-tenant.
- [ ] Migration (se necessária) forward-only, aditiva, commit separado, harness 2×.

## Arquivos no escopo
- `services/api/app/infrastructure/queue/**`, `services/inference/**`, `operations/**`
