# Runbook — Reconciliação de Migration em Produção

**Versão:** 1.0  
**Data:** 2026-06-23  
**Executado por:** HUMANO (não automatizável — afeta BD de produção)  
**Pré-requisito:** PR `fix/migration-reconciliation` aprovado e mergeado em `develop`

> ⚠️ **Este runbook é executado pelo humano. Nenhum script automatizado deve tocar
> o BD de produção sem snapshot prévio.**

---

## URLs

| Ambiente | URL |
|----------|-----|
| **Produção** | `https://api-v3-production-2b22.up.railway.app` |
| **Staging** | Mesmo serviço (branch `staging` → mesmo Railway service) |

> `staging` e produção compartilham o mesmo serviço Railway. O smoke test
> abaixo refere-se a essa URL única.

---

## Passo 0 — Tirar snapshot do PostgreSQL (ponto de rollback)

No painel do Railway:
1. Abrir o serviço **PostgreSQL**
2. Menu → **Backups** → **Create Backup** (ou aguardar o backup automático diário)
3. Anotar o ID do snapshot aqui: `_________________________________`

Só prosseguir após confirmar o snapshot criado.

---

## Passo 1 — Verificação read-only em produção (antes do deploy)

Conectar ao BD de produção via Railway CLI ou cliente psql:

```bash
railway connect postgresql --service PostgreSQL
```

Rodar os seguintes SELECTs (somente leitura):

```sql
-- 1a. Versões aplicadas (deve terminar em "050" e "051")
SELECT version FROM schema_migrations ORDER BY version;

-- Resultado esperado (antes do deploy):
-- 001, 002, ..., 049, 050, 051

-- 1b. Confirmar que edge_sites NÃO existe (drift confirmado)
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'edge_sites'
) AS edge_sites_exists;
-- Esperado: false

-- 1c. Confirmar que device_tokens NÃO existe
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'device_tokens'
) AS device_tokens_exists;
-- Esperado: false

-- 1d. Confirmar colunas de loading_sessions (staging 050 aplicada)
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'counting_sessions'
  AND column_name IN ('bay_id','truck_plate','direction','expected_count','manual_count')
ORDER BY column_name;
-- Esperado: 5 linhas (bay_id, direction, expected_count, manual_count, truck_plate)
```

Se `edge_sites_exists = true`, a tabela já existe — edge_sites provavelmente já foi
criada manualmente. Verificar com a equipe antes de prosseguir.

---

## Passo 2 — Mergear o PR de fix em develop (gate humano)

1. Abrir PR `fix/migration-reconciliation` no GitHub
2. Verificar CI verde (ruff + pytest + tsc + migrations-harness)
3. Aprovar e fazer squash merge para `develop`

---

## Passo 3 — Promover develop → staging (= produção)

```bash
# Criar PR develop → staging no GitHub
gh pr create --base staging --head develop \
  --title "chore(release): promote develop → staging — pós reconciliação 065-079" \
  --body "Fix de colisão de migration (ADR-0021). Migrations 065-079 serão aplicadas no primeiro boot."
```

Aguardar CI verde no PR, então **mergear manualmente**.

Railway iniciará um novo deploy automaticamente. Acompanhar os logs:

```bash
railway logs --service api-v3 --tail
```

### O que deve aparecer nos logs de startup:

```
[MIGRATE] [SKIP] 001_initial_schema.sql (já aplicada)
...
[MIGRATE] [SKIP] 049_counting_deepsort_rebuild.sql (já aplicada)
[MIGRATE] [SKIP] 065_edge_sites.sql (version 050 → ... )
```

> ⚠️ Atenção: o runner vai PULAR `065_edge_sites.sql`? **NÃO.**
> O runner usa `filename.split("_")[0]` = `"065"`. Versão `"065"` NÃO está em
> `schema_migrations`. Portanto vai **RODAR**:

```
[MIGRATE] [APPLY] 065_edge_sites.sql ...
[MIGRATE] [OK] 065_edge_sites.sql
[MIGRATE] [APPLY] 066_device_tokens.sql ...
[MIGRATE] [OK] 066_device_tokens.sql
[MIGRATE] [APPLY] 067_site_id_attribution.sql ...
[MIGRATE] [OK] 067_site_id_attribution.sql
...
[MIGRATE] [APPLY] 079_retention_days.sql ...
[MIGRATE] [OK] 079_retention_days.sql
[MIGRATE] Migrations completas: 64 arquivos processados
```

Se qualquer `[FAIL]` aparecer, o serviço **não** sobe e o deploy falha (Railway
mantém a versão anterior ativa). Ir para **Passo 7 — Rollback**.

---

## Passo 4 — Verificação pós-deploy (read-only)

Após o deploy subir (health check verde no Railway):

```sql
-- 4a. Versões aplicadas (deve terminar em "079")
SELECT version FROM schema_migrations ORDER BY version;

-- Resultado esperado:
-- 001, 002, ..., 049, 050, 051, 065, 066, 067, 068, 069, 070,
-- 071, 072, 073, 074, 075, 076, 077, 078, 079

-- 4b. edge_sites existe agora
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'edge_sites'
) AS edge_sites_exists;
-- Esperado: true

-- 4c. device_tokens existe agora
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'device_tokens'
) AS device_tokens_exists;
-- Esperado: true

-- 4d. cameras tem site_id (migration 067)
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'cameras'
  AND column_name = 'site_id';
-- Esperado: 1 linha

-- 4e. Colunas de loading_sessions ainda existem (não foram removidas)
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'counting_sessions'
  AND column_name IN ('bay_id','truck_plate')
ORDER BY column_name;
-- Esperado: 2 linhas (bay_id, truck_plate)
```

---

## Passo 5 — Smoke test da API

```bash
# Health check
curl -s https://api-v3-production-2b22.up.railway.app/health | jq .
# Esperado: {"status": "ok", ...} com HTTP 200

# Login (substitua com credenciais reais)
curl -s -X POST https://api-v3-production-2b22.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"<email>","password":"<senha>"}' | jq .status
# Esperado: "success"
```

---

## Passo 6 — Segundo boot (idempotência)

Fazer redeploy manual no Railway (sem push — só para confirmar idempotência):

```bash
railway redeploy --service api-v3 -y
```

Aguardar o startup e verificar nos logs que todas as 064 migrations aparecem como
`[SKIP]` (exceto 065-079 que agora devem aparecer como `[SKIP]` também, pois já foram
aplicadas).

---

## Passo 7 — Rollback (se necessário)

Se qualquer passo falhar:

1. **Railway:** Menu do serviço → **Deployments** → selecionar o deploy anterior → **Redeploy**
   - O Railway mantém o container anterior ativo durante rollouts — a reversão é imediata
2. **BD:** Se o schema foi corrompido, restaurar o snapshot do Passo 0:
   - Railway PostgreSQL → **Backups** → selecionar snapshot → **Restore**
   - ⚠️ Restore de backup apaga dados criados após o snapshot

---

## Passo 8 — Verificação de regressão de funcionalidades críticas

Após smoke test verde:

- [ ] Login de operador funciona
- [ ] Lista de câmeras carrega
- [ ] Dashboard de KPIs carrega
- [ ] `GET /api/v1/edge/sites` retorna 200 (vazio se nenhum site cadastrado)
- [ ] AnnotationInterface carrega frames (se aplicável)

---

## Checklist de conclusão

- [ ] Snapshot Railway criado (Passo 0)
- [ ] Verificação pré-deploy (Passo 1) confirmada
- [ ] PR `fix/migration-reconciliation` mergeado em `develop` (Passo 2)
- [ ] PR `develop → staging` mergeado (Passo 3)
- [ ] Logs de deploy sem `[FAIL]` (Passo 3)
- [ ] Verificação pós-deploy (Passo 4) confirmada
- [ ] Smoke test API 200 (Passo 5)
- [ ] Segundo boot idempotente (Passo 6)
- [ ] Funcionalidades críticas OK (Passo 8)
