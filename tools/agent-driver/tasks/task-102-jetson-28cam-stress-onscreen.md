---
title: "PRIORITÁRIA: stress test 28 câmeras no DeepStream com mosaico + telemetria AO VIVO na tela do Jetson"
pr_title: "feat(edge): stress test 28 câmeras com visualização on-screen + telemetria ao vivo"
commit_message: "feat(edge): stress 28 cams no DeepStream + mosaico e telemetria na tela"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA
depende_de: task-088 (pipeline/parser), task-052 (RTSP sintético), task-100 (telemetria), task-084 (benchmark)
relaciona: task-067 (substream), task-095 (rede), ADR-0044
---

# Task 102 — Stress test 28 câmeras + visualização na tela

## Objetivo
Rodar o pipeline com **28 câmeras** e ver o comportamento **em operação real** na tela do Jetson; achar o
**ponto de degradação**. Gera o dataset de dimensionamento real (complementa o benchmark 084).

## Escopo
0. **1 câmera real primeiro (Intelbras):** validar o caminho RTSP real → DeepStream (RTSP típico Intelbras:
   `rtsp://user:senha@IP:554/cam/realmonitor?channel=1&subtype=0`; habilitar ONVIF no web da câmera se preciso).
1. **RTSP sintético (task-052)** replicando stream(s) até **28**. Fases: 4 → 8 → 16 → 28 (achar a curva).
2. **DeepStream** com `nvmultistreamtiler` → **mosaico das 28 na tela física** do Jetson (`DISPLAY=:1`,
   `XAUTHORITY=/run/user/1000/gdm/Xauthority`).
3. **Modelo:** o YOLOX treinado (task-101) ou placeholder, com o parser custom (088). Testar em fases: leve
   (teto) e depois o real (número verdadeiro).
4. **Telemetria (task-100)** capturando + **gráfico AO VIVO na tela**, ao lado do mosaico, pro Vitor acompanhar.
5. **Medir:** FPS sustentado por stream, GPU/DLA%, temperatura, potência, **frames dropados**, latência, RAM.
   Registrar quantas câmeras aguenta no **alvo de FPS/resolução** (definir substream vs full — ver task-067).

## Aceite
- [ ] Mosaico das 28 câmeras + gráfico de telemetria **ao vivo na tela do Jetson**.
- [ ] Relatório do **ponto de degradação** (nº de câmeras x FPS x recursos) — dataset de dimensionamento.
- [ ] 1 câmera Intelbras real validada no pipeline antes do sintético.

## Checkpoint
- BLOQUEADA-HARDWARE (roda no box). Primeiro modelo leve (teto), depois o real.
