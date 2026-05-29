"""
Regression tests — Sprint 0.6 BLOCO 1: operations module schema repair.

Migration 038 had two errors:
  1. camera_id INTEGER (project standard is UUID)
  2. REFERENCES ip_cameras(id) (table renamed to cameras in 013)

Migration 047 repairs both. Code (route + repository + frontend type)
must be aligned with UUID semantics.
"""
import inspect
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "migrations"


class TestMigration047Structure:
    """047_operations_repair.sql must define operations + operation_results with UUID FK."""

    def _read_047(self) -> str:
        path = MIGRATIONS_DIR / "047_operations_repair.sql"
        assert path.exists(), f"Migration 047 not found at {path}"
        return path.read_text()

    def test_047_creates_operations_table(self):
        sql = self._read_047()
        assert "CREATE TABLE IF NOT EXISTS operations" in sql

    def test_047_creates_operation_results_table(self):
        sql = self._read_047()
        assert "CREATE TABLE IF NOT EXISTS operation_results" in sql

    def test_047_uses_uuid_for_camera_id(self):
        sql = self._read_047()
        assert "camera_id   UUID" in sql or "camera_id UUID" in sql, (
            "camera_id must be UUID, not INTEGER (project standard)"
        )

    def test_047_references_cameras_not_ip_cameras(self):
        sql = self._read_047()
        assert "REFERENCES cameras(id)" in sql
        assert "ip_cameras" not in sql, "Must reference cameras, not deprecated ip_cameras"

    def test_047_is_idempotent(self):
        sql = self._read_047()
        assert "CREATE TABLE IF NOT EXISTS operations" in sql
        assert "CREATE TABLE IF NOT EXISTS operation_results" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql


class TestOperationsRouteAcceptsUuid:
    """Flask route must not use <int:camera_id> converter — would reject UUIDs."""

    def test_route_does_not_use_int_converter_for_camera_id(self):
        import app.api.v1.operations.routes as ops

        source = inspect.getsource(ops)
        assert "<int:camera_id>" not in source, (
            "Route must accept UUID camera_id, not int. "
            "Found <int:camera_id> — would reject UUIDs as 404."
        )

    def test_route_uses_str_typed_camera_id(self):
        import app.api.v1.operations.routes as ops

        source = inspect.getsource(ops)
        assert "camera_id: str" in source, (
            "camera_id type hint must be str (UUID), not int"
        )
        assert "def list_camera_operations(camera_id: int)" not in source
        assert "def create_operation(camera_id: int)" not in source


class TestOperationRepositoryTypes:
    """OperationRepository signatures must accept str (UUID) camera_id."""

    def test_repository_methods_use_str_camera_id(self):
        from app.infrastructure.database.repositories.operation_repository import (
            OperationRepository,
        )

        source = inspect.getsource(OperationRepository)
        # No legacy int type hints for camera_id
        assert "camera_id: int" not in source, (
            "OperationRepository must use camera_id: str (UUID), not int"
        )
        # And the methods we care about must accept str
        assert "camera_id: str" in source
