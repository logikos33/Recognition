# Roadmap Go-Live RVB — estado reconciliado

> **Reescrito em 2026-07-21** (a versão anterior era de 2026-06-04, numeração 017–037 e falava em "quando o Mini
> PC chegar" — o box já está em campo). **C-04: reconciliar sempre com `git fetch` fresco + `gh` + código real.**
> Detalhe da reconciliação: `docs/edge/GO_LIVE_EXECUCAO_2026-07-21.md`.

## Onde estamos (verificado no código, 2026-07-21)
- **Todo o control plane cloud + edge + segurança + AGPL-zero já está na `develop`.** `develop` = +128/−2 vs
  `staging` (=produção), +134/−3 vs `main`. CI substantivo verde (License gate ✅).
- **Único PR aberto:** #78 (cloud-first evidence storage) — provavelmente **superseded** (a capacidade já está na
  develop via outros PRs); CONFLICTING/DIRTY. Vitor decide fechar/extrair delta.
- **Box RVB (Orin NX):** DeepStream+TensorRT validados; soak co-residência 4.8h **GO** (task-113); 40 cams INT8
  viável; cenário multi-módulo fecha (ADR-0053). Baseline **congelada** JP6.2/DS 7.1 (`REGRAS_PLATAFORMA_JETSON.md §8`).

## O caminho crítico até o go-live (em ordem)

### 1. 🔴 Promoção `develop → staging` — EVENTO PRÓPRIO, gate humano (Vitor)
O coração do go-live: remove o AGPL de produção **e** sobe todo o edge de uma vez. **Não é bloqueado pela migration
052** (mito desmentido — ver GO_LIVE_EXECUCAO §0.1). Plano pronto: `docs/negocio/PLANO_PROMOCAO_DEVELOP_STAGING_2026-07-21.md`.
- Pré-condição real: rotacionar a senha `admin@rvb.com.br` pela app (Bloco 6).

### 2. 🟢 Ponte plataforma↔edge (F0/F1 ✅ feitos) — **4 decisões do Vitor** antes do resto
F0 (device auth) e F1 (`/api/v1/edge/config/poll`) já existem. F2 (fps/quality da config) tem o lado cloud pronto;
a obediência do pipeline é do Bloco 4 (box). As 4 decisões (registry de operation-types; config runtime vs gerada;
`/detections` vs `/events`; enrollment duplo) estão formuladas na GO_LIVE_EXECUCAO §BLOCO 2.

### 3. 🟢 Cenário RVB (operation-types ✅) — motor em produção + Wiser
`attention_points`/`stage_timer` já implementados. Falta: **worker que avalia operações contra o stream de
detecção** e popula `operation_results` fora do `/test` (depende da decisão 2). Wiser = adaptador plugável,
bloqueado no contrato do cliente.

### 4. 🔴 Pipeline de inferência (Jetson) — sudo + credenciais de câmera = Vitor
`deepstream/` vazio; construir pipelines EPI/pátio/qualidade reusando `~/jetson-experiments/mm/` (§6 reuse-first).
Download de modelo pro device (escopo+checksum+rollback). Qualidade: RF-DETR incumbente até o dataset REAL da RVB.

### 5. 🔴 Provisionamento e embarque (task-097) — box/creds
Frontend web no edge, golden image + registry privado (pull por digest), acesso LOCAL+WEB do operador,
fan quiet→cool antes da carga 24/7.

## 🔴 Bloqueantes que o Code NÃO resolve (Vitor/cliente)
1. Senha `admin@rvb.com.br` → trocar **pela app** (código já env-gated; expurgar histórico do git).
2. Promoção develop→staging (gate humano).
3. Fan quiet→cool (sudo).
4. Credenciais das câmeras Intelbras (28).
5. Contrato da API do Wiser (Alexandre).
6. **Pontos de atenção da peça + ponto focal de qualidade** — gargalo do dataset de qualidade (o número final de
   qualidade só vale com dataset REAL).

## Nota de plataforma (não repetir o erro)
Produção roda migrations via **`railway_start.py`** (re-roda TODAS as `infra/migrations/*.sql` a cada deploy,
idempotente, **sem `schema_migrations`**). O `infra/migrations/run_migrations.py` (chaveia por prefixo, PULA
colisões) **não é o runner de produção** — foi a fonte do falso alarme "052 quebra o deploy".
