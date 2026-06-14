"""
Regression tests — ADR-0018: counting DeepSORT schema rebuild.

Migration 049 drops zombie tables (counting_sessions with fueling schema +
session_events, both from legacy migrations/004_rules_engine.sql) and
rebuilds counting_sessions + counting_events with the DeepSORT schema
that counting_repository expects (tenant_id, module_code, track_id,
class_name, UNIQUE(session_id, track_id) anti-duplicate).

Migrations 015 and 048 are intentional no-ops, superseded by 049, kept
to preserve migration sequence integrity.
"""
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "migrations"


class TestMigration049Structure:
    """049 drops zombies and rebuilds counting tables with DeepSORT schema."""

    def _read_049(self) -> str:
        path = MIGRATIONS_DIR / "049_counting_deepsort_rebuild.sql"
        assert path.exists(), f"Migration 049 not found at {path}"
        return path.read_text()

    def test_049_drops_zombie_session_events(self):
        sql = self._read_049()
        assert "DROP TABLE IF EXISTS public.session_events CASCADE" in sql

    def test_049_drops_zombie_counting_sessions(self):
        sql = self._read_049()
        assert "DROP TABLE IF EXISTS public.counting_sessions CASCADE" in sql

    def test_049_creates_counting_sessions_with_deepsort_schema(self):
        sql = self._read_049()
        assert "CREATE TABLE IF NOT EXISTS public.counting_sessions" in sql
        # Required columns for counting_repository
        assert "tenant_id" in sql and "REFERENCES public.tenants(id)" in sql
        assert "camera_id" in sql and "REFERENCES public.cameras(id)" in sql
        assert "module_code" in sql
        assert "total_counts" in sql and "JSONB" in sql

    def test_049_counting_sessions_status_check(self):
        sql = self._read_049()
        assert "CHECK (status IN ('running', 'stopped'))" in sql

    def test_049_creates_counting_events_with_unique_anti_duplicate(self):
        sql = self._read_049()
        assert "CREATE TABLE IF NOT EXISTS public.counting_events" in sql
        # Anti-duplicate constraint — core DeepSORT behavior
        assert "UNIQUE (session_id, track_id)" in sql

    def test_049_counting_events_has_seen_at_columns(self):
        """counting_repository upsert_event does SET last_seen_at = NOW() on conflict."""
        sql = self._read_049()
        assert "first_seen_at" in sql
        assert "last_seen_at" in sql

    def test_049_counting_events_has_tenant_id(self):
        sql = self._read_049()
        # tenant_id appears on both tables; events block specifically
        assert "tenant_id" in sql
        # At least 2 tenant_id FKs (one per table)
        assert sql.count("REFERENCES public.tenants(id)") >= 2

    def test_049_creates_indexes(self):
        sql = self._read_049()
        assert "CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_counting_sessions_camera" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_counting_events_session" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_counting_events_tenant" in sql

    def test_049_fks_cascade_on_delete(self):
        sql = self._read_049()
        assert sql.count("ON DELETE CASCADE") >= 4, (
            "All FKs (tenant_id+camera_id on sessions, session_id+tenant_id on events) must cascade"
        )

    def test_049_is_idempotent(self):
        sql = self._read_049()
        assert "DROP TABLE IF EXISTS" in sql
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql


class TestSupersededMigrationsAreNoOps:
    """015 and 048 must be intentional no-ops referencing ADR-0018."""

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        """Drop -- line comments so DDL detection ignores explanatory text."""
        return "\n".join(
            line for line in sql.splitlines() if not line.strip().startswith("--")
        )

    def test_015_is_no_op(self):
        path = MIGRATIONS_DIR / "015_counting_sessions.sql"
        sql = path.read_text()
        assert "SUPERSEDED" in sql
        assert "049" in sql
        # Must not contain actual DDL outside comments
        executable = self._strip_sql_comments(sql)
        assert "CREATE TABLE" not in executable
        assert "ALTER TABLE" not in executable

    def test_048_is_no_op(self):
        path = MIGRATIONS_DIR / "048_counting_sessions_tenant_id.sql"
        sql = path.read_text()
        assert "SUPERSEDED" in sql
        assert "049" in sql
        executable = self._strip_sql_comments(sql)
        assert "CREATE TABLE" not in executable
        assert "ALTER TABLE" not in executable

    def test_no_ops_are_valid_sql(self):
        """SELECT 1 is valid SQL that psycopg2 accepts as a migration body."""
        for name in ("015_counting_sessions.sql", "048_counting_sessions_tenant_id.sql"):
            sql = (MIGRATIONS_DIR / name).read_text()
            # Need at least one executable statement
            stripped_no_comments = "\n".join(
                line for line in sql.splitlines() if not line.strip().startswith("--")
            )
            assert "SELECT 1" in stripped_no_comments, (
                f"{name} must contain SELECT 1 (or equivalent no-op statement)"
            )
