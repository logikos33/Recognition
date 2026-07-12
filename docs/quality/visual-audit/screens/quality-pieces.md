# Peças — Quality Gate — spec visual

**Rota:** `/quality/pieces` (lazy via Suspense)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityPiecesPage.tsx` (100% estilos inline), `types/gate.ts`, `services/api.ts`
**Endpoints:** `GET /api/v1/quality/gate/pieces?page&per_page[&status&date&work_order]`, `GET /api/v1/quality/gate/pieces/{id}` (detalhe no expand). Foto final: URL montada com `API_BASE` local (fallback `http://localhost:5001`) — divergente do wrapper `api.ts`.
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/quality-pieces/dark-default.png | ../screenshots/quality-pieces/light-default.png |
| empty | ../screenshots/quality-pieces/dark-empty.png | ../screenshots/quality-pieces/light-empty.png |
| expanded-detalhe | ../screenshots/quality-pieces/dark-expanded-detalhe.png | ../screenshots/quality-pieces/light-expanded-detalhe.png |

## Layout — regiões

- Conteúdo: `padding: 24`, `maxWidth: 1400`, centralizado.
- Título h1 24px/700, `marginBottom: 24`.
- Filtros: flex gap 12 wrap, align flex-end — Status (select ≥180px) · Data (date) · Ordem de Produção (text ≥200px) · `Limpar filtros` (só aparece com filtro ativo). Labels 12px/500 `textSecondary`; controles padding 8×12, radius 8, borda `borderDefault`, bg `bgCard`, 14px.
- Tabela como grid CSS: container bg `bgCard`, borda `borderDefault`, radius 12; header grid `1fr 1fr 1.5fr 1fr 1fr 0.8fr`, bg `bgSurface`, 12px/600 uppercase `textSecondary`, letterSpacing .5.
- Painel expandido: bg `bgSurface`, padding 16×24, flex gap 32 wrap — colunas Informações / Retrabalhos / Foto Final.
- Paginação (se total > 20): flex à direita, gap 8.

## Árvore de componentes

- Filtros (3 + botão condicional `Limpar filtros`).
- Loading: texto `Carregando peças...` 14px `textSecondary` (sem skeleton).
- Erro: box `danger` sobre `dangerMuted`, radius 8.
- **Linha de peça** (grid 6 colunas, clicável, borda inferior `borderDefault`; expandida → bg `primaryAlpha`):
  - `piece_number` 600 `textPrimary` · `work_order` 13px `textSecondary` · **pill de status** (padding 3×10, radius 20, 12px/600, `color` = STATUS_COLOR, bg = `STATUS_COLOR + '20'`) · retrabalhos (`{N}x` em `warning` ou `—`) · iniciada/concluída 13px `textSecondary`.
  - STATUS_COLOR: idle/`textSecondary`, identified/`primary`, validating_v1-3/`warning`, rework_v1-3/`danger`, waiting_bench_b/`primaryDark`, approved/`success`, **rejected/`#991B1B` (hardcoded)**.
  - STATUS_LABEL: Aguardando · Identificada · V1/V2/V3 Analisando · Retrabalho V1/V2/V3 · Aguardando Bancada B · Aprovada · Rejeitada.
- **Painel expandido**:
  - `INFORMAÇÕES` (12px/600 uppercase `textSecondary`): `Tipo:` · `Operador:` · `Bancada:` · `Wiser:` (`✓ Exportado` em `success` | `Pendente` em `warning`).
  - `RETRABALHOS ({N})`: linhas com pill container bg `bgCard`, borda `borderDefault`, radius 6 — `V1`/`V2` 600 `warning` + defeito `textPrimary` + `#{tentativa}` + duração (`3m 30s`) em `textSecondary`.
  - `FOTO FINAL` (se `photo_quality_path`): img ≤200×150, radius 6, borda `borderDefault`.
  - Fallbacks: `Carregando detalhes...` · `Sem detalhes disponíveis.`
- Paginação: `{total} peças · página {p} de {N}` 13px `textSecondary` + `← Anterior`/`Próxima →` (bg `bgCard`, borda `borderDefault`; **disabled: cor = `vars.color.borderDefault`**).

## Copy exata

- Título: `Peças — Quality Gate`
- Filtros: `Status` (opção `Todos` + 11 status) · `Data` · `Ordem de Produção` (placeholder `Ex: OP-2024-001`) · `Limpar filtros`
- Cabeçalhos: `PEÇA` · `OP` · `STATUS` · `RETRABALHOS` · `INICIADA` · `CONCLUÍDA`
- Estados: `Carregando peças...` · `Erro ao carregar peças.` · `Nenhuma peça encontrada com os filtros aplicados.`
- Expandido: `INFORMAÇÕES` · `Tipo:` · `Operador:` · `Bancada:` · `Wiser:` · `✓ Exportado` · `Pendente` · `RETRABALHOS ({N})` · `FOTO FINAL` · `Carregando detalhes...` · `Sem detalhes disponíveis.`
- Paginação: `{total} peças · página {p} de {N}` · `← Anterior` · `Próxima →`

## Dados de exemplo (fixtures — 7 peças)

| Peça | OP | Status | Retrab. | Iniciada | Concluída |
|---|---|---|---|---|---|
| PC-88412 | OP-2026-0142 | V1 Analisando | — | 06/07/2026, 23:48 | — |
| PC-88409 | OP-2026-0142 | Retrabalho V2 | 2x | 06/07/2026, 23:14 | — |
| PC-88405 | OP-2026-0142 | Aguardando Bancada B | — | 06/07/2026, 22:52 | — |
| PC-88398 | OP-2026-0142 | Aprovada | — | 06/07/2026, 21:52 | 06/07/2026, 22:52 |
| PC-88391 | OP-2026-0139 | Rejeitada | 3x | 06/07/2026, 19:52 | 06/07/2026, 21:52 |
| PC-88387 | OP-2026-0139 | Identificada | — | 06/07/2026, 23:51 | — |
| PC-88380 | OP-2026-0142 | Aprovada | 1x | 06/07/2026, 18:52 | 06/07/2026, 20:52 |

Detalhe expandido (PC-88409): Tipo `Chicote 12V` · Operador `José C. Menezes` · Bancada `bench_a` · Wiser `Pendente` · Retrabalhos: `V1 Fio fora do anel #1 3m 30s` e `V2 Saída sem isolamento #2 4m 30s` · foto null.

## Estados

- **default**: 7 linhas, sem paginação (7 < 20).
- **empty**: linha única `Nenhuma peça encontrada com os filtros aplicados.` centrada, `textMuted` (sem CTA).
- **loading**: texto simples; tabela some inteira durante reload (flicker a cada mudança de filtro).
- **expanded**: linha destacada `primaryAlpha` + painel `bgSurface`; re-clique fecha.
- **hover**: NENHUM — linha é clicável (cursor pointer) mas sem feedback de hover; botões idem.
- **erro**: box vermelho acima da tabela.

## Navegação e fluxos

- Clique na linha → expande/colapsa detalhe (GET por id a cada expansão).
- Filtros re-executam o GET (page reset para 1).
- `← Anterior`/`Próxima →` → paginação server-side.
- Foto final → renderiza `{API_BASE}/api/v1/quality/gate/photos/{path}`.

## Problemas identificados

1. **P0 dark**: select `Status` e inputs `Data`/`OP` definem `background: bgCard` sem `color` — valor "Todos"/data renderiza **preto do UA sobre `#161a20` = 1.20:1** no tema escuro (confirmado por pixel-sampling em dark-default.png) (QualityPiecesPage.tsx:158-161, 177-180, 192-195).
2. **P1 dark**: pill `Rejeitada` usa `#991B1B` hardcoded → sobre `#991B1B20`+card escuro = **2.04:1**, quase ilegível no tema padrão (light passa 5.73:1) (QualityPiecesPage.tsx:20; evidência dark-default.png).
3. **P1 light**: pills de status com cor sobre `{cor}20`: `V1 Analisando`/`Retrabalho Vx` em `warning #f59e0b` = **1.85:1** no claro; `Aguardando Bancada B` `primaryDark #0891b2` = **3.17:1**; `Aprovada` `success #10b981` = **2.18:1**; contagem `2x/3x` warning = 1.85:1 (QualityPiecesPage.tsx:16-21, 292-300).
4. **P2**: paginação disabled usa `color: vars.color.borderDefault` sobre `bgCard` = **1.15:1** — rótulo invisível em dark; usar `textMuted` + opacity (QualityPiecesPage.tsx:408, 419).
5. **P2 inconsistency**: `API_BASE` com fallback `http://localhost:5001` e fetch de imagem fora do wrapper `api.ts` — em produção sem `VITE_API_URL` a foto quebra (QualityPiecesPage.tsx:12, 378).
6. **P2**: sem hover em linhas clicáveis e botões; sem skeleton no loading (tabela desaparece a cada filtro); página inteira em estilos inline (fora do padrão .css.ts).
7. **P3 copy**: valores técnicos expostos ao operador: Bancada `bench_a` (deveria ser "Bancada A"), Operador `José C. Menezes` vindo de `operator_id`; date input com placeholder `mm/dd/yyyy` en-US.
8. **P3**: empty sem ação (não oferece "Limpar filtros" no próprio estado vazio).

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063 (tokenização painel vídeo), task-065 (guard-rail CI), WS1 design system (d7a3ad3).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | ~~P0 dark~~ | ~~select/inputs sem `color` — texto UA preto sobre `#161a20` = 1.20:1~~ | **RESOLVIDO** — develop: select "Todos" e inputs de data/OP aparecem com texto legível (claro) sobre fundo escuro em `dark-default.png`; WS1 (d7a3ad3) provavelmente adicionou `color: textPrimary` nos controles de filtro. Confirmar em código. |
| 2 | P1 dark | pill `Rejeitada` `#991B1B` hardcoded — aparece como texto vermelho-escuro quase invisível em `dark-default.png` | PERSISTE |
| 3 | P1 light | pills warning/success/primaryDark sobre bg claro = 1.85–3.17:1 — confirmado em `light-default.png` | PERSISTE |
| 4 | P2 | paginação disabled `borderDefault` = 1.15:1 no dark | PERSISTE |
| 5 | P2 | `API_BASE` fallback localhost e fetch de imagem fora de `api.ts` | PERSISTE |
| 6 | P2 | Sem hover em linhas/botões; sem skeleton; estilos inline | PERSISTE |
| 7 | P3 copy | `bench_a` exposto, placeholder `mm/dd/yyyy` en-US | PERSISTE |
| 8 | P3 | Empty sem ação "Limpar filtros" | PERSISTE |

**Resumo develop:** 1 resolvido (P0 dark inputs) · 7 persistem · 0 novos.
