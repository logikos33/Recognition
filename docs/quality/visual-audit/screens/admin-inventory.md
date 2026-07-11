# Inventário de Câmeras — spec visual

**Rota:** `/admin/inventory`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminInventoryPage.tsx` (página autocontida — NÃO usa `admin.css.ts`; todos os estilos são objetos `CSSProperties` inline no próprio arquivo)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (após clicar "Buscar") | `../screenshots/admin-inventory/dark-default.png` | `../screenshots/admin-inventory/light-default.png` |
| empty (estado inicial, sem busca) | `../screenshots/admin-inventory/dark-empty.png` | `../screenshots/admin-inventory/light-empty.png` |

Fluxos Import CSV e probe/probe-batch não capturados (upload de arquivo/mutações).

## Layout — regiões

- Shell AdminLayout. Conteúdo: `padding: 24px 32px; maxWidth: 1400; margin: 0 auto` (mais largo que as demais páginas admin, 1200).
- h1 22px/700 (mb 4) + parágrafo 14px textSecondary (mb 24).
- Linha de filtros: flex gap 12, `alignItems: flex-end` — 3 grupos label(12px textSecondary)+campo + botão "Buscar".
- Barra de ações: flex gap 10 — "Testar Selecionadas (n)" + "Importar CSV" + hint do formato.
- Banners de import/erro (verde `#d1fae5` / `dangerMuted`), radius 6, padding 10px 14px.
- Tabela: wrapper `overflowX: auto; border: 1px borderDefault; borderRadius: 8`; thead com `background: bgSurface`; células `padding: 10px 12px`, fonte 13px.
- Rodapé: contagem "n câmera(s) encontrada(s)" 12px textMuted.

## Árvore de componentes

- h1 "Inventário de Câmeras" + subtítulo
- Filtros: input "Tenant ID" (placeholder `UUID do tenant`) · input "Marca" (placeholder `Ex: Intelbras`) · select "Status Probe" (Todos/Pendente/OK/Erro/Timeout, bg bgCard) · botão primário "Buscar"
- Ações: botão "Testar Selecionadas ({n})" (desabilitado sem seleção) · botão secundário "Importar CSV" (input file oculto) · hint `CSV: name,brand,ip,port,username,module,tenant_id`
- Tabela: colunas `[checkbox]` · `Nome` (nome 600 + modelo 11px textMuted) · `Marca` · `IP / Host` (`<code>` 12px) · `Porta` · `Módulo` (**só renderiza "(draft) " em #6366f1 quando inativa — nunca o módulo**) · `Probe` (`ProbeStatusBadge` + timestamp 10px) · `Codec` (`<code>` ou —) · `Substream` (`BoolBadge` Sim #059669 / Não danger / —) · `Tenant` · `Ações` (botão "Testar" mint `#f0fdf4`/`#166534`, borda `#bbf7d0`; probing → "..." desabilitado)
- `ProbeStatusBadge` (pill 2px 8px, radius 12, 11px/600): ok `#d1fae5`/`#065f46` "OK" · error `dangerMuted`/`#991b1b` "Erro" · timeout `warningMuted`/`#92400e` "Timeout" · pending `borderDefault`/`textPrimary` "Pendente"
- Linha selecionada: `background: vars.color.primaryAlpha`.

## Copy exata

- Título: `Inventário de Câmeras` · Subtítulo: `Onboarding em lote e diagnóstico de conectividade por câmera.`
- Labels: `Tenant ID` · `Marca` · `Status Probe` · placeholders `UUID do tenant`, `Ex: Intelbras`
- Botões: `Buscar` / `Carregando...` · `Testar Selecionadas ({n})` · `Importar CSV` · `Testar` / `...`
- Hint: `CSV: name,brand,ip,port,username,module,tenant_id`
- Estado inicial: `Clique em "Buscar" para carregar o inventário.`
- Import ok: `Importação concluída: {n} câmera(s) criada(s).` · com erros: `... {n} erro(s):\n  Linha {row}: {reason}` · `CSV vazio ou sem linhas de dados` · `Erro na importação`
- Erro de load: `Erro ao carregar inventário`
- Rodapé: `{n} câmera(s) encontrada(s)`
- Cabeçalhos: `Nome` · `Marca` · `IP / Host` · `Porta` · `Módulo` · `Probe` · `Codec` · `Substream` · `Tenant` · `Ações`

## Dados de exemplo (fixtures)

| Nome (modelo) | Marca | IP | Porta | Probe | Codec | Substream | Tenant |
|---|---|---|---|---|---|---|---|
| Câmera Pátio Norte (VIP 3230 B) | Intelbras | 192.168.10.21 | 554 | OK (há 22min) | h264 | Sim | Tenant RVB Industrial |
| Câmera Doca 3 (DS-2CD2043G2) | Hikvision | 192.168.10.34 | 554 | OK | h265 | Sim | Tenant RVB Industrial |
| Câmera Almoxarifado (VIP 1230 B) | Intelbras | 192.168.20.11 | 554 | Timeout | — | Não | Construtora Horizonte Sul |
| Câmera Portaria Sul | Hikvision | 10.0.4.18 | 8554 | Erro | — | — | Metalúrgica São Carlos |
| Câmera Linha Produção A (draft) | generic | 192.168.30.7 | 554 | Pendente | — | — | Transportadora Andrade & Filhos |
| Câmera Bomba Diesel 02 (VIP 3240) | Intelbras | 172.16.8.42 | 554 | OK | h264 | Não | Agroindústria Vale Verde |

## Estados

- **empty/inicial**: só filtros + ações + hint "Clique em Buscar..." — a página NÃO carrega dados sozinha.
- **default**: tabela com 6 câmeras (após clique em Buscar no harness).
- **loading**: botão "Carregando...".
- **selecionada**: linha com bg `primaryAlpha`; botão "Testar Selecionadas (n)" habilita.
- **probing**: botão da linha vira "..." desabilitado.
- **import ok/erro**: banners verde/vermelho com `white-space: pre-wrap`.

## Navegação e fluxos

- "Buscar" → `GET /v1/admin/inventory?tenant_id&brand&probe_status`.
- "Testar" → `POST /v1/admin/cameras/{id}/probe` (atualiza probe/codec/substream na linha).
- "Testar Selecionadas" → `POST /v1/admin/cameras/probe-batch` (máx 5 simultâneos no servidor).
- "Importar CSV" → file picker → parse client-side → `POST /v1/admin/cameras/import` → recarrega.

## Problemas identificados

1. **P1 contraste (dark)** — badges com hex fixos de tema claro: "Erro" `#991b1b` sobre `dangerMuted` em fundo escuro = **2.17:1**; "Timeout" `#92400e` = **2.40:1** (AdminInventoryPage.tsx:93-94). No light ambos ≥6.7. Classe task-063 (hardcode que só funciona num tema).
2. **P1 layout/copy** — coluna "Módulo" nunca exibe o módulo: renderiza apenas `(draft) ` quando `is_active=false` e string vazia caso contrário (:450-454) — coluna efetivamente vazia para toda câmera ativa.
3. **P2 hardcode** — paleta Tailwind fixa espalhada: `#d1fae5`/`#065f46` (badge OK e banner import), `#f0fdf4`/`#166534`/`#bbf7d0` (botão Testar), `#6ee7b7`, `#fca5a5`, `#059669` (Sim = 3.45:1 no light), `#6366f1` (4.38:1 no dark) — :92, :121, :381, :386, :391, :451, :530-537. Candidata direta ao guard-rail task-065.
4. **P2 inconsistency (dark)** — inputs de filtro sem `background`/`color` (`inputStyle` :499) → campos brancos default do browser destoando do input tokenizado (`admin.css` usa `bgElevated`); o select ao lado usa `bgCard` (escuro), criando dois estilos de campo na mesma linha. Evidência: `dark-empty.png`.
5. **P2 inconsistency** — página inteira fora do design system do admin (h1 22px vs `pageTitle` 20px; botões, tabela e banners próprios em vez de `s.card/s.table/s.btn*/alertBanner`).
6. **P2 a11y-other/UX** — inventário só carrega após clique manual em "Buscar"; estado inicial é uma instrução, não um convite com dados. Checkboxes de seleção sem `aria-label`.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063, task-065 (guard-rail), WS1 (d7a3ad3) — nenhum cobriu AdminInventoryPage.

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P1 dark | Badges "Erro" `#991b1b` = 2.17:1 dark; "Timeout" `#92400e` = 2.40:1 dark — **confirmados** em `dark-default.png` (badges presentes na coluna Probe) | PERSISTE |
| 2 | P1 layout | Coluna "Módulo" efetivamente vazia para câmeras ativas — **confirmado** em `dark-default.png` e `light-default.png` (coluna Módulo aparece com apenas "(draft)" na câmera genérica inativa, vazia nas demais) | PERSISTE |
| 3 | P2 hardcode | Paleta Tailwind fixa espalhada (badge OK, botão Testar, BoolBadge, etc.) — task-065 guard-rail impedirá novos; existentes não foram corrigidos | PERSISTE |
| 4 | P2 dark | Inputs "Tenant ID" e "Marca" mostram **FUNDO BRANCO com texto preto** no dark em `dark-empty.png` — contrastando com o select "Todos" ao lado que usa fundo escuro `bgCard`. Regressão visual confirmada. | PERSISTE |
| 5 | P2 | Página fora do design system do admin (h1 22px, componentes ad-hoc) | PERSISTE |
| 6 | P2 a11y | Inventário só carrega no clique; checkboxes sem `aria-label` | PERSISTE |

**Resumo develop:** 0 resolvidos · 6 persistem · 0 novos. Finding #4 (P2 dark inputs brancos) confirmado com evidência visual clara em `dark-empty.png` — inputs text com `inputStyle` sem `background` renderizam como branco UA sobre tema escuro, enquanto o select tokenizado aparece dark.
