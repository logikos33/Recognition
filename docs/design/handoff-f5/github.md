repo: logikos33/Recognition
branch: develop
path: docs/migration

## Last sync
date: 2026-08-23T17:05:00Z
### Updated in this project
- Lido o mapa-contrato da migração (LISTA-PARA-O-DESIGN, RESUMO-EXECUTIVO, CHECKLIST, inventory/domains/*.json) em `origin/develop`
- Coluna NOVO FRONT fechada para 421/421 operações — decisão + evidência por rota em `Contrato de Migração.dc.html` (dados em `contrato-dados.js`)
- Entregues: matriz de acesso 4 perfis, veredito dos 122 GAPs, 16 pedidos ao backend, 10 otimizações de UX
- Backlog de 140 operações "não cobre" agrupado em 9 entregas de tela priorizadas (P1–P3)

## Screen map
| Tela do projeto | Arquivos do repo |
|---|---|
| Contrato de Migração.dc.html | docs/migration/LISTA-PARA-O-DESIGN.md, RESUMO-EXECUTIVO.md, CHECKLIST-PRONTO-PARA-MIGRAR.md, inventory/domains/*.json, inventory/consumers.md, inventory/map_summary.json |
| Shell Logikos Vision.dc.html | auth-identity (login/contexto/impersonation), models-datasets-rules (/api/modules/), admin-aux (/v1/tenant/branding) |
| EPI Dashboard/Eventos/Evento Detalhe/Ações/Verificação | events-alerts-media (alerts, events, verification), models-datasets-rules (module stats) |
| EPI Ao Vivo | cameras-streams (stream/info,start,stop,serve_hls) |
| EPI Câmeras.dc.html | cameras-streams (CRUD, probe, test, health-context), edge-fleet (overview, sites, heartbeats) |
| EPI Relatórios.dc.html | events-alerts-media (alerts/export), ops-dashboard-misc (reports) |
| Qualidade.dc.html + Kiosk RVB + Revisão/Gestão/Configuração | quality (cameras, dashboard, gate/pieces, reworks, stations, inspections) |
| Carga.dc.html | ops-dashboard-misc (counting/sessions, fueling) |
| Estúdio.dc.html | training (images, frames, jobs, propagation, search), models-datasets-rules (datasets, models, eval, drift) |
| Admin Plataforma.dc.html | admin-core-a (dashboard, tenants, audit-log), admin-core-b (users, sessions) |
| Acesso Logikos.dc.html | auth-identity (login, forgot/reset-password) |

## Sync history
### 2026-08-04 — apps/frontend
- Explorado kiosk atual (tablet/: TabletKiosk, Idle, Identified, ResultOK/NOK) e tokens (docs/design-tokens.md)
- Lido QualityLayout.tsx e types/gate.ts (modelo V1/V2/V3 descontinuado)
- Protótipo do kiosk RVB (K1–K9) criado a partir do brief FRONTEND_EXPERIENCIA_QUALIDADE_RVB.md
