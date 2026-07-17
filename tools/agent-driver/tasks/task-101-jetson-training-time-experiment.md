---
title: "PRIORITÁRIA: experimento — tempo de treino YOLOX-Tiny NO Jetson (dataset PPE público) + telemetria + visualização na tela"
pr_title: "feat(edge): experimento de tempo de treino on-device (YOLOX-Tiny) com telemetria"
commit_message: "feat(edge): mede tempo de treino no Jetson + curvas de telemetria"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA
depende_de: task-087 (baseline), task-100 (telemetria)
relaciona: task-084 (benchmark), task-086 (treino RF-DETR produção), ADR-0044, ADR-0047
---

# Task 101 — Tempo de treino NO Jetson (experimento) + visualização

## Objetivo
Medir **quanto tempo leva treinar um modelo no próprio Jetson** (edge-only), como estudo, e provar o loop
completo **treinar → exportar ONNX → build TensorRT → inferir** num box só. Rodar via SSH em `pandora@100.93.126.76`.

## IMPORTANTE (expectativa)
Treino no Jetson é **experimento**, não produção. É lento (memória unificada 16GB, batch pequeno, teto 40W).
Produção de treino = GPU off-box (task-086). Aqui o objetivo é o **número real** + a curva térmica/energética.

## Escopo
1. **Dataset:** público PPE **"PPE Dataset for Workplace Safety" (SiaBar, Roboflow)** — cobre óculos/luvas/protetor
   auricular. Export **COCO** (YOLOX consome COCO). Download via Roboflow (API key = passo externo, como o NGC foi).
   Simula cenário fabril; sem imagem real de trabalhador (LGPD ok).
2. **Env de treino:** PyTorch para Jetson (wheel L4T/JetPack 6.2) + repo **YOLOX (Apache 2.0 — ZERO ultralytics)**.
3. **Treinar YOLOX-Tiny**, épocas fixas (ex. 30). Medir **wall-clock total, img/s, épocas/hora**, pico de RAM.
4. **Telemetria (task-100) rodando em paralelo** → curva GPU%/temp/potência durante o treino.
5. **Export ONNX → engine TensorRT → inferência de sanidade** (imagem/vídeo do dataset) com o parser custom (088).
6. **VISUALIZAÇÃO NA TELA FÍSICA do Jetson** (o Vitor acompanha): progresso do treino + gráfico de telemetria
   renderizados no monitor HDMI. Usar a sessão gráfica existente: `DISPLAY=:1`,
   `XAUTHORITY=/run/user/1000/gdm/Xauthority` (ver `docs/edge/STATUS_2026-07-16_jetson_handson.md`).

## Aceite
- [ ] Relatório com **tempo de treino real no Jetson** (wall-clock, img/s, épocas/h) + curvas de telemetria.
- [ ] Modelo treinado exporta ONNX e infere (sanidade). Zero ultralytics/AGPL no caminho.
- [ ] Progresso do treino + telemetria **visíveis na tela do Jetson** durante a execução.

## Checkpoint
- BLOQUEADA-HARDWARE (roda no box). `sudo`/instalações que exigem senha → precisam do Vitor presente.
