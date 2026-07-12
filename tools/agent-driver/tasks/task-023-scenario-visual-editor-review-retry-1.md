---
title: "Editor visual de cenário (desenhar ROI/linha/zona na câmera)"
pr_title: "feat(frontend): editor visual de cenário — desenhar ROI/linha/zona + módulo/classes/regra"
commit_message: "feat(frontend): editor visual de cenário (overlay de desenho + config + salvar via API)"
eval: default
budget_minutes: 90
risk: low
---

# Tarefa 023 — Editor visual de cenário (frontend)

## Objetivo
Tela onde o operador **desenha o cenário sobre a imagem da câmera**: escolhe módulo → desenha ROI/linha/zona
→ escolhe classes + regra + agenda → salva. Consome a API de cenário (task-022) e escreve via o CRUD de
`operations` existente. Frontend; sem hardware, sem migration. Ver `docs/architecture/PLATAFORMA_CENARIOS.md`.
**Depende de:** task-021 (harness de teste de front) e task-022 (API de cenário) mergeadas.

## Contexto (LER antes — C-04)
- apps/frontend (React 18 + TS strict + Vite; Zustand; Radix; HLS.js). Padrões do projeto (componentes pequenos, sem any).
- task-022: GET /cameras/<id>/scenario e GET /scenarios/operation-types. CRUD existente em operations (POST/PUT) pra salvar.
- task-021: usar Vitest/RTL (componente) + Playwright (e2e).

## Comportamento / boas práticas de front
- Mostrar um frame da câmera (still/HLS snapshot) com **overlay de desenho** (canvas ou SVG):
  ferramentas **zona (polígono)**, **linha** e **ponto**, escolhidas conforme o operation-type.
- Escolher módulo → o editor carrega classes + o schema de config do tipo (de task-022) e mostra os campos certos.
- Definir classes a vigiar + regra de alerta + agenda. Salvar → grava a `config` (geometria + params) via operations API; versiona.
- **UX:** undo/redo do desenho, feedback de salvamento, estados de loading/erro. **Acessibilidade:** teclado +
  ARIA nas ferramentas, contraste. Tenant vem do JWT (nunca do front).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- apps/frontend/ (componentes do editor, store Zustand, chamadas à API, testes)
- NÃO criar endpoint novo de backend — usar task-022 (read) + operations CRUD (write) existentes.

## Eval (default + harness de front da task-021) — testes SÃO o critério
- **Vitest/RTL:** componente do editor renderiza; trocar de módulo troca ferramentas/classes; estados de loading/erro.
- **Playwright e2e:** abrir o editor, desenhar uma linha/zona, salvar, recarregar → cenário persiste (geometria volta).
- **Validação de UX (parte do "concluído"):** rodar o editor, **tirar screenshot, revisar e anotar melhorias**
  (ergonomia do desenho, snap, undo/redo, feedback) num comentário do PR. Se algo estiver ruim de usar, ajustar.
- tsc + lint verdes.

## Critérios de aceitação
- [ ] Editor desenha ROI/linha/zona sobre o frame e salva via operations API (config versionada).
- [ ] Módulo escolhido carrega ferramentas + classes + schema de config certos (de task-022).
- [ ] Testes Vitest + Playwright (incl. desenhar→salvar→persistir) verdes; tsc + lint verdes.
- [ ] Acessibilidade (teclado/ARIA/contraste) + estados loading/erro + undo/redo.
- [ ] Nota de validação de UX no PR (screenshot + melhorias). PR para develop.

## NEEDS CLARIFICATION
- Se não houver um "still/snapshot" pronto da câmera no front, usar um frame do HLS ou um placeholder de
  imagem em dev — NÃO bloquear o editor por causa do stream real; reportar a decisão.

## Checkpoint
- Só PR (humano revisa — feature de front; eu olho a UX/screenshots). Sem produção. Sem migration.

---

# Feedback do Revisor Adversarial (retry 1)

O revisor encontrou os seguintes problemas — corrija TODOS antes de finalizar:

## Findings

- [HIGH] Playwright E2E tests missing (spec acceptance criterion): The spec explicitly requires: 'Playwright e2e: abrir o editor, desenhar uma linha/zona, salvar, recarregar → cenário persiste (geometria volta).' No Playwright test file exists. This is listed as an acceptance criterion: 'Testes Vitest + Playwright (incl. desenhar→salvar→persistir) verdes.' The PR cannot be considered complete without this.
- [MEDIUM] DrawingCanvas has zero dedicated unit tests: ScenarioEditor.test.tsx exists (12 tests) but covers only the sidebar/config UI. DrawingCanvas — the most complex and interactive component (285 lines: click-to-add-points, undo/redo keyboard shortcuts, tool switching, hover preview, SVG rendering of existing operations) — has no dedicated test file. The single assertion 'DrawingCanvas está presente no editor' only checks mount, not behavior. Core interactions (clicking adds normalized points, zone closure at 0.03 threshold, line reset after 2 points, undo/redo via Ctrl+Z) are untested.
- [MEDIUM] JWT token leaked in HLS URL query parameter: EpiScenarioEditorPage.tsx:24-25 constructs hlsUrl with the full JWT as a query parameter: `?token=${token}`. This exposes the long-lived JWT in server access logs, proxy/CDN logs, browser network tab, and potentially Referer headers. While this follows the existing HLS pattern in the codebase (documented as a known limitation in CLAUDE.md), this PR extends the pattern to a new page. A short-lived, scoped token or signed URL would limit blast radius if logs are compromised.
- [LOW] NaN can be sent as threshold parameter to API: ScenarioEditor.tsx:360: `Number(e.target.value)` produces NaN when the input is cleared (empty string). This NaN is stored in `params.threshold` and would be serialized as `null` in JSON, sent to the backend via createOperation. Frontend should guard: `const n = Number(e.target.value); if (!isNaN(n)) setParams(...)` or clamp to a minimum.
- [LOW] Unbounded undo history array: ScenarioEditor.tsx:70-76: pushHistory appends to history without any cap. Pathological user clicking thousands of times grows the array indefinitely. Practical risk is near-zero for a drawing tool, but a cap (e.g., 100 entries) would be trivially cheap insurance.

## Testes propostos (adicionar ao PR)

- DrawingCanvas unit test: clicking the canvas with tool='zone' adds normalized [0,1] points; clicking near the first point (distance < 0.03) does NOT add a new point (zone closure)
- DrawingCanvas unit test: tool='line' resets points to [newPt] when clicking after 2 points already exist
- DrawingCanvas unit test: tool='point' always replaces with a single point on click
- DrawingCanvas unit test: Ctrl+Z fires onUndo, Ctrl+Shift+Z fires onRedo, and the callbacks propagate correctly
- DrawingCanvas unit test: existing operations render SVG elements (polygon for ≥3 pts, line for 2, circle for 1) with correct status colors
- Playwright E2E: navigate to /epi/cameras/:id/scenario, select module, select operation type, click canvas 3+ times to draw a zone, fill name, save → verify operation appears in the sidebar list
- Playwright E2E: after saving, reload the page → verify the saved operation's geometry is rendered as an existing operation overlay on the canvas
- Playwright E2E: verify that an unauthenticated user is redirected to /login when accessing /epi/cameras/:id/scenario
- ScenarioEditor unit test: clearing the threshold input and saving sends a valid config (no NaN)
- ScenarioEditor unit test: undo after drawing 3 points reduces visible points to 2; redo restores to 3
