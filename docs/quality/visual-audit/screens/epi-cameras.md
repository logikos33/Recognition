# Câmeras (EPI) — spec visual

**Rota:** `/epi/cameras` (`EpiCameras` é wrapper direto de `CamerasPage`)

**Fontes:**
- `apps/frontend/src/pages/epi/EpiCameras.tsx`
- `apps/frontend/src/pages/CamerasPage.tsx` + `CamerasPage.css.ts`
- `apps/frontend/src/components/cameras/CameraFpsConfig.tsx` (painel "Desempenho por câmera", task-063)
- `apps/frontend/src/components/cameras/CameraModelAssignment.tsx` (task-045)
- `apps/frontend/src/components/cameras/CameraOnboardingWizard.tsx` (wizard "Adicionar Câmera", task-046)
- `apps/frontend/src/components/cameras/CameraWizard.tsx` + `CameraWizard.css.ts` + `WizardSteps.tsx` (wizard "Editar Câmera")
- `apps/frontend/src/components/ui/Modal/Modal.tsx` + `Modal.css.ts` (Radix Dialog + Portal)
- `apps/frontend/src/components/ui/ConfirmDialog/ConfirmDialog.tsx`
- `apps/frontend/src/components/ui/Toast/Toast.css.ts` (viewport fixed top 16 / right 16)
- `apps/frontend/src/components/ui/Skeleton/Skeleton.css.ts`
- Spec E2E: `apps/frontend/src/test/e2e/visual-audit/12-epi-cameras.spec.ts`

**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/epi-cameras/dark-default.png` | `../screenshots/epi-cameras/light-default.png` |
| detail | `../screenshots/epi-cameras/dark-detail.png` | `../screenshots/epi-cameras/light-detail.png` |
| detail-logs | `../screenshots/epi-cameras/dark-detail-logs.png` | `../screenshots/epi-cameras/light-detail-logs.png` |
| empty | `../screenshots/epi-cameras/dark-empty.png` | `../screenshots/epi-cameras/light-empty.png` |
| loading | `../screenshots/epi-cameras/dark-loading.png` | `../screenshots/epi-cameras/light-loading.png` |
| error | `../screenshots/epi-cameras/dark-error.png` | `../screenshots/epi-cameras/light-error.png` |
| wizard-step1..4 | `../screenshots/epi-cameras/dark-wizard-step{1..4}.png` | `../screenshots/epi-cameras/light-wizard-step{1..4}.png` |
| modal-edit | `../screenshots/epi-cameras/dark-modal-edit.png` | `../screenshots/epi-cameras/light-modal-edit.png` |
| modal-delete | `../screenshots/epi-cameras/dark-modal-delete.png` | `../screenshots/epi-cameras/light-modal-delete.png` |
| hover item lista | `../screenshots/epi-cameras/dark-hover-list-item.png` | — |
| hover Nova Camera | `../screenshots/epi-cameras/dark-hover-nova-camera.png` | — |

---

## Layout — regiões

- **Page** (`page`): flex column, `height: 100%`, `overflow: hidden`.
- **Page header** (`pageHeader`): flex space-between, padding `16px 32px` (`md xl`), `borderBottom: 1px solid borderSubtle`, `flexShrink: 0`.
  - Esquerda: título `h2` 22px/700 `textPrimary` + linha meta (gap 16, marginTop 4): contagem 13px `textMuted` + `Badge` de gateway.
  - Direita (`headerActions`, gap 8): `Button ghost sm` "Atualizar" (ícone RefreshCw 14) + `Button primary` "Nova Camera" (ícone Plus 15).
- **Split view** (`splitView`): flex, `flex: 1`, `minHeight: 0`, overflow hidden.
  - **Lista de câmeras** (`cameraList`): largura fixa `320px`, `flexShrink: 0`, `borderRight: 1px solid borderSubtle`, `overflowY: auto`.
    - Item (`cameraListItem`): flex align-center, gap 8, padding `8px 16px`, `borderBottom: 1px solid borderSubtle`, cursor pointer, hover `background: bgHover` (transition 150ms). Ativo: + `borderLeft: 3px solid primary` e `background: bgHover`.
    - Conteúdo do item: dot 8×8 (`success` se `stream_status ∈ {active, online}`, senão `textMuted`), nome 13px/600 `textPrimary` (ellipsis), local 11px `textMuted` (ellipsis, maxWidth 120px).
  - **Painel de detalhe** (`detailPanel`): `flex: 1`, `overflowY: auto`, padding 24 (`lg`), flex column, gap 24.
    1. `previewWrap`: 16:9, radius 10 (`lg`), `background: #000`, `maxHeight: 360px`, overflow hidden. Dentro: `CameraPlayer` (se stream ativo) OU placeholder inline 640×360 `rgba(0,0,0,0.3)` com texto `rgba(255,255,255,0.5)` 14px. **BUG: colapsa a ~0px (sem `flexShrink: 0`) — invisível nos screenshots.**
    2. `detailFields`: grid 2 colunas, gap 16. Cada `fieldGroup`: label 11px/600 uppercase letterSpacing 0.05em `textMuted`; valor 13px `textPrimary`, padding `6px 8px`, `background: bgSurface`, `border: 1px solid borderSubtle`, radius 4 (`sm`).
    3. `CameraModelAssignment`: h4 13px/600 `textSecondary` (ícone Cpu 14) + grid `auto-fit minmax(180px, 1fr)` gap 12 com 3 selects (label 11px uppercase `textMuted`; select `background: bgSurface`, `border: 1px solid borderStrong`, radius 6, `color: #f1f5f9` hardcoded, padding `6px 10px`, 13px).
    4. `CameraFpsConfig` (painel): `background: rgba(255,255,255,0.04)`, `border: 1px solid rgba(255,255,255,0.08)`, radius 8, padding `12px 14px`, flex column gap 10. Título 13px/600 com ícone Zap 14 `primaryLight`. Chips FPS/qualidade: padding `4px 10px`, radius 5, selecionado `border 1px primaryLight` + `bg rgba(167,139,250,0.18)` + `color #c4b5fd`/600; não selecionado `border rgba(255,255,255,0.12)` + `color rgba(255,255,255,0.6)`. Faixa de carga: `bg rgba(0,0,0,0.2)`, radius 6, padding `7px 10px`, 11px `rgba(255,255,255,0.65)`, `borderLeft: 3px solid <cor da carga>` (`success` <50%, `#f59e0b` 50–79%, `#ef4444` ≥80%).
    5. Dica RTSP: botão texto 12px `rgba(139,92,246,0.7)` (ícone Info 13); box expandida (`rtspTip`): 12px `textMuted`, `bg rgba(139,92,246,0.05)`, `border rgba(139,92,246,0.15)`, radius 6, lineHeight 1.5.
    6. `detailActions`: flex gap 8 wrap — botões sm.
    7. Logs (se houver): `sectionTitle` 13px/700 + `logList` (gap 4); `logItem` 12px `textSecondary`, `bg bgSurface`, radius 4, padding `4px 8px`; timestamp com opacity 0.5.
  - **Detalhe vazio** (`detailEmpty`, sem seleção): centro flex column, ícone Camera 40 opacity 0.2, texto 14px `textMuted`.
- **Empty state global** (0 câmeras, `emptyState`): padding `60px 40px` centrado, `bg bgCard`, radius 10, `border borderDefault`; ícone Camera 48 opacity 0.3; título 18px/600; texto 14px `textMuted`; botão primary.
- **Toasts**: viewport fixed `top: 16; right: 16`, width 340, zIndex 9999 — sobrepõe o header do app.

## Árvore de componentes

```
EpiCameras
└─ CamerasPage
   ├─ pageHeader
   │  ├─ h2 "Cameras" + pageCount + Badge (gateway)
   │  └─ Button ghost "Atualizar" · Button primary "+ Nova Camera"
   ├─ [loading] Skeleton (title, rect 140×32; lista 5× text 70%/45%; painel rect 200px + 2 text)
   ├─ [0 câmeras] emptyState (ícone + título + texto + Button primary "+ Adicionar camera")
   └─ splitView
      ├─ cameraList → cameraListItem × N (dot status + nome + local)
      └─ detailPanel (câmera selecionada)
         ├─ previewWrap → CameraPlayer | placeholder "Stream inativo"
         ├─ detailFields (Nome, Local, RTSP URL, Fabricante, Porta, Status)
         ├─ CameraModelAssignment (selects EPI / Qualidade / Contagem)
         ├─ CameraFpsConfig (chips FPS, chips qualidade, faixa de carga, Button "Salvar configuração")
         ├─ Dica RTSP (toggle + rtspTip)
         ├─ detailActions (Iniciar/Parar Stream, Testar Conexao, Operações, Editar, Excluir)
         └─ Logs (após Testar Conexao)
   ├─ CameraOnboardingWizard (modal "Adicionar Câmera" — ui/Modal Radix Portal, 4 etapas)
   ├─ CameraWizard (modal "Editar Câmera" — overlay/modal próprios, 4 passos)
   └─ ConfirmDialog "Confirmar exclusão" (ui/Modal, footer ghost+danger)
```

## Copy exata

**Header/lista/detalhe (CamerasPage.tsx):**
- Título: `Cameras` · contagem: `{n} camera{s}` · badge: `Gateway: {online|offline}`
- Botões: `Atualizar` · `Nova Camera`
- Sem seleção: `Selecione uma camera para ver detalhes`
- Empty: `Nenhuma camera cadastrada` / `Adicione uma camera para comecar o monitoramento` / `Adicionar camera`
- Placeholder preview: `Stream inativo — clique em "Iniciar Stream"`
- Labels de campo: `NOME` · `LOCAL` · `RTSP URL` · `FABRICANTE` · `PORTA` · `STATUS` (valores crus: `hikvision`, `inactive`, `rtsp://admin:****@10.20.30.102:554/...`)
- Ações: `Iniciar Stream` · `Parar Stream` · `Testar Conexao` / `Testando...` · `Operações` · `Editar` · `Excluir`
- Dica: `Dica: URLs RTSP por fabricante` → box: `Hikvision: rtsp://user:pass@IP:554/Streaming/Channels/101` / `Dahua/Intelbras: rtsp://user:pass@IP:554/cam/realmonitor?channel=1` / `Generico ONVIF: rtsp://IP:554/stream1`
- Logs: `Logs` · `Testando conexao...` · `Conexao estabelecida` · `Erro ao testar conexao`
- Erros amigáveis: `Camera nao esta transmitindo. Verifique se esta ligada.` · `Nao foi possivel conectar. Verifique IP e porta.` · `Camera nao respondeu a tempo. Verifique a rede.` · `Credenciais incorretas.` · `Endereco IP invalido ou nao encontrado.`
- Toasts: `Stream iniciado` · `Stream parado` · `Camera "{nome}" removida` · `Erro ao carregar cameras` · `Erro ao iniciar stream` · `Erro ao parar stream` · `Erro ao remover`

**CameraModelAssignment:** `Modelos de IA por módulo` · labels `EPI` / `QUALIDADE` / `CONTAGEM` (+ ` — salvando...`) · opção `Modelo padrão` · `Carregando modelos...` · toasts `Modelo atribuído à câmera` / `Atribuição de modelo removida` / `Erro ao atribuir modelo` · formato de opção: `{name} (mAP50 {pct}%)`

**CameraFpsConfig:** `Desempenho por câmera` · `FPS de inferência` · chips `1 fps · 5 fps · 10 fps · 15 fps · 30 fps` · `Qualidade do stream` · `Baixa · Média · Alta` · `{n}% de carga estimada no worker com {k} câmera(s) a {f} fps.` · `Carga alta — considere reduzir o FPS ou o numero de cameras ativas.` (≥80%) · `Carga moderada — fique de olho na performance do worker.` (50–79%) · `Salvar configuração` / `Salvando...` / `Salvo!` · `Sem alterações`

**CameraOnboardingWizard ("Adicionar Câmera", etapas `Fabricante · Acesso · Verificação · Confirmar`):**
- Etapa 1: `Selecione o fabricante da câmera` · cards: `Intelbras — Câmeras IP Intelbras (VIP, Mibo)` / `Hikvision — Câmeras Hikvision DS-2CD / DS-2DE` / `Dahua — Câmeras Dahua IPC / SD` / `Genérico / ONVIF — Qualquer câmera compatível com RTSP` · `Cancelar` · `Próximo →`
- Etapa 2: `Informe o endereço e credenciais da câmera` · `Nome da câmera *` (ph `Ex: Portão principal`) · `IP ou hostname *` (ph `192.168.1.100 ou camera.local`) · `Porta` (ph `554`) · `Canal` (ph `1`) · `Usuário` (ph `admin`) · `Senha` (ph `••••••••`) · checkbox `Câmera sem IP público / atrás de NAT` · `← Voltar` · `Verificar conexão →` / `Verificando...`
- Etapa 3 (probe ok): `✓ Câmera encontrada!` · `Codec: H264` · `Resolução: 1280x720` · `FPS: 15` · (falha) `✗ Não foi possível conectar` · (NAT) `Câmera atrás de NAT` / `✓ Gateway ativo detectado para este tenant.` / `Você pode salvar a câmera agora e a conexão será estabelecida via gateway.` · `← Corrigir dados` · `Confirmar →`
- Etapa 4: `Revise os dados antes de salvar` · linhas `Nome / Fabricante / Host / Canal / Usuário / Codec detectado / Resolução` · `← Voltar` · `Salvar câmera` / `Salvando...`

**CameraWizard ("Editar Câmera", passos `Fabricante · Conexão · Identificação · Teste`):**
- Header: `Editar Câmera` / `Nova Câmera` + `Passo {n} de 4 — {label}` + `×`
- Passo 1: hint `Selecione o fabricante para configuração automática do caminho RTSP.` · marcas `Hikvision · Dahua · Intelbras · Axis · Samsung · Outra marca`
- Passo 2: `Endereço IP *` · `Porta` · `Usuário` · `Senha` (ph edição `(deixe vazio para manter)`) · `Caminho do stream (opcional)`
- Passo 3: `Nome da câmera *` (ph `Ex: Entrada Principal, Baia 1...`) · `Localização (opcional)` (ph `Ex: Bloco A, Térreo...`)
- Passo 4: `Testar Conexão` · `✓ Conexão estabelecida!` / `✗ Falha na conexão` · checks: `Formato da URL RTSP · Câmera acessível na rede · Porta RTSP aberta · Resposta ao protocolo RTSP · Stream de vídeo disponível` · `← Corrigir dados` · `Testar novamente`
- Footer: `Cancelar` / `← Voltar` · `Próximo →` · `Concluir`
- Validações: `Selecione o fabricante` · `Informe o IP da câmera` · `IP inválido (ex: 192.168.1.100)` · `Porta inválida (1–65535)` · `Dê um nome para a câmera`

**ConfirmDialog:** `Confirmar exclusão` · `A câmera "{nome}" será permanentemente removida. Esta ação não pode ser desfeita.` · `Cancelar` · `Excluir` / `Aguarde...`

## Dados de exemplo (fixtures do spec E2E)

| Nome | Local | Fabricante | Host:porta | Status | FPS | Qualidade |
|---|---|---|---|---|---|---|
| Câmera Pátio Norte | Pátio Norte — Galpão A | intelbras | 10.20.30.101:554 | active | 10 | medium |
| Câmera Doca de Carga 2 (selecionada) | Doca 2 — Expedição | hikvision | 10.20.30.102:554 | inactive | 5 | high |
| Câmera Linha de Produção | Linha 1 — Envase | dahua | 10.20.30.103:554 | error (timeout) | 15 | low |
| Câmera Portaria Principal | Portaria — Entrada de Veículos | intelbras | 10.20.30.104:554 | active | 5 | medium |
| Câmera Almoxarifado | Almoxarifado Central | generic | 10.20.30.105:8554 | inactive (is_active=false) | 1 | low |
| Câmera Estacionamento Sul | Estacionamento — Bloco S | hikvision | 10.20.30.106:554 | offline | 5 | medium |

- Gateway: `{status: 'online'}` (rico) / `offline` (empty/error).
- Modelos treinados: `EPI RVB Industrial v3 (mAP50 87%)` · `Qualidade Solda v1 (79%)` · `Contagem Pallets v2 (91%)`; atribuição da cam-2: `epi: mdl-epi-v3`, demais `Modelo padrão`.
- Faixa de carga exibida: `50% de carga estimada no worker com 5 câmeras a 5 fps.` + `Carga moderada — fique de olho na performance do worker.`
- Probe (wizard etapa 3): codec `h264`, `1280x720`, 15 fps. Teste: 5 checks ok.
- Erro (estado error): `Falha ao conectar ao banco de dados` (HTTP 500, toast duplicado).

## Estados

- **default**: lista com 6 câmeras + `detailEmpty` à direita.
- **detail**: cam-2 selecionada (borda esquerda ciano + bgHover). Preview 16:9 **não aparece** (colapso, ver Problemas). Campos, selects de modelo, painel FPS, dica, ações.
- **detail-logs**: idem + `Logs` com `HH:MM:SS ✓ Conexao estabelecida` (scroll desce; NOME/LOCAL saem do viewport).
- **empty**: card centralizado com CTA `Adicionar camera` — bom convite à ação.
- **loading**: skeletons (título, botão, 5 itens de lista, retângulo 200px + 2 linhas). No tema claro os skeletons são quase invisíveis.
- **error**: empty state + 2 toasts idênticos de erro no topo-direito **sem fundo opaco**, texto colide com o header.
- **hover**: item da lista ganha `bgHover`; botão Nova Camera ganha borda/anel de foco. Chips FPS/qualidade e botões do onboarding **não têm** hover.
- **wizard-step1..4 / modal-delete**: modal via Radix Portal **sem painel visível** (transparente) nos dois temas — conteúdo da página vaza por trás.
- **modal-edit**: modal opaco correto (`bgCard` + overlay 0.65) nos dois temas; hint azul ilegível no claro.

## Navegação e fluxos

- `Nova Camera` / `Adicionar camera` (empty) → abre `CameraOnboardingWizard` (4 etapas; probe em Verificação; salvar em Confirmar → recarrega lista).
- Clique em item da lista → seleciona câmera, limpa logs.
- `Iniciar Stream`/`Parar Stream` → `POST /cameras/:id/stream/start|stop` + toast + reload.
- `Testar Conexao` → `POST /cameras/:id/test` → adiciona entradas em Logs (máx 8 exibidas).
- `Operações` → navega `/epi/cameras/{id}/operations`.
- `Editar` → abre `CameraWizard` no passo 1 com dados preenchidos.
- `Excluir` → `ConfirmDialog` → `DELETE /cameras/:id` → toast + deseleciona.
- `Atualizar` → refetch `GET /cameras`.

## Problemas identificados (resumo — detalhes no findings JSON)

1. **P0 transparency (task-066)** — `ui/Modal` (Radix Portal) e `ToastProvider` montam FORA do div temático do `AppShell` (`AppShell.tsx:33`); todos os tokens do contrato vanilla-extract ficam indefinidos → painel do modal, overlay, inputs e toasts renderizam transparentes. Afeta "Adicionar Câmera" (4 etapas), "Confirmar exclusão" e toasts de erro, nos dois temas.
2. **P1 layout** — `previewWrap` sem `flexShrink: 0` colapsa a 0px: preview/"Stream inativo" nunca aparece no detalhe.
3. **P0 hardcode (task-063)** — `CameraFpsConfig` inteiro em `rgba(255,255,255,*)`/`#c4b5fd`/roxo hardcoded: ilegível no tema claro (ratios 1.05–1.46).
4. **P0 hardcode** — `CameraModelAssignment` select `color: '#f1f5f9'` → branco sobre branco no claro (1.10:1).
5. **P1 contraste** — botão "Dica: URLs RTSP por fabricante" `rgba(139,92,246,0.7)`: falha nos DOIS temas (2.80 dark / 2.51 light) e roxo fora da identidade ciano/laranja.
6. **P1 contraste** — hint do CameraWizard `#93c5fd` sobre azul claro: 1.37:1 no claro.
7. **P2 inconsistency** — dois wizards distintos para criar vs editar (listas de fabricantes, labels de etapas e implementações de modal diferentes).
8. **P2 copy** — copy sem acentos ("Cameras", "camera", "Testar Conexao", "comecar", "nao"...) convivendo com copy acentuada; valores crus de backend expostos (`inactive`, `hikvision`, `Gateway: online`).
9. **P2 contraste** — skeletons quase invisíveis no tema claro (bgElevated≈branco sobre bgBase claro).
10. **P2 a11y** — chips FPS/qualidade sem `aria-pressed`/radiogroup; seleção comunicada apenas por cor.
11. **P3 hover** — chips e botões inline-styled sem estado hover; toast de erro duplicado no estado error.

**Deferred (não capturado):** detail com stream ativo (CameraPlayer/HLS); CameraWizard edição passos 2–4; dica RTSP expandida; hovers no tema claro; estados de foco de teclado.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | ~~P0~~ | both | **RESOLVED (task-066)** | ~~`ui/Modal` via Radix Portal sem tema → ConfirmDialog e overlays transparentes~~ — `dark-modal-delete` e `light-modal-delete` mostram modal opaco com overlay e blur corretos. |
| 2 | ~~P0~~ | dark | **RESOLVED (task-063)** | ~~`CameraFpsConfig` inteiro em `rgba(255,255,255,*)` hardcoded — ilegível no claro~~ — `dark-detail` mostra painel "Desempenho por câmera" com tokens corretos; chips FPS/qualidade estilizados. |
| 3 | P0 | light | **PERSISTS** | `CameraModelAssignment` selects com `color:'#f1f5f9'` → texto branco sobre branco no claro: selects EPI/QUALIDADE/CONTAGEM aparecem vazios em `light-detail` (placeholder sem cor visível). |
| 4 | P0 | dark | **PERSISTS (parcial)** | `CameraOnboardingWizard` (wizard "Adicionar Câmera") ainda renderiza sem fundo opaco no dark (`dark-wizard-step1`): conteúdo visível mas background é semitransparente. No light o wizard aparece corretamente opaco (`light-wizard-step1`). |
| 5 | P1 | both | **PERSISTS** | `previewWrap` colapsa a 0px sem `flexShrink: 0` — preview/"Stream inativo" não aparece no detalhe (não capturado nos screenshots de detalhe). |
| 6 | P1 | both | **PERSISTS** | Botão "Dica: URLs RTSP" em `rgba(139,92,246,0.7)`: contraste 2.80 dark / 2.51 light — fora do primary ciano/laranja da marca. |
| 7 | P1 | light | **PERSISTS** | Hint do CameraWizard `#93c5fd` sobre fundo azul claro: ratio ≈1.37:1. |
| 8 | P2 | both | **PERSISTS** | Copy sem acentos ("Cameras", "Testar Conexao", "camera") e valores crus de backend expostos (`inactive`, `hikvision`, `Gateway: ONLINE`). |
| 9 | P2 | both | **PERSISTS** | Dois wizards distintos (criar vs editar) com fabricantes, etapas e implementações de modal diferentes. |
| 10 | P2 | light | **PERSISTS** | Skeletons quase invisíveis no tema claro (bgElevated≈branco sobre bgBase claro). |
| 11 | P2 | both | **PERSISTS** | Chips FPS/qualidade sem `aria-pressed`/radiogroup — seleção comunicada apenas por cor. |
| 12 | P2 | — | **NEW** | Seção "Saúde do edge" adicionada ao `CameraFpsConfig` (`dark-detail`) — sem spec de copy/layout anterior; label e barra de alerta precisam de validação no light. |
| 13 | P3 | both | **PERSISTS** | Chips e botões inline-styled sem `:hover`; toast de erro duplicado no estado error. |
