# HANDOFF — Continuidade do projeto Recognition (nova conta Claude Code)

> **Propósito:** permitir que uma nova sessão/conta retome o projeto EXATAMENTE de onde paramos.
> **Data do handoff:** 2026-07-12 · **Mecanismo de transferência:** o repositório git (tudo commitado).
> A nova conta só precisa de acesso ao repo GitHub — todos os ADRs, tasks, docs e o design estão versionados.

## 0. Como usar este arquivo (ordem de leitura para a nova sessão)

1. Este arquivo (visão geral + estado + próximo passo).
2. `docs/PLANO_EXECUCAO_MIGRACAO_V3.md` — o plano-mestre em 6 fases.
3. **Correções ao `CLAUDE.md`** (seção 2 abaixo) — o CLAUDE.md está DESATUALIZADO; leia isto antes de tocar código.
4. Por tema: contrato (`docs/API_CONTRACT_MAP.md`), migração (`docs/decisions/adr/0041-*` + `docs/design/recognition-v3/*`), pipeline de treino (ADRs 0031/0037/0038/0039).

## 1. Identidade do projeto

**Recognition (EPI Monitor V2)** — SaaS multi-tenant de visão computacional em CFTV. Cada cliente
**treina o próprio modelo** (não é detector fixo). Multi-módulo (EPI/Segurança, Qualidade,
Carga-descarga/Contagem), edge (NVIDIA Jetson Orin NX) + nuvem (Railway) + Cloudflare R2, white-label.
Cliente âncora: **RVB Isolantes** (módulo EPI, ~28 câmeras). Dono: Vitor Emanuel / Logikos.

**Stack:** Flask + psycopg2 (RealDictCursor, SEM ORM) + Celery + Redis + SocketIO · React 18 + TS + Vite
(vanilla-extract) · PostgreSQL · Railway · R2. Detector servido = ONNX (YOLOX/RF-DETR, **Apache 2.0** —
NUNCA ultralytics/AGPL no caminho servido).

## 2. ⚠️ CORREÇÕES CRÍTICAS ao CLAUDE.md (está desatualizado)

- Backend **NÃO** é `backend/app/` → é **`services/api/app/`** (monorepo, ADR-0010).
- Migrations **NÃO** ficam em `backend/.../migrations/` → é **`infra/migrations/`** (últimas: 100
  model_deployments, 101 model_eval_drift).
- Frontend = **`apps/frontend/`**.
- **PRODUÇÃO = branch `staging`** (auto-deploy Railway). **NÃO é `main`.** main = branch estável + gráfico
  de contribuições. develop = trabalho ativo.
- Regra C-04: sempre validar o estado real no código/git, nunca confiar em CLAUDE.md/memória.

## 3. Estado das branches (no momento do handoff)

- **main** `06f5aa7` — sincronizada com develop (merge commit, autoria Vitor preservada). CI verde.
- **staging (PRODUÇÃO)** `786f680` (01/jul) — **desatualizada**; merge de reconciliação `f285e1e` já
  resolvido e verde no worktree `wt-staging-promo`, **aguardando push** (Bloco A do prompt em curso).
- **develop** `761c784` — mais recente; contém tudo (pipeline de treino + 5 correções de segurança +
  contrato). 39 commits órfãos em staging (13 dups / 8 únicos / 18 merges) a portar.
- Disciplina: `develop→staging→main` são gates humanos; merge para main/staging = **merge commit,
  NUNCA squash** (runbook `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`). Trabalho novo em
  **worktree a partir de origin/develop**, nunca no checkout `wip/*`.

## 4. O que está FEITO

- **Pipeline de treinamento completa** (4 PRs mergeados em develop): Fase A (dataset→treino→export ONNX→
  registry, validado E2E com dado real), Fase B (#129: NVR/DVR recorders, active learning, auto-captura
  idempotente, pré-anotação plugável flag OFF), Fase C (#140: campeão×desafiante, deploy/model-config
  por câmera, drift monitor), Compute Providers (#143, ADR-0039: TrainingCompute VastAi/Edge/Local;
  EdgeProvider mock-only, issue #142 p/ validação de hardware).
- **Auditoria de contrato** (task-069, #130): `docs/API_CONTRACT_MAP.md` + `docs/quality/CONTRATO_FRONT_BACK.md`.
- **5 correções de segurança** (task-072..076, mergeadas em develop): seed destrutivo, tenant_id em
  módulos/alertas/verificação, senha de tenant aleatória. **Ainda NÃO em produção** até o push da staging.
- **Design v3 importado** (`docs/design/recognition-v3/Recognition-visao-final.dc.html` = fonte única;
  exports antigos em `_ARQUIVO-NAO-USAR/` quarentena).
- **Validação de cobertura design×contrato**: 61% coberto / 22% parcial / 17% falta
  (`docs/design/recognition-v3/CONTRACT_COVERAGE_VALIDATION.md`).

## 5. PRÓXIMO PASSO IMEDIATO (onde paramos)

Um prompt autônomo de 2 blocos está pronto pra rodar (ver seção 11 — Histórico, último item):
- **Bloco A:** push staging (patcha os 5 vulns em produção) → portar os 8 commits únicos pra develop
  (destrava task-052) → develop→main.
- **Bloco B:** validação de contrato — enumerar o domínio **Quality** (50 rotas, ponto cego), confirmar
  **Fueling→Contagem**, re-rodar a cobertura com as rotas corrigidas, e **surfar** (não decidir) as
  decisões pendentes.

## 6. Decisões PENDENTES do Vitor (destravam a migração)

1. **Os 4 "FALTA que bloqueia"** (cada um: backend novo OU UI "em breve"): Validação de Contagem
   (aceite/rejeição/agregado/threshold — endpoints não existem), clipes de evidência ~20s (ADR-0033),
   pré-anotação IA (flag OFF), verificação segura.
2. **Consolidação de uploads:** `/api/v1/videos/*` (recomendado) vs `/api/training/videos` legado.
3. **Fueling→Contagem:** confirmar se o módulo foi absorvido.
4. **2 lacunas de UI no design** (opcionais antes do cutover): onboarding de device/edge; canais de
   notificação (prompt de Claude Design pronto no histórico).

## 7. Plano-mestre (6 fases — ver PLANO_EXECUCAO_MIGRACAO_V3.md)

`[1] Correções+merges (FEITO)` → `[2] Patch prod (staging) + main (EM CURSO)` → `[3] Validar contrato
FE↔BE (EM CURSO, Bloco B)` → `[4] Migração v3 em develop (tela a tela, gated)` → `[5] Validação final
(inclui E2E do fluxo de treino pela UI nova)` → `[6] Main #2 cutover`.

## 8. Migração v3 — tudo pronto pra Fase 4

- Fonte: `docs/design/recognition-v3/Recognition-visao-final.dc.html` (+ support.js + screenshots).
- ADR-0041 (estratégia: shell paralelo atrás de flag `ui_v3`, tema real charcoal/cyan dark+light +
  accents = white-label, Inter+JetBrains Mono; cutover remove temas antigos preservando white-label).
- task-070 (andaime Fase 0) · task-071 (migração tela a tela, EPI primeiro, com as correções embutidas).
- `docs/design/recognition-v3/MIGRATION_WIRING_SPEC.md` (tela→endpoints) — regra: COBERTO→portar;
  PARCIAL→consertar (envelope {status,data}, path real /api vs /api/v1, dono de rota); FALTA→"em breve".

## 9. Blockers externos (paralelo, do Vitor)

- **VAST_API_KEY** no Railway dev (treino real na nuvem; local fallback funciona sem).
- **Token R2-dev** com escopo `epi-monitor-dev` no Cloudflare (senão treino/evidência cai em LocalStorage).
- **GitHub:** verificar `logikos33@gmail.com` em Settings→Emails + ligar "Include private contributions"
  (senão 417 commits não entram no gráfico).
- Issues de validação de hardware: #131 (NVR/DVR Intelbras), #142 (treino no edge Jetson).

## 10. Disciplinas inegociáveis (constituição operacional)

- Prod = staging; nunca push direto em main sem gate; merge para main/staging = **merge commit, nunca squash**.
- Migrations forward-only (`ADD COLUMN/CREATE ... IF NOT EXISTS`), NUNCA DROP; rodar harness 2x.
- Multi-tenant: toda query filtra `tenant_id`; cross-tenant → 404 (C-01).
- Detector servido = ONNX Apache (YOLOX/RF-DETR); ZERO ultralytics/AGPL no caminho servido.
- `risk:security` PARA a fila pra revisão humana. STOP-for-review ao fim de cada PR grande.
- Antes de implementar: VERIFICAR se já não foi feito (git/gh). Esforço: planejar pode ser alto,
  executar dimensiona por task (nunca sempre o máximo).
- Trabalho novo em worktree a partir de origin/develop, nunca no checkout wip/*.

## 11. Histórico narrativo desta sessão (o "chat" em forma utilizável)

Ordem cronológica do que foi decidido e por quê:
1. **Edge Jetson (ADR-0040):** analisado o Palit Pandora Orin NX Super 16GB + Jetson Platform Services;
   decisão de ancorar o edge em DeepStream (inferência) + VST (câmera/gravação) + DLA; YOLOX preferido
   pro edge (TensorRT maduro).
2. **Pré-anotação (WS-B4):** reaberta como plugável flag OFF (DINO+SAM foi removido em maio/2026 por
   custo×qualidade; histórico registrado no ADR-0031; Jetson Zero-Shot/VLM como candidato futuro).
3. **Contrato FE↔BE:** descoberto que não havia contrato único → task-069 gerou o mapa canônico
   (`API_CONTRACT_MAP.md`), que revelou 15 achados graves incluindo 5+ vulnerabilidades P0 em produção.
4. **Pipeline de treino:** PR-3 (Fase B) revisado e aprovado; PR-4 (Fase C) e PR-5 (compute providers)
   revisados/aprovados com guard-rails (edge = hardware-gated, sem alegar E2E).
5. **Design v3:** importado o handoff do Claude Design; identidade real = charcoal/cyan (não amber);
   exports antigos movidos pra quarentena; fonte única = Recognition-visao-final.dc.html.
6. **Validação de cobertura:** design×contrato = 61/22/17%; ponto cego no domínio Quality (50 rotas não
   mapeadas); Fueling parece ter virado Contagem.
7. **AUTORUN da fila:** 19 tasks — 8 já feitas, 7 corrigidas, 3 bloqueadas; 5 PRs abertos + 5 tasks de
   segurança criadas (072-076).
8. **Sequência de promoção definida pelo Vitor:** corrigir → main → validar contrato → migrar em develop
   → validar (inclui todo o fluxo de treino) → main cutover.
9. **Merges:** 10 PRs mergeados em develop (verde); develop→main FEITO (06f5aa7); develop→staging
   BLOQUEADO por conflito real (staging divergiu — implementações independentes) → merge resolvido
   `f285e1e` (regras: develop vence nos arquivos evoluídos; counting dedup pra develop; CollapsibleSidebar
   combinado — "Sites & Saúde" tinha sido dropado silenciosamente, restaurado). Testes verdes.
10. **Prompt autônomo A+B** montado pra: patchar prod (staging) + convergir develop + main + validar
    contrato (enumerar Quality, confirmar Fueling, re-rodar cobertura, surfar decisões). Migração das
    telas (Fase 4) fica gated tela a tela.

### Prompt autônomo pendente (copiar pra nova conta se ainda não rodou)
Ver o bloco "BLOCO A + BLOCO B" na última mensagem — resumo: push staging → smoke dos 5 vulns → portar
8 únicos → develop→main → enumerar Quality → confirmar Fueling → re-rodar cobertura → surfar decisões.

## 12. Índice de artefatos (tudo no repo)

- Plano: `docs/PLANO_EXECUCAO_MIGRACAO_V3.md`
- Contrato: `docs/API_CONTRACT_MAP.md`, `docs/quality/CONTRATO_FRONT_BACK.md`
- Migração/design: `docs/decisions/adr/0041-migracao-design-v3-centro-de-comando.md`,
  `docs/design/recognition-v3/` (Recognition-visao-final.dc.html, FONTE-DE-VERDADE.md,
  MIGRATION_WIRING_SPEC.md, CONTRACT_COVERAGE_VALIDATION.md, HANDOFF_README.md, screenshots/)
- Tasks: `tools/agent-driver/tasks/` (070 andaime, 071 migração, 072-076 segurança, 069 contrato)
- ADRs de treino: 0031, 0037, 0038, 0039, 0040 (edge Jetson)
- Runbooks: `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`, `TRAINING_PIPELINE_WEEKEND_MVP.md`
- Fila: `tools/agent-driver/queue.txt` + `queue-hardware.txt`
