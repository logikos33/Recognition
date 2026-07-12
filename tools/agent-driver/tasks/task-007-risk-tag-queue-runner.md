---
title: "Risk-tag + queue runner (auto-merge gated) — L2"
pr_title: "feat(driver): queue runner com auto-merge gated por risco (L2)"
commit_message: "feat(driver): risk-tag nas specs + queue_runner com auto-merge só para low-risk"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 007 — Risk-tag + queue runner (auto-merge gated)

## Objetivo
Permitir disparar um LOTE de tasks que roda sequencialmente, com auto-merge APENAS para tarefas de
baixo risco e CI verde; tarefas de risco de segurança PARAM para revisão humana. main/staging nunca
auto-mergeiam. É o passo L2: velocidade sem perder o gate onde importa. Sem hardware, sem migration.

## Princípio de segurança (inegociável)
- **Default fail-safe:** spec SEM campo `risk` é tratada como `security` (NÃO auto-mergeia).
- Auto-merge só acontece se: `risk: low` E todos os checks de CI = success E base = develop.
- NUNCA auto-mergear em main ou staging. NUNCA `--admin`/bypass de checks. NUNCA force-merge.

## Contexto (LER antes — C-04)
- tools/agent-driver/driver.py (como roda uma task, abre PR, branch agent/*), config.yaml, _TEMPLATE.md.
- Como o gh expõe status de checks: `gh pr checks <pr>` / `gh pr view <pr> --json ...`.
- docs/methodology/SPEC_DRIVEN_ADOCAO.md (M1 NEEDS CLARIFICATION, M3 test-first, M5 risk-tag).

## Tarefa 1 — Risk-tag + melhorias no template
- _TEMPLATE.md das task specs: adicionar no front-matter `risk: low|security` (com comentário: ausência = security)
  e uma seção "## NEEDS CLARIFICATION" (M1) + ordem test-first (critérios de aceite/invariantes antes das dicas de implementação, M3).
- Documentar a convenção de risco: `security` = toca auth, multi-tenant, token, migration, dados de cliente,
  ou qualquer coisa com invariante de segurança; `low` = leitura pura, docs, display/frontend sem auth nova.

## Tarefa 2 — queue_runner.py (tools/agent-driver/queue_runner.py)
- Entrada: uma lista ORDENADA de specs (arquivo `queue.txt` com um caminho por linha, ou args).
- Para cada spec, em ordem:
  1. Ler o front-matter; extrair `risk` (default `security`).
  2. Rodar o driver: `python driver.py <spec>` (subprocess). Capturar o número do PR criado (do output/log do driver).
  3. Se `risk == low`:
       - Esperar CI: `gh pr checks <pr> --watch` (ou poll com timeout configurável).
       - Se TODOS os checks = success → `gh pr merge <pr> --merge` (merge commit, base develop). Depois
         `git checkout develop && git pull`. Seguir para a próxima.
       - Se algum check falhar/timeout → PARAR o lote, logar, deixar o PR aberto para o humano.
  4. Se `risk == security`:
       - NÃO mergear. Logar "PR #<n> (security) aguardando revisão humana" e PARAR o lote (as próximas
         podem depender desta). Sair com código que sinalize "pausado para revisão".
- Tudo logado em tools/agent-driver/runs/queue-<ts>.log. Config (timeout de CI, etc.) em config.yaml.
- Reusar os guard-rails do driver (o driver já garante branch agent/*, base develop, tree limpo).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- tools/agent-driver/_TEMPLATE.md (risk + NEEDS CLARIFICATION + ordem test-first)
- tools/agent-driver/queue_runner.py (novo)
- tools/agent-driver/test_queue_runner.py (novo — ver eval)
- tools/agent-driver/README.md (documentar o queue runner + convenção de risco)
- config.yaml (timeout de CI, opções do queue)

## Eval (default) — testes SÃO o critério (sem chamar gh/driver/CI reais — mockar)
- parse de risco: spec com `risk: low` → low; spec SEM risk → `security` (fail-safe). [crítico]
- decisão de auto-merge: low + checks=success → decide mergear; low + checks=failure → não mergeia, para;
  security → nunca mergeia, pausa. (testar a função de decisão pura, sem efeitos colaterais.)
- nunca decide mergear se base != develop.
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] _TEMPLATE.md com `risk` (default security documentado), NEEDS CLARIFICATION e ordem test-first.
- [ ] queue_runner roda specs em ordem; low-risk auto-mergeia só com CI verde; security pausa para humano.
- [ ] Função de decisão de merge é pura e testada; default ausente = security; nunca main/staging.
- [ ] test_queue_runner.py verde; ruff + pytest verdes.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma no momento. Se o output do driver não expuser o número do PR de forma parseável, NÃO adivinhar —
  ajustar o driver para imprimir o PR de forma estável e documentar, ou deixar [NEEDS CLARIFICATION] e reportar.

## Checkpoint
- Só PR (humano revisa — é a máquina de auto-merge, tem que ser revisada à mão). Sem produção. Sem migration.
