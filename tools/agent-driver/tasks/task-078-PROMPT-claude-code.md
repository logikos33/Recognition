# Prompt de handoff — Claude Code · task-078

> Copie o bloco abaixo para o Claude Code executar a task-078.
> Companion da spec: `tools/agent-driver/tasks/task-078-transparent-container-audit-fix.md`.

```
Implemente a task-078 (auditoria e fix dos containers/overlays transparentes sem fundo — onda de restyle WS1).

LEIA PRIMEIRO:
1. tools/agent-driver/tasks/task-078-transparent-container-audit-fix.md (a spec — traz o inventário já auditado, com file:line)
2. constitution.md e a seção "CORREÇÕES CRÍTICAS ao CLAUDE.md" do docs/HANDOFF_CONTINUIDADE.md
   (frontend = apps/frontend/, produção = staging, C-04 = validar o código real antes de mudar)
3. O padrão correto: apps/frontend/src/components/ui/Modal/Modal.css.ts (overlay + content bgElevated opaco)

SETUP:
- Worktree novo a partir de origin/develop (NUNCA no checkout wip/*). git fetch antes.

ESCOPO (nesta ordem, conforme a spec):
1. CONFIRMADO: components/cameras/CameraFpsConfig.tsx — container :76 rgba(255,255,255,0.04) → fundo opaco de
   token (ui/Panel card/elevated ou vars.color.bgCard + borda borderDefault); labels :91/:120 → textSecondary/
   textMuted; botões :99-114/:128-143 → estado não-selecionado opaco + :hover com bgHover; trocar #c4b5fd,
   rgba(167,139,250,0.18), #ef4444, #f59e0b por tokens. (fecha task-063)
2. Tokenizar os painéis internos rgba(255,255,255,0.03-0.05) listados na spec (TrainingPage, AnnotationPage,
   ModelScenarioWizard, AnnotationInterface.jsx) → bgSurface/bgCard. NÃO tocar MonitoringPage.css.ts:251 (exceção).
3. Migrar/tokenizar os modais TODO-WS1 (priorizar os #1a1d23: AlertsHistoryPage, EpiInvestigation) reusando ui/Modal.
- NÃO tocar nos itens marcados OK na spec; NÃO tocar em .jsx.backup.

DISCIPLINAS:
- Reusar ui/Modal / ui/AppDrawer / ui/Panel — não recriar overlay. Fundo sempre de token (bgElevated/bgSurface/bgCard).
- Zero rgba(255,255,255,0.0x) de container e zero hex cru de fundo/borda no escopo tocado (coerente com o guard-rail
  da task-065). White-label preservado: cores vêm de tokens, nunca hardcoded.
- Contraste WCAG AA em texto sobre fundo.

ACEITE / ENTREGA:
- Nenhum overlay abre transparente; CameraFpsConfig legível com hover e botão Salvar visível.
- tsc --noEmit limpo; guard-rail 065 verde; sem regressão nos itens OK.
- Screenshot ANTES/DEPOIS de cada tela tocada (o harness de front 021 tira screenshots — use-o).
- Atualizar docs/quality/UX_FUNCTIONAL_BACKLOG.md (WS1) e marcar task-063 e task-066 como resolvidas por esta.
- Conventional commits. PR para develop. risk:security → STOP-for-review: NÃO faça merge nem promova pra staging/main.
- Se alguma premissa da spec não bater com o código real, PARE e reporte.
```
