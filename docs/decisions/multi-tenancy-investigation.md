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

---

## 7. Ambiguidades resolvidas — PR #4 (2026-05-28)

### 7.1 camera_events — existe mas é dead code

**Existe?** Sim — criada em migration `002_cameras.sql` (public schema):
```sql
CREATE TABLE IF NOT EXISTS camera_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES ip_cameras(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
```

**Tem `tenant_id`?** Não — o tenant é implícito via `ip_cameras.tenant_id`.

**Código de runtime que a usa:** **zero** — `git grep camera_events backend/app/` retorna vazio.
A tabela foi criada mas nunca implementada. É código morto.

**Onde ficam os eventos de detecção de câmera hoje?**
`public.alerts` — `socket_bridge.py` insere detecções diretamente em `alerts`:
```python
# socket_bridge.py:99 — sem SET search_path → vai para public.alerts
cur.execute(
    "INSERT INTO alerts (camera_id, violations, confidence, class_name, verification_status) "
    "VALUES (%s, %s::jsonb, %s, %s, 'pending') RETURNING id",
    ...
)
```

**Impacto para edge migration 044:** A migration deve adicionar `site_id` a `public.alerts`
(a tabela real de eventos), não a `camera_events` (dead code). A referência do plano a
"camera_events" estava errada — deve ser corrigida para `alerts`.

---

### 7.2 alerts canônica — `public.alerts` é a tabela real

**Veredicto:** `public.alerts` é a tabela canônica e única sendo usada.

| Local | Query | Schema usado |
|-------|-------|-------------|
| `socket_bridge.py:99` | `INSERT INTO alerts` (sem search_path) | **public** |
| `alert_repository.py:22` | `INSERT INTO alerts (camera_id, ...)` | **public** |
| `alert_repository.py:131` | `FROM alerts WHERE tenant_id = %s` | **public** (tem tenant_id) |
| `fueling/routes.py:53` | `FROM alerts WHERE tenant_id = %s` | **public** (tem tenant_id) |
| `dashboard/routes.py:85` | `FROM alerts` (sem search_path) | **public** |
| `verification_service.py:62` | `FROM alerts a LEFT JOIN ip_cameras` | **public** |

Nenhuma query usa `SET search_path` antes de acessar `alerts`.

**`tenant_schema.alerts` (criada por 024/028/033) é dead code.** Não existe código que
faça `SET search_path` e depois acesse `alerts`. Provavelmente foi criada em antecipação
de uma migração futura para schema isolation que nunca aconteceu.

**Impacto para OQ-008:** `public.alerts` recebe `site_id` via `ALTER TABLE` simples.
A versão `tenant_schema.alerts` pode ser ignorada (dead code) ou removida em sprint futura.

---

### 7.3 Como iterar sobre tenant schemas em migrations

**`tenants.slug` é o nome do schema PostgreSQL** — confirmado:
- Migration 005 insere `slug = 'default'`
- Migration 024 chama `create_tenant_schema('admin')` e `create_tenant_schema('rvb')`
- Os slugs `admin` e `rvb` correspondem exatamente aos schemas criados

**Como o código descobre o tenant_schema:**

`app/core/auth.py`:
```python
def get_tenant_schema() -> str:
    """Extrai tenant_schema do JWT. Retorna 'public' como fallback."""
    return claims.get("tenant_schema", "public")
```
O claim `tenant_schema` no JWT contém o slug do tenant (ex: `"rvb"`).

**Não existe tabela `tenant_schemas`** — o `tenants.slug` é a fonte de verdade.

**Loop canônico para migrations que modificam tabelas tenant_schema:**
```sql
DO $$ DECLARE t RECORD; BEGIN
    FOR t IN SELECT slug FROM public.tenants WHERE is_active = true LOOP
        EXECUTE format(
            'ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID',
            t.slug
        );
    END LOOP;
END $$;
```

**Importante:** novos tenants criados DEPOIS desta migration não terão `site_id`
automaticamente. Para isso, a função `create_tenant_schema()` também deve ser atualizada
para incluir `site_id` nos DDLs das tabelas relevantes.

---

### 7.4 Resumo para OQ-008 (decisão C — híbrido)

Com as ambiguidades resolvidas, a regra de roteamento para migrations 042-045:

| Tabela | Localização real | Como adicionar site_id |
|--------|-----------------|----------------------|
| `ip_cameras` | PUBLIC (com tenant_id) | `ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS site_id` |
| `camera_events` | PUBLIC (dead code) | **Ignorar** — tabela não usada |
| `alerts` | PUBLIC (com tenant_id) | `ALTER TABLE alerts ADD COLUMN IF NOT EXISTS site_id` |
| `counting_events` | PUBLIC | `ALTER TABLE counting_events ADD COLUMN IF NOT EXISTS site_id` |
| `quality_inspections` | TENANT_SCHEMA ONLY | Loop `EXECUTE format` sobre `tenants.slug` + update `create_tenant_schema()` |
| `operations` | PUBLIC (com tenant_id) | `ALTER TABLE operations ADD COLUMN IF NOT EXISTS site_id` |

`edge_sites` e `device_tokens` (novas): `public` com `tenant_id NOT NULL` — consistente
com `operations`, `ip_cameras` (tabelas globais de configuração com tenant_id).
