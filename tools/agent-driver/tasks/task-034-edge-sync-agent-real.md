---
title: "edge-sync-agent integração real (MQTT DeepStream + câmera + drain) — Fase 4 real"
pr_title: "feat(edge-agent): integração real — MQTT do DeepStream, câmera RTSP, drain offline→cloud"
commit_message: "feat(edge-agent): consumo MQTT real do DeepStream + câmera + drain do buffer pro cloud"
eval: manual-hardware
budget_minutes: 120
risk: security
requires_hardware: true
status: BLOQUEADA-HARDWARE — rodar quando o Mini PC estiver disponível. Fora da queue.txt autônoma.
---

# Tarefa 034 — edge-sync-agent integração real (Fase 4) · BLOQUEADA-HARDWARE

> 🔴 Precisa do PC + câmera. O núcleo lógico (buffer/uploader/poller) já vem testado na task-028 (mocks);
> aqui é plugar o real.

## Objetivo
Ligar o edge-sync-agent (núcleo da 028) ao mundo real: consumir as detecções do DeepStream via MQTT local,
puxar frames RTSP da câmera (com retry-seguro anti-lockout), e drenar o buffer SQLite pro cloud quando online.

## Depende de
- task-028 (núcleo lógico), deepstream (032), edge stack (033), câmera real.

## Escopo (expandir ao desbloquear)
- MQTT consumer (QoS 1) das detecções/alertas do DeepStream; mapear pro schema de eventos (029).
- Câmera RTSP: conexão TCP, MTU correto, reconnect/backoff; em falha de auth → para e alerta (anti-lockout).
- Drain offline→online: cloud cai → buffer; volta → drena em ordem, zero perda (cenário 2 da Fase 9, agora real).

## Eval (manual-hardware)
- No PC: detecção real do DeepStream → MQTT → buffer → cloud; offline 1h → drain sem perda.

## Critérios de aceitação
- [ ] Integração real validada no PC; zero perda no drain; retry-seguro anti-lockout na câmera.

## Checkpoint
- HARDWARE. Validação humana no PC.
