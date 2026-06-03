---
title: "Suíte de invariantes de segurança para rotas /edge"
pr_title: "test(edge): suíte de invariantes (auth obrigatória + helpers cross-tenant)"
commit_message: "test(edge): invariant suite — toda rota /edge exige auth; helpers de isolamento multi-tenant"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 006 — Suíte de invariantes de segurança (/api/v1/edge)

## Objetivo
Criar testes que TODA rota do blueprint /api/v1/edge precisa passar, para que "CI verde" passe a
significar "invariantes de segurança respeitados". É a fundação que torna o auto-merge (L2) seguro:
sem isso, um endpoint novo que esqueça auth ou vaze cross-tenant passaria batido. Sem hardware, sem migration.

## Contexto (LER antes — C-04; C-01 multi-tenant; C-05 segurança)
- /constitution.md, docs/methodology/SPEC_DRIVEN_ADOCAO.md (por que invariantes/eval-driven).
- app/__init__.py (registro de blueprints e url_map), app/api/v1/edge/routes.py (rotas existentes:
  POST /heartbeat, POST /sites, GET /sites, POST /sites/<id>/enrollment-tokens, e /enroll se já existir).
- app/core/auth.py e app/core/device_auth.py (os modos de auth: JWT de usuário vs device token RS256).
- services/api/tests/ (conftest, fixtures existentes; seguir o padrão).

## Conteúdo a criar
Arquivo: services/api/tests/security/test_edge_invariants.py

1) INVARIANTE — auth obrigatória em toda rota /edge (pega "endpoint público acidental"):
   - Iterar app.url_map; para CADA rota cujo path começa com /api/v1/edge/, fazer a requisição SEM
     nenhuma credencial (sem Authorization, sem cookie/JWT) usando o método aceito.
   - Assert: resposta é 401 ou 403 — NUNCA 2xx. Falhar lista a rota culpada.
   - Parametrizar por (rule, method) para o relatório apontar exatamente qual rota falhou.
   - Detalhe: rotas que autenticam por corpo (ex: /enroll usa enrollment_token no body) também devem
     rejeitar sem credencial (token ausente/ inválido → 4xx). Se alguma rota legitimamente não exige auth,
     ela deve estar numa ALLOWLIST explícita e versionada no teste, com comentário justificando (default = exige).

2) HELPERS reutilizáveis de isolamento multi-tenant (para as tasks de endpoint reusarem):
   - Em services/api/tests/security/_helpers_tenant.py (ou conftest local): factories/fixtures que semeiam
     2 tenants (tenant_a, tenant_b) com seus sites/devices, e helpers:
       - make_user_jwt(tenant_id, role) / make_device_token(...) reaproveitando o que já existe nos testes.
       - assert_response_only_contains_tenant(resp_json, tenant_id): garante que nenhum id/registro de
         outro tenant aparece na resposta.
   - Documentar no topo do arquivo: "toda task de endpoint /edge DEVE incluir um teste cross-tenant usando estes helpers".

3) NEEDS CLARIFICATION: se ao iterar o url_map houver rota cujo modo de auth você não conseguir
   determinar lendo o código, NÃO assuma — deixe `# [NEEDS CLARIFICATION: rota X usa qual auth?]` e
   inclua-a na allowlist temporária comentada, reportando no PR. Não silencie a dúvida.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- services/api/tests/security/test_edge_invariants.py (novo)
- services/api/tests/security/_helpers_tenant.py (novo, se fizer sentido)
- atualizar docs/EVALS.md: registrar a suíte de invariantes como eval obrigatória das rotas /edge

## Eval (default) — os testes SÃO o critério
- A suíte roda e passa contra as rotas /edge atuais (heartbeat, sites, enrollment-tokens).
- O teste genérico de auth realmente itera o url_map (não uma lista hardcoded) e cobre todas as rotas /edge.
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] Teste genérico: toda rota /api/v1/edge/* sem credencial → 401/403 (nunca 2xx); allowlist explícita se houver exceção.
- [ ] Helpers cross-tenant criados e documentados para reuso pelas tasks de endpoint.
- [ ] docs/EVALS.md atualizado citando a suíte como invariante obrigatória.
- [ ] Sem NEEDS CLARIFICATION pendente não-documentado. ruff + pytest verdes.
- [ ] PR para develop.

## Checkpoint
- Só PR (humano revisa — é tooling de segurança). Sem produção. Sem migration. Faltou contexto → ler.
