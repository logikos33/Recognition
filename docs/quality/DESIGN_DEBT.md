# Design Debt — Registro (task-065)

Registro de débitos de design system / acessibilidade visual. Atualizar a cada correção.

## Guard-rail anti-cores-hardcoded (CI do develop)

- **Arquivo**: `apps/frontend/src/theme/__tests__/no-offbrand-colors.test.ts`
- **Roda em**: job "Frontend tests" do `.github/workflows/ci.yml` (`npm run test` → `vitest run`)
- **Regras**: backgrounds claros hardcoded, azuis/violet fora da marca, `rgba(0,0,0,x)` hand-rolled
  e — adicionado na task-065 — `rgba(255,255,255,x)` hand-rolled (classe do bug da task-063:
  invisível sob superfícies claras de white-label).
- **Exceções**: marcador inline `// allow: <justificativa>` (overlays sobre vídeo/canvas, sandbox
  de branding), `TODO-WS1` (baseline congelada) e ALLOWLIST de arquivos no próprio teste.

## Contraste — tema legacy `professional` (CORRIGIDO na task-065)

- **Problema**: `textMuted: #71717a` sobre `bgSurface: #13131a` = **3.83:1**, abaixo de
  WCAG AA (4.5:1) para labels pequenos (11–13px). Sobre `bgCard #20202a` era pior: 3.34:1.
- **Correção**: token subido para `#8a8a93` em
  `apps/frontend/src/styles/themes/professional.css.ts`:
  - 5.40:1 sobre `bgSurface #13131a` (AA ok)
  - 4.72:1 sobre `bgCard #20202a` (AA ok)
  - Hierarquia preservada: continua abaixo de `textSecondary #a1a1aa` (7.21:1).

## Débitos remanescentes (não corrigidos — anotar para sprint de qualidade)

1. **`professional.textDim: #52525b`** — 2.39:1 sobre `bgSurface`. Uso é decorativo/desabilitado,
   mas onde carregar texto informativo precisa subir para ≥4.5:1 ou trocar por `textMuted`.
2. **`recognition-dark.textMuted: #668096`** — 4.51:1 sobre `bgSurface #111318`: passa AA por
   margem mínima (0.01). Qualquer escurecimento do token ou uso sobre `bgCard`/`bgElevated`
   derruba abaixo de AA. Considerar clarear ~1 step no próximo ajuste de paleta.
3. **Cores de status em rgba fixo** (ex.: `rgba(34,197,94,x)` verde em ternários de
   TrainingPage/AnnotationPage parcialmente convertidos na task-065) — os casos flagrados pelo
   guard-rail foram tokenizados (`success`/`successMuted`); rgba de status remanescentes não
   disparam o guard-rail mas devem migrar para `successMuted`/`dangerMuted` etc. no WS1.
