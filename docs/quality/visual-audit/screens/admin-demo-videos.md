# Vídeos Demo — spec visual

**Rota:** `/admin/demo-videos` (guard client-side: `isSuperAdmin`, senão `<Navigate to="/" />`)
**Fontes:** `apps/frontend/src/modules/admin/pages/DemoVideosPage.tsx` (autocontida — não usa `admin.css.ts`; estilos inline) · API `GET/POST/DELETE /api/admin/demo-videos*` (**sem prefixo `/v1`**, diferente do resto do admin)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (tab Abastecimento) | `../screenshots/admin-demo-videos/dark-default.png` | `../screenshots/admin-demo-videos/light-default.png` |
| empty | `../screenshots/admin-demo-videos/dark-empty.png` | `../screenshots/admin-demo-videos/light-empty.png` |
| modal-upload | `../screenshots/admin-demo-videos/dark-modal-upload.png` | `../screenshots/admin-demo-videos/light-modal-upload.png` |

## Layout — regiões

- Shell AdminLayout. Conteúdo: `padding: 28; maxWidth: 900`.
- Cabeçalho: flex space-between (mb 24) — esquerda: ícone `Video` 20 `#a5b4fc` + h2 18px/700 `#f1f5f9` + badge `SUPERADMIN` (indigo, 11px/700, letterSpacing .05em); direita: botão "Upload de vídeo" (`rgba(99,102,241,0.2)` + borda `rgba(99,102,241,0.4)` + texto `#a5b4fc`).
- Banner explicativo (mb 24): `rgba(99,102,241,0.08)`, borda `rgba(99,102,241,0.2)`, radius 8, 13px textSecondary.
- Tabs por módulo (flex gap 4, mb 20): pill 8px 18px radius 6; ativa `rgba(99,102,241,0.18)` + `#a5b4fc`; inativa transparente + textMuted.
- Container da tabela: `background: bgBase; border: 1px vars.color.bgSurface` (token de FUNDO usado como borda), radius 10; header interno 12px 20px.
- Zebra: linha ímpar `rgba(255,255,255,0.015)`.
- **Modal**: overlay `vars.color.overlay` + `backdropFilter: blur(4px)`, zIndex 100; caixa `background: bgBase`, borda `1px bgSurface`, radius 12, padding 28, width 420/max 90vw.

## Árvore de componentes

- Header (ícone + h2 + badge + botão upload)
- Banner explicativo (strong "loop" em `#a5b4fc`)
- Tabs: `Abastecimento` (fueling, inicial) · `EPI` (epi) · `Controle de Acesso` (access_control)
- Card da tabela: header "Vídeos demo ativos — {módulo}" (13px/600 textMuted)
  - th uppercase 11px/600 textMuted: `Label` · `Câmera ID` · `Tamanho` · `Data de upload` · (ações)
  - td: label 13px/500 `#f1f5f9` (ou "sem label" em textMuted) · camera_id mono 12 textMuted · tamanho formatado (KB/MB) · data pt-BR · botão "Remover" (`Trash2` 12, borda `rgba(239,68,68,0.3)`, texto `#f87171`)
- Empty state: ícone `Video` 28 opacity .25 + "Nenhum vídeo demo cadastrado" (14/600) + hint 12px
- Modal upload: h3 "Upload de vídeo demo" (16/700 `#f1f5f9`) · bloco "MÓDULO" read-only (bg bgSurface, texto `#a5b4fc`) · "ARQUIVO MP4 *" input file · "LABEL (OPCIONAL)" input texto (bg bgSurface, borda borderStrong, texto `#f1f5f9`, placeholder `ex: Pátio Baia 01`) · erro 13px `#f87171` · botões "Cancelar" (ghost borda borderStrong) e "Fazer upload" (indigo)

## Copy exata

- Título: `Vídeos Demo` · badge `SUPERADMIN`
- Banner: `Vídeos MP4 aqui ficam em loop no lugar do feed HLS durante demonstrações. Apenas visível para superadmin — clientes nunca veem esta página nem os vídeos.`
- Tabs: `Abastecimento` · `EPI` · `Controle de Acesso`
- Header do card: `Vídeos demo ativos — Abastecimento`
- Cabeçalhos: `LABEL` · `CÂMERA ID` · `TAMANHO` · `DATA DE UPLOAD`
- Célula sem label: `sem label` · sem câmera: `—`
- Botões: `Upload de vídeo` · `Remover` · modal `Cancelar` / `Fazer upload` / `Enviando...`
- Empty: `Nenhum vídeo demo cadastrado` + `Faça upload de um MP4 para usar neste módulo durante demonstrações.`
- Loading: `Carregando...`
- Modal: `Upload de vídeo demo` · labels `MÓDULO`, `ARQUIVO MP4 *`, `LABEL (OPCIONAL)` · placeholder `ex: Pátio Baia 01`
- Validações: `Selecione um arquivo MP4.` · `Apenas arquivos MP4 são aceitos.` · `Erro no upload.`
- Confirm nativo: `Remover este vídeo demo?` · `Erro ao remover vídeo.`

## Dados de exemplo (fixtures, tab fueling)

| Label | Câmera ID | Tamanho | Data |
|---|---|---|---|
| Pátio Baia 01 | 12 | 46.0 MB | 28/06/2026 |
| Bomba Diesel 02 | 14 | 58.7 MB | 28/06/2026 |
| Descarga de Caminhão | — | 32.2 MB | 15/06/2026 |
| *sem label* | — | 500 KB | 27/05/2026 |

Modal preenchido no harness: label `Pátio Baia 03 — turno noturno`.

## Estados

- **default**: 4 linhas na tab Abastecimento; zebra sutil.
- **empty**: ícone + título + hint (bom empty state — convida à ação).
- **loading**: `Carregando...` centralizado (padding 48).
- **modal aberto**: backdrop escuro + blur; "Fazer upload" com opacity .6 durante envio.
- Trocar de tab recarrega a lista do módulo.

## Navegação e fluxos

- Tabs → `GET /api/admin/demo-videos?module={key}`.
- "Upload de vídeo" → abre modal (módulo travado na tab ativa) → `POST /api/admin/demo-videos/upload` (FormData) → fecha e recarrega.
- "Remover" → `confirm()` → `DELETE /api/admin/demo-videos/{id}`.

## Problemas identificados

1. **P0 hardcode/contraste (light)** — textos principais com `#f1f5f9` fixo (h2 :127, células Label :227, h3 do modal :282, texto do input :319): sob superfície clara white-label o ratio é **1.00–1.06:1 — invisível**. Nas capturas light, o título da página, a coluna Label inteira e o título do modal desaparecem; o texto digitado no input do modal é ilegível. Classe task-063.
2. **P1 hardcode (both)** — paleta indigo alheia à identidade (primary é ciano #06b6d4): `#a5b4fc` + `rgba(99,102,241,x)` em ícone, badge SUPERADMIN, botão upload, banner, tabs, "MÓDULO" do modal e "Fazer upload" (:116-117, :126, :130-141, :149-152, :173, :290, :346-348). No light, `#a5b4fc` sobre os fundos indigo-claros = **1.43–1.47:1** (botões/tab ativos ilegíveis).
3. **P2 hardcode** — zebra `rgba(255,255,255,0.015)` base-branca (:225) — padrão exato da task-063; "Remover"/erros `#f87171` = **2.54:1** no light (:247, :326).
4. **P2 inconsistency** — `vars.color.bgSurface` usado como **cor de borda** do card e do modal (:191, :209, :224, :279) — no light a borda fica branca sobre branco (a tabela perde o contorno); usar `borderSubtle/borderDefault`. Página inteira fora do `admin.css` e modal fora do padrão do kit (ADR-0023) — backdrop presente e fundo opaco, sem defeito 066.
5. **P3 inconsistency (API)** — endpoints sem prefixo `/v1` (`/api/admin/demo-videos`), único do grupo.

---

## Findings (develop — 2026-07-07)

### Contexto de mudanças relevantes
- **WS1** (d7a3ad3): `DemoVideosPage.tsx` usa **estilos inline exclusivamente** (`não usa admin.css.ts`). Por isso **não foi coberta** pela migração WS1.
- **task-063**: abordou painel de vídeo de Operações (TrainingModeLayout/RoiDrawer), **não** `DemoVideosPage`.
- **task-065**: guard-rail anti-hardcode no CI. A página ainda usa inline styles → escapa ao lint de CSS-in-JS.

### Tabela de findings

| # | Sev | Descrição | Status |
|---|---|---|---|
| 1 | P0 | Textos com `#f1f5f9` fixo invisíveis no light: título da página (h2), células da coluna Label nas linhas 1-3, título do modal "Upload de vídeo demo" e valor digitado no input de label. Confirmado em `light-default.png` (células Label vazias) e `light-modal-upload.png` (título ausente, valor do input invisível). | **PERSISTE** |
| 2 | P1 | Paleta indigo (`#a5b4fc` + `rgba(99,102,241,x)`) incompatível com identidade ciano: ícone, badge SUPERADMIN, botão "Upload de vídeo", banner, tabs, campo MÓDULO do modal, botão "Fazer upload". No light, botões/tabs ativos ≈ 1.43:1 (ilegíveis). Confirmado em `light-default.png` e `light-modal-upload.png`. | **PERSISTE** |
| 3 | P2 | Zebra `rgba(255,255,255,0.015)` (branca base) não adapta ao light; "Remover" `#f87171` ≈ 2.54:1 sobre branco no light. Confirmado em `light-default.png`. | **PERSISTE** |
| 4 | P2 | `vars.color.bgSurface` como cor de borda do card — no light o card perde contorno (borda branca sobre fundo branco). Confirmado em `light-default.png` (tabela sem bordas visíveis). | **PERSISTE** |
| 5 | P3 | Endpoints sem prefixo `/v1` — inconsistência de API vs. restante do grupo admin. | **PERSISTE** |

### Novos findings (develop)

| # | Sev | Descrição |
|---|---|---|
| 6 | P2 | Modal `light-modal-upload.png`: a caixa modal tem fundo branco (`bgBase`) mas a **área MÓDULO** (campo read-only) usa `bgSurface` como fundo — no light fica cinza-claro com texto `#a5b4fc` (indigo claro sobre cinza ≈ 2.10:1). O campo parece preenchido mas o valor "Abastecimento" é ilegível. |

### Resumo

- **Resolvidos:** 0
- **Persistem:** 5
- **Novos:** 1 (P2 — módulo read-only no modal ilegível em light)

### Notas de observação visual
- A página é a única que **não herda nenhum token via admin.css.ts** — risco estrutural: toda melhoria de design system precisa ser aplicada manualmente nos inline styles.
- `dark-modal-upload.png`: modal funciona corretamente no dark; backdrop escuro + fundo opaco (sem defeito ADR-066).
- `dark-empty.png` / `light-empty.png`: empty state (ícone + título + hint) legível no dark; em light o ícone e textos do empty state usam tokens e aparecem corretamente.
