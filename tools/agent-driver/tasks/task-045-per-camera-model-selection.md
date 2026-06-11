---
title: "Seleção de modelo de reconhecimento POR CÂMERA (usa colunas existentes) — AUTO"
pr_title: "feat(models): seleção de modelo por câmera (model_epi/quality/counting_id) + resolução + UI role-gated"
commit_message: "feat(models): API+front pra escolher modelo por câmera usando colunas existentes + hot-reload Redis"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 045 — Modelo de reconhecimento por câmera · AUTO (SEM migration)

## Objetivo
Permitir que o admin escolha, **por câmera**, qual modelo de reconhecimento ela usa — sobrepondo o default de
tenant×módulo (model-rollout 025). Tudo pelo frontend, role-gated. **NÃO precisa de migration**: o `{schema}.cameras`
**já tem** as colunas `model_epi_id`, `model_quality_id`, `model_counting_id` (ver `create_tenant_schema` / 054).

## Contexto (CONFIRMADO no schema — C-04)
- `{tenant_schema}.cameras` tem `active_module` + `model_epi_id` + `model_quality_id` + `model_counting_id` (UUID, nullable).
- Modelos em `{tenant_schema}.models` (id, module, version, r2_key, active). Default por módulo = model-rollout 025
  (`get_active_model(schema, module)` → `active=TRUE`).
- Hot-reload: já existe `app/api/v1/cameras/model_handlers.py` com Redis `camera:model:{id}` + pub/sub
  `camera:model_change:{id}` — usar como canal de propagação (banco vira a fonte de verdade).

## Comportamento
- **Resolução (lógica central):** modelo efetivo da câmera = `cameras.model_<active_module>_id` se setado,
  **senão** `get_active_model(schema, active_module)` (fallback ao default do módulo). Documentar + testar.
- **API (role admin/superadmin; tenant de get_tenant_schema; C-01):**
  - `GET /api/v1/cameras/<id>/available-models` → modelos do módulo ativo da câmera (de `{schema}.models`).
  - `PUT /api/v1/cameras/<id>/model` (body `{model_id | null}`): valida que o `model_id` existe em `{schema}.models`
    **e** que `model.module == camera.active_module`; grava na coluna `model_<active_module>_id`; **empurra pro Redis**
    (`camera:model:{id}`) + publica `camera:model_change:{id}`. `null` limpa → volta ao default.
  - `GET /api/v1/cameras/<id>/effective-model` → modelo efetivo + flag `inherited|override`.
- **Frontend (role-gated):** no editor de cenário / detalhe da câmera, seletor "Modelo de reconhecimento" mostrando o
  **default herdado** + opção de **override** (dropdown dos modelos do módulo), deixando claro herdado vs override.
  Admin/superadmin edita; operador vê read-only. Estados loading/erro.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/cameras/ (consolidar model_handlers.py: persistir na coluna + Redis), camera repo/service, model_rollout reuse
- apps/frontend (seletor) · tests novos

## Eval (default + harness front 021) — testes (DB real, padrão PR #25)
- set model na câmera → `effective-model` retorna o escolhido; sem set → retorna o `active` do módulo (fallback).
- modelo de outro módulo/tenant → rejeitado (422/404); cross-tenant → 404; sem JWT → 401; role não-admin → 403.
- Redis recebe `camera:model:{id}` + evento ao setar/limpar.
- front: seletor mostra herdado vs override, salva e persiste. ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] Seleção por câmera nas colunas existentes + resolução com fallback + hot-reload Redis + UI role-gated + tenant-scoped; testes verdes. PR para develop.

## Checkpoint
- Só PR (humano revisa — toca seleção de modelo, risk security). SEM migration. SEM produção.
