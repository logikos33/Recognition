---
title: "Revisor-agente adversarial no pipeline (L3 gated)"
pr_title: "feat(driver): reviewer-agent adversarial integrado ao queue runner"
commit_message: "feat(driver): reviewer-agent (Opus, read-only) com veredito estruturado e escalonamento obrigatório"
eval: default
budget_minutes: 75
risk: security
---

# Tarefa 008 — Revisor-agente adversarial (gate de merge)

## Objetivo
Adicionar ao pipeline um AGENTE REVISOR, separado do implementador, que avalia cada PR antes do merge:
tenta FALSIFICAR os invariantes (constituição + suíte da task-006 + critérios de aceite da spec), emite
veredito estruturado, e propõe os testes que faltam quando acha um gap. Isso automatiza o caminho comum de
ponta a ponta (implementa → revisa → CI → merge) mantendo humano só no escalonamento. Sem hardware, sem migration.
**Depende de:** task-007 (queue runner) e task-006 (suíte de invariantes) já mergeadas.

## Princípios de segurança (inegociáveis)
- **Separação de funções:** o revisor é READ-ONLY. allowedTools só de leitura (Read, Grep, Glob, Bash(git diff:*),
  Bash(git log:*)). Ele NUNCA edita código nem mergeia — só emite veredito; quem age é o queue runner.
- **Modelo diferente/mais forte:** revisor roda em Opus (config `reviewer_model`), implementador em Sonnet — diversidade reduz ponto-cego compartilhado.
- **Não validar a própria salvaguarda:** se o PR toca `constitution.md`, a suíte de invariantes
  (tests/.../test_edge_invariants.py + helpers), o próprio reviewer/driver/queue_runner, `infra/migrations/`,
  `.github/`, ou `railway_start.py` → veredito é forçado a **ESCALATE** independentemente do conteúdo. Sem auto-aprovar mudança no próprio gate.
- **Spec pode estar errada:** instruir o revisor a NÃO só checar código-vs-spec — deve provar o threat-model de
  forma independente (multi-tenant, auth, idempotência, segredos) assumindo que a spec pode ter premissa errada.

## Contexto (LER antes — C-04)
- tools/agent-driver/{driver.py, queue_runner.py, config.yaml} (task-007), /constitution.md,
  tests/.../test_edge_invariants.py (task-006), docs/methodology/SPEC_DRIVEN_ADOCAO.md.
- Como obter o diff do PR e o número do PR (gh pr diff <n>, gh pr view).

## Tarefa 1 — reviewer.py (tools/agent-driver/reviewer.py)
- Entrada: número do PR (ou branch) + caminho da spec.
- Monta prompt do revisor injetando: diff do PR, a spec, /constitution.md, e um CHECKLIST DE AMEAÇA explícito
  (tenant_id vem do servidor e nunca do body/claims? auth verifica assinatura de verdade? token one-time é
  atômico? segredo guardado como hash? SQL parametrizado? sem print? há teste cross-tenant e de auth ausente?).
- Chama `claude -p` com `--model <reviewer_model>` (Opus) e allowedTools SÓ de leitura. `--output-format json`.
- Exige saída JSON estruturada do revisor:
  `{ "verdict": "APPROVE|REQUEST_CHANGES|ESCALATE", "findings": [{"invariant": "...", "severity": "...", "detail": "..."}],
     "proposed_tests": ["..."] }`
- Parse robusto; se não vier JSON válido → tratar como ESCALATE (fail-safe).

## Tarefa 2 — Integração no queue_runner (decisão pura e testável)
Após o driver abrir o PR, antes de decidir merge, o queue runner chama o reviewer e combina:
- Forçar ESCALATE se o PR toca qualquer path/arquivo de salvaguarda (lista acima) OU se `risk: security`.
- Senão, por veredito:
  - APPROVE + risk:low + CI verde → auto-merge (regras da task-007).
  - REQUEST_CHANGES → devolve `findings` + `proposed_tests` ao driver como feedback e re-roda o implementador
    (até max_retries); se persistir → ESCALATE.
  - ESCALATE → para, loga, deixa o PR aberto + registra os findings para o humano.
- Sempre logar o veredito e os findings em runs/. NUNCA auto-merge em main/staging.

## Tarefa 3 — Flywheel de eval
- Quando o veredito traz `proposed_tests`, registrar num arquivo (ex: runs/proposed-tests-<pr>.md) e, se
  REQUEST_CHANGES, instruir o implementador a adicionar esses testes. Todo gap pego vira eval permanente.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- tools/agent-driver/reviewer.py (novo)
- tools/agent-driver/queue_runner.py (integrar o passo de review + decisão)
- tools/agent-driver/test_reviewer.py (novo — ver eval)
- tools/agent-driver/config.yaml (reviewer_model: claude-opus-4-6; allowedTools de review; lista de paths de salvaguarda)
- tools/agent-driver/README.md (documentar o fluxo com revisor)

## Eval (default) — testes SÃO o critério (mockar claude/gh; testar a lógica pura)
- decisão: APPROVE+low+CI verde → merge; REQUEST_CHANGES → loop de feedback; ESCALATE → pausa.
- forçar ESCALATE quando o diff toca constitution.md / invariant suite / reviewer / driver / migrations / .github,
  MESMO com verdict=APPROVE. [crítico — anti self-weakening]
- forçar ESCALATE quando risk=security (mesmo APPROVE).
- JSON inválido do revisor → ESCALATE (fail-safe).
- reviewer é read-only: assert que os allowedTools dele não contêm Edit/Write/merge.

## Critérios de aceitação
- [ ] reviewer.py: read-only, Opus, saída JSON estruturada, fail-safe ESCALATE em parse inválido.
- [ ] queue runner combina veredito + risco + paths de salvaguarda; self-weakening sempre escala.
- [ ] proposed_tests registrados e realimentados no REQUEST_CHANGES (flywheel).
- [ ] test_reviewer.py cobre a tabela de decisão acima, verde; ruff + pytest verdes.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se a saída do `claude -p` em modo review não for parseável de forma estável, NÃO adivinhar —
  fixar o formato (system prompt do revisor exigindo só JSON) e documentar.

## Checkpoint
- Só PR (humano revisa — é o gate de merge; tem que ser revisado à mão). Sem produção. Sem migration.
