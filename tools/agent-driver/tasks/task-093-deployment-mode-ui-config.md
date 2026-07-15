---
title: "Deployment modes: edge/dual/cloud-only configurável na UI por tenant/site (sem código)"
pr_title: "feat(platform): modo de deployment por site editável na UI (edge/dual/cloud-only)"
commit_message: "feat(platform): DEPLOYMENT_MODE como config de tenant/site na UI"
eval: default
risk: security
requires_migration: talvez (coluna deployment_mode em site/tenant)
depende_de: ADR-0046
bloco: 6 (Deployment modes)
---

# Task 093 — Modo de deployment na UI

## Status (C-04 — investigação real do código, 2026-07-15)

**Backend: já existia, zero mudança necessária.**
- `public.edge_sites.deployment_mode` (migration 065) e `public.tenants.deployment_mode`
  (migration 067) já existem, CHECK `IN ('cloud','edge','hybrid')`.
- `GET/POST/PATCH /api/v1/edge/sites[/<id>]` (`services/api/app/api/v1/edge/routes.py`,
  desde task-003/017) já aceitam e persistem `deployment_mode`.
- Já **role-gated**: `has_permission('edge:manage')`, `default_roles=['superadmin','admin']`
  (`services/api/app/core/permissions.py`), `enforced=True`. Confirmado com
  `services/api/tests/integration/test_edge_site_detail_update.py` (já passava antes
  desta task): `operator` → 403, sem JWT → 401, cross-tenant → **404** (C-01), enum
  inválido → 400, `tenant_id` no body é ignorado.
- **Nenhum arquivo de backend foi tocado nesta task.**

**Frontend: gap real era 100% aqui.**
- `EdgeFleetPanel.tsx` (única tela que tocava em edge sites) era read-only, cross-tenant
  (visão de frota do superadmin) e nem exibia `deployment_mode`.
- Não existia nenhuma função de client para `GET/PATCH /v1/edge/sites` (só
  `overview`/`sites/health`/`heartbeats`/`heartbeat-summary` em `edgeService.ts`).
- **Gap de roteamento descoberto durante a investigação**: não existe hoje nenhuma tela
  do frontend acessível por `role === 'admin'` (tenant admin, não superadmin) fora de
  `/admin/*` — e `/admin/*` é bloqueado para `admin` por dois guards hardcoded em
  `superadmin` (`AdminRoute.tsx` + `AdminLayout.tsx`). Isso é um padrão maior (afeta
  outras permissões WS7 como `devices:manage`), não resolvido aqui — só contornado para
  este caso reaproveitando a rota legada `/epi/sites-health` (fora de `/admin`) para
  redirecionar `admin` a uma tela nova `/epi/sites`.
- **Nomenclatura**: ADR-0046 usa rótulos de produto `edge | dual | cloud_only`; o schema
  persiste `edge | hybrid | cloud`. Decisão: mapear só na apresentação
  (`DEPLOYMENT_MODE_LABELS` em `apps/frontend/src/types/edge.ts`) — **sem migration**,
  sem alterar o CHECK constraint.
- Gap conhecido, documentado mas fora de escopo: `{tenant_schema}.cameras` (módulo
  Qualidade) não tem `site_id` — só `public.cameras` tem (migrations 067/081). Não afeta
  esta task porque a UI é por-site, não por-câmera.

**Implementado:**
- `apps/frontend/src/types/edge.ts`: `DeploymentMode`, `DEPLOYMENT_MODE_LABELS`, `EdgeSite`.
- `apps/frontend/src/services/edgeService.ts`: `listSites()`, `updateSite(id, updates)`.
- `apps/frontend/src/pages/epi/EpiSitesPage.tsx` (+ `.css.ts`): lista os sites do tenant,
  select de `deployment_mode` por site com update otimista + rollback em erro, gated por
  `useAuth().isAdmin` (defesa em profundidade — backend é a fonte de verdade).
- `apps/frontend/src/AppRoutes.tsx`: rota `/epi/sites`; `SitesHealthRedirect` agora manda
  `admin` (não superadmin) para `/epi/sites` em vez do dashboard.
- Testes: `EpiSitesPage.test.tsx` (7 casos: gating, list, PATCH otimista, rollback,
  rótulos, estados vazio/erro) + extensão de `edgeService.test.ts` (listSites/updateSite).
- **Sem migration** — confirmado desnecessária.

## Objetivo
Tornar o modo (edge | dual | cloud_only) configuração por tenant/site editável na plataforma, não env hard-coded.

## Escopo
- Persistir o modo por site (migration aditiva se preciso, forward-only, commit separado).
- UI role-gated para setar o modo; backend resolve o comportamento (origem de vídeo/evidência) por modo.

## Aceite
- [x] Admin troca o modo pela UI (`/epi/sites`); comportamento muda sem deploy (só grava
      `deployment_mode`, lido pelo código de runtime existente — `stream_handlers.py`,
      `quality_clips.py::_should_upload_evidence_to_r2`); tenant-scoped (404 cross-tenant,
      já coberto por `test_edge_site_detail_update.py`).

## Checkpoint
- STOP-for-review. Migration (se houver) separada da lógica.
