---
title: "Harness D2: synthetic RTSP + cenários baseline/isolamento (sem GPU)"
pr_title: "test(harness): synthetic RTSP (MediaMTX) + cenários baseline e multi-tenant isolation"
commit_message: "test(harness): MediaMTX synthetic RTSP + cenários 1 (baseline) e 5 (isolamento) sem GPU"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 027 — Harness D2: synthetic RTSP + cenários núcleo

## Objetivo
Antecipar a Fase 9 sem hardware: simular câmera (RTSP sintético) + cloud em containers e validar 2 cenários
núcleo — baseline (evento chega ao cloud) e isolamento multi-tenant. Vira fonte de verdade de edge↔cloud e
fixture de operação. Sem GPU (cenários que exigem GPU ficam pra HARDWARE/032). Ver EDGE_DEPLOYMENT_PLAN §14.

## Contexto (LER — C-04)
- tests/harness/ (já tem migrations/), docker-compose.dev.yml, app/api/v1/edge/*. _helpers_tenant.
- MediaMTX servindo um vídeo loop como RTSP fake.

## Conteúdo
- tests/harness/scenarios/: docker-compose.harness.yml (cloud api+pg+redis + MediaMTX + edge simulado).
- Cenário 1 (baseline): enrollment fake → evento sintético chega ao cloud (< 5s) e aparece via API.
- Cenário 5 (isolamento): 2 tenants; eventos de A não vazam pra B; device token de A em B → 403.
- runner + fault_injection mínimo (derruba rede do edge). Subset rápido no CI; completo sob demanda.

## Eval (default)
- Cenário 1 verde (evento ponta-a-ponta no synthetic). Cenário 5 verde (isolamento + 403).
- roda local (docker) e o subset no CI; ruff + pytest verdes.

## Critérios de aceitação
- [ ] synthetic RTSP sobe; cenários 1 e 5 verdes; subset no CI < 5 min. PR para develop.

## NEEDS CLARIFICATION
- Se o "edge simulado" exigir partes do edge-sync-agent ainda não prontas, mockar o mínimo e reportar o gap (liga com 028).

## Checkpoint
- Só PR (humano revisa — infra de teste/eval). Sem produção. Sem migration. Sem GPU.
