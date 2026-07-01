---
title: "edge-sync-agent: core lógico (buffer SQLite + uploader backoff + config poller) — testável sem PC"
pr_title: "feat(edge-agent): core — SQLite buffer offline + uploader com backoff + config poller (mocks)"
commit_message: "feat(edge-agent): buffer SQLite, uploader idempotente com backoff, config poller — testado com mocks"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 028 — edge-sync-agent: núcleo lógico (parte da Fase 4 sem hardware)

## Objetivo
Construir a lógica do edge-sync-agent que NÃO depende de hardware: buffer SQLite offline, uploader em batch
com backoff/idempotência (X-Batch-Id), e config poller (puxa cenário/modelo do cloud). MQTT real do DeepStream
e câmera real ficam pra HARDWARE/034. Testável 100% com mocks/synthetic. Ver EDGE_AGENT_ARCHITECTURE + Fase 4.

## Contexto (LER — C-04)
- services/edge-sync-agent/ (SDD.md, AGENT.md scaffold). ADR-0004 (HTTP polling + batch idempotente).
- Endpoints cloud: /edge/heartbeat (002), enroll (004), e os de cenário/modelo (022/025). recognition_shared.

## Conteúdo
- **SQLite buffer:** fila local persistente de eventos (sobrevive a restart); drena ao reconectar; descarta nada (durável).
- **Uploader:** POST batch com X-Batch-Id idempotente + backoff exponencial; reenvio não duplica.
- **Config poller:** GET periódico do cenário/manifesto de modelo do cloud; aplica em memória (sem reiniciar).
- Tudo com cliente HTTP mockado nos testes (sem cloud real, sem MQTT, sem câmera).

## Eval (default)
- buffer persiste e drena na ordem; reenvio de batch (mesmo X-Batch-Id) não duplica (idempotência).
- uploader: backoff cresce em falha; para ao sucesso; não perde evento.
- config poller: aplica nova config/versão sem perder estado.
- ruff + pytest (mocks) verdes.

## Critérios de aceitação
- [ ] buffer durável + uploader idempotente/backoff + config poller, todos testados com mocks (sem hardware).
- [ ] Idempotência de batch comprovada. PR para develop.

## NEEDS CLARIFICATION
- A parte real (MQTT do DeepStream, câmera RTSP) NÃO entra aqui — é HARDWARE/034. Se a fronteira ficar
  ambígua, deixar a integração real como interface/porta a ser plugada depois, e reportar.

## Checkpoint
- Só PR (humano revisa — núcleo do edge). Sem produção. Sem migration. Sem hardware (só lógica + mocks).
