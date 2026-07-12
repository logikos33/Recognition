---
title: "Security clearance: bateria de invariantes + SAST + clearance no gate"
pr_title: "feat(driver): security battery + SAST + security-clearance gated no queue runner"
commit_message: "feat(driver): bateria de segurança + SAST (bandit/pip-audit) + clearance de security só sem superfície nova"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 015 — Security clearance (encolher o gate humano da classe security)

## Objetivo
Tornar a segurança VERIFICÁVEL POR MÁQUINA para que tarefas `risk: security` que só tocam superfícies já
cobertas possam ser auto-aprovadas (revisor + bateria + SAST), reservando o humano apenas para
superfície de segurança NOVA. Flywheel: toda revisão humana vira teste de invariante. Sem hardware, sem migration.
**Depende de:** task-006 (suíte de invariantes) e task-008 (reviewer + queue runner) mergeados.

## Princípios inegociáveis (segurança)
- Security-clearance auto SÓ se TODOS: verdict APPROVE + bateria de segurança verde + SAST verde + diff NÃO
  introduz superfície nova. Falha em qualquer um → ESCALATE.
- Safeguard paths (constitution, agent-driver, tests/security, migrations, .github, railway_start) → SEMPRE escalam (mantém task-008).
- Superfície de segurança NOVA → SEMPRE escala + revisor propõe o teste de bateria que falta (não auto-aprova).
- Promoção develop→main e net-new auth/cripto → sempre humano. Default fail-safe: na dúvida, ESCALATE.

## Contexto (LER antes — C-04)
- tools/agent-driver/{queue_runner.py, reviewer.py, config.yaml}, services/api/tests/security/ (suíte da 006),
  .github/workflows/ci.yml, docs/methodology/SPEC_DRIVEN_ADOCAO.md (EDD/flywheel).

## Tarefa 1 — Expandir a bateria de segurança (genérica, services/api/tests/security/)
Testes que TODA rota /edge mutante (POST/PATCH/DELETE) deve passar, descobertos via url_map:
- forged-body: enviar tenant_id/site_id falsos no body com auth válida de outro tenant → o efeito NUNCA usa o
  tenant do body (atribuição server-side). Cobre a classe do bug do task-002 de forma genérica.
- secret-leak: resposta de qualquer rota /edge nunca contém padrões de segredo (token_hash, BEGIN PRIVATE KEY,
  bearer ...) — varredura por regex no corpo de respostas de sucesso.
- auth-required: já coberto pela 006 (manter/estender).
Marcar com allowlist explícita qualquer rota legitimamente isenta (justificada).

## Tarefa 2 — SAST no CI (.github/workflows/ci.yml)
Adicionar job `sast`: bandit (services/api/) + pip-audit (dependências). gitleaks já existe. < 3 min, bloqueia merge.
Baseline: se houver findings pré-existentes, baselina-los explicitamente (documentado), nunca silenciar gerais.

## Tarefa 3 — Security-clearance no queue runner (decisão pura, testável)
- Função pura _security_clearance(verdict, battery_passed, sast_passed, introduces_new_surface) -> 'auto'|'escalate':
  retorna 'auto' SOMENTE se verdict==APPROVE AND battery_passed AND sast_passed AND not introduces_new_surface;
  senão 'escalate'.
- Detector de superfície nova (heurístico, conservador) sobre o diff: introduces_new_surface=True se o diff
  ADICIONA qualquer um: novo decorator de auth, uso novo de jwt/cripto/hashlib/secrets, novo parsing de input
  externo não-padrão, nova dependência em requirements. Marcadores configuráveis em config.yaml
  (`security_surface_markers`). Na dúvida → True (escala).
- Integrar: para risk==security, em vez de escalar incondicionalmente, aplicar _security_clearance; só 'auto'
  segue para o gate de CI (_should_auto_merge tratando security-cleared como elegível). Safeguard paths e
  promoção continuam fora.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- services/api/tests/security/ (novos testes de bateria)
- .github/workflows/ci.yml (job sast)  ← É SAFEGUARD: este PR vai escalar pra revisão humana (esperado)
- tools/agent-driver/{queue_runner.py, config.yaml}, tools/agent-driver/test_queue_runner.py
- requirements (bandit, pip-audit como dev deps)

## Eval (default) — testes SÃO o critério (mockar gh/claude)
- _security_clearance: APPROVE+battery+sast+no-new-surface → 'auto'; qualquer um faltando → 'escalate'.
- introduces_new_surface=True força 'escalate' mesmo com tudo verde.
- detector: diff adicionando `import jwt`/novo `@requires_auth`/nova dep → new_surface True; diff só de SQL de
  leitura tenant-scoped → False.
- bateria genérica roda contra as rotas /edge atuais e passa.
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] Bateria genérica (forged-body, secret-leak) cobrindo rotas /edge mutantes via url_map.
- [ ] Job SAST no CI (bandit + pip-audit), bloqueante.
- [ ] _security_clearance puro e testado; superfície nova sempre escala; fail-safe na dúvida.
- [ ] Safeguard paths e promoção continuam sempre humanos.
- [ ] ruff + pytest verdes. PR para develop.

## NEEDS CLARIFICATION
- Se o detector de superfície nova ficar ambíguo demais (muitos falsos-escalate), NÃO afrouxar sozinho —
  reportar e ajustar os marcadores com revisão humana.

## Checkpoint
- Só PR (humano revisa — muda o gate de segurança E toca .github/. SEMPRE humano). Sem produção. Sem migration.
