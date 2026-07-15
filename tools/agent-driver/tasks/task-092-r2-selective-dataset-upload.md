---
title: "Recorder-first: R2 vira upload SELETIVO/diferido para dataset (não toda evidência)"
pr_title: "feat(storage): upload seletivo para R2 (flywheel de dataset), não evidência em tempo real"
commit_message: "feat(storage): R2 seletivo para dataset; evidência fica no gravador"
eval: default
risk: security
depende_de: ADR-0045
bloco: 5 (Recorder-first)
---

# Task 092 — R2 seletivo para dataset

## Status (investigação C-04, 2026-07-15)

**Implementado nesta branch (`agent/task-092-r2-selective-dataset-upload`), PR aberto para `develop`, NÃO mergeado.**

### O que já existia (confirmado por leitura de código, não por memória)

1. **Flywheel de dataset já é seletivo — não duplicado aqui.**
   `services/api/app/infrastructure/queue/tasks/inference.py::_auto_capture_frame`
   (+ `_auto_capture_enabled` / `_auto_capture_daily_cap` / dedup Redis) já sobe
   1 frame por violação pro R2 (`training-images/{tenant}/auto/...`), com
   feature flag por tenant, teto diário (default 20/dia) e debounce — é
   exatamente o "upload seletivo pro flywheel" que o objetivo desta task pede.
   **Cobre só o módulo EPI** (chamado de dentro de `_save_alert`). Módulos
   Quality/Counting não têm equivalente — fora de escopo aqui (não inventado).

2. **O padrão "empurra tudo pro R2" que a ADR-0045 supersede vive em
   `services/api/app/infrastructure/queue/tasks/quality_clips.py`:**
   - `generate_quality_clip`: sobe um clip de 60s (`quality-clips/{tenant}/{camera}/{inspection}.mp4`)
     pra **TODA** inspeção NOK, sem seleção.
   - `capture_reference_snapshot`: sobe um snapshot (`quality-snapshots/...`)
     pro **primeiro OK de todo lote**, sem seleção.
   - Consumidos pela UI: `apps/frontend/src/modules/quality/pages/QualityInspectionDetail.tsx`
     → `ClipPlayer.tsx` (player de vídeo a partir de `clip_r2_key`/`clip_status`).

3. **`edge-sync-agent/app/uploader.py` NUNCA subiu evidência bruta** — só
   faz POST de lotes de detecções JSON (`/api/v1/edge/detections`), nunca
   toca R2/clipes/frames. A frase do escopo "ajustar o edge-sync-agent pro
   novo alvo" já estava satisfeita antes desta task; **nenhuma mudança feita
   nele** (confirmado por leitura, não presumido).

4. **`DEPLOYMENT_MODE` já existe, mas não como env var global** — é a coluna
   `public.edge_sites.deployment_mode` (`'cloud' | 'edge' | 'hybrid'`, task-003/016/017),
   por site do tenant. Já é usado para decidir comportamento por câmera em
   `services/api/app/api/v1/cameras/stream_handlers.py::stream_info` (dual-mode
   HLS via `public.cameras.site_id` → `EdgeSiteRepository.get_site_by_id`).
   **Porém não está conectado ao módulo Quality**: `quality_inspections` e
   `quality_recording_segments` têm coluna `site_id` (migration 054) mas ela
   **nunca é populada** em nenhum INSERT hoje, e `{tenant_schema}.cameras`
   (usada pelas queries do módulo Quality via `SET search_path`) **não tem
   coluna `site_id`** — é uma tabela diferente de `public.cameras` (que tem
   site_id e é usada pelo streaming EPI). Duas tabelas `cameras` coexistindo
   é uma inconsistência arquitetural real, fora do escopo desta task para corrigir.

### Decisão tomada

Gate por **tenant inteiro** (não por câmera/site individual, pela limitação
acima), em `quality_clips.py::_should_upload_evidence_to_r2`, ordem de decisão:
1. Feature flag explícita do tenant `quality_evidence_r2_upload_enabled`
   (tenants.feature_flags JSONB — mesmo padrão de `_auto_capture_enabled`/task-086)
   — override manual.
2. Se ausente: qualquer `edge_sites.deployment_mode='edge'` do tenant desliga
   o upload automático (evidência já disponível via mini-API task-090 + índice
   ONVIF task-091).
3. Fail-safe (ADR-0017): tenant não resolvido, erro de leitura, ou nenhum site
   `edge` cadastrado → **mantém upload** (comportamento atual, cloud_only-safe).
   Perder custo é reversível; perder evidência não é.

`clip_status` ao pular por gate = `'unavailable'` (reutiliza valor existente do
enum fechado do frontend — `apps/frontend/src/modules/quality/types/quality.ts::ClipStatus`
— para não quebrar a UI sem tocar contrato/tipos do front; ver comentário no código).

### Dependência real documentada para task-093/094 ("Deployment modes configuráveis")

- Formalizar `DEPLOYMENT_MODE` ponta-a-ponta (hoje só existe como coluna por
  site em `public.edge_sites`, sem propagação pro módulo Quality).
- Popular `quality_inspections.site_id`/`quality_recording_segments.site_id`
  (ou dar a `{tenant_schema}.cameras` uma coluna `site_id`) para permitir gate
  por câmera/site em vez de por tenant inteiro.
- Considerar unificar `public.cameras` (streaming/EPI, com site_id) e
  `{tenant_schema}.cameras` (Quality/Counting, sem site_id) — duas tabelas
  `cameras` divergentes é dívida arquitetural pré-existente, não criada por
  esta task.
- Wiring da UI de Quality para consumir a mini-API local (task-090/091) quando
  `clip_status='unavailable'` mas o tenant é `deployment_mode='edge'` — hoje a
  UI só mostra "Clipe não disponível para esta inspeção.", sem link pro
  gravador local.

## Objetivo
Parar de empurrar toda evidência pro R2; subir só o que alimenta o flywheel de dataset da Logikos, de forma diferida.

## Escopo
- Política de seleção (amostragem/curadoria) do que vai pro R2; upload diferido (não por evento).
- Ajustar o edge-sync-agent para o novo alvo (dataset, não evidência).

## Aceite
- [x] Evidência não vai mais em massa pro R2 (para tenants `deployment_mode='edge'`); upload
      seletivo comprovado via testes (`test_quality_clips_evidence_gate.py`, 15 casos); custo de
      nuvem reduzido — mudança de comportamento esperada: de 1 upload de clip (~60s de vídeo) por
      inspeção NOK + 1 snapshot por primeiro-OK-de-lote, para 0 uploads automáticos por evento
      quando `edge` (evidência fica no gravador local). Tenants `cloud_only`/sem site cadastrado
      mantêm o comportamento atual sem regressão (fail-safe).

## Checkpoint
- STOP-for-review.
