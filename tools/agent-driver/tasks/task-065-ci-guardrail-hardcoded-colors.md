# Task 065 — Guard-rail CI anti-cores-hardcoded (develop) + débito de contraste tema legacy

**Status**: PENDING (blindagem — recomendado antes do go-live)
**Risk**: P2-MÉDIO (CI/lint; previne regressão da classe de bug visual da task-063)
**Branch**: fix/task-065-ci-guardrail-hardcoded-colors

## Contexto (achado na task-063 — 2026-07-06)

O bug visual do painel de Operação era **cores hardcoded baseadas em branco** (`rgba(255,255,255,…)`,
roxo/azul fixos) que quebram quando o tenant usa **superfícies claras via white-label (WS1)** — texto
e botões ficam invisíveis. A **staging já tem um guard-rail** que barra cores hardcoded, mas o
**develop não tem** — então novo hardcode entra no develop e só é pego (ou não) na staging/produção.

## Objetivo

Portar/ativar o guard-rail anti-cores-hardcoded no **CI do develop**, matando a classe inteira de bug
(hardcode que quebra sob white-label). E registrar o débito de contraste do tema legacy.

## Entregáveis

- [ ] Guard-rail (lint/check) que **falha o CI** quando há cor hardcoded fora dos tokens do design
      system em `apps/frontend` (mesma regra que a staging já usa). Exceções explícitas só com
      anotação `// allow:` (ex.: overlays escuros sobre vídeo), como já feito na task-063.
- [ ] Rodar o guard-rail no código atual do develop e **corrigir os hardcodes remanescentes** que ele
      apontar (ou anotar `// allow:` quando legítimo).
- [ ] **Débito de contraste**: tema legacy "professional" com `textMuted` abaixo de AA em labels 11px
      — registrar (docs/quality) e, se barato, subir o token pra ≥ AA.

## Aceite

- CI do develop **falha** se alguém commitar cor hardcoded não-anotada (teste: PR de exemplo com
  `rgba(255,255,255,…)` reprova).
- Zero hardcode não-anotado no `apps/frontend` do develop.
- Débito do tema legacy documentado (e corrigido se trivial).
- Sem regressão visual (baselines dos temas escuros + o caso white-label claro da task-063).

## Referências

- task-063 (fix visual + evidência), WS1 (design system) em `docs/quality/UX_FUNCTIONAL_BACKLOG.md`,
  `apps/frontend` (tokens, statusColors.ts), guard-rail existente na staging
