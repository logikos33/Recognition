---
title: "Inventário de câmeras/edge + onboarding em lote + teste 1-a-1 no painel admin"
pr_title: "feat(admin): inventário de ativos + onboarding em lote + probe por câmera"
commit_message: "feat(admin): inventário de câmeras/devices/sites + import lote + teste por câmera"
risk: security
status: AUTO (parte cloud); validação final de probe contra câmera real é on-site
---

# Tarefa 052 — Inventário de ativos + onboarding em lote + teste 1-a-1 (painel admin)

## Por quê
Padrão de SaaS auto-administrável (ver `docs/architecture/AUTOADMIN_STUDY.md`): operar **na
plataforma**, não no terminal. Hoje não há um inventário unificado nem onboarding/teste de câmera
no painel — substitui a planilha de survey externa e destrava RVB + Roccabela (frota mista
Intelbras + Hikvision) sem ir a campo às cegas.

## Objetivo
Uma tela de **Inventário** no admin onde se vê e gerencia **câmeras + edge devices + sites + modelos**
num só lugar, com **import em lote**, **teste 1-a-1** (probe read-only que não perturba o CFTV) e
**status de conexão/codec/saúde** por ativo.

## Modelo de dados (a "tabela do survey" vira registro no sistema)
Campos por câmera (estender `{schema}.cameras` com `ADD COLUMN IF NOT EXISTS`, aditivo):
`site_id`, `brand` (intelbras/hikvision/other), `model`, `ip`, `rtsp_substream_url`,
`codec_detectado` (h264/h265/h265+...), `substream_ok` (bool), `max_connections` (do survey),
`module` (epi/quality/counting), `last_probe_at`, `probe_status` (ok/fail/pending), `notes`.
(Device edge e site já têm tabelas: edge_sites, device_tokens; expor no inventário.)

## Escopo
### Backend (`services/api/app/api/v1/admin` + cameras)
- `GET /api/v1/admin/inventory` — câmeras+devices+sites+modelos com status, filtrável por tenant/site/brand/status.
- `POST /api/v1/admin/cameras/import` — import em lote (CSV/JSON): cria câmeras em rascunho (não conecta ainda).
- `POST /api/v1/admin/cameras/<id>/probe` — reusa o `/probe` anti-SSRF da task-046; testa **uma** câmera
  (substream), grava `codec_detectado`/`substream_ok`/`probe_status`. **Read-only, não perturba o CFTV.**
- `POST /api/v1/admin/cameras/probe-batch` — testa um lote em paralelo controlado (limite de concorrência;
  respeita max_connections), uma a uma, com resultado por câmera. Nunca "tudo de uma vez" sem limite.
- Tudo filtrado por `tenant_id`; brand/codec por câmera (frota mista). Flag de alerta quando `codec_detectado`
  for H.265+/H.264+ (Hikvision) → orienta trocar pra padrão.

### Frontend (`apps/frontend/src/modules/admin`)
- Página `AdminInventoryPage`: tabela de ativos (filtros), import em lote (upload CSV), botão **Testar**
  por linha + **Testar selecionadas** (lote), badges de status/codec, e link pro diagnóstico do device.
- Reusar `api.ts`; nada de fetch raw.

## Critérios de aceite
- Importar N câmeras em lote, testar 1-a-1 e em lote pelo painel, sem tocar no terminal.
- Probe é read-only (não derruba CFTV); respeita limite de conexões; detecta e sinaliza H.265+/H.264+.
- Isolamento por tenant; frota mista (marca/codec por câmera) suportada.
- Migration aditiva/idempotente para os campos novos; backfill por tenant.
- Testes: import, probe single/batch, isolamento, sinalização de codec proprietário.

## Risco
security — toca ingestão de URL de câmera (anti-SSRF via 046) + isolamento por tenant. Review C2.
