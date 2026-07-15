---
title: "Plug-and-play: descoberta de câmeras por ONVIF/DHCP (sem IP hard-coded)"
pr_title: "feat(cameras): descoberta ONVIF/DHCP das câmeras no edge"
commit_message: "feat(cameras): auto-descoberta ONVIF das câmeras atrás do MikroTik"
eval: default
risk: security
depende_de: task-095
bloco: 7 (Portabilidade de rede)
---

# Task 096 — Descoberta ONVIF/DHCP

## Objetivo
Descobrir câmeras por ONVIF/DHCP no subnet isolado, sem depender de IP fixo — chave para a portabilidade.

## Escopo
- Scan ONVIF no subnet de câmera; associar às câmeras cadastradas; validar via RTSPUrlValidator antes do FFmpeg/DeepStream.

## Aceite
- [ ] Câmeras descobertas automaticamente no subnet; mapeadas ao cadastro; sem IP hard-coded.

## Checkpoint
- STOP-for-review.
