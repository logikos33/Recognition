# Proposta de Arquitetura de Informação — Painel Admin

**Data:** 2026-07-01
**Autor:** Agente chore/audit-admin-ia
**Base:** AppRoutes.tsx + modules/admin/ (inventário completo) + VMS_MONITORING_UX.md §5

---

## 1. Contexto e Motivação

O painel admin atual (`/admin/*`) cresceu organicamente. Cada feature nova ganhou uma entrada no
sidebar sem revisão de agrupamento. O resultado são 6 grupos misturando preocupações distintas
(ex.: "Aprovações de Treinamento" sob "Operações" ao lado de "Tickets"; "Branding" isolado do restante
da administração por tenant). Do lado do operador, telas como `EpiOperationsPage`, `CountingPage` e
`VerificationQueuePage` existem como rotas top-level sem âncora visual clara.

O VMS_MONITORING_UX.md §5 aponta um gap crítico: a matriz de permissões existe como componente
(`PermissionMatrixTable.tsx`) mas **não há página dedicada** para criar/editar perfis de role — a
feature nunca chegou ao usuário final.

Esta proposta reorganiza as 29 telas existentes em 5 grupos coesos, identifica 5 telas ausentes
(gaps) e propõe o fluxo de cada uma.

---

## 2. Inventário de Telas Existentes

### 2.1 Painel Admin (`/admin/*`) — 20 telas

| # | Componente | Rota atual | Nav group atual |
|---|---|---|---|
| A1 | AdminDashboard | `/admin` | Visão Geral |
| A2 | AdminTenantsPage | `/admin/tenants` | Tenants & Usuários |
| A3 | AdminTenantDetailPage | `/admin/tenants/:id` | (drill-down de A2) |
| A4 | AdminUsersPage | `/admin/users` | Tenants & Usuários |
| A5 | AdminTrainingApprovalsPage | `/admin/training-approvals` | Operações |
| A6 | AdminWorkersPage | `/admin/workers` | Operações |
| A7 | AdminPlansPage | `/admin/plans` | Tenants & Usuários |
| A8 | AdminFeatureFlagsPage | `/admin/feature-flags` | Plataforma |
| A9 | AdminTicketsPage | `/admin/tickets` | Operações |
| A10 | AdminAuditLogPage | `/admin/audit-log` | Plataforma |
| A11 | AdminAnnouncementsPage | `/admin/announcements` | Plataforma |
| A12 | AdminHealthPage | `/admin/health` | Plataforma |
| A13 | AdminSettingsPage | `/admin/settings` | Plataforma |
| A14 | AdminVersionsPage | `/admin/versions` | Versionamento |
| A15 | AdminChangelogPage | `/admin/changelog` | Versionamento |
| A16 | AdminBrandingTenantsPage | `/admin/branding/tenants` | Identidade Visual |
| A17 | AdminBrandingEditorPage | `/admin/branding/tenants/:id` | (drill-down de A16) |
| A18 | AdminBrandingDefaultPage | `/admin/branding/default` | Identidade Visual |
| A19 | AdminBrandingSandboxPage | `/admin/branding/sandbox` | Identidade Visual |
| A20 | DemoVideosPage | `/admin/demo-videos` | Identidade Visual |

### 2.2 Telas do Operador (`/epi/*`) — 9 telas

| # | Componente | Rota atual |
|---|---|---|
| B1 | EpiDashboard | `/epi/dashboard` |
| B2 | EpiCameras | `/epi/cameras` |
| B3 | EpiAlerts | `/epi/alerts` |
| B4 | TrainingPage | `/epi/training` |
| B5 | ModuleClassesPage | `/epi/training/classes` |
| B6 | EpiOperationsPage | `/epi/cameras/:id/operations` |
| B7 | ReportsPage | `/epi/reports` |
| B8 | VerificationQueuePage | `/epi/verification` |
| B9 | CountingPage | `/epi/counting` |
| B10 | StreamHealthPage | `/epi/health` |

---

## 3. Grupos Propostos

### Grupo 1 — Operacao

**Conceito:** Tudo que o operador faz durante o turno. Foco em tempo real. Nunca sai desta seção
para monitorar, reagir a um alerta ou checar câmeras.

**Ancoragem VMS:** VMS_MONITORING_UX.md §1 define a tela de monitoramento como "a tela que não pode
morrer". Ela deve ser o ponto de entrada padrão do operador (rola para `/modules` → clica no módulo
→ aterrissa diretamente no VMS do módulo, não num dashboard estático).

| Tela proposta | Telas de origem | Rota sugerida |
|---|---|---|
| Monitoramento ao Vivo (VMS) | B1 EpiDashboard + B9 CountingPage | `/epi/monitoring` |
| Cameras | B2 EpiCameras | `/epi/cameras` |
| Detalhes da Camera (drawer) | B6 EpiOperationsPage | drawer sobre `/epi/cameras` |
| Alertas | B3 EpiAlerts | `/epi/alerts` |
| Fila de Verificacao | B8 VerificationQueuePage | `/epi/alerts/verification` |

**Justificativas e fluxos melhorados:**

- **B1 + B9 → Monitoramento ao Vivo:** `EpiDashboard` exibe KPIs estáticos (relatórios home) enquanto
  `CountingPage` exibe contagem em tempo real como se fossem telas separadas. Na prática o operador
  precisa de um grid VMS com overlay de detecção on/off (VMS §1) e contagem embutida em cada célula.
  Unificar elimina o salto entre telas durante o turno.

- **B6 → drawer sobre /epi/cameras:** `EpiOperationsPage` é hoje uma rota full-page
  (`/epi/cameras/:id/operations`). Seguindo o padrão de container (VMS §7), ela deve abrir como
  drawer lateral sobre a lista de câmeras: o operador clica na câmera, o drawer abre com config de
  FPS/qualidade e saúde do stream, fecha sem perder o contexto do grid. Eliminar a rota full-page
  reduz a pilha de navegação.

- **B8 → /epi/alerts/verification:** A fila de verificação humana é a continuação natural de um
  alerta de baixa confiança. Colocar em sub-rota de Alertas deixa a hierarquia clara: alertas →
  verificacao humana → aprovado/rejeitado.

---

### Grupo 2 — Modelos & Treino

**Conceito:** Ciclo de vida completo de um modelo — do dataset ao deploy. Perfil: engenheiro ML /
superadmin. O operador comum não acessa este grupo.

| Tela proposta | Telas de origem | Rota sugerida |
|---|---|---|
| Registry de Modelos | B5 ModuleClassesPage | `/admin/models` |
| Criar / Editar Modelo | (novo, ver gaps §4) | `/admin/models/new` |
| Anotacao e Dataset | B4 TrainingPage | `/admin/models/:id/dataset` |
| Aprovacoes de Treino | A5 AdminTrainingApprovalsPage | `/admin/models/approvals` |
| Treino ao Vivo | (novo, ver gaps §4) | `/admin/models/jobs/:jobId/live` |
| Benchmark | (novo, ver gaps §4) | `/admin/models/:id/benchmark` |

**Justificativas e fluxos melhorados:**

- **A5 → Modelos & Treino (saindo de "Operacoes"):** A aprovação de treinamento não é operação
  de negócio — é um gate do ciclo ML. Hoje vive ao lado de Tickets e Workers, que são preocupações
  completamente distintas. Mover para Modelos & Treino coloca a aprovação no contexto onde faz
  sentido: o aprovador vê o dataset, as classes, a métrica esperada e então aprova/rejeita.

- **B5 → Registry:** `ModuleClassesPage` lista as classes de um módulo YOLO, o que é essencialmente
  o registry de capacidades de um modelo. Renomear e elevar para primeiro nível do grupo deixa claro
  que esta é a entrada do ciclo de treino.

- **B4 → sub-rota do modelo:** `TrainingPage` existe hoje como `/epi/training` isolada. Deve ser
  `/admin/models/:id/dataset` — anotação e submissão de dataset são etapas internas do fluxo de
  um modelo específico.

---

### Grupo 3 — Relatorios

**Conceito:** Saídas documentais e investigativas. Diferente de Operação (tempo real) e Saúde
(infra), Relatórios é sobre evidências e compliance — exportáveis, auditáveis.

| Tela proposta | Telas de origem | Rota sugerida |
|---|---|---|
| Compliance EPI | B7 ReportsPage | `/epi/reports/compliance` |
| Busca Investigativa | (novo, ver gaps §4) | `/epi/reports/investigate` |

**Justificativas e fluxos melhorados:**

- **B7 → /epi/reports/compliance:** `ReportsPage` já existe e gera relatórios de EPI. A rota
  `/epi/reports` continua funcionando como redirect para a primeira sub-aba. Adicionar
  "Busca Investigativa" como segunda aba no mesmo layout aproveita a infraestrutura existente.

- **Busca Investigativa (gap):** Permite que o operador busque eventos históricos por câmera +
  janela de tempo + classe detectada e veja os frames/vídeos de evidência. Atende investigações
  de acidentes e auditorias externas sem precisar de acesso direto ao banco.

---

### Grupo 4 — Administracao

**Conceito:** Configuração estrutural da plataforma. Mudanças aqui têm impacto cross-tenant ou
alteram billing. Risco alto → confirmação explícita em ações destrutivas.

| Tela proposta | Telas de origem | Rota sugerida |
|---|---|---|
| Tenants | A2 AdminTenantsPage | `/admin/tenants` |
| Detalhe do Tenant (drawer) | A3 AdminTenantDetailPage | drawer sobre `/admin/tenants` |
| Usuarios | A4 AdminUsersPage | `/admin/users` |
| Permissoes / Roles | (novo, ver gaps §4) | `/admin/roles` |
| Planos | A7 AdminPlansPage | `/admin/plans` |
| Feature Flags | A8 AdminFeatureFlagsPage | `/admin/feature-flags` |
| Integracoes e Segredos | (novo, ver gaps §4) | `/admin/integrations` |
| White-label | A16-A20 Branding* | `/admin/branding` |
| Comunicados | A11 AdminAnnouncementsPage | `/admin/announcements` |
| Configuracoes | A13 AdminSettingsPage | `/admin/settings` |
| Versoes e Changelog | A14+A15 Versions+Changelog | `/admin/versions` |
| Suporte (Tickets) | A9 AdminTicketsPage | `/admin/tickets` |

**Justificativas e fluxos melhorados:**

- **A3 → drawer sobre /admin/tenants:** Igual ao padrão de EpiOperationsPage. Clicar num tenant
  abre drawer com abas: Dados gerais | Usuarios | Modulos ativos | Branding | Plano. Elimina
  a navegação full-page para detalhe, permite comparar tenants na lista sem perder contexto.

- **Branding consolidado em Administracao:** Os 4 componentes de branding (list, editor, default,
  sandbox) hoje formam um grupo isolado "Identidade Visual". São funcionalidades de config por
  tenant — pertencem logicamente em Administracao sob uma sub-rota `/admin/branding`. O sandbox
  vira aba dentro do editor, não uma rota separada.

- **DemoVideosPage → White-label:** Vídeos de demo são conteúdo de onboarding por tenant,
  conceitualmente ligado ao white-label. Colocar como aba de Branding ou sub-rota
  `/admin/branding/demo-videos` deixa a relação explícita.

- **Tickets em Administracao (saindo de "Operacoes"):** Tickets são suporte administrativo,
  não operação de câmeras/modelos. Mover para Administracao.

- **Permissoes/Roles (gap critico):** Ver §4.1.

- **Integracoes/Segredos (gap):** Ver §4.2.

---

### Grupo 5 — Saude

**Conceito:** Observabilidade da infra. Dados somente leitura para diagnóstico. Entram aqui
telas que o superadmin monitora para saber se o produto está rodando — não para configurar nada.

| Tela proposta | Telas de origem | Rota sugerida |
|---|---|---|
| Dashboard Admin | A1 AdminDashboard | `/admin` (index) |
| Workers | A6 AdminWorkersPage | `/admin/health/workers` |
| Saude da Plataforma | A12 AdminHealthPage | `/admin/health` |
| Saude dos Streams | B10 StreamHealthPage | `/admin/health/streams` |
| Audit Log | A10 AdminAuditLogPage | `/admin/health/audit` |

**Justificativas e fluxos melhorados:**

- **A1 → index permanece:** O Dashboard Admin é a homepage do painel e permanece como `/admin`
  (index). Ele agrega métricas dos outros grupos (workers online, aprovações pendentes, etc.) e
  funciona como ponto de entrada — sem mudança de rota.

- **A10 → Saude (saindo de "Plataforma"):** Audit log é observabilidade de segurança — quem fez
  o quê, quando, com qual IP. Conceitualmente pertence ao grupo de saúde/diagnóstico, não a um
  grupo de configuração. Mover para `/admin/health/audit` coloca audit log ao lado de workers e
  health checks, onde o superadmin já está quando investigando problemas.

- **B10 → Saude/streams:** `StreamHealthPage` existe como `/epi/health`, visível para o tenant.
  Uma visão cross-tenant (todos os streams de todos os tenants) deve existir em
  `/admin/health/streams`. A versão por-tenant permanece em `/epi/health`.

- **A6 Workers consolidado com Health:** Workers e Health hoje são entradas separadas no sidebar
  ("Operacoes" e "Plataforma"). Ambos são observabilidade de infra — unificar sob `/admin/health`
  com sub-abas reduz o sidebar em 2 entradas sem perder funcionalidade.

---

## 4. Gaps — Telas Ausentes (a criar)

### 4.1 Permissoes / Roles — PRIORIDADE P0

**Por que P0:** VMS_MONITORING_UX.md §5 lista explicitamente como requisito de produto: "Refazer:
criar/editar perfis (roles) e escolher quais funcionalidades cada um tem, com UX boa pro proprio
admin. Por tenant." O componente `PermissionMatrixTable.tsx` ja existe mas nenhuma rota o exibe.
A feature nunca chegou ao usuário.

**Fluxo proposto:**
1. `/admin/roles` → lista de roles da plataforma (superadmin) e por tenant (tenant-admin)
2. Clicar em um role → drawer abre `PermissionMatrixTable` editavel com toggle por funcionalidade
3. "Criar novo role" → wizard de 2 passos: nome/descricao → matrix de permissoes → salvar
4. Aplicar role a usuario → botao na `AdminUsersPage` com dropdown dos roles disponíveis

**Impacto:** Desbloqueia o tenant-admin de depender do superadmin para gerenciar permissoes
dentro do seu proprio tenant.

### 4.2 Integracoes e Segredos

**Por que existe:** Tenants precisam de webhooks de saída (para integrar alertas com Slack,
SIEM, ou sistema interno), API keys para acessar a API programaticamente e possivelmente
conexoes a sistemas externos (Active Directory, SSO). Hoje nao ha superficie para isso.

**Fluxo proposto:**
- `/admin/integrations` → lista de integracoes ativas por tenant (visao superadmin)
- Dentro do detalhe de um tenant (drawer) → aba "Integracoes": webhooks configurados,
  API keys ativas (masked), OAuth apps autorizadas
- Rotacao de segredos com confirmacao de 2 fatores e registro no audit log

### 4.3 Benchmark de Modelo

**Por que existe:** Antes de fazer deploy de um novo modelo treinado, o superadmin precisa
comparar métricas (mAP, precision, recall, FPS de inferencia) entre versoes. Hoje a aprovacao
(`AdminTrainingApprovalsPage`) nao exibe essas metricas — o aprovador aprova "no escuro".

**Fluxo proposto:**
- `/admin/models/:id/benchmark` → tabela comparativa entre versoes do modelo
- Acessível a partir do card de aprovacao (link direto "Ver metricas")
- Metricas: mAP@50, mAP@50-95, precision, recall, FPS no worker de producao

### 4.4 Treino ao Vivo (Job Monitor)

**Por que existe:** `AdminTrainingApprovalsPage` lista jobs aguardando aprovacao mas nao mostra
o progresso de jobs em execucao. O superadmin nao sabe se um job travou, quantas epochs foram
concluídas ou qual é a GPU utilization.

**Fluxo proposto:**
- `/admin/models/jobs/:jobId/live` → polling ou WebSocket com curva de loss/val-loss,
  epochs restantes, GPU/VRAM do worker, ETA
- Botao "Cancelar job" com confirmacao
- Redireciona para Benchmark quando job conclui

### 4.5 Busca Investigativa

**Por que existe:** Operadores precisam localizar frames/eventos historicos para investigar
acidentes, responder auditorias ou treinar novos modelos com exemplos reais. Hoje isso
requer acesso direto ao banco ou ao storage R2.

**Fluxo proposto:**
- `/epi/reports/investigate` → filtros: camera, janela de tempo, classe detectada,
  confidence threshold
- Resultado: galeria de frames com metadados (timestamp, camera, classes detectadas,
  confianca)
- Acoes: exportar CSV, marcar para dataset de treino, compartilhar link assinado

---

## 5. Mapa de Relocacao Completo

Tabela consolidada de todas as telas existentes com o grupo de destino proposto.

| ID | Componente | Rota atual | Grupo proposto | Rota proposta | Relocacao? |
|---|---|---|---|---|---|
| A1 | AdminDashboard | `/admin` | Saude | `/admin` | Nao (index permanece) |
| A2 | AdminTenantsPage | `/admin/tenants` | Administracao | `/admin/tenants` | Nao |
| A3 | AdminTenantDetailPage | `/admin/tenants/:id` | Administracao (drawer) | drawer sobre `/admin/tenants` | Sim — full-page → drawer |
| A4 | AdminUsersPage | `/admin/users` | Administracao | `/admin/users` | Nao |
| A5 | AdminTrainingApprovalsPage | `/admin/training-approvals` | Modelos & Treino | `/admin/models/approvals` | Sim — muda grupo e rota |
| A6 | AdminWorkersPage | `/admin/workers` | Saude | `/admin/health/workers` | Sim — muda grupo e rota |
| A7 | AdminPlansPage | `/admin/plans` | Administracao | `/admin/plans` | Nao |
| A8 | AdminFeatureFlagsPage | `/admin/feature-flags` | Administracao | `/admin/feature-flags` | Nao |
| A9 | AdminTicketsPage | `/admin/tickets` | Administracao | `/admin/tickets` | Sim — sai de Operacoes |
| A10 | AdminAuditLogPage | `/admin/audit-log` | Saude | `/admin/health/audit` | Sim — sai de Plataforma |
| A11 | AdminAnnouncementsPage | `/admin/announcements` | Administracao | `/admin/announcements` | Nao |
| A12 | AdminHealthPage | `/admin/health` | Saude | `/admin/health` | Nao |
| A13 | AdminSettingsPage | `/admin/settings` | Administracao | `/admin/settings` | Nao |
| A14 | AdminVersionsPage | `/admin/versions` | Administracao | `/admin/versions` | Sim — sai de Versionamento |
| A15 | AdminChangelogPage | `/admin/changelog` | Administracao | `/admin/versions` (aba) | Sim — vira aba de Versoes |
| A16 | AdminBrandingTenantsPage | `/admin/branding/tenants` | Administracao | `/admin/branding` | Sim — sai de grupo isolado |
| A17 | AdminBrandingEditorPage | `/admin/branding/tenants/:id` | Administracao (drawer) | drawer sobre `/admin/branding` | Sim — full-page → drawer |
| A18 | AdminBrandingDefaultPage | `/admin/branding/default` | Administracao | `/admin/branding` (aba) | Sim — vira aba |
| A19 | AdminBrandingSandboxPage | `/admin/branding/sandbox` | Administracao | editor (aba preview) | Sim — vira aba inline |
| A20 | DemoVideosPage | `/admin/demo-videos` | Administracao | `/admin/branding/demo-videos` | Sim — move para branding |
| B1 | EpiDashboard | `/epi/dashboard` | Operacao (VMS) | `/epi/monitoring` | Sim — renomeia + expande |
| B2 | EpiCameras | `/epi/cameras` | Operacao | `/epi/cameras` | Nao |
| B3 | EpiAlerts | `/epi/alerts` | Operacao | `/epi/alerts` | Nao |
| B4 | TrainingPage | `/epi/training` | Modelos & Treino | `/admin/models/:id/dataset` | Sim — sai do operador, entra em ML |
| B5 | ModuleClassesPage | `/epi/training/classes` | Modelos & Treino (Registry) | `/admin/models` | Sim — eleva para registry |
| B6 | EpiOperationsPage | `/epi/cameras/:id/operations` | Operacao (drawer) | drawer sobre `/epi/cameras` | Sim — full-page → drawer |
| B7 | ReportsPage | `/epi/reports` | Relatorios | `/epi/reports/compliance` | Sim — vira sub-rota |
| B8 | VerificationQueuePage | `/epi/verification` | Operacao | `/epi/alerts/verification` | Sim — ancora em Alertas |
| B9 | CountingPage | `/epi/counting` | Operacao (VMS) | integrar ao `/epi/monitoring` | Sim — unifica com VMS |
| B10 | StreamHealthPage | `/epi/health` | Saude | `/epi/health` (tenant) + `/admin/health/streams` (cross) | Sim — duplica visao |

---

## 6. Sidebar Proposto (AdminLayout)

```
[Saude]
  Dashboard                    /admin
  Saude da Plataforma          /admin/health
  Workers                      /admin/health/workers
  Streams (cross-tenant)       /admin/health/streams
  Audit Log                    /admin/health/audit

[Modelos & Treino]
  Registry de Modelos          /admin/models
  Aprovacoes              (🔴) /admin/models/approvals
  Jobs ao Vivo                 /admin/models/jobs

[Administracao]
  Tenants                      /admin/tenants
  Usuarios                     /admin/users
  Permissoes / Roles     (novo)/admin/roles
  Planos                       /admin/plans
  Feature Flags                /admin/feature-flags
  Integracoes & Segredos (novo)/admin/integrations
  White-label                  /admin/branding
  Comunicados                  /admin/announcements
  Configuracoes                /admin/settings
  Versoes & Changelog          /admin/versions
  Suporte (Tickets)       (🔴) /admin/tickets
```

Reducao de grupos: 6 → 3 no painel admin. Entradas no sidebar: 18 → 14 (colapsando
full-pages que viram drawers/abas e unificando Workers+Health).

---

## 7. Prioridades de Implementacao

### P0 — Critico (gap que bloqueia feature prometida)
1. **Permissoes/Roles:** `PermissionMatrixTable` existe, precisa de rota + CRUD de roles.
   Desbloqueia VMS §5 que esta documentado como requisito de produto.

### P1 — Alto (relocacoes que causam confusao operacional hoje)
2. **A5 Aprovacoes → Modelos & Treino:** Aprovadores sao engenheiros ML, nao operadores.
   Mover elimina ruido no grupo "Operacoes".
3. **B6 EpiOperationsPage → drawer:** Full-page break de contexto no VMS. Drawer resolve
   sem novo componente (reutiliza layout existente via portal/Sheet).
4. **B1 + B9 → VMS unificado:** EpiDashboard estático + CountingPage separada formam
   uma experiencia fragmentada para o operador durante o turno.
5. **B8 VerificationQueuePage → /epi/alerts/verification:** Hoje o operador nao tem caminho
   visual de "alerta → verificar". A sub-rota cria o caminho natural.

### P2 — Medio (melhorias de coesao que nao bloqueiam uso)
6. **A10 AuditLog → Saude:** Relocacao de nav group, zero mudanca de componente.
7. **A9 Tickets → Administracao:** Idem.
8. **A3 TenantDetail → drawer:** Melhora UX do superadmin ao gerenciar tenants.
9. **A15 Changelog → aba de Versoes:** Reduz uma entrada no sidebar.
10. **A19 BrandingSandbox → aba inline:** Reduz uma entrada no sidebar.

### P3 — Baixo (novos fluxos, requerem backend novo)
11. **Benchmark de Modelo:** Requer endpoint de metricas de treino no training-service.
12. **Treino ao Vivo:** Requer WebSocket ou polling de status de job no worker.
13. **Busca Investigativa:** Requer endpoint de busca full-text em frames + presigned URLs R2.
14. **Integracoes/Segredos:** Requer schema novo (webhook_configs, api_keys) + migration 014+.

---

## 8. Redirects Necessarios (compatibilidade)

Para nao quebrar bookmarks e links externos ja em circulacao:

```
/epi/training           → /admin/models/:defaultModuleId/dataset
/epi/training/classes   → /admin/models
/epi/counting           → /epi/monitoring
/epi/health             → /epi/health  (permanece, cross-tenant vai para /admin/health/streams)
/epi/verification       → /epi/alerts/verification
/admin/training-approvals → /admin/models/approvals
/admin/workers          → /admin/health/workers
/admin/audit-log        → /admin/health/audit
/admin/branding         → /admin/branding  (sem mudanca de URL base)
/admin/versions         → /admin/versions  (sem mudanca)
/admin/changelog        → /admin/versions  (redirect + abrir aba changelog)
```

---

*Este documento e a entrada de auditoria de IA/UX da Fase 1 do MUTIRAO. Implementar
na ordem de prioridade da secao 7. Cada item P1+ deve gerar sua propria task antes de
implementar.*
