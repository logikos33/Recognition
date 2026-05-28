# Multi-tenancy — Investigação de Arquitetura

**Data:** 2026-05-28
**Motivação:** Validação do INSERT em `quality_training.py` (PR #4) revelou que o
sistema usa schema-per-tenant isolation, não coluna `tenant_id` para tabelas de
dados tenant-específicos. Esta investigação mapeia a arquitetura real para informar
OQ-008 (onde ficam as tabelas de edge).

---

## 1. Como um tenant schema é criado

Migration `024_tenant_schema_function.sql` define:

```sql
CREATE OR REPLACE FUNCTION public.create_tenant_schema(p_schema_name TEXT)
RETURNS void AS $$
BEGIN
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_schema_name);
    -- Cria todas as tabelas tenant-específicas via EXECUTE format(...)
    ...
END;
$$ LANGUAGE plpgsql;

-- Schemas criados explicitamente no final da migration:
SELECT public.create_tenant_schema('admin');
SELECT public.create_tenant_schema('rvb');
```

**Schemas existentes (confirmados via migrations):**
- `public` — tabelas globais/infraestrutura
- `admin` — schema do tenant Logikos/admin
- `rvb` — schema do tenant RVB Isolantes (primeiro cliente)

Para criar novo tenant: `SELECT public.create_tenant_schema('<nome>');` + INSERT em `public.tenants`.

---

## 2. Mapa completo: PUBLIC vs TENANT_SCHEMA

### 2.1 Tabelas em `public` (schema global)

Criadas com `CREATE TABLE IF NOT EXISTS <nome>` (sem prefixo de schema):

| Tabela | Migration | Tem tenant_id? | Notas |
|--------|-----------|---------------|-------|
| `tenants` | 005 | — | Tabela raiz de tenants |
| `users` | 001 | via tenant FK | Usuários globais |
| `ip_cameras` | 002 | YES (via 035) | Consolidado de ip_cameras→cameras em 013 |
| `cameras` | 013 | YES (via 035) | Consolidação final |
| `alerts` | 004 | YES | Também existe em tenant_schema (ver §2.3) |
| `dataset_versions` | 004 | — | |
| `rules` | 004 | — | Alert rules |
| `alert_rules` | 006 | — | |
| `models` | 007 | YES NOT NULL | Versão public; também em tenant_schema (ver §2.3) |
| `tenant_modules` | 008 | YES | |
| `module_classes` | 009 | — | |
| `yolo_classes` | 009 | — | |
| `training_frames` | 003 | — | |
| `training_videos` | 003 | — | |
| `trained_models` | 003 | via user_id | Legacy; scoped por user_id |
| `training_jobs` | 003 | — | Também em tenant_schema (ver §2.3) |
| `frame_annotations` | 019 | — | |
| `counting_sessions` | 015 | — | |
| `counting_events` | 015 | — | |
| `model_activation_log` | 014 | — | |
| `operations` | 038 | YES | |
| `operation_results` | 039 | YES | |
| `assistant_docs` | 036 | — | pgvector |
| `demo_videos` | 037 | — | |
| `schema_migrations` | 001 | — | |
| `active_sessions` | 029 | — | |
| `announcement_reads` | 029 | — | |
| `audit_log` | 029 | YES | |
| `plans` | 029 | — | |
| `platform_announcements` | 029 | — | |
| `platform_feature_flags` | 029 | — | |
| `quality_video_access_log` | 029 | — | |
| `support_tickets` | 029 | — | Versão public; também em tenant_schema |
| `system_changelog` | 031/032 | — | |
| `system_versions` | 031/032 | — | |
| `tenant_plan_history` | 029 | YES | |
| `ticket_messages` | 029 | — | |
| `training_approvals` | 029 | — | |
| `worker_metrics` | 029 | — | |
| `worker_registry` | 029 | — | |

### 2.2 Tabelas em `<tenant_schema>` (criadas via `create_tenant_schema()`)

Criadas com `EXECUTE format('CREATE TABLE IF NOT EXISTS %I.<nome> ...', p_schema_name)`.
**Nenhuma tem coluna `tenant_id`** — o schema é o isolamento.

**Definidas em migration 024** (`create_tenant_schema` base):

| Tabela | Notas |
|--------|-------|
| `<schema>.cameras` | Câmeras com módulos, schedule_rules, model_*_id |
| `<schema>.alerts` | Alertas tenant-específicos |
| `<schema>.crossings` | Eventos de cruzamento |
| `<schema>.models` | Modelos YOLO — **canônica para edge** |
| `<schema>.training_jobs` | Jobs de treinamento |
| `<schema>.support_tickets` | Tickets por tenant |

**Adicionadas em migration 028** (quality module):

| Tabela | Notas |
|--------|-------|
| `<schema>.quality_inspections` | Inspeções de qualidade — **sem tenant_id** |
| `<schema>.quality_annotation_frames` | Frames anotados |
| `<schema>.quality_camera_config` | Config de câmera para quality |
| `<schema>.quality_cep_baseline` | Baseline CEP |
| `<schema>.quality_pieces` | Peças inspecionadas |
| `<schema>.quality_recording_segments` | Segmentos gravados |
| `<schema>.quality_reference_snapshots` | Snapshots de referência |
| `<schema>.quality_retrain_suggestions` | Sugestões de retrain |
| `<schema>.quality_reworks` | Reworks de peças |
| `<schema>.quality_stations` | Estações de qualidade |
| `<schema>.quality_training_jobs` | Jobs de treino quality |
| `<schema>.quality_wiser_exports` | Exports Wiser |

### 2.3 Tabelas com nome duplicado (public E tenant_schema)

| Tabela | Em public | Em tenant_schema | Qual usam as queries? |
|--------|-----------|------------------|-----------------------|
| `alerts` | YES (tenant_id) | YES (sem tenant_id) | tenant_schema (via search_path) |
| `cameras` | YES (tenant_id via 035) | YES (sem tenant_id) | tenant_schema (via search_path) |
| `models` | YES (tenant_id) | YES (sem tenant_id) | tenant_schema (edge/quality) |
| `training_jobs` | YES | YES | tenant_schema (via search_path) |
| `support_tickets` | YES (public.) | YES (tenant_schema.) | depende do contexto |

---

## 3. Tabelas que o edge plan quer modificar (adicionar `site_id`)

EDGE_DEPLOYMENT_PLAN Fase 1, migration 044, quer adicionar `site_id` a:

| Tabela do plano | Onde fica | Impacto para migration |
|----------------|-----------|----------------------|
| `ip_cameras` | **PUBLIC** (tem tenant_id) | `ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS site_id` — migration normal |
| `camera_events` | **PUBLIC** | `ALTER TABLE camera_events ADD COLUMN IF NOT EXISTS site_id` — migration normal |
| `alerts` | **AMBÍGUO** — existe em public E tenant_schema | Precisa decidir qual; se for tenant_schema, precisa alterar via `create_tenant_schema` ou fazer UPDATE da função |
| `counting_events` | **PUBLIC** | `ALTER TABLE counting_events ADD COLUMN IF NOT EXISTS site_id` — migration normal |
| `quality_inspections` | **TENANT_SCHEMA ONLY** | **Não pode ser ALTER TABLE simples** — precisa ser EXECUTE format via função ou loop sobre schemas existentes |
| `operations` | **PUBLIC** (tem tenant_id) | `ALTER TABLE operations ADD COLUMN IF NOT EXISTS site_id` — migration normal |

---

## 4. Tabela `tenants` — confirmação

`public.tenants` (migration 005):
```sql
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);
```
Confirmado em `public`. ✓

---

## 5. Padrão de acesso às tabelas tenant_schema

Toda query que acessa tabelas tenant-específicas usa:
```python
cur.execute("SET search_path TO %s, public", (tenant_schema,))
# Agora "cameras", "alerts", "models" etc. resolvem para tenant_schema primeiro
cur.execute("SELECT ... FROM cameras WHERE ...")
```

O `tenant_schema` vem de:
- `get_tenant_id()` em `app/core/auth.py` — extrai do JWT
- Funções de task Celery recebem `tenant_schema` como parâmetro

---

## 6. Implicações para OQ-008 (tabelas de edge)

### edge_sites, device_tokens (tabelas novas)

São tabelas de **infraestrutura de site/device**, não dados de negócio por tenant:
- Um "edge site" é uma localização física (uma fábrica, uma filial)
- Um tenant pode ter múltiplos edge sites
- Um edge site serve um tenant específico

**Opção A (tenant_id em public):** `edge_sites(id, tenant_id, name, ...)` em `public`
→ Consistente com `operations`, `ip_cameras` (que também são globais com tenant_id)

**Opção B (tenant_schema):** `<schema>.edge_sites(id, name, ...)`
→ Consistente com `cameras`, `alerts` tenant-específicas

**Opção C (híbrido):**
→ `public.edge_sites` (registro de sites — dado de infraestrutura)
→ `public.device_tokens` (registro de devices — dado de segurança)
→ `site_id` nas tabelas de evento: público onde a tabela-pai está em public, via ALTER TABLE na função onde está em tenant_schema

### Problema crítico com `quality_inspections`

`quality_inspections` está SOMENTE em `tenant_schema` (sem versão public).
Para adicionar `site_id` a ela, migration 044 precisaria:
```sql
-- ERRADO: ALTER TABLE quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID
-- Não funciona — tabela não existe em public

-- CORRETO (opção 1): loop sobre schemas existentes
DO $$ DECLARE r RECORD; BEGIN
  FOR r IN SELECT schema_name FROM tenant_schemas LOOP
    EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID', r.schema_name);
  END LOOP;
END $$;

-- CORRETO (opção 2): atualizar a função create_tenant_schema para incluir site_id
-- quando novos tenants forem criados
```

---

## Referências

- Migration 024: `backend/app/infrastructure/database/migrations/024_tenant_schema_function.sql`
- Migration 028: `backend/app/infrastructure/database/migrations/028_quality_module.sql`
- Migration 007: `backend/app/infrastructure/database/migrations/007_camera_model.sql`
- OQ-008: `docs/decisions/open-questions.md`
- ADR-0012: `docs/decisions/adr/0012-models-vs-trained-models.md`
