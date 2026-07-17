---
title: "Stress test 3 módulos SIMULTÂNEOS no Jetson (28 cams RVB) — PRIORITÁRIO"
risk: default
adr: 0053
---

# Task 111 — Stress 3 módulos juntos (ADR-0053) — PRIORITÁRIO

## Objetivo
Medir o **custo real** dos 3 módulos rodando JUNTOS no Orin NX (28 câmeras RVB):
- Instâncias nvinfer separadas por grupo (Qualidade principal/auxiliar, Estacionamento, EPI),
  cada grupo roteado pro seu modelo. Config ótima da campanha (INT8 + sub-batch + interval +
  NvDCF, headless).
- **Ponto crítico não medido: custo das 2 câmeras 4MP em ALTA-RES por ROI** — medir isolado
  e combinado.
- Medir combinado: GPU/DLA/EMC, temps, potência, **FPS/stream POR MÓDULO**, drops, latência →
  telemetria JSONL **etiquetada por módulo**. Achar o **ponto de saturação** dos 3 juntos.
- Evidência: mosaico + telemetria na tela física (`DISPLAY=:1`).

## Critérios de aceitação
- [ ] Matriz combinada medida (isolado por grupo + 3 juntos) com números crus registrados.
- [ ] Ponto de saturação identificado e documentado.
- [ ] Telemetria JSONL por módulo copiada pro repo; mosaico na tela física fotografado.
- [ ] Resultados em docs/edge/CENARIO_RVB_<data>.md + REGRAS alimentado com landmines novas.
