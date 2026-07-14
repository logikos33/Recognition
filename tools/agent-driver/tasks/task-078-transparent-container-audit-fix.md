# Task 078 — Auditoria ponta a ponta: containers/overlays transparentes sem fundo (onda de restyle WS1)

**Status**: DONE — re-auditoria de código (2026-07-14) achou a maior parte do inventário já resolvida
por trabalho anterior (não pela task-078): item 1 (CameraFpsConfig) fechado por `ff819d0`/`0d1a5db`;
item 2 (TrainingPage/AnnotationPage/ModelScenarioWizard) sem instâncias do padrão no código atual;
`EpiInvestigation.tsx` renomeado pra `InvestigationPage.tsx` (já em `ui/Modal`). Fix real aplicado:
`AlertsHistoryPage.tsx` — hex cru (`#1a1d23`/`#ef4444`) trocado por tokens, **sem** migrar pro
`ui/Modal` (decisão deliberada, ver achado abaixo). `AnnotationInterface.jsx` NÃO tocado — arquivo
marcado congelado em 3 lugares no código, conflita com o item 2 da spec; decisão: respeitar o freeze.

**ACHADO NÃO-PREVISTO NA SPEC (o mais importante desta task):** `ui/Modal`/`ui/AppDrawer`/`ui/Popover`
portalam via Radix pra `document.body`, fora da `<div>` onde `AppShell.tsx` aplica a classe de tema —
os tokens `vars.color.*` não chegam lá, então esses componentes renderizam com fundo TRANSPARENTE na
prática (confirmado via `getComputedStyle` em teste real). Isso inclui os modais que a spec listou como
"OK, já no ui/Modal" (`OperationCreateModal`, `DeleteConfirmModal`, `AdminPlansPage`,
`InvestigationPage`) — o próprio padrão de referência que a spec mandou reusar está quebrado quando
portalado. Por isso `AlertsHistoryPage.tsx` foi corrigido SEM migrar pro `ui/Modal` (teria trocado um
bug visual por outro). Não corrigido nesta task (blast radius: toda a plataforma) — recomenda-se task
dedicada de prioridade alta antes de qualquer nova migração pro `ui/Modal`. Detalhe completo em
`docs/quality/UX_FUNCTIONAL_BACKLOG.md` § task-078.
**Risk**: P1-ALTO (user-facing; bloqueia leitura/uso de painéis e modais) · risk:security no runner (front, revisar)
**Branch**: fix/task-078-transparent-container-audit
**Gate**: PR para develop · gate humano pra staging · SEM migration · SEM hardware
**Absorve**: task-063 (painel de vídeo) · **encerra** task-066 (modal Nova Operação já resolvido — ver §Achados)
**Referências**: ADR-0023 (padrão Container/Modal), WS1 em `docs/quality/UX_FUNCTIONAL_BACKLOG.md`, task-065 (guard-rail de cor)

## Sintoma (reportado pelo Vitor)
Ao clicar em certas funcionalidades, abre um container **sem fundo** — o conteúdo/vídeo atrás vaza e não dá
pra ver todas as opções. Pedido: **validar a plataforma de ponta a ponta** e corrigir a classe inteira, não
um caso isolado.

> Nota: os prints sinalizados pelo Vitor não chegaram anexados nesta rodada. Esta task foi montada a partir
> de **auditoria do código** (varredura completa de overlays em `apps/frontend/src`). Se o Vitor reanexar as
> marcações, cruzar com o inventário abaixo e adicionar qualquer tela faltante.

## Padrão CORRETO (fonte da verdade — reusar, não recriar)
- `components/ui/Modal/Modal.css.ts`: `overlay` = `vars.color.overlay` + `backdropFilter: blur(4px)` (z50);
  `content` = `background: vars.color.bgElevated` opaco (z51). Portal Radix.
- `components/ui/AppDrawer` (overlay + `bgElevated`), `ui/Popover` (`bgSurface`), `ui/Panel`, `ui/ConfirmDialog`.
- **Regra:** todo overlay reusa `ui/Modal`/`ui/AppDrawer`; conteúdo com **fundo opaco de token**
  (`bgElevated`/`bgSurface`/`bgCard`) + **backdrop**. Proibido container com `rgba(255,255,255,0.0x)` ou hex cru.

## Achados da auditoria (confirmados no código — C-04)

### CONFIRMADO — transparente sobre o vídeo (o bug principal; = task-063)
- **`components/cameras/CameraFpsConfig.tsx`** — painel "Desempenho por câmera" (Câmeras → câmera → detalhe,
  logo abaixo do `CameraPlayer`, em `pages/CamerasPage.tsx:307`).
  - `:76` container `background: 'rgba(255,255,255,0.04)'` + `:77` borda `rgba(255,255,255,0.08)` → some sobre a
    área escura do vídeo.
  - `:91,:120` labels `color: 'rgba(255,255,255,0.5)'` → falha AA.
  - `:99-114,:128-143` botões FPS/qualidade `background: 'transparent'`, texto `rgba(255,255,255,0.6)`, **sem hover**.
  - Cores cruas: `#c4b5fd`, `rgba(167,139,250,0.18)`, e (mais abaixo) `#ef4444`/`#f59e0b`.
  - **Fix:** envelopar em `ui/Panel` variante `card`/`elevated` (ou `background: vars.color.bgCard` + borda
    `borderDefault`); labels → `textSecondary`/`textMuted`; botões com estado não-selecionado **opaco** + `bgHover`
    no hover; trocar TODO hex/rgba por tokens.

### CORRIGIR na mesma onda — painéis internos quase-transparentes (mesmo anti-padrão, severidade menor)
`background: rgba(255,255,255,0.03–0.05)` em cards aninhados (não vazam vídeo porque o pai é opaco, mas ficam
"sem container" quando a superfície é escura, e usam valor cru):
- `pages/TrainingPage.tsx:122,544,607,706,744`
- `pages/AnnotationPage.tsx:151,191`
- `components/scenario/ModelScenarioWizard.tsx:389,409` (cards de revisão)
- `components/AnnotationInterface.jsx:774` (ignorar `AnnotationInterface.jsx.backup`)
- `pages/MonitoringPage.css.ts:251` — já anotado `allow: VMS overlay`; **manter** (exceção intencional).
- **Fix:** trocar por `vars.color.bgSurface`/`bgCard` conforme o nível da superfície.

### MIGRAR pro kit — modais custom que funcionam mas fogem do padrão (marcados `TODO-WS1`)
Têm backdrop + conteúdo opaco (não é o bug de transparência), porém usam **hex cru** e recriam o modal:
- `pages/AlertsHistoryPage.tsx:204,211` (`#1a1d23`) · `pages/epi/EpiInvestigation.tsx:211,218` (`#1a1d23`)
- Admin: `AdminTenantsPage`, `AdminUsersPage`, `AdminPlansPage`, `AdminVersionsPage`, `AdminChangelogPage`,
  `AdminAnnouncementsPage`, `AdminRolesPage`, `DemoVideosPage` · Quality: `QualityConfigPage`, `QualityReworkPage`,
  `QualityInspectionsPage` · `pages/epi/InvestigationPage.tsx`.
- **Fix:** migrar pro `ui/Modal`/`ui/AppDrawer` (ou no mínimo trocar hex por token). Priorizar os de `#1a1d23`.

### OK — não mexer (já corretos)
- **task-066 satisfeita:** `training/modals/OperationCreateModal` ("Nova Operação"), `OperationEditModal`,
  `DeleteConfirmModal`, `CameraWizard`, `CameraOnboardingWizard` — todos já no `ui/Modal`. → **encerrar task-066**.
- Dropdowns/menus opacos: `camera-grid/*`, `NotificationBell`, `chat`. Overlays sobre vídeo intencionais em
  `RoiDrawer`/`LiveVideoWithOperations` (chrome semi-opaco proposital).

## Escopo do fix
1. **CameraFpsConfig.tsx** — fundo opaco de token + labels/botões legíveis + hover + tokens. (fecha task-063)
2. **Tokenizar** os painéis internos `rgba(255,255,255,0.0x)` listados (exceto a exceção do MonitoringPage).
3. **Migrar/tokenizar** os modais `TODO-WS1` (priorizar `#1a1d23`), reusando `ui/Modal`.
4. **Não** tocar nos itens OK; **não** tocar em `.jsx.backup`.

## Aceite
- [ ] Nenhum container/overlay abre transparente sobre o vídeo/página; texto legível (contraste **WCAG AA**).
- [ ] `CameraFpsConfig` com fundo opaco, botões com estado não-selecionado visível + hover, "Salvar" visível.
- [ ] Painéis internos e modais `TODO-WS1` usando tokens do tema (zero `rgba(255,255,255,0.0x)` de container;
      zero hex cru de fundo/borda no escopo tocado) — coerente com o guard-rail da **task-065**.
- [ ] White-label preservado (cores vêm de tokens, ajustáveis por tenant — WS1).
- [ ] `tsc --noEmit` limpo; guard-rail 065 verde; sem regressão visual nos itens "OK".
- [ ] **Screenshots antes/depois** de cada tela tocada. PR para develop; gate humano pra staging.
- [ ] `docs/quality/UX_FUNCTIONAL_BACKLOG.md` (WS1) atualizado; task-063 e task-066 marcadas resolvidas por esta.

## Checkpoint
- Só front, SEM migration, SEM hardware. `risk:security` no runner (revisar). STOP-for-review ao fim.
