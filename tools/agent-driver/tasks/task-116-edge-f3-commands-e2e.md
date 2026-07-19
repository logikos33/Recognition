---
title: "F3 — Comandos ponta a ponta: command_poller no main tree + ciclo de vida + idempotência"
commit_message: "feat(edge): command_poller + lifecycle pending→...→done/expired (F3)"
eval: default
risk: security
---

# F3 — Comandos ponta a ponta

## Objetivo
Ações pontuais cloud→edge (restart pipeline, reload modelo, capturar frame, testar câmera).

## Critérios de aceitação
- [ ] `command_poller.py` no main tree (`services/edge-sync-agent/app/`) — hoje só existe em worktree.
- [ ] Ciclo de vida explícito: `pending → acked → running → done|failed|expired`, com TTL (comando sem ack em N min expira).
- [ ] Idempotência por `command_id` (retry pode reentregar).
- [ ] **Decisão registrada:** canal de detecção canônico = `/api/v1/edge/events/ingest`; `/edge/detections` **não** é implementado (uploader aponta para `/events/ingest`).
- [ ] Device auth + escopo `commands:read`/`commands:write` (já entregue pela trilha de segurança).

## Invariantes de segurança
- Comando de outro tenant → 404. Escopo obrigatório por verbo.

## Arquivos no escopo
- `services/edge-sync-agent/app/command_poller.py`, `uploader.py`
- `services/api/app/api/v1/edge_commands/**`
