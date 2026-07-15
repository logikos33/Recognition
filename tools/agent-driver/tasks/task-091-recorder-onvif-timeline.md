---
title: "Recorder-first: índice ONVIF/RTSP da timeline do gravador"
pr_title: "feat(edge): índice ONVIF/RTSP da timeline do gravador para replay/evidência"
commit_message: "feat(edge): timeline do gravador via ONVIF/RTSP"
eval: default
risk: security
depende_de: ADR-0045, ADR-0034
bloco: 5 (Recorder-first)
---

# Task 091 — Índice ONVIF do gravador

## Objetivo
Ler a timeline do gravador (ONVIF/RTSP) para localizar e recuperar o trecho de evidência de um evento.

## Escopo
- Descoberta/consulta ONVIF do NVR; mapear evento (timestamp/câmera) → trecho no gravador; integrar ao VST/timeline.

## Aceite
- [ ] Dado um evento, recupera o trecho correto do gravador; testado com NVR real (ou mock + validação on-site).

## Checkpoint
- STOP-for-review. Parte on-site pode ser validada no go-live.
