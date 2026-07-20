---
title: "F1 — A ponte: config/poll versionado (ETag/304) + enriquecer com composer"
commit_message: "feat(edge): versionamento ETag/304 no /config/poll (F1)"
eval: default
risk: security
---

# F1 — A ponte config/poll

## NEEDS CLARIFICATION
Nenhuma.

## Objetivo
`GET /api/v1/edge/config/poll` entrega a config do site ao Jetson por pull, versionada, sem restart.

## Critérios de aceitação
- [x] `config_version` + header `ETag`; `If-None-Match` → **304** quando nada mudou (sem migration — hash de conteúdo). *(feito neste PR)*
- [x] Cliente `config_poller.py`: envia `If-None-Match`, trata 304 (mantém última config boa), grava ETag só após aplicar; intervalo 45s. *(feito neste PR)*
- [ ] **RESTANTE:** enriquecer o payload reusando o composer de `scenarios/routes.py` (câmera + módulos + classes + operações + regras + agenda) — hoje `/config/poll` só devolve câmeras. Extrair `compose_camera_scenario(tenant_id, camera_id)` para um service e iterar as câmeras do site com escopo do device. **Revisar C-05** (nunca vazar credenciais no payload enriquecido).
- [ ] Eval `default` verde.

## Invariantes de segurança
- Escopo site/tenant vem do enrollment (C-01). Payload nunca inclui `username`/`password_encrypted` (C-05).
- Device de outro tenant → 404.

## Arquivos no escopo
- `services/api/app/api/v1/edge/routes.py`
- `services/edge-sync-agent/app/config_poller.py`
- `services/api/app/domain/services/` (novo composer service, na parte RESTANTE)
- `services/api/tests/unit/test_edge_config_poll.py`, `services/edge-sync-agent/tests/test_config_poller.py`

## Frase de aceite
"O operador muda a config do site na UI → em ≤1 ciclo de poll (≤45s) o Jetson recebe a nova
`config_version`; se nada mudou, 304 (sem repassar 28×payload)."
