---
title: "Front: painel Sites & Saúde + fleet overview (UI)"
pr_title: "feat(frontend): painel Sites & Saúde + overview da frota (consome O1)"
commit_message: "feat(frontend): painel de saúde de sites + cards de overview, com testes Vitest/Playwright"
eval: default
budget_minutes: 75
risk: low
---

# Tarefa 026 — Painel Sites & Saúde + overview (frontend)

## Objetivo
UI que mostra a saúde da frota: lista de sites com status derivado, último heartbeat, métricas-chave, e os
cards de overview (contagens). Consome os endpoints O1 já existentes (overview/health/history/summary).
Frontend; depende do harness de teste (task-021). Sem hardware, sem migration.

## Contexto (LER — C-04)
- apps/frontend (React 18 + TS strict + Vite; Zustand; Radix; usePolling/useMonitoringSocket existentes).
- Endpoints: /edge/overview, /edge/sites/health (005), /sites/<id>/heartbeats (009), /heartbeat-summary (018).
- task-021: usar Vitest/RTL + Playwright.

## Comportamento / boas práticas
- Página "Sites & Saúde": cards de overview (sites por status, devices online/total, offline) + tabela de sites
  com status (healthy/degraded/critical/offline), último heartbeat, fps, câmeras online/total.
- Detalhe do site → série de heartbeats (gráfico) + summary. Estados loading/erro/empty tratados.
- Acessibilidade (teclado/ARIA/contraste); componentes pequenos; sem any; tenant via JWT.

## Eval (default + harness front 021)
- Vitest/RTL: render dos cards + tabela; estados loading/erro/empty; mock das respostas O1.
- Playwright e2e: carrega o painel, vê os cards e a lista (com backend mockado/stub).
- **Validação de UX:** screenshot + nota de melhorias no PR (legibilidade, densidade, refresh).
- tsc + lint verdes.

## Critérios de aceitação
- [ ] Painel consome O1 e mostra overview + saúde por site; estados tratados; acessível.
- [ ] Vitest + Playwright verdes; tsc + lint verdes; nota de UX no PR. PR para develop.

## NEEDS CLARIFICATION
- Reusar componentes/hook de polling/socket existentes (não recriar). Se faltar gráfico, usar a lib já no projeto.

## Checkpoint
- Só PR (humano revisa — feature de front, olho a UX). Sem produção. Sem migration.
