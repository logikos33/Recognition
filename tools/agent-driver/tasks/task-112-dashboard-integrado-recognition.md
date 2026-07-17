---
title: "Dashboard integrado no Recognition: observabilidade de modelos + telemetria edge ao vivo"
risk: default
adr: 0053
---

# Task 112 — Dashboard integrado (ADR-0053) — não descartável

## Objetivo
Dashboard **DENTRO da plataforma** (React + api.ts, envelope {status,data}, tenant/site-scoped,
SocketIO ao vivo) — NÃO HTML solto:
- **Observabilidade de MODELOS (Training Studio analytics):** curvas por época por modelo
  (precision, recall, mAP@0.5:0.95, mAP_small/medium/large, losses, LR) + comparação entre modelos.
- **Telemetria do EDGE ao vivo:** GPU/DLA/EMC, temps, rails de potência, fan PWM/RPM, RAM,
  FPS/stream **por módulo**, drops, latência (do ingest task-099/100 via edge-sync).

## Regras
- Integrado ponta a ponta: edge captura (JSONL) → sync → Recognition → dashboard com dados REAIS.
- Sem raw fetch novo (usar api.ts); cross-tenant → 404; TypeScript strict.

## Critérios de aceitação
- [ ] Página(s) no frontend consumindo endpoints tenant-scoped reais; tsc/eslint verdes.
- [ ] Curvas de treino renderizadas a partir das métricas persistidas (item 3 / task-107).
- [ ] Telemetria edge ao vivo via SocketIO com dados reais do box.
