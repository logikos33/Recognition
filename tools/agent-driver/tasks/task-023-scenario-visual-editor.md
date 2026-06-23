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
