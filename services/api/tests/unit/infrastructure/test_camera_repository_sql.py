"""Tests: CameraRepository SQL must target public.cameras explicitly.

Regressão do bug de cadastro em staging (2026-07-01): o INSERT usava
`cameras` sem qualificar o schema. Quando uma conexão do pool voltava com
search_path apontando para um schema de tenant ({schema}.cameras não tem
tenant_id), o INSERT falhava com "column tenant_id of relation cameras
does not exist". Toda query do CRUD principal deve mirar public.cameras.

Também cobre a coluna user_id (NOT NULL em public.cameras): o INSERT
precisa incluí-la ou a criação falha com violação de NOT NULL.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.camera_repository import CameraRepository


class MockPool:
    """Mock leve de DatabasePool com suporte a context manager."""

    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn
        self.mock_conn.commit()


def _make_repo() -> tuple[CameraRepository, MockPool]:
    pool = MockPool()
    return CameraRepository(pool), pool  # type: ignore[arg-type]


class TestCameraRepositorySchemaQualification:
    """Toda query do CameraRepository qualifica public.cameras."""

    def test_create_inserts_into_public_cameras(self) -> None:
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}

        repo.create({
            "tenant_id": uuid4(),
            "user_id": uuid4(),
            "name": "Cam",
            "host": "192.168.1.51",
        })

        sql = pool.mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO public.cameras" in sql, (
            "INSERT sem qualificar public.cameras — vulnerável a search_path "
            "de tenant vazado ({schema}.cameras não tem tenant_id)"
        )

    def test_create_includes_user_id_column(self) -> None:
        """public.cameras.user_id é NOT NULL — o INSERT precisa preenchê-la."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}
        user_id = uuid4()

        repo.create({
            "tenant_id": uuid4(),
            "user_id": user_id,
            "name": "Cam",
            "host": "192.168.1.51",
        })

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "user_id" in sql
        assert str(user_id) in params

    def test_all_queries_qualify_public_cameras(self) -> None:
        """Nenhum método do repository usa `cameras` sem schema."""
        import inspect

        import app.infrastructure.database.repositories.camera_repository as mod

        source = inspect.getsource(mod)
        for token in ("INTO cameras", "FROM cameras", "UPDATE cameras"):
            assert token not in source, (
                f"Query com '{token}' sem qualificar public. — "
                "sujeita a search_path de tenant vazado"
            )
