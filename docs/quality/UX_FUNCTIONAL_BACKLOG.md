# Backlog de UX & Funcional — organizado por fluxos (mutirão de melhoria)

**Data:** 2026-07-01 · Base pra mutirão multi-agente. Referências de experiência (NÃO copiar, só
inspirar): ContaAzul, sistemas de borda populares — clareza pro leigo, visual limpo/profissional.
Regra transversal: **Contrato de Operabilidade + zero endpoint fora + zero regressão** (ver
FRONTEND_OPERABILITY_STANDARD.md e VMS_MONITORING_UX.md).

## BLOQUEADOR 0 — Login/acesso no ambiente DEV (fazer PRIMEIRO)
Sem login funcionando no dev, nada disso é validável. Diagnosticar o erro real (logs Railway),
corrigir (seed de dev env-gated + env/CORS/VITE_API_URL), até logar. (Prompt de login já entregue.)

## WS1 — Design System / Identidade Visual (FUNDACIONAL, transversal — fazer cedo)
- **Containers/modais/drawers estão brancos com título cinza — fora da identidade visual.** Padronizar
  TODOS (site inteiro) com o design system e as cores da marca. Ocorre em: investigação, treinamento,
  peças, retrabalhos, relatórios, integrações, tenants, e qualquer modal/drawer.
- Tornar as cores (inclusive dos containers) **configuráveis no White-Label** — o tenant ajusta tudo.
- Estabelecer tokens + componentes React reutilizáveis (Container/Drawer/Modal com tema) pra não
  repetir o problema.

### task-078 — auditoria ponta a ponta de containers/overlays transparentes (2026-07-14)

**ACHADO PRINCIPAL — bug sistêmico de Portal + escopo de tema (provável causa raiz do sintoma
original do Vitor):** `AppShell.tsx` aplica a classe de tema Vanilla Extract (que define os CSS vars
usados por `vars.color.*`) numa `<div>` interna — nunca em `<html>`/`<body>` (só um `data-theme`
attribute, que não carrega os CSS vars). `ui/Modal`, `ui/AppDrawer` e `ui/Popover` usam
`Dialog.Portal`/`Popover.Portal` do Radix, que por padrão renderizam em `document.body` — **fora**
da árvore DOM da div com a classe de tema. Resultado: **todo** conteúdo desses componentes perde os
tokens `vars.color.*` (ficam `unset` → `background: rgba(0,0,0,0)`, transparente) — confirmado via
`getComputedStyle` num teste Playwright real (`Modal_content` com `background: rgba(0, 0, 0, 0)`,
apesar do resto da página, fora do portal, renderizar o tema corretamente). Ou seja: **os modais que
a spec da task-078 apontou como "OK, já usam ui/Modal"** (`OperationCreateModal`, `OperationEditModal`,
`DeleteConfirmModal`, `InvestigationPage`, `AdminPlansPage`) **também sofrem este bug na prática** —
o padrão de referência "fonte da verdade" que a spec mandou reusar está com um defeito estrutural.
**Não corrigido nesta task** (blast radius grande — afeta todo Modal/AppDrawer/Popover da plataforma,
exige teste de regressão em todas as telas que os usam; fix provável: mover a classe de tema pra
`document.documentElement`/`<body>` em `AppShell.tsx`, ou passar `container` explícito pro
`Dialog.Portal`/`Popover.Portal` apontando pra dentro da div temada). **Recomendação: abrir task
dedicada de alta prioridade** antes de qualquer nova migração de modal pro `ui/Modal`.

Re-auditoria de código sobre o inventário da task-078 (a maior parte já havia sido corrigida por
trabalho anterior, não pela própria task-078):
- **task-063 (painel "Desempenho por câmera")** — CONFIRMADO **já resolvido** (`ff819d0`/`0d1a5db`,
  anteriores à task-078). Ficha `task-063-*.md` atualizada de PENDING → DONE. Não usa Portal (painel
  inline), não afetado pelo achado principal acima.
- **task-066 (modal "Nova Operação")** — código confirma `OperationCreateModal`/`OperationEditModal`/
  `DeleteConfirmModal` usam `ui/Modal` (fecha o "container sem fundo opaco" que a task-066 descrevia),
  mas **agora sabemos que `ui/Modal` tem o bug de Portal acima** — validar visualmente antes de dar
  como 100% encerrado. Ficha `task-066-*.md` atualizada de DEFERRED → DONE com essa ressalva.
- **Painéis internos `rgba(255,255,255,0.03–0.05)`** listados na spec (TrainingPage, AnnotationPage,
  ModelScenarioWizard) — **não existem mais** no código atual (refatorados/tokenizados em onda
  anterior, provavelmente `refactor(frontend): migra ~70 telas para tokens do design system`).
- **`components/AnnotationInterface.jsx`** — o único hit remanescente do padrão (linha do input
  "Nova Classe") **não foi tocado**: o arquivo é marcado `AI_NOTE: CONGELADO — nunca modificar` em
  3 lugares (`AnnotationPage.tsx`, `TrainingPage.tsx`, `AnnotationInterfaceWrapper.tsx`), com
  `.jsx.backup` preservado por essa política. Conflita com a spec da task-078; **decisão: respeitar o
  freeze**, não fixar. Se o painel "Nova Classe" precisar do fix, requer decisão explícita do Vitor pra
  destravar o freeze (fora do escopo desta task).
- **`pages/epi/EpiInvestigation.tsx`** — não existe mais; renomeado/consolidado em
  `pages/epi/InvestigationPage.tsx`, que já usa `ui/Modal` (sujeito ao achado principal acima).
- **`pages/AlertsHistoryPage.tsx`** — CONFIRMADO com o bug real (`background: '#1a1d23'` cru +
  bounding-box `#ef4444` cru). **Corrigido SEM migrar pro `ui/Modal`** (de propósito — ver comentário
  no arquivo): trocado hex cru por tokens (`vars.color.bgElevated`/`borderDefault`/`danger`/
  `textOnPrimary`) mantendo a estrutura de card local (fora de Portal), pra não introduzir a
  transparência do achado principal. Evidência: `docs/quality/evidence/task-078/`.
- **`AdminPlansPage`** — já migrado pro `ui/Modal` (não está mais na lista `TODO-WS1`); a spec estava
  desatualizada ao listá-lo como pendente. Sujeito ao achado principal acima.
- **Demais modais `TODO-WS1`** (11 arquivos: `AdminTenantsPage`, `AdminUsersPage`, `AdminVersionsPage`,
  `AdminChangelogPage`, `AdminAnnouncementsPage`, `AdminRolesPage`, `DemoVideosPage`,
  `QualityConfigPage`, `QualityReworkPage`, `QualityInspectionsPage`, `ModelScenarioWizard`) —
  auditados: overlay já usa `vars.color.overlay`, conteúdo já usa `s.card`/`bgSurface` (token, **mas
  não portalado** — são `<div style={{position:'fixed'}}>` locais, não Radix Dialog, então **não**
  sofrem o achado principal). Sem bug de transparência/hex-cru. O `TODO-WS1` marca só débito
  arquitetural (reimplementam o modal em vez de reusar `ui/Modal` — sem focus-trap/ESC/portal do
  Radix) — e, ironicamente, é exatamente esse "débito" que hoje os protege do bug de Portal. **Não
  migrar pro `ui/Modal` até o achado principal ser corrigido**, ou a migração troca um problema visual
  por outro. Guard-rail da task-065 já isenta essas linhas (marcador `TODO-WS1` = baseline congelada).

## WS2 — Onboarding cognitivo (tooltips + tradução + nomes) — transversal
- **Ícone de informação (i) com tooltip no hover** explicando cada campo/aba: módulo, modelo base,
  epochs, confiança, detecção, latência, cenários, integrações, etc. (não fica sempre visível, só no hover).
- **Traduzir chaves do backend → nomes humanos** em TODA a UI (nada de nome técnico do backend na tela).
  Casos citados: aprovação de treinamento (itens sem nome), teste de modelo, filtros de investigação.
- **Nomenclatura padrão** (por módulo × funcionalidade) consistente em todo o sistema.

## WS3 — Dashboard como BI de verdade
- Manter os cards, mas adicionar **visualizações de BI** (gráficos) num container React (movimentável).
  Backend pode ser Python/stack atual. O dashboard tem que ter "cara de dashboard", não só cards com números.

## WS4 — Investigação
- Containers na identidade visual (WS1). Melhorar UX dos **filtros** (está básico) — campos: módulo,
  data/hora, confiança, com tooltips (WS2).
- Corrigir os **erros de "buscar evento"** (provável falta de dados) → suportar **dados mocados de
  demonstração** (tabela apartada) + **botão no admin pra incluir/remover dados mock** (demo pra novos clientes).

## WS5 — Fluxo de Treino / Teste de Modelo
- Aba de treino ao vivo: tooltips/traduções (WS2). **Bug: "selecionar classes" leva pro dashboard do
  admin e lá não há alteração de classe** — corrigir pra editar classes no lugar certo.
- **Teste de modelo:** tradução do que é cada coisa; explicar os cards (detecção, latência...);
  **seletor de FPS por câmera** (hoje só tem nº de câmeras/modelo); config de cenários (poder incluir
  novos cenários); descrição das integrações configuradas.
- **Modelo:** identificar **onde foi criado** e **quem é o dono** do modelo.

## WS6 — Admin: Tenants (super-admin configura tudo)
- Hoje mostra status/usuários/módulos mas **não dá pra CONFIGURAR cada tenant** — o super-admin deve
  poder editar todas as configurações do tenant (módulos, funcionalidades, **armazenamento por tenant**
  — ex.: R2 próprio).
- **Ver-como (impersonation):** visualizar como cada usuário enxerga a plataforma.
- Restringir o painel admin a super-admin/admin (ex.: **analistas NÃO acessam o admin**).
- Ver, por tenant, os usuários e as funcionalidades de cada um.

## WS7 — Admin: Roles & Permissões
- Roles/permissões com **DESCRIÇÃO do que cada uma libera** (pra saber o que se está concedendo).
- **Permissão granular por usuário** (liberar UMA atividade, não a role inteira) — "usuário customizado".
- Nomenclatura padrão por módulo/funcionalidade. **Investigar e expor MAIS pontos de permissionamento**
  que existam na plataforma e ainda não estão na matriz.

## WS8 — Admin: Planos
- Editar planos: **nº de usuários**, **módulos liberados + funcionalidades por módulo** (pra limitar),
  **valores de cobrança**. Containers na identidade visual (WS1).

## WS9 — Arquitetura de Informação / Unificação
- **Mover "Site/Saúde" (monitoramento de dispositivos/Edge) do módulo EPI PARA o Admin** — é função de
  administrador. O módulo **EPI deve mostrar só: VMS das câmeras, alertas (data/hora + imagens do
  momento da infração), e treino ao vivo** — não o monitoramento de dispositivos.
- **Unificar fluxos** em um só lugar via containers + cross-linking: ex.: criar usuário → permissões →
  tenant → acesso, tudo numa jornada, sem trocar de aba. Estressar outros fluxos que sofrem disso.
- **Botão "Configurações" do painel não leva a lugar nenhum** — definir o que deve ter ali ou remover.
- **Deep-link de notificação:** "configurar chave Vast" deve abrir um drawer pra configurar ali mesmo
  OU levar direto à página certa — não fazer o usuário andar 3 passos.

## WS10 — Operação: FPS por câmera (não só no teste)
- Selecionar **FPS por câmera na OPERAÇÃO** (escolher a câmera e ajustar o FPS direto no front, sem
  parar a operação, sem script) — com os avisos health-aware (VMS_MONITORING_UX.md).

## WS11 — Saúde da Plataforma & Observability (gestão à distância)
Objetivo: transformar a "Saúde da Plataforma" num **observability real** pra o gestor monitorar tudo
de longe (plataforma + Edge) e evitar ir presencialmente ao cliente.
- **Consolidar a observability espalhada** num só lugar (dentro do Admin): além do que já olha
  (Celery, database, R2), trazer **workers + FILAS do Celery** (profundidade, latência, falhas/retries),
  **conexões do DB** (liga com a 053/PgBouncer), Redis, **saúde dos devices Edge por site**
  (heartbeat/GPU/térmica/decode — casa com WS9, que move Site/Saúde pro admin), API/WebSocket,
  status das migrations, taxa de erro. Varrer os pontos de observability dispersos nos serviços e reunir.
- **Dashboard de verdade (BI):** séries temporais/gráficos + resumo de alto nível "OK/degradado"
  entendível pela GESTÃO, com drill-down. Não só cards — refletir a saúde real ao longo do tempo,
  com limiares/alertas.
- **Seletor de intervalo de atualização + janela de observação:** hoje é fixo em 30s (sem cliente
  rodando, não precisa). Deixar configurável (ex.: off / 10s / 30s / 1m / 5m) + janela histórica pra
  olhar tendência. Pausar/retomar.
- **Gestão à distância:** visão de FROTA (múltiplos tenants/sites) num painel só, pra o super-admin
  acompanhar plataforma + Edge de longe. Referências: dashboards estilo Grafana/Datadog, métricas
  RED/USE — inspirar, não copiar. Containers na identidade visual (WS1); tooltips explicando cada
  métrica (WS2).

## Princípios de execução (para todos os WS)
Cada melhoria = visual (identidade) + experiência (jornada clara pro leigo) + otimização + **unificação**
(resolver em um lugar, com containers e ligação entre abas). Tudo operável pela UI, sem script, sem
endpoint fora, sem regressão. Referências de mercado pra inspirar a experiência, sem copiar.
