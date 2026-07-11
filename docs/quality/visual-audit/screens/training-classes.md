# Classes do Módulo EPI — spec visual

**Rota:** `/epi/training/classes` (também alcançável via botão "Configurar Classes" → `/module-classes`)
**Fontes:** `apps/frontend/src/pages/ModuleClassesPage.tsx`, `apps/frontend/src/components/ui/{Skeleton,Toast}`, `apps/frontend/src/services/api.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/training-classes/dark-default.png | ../screenshots/training-classes/light-default.png |
| detect-resultado (3 detecções) | ../screenshots/training-classes/dark-detect-resultado.png | ../screenshots/training-classes/light-detect-resultado.png |
| empty | ../screenshots/training-classes/dark-empty.png | ../screenshots/training-classes/light-empty.png |
| loading | ../screenshots/training-classes/dark-loading.png | ../screenshots/training-classes/light-loading.png |
| error (500) | ../screenshots/training-classes/dark-error.png | ../screenshots/training-classes/light-error.png |
| hover chip ativa | ../screenshots/training-classes/hover-classe-ativa.png | — |
| hover "Testar DINO" | ../screenshots/training-classes/hover-btn-testar-dino.png | — |

## Layout — regiões

- **Container**: `div` com `padding: '24px 32px'`, `maxWidth: 800` (alinhado à esquerda, não centralizado — diferente da Fila de Verificação, que centraliza com `margin: 0 auto`).
- Fluxo vertical: `h2` título → parágrafo descritivo (`marginBottom: 24`) → seção "Ativas" (`marginBottom: 32`) → seção "Inativas" (condicional, `marginBottom: 32`) → seção "Testar Detecção DINO" separada por `borderTop: 1px solid vars.color.borderDefault`, `paddingTop: 24`.
- Chips em `flex` com `flexWrap: wrap`, `gap: 8`.
- Linha de teste: `flex gap 8` — input `flex:1` + botão.

## Árvore de componentes

- `ModuleClassesPage`
  - `h2` "Classes do Módulo EPI" (sem cor explícita — herda do tema; OK nos 2 temas)
  - `p` descrição (`vars.color.textSecondary`)
  - Seção **Ativas**
    - `h3` "Ativas (N)" (14px/600 `textPrimary`)
    - Chips-botão por classe ativa: `padding 6px 14px`, `borderRadius: 20` (fora da escala de radius 4/6/10/16), `border: 2px solid <cls.color ?? primary>`, `background: <cls.color>22` (alpha hex) ou `primaryAlpha`, `color: <cls.color ?? primaryDark>`, texto `<display_name> ✓`, `title="Clique para desativar"`, `opacity 0.5` enquanto `toggling`
    - Vazio: `p` "Nenhuma classe ativa." (`textMuted`, 14px)
  - Seção **Inativas** (só se `inactive.length > 0`)
    - `h3` "Inativas (N)" (14px/600 `textMuted`)
    - Chips-botão: `border: 2px solid borderDefault`, `background: bgSurface`, `color: textMuted`, `title="Clique para ativar"`
  - Seção **Testar Detecção DINO**
    - `h3` "Testar Detecção DINO" (14px/600 `textPrimary`)
    - `p` instrução (`textSecondary`, 13px)
    - `input[type=text]` placeholder `ID do frame (UUID)` — **sem `background` nem `color` de token** (default do browser: branco no dark)
    - Botão "Testar DINO" (`background: primary`, `color: textOnPrimary`, radius 6, sem borda; `Detectando...` + opacity 0.7 quando ocupado) — **sem estado hover**
    - Caixa de resultado (após detect): `padding 12`, radius 6, **`background: '#f0fdf4'` e `border: '1px solid #bbf7d0'` hardcoded** (verde-claro fixo), 13px, **sem `color` explícita** (herda `textPrimary` do tema)
  - Loading: `Skeleton title` 180px + 6 linhas `Skeleton text 40%` + `Skeleton rect 44×24`
  - `Toast` (top fixo, `zIndex 9999`) para sucesso/erro/aviso

## Copy exata

- Título: `Classes do Módulo EPI`
- Descrição: `Ative ou desative as classes que o modelo deve detectar. Classes inativas não entram no treinamento nem na inferência.`
- Seções: `Ativas (6)` · `Inativas (2)` · `Nenhuma classe ativa.`
- Tooltips: `Clique para desativar` / `Clique para ativar`
- Teste DINO: `Testar Detecção DINO` · `Informe o ID de um frame existente para testar a detecção automática com os prompts configurados.` · placeholder `ID do frame (UUID)` · botão `Testar DINO` / `Detectando...`
- Resultado: `3 detecção(ões): capacete (91%), colete (84%), pessoa (97%)` · vazio: `Nenhuma detecção. Tente outro frame.`
- Toasts: `Informe o ID de um frame` · `Nenhuma detecção encontrada. Tente outro frame ou ajuste o prompt.` · `N detecção(ões) encontrada(s)` · `Erro ao testar detecção` · `Erro ao carregar classes` · `Erro ao alterar classe` · `<display_name> ativada` / `<display_name> desativada`

## Dados de exemplo (fixtures)

Ativas (6): Capacete `#10b981` (prompt "construction safety helmet") · Sem capacete `#ef4444` · Colete `#06b6d4` · Sem colete `#f59e0b` · Pessoa `#8ba3bc` · Luvas `#8b5cf6`.
Inativas (2): Óculos de proteção (`color: null`) · Sem óculos (`color: null`).
Frame de teste: `9f4e2a10-77b3-4c11-9d42-frame-patio` → 3 detecções: capacete 91%, colete 84%, pessoa 97%.

## Estados

- **default**: 6 chips ativos coloridos + 2 inativos cinza + formulário de teste vazio.
- **loading**: só skeletons, sem heading (âncora impossível para automação).
- **empty**: `Ativas (0)` + "Nenhuma classe ativa."; seção Inativas some.
- **error (500)**: **idêntico ao empty** ("Ativas (0)") + toast "Erro ao carregar classes" — falso estado saudável, sem retry.
- **detect-resultado**: caixa verde-clara com o texto das detecções; toast de sucesso sobreposto ao header.
- **hover**: chips e "Testar DINO" NÃO têm feedback visual (screenshots de hover idênticos ao default); único affordance é `cursor: pointer` + tooltip nativo.
- **toggling**: chip com `opacity 0.5` e `disabled`.

## Navegação e fluxos

- Chip ativa (click) → `PATCH /modules/epi/classes/<id>` `{is_active:false}` → chip move para "Inativas" + toast.
- Chip inativa (click) → mesmo PATCH com `true`.
- "Testar DINO" → `POST /modules/epi/classes/detect` `{frame_id}` → caixa de resultado + toast.
- Não há navegação de saída na página (volta-se pelo breadcrumb/menu).

## Problemas identificados (resumo)

1. **P0 (dark)**: caixa de resultado DINO com bg `#f0fdf4` hardcoded e texto herdado `textPrimary` (#f0f4f8) — **1.06:1, invisível no dark** (dark-detect-resultado). No claro fica legível (16.1:1) por acidente.
2. **P1 (light)**: chips ativos usam `cls.color` cru como cor de texto sobre `<color>22` — Colete `#06b6d4` 1.99:1, Sem colete `#f59e0b` 1.79:1 no claro. Contraste depende de cor arbitrária do banco.
3. **P1 (both)**: erro 500 renderiza como estado vazio "Ativas (0)" — falso-saudável, sem UI de erro/retry.
4. **P2 (dark)**: input do frame ID sem bg/color de token (branco default do browser no dark — quebra identidade; existe padrão `configInput` tokenizado na TrainingPage).
5. **P1 (both)**: toast de sucesso/erro renderiza colado no topo sobrepondo o header e fica ilegível (light-detect-resultado, dark-error).
6. **P2 (both)**: hover ausente em todos os elementos interativos da página.
7. **P3**: radius 20 dos chips fora da escala (4/6/10/16/full).

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P0 | dark | **PERSISTS** | Caixa de resultado DINO com `background: '#f0fdf4'` hardcoded — em `dark-detect-resultado` o box é visível (verde-claro) mas o texto herdado `textPrimary` (#f0f4f8 light) resulta em 1.06:1: conteúdo completamente invisível. |
| 2 | P1 | light | **PERSISTS** | Chips ativos usam `cls.color` cru como texto sobre `<color>22`: Colete `#06b6d4` = 1.99:1, Sem colete `#f59e0b` = 1.79:1 sobre fundo claro. Confirmado em `light-default`. |
| 3 | P1 | both | **PERSISTS** | Erro 500 renderiza como "Ativas (0)" sem distinção de falha — falso-saudável sem UI de retry. |
| 4 | ~~P2~~ | dark | **RESOLVED** | ~~Input do frame ID sem token de bg/color (branco default do browser no dark)~~ — `dark-default` mostra input com fundo escuro e placeholder visível, usando estilo tokenizado. |
| 5 | P1 | both | **PERSISTS** | Toast de sucesso/erro renderiza colado ao topo sobrepondo o header (`dark-detect-resultado` mostra toast sobre a topbar). |
| 6 | P2 | both | **PERSISTS** | Hover ausente em chips e botão "Testar DINO" — screenshots de hover idênticos ao default. |
| 7 | P3 | both | **PERSISTS** | Radius 20px dos chips fora da escala de tokens (4/6/10/16/full). |
