---
title: "Flywheel de modelo: feedback do operador → curadoria → retrain — melhoria D (migration)"
pr_title: "feat(flywheel): feedback de detecção (errada/certa) + fila de curadoria + gatilho de retrain"
commit_message: "feat(flywheel): detection_feedback + curadoria reusando AnnotationInterface + trigger de retrain/canário"
eval: default
budget_minutes: 90
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; fluxo de migration com checkpoint humano
---

# Tarefa 044 — Flywheel de modelo (active learning) · melhoria D · GATED por migration

## Objetivo
Fazer a acurácia subir com o uso (pesquisa: ~93% real vs ~99% paper). Botão **"isso estava errado/certo"** no
dashboard captura feedback sobre uma detecção → vira amostra rotulada na **AnnotationInterface (já existe)** →
curadoria → **gatilho de retrain** → **canário** (model-rollout 025) → edge. Ver `ARQUITETURA_E_MELHORIAS.md` (D).

## Migration (APENAS aditivo)
- `CREATE TABLE IF NOT EXISTS detection_feedback` (id, tenant_id UUID REFERENCES tenants(id), frame_id, detection_ref,
  verdict, corrected_class, created_by, created_at). Idempotente; sem DROP.

## Comportamento (depois da migration)
- Endpoint pra registrar feedback (JWT; tenant de get_tenant_id; C-01) ligado à evidência (`frames`).
- Feedback alimenta a fila de curadoria/anotação existente (reusar AnnotationInterface — backup antes, testar).
- Gatilho de retrain quando acumula N amostras / por drift; modelo novo entra por **canário** (025), nunca direto.
- Nenhuma escrita afeta o modelo em produção sem passar pelo rollout com pin/canário.

## Arquivos
- infra/migrations/NNN_detection_feedback.sql · endpoint + repo/service de feedback · integração com training/annotation · front (botão) · tests.

## Eval (default) — testes (DB real + harness de front 021)
- registrar feedback grava 1 linha tenant-scoped; cross-tenant → 404; sem JWT → 401.
- feedback entra na fila de curadoria; gatilho de retrain dispara só com N amostras (mock do training).
- front: botão de feedback no dashboard com teste; ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] detection_feedback + captura + curadoria + gatilho de retrain por canário; tenant-scoped; testes verdes.

## Checkpoint
- MIGRATION: eu escrevo a migration, você valida o duplo-boot em staging ANTES do merge. NÃO entra na fila autônoma.
