---
title: "OpenAPI contract dos endpoints /edge (spec-driven)"
pr_title: "docs(edge): OpenAPI contract de /api/v1/edge em shared/proto"
commit_message: "docs(edge): OpenAPI 3.1 dos endpoints /edge + teste de drift (rota sem doc falha)"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 013 — Contrato OpenAPI dos endpoints /edge

## Objetivo
Documentar formalmente os endpoints /api/v1/edge num arquivo OpenAPI em shared/proto/ (ADR-0009, spec-driven):
o contrato que o edge-sync-agent vai consumir. Inclui um teste de DRIFT que falha se uma rota /edge não
estiver documentada. Sem hardware, sem migration.

## Contexto (LER antes — C-04)
- app/api/v1/edge/routes.py (todas as rotas /edge atuais), recognition_shared (models Heartbeat, DeviceClaims,
  EnrollmentRequest/Response — referenciar nos schemas).
- ADR-0009 (spec-driven OpenAPI/AsyncAPI), shared/proto/ (hoje só .gitkeep).

## Comportamento / conteúdo
- Criar shared/proto/edge-openapi.yaml (OpenAPI 3.1): paths para cada rota /api/v1/edge atual
  (heartbeat, enroll, sites [POST/GET], sites/<id>/enrollment-tokens, e as que existirem no momento — health,
  heartbeats, devices), com request/response schemas, códigos (200/201/401/403/404/409/422) e o esquema de auth
  (bearer device token vs JWT de usuário) por rota.
- Componentes/schemas derivados dos models recognition_shared onde aplicável.

## Teste de drift (o que torna a eval forte)
- services/api/tests/contract/test_openapi_edge.py:
  - YAML válido (yaml.safe_load) e OpenAPI mínimo bem-formado (tem `openapi`, `paths`).
  - Para CADA rota /api/v1/edge/ no app.url_map, existe um path correspondente no OpenAPI (normalizando
    <var> ↔ {var}). Rota não documentada → FALHA o teste (pega drift spec↔código).
  - assert len(rotas descobertas) > 0 (não passar vacuamente se a descoberta vier vazia).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- shared/proto/edge-openapi.yaml (novo)
- services/api/tests/contract/test_openapi_edge.py (novo)
- requirements: pyyaml já é dependência; não adicionar libs pesadas de validação OpenAPI (manter o teste simples).

## Eval (default) — testes SÃO o critério
- YAML válido + OpenAPI bem-formado.
- toda rota /edge do url_map presente no contrato; rota faltando → falha.
- descoberta não-vazia (> 0 rotas).
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] edge-openapi.yaml cobre todas as rotas /edge atuais com schemas e auth por rota.
- [ ] Teste de drift falha se uma rota não estiver documentada; descoberta não-vazia.
- [ ] ruff + pytest + tsc verdes. PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se uma rota tiver schema cujo model em recognition_shared você não achar, documentar o shape lido do
  código (não inventar campos).

## Checkpoint
- Só PR. Sem produção. Sem migration.
