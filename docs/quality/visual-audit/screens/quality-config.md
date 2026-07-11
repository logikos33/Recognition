# Configurações — Quality Gate — spec visual

**Rota:** `/quality/config` (lazy via Suspense, fallback null)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityConfigPage.tsx` (100% estilos inline), `types/gate.ts`, `services/api.ts`
**Endpoints:** `GET /api/v1/quality/gate/stations` (+ POST/PATCH stations; `PATCH /v1/quality/gate/config` existe no handler mas o GET de config **nunca é chamado**)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/quality-config/dark-default.png | ../screenshots/quality-config/light-default.png |
| empty | ../screenshots/quality-config/dark-empty.png | ../screenshots/quality-config/light-empty.png |
| modal-adicionar-estacao | ../screenshots/quality-config/dark-modal-adicionar-estacao.png | ../screenshots/quality-config/light-modal-adicionar-estacao.png |

## Layout — regiões

- Conteúdo: `padding: 24`, `maxWidth: 900`, centralizado.
- Título h1 24px/700 `textPrimary`, `marginBottom: 24`.
- Seção "Estações (Bancadas)": header flex space-between (h2 18px/600 + botão primário) `marginBottom: 16`; cards de estação empilhados em coluna, gap 16.
- Seção "Parâmetros de Inspeção": **código morto — nunca renderiza** (gated por `editConfig`, que nunca é populado; nenhum GET de config no mount).
- Modal "Adicionar estação": overlay `fixed inset 0` bg `vars.color.overlay` (rgba(0,0,0,0.7)), zIndex 1000, flex center; caixa 480px, bg `bgCard`, radius 16, padding 32, `boxShadow: 0 20px 60px rgba(0,0,0,0.2)` (hardcoded).

## Árvore de componentes

- Banner de erro (condicional): bg `dangerMuted`, radius 8, texto `danger`.
- Botão **`+ Adicionar estação`**: padding 8×16, radius 8, bg `primary`, cor `textOnPrimary` (#ffffff), 14px/600, sem hover.
- **Card de estação**: bg `bgSurface`, borda `borderDefault`, radius 12, padding 20.
  - Header: título 16px/700 `textPrimary` (label amigável por código: `Bancada A — V1 e V2` / `Bancada B — V3`) + subtítulo 12px `textSecondary` (station_code) | direita: pill de status + botão `Editar` (borda `borderDefault`, bg `bgCard`, 13px `textPrimary`).
    - Pill `Ativa`: bg **`#D1FAE5`** texto **`#059669`** (hardcoded, mesmos nos 2 temas), radius 20, 12px/600.
    - Pill `Inativa`: bg `bgSurface` (idêntico ao card → pill invisível), texto `textSecondary`.
  - Grid 2 colunas (gap 16) de campos: `Nome da estação`, `Controlador de torre`, `Câmera overview (ID)`, `Câmera closeup (ID)`. Leitura: 14px `textPrimary` (`Não configurada` em `textMuted`). Edição: inputs/select com borda `primary`, bg `bgCard`, 14px — **sem `color` definido** (texto preto do UA no tema dark).
  - Ações da edição: `Cancelar` (borda `borderDefault`, bg `bgCard`, `textSecondary`) + `Salvar` (bg `primary`, **cor `textPrimary`**; saving → bg `textSecondary`).
- **Empty**: box `2px dashed borderDefault`, radius 12, bg `bgSurface`, padding 32, texto 14px `textMuted` + botão `Criar primeira estação` (borda `primary`, bg `primaryAlpha`, texto `primary` 14px/600).
- **Modal**: h3 18px/700; campos `Nome *` (autoFocus), `Código *` (monospace; transforma para snake_case; helper 12px `textMuted`), select `Controlador de torre` (GPIO/Modbus/MQTT/Simulado); rodapé `Cancelar` + `Criar estação` (bg `primary`, cor `textPrimary`; disabled → bg `textMuted`).

## Copy exata

- Título: `Configurações — Quality Gate` · loading: `Carregando configurações...`
- Seção: `Estações (Bancadas)` · botão `+ Adicionar estação`
- Labels de card: `Nome da estação` · `Controlador de torre` · `Câmera overview (ID)` · `Câmera closeup (ID)` · `Não configurada` · pills `Ativa`/`Inativa` · botões `Editar`, `Cancelar`, `Salvar`/`Salvando...`
- Labels amigáveis: `Bancada A — V1 e V2` · `Bancada B — V3`
- Empty: `Nenhuma estação configurada.` + `Criar primeira estação`
- Modal: `Adicionar estação` · `Nome *` (placeholder `Ex: Bancada A`) · `Código *` (placeholder `Ex: bench_a`; helper `Identificador único da estação. Use snake_case.`) · `Controlador de torre` (opções `GPIO (Raspberry Pi)`, `Modbus TCP`, `MQTT`, `Simulado (teste)`) · `Cancelar` · `Criar estação`/`Criando...`
- Seção morta (nunca visível): `Parâmetros de Inspeção` · `Padrão OCR (Regex)` · `Threshold V1/V2/V3 (votação)` · `Frames por Validação` · `Confiança Mínima YOLO` · `Salvar Configurações` · `✓ Configurações salvas` + helpers.
- Erros: `Não foi possível carregar as estações.` · `Erro ao salvar configurações.` · `Erro ao salvar estação.` · `Erro ao criar estação.`

## Dados de exemplo (fixtures)

| Estação | Código | Status | Nome | Controlador | Overview cam | Closeup cam |
|---|---|---|---|---|---|---|
| Bancada A — V1 e V2 | bench_a | Ativa | Bancada A — Montagem | gpio | a1b2c3d4-0001-4bcd-9e01-camera000001 | a1b2c3d4-0002-4bcd-9e01-camera000002 |
| Bancada B — V3 | bench_b | Inativa | Bancada B — Acabamento | modbus | a1b2c3d4-0003-4bcd-9e01-camera000003 | Não configurada |

Modal preenchido: Nome `Bancada C — Inspeção Final`, Código `bench_c`, Controlador `GPIO (Raspberry Pi)`.

## Estados

- **default**: 2 cards de estação; seção de parâmetros ausente.
- **empty**: box tracejado com CTA (bom padrão de empty state).
- **loading**: apenas texto `Carregando configurações...` (sem skeleton).
- **edição inline**: campos viram inputs com borda `primary`; botões Cancelar/Salvar aparecem.
- **modal**: overlay 0.7 + caixa opaca (backdrop presente — sem defeito 066).
- **saving/criando**: botão muda label e bg (`textSecondary`/`textMuted`).
- **hover**: NENHUM botão da página define hover.

## Navegação e fluxos

- `+ Adicionar estação` / `Criar primeira estação` → abre modal.
- Overlay click (fora da caixa) → fecha modal.
- `Criar estação` → POST → adiciona card e fecha.
- `Editar` → edição inline; `Salvar` → PATCH `/v1/quality/gate/stations/{code}`.
- Não há botão para excluir estação nem toggle direto de Ativa/Inativa (o pill não é interativo).

## Problemas identificados

1. **P0 dark**: inputs/select (modal + edição inline + seção de config) definem `background: bgCard` sem `color` — texto digitado renderiza **preto do UA sobre `#161a20` = 1.20:1**, ilegível (confirmado por pixel-sampling em dark-modal-adicionar-estacao.png) (QualityConfigPage.tsx:276-279, 299-302, 329-334, 356-361, 632-637, 655-659, 678-681).
2. **P1**: seção inteira `Parâmetros de Inspeção` é código morto — `editConfig` nunca é carregado (nenhum `GET /v1/quality/gate/config` no mount); operador não consegue ajustar OCR/thresholds pela UI (QualityConfigPage.tsx:56, 71-86, 404).
3. **P1 dark**: `Salvar` (estação) e `Criar estação` usam `color: vars.color.textPrimary` sobre `primary` → dark `#f0f4f8` sobre `#06b6d4` = **2.20:1** (light passa 6.95:1). Trocar por `textOnPrimary` com par AA (QualityConfigPage.tsx:389, 587, 707).
4. **P1 both**: `+ Adicionar estação` usa `textOnPrimary #ffffff` sobre `primary #06b6d4` = **2.43:1** nos dois temas — o próprio token `textOnPrimary` falha AA sobre `primary` (QualityConfigPage.tsx:182).
5. **P2 hardcode (task-063/065)**: pill `Ativa` `#D1FAE5`/`#059669` fixos (3.32:1, falha para 12px) e inconsistentes com o padrão `successMuted`/`success` usado em Câmeras (QualityConfigPage.tsx:239-240).
6. **P2**: pill `Inativa` com bg `bgSurface` sobre card `bgSurface` — pill sem forma visível (QualityConfigPage.tsx:239).
7. **P2**: `boxShadow: '0 20px 60px rgba(0,0,0,0.2)'` hardcoded — usar `vars.shadow.lg` (QualityConfigPage.tsx:610). Modal ad-hoc fora do padrão ADR-0023 (comentário TODO-WS1 na linha 602).
8. **P2**: nenhum hover em botões; loading sem skeleton (inconsistente com Câmeras).
9. **P3**: botão saving usa `bg: textSecondary` (cor de texto como fundo) — semanticamente errado.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063 (tokenização TrainingModeLayout/RoiDrawer), task-065 (guard-rail CI), WS1 design system (d7a3ad3 ~70 telas).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | ~~P0 dark~~ | ~~inputs/select sem `color` — texto UA preto sobre `#161a20` = 1.20:1~~ | **RESOLVIDO** — develop: texto nos inputs do modal dark aparece legível (branco/claro) nos screenshots `dark-modal-adicionar-estacao.png`; WS1 (d7a3ad3) provavelmente adicionou `color: textPrimary` nos inputs. Confirmar em código. |
| 2 | P1 | Seção `Parâmetros de Inspeção` é código morto — `editConfig` nunca carregado | PERSISTE |
| 3 | P1 dark | `Salvar`/`Criar estação` usa `textPrimary` sobre `primary` = 2.20:1 no dark | PERSISTE |
| 4 | P1 both | `+ Adicionar estação` `textOnPrimary #fff` sobre `primary` = 2.43:1 ambos os temas | PERSISTE |
| 5 | P2 hardcode | pill `Ativa` `#D1FAE5`/`#059669` fixos, 3.32:1 (falha 12px), inconsistente com padrão | PERSISTE |
| 6 | P2 | pill `Inativa` invisível (bg=bgSurface sobre card bgSurface) — confirmado em dark-default.png | PERSISTE |
| 7 | P2 | `boxShadow` hardcoded; modal ad-hoc com TODO-WS1 | PERSISTE |
| 8 | P2 | Sem hover em botões; loading sem skeleton | PERSISTE |
| 9 | P3 | Saving usa `bg: textSecondary` semanticamente errado | PERSISTE |

**Resumo develop:** 1 resolvido (P0 dark inputs) · 8 persistem · 0 novos.
