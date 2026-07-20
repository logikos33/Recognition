---
title: "F4 — Modelo pro device: /edge/models/<id>/download + checksum + rollback"
commit_message: "feat(edge): download de modelo por device com checksum + rollback (F4)"
eval: default
risk: security
---

# F4 — Distribuição de modelo ao device

## Objetivo
Trocar o modelo de uma câmera na UI → o modelo chega ao Jetson sem cópia manual.

## Critérios de aceitação
- [ ] `GET /api/v1/edge/models/<model_id>/download` com device auth + escopo `models:download`, URL assinada do R2, checksum.
- [ ] Device valida checksum, guarda versão anterior, **rollback automático** se o engine novo não carregar.
- [ ] Device de outro tenant → 404.

## Invariantes de segurança
- Escopo `models:download` obrigatório. R2 URL assinada de vida curta. Zero AGPL no caminho servido.

## Arquivos no escopo
- `services/api/app/api/v1/edge/**`, `services/edge-sync-agent/app/model_manager.py`
