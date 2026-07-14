# Task 070 — Andaime do design v3 "Centro de Comando" (Fase 0, não depende do export final)

**Status**: PENDING (Fase 0 — andaime; Fases 1+ bloqueadas pelo export final do v3)
**Risk**: P1-ALTO (toca shell/rotas/tema do frontend, mas atrás de flag OFF em prod)
**Branch**: feat/ui-v3-andaime (a partir de origin/develop, em worktree — NUNCA no checkout wip/*)
**Relaciona**: ADR-0041, ADR-0035 (feature flags + white-label)

## Objetivo

Preparar a fundação pro shell v3 SEM migrar telas e SEM depender dos pixels finais (que ainda estão
no Claude Design). Deixa o terreno pronto pra que, quando o export final chegar, a migração
workspace-a-workspace comece direto.

## Escopo (Fase 0)

1. **Feature flag `ui_v3`** (ADR-0035): global + override por tenant/usuário; default ON só em dev,
   OFF em prod. Gate no roteamento: flag ON → carrega `AppShellV3`; OFF → shell atual.
2. **Shell v3 vazio** (`components/.../AppShellV3` + rota): estrutura dos 4 workspaces
   (Operar/Investigar/Treinar/Administrar) como cascas navegáveis vazias (placeholders "em breve"),
   sem lógica de dados ainda.
3. **⌘K (command palette)** como casca: Radix dialog + input de comando + lista vazia (sem ações
   reais ainda). Só o esqueleto de abrir/fechar/navegar.
4. **Tema v3** (`styles/themes/recognition-v3.css.ts`): montar o CONTRATO/slots completos com os
   **tokens REAIS** extraídos de `docs/design/recognition-v3/Recognition-visao-final.dc.html` (dark: bgBase
   #0a0c10, bgSurface #111318, textPrimary #f0f4f8, textSecondary #8ba3bc, textMuted #5b6b7d, primary
   #06b6d4, success #10b981, warning #f59e0b, danger #ef4444, borderDefault #1e2730 + light em
   paralelo; accents cyan/amber/purple). Fontes Inter + JetBrains Mono. Preservar o
   `createThemeContract` + bridge de white-label (NÃO remover professional/cyberpunk ainda — cutover).

## NÃO fazer nesta task

- Não migrar nenhum workspace de verdade (bloqueado pelo export final).
- Não remover os temas atuais nem o shell antigo (é cutover, Fase final).
- Não hardcodar cor fora do contrato de tema (guard-rail task-065).

## Aceite

- Flag `ui_v3` funcional (ON dev / OFF prod); alternar mostra shell v3 vazio vs atual.
- 4 workspaces navegáveis como casca; ⌘K abre/fecha.
- `recognition-v3.css.ts` com contrato completo + tokens provisórios marcados.
- `npx tsc --noEmit` limpo; guard-rail de cores verde; PR pra develop.
- STOP-for-review antes de qualquer Fase 1 (migração de workspace).
