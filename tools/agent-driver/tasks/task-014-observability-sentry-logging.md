---
title: "Observabilidade: Sentry + logging JSON estruturado (O1)"
pr_title: "feat(obs): Sentry opt-in + logging JSON estruturado sem PII"
commit_message: "feat(obs): Sentry (DSN via env, no-op sem DSN) + JSON logging sem PII no blueprint /edge"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 014 — Sentry + logging estruturado (O1)

## Objetivo
Plugar observabilidade no cloud: Sentry (erros/traces) e logging JSON estruturado sem PII. É um entregável
da Fase O1. `risk: security` porque adiciona dependência nova e toca o app factory. Sem hardware, sem migration.

## Contexto (LER antes — C-04, C-05)
- app/__init__.py (Application Factory create_app), app/config.py (config por ambiente), app/api/v1/edge/routes.py.
- requirements/ (estrutura por serviço — base.txt/api.txt). Adicionar sentry-sdk em base ou api.

## Comportamento
- Sentry OPT-IN: inicializar sentry-sdk no create_app SOMENTE se `SENTRY_DSN` estiver no ambiente. Sem DSN →
  no-op total (dev/CI sem DSN NÃO podem quebrar). environment = config atual; sem PII no scope.
- Logging JSON estruturado: configurar um formatter JSON para os logs do blueprint /edge (e idealmente app-wide),
  incluindo nível, componente, e contexto seguro (ex: tenant_id truncado/hasheado). NUNCA logar token, public_key,
  ou payload com PII (C-05).
- Tag de site/tenant nos eventos Sentry quando disponível no contexto (truncado, sem PII).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/__init__.py (init Sentry opt-in)
- app/core/ (um helper de logging JSON, ex: logging_config.py)
- requirements/base.txt ou api.txt (adicionar sentry-sdk — dependência esperada/discutida)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- create_app() SEM SENTRY_DSN → não inicializa Sentry e NÃO quebra (app cria normalmente). [crítico p/ CI]
- create_app() COM SENTRY_DSN fake → inicializa sem erro (mockar sentry_sdk.init; assert chamado com o DSN).
- logging: um log do blueprint /edge sai como JSON parseável; assert que um token/segredo de exemplo NÃO aparece no output.
- ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] Sentry opt-in (no-op sem DSN); app não quebra sem DSN (CI verde sem segredo).
- [ ] Logging JSON sem PII; segredo de exemplo não vaza no log.
- [ ] sentry-sdk adicionado aos requirements; import guardado/opcional.
- [ ] Testes acima verdes; ruff + pytest + tsc verdes. PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se já houver config de logging no projeto, ESTENDER (não duplicar) — ler antes.

## Checkpoint
- Só PR (humano revisa — dependência nova + app factory). Sem produção. Sem migration.
