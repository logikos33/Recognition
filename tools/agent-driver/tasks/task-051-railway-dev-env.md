# Task 051 — Railway Developer Environment (develop branch)

**Status**: IN PROGRESS
**Risk**: low
**Branch**: develop (infra config)

## Objetivo

Provisionar ambiente Railway isolado que faça deploy automático do branch `develop`, sem tocar em production/staging.

## Entregáveis

- [x] Ambiente `develop` criado no Railway CLI (`railway environment new develop`)
- [x] Ambiente linkado (`railway environment link develop`)
- [ ] Serviços clonados de production no ambiente `develop` via Railway Dashboard
- [ ] Cada serviço configurado para deploy automático do branch `develop`
- [ ] Variáveis de ambiente copiadas de production para develop (com valores de teste)

## PENDÊNCIAS DE ACESSO (requerem Railway Dashboard)

Pasos a completar manualmente no dashboard (https://railway.app/project/epi-monitor-v2):

1. Ir em "Environments" → selecionar `develop`
2. Para cada serviço (api-v3, worker, frontend):
   a. "Settings" → "Source" → selecionar branch `develop`
   b. "Variables" → copiar variáveis de production (ajustar secrets se necessário)
3. Trigger primeiro deploy manualmente

## Serviços necessários no ambiente develop

- `api-v3` → `services/api/` → branch `develop` → `SERVICE_TYPE=api`
- `worker` → `services/api/` → branch `develop` → `SERVICE_TYPE=worker`
- `frontend` → `apps/frontend/` → branch `develop`

## Notas

- Railway CLI cria ambientes vazios; serviços são adicionados via Dashboard ou `railway add`
- DB e Redis: reutilizar production por enquanto (apenas leitura/testes no schema de teste)
- Railway CLI já autenticado: `railway status` confirma `epi-monitor-v2`
