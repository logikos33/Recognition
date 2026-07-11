# Contagem DeepSORT — spec visual

**Rota:** `/epi/counting` (AppRoutes.tsx:57 → `CountingPage`)
**Fontes:** `apps/frontend/src/pages/CountingPage.tsx` (100% estilos inline), `src/types/counting.ts`, `src/components/ui/Skeleton/Skeleton.tsx`, `src/components/ui/Toast/useToast.ts`, ícones lucide (`Hash`, `StopCircle`, `PlayCircle`, `RefreshCw`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (sessão ativa + stats + outras sessões) | ../screenshots/counting/dark-default.png | ../screenshots/counting/light-default.png |
| empty (sem câmeras/sessões) | ../screenshots/counting/dark-empty.png | ../screenshots/counting/light-empty.png |

Estados sem screenshot (tier 2): loading (skeleton), finalCounts ("Totais da sessão encerrada"), "Aguardando primeiras detecções...".

## Layout — regiões

- Shell do app: topbar com breadcrumb `EPI / Contagem`, sino, Pro/toggle de tema, "Auditor Visual" + `SUPERADMIN`, "Sair"; rodapé de status.
- Container: `padding: 24px; maxWidth: 860px; margin: 0 auto`.
- Empilhamento vertical:
  1. **Header** — flex space-between, `marginBottom: 8`: esquerda `Hash` 22px `primaryLight` + `h2` 20px/700 + badge contador de sessões (bg `primaryDark`, radius 999, `padding: 2px 10px`, 12px/700); direita botão "Atualizar" (transparente, borda `borderStrong`, radius 6, `padding: 6px 12px`, 12px, texto `textSecondary`, ícone `RefreshCw` 13).
  2. Subtítulo 13px `textMuted`, `marginBottom: 24`.
  3. **Card de controles** — bg `bgBase`, borda 1px `bgSurface` (token de fundo usado como borda), radius 10, padding 20, flex gap 12 align-end wrap: label+`select` Câmera (flex 1, minWidth 200; select: bg `bgSurface`, borda `borderStrong`, radius 6, cor `#f1f5f9` hardcoded, `padding: 8px 12px`, 14px) + botão Iniciar/Encerrar.
  4. **Bloco sessão ativa** (condicional): linha de status (dot 8px `success` com glow `boxShadow 0 0 6px`, texto 13px `textSecondary`, nome da câmera em `<strong>` `#f1f5f9`, `SessionMetaChips`, "Total: N" à direita com N em `#f1f5f9`) + grid de stats `repeat(auto-fill, minmax(160px, 1fr))`, gap 10.
  5. **Card "Totais da sessão encerrada"** (condicional `finalCounts`): mesmo grid, cards com bg `bgSurface`.
  6. **Outras sessões ativas** (condicional): label 12px `textMuted` + coluna gap 8 de linhas (bg `bgBase`, borda `bgSurface`, radius 8, `padding: 12px 16px`, flex gap 10).
  7. **Empty state** (condicional): centrado, `padding: 60px 20px`, borda `1px dashed bgSurface`, radius 12, `textMuted`.

## Árvore de componentes

- `CountingPage`
  - Loading: `Skeleton` (title 200px + rect 100%×44 + grid 6× [text 60% + title 40%])
  - Header: `Hash` + `h2` "Contagem DeepSORT" + badge "{n} ativa(s)" + botão "Atualizar"
  - Card controles:
    - `select` Câmera — options `{nome}` + sufixo ` (streaming)`; desabilitado durante sessão (cor `textMuted`, cursor not-allowed); vazio: option "Nenhuma câmera disponível"
    - Botão **Iniciar Contagem** (`PlayCircle` 15): bg `rgba(34,197,94,0.1)` (0.05 desabilitado), borda `rgba(34,197,94,0.3)`, texto `success`, radius 6, `padding: 8px 20px`, 14px/600
    - Botão **Encerrar** (`StopCircle` 15): bg `rgba(239,68,68,0.1)` (0.05 ao encerrar), borda `rgba(239,68,68,0.3)`, texto `#ef4444` hardcoded
  - `SessionMetaChips` (chips 11px/600, radius 4, `padding: 2px 8px`):
    - placa: bg `bgSurface`, cor `#f1f5f9` hardcoded, monospace
    - direção: bg `rgba(99,102,241,0.15)`, cor `#a5b4fc` (indigo fora da paleta)
    - aceite: bg `{cor}22`, cor = `#f59e0b` (Pendente) | `vars.color.success` (Aceita) | `#ef4444` (Rejeitada)
  - Card de stat (por classe): bg `bgBase`, borda `rgba(239,68,68,0.25)` se `no_*` senão `rgba(34,197,94,0.25)`, radius 8, `padding: 14px 16px`; valor 28px/700 monospace na cor `#ef4444` (violação) | `success`; label 12px `textSecondary`
  - Vazio de stats: "Aguardando primeiras detecções..." (borda dashed `bgSurface`, radius 10, 13px `textMuted`)
  - Card totais finais: título 15px/700 `#f1f5f9` + botão fechar "×" 18px `textMuted`; grid igual ao de stats (cards bg `bgSurface`, bordas alpha 0.2)
  - Linha "outra sessão": dot 8px `#f59e0b` hardcoded + "Sessão `<code #f1f5f9>` — câmera: `<strong #f1f5f9>`" + `SessionMetaChips` + chip de status cru (11px `textMuted`, bg `bgSurface`, radius 4)
  - Empty state: `Hash` 40 opacity 0.2 + "Nenhuma contagem ativa" 15px/600 + instrução 13px
  - Toasts (useToast): sucesso/erro das ações

## Copy exata

- Título: `Contagem DeepSORT`; badge: `{n} ativa` / `{n} ativas`; botão `Atualizar`
- Subtítulo: `Contagem por rastreamento DeepSORT. Selecione uma câmera e inicie a sessão.`
- Controles: label `Câmera`; option vazia `Nenhuma câmera disponível`; sufixo ` (streaming)`; `Iniciar Contagem` / `Iniciando...`; `Encerrar` / `Encerrando...`
- Sessão ativa: `Sessão ativa — câmera:` + nome; `Total:` + n
- Stats vazio: `Aguardando primeiras detecções...`
- Labels de classe (`CLASS_LABELS`): `Capacete`, `Sem capacete`, `Colete`, `Sem colete`, `Luvas`, `Sem luvas`, `Óculos`, `Sem óculos`
- Chips: direção `Carga` (load) / `Descarga` (unload); aceite `Pendente` / `Aceita` / `Rejeitada`; status cru `active` (chave do backend, sem tradução)
- Totais: `Totais da sessão encerrada`; vazio: `Nenhuma detecção registrada nesta sessão.`; fechar `×` (title `Fechar`)
- Outras sessões: `Outras sessões ativas`; linha: `Sessão {id8} — câmera: {nome}`
- Empty: `Nenhuma contagem ativa` + `Selecione uma câmera e clique em "Iniciar Contagem".`
- Toasts: `Selecione uma câmera`, `Contagem iniciada`, `Contagem encerrada`, `Erro ao carregar dados`, `Erro ao iniciar contagem`, `Erro ao encerrar contagem`, `Resposta inválida do servidor`

## Dados de exemplo (fixtures do harness)

- Câmeras: Câmera Pátio Norte (streaming), Câmera Doca 02 (streaming), Câmera Portaria Principal, Câmera Almoxarifado, Câmera Linha de Produção A (streaming).
- Sessões ativas (3 → badge "3 ativas"):
  | id (exibido) | câmera | placa | direção | aceite |
  |---|---|---|---|---|
  | sess-8f2 (controlada) | Câmera Doca 02 | RVB4D23 | Carga | Pendente |
  | sess-3b9 | Câmera Pátio Norte | BRA2E19 | Descarga | Aceita |
  | sess-77a | Câmera Linha de Produção A | — | Carga | Rejeitada |
- Stats (polling 3s): Capacete 34, Sem capacete 5, Colete 28, Sem colete 9, Luvas 17, Sem luvas 3 — Total: 96.

## Estados

- **loading:** skeletons (título + barra + grid 6).
- **default:** select desabilitado mostrando "Câmera Pátio Norte (streaming)" (primeira câmera — NÃO a da sessão ativa, ver problemas), botão "Encerrar", linha de sessão ativa com chips, grid de 6 stats, "Outras sessões ativas" com 2 linhas.
- **empty:** select "Nenhuma câmera disponível", "Iniciar Contagem" desabilitado (opacity 0.5), empty state com ícone + instrução. Bom exemplo de vazio com convite à ação.
- **stats vazios:** "Aguardando primeiras detecções..." pontilhado.
- **finalCounts:** card "Totais da sessão encerrada" com grid + fechar.
- **hover:** nenhum estado hover definido em nenhum botão/linha (inline styles).
- **light (BUG task-063):** todo texto `#f1f5f9` hardcoded desaparece — título, nome da câmera da sessão, texto do select, placa, "Total:", IDs `sess-*` (ver light-default.png / light-empty.png).

## Navegação e fluxos

- "Atualizar" → `loadInitialData()` (GET /api/cameras + /api/counting/sessions).
- "Iniciar Contagem" → POST /api/counting/sessions {camera_id} → sessão ativa + polling GET /counting/sessions/{id}/stats a cada 3s → toast "Contagem iniciada".
- "Encerrar" → DELETE /api/counting/sessions/{id} → mostra "Totais da sessão encerrada" → toast "Contagem encerrada".
- "×" no card de totais → fecha o card.
- Não há navegação para outras telas (câmera/sessão não são links).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **task-063 (P0, light):** `#f1f5f9` hardcoded em 7 pontos (título, select, placa, nome de câmera, Total, totais finais, `sess-*`) → 1.0–1.1:1 sob superfícies claras — conteúdo some.
2. **task-065 (P1):** hardcodes `#ef4444`, `#f59e0b`, `#a5b4fc`, `rgba(34,197,94,x)`, `rgba(239,68,68,x)`, `rgba(99,102,241,0.15)`, `${color}22` — nenhum passa por token.
3. **Contraste light (P1):** chips Carga/Descarga 1.53:1, Pendente 1.79:1, Aceita 2.07:1; botão "Iniciar Contagem" 2.15:1; contadores verdes 2.33:1 (tokens `success`/`warning`/`danger` fixos, sem variante para superfície clara).
4. **Semântica de token (P2):** `bgSurface` usado como COR DE BORDA (card de controles, linhas de sessão, bordas dashed) — no light vira borda branca invisível sobre `#f4f5f7`.
5. **Hover ausente (P2)** em todos os botões.
6. **Copy (P3):** chip de status mostra `active` cru em meio a UI pt-BR.
7. **Estado enganoso (P3):** select desabilitado mostra a 1ª câmera da lista ("Pátio Norte") enquanto a sessão ativa é de outra ("Doca 02") — leitura rápida sugere câmera errada.
8. **Escala (P3):** radius 8/999 e paddings 2/6px fora das escalas 4/6/10/16 e 4/8/16/24/32/48.

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop

Nenhuma alteração detectada. Página idêntica ao baseline em todos os estados capturados.

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P0 | light | **PERSISTS** | `#f1f5f9` hardcoded em 7 pontos: título "Contagem DeepSORT" (invisível), nome da câmera ativa, placa `RVB4D23`, `Total: 96`, IDs `sess-3b9`/`sess-77a`, câmeras nas linhas de outras sessões — 1.0–1.1:1 no light. Confirmado em `light-default.png` e `light-empty.png`. task-063 incompleto. |
| 2 | P1 | both | **PERSISTS** | task-065: 7+ hardcodes `#ef4444`, `#f59e0b`, `#a5b4fc`, `rgba(34,197,94,x)`, `rgba(239,68,68,x)`, `rgba(99,102,241,0.15)` — nenhum usa `vars.color.*` |
| 3 | P1 | light | **PERSISTS** | Contraste light: chips `Carga`/`Descarga` 1.53:1, `Pendente` 1.79:1, `Aceita` 2.07:1; botão "Iniciar Contagem" 2.15:1; contadores verdes `success` 2.33:1 |
| 4 | P2 | light | **PERSISTS** | `bgSurface` como cor de borda — borda invisível no light (`#f4f5f7` sobre `#f4f5f7` ≈ 1.0:1) nos cards de controle, linhas de sessão e empty state tracejado |
| 5 | P2 | both | **PERSISTS** | Hover ausente em todos os botões (Iniciar, Encerrar, Atualizar) — estilos inline sem `:hover` |
| 6 | P3 | both | **PERSISTS** | Chip de status exibe `active` cru — sem tradução pt-BR |
| 7 | P3 | both | **PERSISTS** | Select desabilitado mostra "Câmera Pátio Norte" enquanto sessão ativa é "Câmera Doca 02" — estado enganoso |
| 8 | P3 | both | **PERSISTS** | Radius 8/999 e paddings 2/6px fora das escalas do design system |
