# Validação de Contagem (CD-07) — spec visual

**Rota:** `/fueling/validation`
**Fontes:** `apps/frontend/src/pages/fueling/FuelingValidationPage.tsx` (página inteira, estilos inline), `src/components/ui/Badge/Badge` (+`Badge.css.ts`), `src/components/ui/Toast` (toasts de erro/sucesso — montado em `main.tsx` FORA do escopo de tema), `src/components/shared/LoadingSpinner`, `src/services/countingService`, `src/types/counting`
**Endpoint:** `GET /api/counting/sessions/validation-report?start&end&bay_id&threshold` → `data = ValidationReport`; edição inline via `PATCH /api/counting/sessions/<id>` (`manual_count` | `acceptance_status`) — não exercitado na captura.

**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (6 sessões + agregado diário) | ../screenshots/fueling-validation/dark-default.png | ../screenshots/fueling-validation/light-default.png |
| empty (relatório sem sessões) | ../screenshots/fueling-validation/dark-empty.png | ../screenshots/fueling-validation/light-empty.png |
| error (HTTP 500 → fallback + toasts) | ../screenshots/fueling-validation/dark-error.png | ../screenshots/fueling-validation/light-error.png |

## Layout — regiões

- Container `padding: 24px`, `maxWidth: 1100px`, `margin: 0 auto` (mesmo frame da FuelingPage).
- Header: flex space-between `marginBottom: 8` — `ClipboardCheck` 22px (`vars.color.success`) + h2 20px/700; botão "Atualizar" à direita.
- Subtítulo: parágrafo 13px `textMuted`, `marginBottom: 24`.
- Card de filtros: `cardStyle` com padding 16, flex `gap: 14`, `alignItems: flex-end`, wrap — 4 grupos label+input.
- Cards de resumo: grid `repeat(4, 1fr)` gap 14, `marginBottom: 28`.
- Tabela de sessões: card `padding: 0, overflow: hidden`, header interno `14px 20px`, wrapper `overflowX: auto`, `marginBottom: 24`.
- Agregado diário: mesmo padrão de card-tabela.
- `cardStyle` base: `background: vars.color.bgBase`, `border: 1px solid vars.color.bgSurface`, `borderRadius: 10`, padding `18px 22px` (mesma inversão semântica bgBase/bgSurface da FuelingPage).

## Árvore de componentes

- `FuelingValidationPage`
  - Header (`ClipboardCheck` + h2 `#f1f5f9` + botão ghost "Atualizar" com `RefreshCw` 13px)
  - Filtros: `Início` (`<input type=date>`) · `Fim` (`<input type=date>`) · `Baia` (`<select>` minWidth 140: "Todas" + opções acumuladas dos relatórios) · `Threshold (%)` (`<input type=number>` width 90 monospace) — todos com `inputStyle`: bg `bgSurface`, borda `borderStrong`, radius 6, **cor `#f1f5f9` hardcoded**, labels 11px uppercase `textMuted`
  - `LoadingSpinner` | fallback de erro | conteúdo:
  - 4× `SummaryCard` (mesma anatomia do KpiCard; valor 26px/700 monospace):
    - "Sessões Validadas" (accent default `#f1f5f9`) · "Sistema vs Manual" (accent `#6366f1`) · "Erro Agregado" (accent `success` ou `#f87171`) · "Resultado Geral" (card com `PassedBadge`)
  - Tabela "Sessões com conferência manual" — 10 colunas; cada linha é `SessionRow`:
    - Placa (monospace 600 `#f1f5f9`) · Baia (uuid 8 chars monospace 12px) · Direção (`Carga`/`Descarga`) · Início (12px `textMuted`, `dd/mm, hh:mm`) · Sistema (monospace `#a5b4fc`, right) · Manual (input number 76px + botão `Save` 13px — dirty: bg `rgba(99,102,241,0.15)`, borda `rgba(99,102,241,0.4)`, cor `#a5b4fc`; limpo: transparent/`textMuted`, cursor not-allowed) · Erro abs. (monospace right) · Erro % (monospace, `success` se passou senão `#f87171`) · Resultado (`Badge` success/danger: `Aprovado`/`Reprovado`) · Aceite (`Badge` warning/success/danger: `Pendente`/`Aceita`/`Rejeitada` + botões icon `Check` (bg `rgba(34,197,94,0.1)`) / `X` (bg `rgba(239,68,68,0.1)`) condicionais ao status)
  - Tabela "Agregado diário" — 7 colunas: Dia (`#f1f5f9`) · Sessões · Sistema (`#a5b4fc`) · Manual · Erro abs. · Erro % (semafórico) · Resultado (`PassedBadge`)
  - Zebra em ambas as tabelas: `rgba(255,255,255,0.015)` em linhas alternadas; th 11px uppercase `textMuted` padding `10px 14px`; td 13px `textSecondary`
  - Toasts (`ToastProvider` global): sucesso/erro das ações e do load

## Copy exata

- Título: `Validação de Contagem` · Botão: `Atualizar`
- Subtítulo: `Aceite das contagens do sistema vs conferência manual (CD-07). Sessões com erro acima do threshold são reprovadas.`
- Filtros: `Início` · `Fim` · `Baia` (opção `Todas`, opções `Baia {id8}`) · `Threshold (%)`
- Resumo: `Sessões Validadas`/`threshold {n}%` · `Sistema vs Manual` valor `{sys} / {man}`/`itens contados` · `Erro Agregado` valor `{p}%` (2 casas) ou `—`/`{abs} itens de diferença` · `Resultado Geral`
- Badges: `Aprovado` · `Reprovado` · `Pendente` · `Aceita` · `Rejeitada` (Badge renderiza uppercase)
- Colunas sessões: `Placa` · `Baia` · `Direção` · `Início` · `Sistema` · `Manual` · `Erro abs.` · `Erro %` · `Resultado` · `Aceite`; direções: load→`Carga`, unload→`Descarga`; vazio → `—`
- Empty sessões: `Nenhuma sessão validada no período` / `Sessões aparecem aqui após o registro da contagem manual.`
- Agregado diário: header `Agregado diário`; colunas `Dia` · `Sessões` · `Sistema` · `Manual` · `Erro abs.` · `Erro %` · `Resultado`; empty `Sem dados diários no período.`
- Fallback de erro: `Não foi possível carregar o relatório` (ícone `ClipboardCheck` 36px opacity .25)
- Tooltips (atributo `title`): `Salvar contagem manual` · `Aceitar sessão` · `Rejeitar sessão`; aria-label do input: `Contagem manual da sessão {id8}`
- Toasts: `Contagem manual atualizada` · `Contagem manual deve ser um inteiro >= 0` · `Erro ao salvar contagem manual` · `Sessão aceita` · `Sessão rejeitada` · `Erro ao atualizar aceite` · `Erro ao carregar relatório de validação` (na captura de erro o toast exibe o título técnico `HTTP 500` + `Erro interno do servidor`)

## Dados de exemplo (fixtures CD-07 do spec)

- Summary: 6 sessões · 1483/1470 · erro 0.88% (13 itens) · geral APROVADO · threshold 5%
- Sessões: RVB2C34/Carga/250→248/0.81%/Aprovado/Aceita · FKT7A81/Descarga/309→312/0.96%/Aprovado/Pendente · QXP4D18/Carga/196→180/8.89%/Reprovado/Rejeitada · JHM9E55/Carga/419→421/0.48%/Aprovado/Pendente · (sem placa)/—/102→96/6.25%/Reprovado/Pendente · PZX3F77/Descarga/207→213/2.82%/Aprovado/Aceita — baias `7f3e2a10`/`8a4f3b21`
- Diário: hoje 2 sessões 559/560 0.18% ✓ · ontem 2 615/601 2.28% ✓ · D-2 1 102/96 5.88% ✗ · D-3 1 207/213 2.9% ✓
- Empty: summary zerado com `error_pct: null` (exibe `—`) e `passed: true` → badge "APROVADO" mesmo sem sessões

## Estados

- **loading:** `LoadingSpinner`.
- **default:** filtros + 4 cards + 2 tabelas.
- **empty:** tabelas com mensagens internas; cards de resumo mostram 0/`—` mas "Resultado Geral" segue `APROVADO` (enganoso).
- **error:** fallback central "Não foi possível carregar o relatório" + toasts de erro empilhados no topo-direito — toasts SEM fundo opaco sobrepõem o header (ambos os temas).
- **dirty (input Manual):** botão Save troca para estilo índigo ativo; sem valor alterado fica cinza `not-allowed`.
- **saving:** input `disabled`, botão opacity .5.
- **hover:** nenhum elemento define hover (inline styles).

## Navegação e fluxos

- Alterar qualquer filtro refaz o `GET validation-report` (useEffect em `loadReport`).
- "Atualizar" refaz o load manualmente.
- Editar Manual + Save → `PATCH /counting/sessions/<id> {manual_count}` → toast + reload.
- `Check`/`X` no Aceite → `PATCH {acceptance_status: accepted|rejected}` → toast + reload (botão do status atual é ocultado).
- Sem modais/drawers; edição é inline.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 task-063:** título, placas, coluna Dia e valor default dos SummaryCards em `#f1f5f9` hardcoded → invisíveis no claro (1.0–1.1).
2. **P0 task-063 (operação bloqueada):** `inputStyle` com cor `#f1f5f9` sobre `bgSurface` (branco no claro) — datas, select Baia, threshold e contagem manual ficam com texto invisível: filtros e edição inutilizáveis no white-label claro.
3. **P1 task-066:** Toast global sem fundo opaco nos DOIS temas — `ToastProvider` montado em `main.tsx` fora do `AppShell` (classe de tema vanilla-extract), todas as `vars` do `Toast.css.ts` não resolvem → background transparente, texto sobrepõe o header.
4. **P1:** coluna Sistema/accent `#a5b4fc` 1.83 no claro; `#6366f1` e `#f87171` abaixo de 4.5 no claro; paleta índigo fora da identidade (ciano).
5. **P2:** badges (warning/success/danger) 1.83–3.04 sobre superfícies claras (tokens de status fixos do tema dark no `Badge.css.ts`).
6. **P2 copy:** toast de erro exibe `HTTP 500` cru; empty state afirma "APROVADO" com 0 sessões; fallback de erro não orienta recuperação.
7. **P2:** hover ausente em todos os interativos; página inteira inline styles fora do design system; zebra `rgba(255,255,255,0.015)` hardcoded.

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/fueling-validation.md · screenshots analisados: dark-default, light-default, dark-error, light-error, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P0 | Título "Validação de Contagem", valores de placas (RVB2C34, FKT7A81…) e o card SESSÕES VALIDADAS ("6") usam `#f1f5f9` hardcoded → invisíveis no claro. Confirmado: `light-default.png` mostra coluna PLACA vazia e card "6" invisível. | PERSISTE |
| 2 | P0 | `inputStyle` com `color: #f1f5f9` sobre `bgSurface` branco → datas, select Baia e threshold invisíveis no claro. Confirmado: `light-default.png` mostra campos de data em branco sem texto. Filtros e edição de contagem inutilizáveis no tema claro. | PERSISTE |
| ~~3~~ | ~~P1~~ | ~~Toast global sem fundo opaco — `ToastProvider` fora do escopo de tema~~. | **RESOLVIDO** (task-066) — `dark-error.png` e `light-error.png` confirmam toasts com fundo opaco e texto legível. |
| 4 | P1 | Accent `#a5b4fc` (coluna Sistema) 1.83:1 no claro; `#6366f1` e `#f87171` abaixo de 4.5:1 no claro; paleta índigo diverge da identidade ciano. | PERSISTE |
| 5 | P2 | Badges (warning/success/danger) com tokens fixos do tema dark → 1.83–3.04:1 sobre superfícies claras. | PERSISTE |
| 6 | P2 | Toast de erro exibe `HTTP 500` cru (copy técnico exposto ao usuário). Empty state APROVADO com 0 sessões (enganoso). Fallback de erro sem orientação de recuperação. | PERSISTE |
| 7 | P2 | Hover ausente; página inteira inline styles; zebra `rgba(255,255,255,0.015)` invisível no claro. | PERSISTE |
| 8 | P2 | **NOVO:** Toasts opaco mas posicionados sobre a topbar em dark (`dark-error.png`): o painel de toasts cobre parcialmente os elementos da topbar (Pro toggle, Auditor Visual). Em light a sobreposição é menor mas persiste. Positional issue independente da transparência já corrigida. | NOVO |

**Resumo:** 1 resolvido (finding 3, task-066) · 6 persistem · 1 novo (finding 8, posicionamento de toast).
