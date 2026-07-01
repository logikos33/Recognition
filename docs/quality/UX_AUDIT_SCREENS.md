# UX_AUDIT_SCREENS.md

**Auditoria UX tela por tela — Recognition (EPI Monitor V2)**
Data: 2026-07-01
Escopo: todas as páginas em `apps/frontend/src/pages/` e `apps/frontend/src/modules/`
Critério base: "um operador de fábrica sem treinamento técnico consegue operar sozinho?"

---

## 1. Tabela de Avaliação

| Tela | Rota | Avaliação Leigo (1–5) | Gaps Críticos | Prioridade |
|------|------|-----------------------|---------------|------------|
| MonitoringPage | `/epi/monitoring` → redirect `/epi/dashboard` | 2 | Rota ativa é redirect; a CameraGrid bruta não tem filtro por módulo, expand de câmera, nem logs ao vivo; sem VMS real | P0 |
| EpiDashboard | `/epi/dashboard` | 3 | KPIs carregam mas sem tooltips explicativos; CameraGrid sem legenda de status; link "Ver todos" em alertas quebrado se não há alertas | P1 |
| CamerasPage | `/epi/cameras` | 3 | Onboarding wizard só abre via botão "Nova Câmera" — zero guia no empty state além de um botão; RTSP tip escondido atrás de toggle; status de stream como texto puro ("inactive") sem semáforo visível na lista; operações avançadas enterradas 2 níveis abaixo | P1 |
| AlertsHistoryPage | `/epi/alerts` | 2 | Filtro de câmera é campo de texto livre (precisa saber o UUID ou nome exato); bounding boxes no modal de evidência são hardcoded (posição fixa 20%/15%) independente do alerta real; "hover 1 segundo para reconhecer" é affordance invisível sem nenhum hint visual; sem botão "Hoje" no filtro de data | P0 |
| TrainingPage | `/epi/training` | 1 | Terminologia técnica exposta sem glossário: "epochs", "batch size", "mAP@50", "LGKV26n", "LGKV26s"; fluxo upload→extração→anotação→treino não é linearizado em steps; o limite de 20 frames validados aparece só no momento de bloquear o botão, sem roadmap antecipado; "frames validados" vs "frames anotados" não é explicado | P0 |
| AnnotationPage (AnnotationInterface) | via TrainingPage | 2 | Componente congelado sem feedback de atalhos de teclado; sem indicador de quantas classes existem; sem undo visual na UI (flag `@ts-ignore` congela manutenção) | P1 |
| EpiOperationsPage | `/epi/cameras/:id/operations` | 2 | Título mostra UUID da câmera ("Operações — Câmera abc123...") ao invés do nome; acessível apenas via botão "Operações" na CamerasPage — sem entrada na sidebar; TrainingModeLayout sem documentação de abas para o usuário | P1 |
| EpiScenarioEditorPage | `/epi/cameras/:id/scenario` | 2 | ScenarioEditor não aparece na navegação principal — acessível só via EpiOperationsPage; sem preview do stream ativo por padrão (hlsUrl depende de token na query string); ferramentas de desenho (zona/linha/ponto) sem label descritivo de quando usar cada uma | P1 |
| DrawingCanvas | componente dentro de ScenarioEditor | 2 | Não surfaçado independentemente; instrução de uso (clique para adicionar ponto, duplo-clique para fechar) não aparece na UI | P1 |
| VerificationQueuePage | `/epi/verification` | 3 | Sem imagem/frame inline no card (apenas confiança + texto); refresh manual necessário (polling 15s não visível); sem acesso pela sidebar principal | P2 |
| InvestigationPage | `/epi/investigation` | 3 | Boa estrutura de filtros; thumbnails de evidência carregam mas sem lightbox; paginação funciona; sem help text sobre o que "investigação" significa nesse contexto | P2 |
| EpiSitesHealthPage | `/epi/sites-health` | 2 | Requer role admin — operadores comuns recebem 403 sem mensagem clara; label "Sites & Saúde" na sidebar aparece para todos mesmo sendo admin-only; heartbeat chart sem legenda de unidade (ms? s?) | P1 |
| ReportsPage | `/epi/reports` | 3 | Export PDF funciona; sem filtro por período visível na tela inicial; sem preview antes de gerar | P2 |
| ModuleSelectionPage | `/modules` | 4 | Boa tela de entrada; cards claros; "Em breve" bem sinalizado; único gap: sem indicação de quantas câmeras/alertas estão ativos antes de entrar no módulo | P3 |
| HomePage | `/home` (redirect `/epi/dashboard`) | N/A | Rota legacy — redirect funciona; componente `HomePage` existe mas não está na navegação real (sidebar aponta para `/epi/dashboard` = EpiDashboard) | P3 |
| StreamHealthPage | `/epi/health` | 2 | Sem entrada na sidebar; acessível apenas por URL direto; dados técnicos (bitrate, FPS) sem contexto do que é saudável | P2 |
| CountingPage | `/epi/counting` | 2 | Sem entrada na sidebar; funcionalidade de contagem não explicada; sem câmeras vinculadas visíveis | P2 |
| Quality module | `/quality/*` | 3 | Layout próprio com sidebar; QualityDashboard e abas bem estruturadas; TabletKiosk acessível por rota pública sem auth — sem aviso de que é acesso interno | P2 |
| Admin module | `/admin/*` | 3 | AdminLayout com sidebar própria; funcionalidades muito técnicas (feature flags, branding, audit log) sem agrupamento lógico óbvio para novos admins | P3 |
| FuelingPage / FuelingPlaceholder | `/fueling/*` | 1 | Placeholder vazio — sem conteúdo funcional; card "Em breve" na seleção de módulo não impede navegação, usuário chega numa tela em branco | P1 |

---

## 2. Telas que Travam ou Confundem Operadores

### P0 — Bloqueantes (impedem uso efetivo)

**TrainingPage — fluxo sem linearidade**
- Leigo abre "Treinamento" e vê três abas sem contexto de ordem: "Dados", "Treinar", "Modelos".
- Não fica claro que é necessário: (1) enviar vídeo → (2) extrair frames → (3) anotar → (4) validar → (5) treinar.
- O botão "Iniciar Treinamento" fica desabilitado sem roadmap prévio; a mensagem de bloqueio só aparece quando já clicou.
- Termos técnicos ("epoch", "mAP@50", "LGKV26n") sem tooltip ou glossário.

**AlertsHistoryPage — interações invisíveis**
- Hover-to-acknowledge (1s hover = auto reconhece) é completamente invisível: sem cursor change, sem progress ring, sem tooltip.
- Os bounding boxes no modal de evidência estão hardcoded no ponto 20%/15%/25%/50% — sempre no mesmo lugar, independente de qual câmera ou detecção, enganando o operador sobre onde estava a infração real.
- Filtro de câmera é campo de texto livre — operador não sabe o nome exato ou UUID.

**MonitoringPage — ausência de VMS**
- A tela `/epi/monitoring` redireciona para EpiDashboard.
- A CameraGrid não tem: filtro por módulo, expand individual de câmera, logs ao vivo de detecção, indicador de câmera offline destacado.
- Não serve como painel VMS operacional.

### P1 — Críticos (confundem severamente)

**CamerasPage — RTSP e status ocultos**
- RTSP URLs por fabricante estão escondidas atrás de um toggle de texto pequeno.
- Status de stream na lista usa texto "inactive" / "active" sem semáforo colorido na coluna.
- O botão "Operações" existe no painel direito mas nunca é mencionado no empty state ou onboarding.

**EpiOperationsPage — título com UUID**
- Breadcrumb mostra "Câmera abc123-def456..." ao invés do nome da câmera.
- Sem rota na sidebar: usuário não consegue voltar a esta tela diretamente.

**EpiScenarioEditorPage — inacessível pela navegação**
- Rota `/epi/cameras/:id/scenario` só chega via EpiOperationsPage → link interno.
- Sem atalho direto; sem link na sidebar; sem menção no onboarding de câmeras.
- Ferramentas de desenho não têm label de uso (quando usar zona vs linha vs ponto).

**EpiSitesHealthPage — role confusion**
- Item "Sites & Saúde" aparece na sidebar para todos os usuários logados.
- Ao clicar, operadores sem role admin recebem 403 sem mensagem amigável — a página renderiza vazia ou com erro silencioso.

**FuelingPage — placeholder navegável**
- O módulo Fueling está acessível na seleção de módulos e na sidebar.
- Usuário entra e encontra tela em branco (FuelingPlaceholder).
- Não há bloqueio antecipado nem mensagem clara de "ainda não disponível para sua conta".

---

## 3. Endpoints Não Surfaçados na Navegação

As rotas abaixo existem no AppRoutes mas não têm entrada na sidebar principal:

| Rota | Componente | Como acessar hoje |
|------|------------|-------------------|
| `/epi/cameras/:id/operations` | EpiOperationsPage | Botão "Operações" no painel de detalhe de câmera |
| `/epi/cameras/:id/scenario` | EpiScenarioEditorPage | Link dentro de EpiOperationsPage |
| `/epi/health` | StreamHealthPage | URL direta — sem link na UI |
| `/epi/counting` | CountingPage | URL direta — sem link na UI |
| `/epi/verification` | VerificationQueuePage | URL direta — sem link na sidebar |
| `/epi/training/classes` | ModuleClassesPage | URL direta — sem link visível |

---

## 4. Proposta de Grupos de Navegação

### Sidebar EPI (reorganizada)

**Grupo: Monitoramento**
- Dashboard (`/epi/dashboard`) — KPIs + câmeras + alertas recentes
- Monitoramento ao vivo (`/epi/monitoring`) — CameraGrid fullscreen com filtros e expand
- Investigação (`/epi/investigation`) — busca de eventos com timeline

**Grupo: Alertas**
- Histórico de Alertas (`/epi/alerts`) — tabela com filtros + export
- Fila de Verificação (`/epi/verification`) — revisão humana de ambíguos [badge contador]

**Grupo: Câmeras**
- Câmeras (`/epi/cameras`) — lista + wizard + stream control
- _(Operações e Cenário ficam como subnav dentro da câmera, não na sidebar global)_
- Sites & Saúde (`/epi/sites-health`) — apenas se role >= admin

**Grupo: Treinamento** (visível apenas se tenant tem módulo treinamento)
- Dados & Anotação (`/epi/training` → aba Dados)
- Treinar Modelo (`/epi/training` → aba Treinar)
- Modelos (`/epi/training` → aba Modelos)

**Grupo: Relatórios**
- Relatórios (`/epi/reports`)
- Stream Health (`/epi/health`) — admin-only

---

## 5. Melhorias de Alta Prioridade

### P0-1: Linearizar fluxo de treinamento
Substituir a interface de abas por um wizard passo-a-passo com stepper visual:
`Enviar → Extrair → Anotar (N/20) → Validar → Treinar`
Cada passo desabilitado até o anterior estar completo. Termos técnicos aparecem apenas no modo Avançado.

### P0-2: Corrigir bounding boxes no modal de evidência
`AlertsHistoryPage` — bounding boxes hardcoded em `left: '20%', top: '15%'`. Substituir pelas coordenadas reais das `violations[].bbox` (já presentes no payload da API), normalizando para percentual.

### P0-3: Remover hover-to-acknowledge silencioso
`AlertsHistoryPage` — o `startHoverAck` / `setTimeout 1000ms` dispara ação sem affordance. Remover o comportamento ou adicionar cursor progress + ring animado com cancel on mouseleave explícito. Caso de uso mais seguro: apenas o botão "Reconhecer" realiza a ação.

### P0-4: Adicionar VMS à MonitoringPage
`MonitoringPage` precisa de: filtro de módulo, status de câmera offline destacado em vermelho, botão de expand individual (full-screen por câmera), painel lateral de eventos/detecções ao vivo via WebSocket.

### P1-5: Surfaçar ScenarioEditor e VerificationQueue na sidebar
`VerificationQueuePage` deve ter entrada na sidebar com badge contador de itens pendentes.
`EpiScenarioEditorPage` deve ser acessível via botão "Configurar Cenário" direto no detalhe da câmera, com label explicativo.

### P1-6: Corrigir título UUID em EpiOperationsPage
Substituir `Câmera ${cameraId}` por nome real da câmera via hook ou estado passado pela navegação.

### P1-7: Ocultar Sites & Saúde para não-admins
Na sidebar, `{ to: '/epi/sites-health', ... }` deve ser condicionado a `isSuperAdmin || hasRole('admin')` antes de renderizar o item.

### P1-8: Bloquear FuelingPage antecipadamente
Na ModuleSelectionPage, o card "Fueling" deve ser não-clicável (como os módulos "Em breve") em vez de navegar para uma tela vazia.

---

## 6. Resumo por Prioridade

| Prioridade | Quantidade de itens | Exemplos principais |
|------------|--------------------|--------------------|
| P0 — Bloqueante | 3 telas | TrainingPage, AlertsHistoryPage, MonitoringPage |
| P1 — Crítico | 7 telas | CamerasPage, EpiOperationsPage, ScenarioEditor, FuelingPage, SitesHealth, VerificationQueue, DrawingCanvas |
| P2 — Relevante | 5 telas | InvestigationPage, ReportsPage, StreamHealth, CountingPage, Quality |
| P3 — Baixo | 3 telas | ModuleSelectionPage, HomePage (redirect), Admin |
