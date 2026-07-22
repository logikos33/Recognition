---
title: "Dashboard INTEGRADO no Recognition: observabilidade de modelos (métricas de treino) + telemetria do edge ao vivo"
pr_title: "feat(platform): dashboard de observabilidade de modelos + telemetria do edge"
commit_message: "feat(platform): Training Studio analytics + telemetria do edge ao vivo no Recognition"
eval: default
risk: security
depende_de: task-099/100 (telemetria edge→Recognition), task-111 (métricas de treino), ADR-0048
bloco: Observabilidade (plataforma)
---

# Task 112 — Dashboard integrado (modelos + edge) no Recognition

## Objetivo
Um dashboard DE VERDADE dentro da plataforma (não HTML descartável), alimentado pelos dados reais do edge e dos treinos.

## Escopo
- **Observabilidade de modelos (Training Studio analytics):** por modelo, curvas por época — precision, recall,
  **mAP@0.5:0.95, mAP_small/medium/large**, box/cls/dfl loss, learning rate. Fonte: o log de treino por modelo (task-111).
  Comparar modelos (curva acurácia×custo) e acompanhar cada treino novo.
- **Telemetria do edge ao vivo:** por device/site — GPU/DLA/EMC, temps (todos os sensores), potência (rails VDD_*),
  fan PWM/RPM, RAM, FPS/stream por módulo, drops, latência. Fonte: ingest de telemetria (task-099/100) via edge-sync.
- Integrado ao Recognition (React + `api.ts` + envelope {status,data}); tenant/site-scoped (cross-tenant → 404).
  Reusar SocketIO pra ao vivo. Sem raw fetch novo.

## Aceite
- [ ] Dentro da plataforma: analytics de treino por modelo + telemetria do edge ao vivo, com dados reais, tenant-scoped.

## Checkpoint
- STOP-for-review. Depende do ingest (099/100) e do log de métricas de treino (111).
