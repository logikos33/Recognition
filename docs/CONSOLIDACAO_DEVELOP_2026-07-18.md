# Consolidação da develop — 2026-07-18

> **Fonte de verdade:** `git fetch` fresco + `gh` (re-verificado após CADA merge). Vitor autorizou o merge na
> **develop** nesta rodada (inclusive o PR de segurança). **staging e main = GATE HUMANO, não tocados.**

## 🔴 ACHADOS CRÍTICOS (ler primeiro)

1. **AGPL no caminho SERVIDO da `staging` (= PRODUÇÃO) — exposição de licença em ambiente de cliente.**
   A `staging` ainda importa `from ultralytics import YOLO` (AGPL-3.0) **em runtime** no módulo de Qualidade
   servido: `services/api/app/infrastructure/queue/tasks/quality_inference.py:272` (`model = YOLO(model_path) if
   model_path else YOLO("yolov8n.pt")`) e `:552` (gate inspection), + `services/api/app/domain/detectors/ultralytics_compat.py:35`.
   **A `develop` JÁ está limpa** (portada para ONNX/RF-DETR — License gate do CI **verde** na develop). O fix
   existe: é a **promoção `develop→staging`** (traz a remoção do AGPL). Enquanto não promover, produção roda AGPL
   no caminho servido. **Só reportado — não agir (staging = gate humano).**

2. **Colisão de numeração de migration na `develop`: SEIS arquivos no prefixo `052`.**
   `run_migrations.py:60` chaveia por **prefixo numérico** (`version = filename.split("_")[0]`), não pelo nome
   completo → num deploy **FRESH**, só o 1º `052_*` (branding) aplica; os outros **5 são PULADOS** (`052 já
   aplicada`): `camera_fps_quality`, `cameras_retention_days`, `custom_roles`, `events_search_indexes`,
   `model_scenario_config`. O harness passa (migrations idempotentes + não verifica schema completo), por isso
   ficou latente. **Produção NÃO é afetada** — o `main` já renumerou (#159: →077/102/103/104/106). **PORÉM os
   slots do main colidem com os 102-105 que a develop já usa** (frame_annotations/inspection/dashboard) → back-port
   ingênuo do #159 **pioraria**. Precisa de reconciliação deliberada (PR próprio de migration). **PARE e reporte —
   não forcei** (mudança de migration é P0; pré-existente, não introduzida por esta consolidação).

## Pendências do Vitor
1. 🔴 **Senha `admin@rvb.com.br`** commitada no git — rotacionar **pela app** (bloqueante de go-live).
2. ⚠️ **Fan `quiet→cool`** antes da carga 24/7 (sudo, task-097).
3. **Achado crítico 1** (AGPL em staging) — resolve-se com a promoção develop→staging.
4. **Achado crítico 2** (colisão 052) — decidir a reconciliação de migration develop↔main.
5. **#78** — recomendei fechar (superseded); aguarda sua palavra (PR grande).
6. **Promoção `develop→staging`** — evento próprio, com janela + rollback + smoke test. **NÃO nesta rodada.**

## 1. O que ENTROU na develop (merge commit, não squash)

| PR | O que trouxe | CI substantivo | Branch |
|---|---|---|---|
| **#197** | Shootout Qualidade (veredito FINAL: D-FINE-S convergiu, AP_small 0.626>0.565) + housekeeping (ADR 0043→0029, soak reboot/hardening, REGRAS §3.5/§7, higiene/equalização, DIRETRIZ §6.1) | ✅ (só docs) | deletada |
| **#194** | Stack de provisionamento edge: `deployments/edge/*` (install/swap-nvme/sysctl/systemd/pg/redis), `scripts/edge/soak/*`, `seed_rvb_edge.py` (env-gated, sem segredo) — 20 arquivos, delta real ausente na develop | ✅ License/pytest/ruff/tsc/migrations verdes | deletada |
| **#189** | 4 P1 de segurança (verificados ativos na develop): validação de produção morta (config), IDOR cross-tenant câmera, revogação de sessão não-bloqueante, IDOR vídeo/frame — cada um com teste fail-antes/passa-depois | ✅ pytest (inclui os 4 testes de regressão) verde | deletada |

Cada merge foi seguido de **re-fetch + re-verificação** do mergeable dos PRs restantes (regra-mãe).

## 2. O que NÃO entrou

| PR | Decisão | Evidência |
|---|---|---|
| **#112** (7 P1 security) | **FECHADO** (sessão anterior) — superseded por #189 | #189 reverificou seus achados; #112 = 408 commits stale, auth reescrito (HS256→RS256) |
| **#78** (cloud-first storage) | **RECOMENDADO FECHAR — aguarda Vitor** (não fechei sozinho: 50 arquivos) | migrations 050/051 já na develop (que está em 105); `storage/routes.py` + ADR-0051 já na develop; `CONFLICTING/DIRTY`, 3 semanas |

## 3. Health check da develop (pós-consolidação)

- **CI da develop (commit de merge):** License gate ✅ · Lint ruff ✅ · TypeScript ✅ · Frontend ✅ · Migrations
  harness (D1) ✅ · SAST/SBOM/Lockfile ✅ · **Tests (pytest) — rodando** (7min; sem falha até o momento) ·
  **única falha = `SCA (npm audit) (landing)`** = ruído pré-existente (vuln de dep do app landing, não introduzida
  por nenhum merge desta rodada; nenhum PR tocou deps do landing). `gitleaks` falha em todo PR (bug conhecido).
- **Migrations:** harness passa 2× (idempotente), MAS ver **Achado crítico 2** (colisão 052 latente).
- **Consolidação não quebrou a develop:** nenhum dos 3 merges adicionou migration; os gates substantivos seguem verdes.

## 4. Branches deletadas nesta rodada
`claude/rvb-quality-shootout-23564f` (#197), `claude/rvb-edge-soak-memory-indnzg` (#194),
`fix/security-p1-active-vulns` (#189) — via `gh pr merge --delete-branch`. (21 branches mergeadas já haviam sido
limpas na sessão de higiene anterior.)

## 5. Divergência de ambientes (pós-consolidação, medida via compare API)
- **`develop` +119 / −2 vs `staging`** (era +108 antes desta rodada). Os −2 = hotfixes de CI (`ci.yml`
  license-gate) só no staging/main.
- **`develop` +125 / −3 vs `main`.**
- Plano de convergência: `docs/EQUALIZACAO_BRANCHES_2026-07-18.md`. **A promoção develop→staging traz, além das
  features, a REMOÇÃO do AGPL do caminho servido (Achado crítico 1) — é o evento que corrige produção.**
