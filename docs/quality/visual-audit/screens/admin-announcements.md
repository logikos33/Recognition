# Comunicados — spec visual

**Rota:** `/admin/announcements`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminAnnouncementsPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `adminService.getAnnouncements/createAnnouncement/deleteAnnouncement`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-announcements/dark-default.png` | `../screenshots/admin-announcements/light-default.png` |
| empty | `../screenshots/admin-announcements/dark-empty.png` | `../screenshots/admin-announcements/light-empty.png` |
| modal Novo Comunicado | `../screenshots/admin-announcements/dark-modal-novo-comunicado.png` | `../screenshots/admin-announcements/light-modal-novo-comunicado.png` |

## Layout — regiões

- Shell AdminLayout (sidebar ativa em **Comunicados**, seção RELATÓRIOS).
- `pageRoot` (padding 32px, maxWidth 1200) → `pageHeader` (flex space-between, mb 32) → card único com a tabela.
- **Modal** (ad-hoc, `TODO-WS1` no source): `position: fixed; inset: 0; background: vars.color.overlay` (rgba(0,0,0,0.7)), flex center, `zIndex: 1000`. Caixa = `s.card` com `width: 480px` (bg bgSurface opaco, borda borderSubtle, radius 6, padding 24). Campos empilhados com `marginBottom: 12/16`, labels `muted` com `marginBottom: 4`, rodapé flex `justify-content: flex-end` (gap 8).

## Árvore de componentes

- `pageHeader`
  - `pageTitle` "Comunicados" + `pageSubtitle` "{n} comunicados ativos"
  - `btnPrimary` (ciano, texto branco) com `Plus` 14px — "Novo Comunicado"
- `alertBanner.danger` (condicional)
- `card` → `table`
  - th: `Tipo` · `Título` · `Alvo` · `Publicado` · `Expira` · (vazio p/ ações)
  - Linha (`trHover`): badge de tipo (`s.badge` + inline `background: rgba(59,130,246,0.1); color: vars.color.primary`) · `<strong>{title}</strong>` + preview `muted` (`content.slice(0, 60)`) · alvo `muted` · datas `toLocaleDateString('pt-BR')` · `btnGhost` compacto (`padding: 3px 8px; fontSize: 11`) com `Trash2` 11px
- Modal "Novo Comunicado": inputs `s.input` full-width (Título), `textarea` (Conteúdo, minHeight 80, resize vertical), `s.select` (Tipo: info/maintenance/feature/security), input Alvo; botões `btnGhost` "Cancelar" e `btnPrimary` "Publicar".

## Copy exata

- Título: `Comunicados` · Subtítulo: `{items.length} comunicados ativos`
- Botão: `Novo Comunicado`
- Cabeçalhos: `Tipo` · `Título` · `Alvo` · `Publicado` · `Expira`
- Vazio: `Nenhum comunicado`
- Confirm nativo ao excluir: `Arquivar este comunicado?` · erro genérico: `Erro`
- Modal: título `Novo Comunicado`; labels `Título`, `Conteúdo`, `Tipo`, `Alvo (all / tenant:uuid)`; botões `Cancelar` / `Publicar` (saving: `Criando...`); erro: `Erro ao criar comunicado`
- Valores do select Tipo (crus): `info` · `maintenance` · `feature` · `security`
- Célula de data nula: `—`

## Dados de exemplo (fixtures)

| Tipo | Título | Preview (60 chars) | Alvo | Publicado | Expira |
|---|---|---|---|---|---|
| maintenance | Manutenção programada — 12/07 às 02h | "A plataforma ficará indisponível por até 40 minutos para atu" | all | 05/07/2026 | 12/07/2026 |
| feature | Novo módulo: Contagem de Produtos (beta) | "O módulo de contagem automática já está disponível para tena" | all | 02/07/2026 | 05/08/2026 |
| security | Atualização de política de senhas | "A partir de agosto, senhas expiram a cada 90 dias conforme p" | all | 27/06/2026 | — |
| info | Treinamento agendado — Tenant RVB | "Retreino do modelo EPI agendado para o próximo sábado com o" | tenant:t-0001 | 24/06/2026 | 08/07/2026 |
| info | Relatórios mensais disponíveis | "Os relatórios consolidados de junho já podem ser exportados" | all | 21/06/2026 | — |

Modal preenchido no harness: Título "Janela de manutenção — atualização do worker"; Conteúdo "O worker on-premise do Tenant RVB Industrial será atualizado para a versão 2.4 nesta sexta-feira, sem impacto nas câmeras."; Tipo `info`; Alvo `all`.

## Estados

- **default**: 5 linhas; hover `bgHover`.
- **empty**: linha única `Nenhum comunicado` centralizada.
- **carregando**: `Carregando...` no card.
- **erro**: `alertBanner.danger` na página e/ou dentro do modal.
- **modal aberto**: backdrop `overlay` escurece a página (verificado por medição de brilho: 238→71 no light); "Publicar" desabilitado sem título; saving → "Criando...".

## Navegação e fluxos

- "Novo Comunicado" → abre modal ad-hoc (estado local `showModal`).
- "Publicar" → `POST createAnnouncement` → fecha modal e recarrega lista.
- Lixeira → `confirm()` nativo → `deleteAnnouncement` (arquivar) → recarrega.
- "Cancelar" fecha o modal sem limpar erro global.

## Problemas identificados

1. **P1 contraste (light)** — badge de tipo: `vars.color.primary` #06b6d4 sobre `rgba(59,130,246,0.1)` sobre branco = **2.16:1** (texto 11px/600 exige 4.5). No dark passa (6.88).
2. **P2 hardcode** — `rgba(59,130,246,0.1)` é azul blue-500 fixo, fora da paleta ciano; usar `vars.color.primaryAlpha`.
3. **P2 inconsistency** — modal ad-hoc com `TODO-WS1` no source (fora do padrão Modal do kit / ADR-0023). Backdrop e fundo opaco presentes — **não** é o defeito 066.
4. **P2 copy** — Tipo e Alvo expõem chaves técnicas (`info`, `maintenance`, `all`, `tenant:uuid`); Alvo é input de texto livre exigindo sintaxe de backend em vez de um seletor de tenants.
5. **P3 copy** — preview do conteúdo trunca em 60 caracteres sem reticências (corta no meio da palavra: "para atu").
6. **P3 a11y-other** — exclusão usa `confirm()`/`alert()` nativos (fora do kit, sem branding).

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P1 | light | Badges de tipo | #06b6d4 sobre rgba(59,130,246,0.1) sobre branco = 2.16:1 (11px/600) — confirmado em light-default.png | **persists** |
| F-2 | P2 | ambos | Badge bg hardcode | rgba(59,130,246,0.1) = azul blue-500 fixo fora da paleta ciano | **persists** |
| F-3 | P2 | ambos | Modal | Modal ad-hoc TODO-WS1 (backdrop e fundo opaco OK, mas fora do kit) | **persists** |
| F-4 | P2 | ambos | Copy / UX | Tipo e Alvo em chaves técnicas; Alvo input livre com sintaxe backend | **persists** |
| F-5 | P3 | ambos | Preview conteúdo | Trunca em 60 chars sem reticências (corta no meio de palavra) | **persists** |
| F-6 | P3 | ambos | Exclusão | confirm()/alert() nativos fora do kit | **persists** |
| N-1 | P1 | light | Subtítulo | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Afeta "{n} comunicados ativos" 13px — falha WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
