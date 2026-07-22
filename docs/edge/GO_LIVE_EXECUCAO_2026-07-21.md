# Execução Go-Live RVB — reconciliação por blocos (2026-07-21)

> Execução autônoma a partir de `origin/develop` (fetch fresco). **Nada promovido** para staging/main.
> C-04: tudo abaixo foi verificado no **código real**, não em cache/memória/docs. Onde o plano divergiu do
> código, **o código venceu** e o item foi marcado OBSOLETO com evidência.

---

## 🔴 BLOCO 6 — PENDÊNCIAS DO VITOR / CLIENTE (topo, o Code NÃO resolve)

1. **Senha `admin@rvb.com.br`** — trocar **pela aplicação** (nunca shell/SQL). O código já está limpo
   (`scripts/seed_rvb.py` é env-gated: exige `RVB_SEED_ENABLED=true` + `RVB_ADMIN_PASSWORD`, sem default), mas
   o segredo exposto no histórico do git é imutável → rotacionar + avaliar expurgo do histórico. **Bloqueante.**
2. **Promoção `develop→staging`** (+128 commits) — **EVENTO PRÓPRIO**, gate humano. Plano pronto em
   `docs/negocio/PLANO_PROMOCAO_DEVELOP_STAGING_2026-07-21.md`. É o que **remove o AGPL de produção**. NÃO feito aqui.
3. **Fan `quiet→cool`** antes da carga 24/7 no Orin (sudo do Vitor; comando em `REGRAS_PLATAFORMA_JETSON.md §7`).
4. **Credenciais das câmeras Intelbras** (28) — insumo do provisionamento (Bloco 5).
5. **Contrato da API do Wiser/monofatura** — ponto focal Alexandre. Adaptador fica plugável; não trava o resto.
6. **Lista dos pontos de atenção da peça + ponto focal de qualidade** — **gargalo do dataset de qualidade**
   (o número final de qualidade só vale com o dataset REAL da RVB).
7. **As 4 decisões do Bloco 2** (abaixo) — precisam do Vitor antes de mexer na ponte.

---

## PASSO ZERO — a verdade reconciliada (código, 2026-07-21)

`git fetch --all --prune` + `gh`. `develop` HEAD = `ae051735`.

| Afirmação do plano/STATUS | Verificação no código | Veredito |
|---|---|---|
| develop +128/−2 vs staging, +134/−3 vs main | `gh api compare` | ✅ confirmado |
| Só **#78** aberto | `gh pr list --state open` | ✅ confirmado (CONFLICTING/DIRTY) |
| AGPL vivo em staging | `git grep origin/staging` → `quality_inference.py:272,552`, `quality_training.py:218`, `ultralytics_compat.py:35` | ✅ confirmado |
| develop AGPL-limpa | License gate CI = **success**; hits em develop são só comentários históricos | ✅ confirmado |
| **F0** bug device auth (edge_commands/edge_events passa `request` como token) | `@require_device_scope` decorator; `/heartbeat` faz `removeprefix("Bearer ")`; commit `ae295c96` + PR #199 | ✅ **JÁ CORRIGIDO** |
| **F1** `GET /api/v1/edge/config/poll` | `edge/routes.py:223` (ETag/304, config_version, escopo `config:read`); PR #200 | ✅ **JÁ EXISTE** |
| **F2** fps/quality lidos da config | `camera_repository.list_for_site_config` serve `fps_target/quality_preset/module_code`; `update_camera_config`; servido no config/poll | ⚠️ **cloud/dados PRONTO**; obediência do pipeline = Bloco 4 (edge) |
| **Bloco 3** `attention_points` + `stage_timer` | `domain/services/operations/canonical/attention_points.py` + `stage_timer.py` (com `type_id`), + `epi_zone/defect_trigger/counting_line` | ✅ **JÁ EXISTEM** |
| **Bloco 3** motor de operações popula `operation_results` fora do /test | `operation_repository.py:155` INSERT; `evaluate()` chamado em `operations/routes.py:223` (rota) — **worker de stream que popula em produção NÃO confirmado** | ⚠️ parcial — ver Bloco 3 |
| **S1/S2/S3** segurança edge | PR #199 (escopos device S1-S7); S2 = `core/playback_token.py` (task-068); S3 = `modules/routes.py:81-95` (`modules:write`+404, task-073) | ✅ **JÁ CORRIGIDO** |
| **Migration 052** colisão → 5 puladas em deploy fresh, quebra schema | **FALSO em produção** — ver BLOCO 0 | ❌ **OBSOLETO** |
| docs `PLANO_*`, ADR-0054, `STATUS_GO_LIVE_RVB`, `tools/agent-driver/tasks/*-PROMPT` | não existem no repo (working tree nem git) | ❌ **AUSENTES** |

**Resumo:** Blocos **1, 2 (F0/F1), e a maior parte do 3 já estão na develop.** O que o plano pintou como o grande
trabalho autônomo (renumerar a migration 052) **está baseado em premissa falsa**. O go-live real é dominado pela
**promoção develop→staging** (gate humano) — que **não é bloqueada** pela migration 052.

---

## BLOCO 0 — destravar a promoção

### 0.1 Migration 052 — ❌ PREMISSA OBSOLETA, renumeração NÃO feita (com evidência)

O plano diz: "6 arquivos `052_*`; `run_migrations` chaveia por prefixo → num deploy fresh, 5 migrations são
PULADAS; sem reconciliar, promover a staging quebra o schema." **Isso não vale para produção.**

**Evidência (C-04):**
- A produção roda migrations por **`railway_start.py::run_migrations()`** (`nixpacks.toml [start] cmd =
  "python3 railway_start.py"`; chamada em `railway_start.py:556`). Essa função (linhas 56-91):
  - dá `glob('infra/migrations/*.sql')` **sorted** e **executa TODO arquivo em TODO deploy**;
  - **NÃO usa `schema_migrations`**, não chaveia por versão/prefixo, não pula nada;
  - erro "already exists"/"duplicate" → loga "já existe (OK)" e segue (redeploy idempotente).
- Ou seja, em staging/produção **os 6 arquivos `052_*` rodam todos, sempre.** Nenhum é pulado.
- O runner que chaveia por prefixo (`infra/migrations/run_migrations.py`, `version = filename.split("_")[0]`)
  **não é invocado por nenhum caminho de deploy/CI/Procfile/nixpacks** — é script solto/legado. A única
  referência é um trecho **stale** em `services/api/app/infrastructure/AGENTS.md:655` apontando para um caminho
  que nem existe (`app.infrastructure.database.migrations.run_migrations`).
- O harness (`tests/harness/migrations/runner.py:10`) diz textualmente: *"NÃO usa schema_migrations — fiel à
  produção que re-roda tudo a cada deploy"* — confirmando o comportamento real do `railway_start`.
- Os 6 arquivos `052_*` são **todos idempotentes** (`ADD COLUMN/CREATE TABLE/CREATE INDEX IF NOT EXISTS`, zero
  DROP) → re-rodar é no-op. (ADR-0021, o incidente que derrubou startup, foi colisão **não-idempotente**, caso
  diferente.)

**Conclusão:** renumerar os 052 **não é bloqueador de go-live** e seria churn sobre um não-bug. **Não renumerei.**
**Boa notícia p/ o go-live:** um bloqueador que se acreditava existir **não existe** — a promoção aplica os 6 `052`
(e tudo até 105) idempotentemente.

**Higiene opcional (não-bloqueante, recomendada p/ parar de enganar futuras sessões):** o script morto
`infra/migrations/run_migrations.py` é a **raiz** da crença falsa "052 quebra deploy" (docs CONSOLIDACAO/HANDOFF
leram ele achando que era produção). Sugestão: alinhá-lo ao comportamento do `railway_start` **ou** deletá-lo +
corrigir o trecho de `AGENTS.md:655`. Fica como PR próprio de higiene, se o Vitor quiser.

### 0.2 `docs/ROADMAP_GO_LIVE.md` — ✅ reescrito com o estado reconciliado (era de 2026-06-04, numeração antiga).

### 0.3 Plano de promoção `develop→staging` — ✅ preparado (não executado):
`docs/negocio/PLANO_PROMOCAO_DEVELOP_STAGING_2026-07-21.md` (janela + rollback + smoke test). Execução = Vitor.

---

## BLOCO 1 — higiene e segurança → ✅ JÁ NA DEVELOP

- Consolidação: só **#78** aberto (CONFLICTING/DIRTY, +4181/−656, stale 2026-07-19). Sua capacidade
  (presigned upload/download + R2 + `evidence_r2_key`) **já está na develop** via outros PRs
  (`r2_storage.generate_presigned_upload_url/download_url`, `quality .../evidence-url`, `edge_events.evidence_r2_key`).
  **Recomendação: fechar como superseded** (delta residual, se houver, em 4181 linhas → Vitor decide). Não fechei
  unilateralmente um PR desse tamanho.
- Segurança edge S1-S7: **PR #199 mergeado** (escopos de device aplicados via `require_device_scope`;
  cross-tenant→404). **S1** (escopos), **S2** e **S3** confirmados corrigidos no código:
  - **S2 (`serve_hls`)**: ✅ endereçado por `app/core/playback_token.py` (task-068). HLS é público por design
    (hls.js não manda header de auth) → usa **playback token assinado** (`/api/cameras/<id>/stream/s/<token>/`)
    com gate de tenant (`should_enforce_tenant`). `.ts`/`.m3u8` isentos de JWT via `middleware._ROUTINE_STREAM_PATH`.
  - **S3 (`toggle_module_class`)**: ✅ `modules/routes.py:81-95` — `modules:write` + 404 cross-tenant (task-073).
- Senha do admin → Bloco 6.

## BLOCO 2 — a ponte plataforma↔edge → F0/F1 ✅, F2 cloud ✅ / edge pendente; **4 DECISÕES PARA O VITOR**

F0 e F1 já existem (ver Passo Zero). F2 tem o lado cloud pronto (config/poll serve `fps_target/quality_preset`);
falta a **obediência do pipeline** (DeepStream lê a config e muda o FPS) — isso é **Bloco 4**, roda no Jetson.
A frase de aceite *"operador muda o FPS na UI → pipeline obedece em ≤1 poll"* **só pode ser provada no box** (Bloco 4).

**PARE E PERGUNTE — 4 decisões (não decididas por mim):**
1. **Registry de operation-types:** declarativo (mecanismo de registro em runtime) **ou** estático (classe +
   deploy)? Já existem as classes canônicas (`attention_points`, `stage_timer`, `epi_zone`, `defect_trigger`,
   `counting_line`) — a decisão define se novos tipos entram por dado ou por código.
2. **DeepStream config:** o pipeline lê a config **em runtime** (poll) ou o edge **gera o pipeline do banco**?
   Muda quem é dono da verdade da config e como o F2 fecha no Bloco 4.
3. **`/detections` vs `/events`:** o canônico de ingestão é `/api/v1/edge/events/ingest` (existe, com dedup).
   `/detections` **não existe** — confirmar que fica assim (uploader aponta p/ `/events`).
4. **Enrollment duplo:** hoje o device **auto-assina** (ADR-0019 S7); há intenção de um segundo fator/rotação
   (`/auth/rotate` está no backlog, não existe). Decidir se entra antes do go-live.

## BLOCO 3 — cenário RVB → operation-types ✅; motor em produção ⚠️; Wiser plugável (pendente contrato)

- `attention_points` + `stage_timer`: **já implementados** (canonical/). Item 1 do bloco = feito.
- **Motor de operações em produção:** `operation_repository` grava `operation_results` e `evaluate()` roda na
  rota `/operations`. **Não confirmei** um worker/consumer que avalie operações contra o *stream de detecção*
  fora do `/test` — depende da decisão 2 do Bloco 2 (runtime vs geração). **Registrar, não construir às cegas.**
- **Wiser/monofatura:** adaptador plugável + simulação em teste — bloqueado no contrato do cliente (Bloco 6.5).

## BLOCO 4 — pipeline de inferência (Jetson) → ⏸️ PARA (sudo + credenciais = Vitor)

`deepstream/` tem só `.gitkeep`. Construir os pipelines EPI/pátio/qualidade depende da **decisão 2 do Bloco 2**
(gerar do banco vs runtime), de **credenciais de câmera** e de **acesso ao box com sudo** → tudo Bloco 6.
Reuse-first: os artefatos do box (`~/jetson-experiments/mm/`, engines, parsers, MediaMTX) são a base (§6 do doc vivo).
Modelo de qualidade: **RF-DETR segue incumbente servido** (D-FINE-S venceu em dataset PROXY; final só com dataset REAL).

## BLOCO 5 — provisionamento (task-097) → ⏸️ depende do box/creds

Frontend web no edge (soak foi API-only), golden image + registry privado (build de ~10GB no cliente é inviável —
pull por digest), acesso LOCAL+WEB do operador. Reforços da checklist já refletidos em `REGRAS_PLATAFORMA_JETSON.md`.

**🔒 Item OBRIGATÓRIO do provisionamento — admin com e-mail VÁLIDO do responsável (lição 2026-07-21).**
Em produção **não há re-seed**: se o admin for criado com e-mail que o cliente não controla, a recuperação de senha
por e-mail nunca funciona e o acesso fica irrecuperável sem intervenção manual no banco. Aconteceu em **dev** (admin
`admin@rvb.com.br` com e-mail inválido → recuperação quebrada). Regra para o provisionamento RVB (prod):
- Criar o admin do tenant com o **e-mail real do responsável** (Jonas/Odirlei), não um placeholder.
- Mecanismo padrão: `RVB_ADMIN_EMAIL` no `scripts/seed_rvb.py` (já env-gated; normalizado `strip+lower` no PR #218 —
  o `get_by_email` do dev é case-sensitive, e-mail com case misto nunca loga).
- Escopo: este é o admin do **tenant** RVB (não super-admin de plataforma — papel separado, pendência).

---

## Health check

Esta rodada **não tocou código** (só documentação) — não há teste a rodar. A validação foi de **estado do repo**
(git/gh/código), toda read-only. Nenhuma migration criada/alterada.

## Aprendizado de plataforma (para o doc vivo)

O aprendizado desta sessão é de **plataforma de deploy**, não de Jetson: *a produção roda migrations via
`railway_start.py` (re-roda tudo, idempotente, sem `schema_migrations`); o `infra/migrations/run_migrations.py`
NÃO é o runner de produção.* Registrado aqui e no ROADMAP; não polui o `REGRAS_PLATAFORMA_JETSON.md` (Jetson).
