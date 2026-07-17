---
title: "PRÉ-TESTE: avaliação/prontidão do DLA (antes do stress) — caracterizar fallback do YOLOX e decidir GPU-only vs DLA"
pr_title: "feat(edge): avaliação de viabilidade do DLA no Orin (fallback YOLOX + decisão)"
commit_message: "docs(edge): viabilidade DLA + decisão GPU-only vs DLA-augmented"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA (antes do stress 102)
depende_de: task-103 (prontidão), task-084 (benchmark)
relaciona: task-102 (stress), ADR-0044
---

# Task 104 — Prontidão do DLA (decidir antes do stress)

## Objetivo
Resolver a questão do DLA **antes** do stress test, com número na mão em vez de achismo — o DLA pode dobrar a
capacidade de câmeras liberando a GPU, mas só se o modelo for "DLA-clean".

## HONESTIDADE sobre a ordem (dependência do modelo)
O export **DLA-clean do NOSSO modelo depende do modelo treinado (task-101)**. Então esta task = **caracterização
+ decisão AGORA** (com um YOLOX Tiny/Nano de referência); o DLA-clean final é aplicado quando a 101 entregar o
modelo. O stress (102) roda **GPU-only primeiro**; **re-roda com DLA** quando o modelo DLA-clean existir.

## Escopo
- Confirmar toolchain DLA: `trtexec --useDLACore=0 --allowGPUFallback`, 2 núcleos DLA disponíveis.
- **Caracterizar o fallback:** quais camadas da cabeça YOLOX caem pra GPU (as que o DLA não suporta) — com um
  YOLOX Tiny/Nano de referência. Quantificar o custo do fallback (o benchmark já viu DLA 102 vs GPU 310 qps).
- Testar um export "DLA-clean" possível (ou listar as ops que impedem e o que mudaria no modelo/export).
- **Decidir:** stress inicial GPU-only; DLA-augmented vale a pena? (ex.: N cams GPU + M cams DLA).

## Aceite
- [ ] Relatório de viabilidade DLA + **decisão GPU-only vs DLA-augmented** pro stress, + o que falta pro DLA-clean do modelo real.

## Checkpoint
- BLOQUEANTE do stress 102. Hardware.
