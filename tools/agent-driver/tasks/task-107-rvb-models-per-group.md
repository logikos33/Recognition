---
title: "RVB multi-módulo: modelos por grupo de câmera (qualidade alta-res / auxiliar / estacionamento / EPI)"
pr_title: "feat(models): modelos por grupo de câmera do cenário RVB (3 módulos)"
commit_message: "feat(models): seleção/treino de modelos por grupo — qualidade/estacionamento/EPI"
eval: default
risk: security
depende_de: ADR-0048, ADR-0044, task-045 (modelo por câmera), task-105/106 (bench)
bloco: RVB multi-módulo
---

# Task 107 — Modelos por grupo (cenário RVB)

## Objetivo
Definir e preparar os modelos dos 3 módulos que rodam juntos no edge da RVB (28 câmeras).

## Escopo
- **Qualidade principal (2×4MP):** RF-DETR-M/S ou YOLOX-M **alta-res por ROI** — escolher por bench (mAP_small é o juiz).
- **Qualidade auxiliar (2×2MP):** YOLOX-Nano/Tiny + NvDCF (só rastrear a peça + cronometrar).
- **Estacionamento (8×2MP):** YOLOX-Tiny/Nano (pessoa/veículo).
- **EPI (16×2MP):** YOLOX-S ou YOLOX-Tiny INT8 (já validado).
- Cada modelo: treino Apache (zero ultralytics), export ONNX → engine, registrado no registry por módulo.
- **Config por câmera reusa o EXISTENTE:** `active_module` + `model_<módulo>_id` (task-045). NÃO criar roteamento novo.

## Aceite
- [ ] Um modelo por grupo, treinado/exportado, atribuível por câmera na UI; escolha justificada por bench.

## Checkpoint
- STOP-for-review. Inputs do cliente (pontos de atenção da peça) entram na 109.
