# Editor White-Label do Tenant — spec visual

**Rota:** `/admin/branding/tenants/:id` (fixture: `t-0001`, dentro do `AdminLayout`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminBrandingEditorPage.tsx`; componentes: `modules/admin/components/TenantBrandingEditor.tsx`, `SurfacesEditorSection.tsx`, `ColorPicker.tsx`, `BrandingAssetUpload.tsx`, `BrandingPreview.tsx`; UI kit: `components/ui/{Panel,Button,Toast}`; tema: `theme/tenant-theme/{defaults,resolver,types}.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-branding-editor/dark-default.png` | `../screenshots/admin-branding-editor/light-default.png` |
| tab-superficies | `../screenshots/admin-branding-editor/dark-tab-superficies.png` | `../screenshots/admin-branding-editor/light-tab-superficies.png` |
| empty | `../screenshots/admin-branding-editor/dark-empty.png` | `../screenshots/admin-branding-editor/light-empty.png` |
| preview-tenant | `../screenshots/admin-branding-editor/dark-preview-tenant.png` | — (página já recolorida pelos vars do tenant) |

## Layout — regiões

- Conteúdo: `padding: 32px`, `maxWidth: 1100px`.
- Header breadcrumb: botão `← Tenants` (13px, `vars.color.textMuted`) + `/` (`vars.color.textDim`) + H2 nome do tenant (20px/700, `vars.color.textPrimary`) + badge condicional `Visualizando` (`vars.color.primaryAlpha` / `vars.color.primary`, 11px/600).
- Subtítulo 13px `vars.color.textMuted`, `margin: 0 0 28px`.
- Grid `1fr 320px`, `gap: 32`, `alignItems: start`:
  - Coluna esquerda: `Panel variant="surface" title="Configurações de Marca"` com o editor + linha de ações (`marginTop: 28`, `gap: 10`).
  - Coluna direita: wrapper `position: sticky; top: 20` com `Panel variant="surface" padding="md"` contendo `BrandingPreview`.

## Árvore de componentes

- `AdminBrandingEditorPage`
  - Breadcrumb (botão texto + separador + h2 + badge)
  - `Panel` "Configurações de Marca"
    - `TenantBrandingEditor` (coluna, `gap: 20`, 100% tokenizado)
      - Campo "Nome do produto": label 12px `vars.color.textSecondary`; input `vars.color.bgSurface` + `borderDefault`, radius 6, 14px
      - `ColorPicker` "Cor primária" e "Cor de acento": swatch `input[type=color]` 36×36 + input hex mono 90px + badge de contraste `N.NN:1 AA ✓/✗` (successMuted/dangerMuted). **Cheque compara contra `RECOGNITION_DEFAULT_SURFACES.bgBase` (#0a0c10 dark) quando `bgBase` não é passado**
      - `Button ghost sm` "Restaurar cores da marca" (disabled se não custom)
      - `BrandingAssetUpload` Logo: vazio → botão dashed "Fazer upload"; enviando → `Loader2` + "Enviando..."; preenchido → preview (h 36) + botão "Remover" (dangerMuted/danger)
      - `BrandingAssetUpload` Favicon (accept png/svg/webp, preview h 20)
      - `SurfacesEditorSection` — seção colapsável "Containers & Superfícies" (chevron + badge `customizado` primaryAlpha quando há override); aberta: parágrafo explicativo + 7 `ColorPicker` (bgBase, bgSurface, bgElevated, bgCard, textPrimary, textSecondary, border; cada um com cheque AA contra o bgBase DO TENANT) + `Button ghost sm` "Restaurar padrão da seção"
    - Ações: `Button primary` "Salvar"/"Salvando..." (ícone Save) · `Button secondary` "Visualizar como tenant" ⟷ "Sair do preview" (ícone Eye) · `Button ghost` "Resetar padrão" (ícone RotateCcw)
  - `Panel` sticky com `BrandingPreview`
    - Label "PREVIEW AO VIVO" (11px uppercase `vars.color.textMuted`)
    - `LoginPreview` (label "LOGIN"): mini-tela nas superfícies em edição; logo ou monograma; 2 inputs fake `bgCard`; botão "Entrar" na cor primária
    - `PanelModalPreview` (label "PAINEL + MODAL"): painel `bgSurface` + overlay mock `rgba(0,0,0,0.55)` (comentário `// allow`) + modal `bgElevated` com header "Modal (elevado)", corpo "Fundo em bgElevated, borda e textos do tenant." e footer "Cancelar"/"Confirmar"
    - `DashboardPreview` (label "DASHBOARD"): topbar com nome do produto na cor primária, 3 KPIs "42" (primary/accent/success) e mini gráfico de barras

## Copy exata

- Breadcrumb: `Tenants` / `{nome do tenant}` · badge `Visualizando`
- Subtítulo: `Personalize a identidade visual deste tenant — marca, cores e containers. Salva no banco de dados; aplicado no próximo boot do frontend.`
- Loading: `Carregando branding...`
- Labels: `Nome do produto` · `Cor primária` · `Cor de acento` · `Logo (PNG / SVG / JPEG — máx 2 MB)` · `Favicon (PNG / SVG — máx 2 MB)`
- Seção: `Containers & Superfícies` (badge `customizado`) · `Cores de fundo, texto e borda dos contêineres (painéis, cards e modais). Deixe no padrão Recognition se não precisar customizar.`
- Campos de superfície: `Fundo base do app` · `Superfície / painel` · `Elevado (modais, dropdowns)` · `Card` · `Texto primário` · `Texto secundário` · `Borda`
- Botões: `Restaurar cores da marca` · `Restaurar padrão da seção` · `Salvar`/`Salvando...` · `Visualizar como tenant`/`Sair do preview` · `Resetar padrão` · `Fazer upload` · `Remover` · `Enviando...`
- Toasts: `Branding salvo com sucesso` · `Erro ao salvar branding` · `Branding resetado para o padrão` · `Erro ao resetar branding` · `Logo enviado com sucesso` · `Erro no upload do logo` · `Favicon enviado com sucesso` · `Erro no upload do favicon` · `Visualizando como "{produto}"`
- Badge contraste: `{N.NN}:1 AA ✓` / `{N.NN}:1 AA ✗`

## Dados de exemplo (fixture t-0001 / RVB)

- Tenant: `Tenant RVB Industrial`; produto `RVB Safety Vision`; primária `#16a34a` (5.94:1 AA ✓); acento `#f59e0b` (9.11:1 AA ✓); logo SVG "RVB".
- Superfícies WS1: bgBase `#f4f5f7` (1.00:1 ✗) · bgSurface `#ffffff` (1.09:1 ✗) · bgElevated `#ffffff` (1.09:1 ✗) · bgCard `#eceef1` (1.07:1 ✗) · textPrimary `#1a1d23` (15.48:1 ✓) · textSecondary `#3f4650` (8.74:1 ✓) · border `#d4d8de` (1.31:1 ✗).
- Estado empty: defaults Recognition (`Recognition`, `#06b6d4` 8.06:1 ✓, `#ea580c` 5.50:1 ✓, sem logo/favicon).

## Estados

- **default**: formulário preenchido com RVB; seção de superfícies recolhida com badge `customizado`; preview com superfícies claras.
- **tab-superficies**: seção expandida, 7 pickers com badges de contraste (mistos ✓/✗ — ver problemas).
- **empty**: fallback `DEFAULT_BRANDING`; preview volta às superfícies dark padrão dentro do painel (claro no tema light — contraste intencional de "mini-telas dark").
- **loading**: texto `Carregando branding...` (tokenizado).
- **preview-tenant**: badge `Visualizando`; página inteira recolorida via `style#recognition-tenant-theme` em `:root`; botão vira "Sair do preview"; toast `Visualizando como "RVB Safety Vision"` **aparece transparente sobreposto à topbar** (ver problemas).
- **isSaving/isUploading**: botão "Salvando..." com loading; upload mostra "Enviando...".

## Navegação e fluxos

- `← Tenants` → `/admin/branding/tenants`.
- `Salvar` → `PUT /v1/admin/tenants/:id/branding` (formato flat snake_case).
- `Resetar padrão` → PUT com `DEFAULT_BRANDING` + remove preview.
- `Visualizar como tenant` → injeta cssVars do `resolveTheme(overrides)` em `style#recognition-tenant-theme`; `Sair do preview` limpa.
- Upload logo/favicon → `POST /v1/admin/tenants/:id/branding/logo` (não capturado — file chooser real).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P1** Badge de contraste `AA ✗` engana em campos de SUPERFÍCIE/BORDA: compara superfície×bgBase com régua de texto (4.5:1) — `#ffffff` vs `#f4f5f7` = `1.09:1 ✗` e bgBase vs ele mesmo = `1.00:1 ✗` para valores claros perfeitamente válidos; borda deveria usar 3:1 (componentes UI), superfícies nem são texto. Induz o admin a "corrigir" o que está certo (issue já apontada pelo builder).
2. **P2** Cheque AA das cores de MARCA (`Cor primária`/`Cor de acento`) compara contra o bgBase default dark (`#0a0c10`), não contra as superfícies do tenant — `#16a34a` passa (5.94:1) mas sobre `#f4f5f7` do RVB dá ~2.7:1.
3. **P1** Toast do preview (`Visualizando como...`) renderiza SEM fundo opaco e sobrepõe a topbar — texto embaralhado com "Auditor Visual/SUPERADMIN" (classe task-066; causa-raiz: `ToastProvider` montado fora do escopo do tema — ver design-system.md).
4. **P3** Preview "Entrar"/"Confirmar" usa `vars.color.textOnPrimary` fixo sobre a primária do tenant sem cheque de contraste (mock ilustrativo, 8–9px).
5. A página em si é o exemplo positivo do WS1: 100% tokenizada, funciona nos dois temas.

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P1 | ambos | SurfacesEditorSection | Badge AA ✗ engana em campos de superfície/borda (ratio de texto aplicado a tokens de fundo) — visível em dark/light-tab-superficies | **persists** |
| F-2 | P2 | ambos | ColorPicker/marca | Cheque AA das cores de marca compara contra bgBase dark padrão (#0a0c10), não contra as superfícies reais do tenant | **persists** |
| F-3 | P1 | ambos | Toast/preview | Toast `Visualizando como "RVB Safety Vision"` sem fundo opaco sobrepõe a topbar (confirmado em dark-preview-tenant.png — texto sobrepostos com "Auditor Visual/SUPERADMIN") | **persists** |
| F-4 | P3 | ambos | BrandingPreview | Preview mock "Entrar"/"Confirmar" sem cheque de contraste sobre primária do tenant (8–9px) | **persists** |
| N-1 | P1 | light | Breadcrumb / subtítulo | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca (#fff). Subtítulo 13px e link "← Tenants" 13px falham WCAG AA (4.5:1). Era borderline; agora claramente abaixo do mínimo. | **new** |

**Resolved:** nenhum nesta passagem.
