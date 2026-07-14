# Task 063 — Fix visual: painel de ajustes de vídeo em Operação (ilegível / sem container)

**Status**: DONE — resolvida por `ff819d0`/`0d1a5db` (fix(frontend): task-063 — painel de ajustes de
vídeo na identidade visual), antes da auditoria da task-078. `CameraFpsConfig.css.ts` usa
`vars.color.bgCard`/`borderDefault`/tokens de estado+hover; evidência em
`docs/quality/evidence/task-063/`. Confirmada via re-auditoria de código na task-078 (2026-07-14) —
status desta ficha estava desatualizado.
**Risk**: P1-ALTO (bloqueia o uso do painel — não dá pra ler nem aplicar ajustes)
**Branch**: fix/task-063-operation-video-panel-visual

## Contexto (reportado em uso real — 2026-07-06)

Fluxo: **Câmeras → seleciona câmera → Operação → ajustes de vídeo**. O painel de ajustes está
**preto, sem fundo de container**: não dá pra ler os rótulos, não dá pra ver o botão **Aplicar**, e
não há **feedback de hover** — o usuário não consegue operar. É um bug de contraste/estilo naquele
painel (texto escuro sobre fundo escuro / container sem background). Relacionado ao **WS1** do
`docs/quality/UX_FUNCTIONAL_BACKLOG.md` (containers fora da identidade visual).

## Escopo

- Painel de **ajustes de vídeo na tela de Operação** (por câmera) — provavelmente ligado a
  task-039/040 (per-camera tuning) e WS10 (FPS em operação).

## Fixes

- **Container com fundo**: aplicar background do design system (não preto/transparente), com contraste
  adequado (WCAG AA) entre texto e fundo — todos os rótulos legíveis.
- **Botão "Aplicar" visível**: cor/estilo do design system, claramente clicável.
- **Hover states**: todo elemento interativo (campos, opções, botões, itens da lateral) muda de
  coloração no hover pra indicar onde o mouse está.
- **Lateral**: corrigir o bug visual dos itens laterais (ilegíveis) — mesmo tratamento de contraste.
- Usar **tokens/cores da marca** (não hardcode preto). Reaproveitar o componente de Container/Drawer
  com tema (WS1) se existir; se não, alinhar com o padrão do design system.

## Aceite

- Todos os rótulos e valores do painel de ajustes **legíveis** (contraste AA).
- Botão **Aplicar** visível e clicável; ação funciona.
- **Hover** perceptível em todos os controles e nos itens da lateral.
- Container com **fundo** coerente com a identidade visual (não preto solto).
- `tsc --noEmit` limpo; sem regressão nas outras telas que usam o mesmo componente.
- Screenshot antes/depois como evidência. PR develop. Gate humano pra staging.

## Referências

- `docs/quality/UX_FUNCTIONAL_BACKLOG.md` (WS1 design system, WS10 FPS em operação)
- task-039 / task-040 (per-camera tuning), `apps/frontend` (tela de Operação / painel de ajustes)
