# Plano de Promoção `develop → staging` (RVB go-live)

> **PREPARADO, NÃO EXECUTADO.** A execução é **gate humano do Vitor** (DIRETRIZ: `develop→staging→main` são
> gates humanos). `staging` = **PRODUÇÃO** (auto-deploy Railway). Este plano é o roteiro do evento.
> Reconfirmar o estado com `git fetch` fresco + `gh` no momento de executar (C-04).

## Por que este é o coração do go-live
Uma única promoção **(a)** remove o **AGPL de produção** (`quality_inference.py:272,552`, `quality_training.py:218`,
`ultralytics_compat.py:35` vivos na staging hoje) e **(b)** sobe **todo o trabalho de edge/segurança/qualidade**
que já está na develop (+128 commits). Ver `docs/edge/GO_LIVE_EXECUCAO_2026-07-21.md`.

## Pré-condições (checar no dia, todas verdadeiras)
- [ ] `develop` com CI substantivo verde (License gate ✅, ruff, tsc, migrations harness, pytest, SAST/SBOM).
      Vermelhos aceitáveis: `SCA npm audit (landing)` e `gitleaks` (infra, não-required — confirmar que seguem sendo só esses).
- [ ] **Migration:** confirmado que a promoção NÃO quebra schema — `railway_start.py` re-roda TODAS as
      `infra/migrations/*.sql` idempotentemente a cada deploy (não há skip por versão). A colisão `052` é **benigna**
      (6 arquivos, todos `IF NOT EXISTS`). Ver GO_LIVE_EXECUCAO §BLOCO 0.1. **Não há pré-requisito de renumeração.**
- [ ] **Bloco 6.1 resolvido ou aceito:** senha `admin@rvb.com.br` rotacionada pela app (o `smoke_test.sh` ainda usa
      `admin@epimonitor.com / EpiMonitor@2024!` como default — trocar/parametrizar antes de confiar no smoke em prod).
- [ ] Janela de manutenção combinada + alguém de plantão.

## Passos da promoção (merge commit, NUNCA squash)
1. **Snapshot de segurança (rollback anchor):** anotar o SHA atual de `staging` (`gh api
   repos/logikos33/Recognition/branches/staging --jq .commit.sha`) e o SHA de `develop` a promover.
2. **Abrir PR `develop → staging`** (base `staging`, head `develop`). Revisar o diff de alto nível (esp. migrations
   novas 053→105 e remoção do AGPL). Título: `Merge develop→staging: go-live RVB (remove AGPL, sobe edge)`.
3. **Merge commit** (a UI/`gh pr merge --merge`, **nunca** `--squash`; runbook
   `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`).
4. **Auto-deploy Railway** dispara. Se necessário, forçar redeploy dos serviços afetados (memória de operação):
   `railway redeploy -s api-v3 -y`, `-s worker -y`, `-s frontend -y`.
5. **Acompanhar os logs de migration** no boot do `api-v3` (`railway logs`): confirmar que as `*.sql` aplicam sem
   `❌` (só `✅` ou "já existe (OK)"). **License gate** já garante zero AGPL no artefato servido.

## Smoke test (obrigatório pós-deploy)
```bash
./scripts/smoke_test.sh https://api-v3-production-2b22.up.railway.app
```
- [ ] `/health` 200 · `/api/streams/status` · `/api/auth/me` · `/api/cameras` (com token real, não o default do script).
- [ ] Frontend `https://frontend-production-bf96.up.railway.app` carrega e loga.
- [ ] Um endpoint de qualidade que exercite o caminho pós-AGPL (inferência servida por ONNX, sem ultralytics).

## Rollback (se o smoke falhar) — `docs/ROLLBACK.md`
- **Opção 1 (mais rápida):** Railway Rollback para o deploy anterior (sem tocar git) — do dashboard/`railway`.
- **Opção 2 (limpa):** `git revert` do merge commit em `staging` + redeploy.
- **Opção 3 (nuclear):** reset de `staging` para o SHA-âncora do passo 1 (`git reset --hard <sha>` + push forçado —
  só com aval explícito; reescreve histórico de produção).
- Gatilho de rollback: qualquer `❌` de migration no boot, `/health` ≠ 200, ou falha de login/inferência no smoke.

## O que NÃO fazer nesta janela
- Não promover `staging → main` no mesmo evento (é outro gate).
- Não misturar mudança de lógica com a promoção — a promoção é só o merge da develop.
- Não rodar `infra/migrations/run_migrations.py` à mão (script legado, chaveia por prefixo e PULA — não é o runner de prod).
