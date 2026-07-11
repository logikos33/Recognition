# Câmeras — Módulo Qualidade — spec visual

**Rota:** `/quality/cameras` (aba padrão do módulo; `/quality` redireciona para cá)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityCamerasPage.tsx`, `pages/QualityCamerasPage.css.ts`, `components/ui/Skeleton/Skeleton`, `services/qualityService.ts`
**Endpoints:** `GET /api/v1/quality/cameras`, `GET /api/v1/quality/cameras/available` (+ POST assign/unassign, PATCH config — não capturados)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/quality-cameras/dark-default.png | ../screenshots/quality-cameras/light-default.png |
| empty | ../screenshots/quality-cameras/dark-empty.png | ../screenshots/quality-cameras/light-empty.png |
| edit-config (inline) | ../screenshots/quality-cameras/dark-edit-config.png | ../screenshots/quality-cameras/light-edit-config.png |

## Layout — regiões

- Conteúdo: `padding: 24`, `maxWidth: 1200`, centralizado.
- Header: flex space-between, `marginBottom: 24` — título h1 22px/700 `textPrimary` + botão "↺ Atualizar".
- Seção 1 "Atribuídas ao módulo (N)": h2 16px/600 `textSecondary`, `marginBottom: 14`; grid `repeat(auto-fill, minmax(320px, 1fr))`, gap 16; seção com `marginBottom: 36`.
- Seção 2 "Disponíveis para adicionar (N)": grid `repeat(auto-fill, minmax(260px, 1fr))`, gap 12. **Só renderiza se `available.length > 0`.**

## Árvore de componentes

- Banner de erro (condicional): padding 12×16, bg `dangerMuted`, borda `1px danger`, radius 8, texto 13px `danger`.
- **Card de câmera atribuída** (`cameraCard`): borda `borderDefault`, radius 12, padding 16, bg `bgCard`.
  - Header: nome 14px/600 `textPrimary` + badges à direita (gap 6):
    - `Setup` (condicional `is_setup_mode`): 11px/600, bg `warningMuted`, texto `warning`, radius 20
    - `Ativa`: 11px/600, bg `successMuted`, texto `success`, radius 20
  - Modo leitura (`metaText`, 13px `textMuted`): `OP: {…|—}` / `Peça: {…|—}` / `Modelo: {…|—}`
  - Modo edição (`editStack`): 2 inputs (`editInput`: padding 7×10, radius 6, borda `borderDefault`, 13px, bg `bgSurface`, cor `textPrimary`, focus borda `primary`) + linha de ações:
    - `Salvar` (`saveBtn`): flex 1, bg `primary`, **cor `bgBase`**, radius 6, 13px/600, hover `primaryLight`, disabled opacity .5
    - `Cancelar` (`cancelBtn`): borda `borderDefault`, bg `bgCard`, 13px `textSecondary` (sem hover)
  - Ações do card: `Editar config` (flex 1, borda `borderDefault`, bg `bgCard`, 12px `textSecondary`, hover `bgHover`) + `Remover` (borda `danger`, bg `dangerMuted`, 12px `danger`, sem hover)
- **Card disponível** (`availableCard`): borda `borderDefault`, radius 10, padding 14×16, bg `bgSurface`, flex space-between — nome 13px/600 `textSecondary` + botão `+ Adicionar` (`addBtn`: borda `primary`, bg `primaryAlpha`, 12px/600 `primary`; hover redefine o MESMO `primaryAlpha` = sem efeito).
- **Skeleton (loading)**: header com `Skeleton title 240` + `rect 100×32`; grid com 4 cards contendo `text 60%`, `text 80%`, `rect 100%×32`.

## Copy exata

- Título: `Câmeras — Módulo Qualidade` · botão `↺ Atualizar`
- Seções: `Atribuídas ao módulo ({N})` · `Disponíveis para adicionar ({N})`
- Empty: `Nenhuma câmera atribuída. Adicione uma câmera disponível abaixo.`
- Badges: `Setup` · `Ativa`
- Meta: `OP: {valor|—}` · `Peça: {valor|—}` · `Modelo: {valor|—}`
- Placeholders inputs: `Ordem de produção` · `Tipo de peça`
- Botões: `Editar config` · `Remover` · `Salvar` / `Salvando...` · `Cancelar` · `+ Adicionar`
- Erros (catch): `Erro ao carregar câmeras` · `Erro ao atribuir câmera` · `Erro ao remover câmera` · `Erro ao salvar configuração`

## Dados de exemplo (fixtures)

Atribuídas (4): **Câmera Bancada A — Overview** (Ativa; OP-2026-0142, Chicote 12V, mdl-quality-v4) · **Câmera Bancada A — Closeup** (Setup + Ativa; OP-2026-0142, Chicote 12V, modelo —) · **Câmera Bancada B — Overview** (Ativa; OP-2026-0139, Chicote 24V, mdl-quality-v4) · **Câmera Pátio Norte — Retrabalho** (Ativa; OP/Peça/Modelo —).
Disponíveis (3): **Câmera Doca 3 — Expedição** · **Câmera Linha 2 — Solda** · **Câmera Almoxarifado**.
Edit-config (card 1): OP `OP-2026-0155`, peça `Chicote 48V blindado`.

## Estados

- **default**: 4 cards atribuídos + 3 disponíveis.
- **empty**: texto `emptyText` 14px `textMuted`; seção "Disponíveis" oculta (fixture vazio).
- **loading**: skeletons (título + 4 cards).
- **edit-config**: card troca meta por 2 inputs + Salvar/Cancelar; demais cards inalterados.
- **saving**: botão vira `Salvando...`, disabled opacity .5.
- **erro**: banner vermelho acima das seções.
- **hover**: presente em `↺ Atualizar` (bgHover), `Editar config` (bgHover), `Salvar` (primaryLight); AUSENTE em `Remover`, `Cancelar`; NO-OP em `+ Adicionar`.

## Navegação e fluxos

- `↺ Atualizar` → recarrega ambas as listas.
- `Editar config` → edição inline no card (não é modal).
- `Salvar` → `PATCH updateCameraConfig` → fecha edição e recarrega.
- `Remover` → `unassignCamera` → recarrega (sem confirmação!).
- `+ Adicionar` → `assignCamera` → recarrega.

## Problemas identificados

1. **P1 light (task-063 por token não-tematizado)**: `Salvar` usa `color: vars.color.bgBase` sobre `primary` — no claro `#f4f5f7` sobre `#06b6d4` = **2.23:1** (dark passa com 8.06:1) (QualityCamerasPage.css.ts:147-159). Usar `textOnPrimary` fixo escuro ou par calculado.
2. **P1 light**: badge `Ativa` — `success #10b981` sobre `successMuted` sobre card claro = **2.00:1** (dark 5.93:1) (css.ts:109-116). Badge `Setup` (warning) ≈ 1.9:1 no claro (css.ts:100-107).
3. **P1 light**: `+ Adicionar` — `primary #06b6d4` sobre `primaryAlpha` claro = **2.22:1** (dark 6.67:1) (css.ts:214-224).
4. **P2 light**: `Remover` — `danger` sobre `dangerMuted` claro = **2.84:1** (dark 4.23:1) (css.ts:188-196).
5. **P2 hover**: `addBtn` define `:hover { background: primaryAlpha }` idêntico ao estado base — hover no-op; `removeBtn` e `cancelBtn` sem hover (css.ts:161-169, 188-196, 223).
6. **P2 copy/UX**: empty diz "Adicione uma câmera disponível abaixo", mas a seção "Disponíveis" não renderiza quando vazia — beco sem saída (QualityCamerasPage.tsx:108-110 + 173).
7. **P2 UX**: `Remover` desatribui a câmera sem diálogo de confirmação (QualityCamerasPage.tsx:44-51).
8. **P3**: erros de catch genéricos, sem instrução de recuperação além do texto.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063 (tokenização TrainingModeLayout/RoiDrawer), task-065 (guard-rail CI), WS1 design system (d7a3ad3 ~70 telas).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P1 light | `Salvar` usa `color: bgBase` sobre `primary` claro = 2.23:1 — ilegível no light-edit-config (light-edit-config.png mostra botão teal com texto claro; correção não confirmada em código) | PERSISTE |
| 2 | P1 light | Badges `Ativa` (success 2.00:1) e `Setup` (warning ~1.9:1) sobre superfície clara — visíveis no light-default.png mas abaixo de WCAG AA | PERSISTE |
| 3 | P1 light | `+ Adicionar` primary sobre primaryAlpha claro = 2.22:1 — pills ciano sobre branco visíveis no light-default.png mas falham AA | PERSISTE |
| 4 | P2 light | `Remover` danger sobre dangerMuted claro = 2.84:1 | PERSISTE |
| 5 | P2 | hover no-op em `addBtn`; `removeBtn` e `cancelBtn` sem hover | PERSISTE |
| 6 | P2 | Empty copy "abaixo" enquanto seção Disponíveis não renderiza | PERSISTE |
| 7 | P2 | `Remover` sem confirmação | PERSISTE |
| 8 | P3 | Erros genéricos de catch | PERSISTE |

**Resumo develop:** 0 resolvidos · 8 persistem · 0 novos. Nenhum dos problemas desta tela estava no escopo de task-063/065/WS1.
