"""
Regression tests — Fase 1 Edge Deployment: migrations 050-054.

050: public.edge_sites (sites físicos de edge, multi-tenant)
051: public.device_tokens + public.enrollment_tokens (autenticação RS256)
052: site_id em tabelas operacionais de public + tenants.deployment_mode
053: public.edge_heartbeats (telemetria time-series)
054: create_tenant_schema() v4 — inclui site_id em quality_inspections e
     quality_recording_segments. 033 INTOCADA (regra append-only).

Ver ADR-0016 (edge-tables-placement) e ADR-0019 (device-tokens-rs256).
"""
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "migrations"


# ---------------------------------------------------------------------------
# 050 — edge_sites
# ---------------------------------------------------------------------------

class TestMigration050EdgeSites:

    def _read(self) -> str:
        path = MIGRATIONS_DIR / "050_edge_sites.sql"
        assert path.exists(), f"Migration 050 not found at {path}"
        return path.read_text()

    def test_creates_edge_sites_table(self):
        assert "CREATE TABLE IF NOT EXISTS public.edge_sites" in self._read()

    def test_tenant_id_fk(self):
        sql = self._read()
        assert "tenant_id" in sql
        assert "REFERENCES public.tenants(id)" in sql

    def test_deployment_mode_check(self):
        sql = self._read()
        assert "deployment_mode" in sql
        assert "'cloud'" in sql and "'edge'" in sql and "'hybrid'" in sql

    def test_status_check(self):
        sql = self._read()
        assert "'active'" in sql
        assert "'inactive'" in sql
        assert "'maintenance'" in sql
        assert "'provisioning'" in sql

    def test_indexes_created(self):
        sql = self._read()
        assert "CREATE INDEX IF NOT EXISTS idx_edge_sites_tenant" in sql
        assert "CREATE UNIQUE INDEX IF NOT EXISTS uniq_edge_sites_tenant_name" in sql

    def test_updated_at_trigger(self):
        sql = self._read()
        assert "CREATE OR REPLACE FUNCTION public.set_updated_at" in sql
        assert "trg_edge_sites_updated_at" in sql

    def test_is_idempotent(self):
        sql = self._read()
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql
        assert "DROP TRIGGER IF EXISTS" in sql


# ---------------------------------------------------------------------------
# 051 — device_tokens + enrollment_tokens
# ---------------------------------------------------------------------------

class TestMigration051DeviceTokens:

    def _read(self) -> str:
        path = MIGRATIONS_DIR / "051_device_tokens.sql"
        assert path.exists(), f"Migration 051 not found at {path}"
        return path.read_text()

    def test_creates_enrollment_tokens_table(self):
        assert "CREATE TABLE IF NOT EXISTS public.enrollment_tokens" in self._read()

    def test_creates_device_tokens_table(self):
        assert "CREATE TABLE IF NOT EXISTS public.device_tokens" in self._read()

    def test_both_tables_have_tenant_and_site_fk(self):
        sql = self._read()
        assert sql.count("REFERENCES public.tenants(id)") >= 2
        assert sql.count("REFERENCES public.edge_sites(id)") >= 2

    def test_enrollment_token_hash_unique(self):
        assert "token_hash" in self._read()
        assert "UNIQUE" in self._read()

    def test_device_tokens_unique_tenant_device(self):
        sql = self._read()
        assert "UNIQUE (tenant_id, device_id)" in sql

    def test_device_tokens_has_revoked_flag(self):
        sql = self._read()
        assert "revoked" in sql
        assert "BOOLEAN" in sql

    def test_partial_indexes_for_active_devices(self):
        sql = self._read()
        assert "WHERE revoked = false" in sql

    def test_is_idempotent(self):
        sql = self._read()
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# 052 — site_id attribution + deployment_mode
# ---------------------------------------------------------------------------

class TestMigration052SiteIdAttribution:

    def _read(self) -> str:
        path = MIGRATIONS_DIR / "052_site_id_attribution.sql"
        assert path.exists(), f"Migration 052 not found at {path}"
        return path.read_text()

    def test_adds_deployment_mode_to_tenants(self):
        sql = self._read()
        assert "ALTER TABLE public.tenants" in sql
        assert "deployment_mode" in sql
        assert "DEFAULT 'cloud'" in sql

    def test_deployment_mode_check_constraint(self):
        sql = self._read()
        assert "'cloud'" in sql and "'edge'" in sql and "'hybrid'" in sql

    def test_adds_site_id_to_cameras(self):
        sql = self._read()
        assert "ALTER TABLE public.cameras" in sql
        assert "site_id" in sql

    def test_does_not_reference_ip_cameras(self):
        assert "ip_cameras" not in self._read()

    def test_adds_site_id_to_alerts(self):
        assert "ALTER TABLE public.alerts" in self._read()

    def test_adds_site_id_to_counting_events(self):
        assert "ALTER TABLE public.counting_events" in self._read()

    def test_adds_site_id_to_operations(self):
        assert "ALTER TABLE public.operations" in self._read()

    def test_site_id_fk_references_edge_sites(self):
        sql = self._read()
        assert "REFERENCES public.edge_sites(id)" in sql

    def test_loop_uses_schema_name_not_tenant_prefix(self):
        sql = self._read()
        # Correct pattern uses schema_name column from tenants table
        assert "schema_name" in sql
        # Must NOT use the broken tenant_% prefix (matches zero schemas in this repo)
        assert "LIKE 'tenant_%'" not in sql

    def test_loop_covers_quality_inspections(self):
        assert "quality_inspections" in self._read()

    def test_loop_covers_quality_recording_segments(self):
        assert "quality_recording_segments" in self._read()

    def test_site_id_fk_on_delete_set_null(self):
        assert "ON DELETE SET NULL" in self._read()

    def test_indexes_created_for_site_id(self):
        sql = self._read()
        assert "CREATE INDEX IF NOT EXISTS idx_cameras_site" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_alerts_site" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_counting_events_site" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_operations_site" in sql

    def test_is_idempotent(self):
        sql = self._read()
        assert "ADD COLUMN IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# 053 — edge_heartbeats
# ---------------------------------------------------------------------------

class TestMigration053EdgeHeartbeats:

    def _read(self) -> str:
        path = MIGRATIONS_DIR / "053_edge_heartbeats.sql"
        assert path.exists(), f"Migration 053 not found at {path}"
        return path.read_text()

    def test_creates_edge_heartbeats_table(self):
        assert "CREATE TABLE IF NOT EXISTS public.edge_heartbeats" in self._read()

    def test_uses_bigserial_primary_key(self):
        assert "BIGSERIAL" in self._read()

    def test_tenant_and_site_fk(self):
        sql = self._read()
        assert "REFERENCES public.tenants(id)" in sql
        assert "REFERENCES public.edge_sites(id)" in sql

    def test_has_hardware_metrics(self):
        sql = self._read()
        assert "cpu_pct" in sql
        assert "mem_pct" in sql
        assert "disk_pct" in sql

    def test_has_inference_metrics(self):
        sql = self._read()
        assert "inference_fps" in sql
        assert "inference_latency_ms" in sql

    def test_status_check_constraint(self):
        sql = self._read()
        assert "'healthy'" in sql
        assert "'degraded'" in sql
        assert "'critical'" in sql
        assert "'offline'" in sql

    def test_time_series_indexes(self):
        sql = self._read()
        assert "CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_site_time" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_tenant_time" in sql

    def test_partial_index_for_alerts(self):
        sql = self._read()
        assert "idx_edge_heartbeats_status" in sql
        assert "WHERE status IN" in sql

    def test_is_idempotent(self):
        sql = self._read()
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# 054 — create_tenant_schema() v4 (append-only — 033 intocada)
# ---------------------------------------------------------------------------

class TestMigration054CreateTenantSchemaV4:

    def _read(self) -> str:
        path = MIGRATIONS_DIR / "054_create_tenant_schema_site_id.sql"
        assert path.exists(), f"Migration 054 not found at {path}"
        return path.read_text()

    def test_redefines_create_tenant_schema_function(self):
        sql = self._read()
        assert "CREATE OR REPLACE FUNCTION public.create_tenant_schema" in sql

    def test_quality_inspections_has_site_id(self):
        sql = self._read()
        # site_id must appear in the quality_inspections DDL block
        qi_start = sql.find("quality_inspections")
        assert qi_start != -1
        # site_id must appear after quality_inspections block starts
        assert "site_id" in sql[qi_start:]

    def test_quality_recording_segments_has_site_id(self):
        sql = self._read()
        qrs_start = sql.find("quality_recording_segments")
        assert qrs_start != -1
        assert "site_id" in sql[qrs_start:]

    def test_site_id_fk_references_edge_sites(self):
        assert "REFERENCES public.edge_sites(id)" in self._read()

    def test_preserves_all_core_tables(self):
        sql = self._read()
        for table in (
            "cameras", "alerts", "models", "training_jobs",
            "quality_inspections", "quality_pieces", "quality_reworks",
            "quality_wiser_exports", "quality_stations",
            "quality_camera_config", "quality_reference_snapshots",
            "quality_annotation_frames", "quality_retrain_suggestions",
            "quality_training_jobs", "quality_cep_baseline",
            "crossings",
        ):
            assert f"%I.{table}" in sql, f"Table {table!r} missing from create_tenant_schema in 054"

    def test_admin_support_tickets_preserved(self):
        sql = self._read()
        assert "support_tickets" in sql
        assert "p_schema_name = 'admin'" in sql

    def test_033_not_modified(self):
        """033 deve estar intocado — qualquer alteração viola a regra append-only."""
        path_033 = MIGRATIONS_DIR / "033_quality_rvb.sql"
        assert path_033.exists()
        content_033 = path_033.read_text()
        # 033 NÃO deve conter site_id — essa coluna só existe na 054
        assert "site_id" not in content_033, (
            "033_quality_rvb.sql was modified in-place (site_id found). "
            "This violates the append-only migration rule. "
            "Changes to create_tenant_schema() must be in a new numbered migration."
        )

    def test_is_idempotent(self):
        assert "CREATE OR REPLACE FUNCTION" in self._read()
