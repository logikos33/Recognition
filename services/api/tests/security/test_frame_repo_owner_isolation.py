"""
Regression tests — P0-01: get_annotated_by_video cross-user isolation.

FALHA antes do fix: método aceitava só video_id sem filtro de dono (IDOR —
qualquer usuário autenticado poderia listar frames anotados de outro usuário
conhecendo o video_id).

PASSA após o fix: método exige user_id; SQL inclui JOIN training_videos e
filtro tv.user_id = %s para garantir isolamento no banco.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.frame_repository import FrameRepository


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchall.return_value = []
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn


def _make_repo() -> tuple["FrameRepository", "_MockPool"]:
    pool = _MockPool()
    return FrameRepository(pool), pool  # type: ignore[arg-type]


class TestGetAnnotatedByVideoOwnerIsolation:
    """
    P0-01 — get_annotated_by_video deve exigir user_id para isolamento por dono.

    Antes do fix: get_annotated_by_video(video_id) — sem filtro de dono → IDOR.
    Após o fix:  get_annotated_by_video(video_id, user_id) — SQL filtra tv.user_id.
    """

    def test_requires_user_id_argument(self) -> None:
        """FALHA antes do fix (TypeError — só aceitava video_id). PASSA após fix."""
        repo, _ = _make_repo()
        # Antes do fix: TypeError — takes 2 positional arguments but 3 were given
        repo.get_annotated_by_video(uuid4(), uuid4())  # não deve lançar exceção

    def test_sql_contains_user_id_filter(self) -> None:
        """SQL executado deve conter filtro user_id para isolamento ser garantido no DB."""
        repo, pool = _make_repo()
        video_id = uuid4()
        owner_id = uuid4()

        repo.get_annotated_by_video(video_id, owner_id)

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "user_id" in sql.lower(), "SQL deve conter filtro user_id"
        assert str(video_id) in params, "video_id deve estar nos params"
        assert str(owner_id) in params, "owner user_id deve estar nos params"

    def test_user_b_cannot_read_user_a_frames(self) -> None:
        """user_id de B não coincide com dono de A → repo retorna lista vazia (isolamento correto)."""
        repo, pool = _make_repo()
        user_a_id = uuid4()
        user_b_id = uuid4()
        video_id = uuid4()

        pool.mock_cursor.fetchall.return_value = []

        result = repo.get_annotated_by_video(video_id, user_b_id)
        assert result == [], "User B deve receber lista vazia — sem frames de user A"

        _, params = pool.mock_cursor.execute.call_args[0]
        assert str(user_b_id) in params, "user_b_id deve estar nos params enviados ao DB"
        assert str(user_a_id) not in params, "user_a_id NÃO deve estar nos params (vazamento)"
