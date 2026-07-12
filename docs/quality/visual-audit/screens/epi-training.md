# Treinamento (EPI) — spec visual

**Rota:** `/epi/training` (redirects: `/annotation`, `/training`)
**Fontes:** `apps/frontend/src/pages/TrainingPage.tsx`, `apps/frontend/src/pages/TrainingPage.css.ts`, `apps/frontend/src/components/AnnotationInterface.jsx` (congelado), `apps/frontend/src/components/ui/{Badge,Button,Skeleton,Toast}`, `apps/frontend/src/hooks/useTrainingSocket.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (aba Imagens) | ../screenshots/epi-training/dark-default.png | ../screenshots/epi-training/light-default.png |
| tab-modelo | ../screenshots/epi-training/dark-tab-modelo.png | ../screenshots/epi-training/light-tab-modelo.png |
| tab-treino (job RUNNING) | ../screenshots/epi-training/dark-tab-treino.png | ../screenshots/epi-training/light-tab-treino.png |
| tab-treino-sem-gpu | ../screenshots/epi-training/dark-tab-treino-sem-gpu.png | ../screenshots/epi-training/light-tab-treino-sem-gpu.png |
| modal-novo-treino (form config) | ../screenshots/epi-training/dark-modal-novo-treino.png | ../screenshots/epi-training/light-modal-novo-treino.png |
| empty | ../screenshots/epi-training/dark-empty.png | ../screenshots/epi-training/light-empty.png |
| loading | ../screenshots/epi-training/dark-loading.png | ../screenshots/epi-training/light-loading.png |
| error (500 em tudo) | ../screenshots/epi-training/dark-error.png | ../screenshots/epi-training/light-error.png |
| annotation-fullscreen | ../screenshots/epi-training/dark-annotation-fullscreen.png | ../screenshots/epi-training/light-annotation-fullscreen.png |
| hover filtro "Anotadas" | ../screenshots/epi-training/hover-filtro-anotadas.png | — |
| hover botão "Ativar" (modelo) | ../screenshots/epi-training/hover-btn-ativar-modelo.png | — |

## Layout — regiões

- **Header do app** (shell): breadcrumb `EPI / Treinamento`, sino, toggle Pro (tema), "Auditor Visual", badge `SUPERADMIN`, botão `Sair`. Footer de status: `Banco de dados · Redis · câmeras ativas`.
- **Página** (`s.page`): `padding: vars.space.xl` (32px). Header da página (`s.pageHeader`): flex space-between, `marginBottom: vars.space.lg` (24px), com `h2` "Treinamento" (`s.pageTitle`: 22px/700, `vars.color.textPrimary`).
- **Tabs Radix** (`Tabs.Root defaultValue="imagens"`): `s.tabsList` flex, gap 2px, `borderBottom: 1px solid vars.color.borderDefault`, `marginBottom: 24px`. Triggers (`s.tabsTrigger`): padding `8px 16px`, 13px/600, cor `textMuted`; ativo = `textPrimary` + `borderBottom 2px vars.color.primary`; hover = `textSecondary`.
- **Aba Imagens**: upload zone (full-width, altura 1 linha) → barra de filtros (flex, gap 8) → grid da galeria `repeat(auto-fill, minmax(120px,1fr))`, gap 8 → paginação centralizada.
- **Aba Modelo**: card "Modelo Ativo" (full-width) → seção "Classes de Detecção" (grid `minmax(160px,1fr)`, gap 8) → seção "Modelos Treinados" (`s.gridModels`: grid gap 10px, cards full-width).
- **Aba Treino ao Vivo**: banner GPU (condicional) → card "Job Atual" (com form de config embutido condicional) → bloco "Log de Eventos" (console 180px de altura, overflow-y auto) → tabela "Histórico de Treinos" (full-width, `borderCollapse: collapse`, 13px).
- **Annotation fullscreen**: `AnnotationInterface` SUBSTITUI a página inteira (sem tabs/heading) ao clicar numa miniatura da galeria; toolbar própria (Voltar / Desenhar / Selecionar / Apagar / Classe), canvas central, rodapé com navegação de frames (`← 1/10`, `Boxes: 0`) e filmstrip "10 frames".

## Árvore de componentes

- `TrainingPage`
  - `h2` Treinamento
  - `Tabs.Root`
    - `Tabs.List` → 3 `Tabs.Trigger`: "Imagens (N)" / "Modelo" / "Treino ao Vivo"
    - `Tabs.Content[imagens]`
      - Upload zone (div inline-styled: borda `1.5px dashed rgba(255,255,255,0.15)`, bg `rgba(255,255,255,0.03)`, radius 10; drag-over → borda `primaryLight`, bg `rgba(96,165,250,0.08)`) + `input[type=file]` oculto (jpeg/png/webp, multiple)
      - Filtros: label "Filtro:" + 3 botões pill (Todas/Anotadas/Sem anotação; ativo = bg `primaryDark` + texto `textOnPrimary`; inativo = transparent + borda `rgba(255,255,255,0.1)` + texto `textSecondary`) + contador "N imagem(s)" à direita
      - Galeria: cards de imagem (radius 6, borda verde `rgba(34,197,94,0.4)` se anotada, senão `rgba(255,255,255,0.08)`; img 80px cover; badge circular verde `rgba(34,197,94,0.9)` c/ `CheckCircle` 10px; legenda `#<frame_number>` 9px `textMuted`)
      - Paginação: `Button size=sm variant=secondary` "← Anterior" / "Próxima →" + "Página X de Y"
      - Loading da galeria: 12 `Skeleton rect` 80px em grid
    - `Tabs.Content[modelo]`
      - Card "Modelo Ativo" (bg `rgba(255,255,255,0.04)`, borda `rgba(34,197,94,0.3)` se houver ativo, senão `rgba(255,255,255,0.08)`, radius 10): `h3` "Modelo Ativo" (**#f1f5f9 hardcoded**), nome do modelo (15px/600 `primaryLight`), 3 `MetricPill` (mAP@50 `#22d3ee` / Precision `primaryLight` / Recall `#34d399`), "Criado em <data>" (11px `textMuted`); botão `Button secondary sm` "⚙ Configurar Classes" (→ `window.location.href='/module-classes'`)
      - `h3.sectionTitle` "Classes de Detecção" + chips (bg `rgba(255,255,255,0.04)`, borda `rgba(255,255,255,0.08)`, dot 10px na cor da classe, **texto usa `vars.color.borderDefault` como cor**)
      - `h3.sectionTitle` "Modelos Treinados" + `s.modelCard` por modelo (bg `bgCard`, borda `borderDefault`; ativo = `s.modelCardActive` borda 2px `success`): nome (`s.modelName` textPrimary/600), `Badge success` "✓ ativo", botão `Button secondary sm` "Ativar" (hover do design system OK), MetricPills, data
      - Loading: 3 `Skeleton rect` 64px
    - `Tabs.Content[treino]`
      - Banner GPU (se `gpu_enabled=false`): bg `rgba(245,158,11,0.1)`, borda `rgba(245,158,11,0.3)`, ícone `AlertTriangle #f59e0b`, texto **`#fbbf24` hardcoded**, link "Administração → Integrações ↗" (`primaryLight`) → `/admin/integrations`
      - Card "Job Atual" (bg `rgba(255,255,255,0.04)`, borda `rgba(255,255,255,0.08)`, radius 10): `h3` "Job Atual" (**#f1f5f9 hardcoded**); ações: `Button primary sm` "⚡ Novo Treino" (quando parado) OU `Button secondary sm` "▢ Parar" (texto `#ef4444`, quando rodando); botão-ícone refresh (sem borda, `textMuted`)
        - Form de config (toggle "Novo Treino"; NÃO é modal — painel inline bg `rgba(255,255,255,0.03)`, borda `rgba(255,255,255,0.07)`): `configGrid` com selects/inputs tokenizados (`s.configSelect`/`s.configInput`: bg `bgSurface`, borda `borderDefault`, focus `primary`) — campos Módulo / Modelo Base / Epochs / Batch Size / Learning Rate; botões "▶ Iniciar Treinamento" (primary) e "Cancelar" (secondary)
        - Estado do job: `Badge` de status + "LGKV26s · balanced" + data; progress bar (`s.progressTrack` bg `borderDefault` / `s.progressFill` bg `primary`) + label "Epoch 32/50 (64%)"; sparklines `MiniChart` (Loss/`primaryLight`, mAP@50/`#22d3ee`, bg do svg `rgba(255,255,255,0.03)`); MetricPills quando completed; caixa de erro `rgba(239,68,68,0.08)` texto `#f87171` quando failed
      - "LOG DE EVENTOS" (label 12px uppercase `textMuted`) + botão "limpar" (link-button `textMuted` 11px): console `height:180px`, **bg `#0a0f1a` hardcoded**, borda `rgba(255,255,255,0.07)`, mono 11px; placeholder "Aguardando eventos de treinamento..." em **`vars.color.borderStrong` como cor de texto**; linhas `[HH:MM:SS] stage=… epoch=… loss=… mAP50=…` (`textSecondary`; prefixo `[WS` → `primaryLight`); auto-scroll `logsEndRef.scrollIntoView({behavior:'smooth'})`
      - `h3.sectionTitle` "Histórico de Treinos" + tabela: thead 11px uppercase `textMuted`, borda inferior `rgba(255,255,255,0.07)`; linhas com borda `rgba(255,255,255,0.04)`; célula Modelo em **`vars.color.borderDefault` como cor de texto**, mAP@50 `#22d3ee`, Precision `primaryLight`, Recall `#34d399` (mono), Status = `Badge`
  - `AnnotationInterface` (fullscreen, congelado): toolbar "← Voltar", título "Anotação — Vídeo vid-pati", botões Desenhar (azul `#2563eb` fora da paleta)/Selecionar/Apagar, dropdown "Classe: ● Capacete ▾", overlay central "Modo Desenhar — Clique e arraste para desenhar caixas", nav "← 1/10 · Boxes: 0 · Boxes: 0 →", filmstrip "10 frames", timestamp "2:00". **Sempre dark — ignora o tema claro.**

## Copy exata

- Título: `Treinamento` · Tabs: `Imagens (138)` / `Modelo` / `Treino ao Vivo`
- Upload: `Arraste imagens (JPG/PNG/WebP) ou clique — até 50 por vez` · durante upload: `Enviando imagens...`
- Toasts upload: `Selecione imagens JPG, PNG ou WebP` / `Máximo de 50 imagens por upload` / `N imagens enviadas` / `Erro ao enviar imagens`
- Filtros: `Filtro:` `Todas` `Anotadas` `Sem anotação` · contador `138 imagens` / `0 imagens` / `1 imagem`
- Empty galeria: `Nenhuma imagem de treino. Faça upload de imagens ou envie vídeos para extração de frames.` · filtro anotadas: `Nenhuma imagem anotada ainda.` · filtro sem anotação: `Todas as imagens já foram anotadas.`
- Paginação: `← Anterior` · `Página 1 de 6` · `Próxima →`
- Aba Modelo: `Modelo Ativo` · `Nenhum modelo ativo. Ative um modelo abaixo.` · `⚙ Configurar Classes` · `Classes de Detecção` · `Modelos Treinados` · `Nenhum modelo treinado ainda. Inicie um treino na aba "Treino ao Vivo".` · badge `ativo` · botão `Ativar` (`...` enquanto ativa) · `Criado em 02/07/2026, 11:35` · toasts `Modelo ativado` / `Erro ao ativar modelo`
- MetricPill labels: `MAP@50` `PRECISION` `RECALL`
- Banner GPU: `Chave de GPU não configurada — treinos rodarão em simulação.` + link `Administração → Integrações`
- Job Atual: `Job Atual` · `⚡ Novo Treino` · `▢ Parar` / `Parando...` · tooltip `Atualizar` · `Nenhum job em andamento. Clique em "Novo Treino" para iniciar.`
- Form config labels: `MÓDULO` `MODELO BASE` `EPOCHS` `BATCH SIZE` `LEARNING RATE` · opções modelo: `LGKV26n (nano)` / `LGKV26s (small)` / `LGKV26m (medium)` · `▶ Iniciar Treinamento` / `Iniciando...` · `Cancelar` · toasts `Treinamento iniciado` / `Erro ao criar job` / `Job interrompido` / `Erro ao parar job`
- Progress: `Epoch 32/50 (64%)` · ETA: `M:SS restantes`
- Log: `LOG DE EVENTOS` · `limpar` · `Aguardando eventos de treinamento...` · linha ex.: `[23:32:09] stage=training epoch=32 loss=0.0412 mAP50=0.8125`
- Histórico: `Histórico de Treinos` · colunas `MODELO / PRESET / STATUS / EPOCHS / MAP@50 / PRECISION / RECALL / DATA` · `Nenhum job de treinamento ainda.` · valores vazios `—`
- Nomes de modelo re-brandeados: `yolo26n→LGKV26n`, `yolo26s→LGKV26s`, `yolo26m→LGKV26m` (fn `displayModelName`)
- Annotation: `← Voltar` · `Anotação — Vídeo vid-pati` · `Desenhar` `Selecionar` `Apagar` · `Classe:` · `Modo Desenhar` / `Clique e arraste para desenhar caixas` · `Boxes: 0` · `10 frames`

## Dados de exemplo (fixtures)

- **Imagens**: 138 no total, 24/página (6 páginas); frames `#120…#630` (step 30), `filename frame_000120.jpg…`, `video_name "Câmera Pátio Norte — turno manhã"`, `video_id vid-pati…`; anotadas alternadas (badge verde).
- **Classes** (`/api/classes`): Capacete `#10b981`, Sem capacete `#ef4444`, Colete `#06b6d4`, Sem colete `#f59e0b`, Luvas `#8b5cf6`, Sem luvas `#f97316`, Óculos `#22d3ee`, Sem óculos `#e11d48`.
- **Modelos**: `LGKV26s-epi-rvb-v4` (ativo; 91.3/89.7/87.4, 02/07/2026 11:35), `LGKV26n-epi-rvb-v3` (88.1/86.2/84.5, 24/06 06:12), `LGKV26n-epi-rvb-v2` (84.2/83.0/79.0, 10/06 13:40), `LGKV26n-epi-piloto-v1` (78.6, 28/05).
- **Job atual (RUNNING)**: `jb-207` LGKV26s · balanced, epoch 32/50, progress 64%, criado 06/07/2026 22:51; live: loss 0.0412, mAP50 0.8125.
- **Histórico (6 jobs)**: running 32/50 · completed 50/50 (91.3/89.7/87.4) · failed 21/50 (accurate) · stopped 15/50 (fast) · completed 80/80 (88.1/86.2/84.5) · completed 50/50 (84.2/83.0/79.0).
- **Sem-GPU**: `gpu_enabled:false`, job COMPLETED LGKV26s · balanced 02/07/2026 10:08.

## Estados

- **default**: aba Imagens, galeria populada, filtro "Todas" ativo.
- **loading**: skeletons (título + grid 12 rects na galeria; 3 rects na aba Modelo).
- **empty**: contador "0 imagens" + frase de empty; upload zone permanece como CTA.
- **error**: **visualmente idêntico ao empty** (catch vazio engole o fetch) + toast "Erro interno do servidor" sobreposto ao header — falso estado saudável.
- **tab-treino**: página abre ROLADA até o fim do log (`scrollIntoView` no mount corta o card "Job Atual" do viewport).
- **modal-novo-treino**: painel inline expande dentro do card Job Atual (não há backdrop/modal).
- **hover**: tabs e `Button` (design system) têm hover; botões de filtro, upload zone inline e refresh NÃO mudam nada (hover-filtro-anotadas idêntico ao default).
- **annotation-fullscreen**: substitui a página; permanece dark nos dois temas.

## Navegação e fluxos

- Miniatura da galeria (click) → `AnnotationInterface` fullscreen (`annotatingVideoId`); "← Voltar" retorna.
- Upload zone (click/drag) → `POST /v1/videos/images/upload` → recarrega página 1.
- "Configurar Classes" → `window.location.href = '/module-classes'` — **rota inexistente** (a página de classes vive em `/epi/training/classes`); cai no catch-all `*` → `RootRedirect`. Navegação quebrada + full page reload.
- "Novo Treino" → expande form inline; "Iniciar Treinamento" → `POST /training/jobs`; "Parar" → `POST /training/jobs/<id>/stop`.
- "Ativar" (modelo) → `POST /training/models/<id>/activate`.
- Link banner GPU → `/admin/integrations`.
- Polling: `GET /training/jobs/current/status` a cada 3s; WS `useTrainingSocket` alimenta sparklines/logs.

## Problemas identificados (resumo)

1. **P0 (light)**: headings "Modelo Ativo"/"Job Atual" com `color:'#f1f5f9'` hardcoded — invisíveis no tema claro (1.00:1). task-063.
2. **P0 (both)**: chips de "Classes de Detecção" e coluna "Modelo" do histórico usam `vars.color.borderDefault` como cor de TEXTO — ilegível nos dois temas (1.20–1.31:1).
3. **P1 (light)**: dezenas de superfícies/bordas `rgba(255,255,255,0.03–0.15)` (upload zone, filtros, cards, form, thead/linhas da tabela) desaparecem no claro. task-063.
4. **P1 (light)**: console de log com bg `#0a0f1a` hardcoded + texto em tokens do tema claro (2.01:1); banner GPU `#fbbf24` (1.42:1) e link (1.54:1); métricas `#22d3ee`/`#34d399` (1.66/1.76:1).
5. **P1 (dark)**: placeholder do log usa `borderStrong` como texto (1.55:1).
6. **P1 (both)**: `scrollIntoView` no mount rola a página; erro de fetch = estado vazio (falso-saudável) + toast sobrepondo o header.
7. **P2**: hover ausente em filtros/upload/refresh; "modal" de treino é painel inline fora do padrão ADR-0023; AnnotationInterface ignora o tema claro e usa azul `#2563eb` fora da paleta.
8. **P1 (both)**: botão "Configurar Classes" navega para `/module-classes`, rota que NÃO existe (catch-all → RootRedirect). O destino correto é `/epi/training/classes`.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P0 | light | **PERSISTS** | Headings "Modelo Ativo"/"Job Atual" com `color:'#f1f5f9'` hardcoded — quase invisíveis no claro: `light-tab-modelo` mostra o heading do card "Modelo Ativo" apagado sobre fundo claro (~1.00:1). |
| 2 | ~~P0~~ | both | **RESOLVED** | ~~Chips "Classes de Detecção" e coluna "Modelo" do histórico usam `borderDefault` como cor de texto (1.20–1.31:1)~~ — em `light-tab-modelo` os chips exibem nomes de classe legíveis ("Capacete", "Colete", etc.) com cor própria. Em `dark-tab-modelo` os chips também aparecem legíveis com dots coloridos e texto. |
| 3 | ~~P1~~ | light | **RESOLVED (task-063)** | ~~Dezenas de superfícies `rgba(255,255,255,0.03–0.15)` desaparecem no claro~~ — `light-default` (aba Imagens) mostra galeria, upload zone e filtros visíveis com bordas e fundos distinguíveis. |
| 4 | P1 | both | **PERSISTS** | Console de log com `bg: '#0a0f1a'` hardcoded permanece dark no light (`light-tab-treino-sem-gpu`): contraste do texto ≈2.01:1 sobre o fundo escuro no contexto claro; não harmoniza com o tema. |
| 5 | P1 | light | **PERSISTS (parcial)** | Banner GPU: texto `#fbbf24` sobre fundo âmbar — em `light-tab-treino-sem-gpu` o banner é visível, mas ratio estimado 1.42:1 sobre o background claro. |
| 6 | P1 | both | **PERSISTS** | `scrollIntoView` no mount rola a aba "Treino ao Vivo" para o log, cortando o card "Job Atual" do viewport (`dark-tab-treino` começa no meio da página). |
| 7 | P1 | both | **PERSISTS** | Botão "Configurar Classes" navega para `/module-classes` → rota inexistente (catch-all RootRedirect). Destino correto: `/epi/training/classes`. |
| 8 | P2 | both | **PERSISTS** | Hover ausente em filtros/upload zone/refresh; painel inline de "Novo Treino" fora do padrão modal (ADR-0023); AnnotationInterface ignora tema claro e usa `#2563eb`. |
| 9 | P2 | — | **NEW** | Botão "Configurar Cenário" adicionado ao card de modelo (`dark-tab-modelo`, `light-tab-modelo`) substituindo ou acompanhando "Ativar" — não estava no spec anterior; comportamento/rota não documentados. |
| 10 | P2 | — | **NEW** | Coluna "COBERTURA" na tabela histórico (era "RECALL" no spec anterior) — renomeação confirmada em `dark-tab-treino` e `light-tab-treino`. Atualizar copy do spec. |
