# Inspeções — spec visual

**Rota:** `/quality/inspections`
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityInspectionsPage.tsx`, `components/DefectBadge.tsx` (ResultBadge/FeedbackBadge/DefectBadge), `components/quality.css.ts` (table/th/td/trHover/badgeVariants)
**Endpoints:** NENHUM — página roda em **modo demonstração**: 200 inspeções geradas client-side em runtime (`makeInspections()`), apesar de `qualityService.getInspections` existir. Feedback salvo apenas em estado local (`feedbackOverrides`) com `setTimeout(500)`.
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/quality-inspections/dark-default.png | ../screenshots/quality-inspections/light-default.png |
| empty (filtro sem resultado) | ../screenshots/quality-inspections/dark-empty.png | ../screenshots/quality-inspections/light-empty.png |
| modal-feedback-drawer | ../screenshots/quality-inspections/dark-modal-feedback-drawer.png | ../screenshots/quality-inspections/light-modal-feedback-drawer.png |

## Layout — regiões

- Conteúdo: `padding: 24`, `position: relative` (sem maxWidth — full-bleed, diferente das outras abas).
- Header: flex space-between — h2 18px/700 `Inspeções` | direita: `{N} registros` 13px `textMuted` + selo `MODO DEMONSTRAÇÃO` 10px/700 `textPrimary` bg `bgSurface` radius 3.
- Banner condicional (filtros vindos do dashboard, via querystring): bg `#0d1929`, borda `#1a3a5c`, texto/link `#4FC3F7` (hardcoded).
- Barra de filtros: flex wrap gap 8 — 4 selects + input texto (160px) + 2 date + botão `Limpar`. Estilo comum: padding 6×10, radius 4, borda `borderDefault`, bg `bgSurface`, 12px `textSecondary`.
- Tabela full-width (`overflowX: auto`), 9 colunas; paginação central abaixo (25/página).
- Drawer lateral direito: backdrop `fixed inset 0` bg `vars.color.overlay` zIndex 40; painel `fixed` right 320px×100vh, bg `bgBase`, borda esq. `borderDefault`, padding 20, `boxShadow: -8px 0 32px rgba(0,0,0,0.6)` (hardcoded), zIndex 50.

## Árvore de componentes

- Filtros: `Todas as câmeras` (3 opções mock) · `OK + NOK`/`Apenas OK`/`Apenas NOK` · `Todos feedbacks` (Pendente/Confirmado/Rejeitado) · `Todos turnos` (Manhã/Tarde/Noite) · input `Ordem de produção` · 2× `type=date` · `Limpar`.
- Tabela (`table`/`th`/`td` de quality.css.ts; th 11px uppercase `textSecondary` com tooltip nativo + `underline dotted`; td 13px `textPrimary`, borda inferior `borderSubtle`; linha com `trHover` → hover `bgHover`):
  - Colunas: Data/Hora · Câmera · Resultado (`ResultBadge`) · Defeito (`DefectBadge`) · Conf. · Turno · Lote · Feedback ↗ (`FeedbackBadge` + `▾` se pendente) · NOK/1h (vermelho se >10%).
  - Badges (`badgeVariants`, 11px/600 uppercase pill): `ok` `#43D186` sobre rgba(67,209,134,.12) · `nok` `#EF5350` · `pending` `#FFB74D` · `confirmed` `#4FC3F7` · `rejected` `#CE93D8` — todos hardcoded.
- Paginação: `← Anterior` / `{p} / {N}` / `Próxima →` — bg transparent, borda `borderDefault`, 12px; disabled = cor `textMuted` + cursor not-allowed.
- **Drawer de Feedback**:
  - Header: `Feedback de Inspeção` 13px/700 + botão `×` 20px `textMuted`.
  - Card de contexto: bg `bgSurface`, borda `borderDefault`, radius 6 — label `INSPEÇÃO` 10px `textPrimary`, câmera 12px/600 `textSecondary`, turno+data 11px `textMuted`, ResultBadge + DefectBadge + `Conf. {N}%`.
  - `STATUS ATUAL` + FeedbackBadge.
  - `NOTAS (OPCIONAL)` + textarea (bg `bgSurface`, **borda `#2a2a2a`**, texto 12px `textSecondary`, radius 4, resize vertical).
  - Ações (coluna, gap 8): `✓ Confirmar Defeito` (bg **`#0f2e1a`**, texto `success`, 13px/700) · `✗ Falso Positivo` (bg **`#2e0f0f`**, texto `danger`) · `Cancelar` (borda **`#2a2a2a`**, texto `textMuted`). Saving → bg `bgSurface`, texto `borderStrong`, label `Salvando…`.

## Copy exata

- Título: `Inspeções` · contagem `{N} registros` · selo `MODO DEMONSTRAÇÃO`
- Banner: `⚡ Filtros aplicados a partir do dashboard` + link `Limpar`
- Filtros: `Todas as câmeras` · `OK + NOK` · `Apenas OK` · `Apenas NOK` · `Todos feedbacks` · `Pendente` · `Confirmado` · `Rejeitado` · `Todos turnos` · `Manhã` · `Tarde` · `Noite` · placeholder `Ordem de produção` · `Limpar`
- Cabeçalhos: `Data/Hora` · `Câmera` · `Resultado` · `Defeito` · `Conf.` · `Turno` · `Lote` · `Feedback ↗` · `NOK/1h` (todos com tooltips longos — ex.: Conf.: "Confiança do modelo na detecção — valores abaixo de 80% merecem revisão manual"; Feedback: "…Falso Positivo indica detecção incorreta — clique para registrar")
- Badges: `✓ OK` · `✗ NOK` · `Pendente` · `Confirmado` · `Rejeitado`
- Vazio: `Nenhuma inspeção encontrada.`
- Paginação: `← Anterior` · `{page} / {totalPages}` · `Próxima →`
- Drawer: `Feedback de Inspeção` · `INSPEÇÃO` · `STATUS ATUAL` · `NOTAS (OPCIONAL)` · placeholder `Observações sobre esta inspeção…` · `✓ Confirmar Defeito` · `✗ Falso Positivo` · `Cancelar` · `Salvando…` · `Conf. {N}%`

## Dados de exemplo

- Câmeras mock: `Linha A — Frontal` · `Linha B — Lateral` · `Linha C — Embalagem` (OPs ORDEM-004/ORDEM-007).
- Classes de defeito: Arranhão (danger) · Mancha `#FF8A65` · Deformação `#FFB74D` · Cor incorreta `#AB47BC` · Trinca `#F44336`.
- 200 inspeções: ~26% NOK, confiança 78–99%, lotes ORDEM-001…007, turnos por hora (Manhã 06–14h, Tarde 14–22h, Noite 22–06h), NOK/1h 1–18% (alerta CEP >10% em `danger`).
- Drawer capturado: Linha C — Embalagem, Noite · 06/07/2026, 23:53:52, ✓ OK, Conf. 81%, status Pendente, notas "Defeito confirmado na conferência manual — arranhão visível na lateral esquerda.".

## Estados

- **default**: 200 registros, página 1/8.
- **empty**: filtro OP sem resultado → única linha `Nenhuma inspeção encontrada.` colSpan 9 (sem CTA de limpar filtros na própria célula — o botão Limpar fica acima).
- **drawer aberto**: backdrop 0.7 + painel opaco (sem defeito 066); clique fora fecha (bloqueado durante saving).
- **saving**: botões desabilitados com `Salvando…`.
- **hover**: linhas da tabela têm `trHover`; botões de filtro/paginação/drawer NÃO têm hover.

## Navegação e fluxos

- Clique na linha → `/quality/inspections/{id}` (detalhe).
- Clique na célula Feedback → abre drawer (stopPropagation).
- `✓ Confirmar Defeito` / `✗ Falso Positivo` → grava APENAS em estado local (perdido no reload).
- `Limpar` (barra/banner) → zera filtros e volta à página 1.
- Querystring aceita `camera_id`, `result`, `feedback_status`, `shift` (integração dashboard→inspeções).

## Problemas identificados

1. **P1**: página inteira é mock client-side ("MODO DEMONSTRAÇÃO") — não consome `GET /quality/inspections` real; feedback do operador é descartado silenciosamente no reload (QualityInspectionsPage.tsx:12-78, 129-140).
2. **P1 light (task-063)**: botões do drawer com fundos escuros fixos `#0f2e1a` e `#2e0f0f` permanecem idênticos no tema claro — blocos escuros alienígenas sobre painel branco; contraste interno 5.81:1/4.68:1 passa, mas viola white-label e o padrão de botão (QualityInspectionsPage.tsx:439, 453; evidência light-modal-feedback-drawer.png).
3. **P1 light**: badges de tabela hardcoded falham AA sobre superfície clara: `PENDENTE #FFB74D` **1.62:1**, `CONFIRMADO #4FC3F7` **1.85:1**, `OK #43D186` **1.80:1**, `REJEITADO #CE93D8` **2.17:1**, `NOK #EF5350` **3.01:1** (quality.css.ts:54-80; evidência light-default.png).
4. **P2 hardcode (task-063/065)**: banner de filtros `#0d1929`/`#1a3a5c`/`#4FC3F7` fixos — ilha azul-escura no tema claro (QualityInspectionsPage.tsx:183, 188); bordas `#2a2a2a` no textarea e no Cancelar (linhas 421, 467); sombra do drawer `rgba(0,0,0,0.6)` fixa (linha 369) — usar `vars.shadow.lg`.
5. **P2**: drawer ad-hoc com TODO-WS1 (linha 355) — converter para Drawer/Modal do kit (ADR-0023).
6. **P2**: cores de classes de defeito mock hardcoded (`#FF8A65`, `#FFB74D`, `#AB47BC`, `#F44336`) fora da paleta (linhas 22-25).
7. **P2**: sem hover em filtros, paginação e botões do drawer; paginação com bg `transparent` diverge do padrão bg `bgCard` usado em Peças.
8. **P3 copy**: coluna `Lote` exibe valores `ORDEM-xxx` e o filtro chama o mesmo campo de `Ordem de produção` — vocabulário inconsistente; datas `mm/dd/yyyy` (placeholder do browser em en-US) numa UI pt-BR.
9. **P3**: labels de seção do drawer (`INSPEÇÃO`, `STATUS ATUAL`, `NOTAS…`) em `textPrimary` 10px enquanto o conteúdo usa `textSecondary` — hierarquia invertida.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063 (tokenização painel vídeo), task-065 (guard-rail CI), WS1 design system (d7a3ad3).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P1 | Página mock client-side "MODO DEMONSTRAÇÃO" — feedback descartado no reload | PERSISTE |
| 2 | P1 light | Botões drawer `#0f2e1a`/`#2e0f0f` hardcoded — blocos escuros alienígenas sobre painel branco — **confirmado** em `light-modal-feedback-drawer.png` (develop) | PERSISTE |
| 3 | P1 light | Badges tabela PENDENTE/CONFIRMADO/OK/REJEITADO hardcoded falham AA no claro — **confirmado** em `light-default.png` (pills coloridas visíveis mas baixo contraste) | PERSISTE |
| 4 | P2 hardcode | Banner filtros `#0d1929`/`#1a3a5c`/`#4FC3F7`; bordas `#2a2a2a`; sombra drawer fixa | PERSISTE |
| 5 | P2 | Drawer ad-hoc com TODO-WS1 — task-063 não cobriu esta tela | PERSISTE |
| 6 | P2 | Cores mock de defeito hardcoded fora da paleta | PERSISTE |
| 7 | P2 | Sem hover em filtros/paginação/drawer | PERSISTE |
| 8 | P3 copy | Lote vs Ordem de produção inconsistente; datas en-US | PERSISTE |
| 9 | P3 | Hierarquia de labels do drawer invertida | PERSISTE |

**Resumo develop:** 0 resolvidos · 9 persistem · 0 novos. task-063 não cobriu QualityInspectionsPage; botões do drawer permanecem com hardcodes escuros — confirmados visualmente no tema claro.
