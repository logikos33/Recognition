---
title: "Edge Jetson: integrar VST (Video Storage Toolkit / JPS) para ingest/timeline/streaming"
pr_title: "feat(edge): integração VST (JPS) para ingestão e timeline no edge"
commit_message: "feat(edge): VST do Jetson Platform Services no pipeline de câmera"
eval: manual-hardware
risk: security
requires_hardware: true
depende_de: ADR-0040, ADR-0045
bloco: 4 (Edge Jetson + VST)
---

# Task 089 — Integração VST

## Objetivo
Adotar o VST do JPS para ingestão RTSP, timeline e streaming (WebRTC) no edge, reduzindo stack custom.

## Escopo
- VST como camada de vídeo do edge; avaliar substituição/coexistência com MediaMTX (ADR-0009).
- Alimenta a evidência recorder-first (ADR-0045) e o live view.
- Validar **licença** dos componentes JPS usados (coerência AGPL-zero).

## Aceite
- [ ] Ingestão + timeline + streaming via VST funcionando no box; licença dos componentes verificada.

## Checkpoint
- BLOQUEADA-HARDWARE.
