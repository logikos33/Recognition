# Operações da Câmera (EPI) — spec visual

**Rota:** `/epi/cameras/:cameraId/operations` (auditada com `cameraId=1`)
**Fontes:**
- `apps/frontend/src/pages/epi/EpiOperationsPage.tsx` (página, breadcrumb)
- `apps/frontend/src/components/training/TrainingModeLayout.tsx` (orquestrador view/edit + tabela)
- `apps/frontend/src/components/training/modes/ViewMode.tsx` / `modes/EditMode.tsx` (headers)
- `apps/frontend/src/components/training/panels/RegisteredToolsPanel.tsx` (sidebar view)
- `apps/frontend/src/components/training/panels/OperationCatalogPanel.tsx` (sidebar edit)
- `apps/frontend/src/components/training/canvas/LiveVideoWithOperations.tsx` (vídeo + ROIs + botão "Operação")
- `apps/frontend/src/components/training/modals/OperationCreateModal.tsx` (wizard "Nova Operação")
- `apps/frontend/src/components/training/modals/OperationEditModal.tsx` (modal "Editar")
- `apps/frontend/src/components/training/modals/DeleteConfirmModal.tsx` (modal "Confirmar exclusão")
- `apps/frontend/src/components/training/operationTypeForms/{PositionForm,OverlapFixedForm,OverlapDynamicForm,CountStaticForm}.tsx`
- `apps/frontend/src/components/ui/Modal/Modal.tsx` + `Modal.css.ts` (Radix Dialog), `ui/Stepper/Stepper.tsx`
- Hooks: `useOperations`, `useOperationTypes`, `useOperationLiveStatus`, `useMonitoringSocket`

**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | `../screenshots/epi-operations/dark-default.png` | `../screenshots/epi-operations/light-default.png` |
| empty | `../screenshots/epi-operations/dark-empty.png` | `../screenshots/epi-operations/light-empty.png` |
| loading | `../screenshots/epi-operations/dark-loading.png` | `../screenshots/epi-operations/light-loading.png` |
| error (500 → cai no vazio) | `../screenshots/epi-operations/dark-error.png` | `../screenshots/epi-operations/light-error.png` |
| wizard passo 1 (Tipo) | `../screenshots/epi-operations/dark-wizard-step1-tipo.png` | `../screenshots/epi-operations/light-wizard-step1-tipo.png` |
| wizard passo 2 (Configuração) | `../screenshots/epi-operations/dark-wizard-step2-configuracao.png` | `../screenshots/epi-operations/light-wizard-step2-configuracao.png` |
| wizard passo 3 (Revisão) | `../screenshots/epi-operations/dark-wizard-step3-revisao.png` | `../screenshots/epi-operations/light-wizard-step3-revisao.png` |
| modal Editar | `../screenshots/epi-operations/dark-modal-editar-operacao.png` | `../screenshots/epi-operations/light-modal-editar-operacao.png` |
| modal Excluir | `../screenshots/epi-operations/dark-modal-excluir-operacao.png` | `../screenshots/epi-operations/light-modal-excluir-operacao.png` |
| hover botão "Operação" | `../screenshots/epi-operations/hover-btn-operacao.png` (dark) | — |
| hover botão "Editar" | `../screenshots/epi-operations/hover-editar.png` (dark) | — |

## Layout — regiões

Coluna vertical de altura `100vh`, fundo `vars.color.bgBase` (#0a0c10 dark / #f4f5f7 light):

1. **Breadcrumb** (topo, `padding: 10px 16px`, `borderBottom: 1px solid borderDefault`): botão "← Câmeras" (transparente, textMuted, 13px) · separador "/" (textPrimary) · "Câmera 1" (13px textMuted) · "/" · "Operações" (13px textSecondary).
2. **Header de modo** (`padding: 12px 20px`, `minHeight: 52`, `borderBottom: 1px solid borderDefault`):
   - *View*: `<h2>` "Operações — Câmera 1" (16px/600, textSecondary).
   - *Edit*: fundo `rgba(59,130,246,0.06)`, borda inferior `#1e3a5f` (hardcode), dot 8px `primary` com glow, label "MODO EDIÇÃO" (13px/600, primaryLight, letterSpacing .05em), à direita botões "Cancelar" (ghost, borda borderDefault) e "Salvar" (bg primary, texto `textPrimary` — bug de token).
3. **Corpo** (flex horizontal, `flex:1, overflow:hidden`):
   - **Sidebar** 240px fixos, `borderRight: 1px solid borderDefault`, scroll vertical. Modo view → RegisteredToolsPanel; modo edit → OperationCatalogPanel.
   - **Main** `flex:1, padding: 20, gap: 20` (coluna): painel de vídeo 640×360 (radius 8, bg #000) + tabela-resumo (radius 8, borda borderDefault) quando houver operações.
4. **Modais** via Radix `Dialog.Portal` (montados em `document.body` — fora do escopo da classe de tema, ver Problemas). Overlay `vars.color.overlay` + blur(4px); content `bgElevated`, radius `xl` (16px), maxWidth 520px (criar/editar) / 440px (excluir); header 16px/700; body `padding lg` (24px); footer com `bgSurface`.

Escala de espaçamento observada: 4/6/8/10/12/16/20/24 (10/12/20 fora da escala tokenizada 4/8/16/24/32/48).

## Árvore de componentes

```
EpiOperationsPage
├── Breadcrumb (botão Voltar + trilha)
└── TrainingModeLayout (moduleId='ppe', hlsUrl=…/stream.m3u8?token=…)
    ├── ViewMode (h2 título) | EditMode (dot + "MODO EDIÇÃO" + Cancelar/Salvar)
    ├── aside 240px
    │   ├── RegisteredToolsPanel (modo view)
    │   │   ├── header "FERRAMENTAS CADASTRADAS" + contador (11px uppercase textMuted)
    │   │   └── card por operação (bgSurface, borda borderDefault, radius 6, margin 0 8px, padding 10px 12px)
    │   │       ├── linha 1: nº "01" (mono 11px textMuted) + ícone do tipo (14px textMuted) + nome (13px/500 textSecondary, ellipsis)
    │   │       ├── linha 2: ícone+status (12px, cor por status) · "·" · último valor (mono 11px textSecondary) · "·" · timestamp (11px textMuted)
    │   │       └── linha 3: botões "Editar" (texto primary) e "Excluir" (texto #ef4444), borda `#2a2a2a` (hardcode), radius 4, 11px
    │   └── OperationCatalogPanel (modo edit)
    │       ├── seção "TIPOS CANÔNICOS" (11px uppercase textMuted)
    │       ├── TypeCard × N (bgSurface, borda borderDefault, radius 6; hover JS → bg `#181818` hardcode)
    │       │   └── ícone (18px primary) + type_label (13px/500 textSecondary) + description (11px textMuted)
    │       └── seção "ESPECÍFICOS DO MÓDULO" (se houver tipos não-canônicos)
    ├── main
    │   ├── LiveVideoWithOperations (640×360)
    │   │   ├── CameraPlayer (HLS; "Conectando..." enquanto abre)
    │   │   ├── DetectionOverlay (canvas, pointerEvents none)
    │   │   ├── SVG de ROIs (polígonos tracejados, fill 10%, cor por STATUS_COLORS hardcode; label mono "N. Nome")
    │   │   ├── botão "Operação" (top-right; bg rgba(0,0,0,.75), borda rgba(255,255,255,.2), texto #fff, ícone Settings)
    │   │   └── badge "EDITANDO" (modo edit; bg rgba(59,130,246,.85), texto #fff 11px/600)
    │   └── Tabela "FERRAMENTAS CADASTRADAS" (modo view, ≥1 operação)
    │       └── colunas: ID · TIPO · NOME · STATUS · ÚLTIMO VALOR (ver Dados)
    ├── OperationCreateModal (wizard 3 etapas, Stepper "Tipo → Configuração → Revisão")
    ├── OperationEditModal (2 etapas "Configuração → Revisão", tipo travado)
    └── DeleteConfirmModal (alerta danger + regra de digitação se resultCount>0; aqui resultCount=0 fixo)
```

## Copy exata

**Breadcrumb/página:** `Câmeras` · `Câmera {id}` · `Operações` · título `Operações — Câmera {id}` · fallback `Câmera não encontrada`.

**RegisteredToolsPanel:** `Carregando operações...` · `Nenhuma operação cadastrada` · `Clique em "Operação" no vídeo para criar` · header `Ferramentas cadastradas` + contador · status: `ativa` / `alerta` / `erro` / `inativa` · valor vazio `—` · timestamps: `agora`, `{n}s atrás`, `{n}min atrás`, `{n}h atrás` · botões `Editar` (title `Editar operação`), `Excluir` (title `Excluir operação`).

**Vídeo:** botão `Operação` (title `Modo de edição de operações`) · badge `EDITANDO` · labels de ROI `{n}. {nome}` (ex.: `1. Zona Portão Leste`).

**EditMode:** `MODO EDIÇÃO` · `• alterações não salvas` (se dirty) · `Cancelar` · `Salvar` / `Salvando...`.

**OperationCatalogPanel:** `Carregando tipos...` · `Tipos canônicos` · `Específicos do módulo` · `Nenhum tipo disponível para este módulo`.

**Tabela:** header `Ferramentas cadastradas` · colunas `ID`, `Tipo`, `Nome`, `Status`, `Último valor` · status cru (`active`, `error`, `warning`, `inactive`) · valor `—`.

**OperationCreateModal (Nova Operação):** título `Nova Operação` · steps `Tipo`, `Configuração`, `Revisão` · erros: `Selecione um tipo de operação`, `Nome é obrigatório`, `Desenhe o ROI com pelo menos 3 pontos`, `Erro ao criar operação` · botões: `← Voltar`, `Próximo: Configurar →`, `Próximo: Revisar →`, `Criar operação` / `Criando...` · label `Nome da operação *`, placeholder `Ex: {type_label} - Câmera 01` · revisão: `Nome:`, `Tipo:`, `Módulo:`, `ROI: {n} pontos`, `Ver configuração JSON` · fallback de tipo desconhecido: `Tipo "{typeId}" — configure via JSON:`.

**PositionForm:** `Classe monitorada *` · `Selecione uma classe` · `ROI ({n} pontos) *` · `Desenhe o ROI no vídeo ao lado (mínimo 3 pontos)` / `Polígono com {n} pontos definido` · `Métrica` (`Estado (dentro/fora)`, `Coordenadas`, `Ambos`) · `Confiança mínima: {n}%` (slider 10–95).

**OverlapDynamicForm:** `Classe A *` / `Classe B *` (`Selecione`) · `Métrica` (`Sobreposição IoU (%)`, `Distância mínima`, `Tempo de sobreposição (s)`) · `Threshold IoU: {n}%` (slider 1–80).

**OperationEditModal:** título `Editar: {nome}` · steps `Configuração`, `Revisão` · `Tipo: {type_id}` · `Nome *` · erros: `Nome é obrigatório`, `ROI precisa ter pelo menos 3 pontos`, `Erro ao atualizar operação` · revisão: `v{n} → v{n+1}`, `Nome: {nome}`, `ROI: {n} pontos`, `Ver configuração JSON` · botões `← Voltar`, `Próximo: Revisar →`, `Salvar alterações` / `Salvando...`.

**DeleteConfirmModal:** título `Confirmar exclusão` · `Esta ação não pode ser desfeita.` · `A operação "{nome}" será permanentemente removida.` · (se resultCount>0) ` O histórico de {n} resultado(s) também será descartado.` + `Digite o nome da operação para confirmar:` + `Nome não confere` · botões `Cancelar`, `Confirmar exclusão` / `Excluindo...` · erro `Erro ao excluir operação`.

**Modal genérico:** botão fechar aria-label `Fechar`. Stepper aria-label `Progresso`.

## Dados de exemplo (fixtures do harness)

`GET /api/cameras/1/operations?module_id=ppe` → 5 operações:

| # | type_id | Nome | Status | Último valor | Avaliada | Config relevante |
|---|---|---|---|---|---|---|
| 01 | `position` | Zona Portão Leste | active (`ativa`) | `dentro` | 1min atrás | ROI 4 pts, target_class person, confidence 0.6 |
| 02 | `count_static` | Contagem Doca 2 | error (`erro`) | `7.00` | 42min atrás | ROI 4 pts, threshold 12 |
| 03 | `overlap_dynamic` | Empilhadeira × Pedestre — Ala Norte | warning (`alerta`) | `18.40` | 6min atrás | forklift × person, iou 15 |
| 04 | `overlap_fixed` | Colete Zona de Carga | inactive (`inativa`) | — | — | ROI 4 pts, target_class vest |
| 05 | `count_static` | Contagem Pátio Norte | active (`ativa`) | `12.00` | 3min atrás | ROI 4 pts, threshold 20 |

`GET /api/modules/ppe/operation-types` → 4 tipos: `Contagem estática` ("Conta objetos de uma classe dentro de uma zona fixa"), `Sobreposição dinâmica` ("Mede sobreposição (IoU) entre duas classes móveis"), `Posição` ("Verifica permanência de uma classe dentro da zona de interesse"), `Linha de contagem` ("Conta cruzamentos de objetos sobre uma linha virtual").

Wizard passo 2 capturado com: nome "Sobreposição Empilhadeira × Pedestre", Classe A `forklift`, Classe B `person`, métrica IoU, threshold 10%.

## Estados

- **default:** sidebar com 5 cards; vídeo com 4 ROIs sobrepostas (só ops com ≥3 pontos; verde=active, vermelho=error, âmbar=warning, cinza=inactive) + "Conectando..."; tabela com 5 linhas.
- **empty:** sidebar mostra "Nenhuma operação cadastrada" + "Clique em \"Operação\" no vídeo para criar"; tabela oculta; vídeo sem ROIs.
- **loading:** sidebar "Carregando operações..."; resto igual ao empty.
- **error (500):** **idêntico ao empty** — `TrainingModeLayout` não consome `error` do `useOperations`; falha degrada silenciosamente para "Nenhuma operação cadastrada" (defeito).
- **hover:** botão "Operação", "Editar", "Excluir" e cards **não têm feedback hover** (estilos inline sem :hover — screenshots hover idênticos ao default). Única exceção: TypeCard do catálogo (hover JS para `#181818`, hardcode que quebra no tema claro) e o botão fechar do Modal (token bgHover).
- **modo edição:** header azul "MODO EDIÇÃO", sidebar troca para catálogo de tipos, badge "EDITANDO" no vídeo, wizard abre automaticamente.
- **wizard/modais:** conteúdo do modal SEM fundo opaco nos dois temas (defeito 066 — ver Problemas); passo selecionado no passo 1 ganha bg `rgba(59,130,246,0.15)` + borda primary.

## Navegação e fluxos

- "← Câmeras" → `/epi/cameras`.
- Botão "Operação" (vídeo) → entra em modo edit **e** abre `OperationCreateModal` (wizard). Fechar/Cancelar → volta ao modo view.
- TypeCard do catálogo (sidebar em modo edit) → reabre o wizard.
- Wizard: Tipo → (validação) → Configuração (nome + form por tipo) → (validação ROI ≥3 pts p/ position/overlap_fixed/count_static) → Revisão → `POST /cameras/1/operations`.
- "Editar" no card → `OperationEditModal` (`PUT /operations/{id}`).
- "Excluir" no card → `DeleteConfirmModal` (`DELETE /operations/{id}`; digitação do nome só se `resultCount > 0` — aqui sempre 0).
- "Salvar" do EditMode → volta ao view + `refetch()`.

## Problemas identificados (resumo)

1. **P0 · defeito 066 confirmado nos DOIS temas:** todos os modais (wizard, editar, excluir) renderizam sem fundo opaco — o `Dialog.Portal` do Radix monta em `document.body`, fora da `<div>` que carrega a classe de tema vanilla-extract (`AppShell.tsx:33`); todas as `vars.*` de `Modal.css.ts` (bgElevated, overlay, borders) resolvem para CSS vars indefinidas → background transparente e overlay sem escurecimento (só o blur literal funciona). Vídeo/ROIs vazam atrás do formulário; no tema claro os labels ficam escuros sobre o vídeo preto = ilegível.
2. **P1 · classe 063:** `STATUS_COLORS` (#22c55e/#f59e0b/#ef4444/#6b7280) inline em `LiveVideoWithOperations`, `TrainingModeLayout` (tabela), `RegisteredToolsPanel`; no tema claro `#f59e0b` cai a 2.15:1 e `#ef4444` a 3.76:1 sobre branco.
3. **P1 · erro silencioso:** 500 em operations = tela "vazia" enganosa.
4. **P1 · wizard bloqueia tipos com ROI:** `PositionForm` descarta `onRoiChange` (`_onRoiChange`) — impossível desenhar 3 pontos no modal; validação impede avançar.
5. **P2 · hardcodes de borda/hover:** `#2a2a2a` (botões do card), `#141414` (linhas da tabela), `#181818` (hover do TypeCard), `#1e3a5f` + `rgba(59,130,246,…)` (EditMode/badge/seleção — azul #3b82f6 divergente do primary ciano).
6. **P2 · contraste dos CTAs:** branco sobre `primary` #06b6d4 = 2.43:1 ("Próximo", "Criar operação"); "Salvar" do EditMode usa `textPrimary` sobre primary (2.20:1 + quebra em white-label).
7. **P2 · vocabulário inconsistente:** sidebar traduz status (`ativa/erro`), tabela mostra cru (`active/error`) e `type_id` técnico (`count_static`).
8. **P3 · hover ausente** em botões interativos; **P3 ·** label de ROI "3. Colete…" colide com o botão "Operação"; **P3 ·** separadores "/" do breadcrumb em textPrimary (mais fortes que os itens).

Detalhamento com ratios e refs no findings JSON da auditoria.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P0 | dark | **PERSISTS** | Modais (wizard "Nova Operação" e "Confirmar exclusão") ainda renderizam sem fundo opaco no dark — `dark-wizard-step1-tipo` e `dark-modal-excluir-operacao` mostram conteúdo sobre vídeo/ROIs visíveis sem overlay. No light o wizard aparece mais legível (background branco acidental). Defeito 066 parcialmente corrigido só para ConfirmDialog em Câmeras; aqui persiste. |
| 2 | ~~P1~~ | both | **RESOLVED (task-068)** | ~~`CameraPlayer` 640×360 fixo → overlay clipado~~ — `dark-default` e `light-default` mostram "Câmera offline — reconectando..." e botão "Reconectar" completamente visíveis e corretamente dimensionados dentro do painel de vídeo 640×360. |
| 3 | ~~P2~~ | both | **RESOLVED** | ~~`retryBtn` roxo #8b5cf6 hardcoded~~ — botão "Reconectar" em ambos os temas usa ciano/primary tokenizado (`dark-default`, `light-default`). |
| 4 | P1 | both | **PERSISTS** | `STATUS_COLORS` (#22c55e/#f59e0b/#ef4444/#6b7280) hardcoded inline em `LiveVideoWithOperations`, tabela e `RegisteredToolsPanel`: no light `#f59e0b` = 2.15:1 sobre branco; `#ef4444` = 3.76:1. |
| 5 | P1 | both | **PERSISTS** | Erro 500 em `GET /cameras/{id}/operations` é silencioso: UI mostra "Nenhuma operação cadastrada" sem diferença visual de falha. |
| 6 | P1 | both | **PERSISTS** | `PositionForm` descarta `onRoiChange` (`_onRoiChange`) — impossível desenhar ROI no modal; validação de ≥3 pontos bloqueia avanço. |
| 7 | P2 | both | **PERSISTS** | Hardcodes de borda/hover: `#2a2a2a` (botões card), `#141414` (linhas tabela), `#181818` (hover TypeCard), `#1e3a5f` + `rgba(59,130,246,…)` (EditMode/badge/seleção — azul divergente do primary ciano). |
| 8 | P2 | both | **PERSISTS** | CTA branco sobre `primary` #06b6d4 = 2.43:1 ("Próximo", "Criar operação"); "Salvar" EditMode usa `textPrimary` sobre primary = 2.20:1. |
| 9 | P2 | both | **PERSISTS** | Vocabulário inconsistente: sidebar mostra status traduzido (`ativa/erro`), tabela mostra cru (`active/error`) e `type_id` técnico (`count_static`). |
| 10 | P3 | both | **PERSISTS** | Hover ausente em botões interativos da sidebar; label ROI colide com botão "Operação"; separadores "/" do breadcrumb mais fortes que os itens. |
