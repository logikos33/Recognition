---
title: "Frontend dual-mode (fallback edge.{site}.local quando cloud cai) — Fase 7"
pr_title: "feat(frontend): dual-mode — fallback automático para edge LAN quando o cloud cai"
commit_message: "feat(frontend): detecção de queda do cloud + fallback para edge.{site}.local e volta"
eval: default
budget_minutes: 90
risk: low
requires_hardware: partial
status: PARCIAL-HARDWARE — implementável com 021, mas validação real do fallback precisa do edge no site.
---

# Tarefa 036 — Frontend dual-mode (Fase 7) · validação real precisa do edge

> 🟡 A lógica/UX dá pra implementar e testar com mock (task-021); o fallback REAL (cloud cai → vai pro
> edge.{site}.local) só valida de verdade com o edge no site. Pode ir na fila AUTO pra implementar, mas a
> aceitação final é no equipamento.

## Objetivo
O painel detecta queda do cloud e faz fallback automático para a API/live-view LAN do edge (`edge.{site}.local`
via overlay), e volta pro cloud quando ele retorna — sem o operador perder visão.

## Depende de
- task-021 (harness front), edge stack/overlay (033) pra validação real.

## Escopo / Eval
- Detecção de indisponibilidade do cloud (timeout/health) → troca base URL pro edge LAN → indica modo no UI.
- Volta automática ao cloud. Vitest/Playwright com cloud mockado caindo/voltando; validação real no site.

## Critérios de aceitação
- [ ] Fallback e retorno automáticos, com indicação no UI; testes (mock) verdes; validação real no site marcada como pendente-hardware.

## Checkpoint
- PR (front). Aceitação final no equipamento (overlay + edge).
