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

> **Status:** EM REVISÃO — implementado em `agent/task-091-recorder-onvif-timeline` (PR para develop;
> STOP-for-review, risk:security). `RecorderClient` real em `services/edge-sync-agent/app/`:
> `onvif_recorder_client.py` (ONVIF Profile G, porte spec-compliant de
> `services/api/app/infrastructure/nvr/onvif_client.py`) e `rtsp_timestamp_recorder_client.py` (fallback
> RTSP-com-timestamp dialeto Dahua — protocolo real da RVB/Intelbras, sem índice de timeline verdadeiro,
> limitação documentada, não escondida). `rtsp_validator.py` porta o `RTSPUrlValidator` do monolito;
> `rtsp_clip_stream.py` puxa bytes de uma URL RTSP resolvida via subprocess `ffmpeg` (nova dependência de
> runtime do serviço), sem tocar disco. `recorder_factory.py` resolve protocolo → client a partir de env vars
> locais ao device (`RECORDER_PROTOCOL/HOST/PORT/USERNAME/PASSWORD/CHANNEL_MAP`) — decisão registrada: NÃO usa a
> tabela cloud `public.recorders` (serve outro fluxo, WS-B1/ADR-0034, sem mapeamento câmera→canal e não cabeada
> em `GET /edge/config/poll`). `main.py` (não existia) agora sobe a mini-API de evidência (task-090) com o
> RecorderClient real + `TrustAnchor`. Hikvision ISAPI não foi portado (nenhum cliente RVB usa). 173 testes
> verdes em `services/edge-sync-agent/tests/` (98% cobertura em `app/`), zero erros de lint nos arquivos novos.
> **Sem validação em hardware real** (mesma limitação documentada no `onvif_client.py` do monolito e no
> ADR-0050 da task-090) — ver seção "Security review" no PR.

## Objetivo
Ler a timeline do gravador (ONVIF/RTSP) para localizar e recuperar o trecho de evidência de um evento.

## Escopo
- Descoberta/consulta ONVIF do NVR; mapear evento (timestamp/câmera) → trecho no gravador; integrar ao VST/timeline.

## Aceite
- [ ] Dado um evento, recupera o trecho correto do gravador; testado com NVR real (ou mock + validação on-site).

## Checkpoint
- STOP-for-review. Parte on-site pode ser validada no go-live.
