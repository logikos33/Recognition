# Fase 1 Edge Deployment — Schema e Models

**Data:** 2026-06-01
**Branch:** `feature/fase-1-edge-schema-v2`
**ADRs:** `docs/decisions/adr/0016-edge-tables-placement.md`, `docs/decisions/adr/0019-device-tokens-rs256.md`

---

## Resumo

Criação da fundação de dados para edge computing no Recognition.
Nenhuma câmera, inferência ou WebSocket foi alterado — apenas schema e Pydantic models.

## Migrations aplicadas

| # | Arquivo | Conteúdo |
|---|---------|----------|
| 050 | `050_edge_sites.sql` | `public.edge_sites` + trigger `set_updated_at()` |
| 051 | `051_device_tokens.sql` | `public.enrollment_tokens` + `public.device_tokens` |
| 052 | `052_site_id_attribution.sql` | `tenants.deployment_mode` + `site_id` em cameras/alerts/counting_events/operations + loop tenant schemas |
| 053 | `053_edge_heartbeats.sql` | `public.edge_heartbeats` (telemetria BIGSERIAL) |
| 054 | `054_create_tenant_schema_site_id.sql` | `create_tenant_schema()` v4 — inclui `site_id` em quality_inspections e quality_recording_segments |

**Regra append-only respeitada:** `033_quality_rvb.sql` intocado. 054 é a 4ª redefinição da função (024→028→033→054).

## Correções vs prompt mestre original

- Loop de tenant schemas usa `schema_name FROM public.tenants WHERE is_active = true AND schema_name IS NOT NULL AND schema_name <> 'public'` (schemas reais: `admin`, `rvb` — não `tenant_%`).
- `public.cameras` referenciada (não `ip_cameras`, renomeada na migration 013).
- ADR para Device Tokens RS256 criado como **0019** (ADR-0008 do repo é pipeline Roboflow/Colab).
- Migration 054 numerada sequencialmente (não `052b`).

## Package `recognition_shared`

Instalável via:
```bash
pip install -e shared/python/recognition_shared
```

Módulos: `enums`, `edge_site`, `device`, `heartbeat`.
Todos os models têm `ConfigDict(from_attributes=True)` (compatível com `RealDictCursor`).

## Validação

```bash
# Testes de migrations (46 testes)
venv/bin/python3 -m pytest services/api/tests/security/test_edge_schema.py -v

# Testes de models (18 testes)
venv/bin/python3 -m pytest shared/python/recognition_shared/tests/test_models.py -v
```

Resultado: **64 testes passando** (46 schema + 18 models).

## Validação de schema no banco real (CHECKPOINT 1)

Executado via `railway run bash -c 'psql "$DATABASE_PUBLIC_URL" ...'` antes de escrever as migrations.

Tabelas confirmadas em produção pré-execução:
- `cameras`, `alerts`, `tenants`, `operations`, `counting_events` — ✅ existem
- `tenant_id` em `operations`, `counting_events`, `alerts` — ✅ (Sprint 0.6)
- `edge_sites`, `device_tokens`, `enrollment_tokens`, `edge_heartbeats` — não existiam (criadas por 050-053)
- `tenants.deployment_mode` — não existia (criada por 052)

## Próximos passos (Fase 2)

- Endpoints de gerenciamento de sites e dispositivos (`/api/v1/edge/sites`, `/api/v1/edge/enrollment/redeem`)
- Ingestão de heartbeats (`/api/v1/edge/heartbeat`)
- Dashboard de saúde de sites no frontend
