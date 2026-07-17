---
title: "Modelos por grupo do cenário RVB multi-módulo (Qualidade/Estacionamento/EPI)"
risk: default
adr: 0053
---

# Task 107 — Modelos por grupo (cenário RVB, ADR-0053)

## Objetivo
Preparar, por grupo de câmeras, o modelo servível (Apache, ONNX→engine TRT) registrado por módulo:

| Grupo | Câmeras | Modelo | Critério |
|---|---|---|---|
| Qualidade principal | 2×4MP | RF-DETR-M/S OU YOLOX-M, alta-res POR ROI | escolher por bench; **mAP_small é o juiz** |
| Qualidade auxiliar | 2×2MP | YOLOX-Nano/Tiny + NvDCF | rastrear peça + cronometrar |
| Estacionamento | 8×2MP | YOLOX-Tiny/Nano (pessoa/veículo) | COCO Apache serve para bootstrap |
| EPI | 16×2MP | YOLOX-S ou Tiny INT8 | já validado (campanha 2026-07-17) |

## Regras
- Treino Apache, export ONNX → engine TensorRT, registrado por módulo ({schema}.models).
- Alta-res por ROI na Qualidade principal = nvdspreprocess com ROIs; NUNCA o frame 4MP inteiro.
- Métricas de treino por época persistidas (JSONL) — ver item 3 do ADR-0053 / task-112.

## Critérios de aceitação
- [ ] Engine pronta e validada (detecções sanas) por grupo, no box real.
- [ ] Licença de cada modelo registrada (trava ADR-0043 addendum).
- [ ] Resultados registrados em docs/edge/CENARIO_RVB_<data>.md.
