---
title: "Hardening da câmera: detection_stream + codec + max_auth_failures (migration)"
pr_title: "feat(cameras): campos de hardening (detection_stream/codec/max_auth_failures) + migration"
commit_message: "feat(cameras): ADD COLUMN detection_stream_url/video_codec/max_auth_failures + model/repo/route"
eval: default
budget_minutes: 75
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; fluxo de migration com checkpoint humano
---

# Tarefa 041 — Hardening da câmera (contenção R1/R2/R4) · GATED por migration

## Objetivo
Dar à câmera os campos que o edge precisa pra aplicar as contenções de decode/lockout/banda: a URL da
**sub-stream de detecção**, o **codec** (preferir H.265) e o **teto de tentativas de auth** (anti-lockout).
Aditivo e idempotente; endpoint/edge usam depois. Ver CONTENCAO_RISCOS_ESCALA.md (R1/R2/R4).

## Migration (APENAS aditivo — Migration Protocol do CLAUDE.md)
- `ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS detection_stream_url TEXT;`
- `ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS video_codec TEXT;`  -- 'h264' | 'h265'
- `ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS max_auth_failures INTEGER DEFAULT 5;`
- Idempotente (rodar 2x sem erro). Sem DROP / ALTER TYPE / DELETE.

## Depois da migration (checklist CLAUDE.md)
- model/dataclass (cameras) + repository + service + route + types frontend atualizados.
- `detection_stream_url` validado por RTSPUrlValidator quando setado; tenant-scoped (C-01).
- docs/DATABASE.md atualizado.

## Eval (default) — testes (DB real)
- migration aplica 2x sem erro; CRUD de câmera lê/escreve os campos; RTSPUrlValidator no detection_stream_url.
- tenant-scoped; ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] Migration aditiva idempotente + model/repo/service/route/types + validação de URL; testes verdes.

## Checkpoint
- MIGRATION: eu escrevo, você valida o duplo-boot em staging ANTES do merge. NÃO entra na fila autônoma.
