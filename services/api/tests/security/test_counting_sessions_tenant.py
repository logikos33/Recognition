"""
Regression tests — Sprint 0.6 BLOCO 2: counting tables tenant_id backfill.

Migration 015 declared tenant_id NOT NULL on counting_sessions but the
tables existed from earlier deploy without the column. CREATE TABLE IF
NOT EXISTS skipped recreation; subsequent CREATE INDEX failed.

Migration 048 backfills tenant_id, promotes to NOT NULL + FK, creates
the missing indexes. RAISES EXCEPTION on orphan rows.
"""
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "migrations"


class TestMigration048Structure:
    """048 must backfill tenant_id in counting_sessions + counting_events safely."""

    def _read_048(self) -> str:
        path = MIGRATIONS_DIR / "048_counting_sessions_tenant_id.sql"
        assert path.exists(), f"Migration 048 not found at {path}"
        return path.read_text()

    def test_048_adds_tenant_id_to_counting_sessions(self):
        sql = self._read_048()
        assert "ALTER TABLE counting_sessions" in sql
        assert "ADD COLUMN IF NOT EXISTS tenant_id UUID" in sql

    def test_048_adds_tenant_id_to_counting_events(self):
        sql = self._read_048()
        assert "ALTER TABLE counting_events" in sql

    def test_048_backfills_via_cameras_join(self):
        sql = self._read_048()
        assert "UPDATE counting_sessions" in sql
        assert "FROM cameras" in sql
        assert "cs.camera_id = c.id" in sql

    def test_048_backfills_events_via_counting_sessions(self):
        sql = self._read_048()
        assert "UPDATE counting_events" in sql
        assert "FROM counting_sessions" in sql
        assert "ce.session_id = cs.id" in sql

    def test_048_raises_on_orphan_rows(self):
        sql = self._read_048()
        assert "RAISE EXCEPTION" in sql
        assert "could not be backfilled" in sql

    def test_048_promotes_not_null_and_fk(self):
        sql = self._read_048()
        assert "SET NOT NULL" in sql
        assert "FOREIGN KEY (tenant_id) REFERENCES tenants(id)" in sql

    def test_048_creates_indexes(self):
        sql = self._read_048()
        assert "CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_id" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_counting_events_tenant_id" in sql

    def test_048_is_idempotent(self):
        sql = self._read_048()
        # Guards on SET NOT NULL: only fires if column still nullable
        assert "is_nullable = 'YES'" in sql
        # Guards on FK: only adds if constraint doesn't exist
        assert "constraint_type = 'FOREIGN KEY'" in sql
