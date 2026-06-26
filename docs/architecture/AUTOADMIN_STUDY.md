# Estudo de Auto-Administrabilidade — Recognition × Mercado (ServiceNow / Verkada / Rhombus)

**Data:** 2026-06-23 · **Objetivo:** mapear o que falta para que **tudo que envolve a plataforma
seja resolvido NA plataforma** (sem Claude Code / SQL manual) — o padrão de um SaaS multi-módulo
auto-administrável.

## Princípio-guia
Como num SaaS maduro (ServiceNow): **operação por UI, não por terminal.** Toda configuração, onboarding,
diagnóstico e correção de rotina deve ter um caminho no painel. Claude Code/SQL fica só para
desenvolvimento e incidentes excepcionais — nunca para operar o dia a dia de um cliente.

## Onde já estamos fortes (paridade real com o mercado)
O painel admin atual já cobre, via UI: **tenants** (CRUD, suspender/reativar, overview, histórico de
plano), **usuários** (CRUD, desativar, reset de senha, sessões), **matriz de permissões (RBAC)**,
**feature flags** (global + por tenant), **planos**, **tickets de suporte**, **audit log (+export)**,
**announcements**, **health/métricas da plataforma**, **branding/white-label**, **versões + rollback**,
e **monitor de workers**. Isso é uma base de plataforma — não um app simples.

## Os pilares do mercado mapeados pra nós

| Pilar (ServiceNow / VSaaS) | O que é | Nós hoje | Gap |
|---|---|---|---|
| **Inventário unificado (CMDB / device fleet)** | Sistema único de registro de todos os ativos (câmeras, devices edge, sites, modelos) com status/saúde | Câmeras existem no backend; **não há inventário unificado no painel** com câmera+device+site+modelo+saúde | **P0 — maior gap** |
| **Onboarding self-service / Service Catalog** | Adicionar/testar ativos pela UI, em lote | Onboarding por câmera (probe, task-046) existe no backend; **sem import em lote nem teste 1-a-1 no painel** | **P0** (pedido do usuário) |
| **Hierarquia site/sub-site + RBAC herdado** (Verkada) | Sites e subsites com permissões herdadas | Temos tenant + `edge_sites`; **sem subsite nem herança de permissão fina** | P1 |
| **No-code config de tudo** | Cenários, regras, alertas, retenção, modelo por câmera pela UI | Editor visual de cenário (024), retenção (047), modelo por câmera (045), branding — **maioria já existe**. Falta UI de regras de notificação (042) e tuning por câmera (039) | P1 (parcial) |
| **Motor de automação/workflow** (Flow Designer) | Escalonamento, jobs agendados, respostas automáticas por UI | Scheduled tasks/conceito existe; **sem construtor visual de automação** | P1 |
| **Hub de integração / API + webhooks** (Rhombus 50+) | Conectar ERP/BI/acesso, webhooks gerenciáveis | OpenAPI (013) + canais de notificação (042); **sem hub de webhooks/integrações no painel** | P1 |
| **Observabilidade/diagnóstico por ativo** | Ver/diagnosticar cada câmera/device na UI | Health da plataforma + fleet (016/026); **sem diagnóstico/teste por câmera** | P0 (junto do inventário) |
| **Relatórios self-service** (Performance Analytics) | Montar relatório/dashboard sem código | Relatórios de compliance (043) | P2 |
| **Assistente / base de conhecimento** (Virtual Agent) | Ajuda guiada no produto | Tickets de suporte existem | P2 |

## Roadmap priorizado (para chegar ao nível "tudo na plataforma")

**P0 — operacional, destrava os 2 clientes (RVB + Roccabela):**
- **Inventário de ativos no painel** (CMDB-equivalente): câmeras + edge devices + sites + modelos num
  só lugar, com status de conexão/codec/saúde. → **task-052**.
- **Onboarding em lote + teste 1-a-1** de câmera no painel (usa o `/probe` da 046; importa CSV/lote;
  testa cada uma sem perturbar o CFTV; mostra codec real → pega o H.265+ da Hikvision). → **task-052**.
- **Diagnóstico por câmera/device** (último heartbeat, FPS, latência, último frame, erros) na UI.

**P1 — maturidade de plataforma:**
- UI de **regras de notificação/escalonamento** (sobre 042) — quem é avisado, quando, por qual canal.
- **Hierarquia site/subsite + herança de RBAC** (padrão Verkada) para clientes com vários sites.
- **Hub de integrações/webhooks** gerenciável (ERP/BI/acesso) — sobre o OpenAPI (013).
- UI de **tuning por câmera** (zonas/exclusão/perfil dia-noite, sobre 039).

**P2 — diferenciação:**
- **Construtor de relatórios** self-service (sobre 043).
- Construtor de **automação no-code** (regra → ação) leve.
- **Base de conhecimento / ajuda guiada** in-app.

## Conclusão
Já temos a espinha de um SaaS auto-administrável (tenancy, RBAC, flags, planos, tickets, audit,
branding, versões). O que falta para o nível ServiceNow/Verkada é, na ordem: **(1) um inventário
unificado de ativos com onboarding e teste de câmera no próprio painel** (P0 — também é o que destrava
RVB/Roccabela sem ir a campo às cegas), **(2)** automação/notificação e hierarquia de sites por UI,
**(3)** hub de integrações e relatórios self-service. O P0 está especificado na task-052.

Fontes: ServiceNow Now Platform (pilares, CMDB, Service Catalog, self-service/no-code), Verkada
(hierarquia site/subsite + RBAC herdado, add/test de câmera self-service), Rhombus (API aberta +
integrações, relay para câmeras legadas).
