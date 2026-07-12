---
title: "Planner agent — gera a próxima fila conforme as entregas (REGISTRADO, pós-go-live)"
pr_title: "feat(driver): planner agent — gera specs draft on-merge + spec-gate"
commit_message: "feat(driver): planner agent (on-merge → draft specs → spec-reviewer → fila)"
eval: default
budget_minutes: 90
risk: security
status: REGISTRADO — NÃO RODAR AGORA (pós-go-live; spec-writing não é o gargalo atual)
---

# Tarefa 020 — Planner agent (auto-geração da fila) · REGISTRADA, não priorizada

> ⚠️ **Não disparar agora.** Spec-writing não é o gargalo do go-live (o gargalo é PC + modelo). Esta task fica
> registrada para **pós-go-live**, quando gerar specs vira o gargalo (muitos clientes/features). Construir antes
> é meta-trabalho com retorno decrescente perto do deadline RVB.

## Objetivo
Fechar o topo do loop autônomo: em vez de um humano escrever cada spec, um **planner** lê o roadmap + o estado
real do código e **emite o próximo lote de specs draft**, que passam por um **spec-gate** antes de entrar na fila.
Pipeline final de 4 agentes: **Planner → Spec-reviewer → Implementer (driver) → PR-reviewer (Opus)**.

## Componentes
- **planner.py** — gatilho **on-merge-to-develop** (GitHub Action) ou cron. Lê: EDGE_DEPLOYMENT_PLAN.md,
  HARNESS_PLANO_IMPLEMENTACAO.md, ADRs, `docs/EVALS.md`, o git log/estado, o schema real, os PENDs. Emite
  specs draft no `_TEMPLATE.md`, com risk-tag, respeitando: **só tabela-existente para o autônomo**; qualquer
  migration/hardware/net-new-security → marca como **escalonado pro humano**, não entra no autônomo.
- **spec_reviewer.py** (Opus, adversarial) — valida cada spec draft contra a constituição + checklist de lições:
  tem critério de aceite verificável? invariantes de segurança? `[NEEDS CLARIFICATION]` nas suposições?
  teste em DB real para query? offline via helper compartilhado? tabela-existente ou migration sinalizada?
  Veredito: APROVA (entra na fila) | DEVOLVE (planner refina) | ESCALA (humano).
- **Gate humano:** você aprova o **lote** (não cada spec) antes do queue_runner tocar.

## Restrições inegociáveis
- O planner só emite tasks que **mapeiam para fases/entregáveis documentados** (sem escopo inventado).
- Safeguard paths, migrations, hardware, net-new security, promoção develop→main → **sempre humano**.
- Spec com `[NEEDS CLARIFICATION]` pendente NÃO entra na fila (bloqueante).

## Eval (default, quando for implementada)
- planner gera specs válidas (front-matter completo, risk-tag, mapeadas a uma fase do roadmap).
- spec_reviewer reprova spec sem critério de aceite / sem invariante de segurança / com suposição não-marcada.
- task que precisa de migration/hardware → planner marca como escalonada, não autônoma.
- testes da lógica de decisão (pura), mockando claude.

## Checkpoint
- Só PR (humano revisa — é a máquina que decide O QUE entra na fila; safeguard). Sem produção. Sem migration.
- NÃO adicionar à `queue.txt` enquanto registrada.
