# Workspace de Anotação (Qualidade) — spec visual

**Rota:** `/quality/inspections/:inspectionId/annotate` (capturado em `/quality/inspections/insp-0107/annotate`). A rota `/quality/annotation` NÃO existe (catch-all → cameras).
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityAnnotationWorkspace.tsx` · canvas: `src/modules/quality/components/AnnotationCanvas.tsx` · estilos compartilhados: `src/modules/quality/components/quality.css.ts` (`thumbStrip`, `thumbItem`) · hook: `src/modules/quality/hooks/useQualityAnnotation.ts`
**Screenshots:**

| Estado  | Dark | Light |
|---------|------|-------|
| default | `../screenshots/quality-annotation/dark-default.png` | `../screenshots/quality-annotation/light-default.png` |
| empty   | `../screenshots/quality-annotation/dark-empty.png`   | `../screenshots/quality-annotation/light-empty.png`   |

## Layout — regiões

- AppShell + submenu Qualidade (item ativo: **Inspeções**).
- Root: `display:flex; height: calc(100vh - 120px); overflow:hidden` (120px = magic number para topbar+submenu).
- **Coluna esquerda** (flex:1, padding 16, gap 12): linha de status/navegação ("Frame 1 / 8" 13px `textMuted` + botões ← Anterior / Pular (S) / Próximo →) · `AnnotationCanvas` (container `quality.css.ts#canvasContainer`: radius md, bg `bgCard`, cursor crosshair; bboxes com `pointerEvents:'none'`) · tira de thumbnails (`thumbStrip`: flex, gap xs, overflowX auto; `thumbItem` 40×30, radius sm — variantes: pending borda `borderDefault`; annotated borda `#43D186` + bg rgba(67,209,134,0.08); skipped borda `borderSubtle` opacity 0.4; active borda `#4FC3F7` + outline rgba(79,195,247,0.3)).
- **Coluna direita** (width 220, padding 16, gap 16, borderLeft `borderDefault`): seção "CLASSE ATIVA" (label 11px uppercase `textMuted` + botões de classe empilhados gap 4) · "BBOX SELECIONADA" (condicional) com botão "Remover (Del)" · progresso ("Anotados: 3 / 8" + barra 4px `success` sobre `bgCard`) · botão "Criar Job Treino" (marginTop auto) · dica "Anote ao menos 10 frames para habilitar" · bloco de atalhos (10px, `textPrimary`, lineHeight 1.8).

## Árvore de componentes

- `QualityAnnotationWorkspace`
  - Botões de navegação (`btnStyle`: radius 4, border `borderDefault`, bg transparent, texto `textSecondary` 12px)
  - `AnnotationCanvas` — imagem SVG 1280×720 + overlay de bboxes rotuladas (label pill acima da caixa: `produto_nok` vermelho, `bolha` lilás), preview de desenho, seleção por hit-test
  - Botão de classe: ativo → border/texto `c.color` + bg `{c.color}22`, 700; inativo → **border `vars.color.textPrimary`** (borda branca no dark / preta no light), bg transparent, texto `textMuted` 11px
  - Barra de progresso custom (não usa `progressBar` do quality.css.ts)
  - Botão "Criar Job Treino": habilitado → bg `#4FC3F7` texto `#000`; desabilitado → bg `bgCard` texto `textMuted`
  - `CLASS_COLORS` (0..8): `vars.color.success`, `vars.color.danger`, `#FF8A65`, `#FFB74D`, `#F06292`, `#CE93D8`, `#4FC3F7`, `#E57373`, `#FFD54F` — 7 de 9 hex fixos
  - Indicador "Salvando…" — cor `#FFB74D` hardcoded

## Copy exata

- `Frame {i} / {n}` · `Salvando…`
- Botões: `← Anterior` · `Pular (S)` · `Próximo →` · `Remover (Del)` · `Criar Job Treino` / `Criando…`
- Seções: `CLASSE ATIVA` · `BBOX SELECIONADA` · `Anotados: {a} / {t}` · `Anote ao menos 10 frames para habilitar`
- Atalhos: `A / ← anterior` · `D / → próximo` · `S — pular` · `Del — remover bbox` · `Esc — desselecionar`
- Loading: `Carregando frames…` · Erro: `{annotation.error}`
- Vazio: `Nenhum frame disponível para anotação.` + `Verifique se o clip foi gerado e o processo de extração foi concluído.`
- Erro do job: `Erro ao criar job de treinamento.` (via `alert()` nativo)
- Tooltip thumbnail: `Frame {i+1}: {status}` (status cru em inglês: annotated/skipped/pending)

## Dados de exemplo (fixtures)

- 8 frames; frame atual: SVG "insp-0107 · Câmera Bancada A close-up" com 2 bboxes: `produto_nok` (vermelho, grande à esquerda) e `bolha` (lilás, pequena à direita).
- Classes NOK: `Produto NOK` (ativa, vermelho) · `Bolha` · `Mancha` · `Montagem faltando`.
- Thumbnails: 3 annotated (verde), 1 skipped (apagada), 4 pending; 1ª ativa (ciano).
- Progresso: `annotated: 3, total: 8, can_create_job: false` → botão Criar Job desabilitado.

## Estados

- **default**: canvas com bboxes, classe Produto NOK ativa, progresso 3/8, Criar Job desabilitado + dica.
- **empty**: apenas texto de vazio no topo esquerdo — sem CTA de volta para inspeções (beco).
- **loading**: `Carregando frames…` `textMuted` padding 32.
- **erro**: texto `danger` padding 32.
- **selecionado**: seção BBOX SELECIONADA com "Remover (Del)" (borda `#EF535044`).
- **hover**: nenhum estado hover (botões inline); thumbnails só têm `cursor:pointer`.
- **interações de canvas** (bbox com handles, drag preview): não capturadas (tier 2 — deferred do builder).

## Navegação e fluxos

- ← / Pular / → navegam frames com auto-save ao trocar; atalhos A/D/S/Del/Esc.
- Click em thumbnail → `goToFrame(i)`.
- "Criar Job Treino" → `POST` job → `navigate('/quality/training')`; erro → `alert()`.
- Vazio/erro não oferecem navegação de retorno.

## Problemas identificados (resumo)

1. **Inconsistência**: botão de classe inativa usa `vars.color.textPrimary` como cor de borda — borda quase branca no dark (visualmente "acesa" para um item inativo) e quase preta no light; o resto do módulo usa `borderDefault`.
2. **Hardcode (task-065)**: `CLASS_COLORS` com 7 hex fixos, `#4FC3F7` no Criar Job, `#FFB74D` no "Salvando…", `#EF535044` na borda do Remover; `thumbItem` com `#43D186`/`#4FC3F7` no `quality.css.ts`.
3. **Contraste light**: "Salvando…" `#FFB74D` sobre `#f4f5f7` = 1.59:1 (ilegível no tema claro).
4. **Copy**: tooltip de thumbnail expõe status técnico em inglês (`annotated`/`skipped`/`pending`); erro via `alert()` nativo fora do padrão de toast/banner.
5. **Empty state** sem ação (nenhum link para voltar às inspeções).
6. **Layout**: `calc(100vh - 120px)` acoplado à altura do chrome; quebra se o AppShell mudar.
7. Paleta legada `#4FC3F7`/`#43D186` diverge da identidade Recognition (`primary` ciano #06b6d4 / `success` #10b981) — texto `#000` sobre `#4FC3F7` passa (10.48:1), mas a cor é fora do DS.

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/quality-annotation.md · screenshots analisados: dark-default, light-default, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P2 | Botão de classe **inativo** usa `vars.color.textPrimary` como border-color → borda branca no dark (parece ativo) e preta no light (estilo errado para item desmarcado). Confirmado em ambos os temas: "Bolha", "Mancha", "Montagem faltando" mostram borda branca/preta vs borda sutil `borderDefault` esperada. | PERSISTE |
| 2 | P1 | `CLASS_COLORS` com 7 de 9 valores hex fixos (`#FF8A65`, `#FFB74D`, `#F06292`, `#CE93D8`, `#4FC3F7`, `#E57373`, `#FFD54F`); botão "Criar Job Treino" habilitado usa `bg: #4FC3F7` com `color: #000`; indicador "Salvando…" usa `#FFB74D`. Viola guard-rail task-065. | PERSISTE |
| 3 | P1 | Indicador "Salvando…" em `#FFB74D` sobre `bgCard` claro (#f4f5f7) = 1.59:1 — ilegível no tema claro (não capturado mas código persiste). | PERSISTE |
| 4 | P2 | Tooltip de thumbnail expõe status técnico em inglês (`annotated`/`skipped`/`pending`). Erro ao criar job dispara `alert()` nativo em vez de toast/banner. | PERSISTE |
| 5 | P2 | Empty state (`dark-empty.png`, `light-empty.png`) exibe mensagem de orientação mas sem CTA ou link para voltar às Inspeções — dead end de navegação. | PERSISTE |
| 6 | P2 | `height: calc(100vh - 120px)` magic number acoplado ao chrome atual do AppShell — frágil a mudanças de layout. | PERSISTE |
| 7 | P3 | Paleta `#4FC3F7`/`#43D186` nos thumbItems (`quality.css.ts`) diverge dos tokens `primary #06b6d4` e `success #10b981` do DS Recognition. | PERSISTE |

**Resumo:** 0 resolvidos · 7 persistem · 0 novos. Workspace de anotação não foi incluído na migração WS1.
