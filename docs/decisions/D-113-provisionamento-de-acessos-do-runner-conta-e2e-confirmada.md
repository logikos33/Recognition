# D-113 · Provisionamento de acessos do runner: conta E2E confirmada, R2 read-only preparado (não criado), beat ausente

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**16/08 · Claude · ✅ verificado no DEV** · *(número D-113: o prompt sugeriu D-112, mas o #386 aberto reivindica D-112 — usei D-113 para não colidir; reconciliar no merge)*

- **Conta de teste JÁ EXISTE — não criei outra.** `e2e-anotacao@recognition.dev` ("E2E Anotacao
  (temporario)", ativa) casa com a variável `E2E_ANNOT_PASSWORD` (serviço API-V3, DEV). **Login
  confirmado** contra `POST /api/auth/login` no DEV via injeção por ENV (senha nunca impressa; só
  `success=true` + token presente). ⚠️ **Achado:** o usuário é **superadmin** (tenant 22222222), não o
  papel mínimo de anotador no RVB que o ideal pede — recomendo o Vitor rebaixar para papel mínimo, mas
  a regra "se existir, não crie outro" prevaleceu (não criei substituto). Falta `E2E_ANNOT_EMAIL` como
  variável (o e-mail não é segredo; runner precisa dele além da senha).
- **R2 read-only: PREPARADO, não criado.** ⛔ Agente não cria credencial de nuvem (acesso auto-concedido).
  Entregue: `docs/runbooks/R2_RO_TOKEN_PROVISION.md` (caminho de 60s — Object Read only, só bucket DEV,
  TTL 90d, cola `R2_RO_ACCESS_KEY`/`R2_RO_SECRET` no ambiente do **runner**, ⛔ não no Railway) +
  `scripts/ops/verify_r2_ro_access.py` (lê ENV, `list_objects_v2 MaxKeys=1`, sem baixar, sem imprimir
  chave; barra reuso do `R2_KEY` read-write). Verificação do R2 fica **pendente** até o Vitor criar o token.
- 🔴 **Beat do reconciler confirmado AUSENTE no DEV** (causa raiz do pod órfão de 43h): `railway_start.py`
  tem `SERVICE_TYPE=beat` como serviço separado (worker **não** usa `-B`, linha 527-529), mas **não há
  serviço `beat`** no projeto DEV (serviços: Frontend, celery-worker, API-V3, Redis, Postgres,
  landing-page). O `SAFE_BEAT_SCHEDULE` agenda `reconcile_runpod_pods` a cada 300s — que **nunca dispara**.
  ⛔ Não provisionei (infra = decisão do Vitor): falta **1 serviço Railway `SERVICE_TYPE=beat`** (mesmo
  repo/branch, réplica única).

*Segredo: nenhum valor de credencial foi impresso em log, relatório ou arquivo nesta rodada.*

<!-- entradas do #384 (aba Classificar) renumeradas para não colidir com a develop; ver notas em cada uma -->
