---
title: "PRIORITÁRIA: validar RF-DETR no MESMO teste (treino + stress 28 cams) — bench head-to-head vs YOLOX"
pr_title: "feat(edge): RF-DETR no mesmo pipeline (treino + stress) + bench vs YOLOX"
commit_message: "feat(edge): experimento RF-DETR (treino/stress/bench) comparável ao YOLOX"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA
depende_de: task-101 (YOLOX baseline), task-102 (stress), task-104 (DLA), ADR-0044
---

# Task 105 — RF-DETR no mesmo teste (bench comparável ao YOLOX)

## Objetivo
Rodar o **RF-DETR** (Apache, alvo de acurácia do ADR-0044) pelo **mesmo pipeline** que o YOLOX passou (treino no
Jetson → export ONNX → DeepStream → stress 28 câmeras), com as **mesmas métricas**, pra o **bench head-to-head**
e a decisão RF-DETR vs YOLOX-S com número na mão.

## Escopo (espelhar 101+102, trocando o detector)
- **Mesmo dataset** (SiaBar PPE, COCO) e **mesmas condições** do YOLOX (mesmas épocas/resolução onde fizer sentido) pra comparabilidade.
- Treinar **RF-DETR** (variante leve — ex. RF-DETR-Nano/S) no Jetson; MEDIR wall-clock/img-s/RAM/potência (telemetria 100).
  Nota honesta: RF-DETR é transformer, **mais pesado** — treino tende a ser bem mais lento que os 8min do YOLOX-Tiny; se
  inviável no box, treinar off-box e registrar (mas tentar no Jetson pro número comparável).
- **Parser DeepStream próprio do RF-DETR** (o parser YOLOX da 088 NÃO serve — saída DETR é diferente).
- Export ONNX → TensorRT; rodar o **stress 28 câmeras** igual à 102 (substream, GPU-only, telemetria + mosaico na tela).
- Reavaliar **DLA** pro grafo RF-DETR (transformers costumam ter fallback ainda pior — caracterizar).

## Aceite
- [ ] Tabela **bench comparável**: RF-DETR vs YOLOX em treino (tempo), acurácia (AP), inferência (qps/latência), 28-cam (FPS/GPU/potência), DLA.
- [ ] Recomendação: RF-DETR (acurácia) vs YOLOX-S (throughput) pra produção EPI, com dados.
- [ ] Renderizado na tela do box; zero AGPL.

## Checkpoint
- BLOQUEADA-HARDWARE. Roda depois do YOLOX (101/102) pra ser comparável.
