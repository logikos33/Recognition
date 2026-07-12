---
title: "Harness de teste de frontend (Vitest + RTL + Playwright + CI)"
pr_title: "test(frontend): Vitest + Testing Library + Playwright + job de CI"
commit_message: "test(frontend): setup Vitest/RTL (componentes) + Playwright (e2e) + job de CI de frontend"
eval: default
budget_minutes: 75
risk: security
---

# Tarefa 021 — Harness de teste de frontend

## Objetivo
Tornar o frontend TESTÁVEL com boas práticas, pra que features de front (ex: editor de cenário) virem
avaliáveis/autônomas. Hoje a única verificação de front é `tsc`. Adicionar testes de componente (Vitest +
React Testing Library) e e2e (Playwright) + um job de CI. Pré-requisito da edição visual. Sem hardware, sem migration.

## Contexto (LER antes — C-04)
- apps/frontend (React 18 + TS strict + Vite; Zustand; Radix; HLS.js). package.json, vite.config.ts, tsconfig.
- .github/workflows/ci.yml (job tsc atual) — ESTENDER, não quebrar.
- Convenção do projeto: TS strict, zero any implícito.

## Conteúdo
- **Vitest + @testing-library/react + jsdom**: configurar; um teste de componente real (smoke de um componente
  já existente, ex: um card/badge), cobrindo render + um estado (loading/erro).
- **Playwright**: configurar; um e2e smoke headless (sobe a app em modo dev/preview, carrega uma rota e
  valida um elemento). Sem depender de backend real (mock/stub onde precisar).
- **CI**: job `frontend` em ci.yml rodando `npm run lint` (se houver) + `tsc --noEmit` + `vitest run` +
  `playwright test` (headless, com browsers instalados no job). < 5 min; não quebrar os jobs existentes.
- Scripts no package.json: `test`, `test:e2e`.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- apps/frontend/ (config de Vitest/Playwright, testes exemplo, package.json/scripts)
- .github/workflows/ci.yml (job frontend)  ← safeguard: este PR escala pra revisão humana (esperado)

## Eval (default) — testes SÃO o critério
- `vitest run` passa (o teste de componente exemplo verde).
- `playwright test` headless passa (o e2e smoke verde).
- `tsc --noEmit` continua verde; jobs de CI existentes não quebram.

## Critérios de aceitação
- [ ] Vitest + RTL configurados com 1 teste de componente real verde.
- [ ] Playwright configurado com 1 e2e smoke headless verde.
- [ ] Job de CI de frontend (lint + tsc + vitest + playwright) verde, < 5 min.
- [ ] Scripts test/test:e2e no package.json. PR para develop.

## NEEDS CLARIFICATION
- Se já existir algum setup de teste de front, ESTENDER (não duplicar). Se Playwright pesar demais no CI,
  rodar só o subset smoke no PR e o resto sob demanda — reportar a decisão.

## Checkpoint
- Só PR (humano revisa — toca .github/ e a eval). Sem produção. Sem migration.
