# PROMPT MESTRE — FASE 1: Schema e Models de Edge

> Cole este bloco inteiro no Claude Code (CLI ou VSCode) na raiz do repositório `Recognition`.
> Modelo recomendado: `claude-opus-4-6` (decisões), `claude-sonnet-4-6` (implementação).
> Este prompt é auto-suficiente: contém contexto, regras, SQL pronto, models, testes, gates e checkpoints.

---

## 0. Quem você é e o que vai fazer

Você é o time de engenharia do **Recognition** (plataforma de visão computacional CCTV multi-tenant). Sua tarefa nesta sessão é executar a **Fase 1 do Edge Deployment Plan**: criar o schema e os models que permitem que a plataforma conheça *sites físicos de edge*, *dispositivos (Mini PCs)* e a *telemetria* que eles enviam. Nenhuma câmera ou inferência entra aqui — é só a fundação de dados do edge.

Leia, antes de qualquer ação:
- `CLAUDE.md` (regras absolutas do projeto — prevalecem sobre tudo)
- `EDGE_DEPLOYMENT_PLAN.md` (seções 1, 2 e Fase 1)
- `docs/decisions/adr/0016-edge-tables-placement.md` (placement das tabelas)
- `docs/runbooks/sprint-0.6-complete.md` (por que o schema real ≠ o que as migrations sugerem)

---

## 1. Estado atual confirmado (não re-descobrir, mas validar)

- Branch base: `develop` (tree limpa, PR #12 já mergeada).
- Última migration no `develop`: **049**. Próxima numeração livre: **050**.
- Existe uma branch LOCAL `feature/edge-schema-fase-1` com um rascunho ANTIGO (migrations 042–045) feito antes da Sprint 0.6. **NÃO MERGEAR essa branch** — ela foi cortada de baseline velho, apaga as migrations 046–049 e usa `ip_cameras` (tabela que não existe mais). Use o SQL dela apenas como referência; o SQL correto já está neste prompt (seção 4).
- `shared/python/recognition_shared/` está vazio (só `.gitkeep`) — o package Pydantic NÃO existe ainda. Você vai criá-lo.
- Tabela canônica de câmeras é **`public.cameras`** (UUID). `ip_cameras` foi renomeada na migration 013 e **não existe**.

### CHECKPOINT 1 — validar schema real ANTES de escrever migration

O runner aplica cada `.sql` como uma transação e registra em `schema_migrations`. Antes de escrever os ALTERs da migration 052, confirme no banco REAL os nomes/tipos reais (não confie em memória nem nas migrations antigas):

```bash
railway service Postgres
railway run bash -c 'psql "$DATABASE_PUBLIC_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_schema='"'"'public'"'"' AND table_name IN ('"'"'cameras'"'"','"'"'alerts'"'"','"'"'operations'"'"','"'"'counting_events'"'"','"'"'tenants'"'"') ORDER BY 1;"'
railway run bash -c 'psql "$DATABASE_PUBLIC_URL" -c "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='"'"'public'"'"' AND table_name='"'"'cameras'"'"' ORDER BY ordinal_position;"'
```

Confirme: `cameras` existe (não `ip_cameras`), `operations`/`counting_events` existem e já têm `tenant_id` (Sprint 0.6). Se algo divergir do esperado, PARE e reporte antes de continuar.

---

## 2. Regras inegociáveis (do CLAUDE.md)

- **Migrations só aditivas**: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`. **NUNCA** `DROP`, `ALTER COLUMN TYPE`, `DELETE`, `TRUNCATE`.
- Qualificar tudo com `public.` (search_path-independente). `information_schema` sempre filtrando `table_schema='public'`.
- Toda tabela nova tem `tenant_id UUID NOT NULL REFERENCES public.tenants(id)`.
- `psycopg2` + `RealDictCursor`, zero ORM, zero SQL inline na camada de negócio (SQL fica em repository).
- Idempotência: rodar a migration 2x não pode dar erro.
- TypeScript strict; zero `print()` no backend (use `logging`).
- Commits Conventional Commits, atômicos por subtarefa.

---

## 3. Branch e fluxo

```bash
git checkout develop && git pull
git checkout -b feature/fase-1-edge-schema-v2
```

Trabalhe nessa branch. Ao final, abra PR para `develop` (NÃO para `main`). Não force-push. Não toque `main`.

---

## 4. Tarefas

### Tarefa 4.1 — Migration 050: `edge_sites`

Cria `infra/migrations/050_edge_sites.sql`:

```sql
-- 050_edge_sites.sql
-- Sites físicos onde o edge roda. Multi-tenant: tenant pode ter N sites (ADR-0016).
CREATE TABLE IF NOT EXISTS public.edge_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    location TEXT,
    deployment_mode TEXT NOT NULL CHECK (deployment_mode IN ('cloud', 'edge', 'hybrid')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance', 'provisioning')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_edge_sites_tenant ON public.edge_sites(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_edge_sites_tenant_name ON public.edge_sites(tenant_id, name);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_sites_updated_at ON public.edge_sites;
CREATE TRIGGER trg_edge_sites_updated_at
    BEFORE UPDATE ON public.edge_sites
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
```

> Nota: a função `set_updated_at()` usa `CREATE OR REPLACE` e é genérica; se já existir uma equivalente no schema, confirme a assinatura antes (não deve quebrar — é no-arg trigger). Se houver conflito de nome, renomeie a sua para `public.set_updated_at_edge()`.

### Tarefa 4.2 — Migration 051: `device_tokens` + `enrollment_tokens`

Cria `infra/migrations/051_device_tokens.sql` (ADR-0008 device tokens RS256 + ADR-0016 placement):

```sql
-- 051_device_tokens.sql
CREATE TABLE IF NOT EXISTS public.enrollment_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    used_by_device_id TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_tenant_site ON public.enrollment_tokens(tenant_id, site_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_expires ON public.enrollment_tokens(expires_at) WHERE used_at IS NULL;

CREATE TABLE IF NOT EXISTS public.device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    device_name TEXT,
    public_key_pem TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID,
    revocation_reason TEXT,
    last_seen_at TIMESTAMPTZ,
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, device_id)
);
CREATE INDEX IF NOT EXISTS idx_device_tokens_tenant_site ON public.device_tokens(tenant_id, site_id);
CREATE INDEX IF NOT EXISTS idx_device_tokens_active ON public.device_tokens(tenant_id, device_id) WHERE revoked = false;
CREATE INDEX IF NOT EXISTS idx_device_tokens_fingerprint ON public.device_tokens(fingerprint) WHERE revoked = false;
```

### Tarefa 4.3 — Migration 052: `site_id` + `deployment_mode` em tenants

Cria `infra/migrations/052_site_id_attribution.sql`. **Use `public.cameras` (NÃO `ip_cameras`).** `operations` e `counting_events` já existem e já têm `tenant_id` (Sprint 0.6) — aqui só adicionamos `site_id`.

```sql
-- 052_site_id_attribution.sql
-- Roteamento por site (ADR-0016). ALTER direto em public; loop EXECUTE em tenant_schemas.

-- deployment_mode por tenant (ADR-0007): default 'cloud' p/ não quebrar tenants existentes
ALTER TABLE public.tenants
    ADD COLUMN IF NOT EXISTS deployment_mode TEXT NOT NULL DEFAULT 'cloud'
    CHECK (deployment_mode IN ('cloud', 'edge', 'hybrid'));

-- site_id em tabelas operacionais de public
ALTER TABLE public.cameras        ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;
ALTER TABLE public.alerts         ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;
ALTER TABLE public.counting_events ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;
ALTER TABLE public.operations     ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_site         ON public.cameras(site_id);
CREATE INDEX IF NOT EXISTS idx_alerts_site          ON public.alerts(site_id);
CREATE INDEX IF NOT EXISTS idx_counting_events_site ON public.counting_events(site_id);
CREATE INDEX IF NOT EXISTS idx_operations_site      ON public.operations(site_id);

-- quality_inspections vive em cada tenant_schema → loop
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name LIKE 'tenant_%'
    LOOP
        EXECUTE format(
            'ALTER TABLE IF EXISTS %I.quality_inspections
             ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;',
            r.schema_name
        );
    END LOOP;
END $$;
```

> ATENÇÃO `create_tenant_schema()`: essa função tem 3 definições progressivas (migrations 024, 028, 033). Para que NOVOS tenants já nasçam com `site_id` em `quality_inspections`, leia a versão mais recente (033), preserve TODO o conteúdo dela e só adicione a coluna `site_id`. **Isso toca todos os tenants → ver CHECKPOINT 2 antes de alterar a função.**

### Tarefa 4.4 — Migration 053: `edge_heartbeats`

Cria `infra/migrations/053_edge_heartbeats.sql` (telemetria time-series):

```sql
-- 053_edge_heartbeats.sql
CREATE TABLE IF NOT EXISTS public.edge_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cpu_pct NUMERIC(5,2), mem_pct NUMERIC(5,2), gpu_pct NUMERIC(5,2),
    gpu_mem_pct NUMERIC(5,2), disk_pct NUMERIC(5,2),
    inference_fps NUMERIC(6,2), inference_latency_ms NUMERIC(8,2),
    cameras_online INT, cameras_total INT, queue_depth INT,
    upload_kbps NUMERIC(10,2), download_kbps NUMERIC(10,2),
    status TEXT CHECK (status IN ('healthy', 'degraded', 'critical', 'offline')),
    last_error TEXT,
    edge_version TEXT
);
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_site_time   ON public.edge_heartbeats(site_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_tenant_time ON public.edge_heartbeats(tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_status      ON public.edge_heartbeats(site_id, status, received_at DESC)
    WHERE status IN ('degraded', 'critical', 'offline');
```

### Tarefa 4.5 — Package `recognition_shared` (Pydantic v2)

Crie o package em `shared/python/recognition_shared/`. Pydantic v2, com `ConfigDict(from_attributes=True)` em todo model (compatibilidade com `RealDictCursor`). Estrutura mínima:

```
shared/python/recognition_shared/
├── __init__.py            # exporta os símbolos públicos
├── pyproject.toml         # package instalável (pip install -e)
├── enums.py               # DeploymentMode, SiteStatus, DeviceStatus, HeartbeatStatus
├── edge_site.py           # EdgeSite, EdgeSiteCreate
├── device.py              # DeviceToken, DeviceClaims, EnrollmentRequest, EnrollmentResponse
├── heartbeat.py           # Heartbeat (ingest) + HeartbeatRecord (persistido)
└── tests/
    └── test_models.py     # round-trip dict↔model, validação de enums, from_attributes
```

Regras dos models:
- Enums como `str, Enum` (serializáveis e legíveis no banco). `DeploymentMode = {cloud, edge, hybrid}`, `SiteStatus = {active, inactive, maintenance, provisioning}`, `HeartbeatStatus = {healthy, degraded, critical, offline}`.
- `DeviceClaims`: o que vai dentro do JWT RS256 do device — `tenant_id`, `site_id`, `device_id`, `scopes: list[str]`, `iat`, `exp`. Sem segredos de usuário.
- `EnrollmentRequest`: `enrollment_token`, `device_id`, `device_name`, `public_key_pem`. `EnrollmentResponse`: `device_token` (assinado) + `expires_at`.
- Todo campo com tipo explícito; nada de `Any`.

### Tarefa 4.6 — Testes

- `shared/python/recognition_shared/tests/test_models.py`: round-trip dict↔model, rejeição de enum inválido, `from_attributes` a partir de um objeto que imita `RealDictRow`.
- `services/api/tests/migrations/test_fase1_schema.py` (ou onde os testes de migration vivem): valida que, após rodar as migrations num banco de teste limpo, as 4 tabelas existem, têm `tenant_id NOT NULL` (onde aplicável), os índices esperados existem, e `tenants.deployment_mode` default = `'cloud'`. Reaproveite o padrão dos testes existentes de Sprint 0.6.
- Idempotência: teste que aplica as migrations 050–053 duas vezes sem erro.

### Tarefa 4.7 — Documentação

- `docs/DATABASE.md`: adicionar as 4 tabelas novas + `tenants.deployment_mode`.
- `docs/runbooks/fase-1-edge-schema.md`: o que foi feito, comandos de validação, SHAs.
- Se tomar alguma decisão arquitetural nova, ADR curto em `docs/decisions/adr/`.

---

## 5. Critérios de aceitação (a Fase 1 só fecha com tudo verde)

- [ ] Migrations 050–053 criadas, idempotentes (rodam 2x sem erro), só aditivas.
- [ ] `052` usa `public.cameras` (NÃO `ip_cameras`) e não dá erro de relação inexistente.
- [ ] `tenants.deployment_mode` existe com default `'cloud'` (tenants atuais não quebram).
- [ ] Package `recognition_shared` instalável (`pip install -e shared/python/recognition_shared`) e importável.
- [ ] Testes novos passam: `pytest shared/python/recognition_shared/tests` e os de migration.
- [ ] CI verde nos 4 checks: ruff, gitleaks, pytest, tsc.
- [ ] Coverage subiu na direção da meta (~31%→40% na área nova).
- [ ] `docs/DATABASE.md` + runbook atualizados.
- [ ] PR aberta para `develop` (não main), com descrição linkando este plano.

---

## 6. CHECKPOINTS obrigatórios (PARE e peça revisão humana)

- **CHECKPOINT 1** (seção 1): validar schema real no banco antes de escrever a 052.
- **CHECKPOINT 2**: antes de alterar `create_tenant_schema()` — toca TODOS os tenants. Mostre o diff e espere OK.
- **CHECKPOINT 3**: antes de rodar QUALQUER migration contra o banco de **produção/staging**. Em dev/harness local, pode rodar à vontade.
- **CHECKPOINT 4**: antes de mergear a PR.
- Nunca: `DROP`, `main`, force-push, dados de cliente, dependência nova não discutida.

## 7. Comunicação

Direta, em português, sem cordialidade redundante. Qualidade > prazo. Quando a inferência divergir do banco real, o banco real ganha — sempre.
