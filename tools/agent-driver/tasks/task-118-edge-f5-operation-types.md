---
title: "F5 — Operation-types faltantes (JÁ RESOLVIDO) + decisão registry estático"
commit_message: "docs(edge): registrar registry estático + op-types RVB já existentes (F5)"
eval: default
risk: low
---

# F5 — Operation-types

## Objetivo
Garantir que o cenário RVB (ADR-0053) tem os operation-types necessários.

## Critérios de aceitação
- [x] `attention_points`, `stage_timer`, `crowd_zone`, `dwell_zone` **JÁ registrados** (`operations/canonical/__init__.py`, task-109/110) — **RVB desbloqueado**. Verificado no código (C-04).
- [x] **Decisão do Vitor:** registry **permanece estático** (classe Python + deploy) por ora. Tipo novo = deploy. Declarativo (schema em banco) vira ADR/backlog futuro — não bloqueia go-live RVB.
- [ ] Documentar a limitação "tipo novo exige deploy" no README de operations.

## Notas
Obsoleto vs. o plano original (que assumia os tipos faltando). Evidência na reconciliação.
