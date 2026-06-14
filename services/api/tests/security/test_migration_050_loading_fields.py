"""
Regression tests — Migration 050: loading sessions fields (CD-03/CD-06/CD-07).

A 050 estende public.counting_sessions com os campos de sessão de
carga/descarga. Deve ser idempotente (ADD COLUMN IF NOT EXISTS /
CREATE INDEX IF NOT EXISTS), forward-only (sem DROP/ALTER TYPE) e
com CHECK constraints para direction e acceptance_status.
"""
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "migrations"

EXPECTED_COLUMNS = (
    "bay_id",
    "truck_plate",
    "direction",
    "expected_count",
    "divergence",
    "video_clip_url",
    "manual_count",
    "acceptance_status",
)


class TestMigration050Structure:

    def _read_050(self) -> str:
        path = MIGRATIONS_DIR / "050_loading_sessions_fields.sql"
        assert path.exists(), f"Migration 050 not found at {path}"
        return path.read_text()

    def test_050_adds_all_loading_columns(self):
        sql = self._read_050()
        for column in EXPECTED_COLUMNS:
            assert f"ADD COLUMN IF NOT EXISTS {column}" in sql, (
                f"Coluna {column} ausente na migration 050"
            )

    def test_050_targets_counting_sessions(self):
        sql = self._read_050()
        assert "ALTER TABLE public.counting_sessions" in sql

    def test_050_direction_check_constraint(self):
        sql = self._read_050()
        assert "CHECK (direction IN ('load', 'unload'))" in sql

    def test_050_acceptance_status_check_constraint(self):
        sql = self._read_050()
        assert "CHECK (acceptance_status IN ('pending', 'accepted', 'rejected'))" in sql

    def test_050_tenant_bay_index(self):
        sql = self._read_050()
        assert "CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_bay" in sql
        assert "ON public.counting_sessions (tenant_id, bay_id)" in sql

    def test_050_is_idempotent_and_forward_only(self):
        sql = self._read_050()
        executable = "\n".join(
            line for line in sql.splitlines() if not line.strip().startswith("--")
        )
        # Idempotência
        assert "IF NOT EXISTS" in executable
        # Forward-only — proibido pelo Migration Protocol
        assert "DROP" not in executable.upper()
        assert "ALTER COLUMN" not in executable.upper()
        assert "TRUNCATE" not in executable.upper()
        assert "DELETE FROM" not in executable.upper()
