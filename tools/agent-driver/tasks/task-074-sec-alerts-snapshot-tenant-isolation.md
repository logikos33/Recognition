# Task 074 — [SEC] `GET /api/alerts/<id>/snapshot` sem tenant_id (achado #7)

**Status**: CONCLUÍDA (2026-07-12)
**Risk**: security (P0 — leak cross-tenant)
**Branch**: fix/sec-alerts-snapshot-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #7 · **Relaciona**: ADR-0017, C-01.

## Problema (produção)
`GET /api/alerts/<alert_id>/snapshot` faz query direta **sem filtro `tenant_id`** → um tenant pode ler
o snapshot (imagem do evento) de um alerta de **outro tenant**.

## Fix
- Filtrar `tenant_id` na busca do alerta antes de servir o snapshot. Alerta de outro tenant → 404.
- Conferir se o path do artefato (R2/local) também é escopado por tenant (não montar path a partir de
  input do usuário sem validar posse).

## Teste (falha-antes/passa-depois)
- Tenant A pede snapshot de alerta do tenant B → 404 (antes: 200 + imagem). Mesmo tenant → ok.

## Aceite
- Query com `tenant_id`; 404 cross-tenant; teste prova; ruff+pytest verde; PR develop; STOP.

## Execução — 2026-07-12

- **Vulnerabilidade confirmada** em `services/api/app/api/v1/alerts/routes.py::alert_snapshot`
  (linha 143): a query `SELECT evidence_key FROM alerts WHERE id = %s` não filtrava por `tenant_id` —
  qualquer tenant autenticado que soubesse/adivinhasse um `alert_id` de outro tenant recebia 200 +
  `snapshot_url` presignada para a imagem de evidência alheia.
- **Fix**: novo método `AlertRepository.get_evidence_key(alert_id, tenant_id)`
  (`services/api/app/infrastructure/database/repositories/alert_repository.py`) — SQL agora é
  `SELECT evidence_key FROM alerts WHERE id = %s AND tenant_id = %s`. A rota passou a chamar esse
  método com `tenant_id=get_tenant_id()` em vez do `repo._execute_one(...)` cru sem tenant. Alerta
  inexistente e alerta de outro tenant retornam o **mesmo** 404 ("Snapshot não disponível") — sem
  diferenciar, para não permitir enumeração cross-tenant via diferença de status/mensagem.
- **Path do artefato**: confirmado que `evidence_key` é sempre gerado server-side
  (`f"evidence/{camera_id}/{timestamp}.jpg"` em `infrastructure/queue/tasks/inference.py`), nunca
  a partir de input do usuário — o único vetor de acesso é via `alert_id` na query, agora tenant-scoped.
  `get_storage()` continua sem `tenant_id` nesta rota, igual ao padrão já usado pela contraparte segura
  `events/routes.py::_serialize_event` — evidências de alerta usam storage de plataforma por design,
  não BYODB (diferente de vídeos/clips de qualidade, que usam `get_storage(tenant_id)`).
- **Teste falha-antes/passa-depois**: `services/api/tests/unit/api/test_alerts_routes.py::TestAlertSnapshot`
  (7 casos, incluindo `test_cross_tenant_alert_returns_404` e regressão
  `test_same_tenant_alert_returns_snapshot_url`) — rodado contra o código pré-fix, 5/7 falharam
  (rota retornava 400/nunca chamava a busca tenant-scoped); após o fix, 7/7 passam. Reforçado com
  testes de SQL em `services/api/tests/security/test_alert_repo_tenant_isolation.py::TestGetEvidenceKeyTenantIsolation`
  (SQL contém `tenant_id`, params nunca vazam tenant_id de outro tenant).
- `ruff check` limpo nos arquivos alterados; suite completa `pytest services/api/tests/` — 3436
  passed, 47 skipped, cobertura 66.75% (gate 60%).
- Skill `security-review` executada sobre o diff antes do PR — achados resolvidos/registrados no PR.
