---
title: "Fix auto-bounce: retry do revisor sem arquivo untracked"
pr_title: "fix(driver): auto-bounce de REQUEST_CHANGES em memória (sem untracked / sem exit 7)"
commit_message: "fix(driver): retry do revisor passa findings em memória na mesma branch agent/*, sem escrever spec untracked"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 019 — Fix do auto-bounce (REQUEST_CHANGES não pode travar a mão)

## Objetivo
Fechar o loop autônomo: quando o revisor dá REQUEST_CHANGES, o retry deve reinjetar os achados NO MESMO
fluxo, em memória, **sem criar arquivo de spec untracked** (que hoje trip o `_assert_clean_tree` → exit 7,
travando toda revisão na mão). Bug observado no ciclo da task-016. Sem hardware, sem migration.

## Contexto (LER antes — C-04)
- tools/agent-driver/{queue_runner.py, driver.py, reviewer.py} — entender o fluxo atual de retry e o ponto
  onde o "spec aumentado" é gerado/escrito.
- O `_assert_clean_tree` (estrito: untracked = sujo) — manter; o fix é NÃO gerar untracked, não relaxar o guard.

## Comportamento alvo
- No REQUEST_CHANGES, o orquestrador monta o prompt de retry com `findings` + `proposed_tests` **em memória**
  (string) e re-invoca o implementador (`claude -p`) **na MESMA branch agent/* já criada** — sem novo arquivo de spec.
- Se algo precisar ser persistido (log do retry, findings), gravar SOMENTE em `tools/agent-driver/runs/`
  (já gitignored) — nunca no working tree versionável.
- Respeitar `max_retries`; estourou → ESCALATE pro humano (PR aberto + findings no log), sem loop infinito.
- A branch de trabalho continua a mesma entre tentativas (não recriar agent/* a cada retry; não sujar develop).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- tools/agent-driver/queue_runner.py e/ou driver.py (loop de retry)
- tools/agent-driver/test_queue_runner.py / test_driver.py (testes)

## Eval (default) — testes SÃO o critério (mockar claude/gh)
- Simular REQUEST_CHANGES → a função de retry NÃO escreve nenhum arquivo no working tree versionável
  (assert: nenhum path fora de runs/ é criado/modificado pelo retry).
- Os findings + proposed_tests são passados ao prompt de retry (assert no prompt montado).
- Após `max_retries` sem APPROVE → decisão = escalate (não loop).
- O fluxo não chama `_assert_clean_tree` de forma que o próprio retry o viole (sem exit 7 auto-induzido).
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] Retry de REQUEST_CHANGES roda em memória, mesma branch agent/*, zero arquivo untracked versionável.
- [ ] Persistência só em runs/ (gitignored). max_retries → escalate.
- [ ] `_assert_clean_tree` permanece estrito (não relaxado).
- [ ] Testes acima verdes; ruff + pytest verdes. PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se a estrutura atual do driver dificultar passar findings sem arquivo, refatorar o ponto de
  retry para aceitar um "feedback string" — NÃO criar arquivo só pra contornar.

## Checkpoint
- Só PR (humano revisa — toca a máquina do driver, safeguard). Sem produção. Sem migration.
