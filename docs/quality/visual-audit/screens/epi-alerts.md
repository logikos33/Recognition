# Histórico de Alertas (EPI) — spec visual

**Rota:** `/epi/alerts` (wrapper `EpiAlerts` → `AlertsHistoryPage`; `/alerts` redireciona via `Navigate replace`)
**Fontes:**
- `apps/frontend/src/pages/epi/EpiAlerts.tsx` (wrapper puro)
- `apps/frontend/src/pages/AlertsHistoryPage.tsx` (toda a lógica/markup, modal inline)
- `apps/frontend/src/pages/AlertsHistoryPage.css.ts` (estilos vanilla-extract)
- `apps/frontend/src/components/ui/Button/Button.css.ts` (variantes success/primary/secondary)
- `apps/frontend/src/components/shared/LoadingSpinner`
- `apps/frontend/src/components/ui/Toast/useToast`

**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | ../screenshots/epi-alerts/dark-default.png | ../screenshots/epi-alerts/light-default.png |
| empty | ../screenshots/epi-alerts/dark-empty.png | ../screenshots/epi-alerts/light-empty.png |
| loading | ../screenshots/epi-alerts/dark-loading.png | ../screenshots/epi-alerts/light-loading.png |
| error (toast + caixa vazia) | ../screenshots/epi-alerts/dark-error.png | ../screenshots/epi-alerts/light-error.png |
| exporting | ../screenshots/epi-alerts/dark-exporting.png | ../screenshots/epi-alerts/light-exporting.png |
| modal-evidencia | ../screenshots/epi-alerts/dark-modal-evidencia.png | ../screenshots/epi-alerts/light-modal-evidencia.png |
| modal-sem-evidencia | ../screenshots/epi-alerts/dark-modal-sem-evidencia.png | ../screenshots/epi-alerts/light-modal-sem-evidencia.png |
| hover-row | ../screenshots/epi-alerts/dark-hover-row.png | — (não capturado) |
| hover-export | ../screenshots/epi-alerts/dark-hover-export.png | — (não capturado) |

## Layout — regiões

- **Shell compartilhado**: topbar (breadcrumb `EPI / Alertas`, sino com badge "7", toggle "Pro", "Auditor Visual" + badge `SUPERADMIN`, botão "Sair"), footer de status (`Banco de dados`, `Redis`, `câmeras ativas`), FAB de chat ciano no canto inferior direito.
- **Página** (`page`): `padding: vars.space.xl` (32px), largura fluida.
- **Header da página** (`pageHeader`): flex `space-between`, `marginBottom: vars.space.lg` (24px). Esquerda: título H2; direita: botão "Exportar CSV" (`Button variant=success size=sm`).
- **Linha de filtros** (`filtersRow`): flex com `gap: 10px` (fora da escala 4/8/16/24/32/48), `marginBottom: 24px`, `flexWrap: wrap`. 4 controles na ordem: date início, date fim, select tipo, select status.
- **Tabela** (`tableWrapper`): `background: vars.color.bgCard`, `borderRadius: vars.radius.lg` (10px), `border: 1px solid vars.color.borderDefault`, `overflow: hidden`. Tabela 100%, `borderCollapse: collapse`. `thead` com `background: vars.color.bgSurface`. Células `padding: 12px 16px`.
- **Paginação** (`pagination`): flex `space-between`, `marginTop: vars.space.md` (16px). Esquerda texto total; direita controles (gap `vars.space.sm` = 8px).
- **Modal "Detalhe do Alerta"** (inline, fora do kit): backdrop `position: fixed; inset: 0; background: vars.color.overlay` (rgba(0,0,0,0.7)), `zIndex: 1000`, flex centralizado, `padding: 24px`. Container: `background: '#1a1d23'` **hardcoded**, `borderRadius: '12px'` (fora da escala de radius 4/6/10/16), `maxWidth: 720px`, `maxHeight: 90vh`, `overflow: auto`, `padding: 24px`.

## Árvore de componentes

- `AlertsHistoryPage`
  - `pageHeader`
    - `h2.pageTitle` — 22px / 700 / `vars.color.textPrimary`
    - `Button variant="success" size="sm"` — "Exportar CSV" / "Exportando..." (disabled durante export, opacity 0.45)
  - `filtersRow`
    - `input[type=date]` ×2 (`filterInput`: 8px 10px, radius sm 4px, borda `borderDefault`, bg `bgSurface`, texto `textPrimary` 13px) — **sem label/aria-label**
    - `select` tipo de violação (`filterInput`) — **sem label**
    - `select` status (`filterInput`) — **sem label**
  - Condicional:
    - `LoadingSpinner` (spinner ciano centralizado)
    - `emptyBox` — padding 40px, texto centralizado `textMuted`, bg `bgCard`, radius lg, borda `borderDefault`
    - Tabela + paginação:
      - `thead` 6 colunas (th: 12px / 700 / `textMuted` / letterSpacing 0.04em)
      - `tr` por alerta — `borderTop: 1px solid borderSubtle`, `cursor: pointer`, `onClick` abre modal, `onMouseEnter` inicia timer de 1s que **auto-reconhece** alertas pendentes (`hoverTimers`), `onMouseLeave` cancela. **Sem estilo :hover.**
        - `tdDate` (`textSecondary`), `tdCamera` (`textPrimary`), `tdViolation` (`danger`, 600), `tdConf` (`textSecondary`), status `span` (`statusAck` = success 600 | `statusPending` = warning 600), célula Ação com `Button variant="primary" size="sm"` "Reconhecer" (só se pendente; vira "..." enquanto `ackingId`)
      - `pagination`: `paginationText` (`textMuted` 13px) + `Button secondary sm` "←" / `pageNum` (`textSecondary` 13px) / `Button secondary sm` "→" (disabled nos limites)
  - Modal (renderizado se `selectedAlert`):
    - backdrop (click fecha) → container (stopPropagation)
      - header flex: `h3` "Detalhe do Alerta" (18px, `textPrimary`) + `button` "×" (20px, `textMuted`, background none)
      - Bloco snapshot (se `snapshotUrl`): `img` 100% + overlays por violação: box absoluto `left 20% / top 15% / width 25% / height 50%`, `border: 3px solid #ef4444` **hardcoded**, radius 4px, `animation: pulse 2s infinite`; label acima do box: `background: #ef4444` **hardcoded**, `color: vars.color.textPrimary`, 11px, padding 2px 6px, radius 3px
      - Se `evidence_key` sem snapshot ainda: caixa "Carregando imagem..." (`bgSurface`, radius 8px, padding 40px, `textSecondary`)
      - Grid de infos: `grid 1fr 1fr`, gap 12px, **`color: vars.color.borderDefault` usado como cor de texto dos VALORES**, 14px; labels `strong` com `color: vars.color.textMuted`
      - Footer (só se pendente): `Button variant="primary" size="sm"` "Reconhecer" (reconhece e fecha)

## Copy exata

- Título: `Histórico de Alertas`
- Botão export: `Exportar CSV` → `Exportando...`
- Selects: `Todos os tipos` | `Sem capacete` | `Sem colete` | `Sem luvas` | `Sem óculos`; `Todos os status` | `Pendente` | `Reconhecido`
- Inputs de data: placeholder nativo do browser `mm/dd/yyyy` (en-US, sem localização)
- Vazio: `Nenhum alerta encontrado`
- Cabeçalhos: `Data`, `Câmera`, `Violação`, `Confiança`, `Status`, `Ação`
- Status: `Pendente` / `Reconhecido`; botão de linha: `Reconhecer` → `...`
- Paginação: `Total: {n} alertas` · `←` · `{page} / {pages}` · `→`
- Modal: `Detalhe do Alerta`, `×`, `Carregando imagem...`, labels `Câmera:`, `Data:`, `Violações:`, `Confiança:`, `Status:`, botão `Reconhecer`
- Label do bounding box: `{violação} — {confiança}%` (ex.: `Sem capacete — 76%`)
- Toast de erro do export: `Erro ao exportar` (na captura de erro aparece `Erro interno do servidor`, vindo do wrapper de API)
- Mapa `VIOLATION_LABELS`: `no_helmet→Sem capacete`, `no_vest→Sem colete`, `no_gloves→Sem luvas`, `no_safety_glasses|no_glasses→Sem óculos`

## Dados de exemplo (fixtures do spec)

`Total: 42 alertas`, página `1 / 3`, 7 linhas:

| Data | Câmera | Violação | Confiança | Status |
|---|---|---|---|---|
| 04/07/2026, 14:32:00 | Câmera Pátio Norte | Sem capacete | 94% | Pendente |
| 04/07/2026, 11:32:18 | Câmera Doca de Carga 2 | Sem colete, Sem capacete | 88% | Pendente |
| 04/07/2026, 08:05:44 | Câmera Linha de Produção | Sem luvas | 71% | Reconhecido |
| 03/07/2026, 16:48:10 | Câmera Portaria Principal | Sem óculos | 83% | Reconhecido |
| 03/07/2026, 13:21:37 | Câmera Almoxarifado | Sem capacete | 97% | Pendente |
| 03/07/2026, 06:14:02 | Câmera Estacionamento Sul | Sem colete | 62% | Pendente |
| 02/07/2026, 19:40:55 | Câmera Pátio Norte | Sem capacete, Sem luvas | 91% | Reconhecido |

Modal com evidência (alerta 2): snapshot SVG `CAM 02 — DOCA DE CARGA 2 — 04/07/2026 14:32:18` com "REC", box vermelho e label `Sem capacete — 76%`; grid: Câmera `Câmera Doca de Carga 2`, Data `04/07/2026, 11:32:18`, Violações `Sem colete, Sem capacete`, Confiança `88%`, Status `Pendente`. Modal sem evidência (alerta 5): Câmera `Câmera Almoxarifado`, Data `03/07/2026, 13:21:37`, Confiança `97%`, Status `Pendente`.

## Estados

- **default**: filtros + tabela + paginação.
- **loading**: some tudo abaixo dos filtros; só `LoadingSpinner` (a tabela inteira desmonta a cada mudança de filtro/página — layout shift).
- **empty**: caixa `Nenhum alerta encontrado` (sem CTA, sem sugestão de limpar filtros).
- **error (fetch)**: `catch` só faz `console.error` → UI degrada para o MESMO estado empty (`Nenhum alerta encontrado`) — não existe estado de erro dedicado nem retry.
- **error (export)**: toast `Erro ao exportar`/`Erro interno do servidor` renderizado SOBRE a topbar (colide com "Auditor Visual"/"Sair").
- **exporting**: botão vira `Exportando...` disabled (opacity 0.45).
- **hover em linha**: nenhum feedback visual (sem `:hover` no `tr`); em linha PENDENTE, hover ≥1s dispara `POST /alerts/:id/acknowledge` silenciosamente e recarrega a lista.
- **hover no Exportar CSV**: `filter: brightness(1.1)` (mudança quase imperceptível na captura).
- **acking**: botão da linha vira `...` disabled.
- **modal aberto**: backdrop `vars.color.overlay`; container SEMPRE `#1a1d23` (não retematiza).

## Navegação e fluxos

- Clique em linha → abre modal "Detalhe do Alerta"; se `evidence_key`, busca `GET /alerts/:id/snapshot` e mostra imagem + bounding boxes.
- Botão "Reconhecer" (linha ou modal) → `POST /alerts/:id/acknowledge` → recarrega lista (modal também fecha).
- Hover 1s em linha pendente → MESMO POST de reconhecimento, sem confirmação (comportamento oculto).
- "Exportar CSV" → `GET /alerts/export?...` → download `alertas.csv`.
- Filtros/paginação → refetch `GET /alerts?...` (mudar filtro reseta page=1). Filtro `camera_id` existe no estado mas NÃO tem controle na UI.
- Fechar modal: clique no backdrop ou no "×".

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 (dark)** Valores do grid do modal usam `vars.color.borderDefault` como cor de texto → 1.12:1, invisíveis no tema padrão (AlertsHistoryPage.tsx:252).
2. **P0 (light)** Modal com `background: '#1a1d23'` hardcoded (task-063/066): sob white-label claro o título `textPrimary` vira #1a1d23 sobre #1a1d23 → 1.00:1, título some (AlertsHistoryPage.tsx:211/216).
3. **P1 (both)** Hover de 1s em linha pendente auto-reconhece o alerta sem confirmação (AlertsHistoryPage.tsx:141–152).
4. **P1 (both)** Erro de fetch é engolido e vira "Nenhum alerta encontrado" — sem estado de erro/retry (linha 59).
5. **P1 (light)** Tokens semânticos fixos sob superfície clara: `Pendente` #f59e0b em #eceef1 = 1.85:1; `Reconhecido` #10b981 = 2.18:1; coluna Violação #ef4444 = 3.24:1.
6. **P1 (both)** Botões sólidos do kit: `#ffffff` sobre `primary #06b6d4` = 2.43:1 e sobre `success #10b981` = 2.54:1 (texto 12px).
7. **P2 (both)** Linhas clicáveis sem estado `:hover` (deveria `vars.color.bgHover`).
8. **P2 (both)** Modal ad-hoc inline fora do padrão ADR-0023 (TODO-WS1 na linha 204); radius 12px fora da escala; gap 10px dos filtros fora da escala.
9. **P2 (both)** `#ef4444` hardcoded no bounding box/label (linhas 230/237) em vez de `vars.color.danger`; label 11px com 3.40:1 no dark.
10. **P2 (both)** Toast de erro sobrepõe a topbar; ilegível.
11. **P2 (both)** Filtros sem label/aria-label (WCAG 1.3.1/4.1.2); paginação "←"/"→" sem `aria-label`.
12. **P3** Inputs de data exibem `mm/dd/yyyy` (en-US) em app pt-BR; empty state sem CTA; labels do modal (`textMuted` 4.09:1 dark / 3.49:1 light sobre #1a1d23) abaixo de AA.
13. **P3 (both)** Contrastes no limite de AA para texto 13px `textMuted`: caixa vazia `Nenhum alerta encontrado` (#668096 sobre #161a20 = 4.23:1 dark; #6b7280 sobre #eceef1 = 4.16:1 light) e `Total: 42 alertas` no light (#6b7280 sobre #f4f5f7 = 4.43:1) — todos < 4.5:1 (AlertsHistoryPage.css.ts:26-30, 64).
14. **P3 (both)** Estado `exporting`: botão disabled a `opacity: 0.45` deixa "Exportando..." quase invisível no light (branco sobre verde já era 2.54:1); preferir spinner + texto mantendo contraste (Button.css.ts:24-27).

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop

**Filtro `camera_id` agora tem controle na UI (NOVO)**

A linha de filtros agora tem 5 controles: campo `ID da câmera` (texto) foi adicionado como primeiro elemento. Baseline dizia "filtro camera_id existe no estado mas NÃO tem controle na UI" — resolvido na develop. Em viewports < 800px o `flexWrap: wrap` pode causar quebra de linha extra nos filtros.

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P0 | dark | ~~Valores do grid do modal via `borderDefault` → 1.12:1, invisíveis~~ **(RESOLVED)** | `light-modal-evidencia.png` mostra valores legíveis no modal; texto provavelmente movido para `textSecondary` |
| 2 | P0 | light | **PERSISTS** | Modal bg `#1a1d23` hardcoded — modal permanece com fundo escuro no light theme (`light-modal-evidencia.png` confirma backdrop claro + modal escuro) |
| 3 | P1 | both | **PERSISTS** | Hover 1s em linha pendente auto-reconhece silenciosamente — comportamento oculto de segurança; sem indicador visual de "prestes a reconhecer" |
| 4 | P1 | both | **PERSISTS** | Erro de fetch engolido → UI vira estado vazio sem distinção — sem retry/estado de erro dedicado |
| 5 | P1 | light | **PERSISTS** | `Pendente` #f59e0b = 1.85:1, `Reconhecido` #10b981 = 2.18:1, coluna Violação #ef4444 = 3.24:1 — todos abaixo de AA no light |
| 6 | P1 | both | **PERSISTS** | Botões do kit: branco sobre ciano 2.43:1 e sobre verde 2.54:1 (texto 12px) |
| 7 | P2 | both | **PERSISTS** | Linhas clicáveis sem `:hover` (cursor pointer mas sem `bgHover`) |
| 8 | P2 | both | **PERSISTS** | Modal ad-hoc inline (TODO-WS1); radius 12px e gap 10px fora da escala |
| 9 | P2 | both | **PERSISTS** | Bounding box/label `#ef4444` hardcoded; label 11px 3.40:1 no dark |
| 10 | P2 | both | **PERSISTS** | Toast de erro sobrepõe topbar |
| 11 | P2 | both | **PERSISTS** | Filtros de data/select sem `label`/`aria-label` (WCAG 1.3.1/4.1.2); paginação sem `aria-label` |
| 12 | P3 | both | **PERSISTS** | Datas en-US `mm/dd/yyyy`; empty state sem CTA; labels do modal abaixo de AA |
| 13 | P3 | both | **PERSISTS** | `textMuted` limítrofe: empty 4.23:1/4.16:1; paginação 4.43:1 — todos < 4.5:1 |
| 14 | P3 | both | **PERSISTS** | `exporting` opacity 0.45 sobre verde 2.54:1 — texto quase invisível no light |
| 15 | P2 | both | **NEW** | Linha de filtros passou de 4 para 5 controles (`ID da câmera` adicionado) — em telas < 800px `flexWrap` gera segunda linha sem separação visual; o novo campo carece de `aria-label` assim como os outros |
