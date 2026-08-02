-- 107_migrations_ledger.sql
--
-- Ledger de migrations aplicadas (mutirão de dívida técnica — itens 3.2/3.3/3.4).
-- Usado pelo runner NOVO em infra/migrations/runner_core.py, atrás da flag
-- MIGRATIONS_LEDGER_CUTOVER=1 (OFF por padrão em produção — ver runner_core.py).
--
-- NÃO é a mesma tabela que public.schema_migrations (criada por 001_initial_schema.sql).
-- Não reaproveitamos schema_migrations porque seu PRIMARY KEY (version) é imutável
-- (forward-only proíbe DROP/ALTER de constraint) e não comporta mais de uma linha por
-- versão — e precisamos disso para os 6 arquivos históricos com prefixo "052"
-- (052_branding_tenants, 052_camera_fps_quality, 052_cameras_retention_days,
-- 052_custom_roles, 052_events_search_indexes, 052_model_scenario_config).
--
-- Identidade de cada linha: (tenant_schema, version, filename) — sempre os três,
-- inclusive para migrations "normais" onde version já seria suficiente sozinho.
-- tenant_schema = '_global' hoje porque o runner aplica cada arquivo .sql UMA única vez,
-- de forma global (não itera schemas de tenant um a um — migrations que precisam tocar
-- todos os tenants fazem esse loop internamente via DO $$ ... FOR r IN SELECT schema_name
-- FROM public.tenants ... END $$, ver 052/067_site_id_attribution.sql).
--
-- Também criada proativamente pelo bootstrap do runner novo (runner_core.py,
-- _ensure_ledger_table) ANTES deste arquivo rodar — migrations 001-106 precisam do
-- ledger existindo para serem registradas. Esta migration garante que uma reconstrução
-- futura só a partir dos arquivos .sql (sem passar pelo runner Python) chegue ao mesmo
-- estado. CREATE TABLE IF NOT EXISTS torna a dupla criação um no-op seguro.

CREATE TABLE IF NOT EXISTS public.migrations_ledger (
    tenant_schema   VARCHAR(255) NOT NULL DEFAULT '_global',
    version         VARCHAR(10)  NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    checksum        VARCHAR(64)  NOT NULL,
    installed_rank  INTEGER,
    installed_on    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    success         BOOLEAN      NOT NULL DEFAULT TRUE,
    PRIMARY KEY (tenant_schema, version, filename)
);

-- Defesa em profundidade (além do pre-flight em Python): fora dos prefixos duplicados
-- JÁ conhecidos (infra/migrations/.duplicate-prefix-baseline), cada (tenant_schema,
-- version) só pode aparecer uma vez no ledger. É isso que mata a classe de bug dos
-- 6x052 caso ela se repita — uma migration nova que reaproveite um prefixo já usado
-- falha essa constraint (e o pre-flight do runner já teria abortado antes de chegar aqui).
--
-- A lista abaixo é hardcoded (predicados de índice parcial não podem ler um arquivo em
-- runtime) e DEVE ficar em sincronia com .duplicate-prefix-baseline. Se o baseline
-- ganhar uma entrada nova no futuro, abra uma NOVA migration para atualizar este índice
-- (não edite este arquivo — regra de forward-only, C-02).
CREATE UNIQUE INDEX IF NOT EXISTS uq_migrations_ledger_tenant_version
    ON public.migrations_ledger (tenant_schema, version)
    WHERE version NOT IN ('052');

CREATE INDEX IF NOT EXISTS idx_migrations_ledger_installed_on
    ON public.migrations_ledger (installed_on);
