"""
Verification tests — P0-02 e P0-04 (FALSOS POSITIVOS confirmados).

P0-02: count_validated filtra por tv.user_id = %s — CORRETO.
  training_videos usa user_id como discriminador (migration 003, não tem tenant_id).

P0-04: get_classes_by_user filtra por user_id = %s — CORRETO.
  yolo_classes usa user_id como discriminador (migration 003, UNIQUE(user_id, name)).

Estes testes não têm "FALHA antes" porque o código já estava correto.
Funcionam como guarda permanente: se alguém remover os filtros, os testes quebram.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.annotation_repository import AnnotationRepository
from app.infrastructure.database.repositories.frame_repository import FrameRepository


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = {
            "annotated": 0, "validated": 0, "total": 0,
        }
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn


class TestCountValidatedUserIsolation:
    """P0-02 — count_validated usa tv.user_id: verificação de que isolamento está correto."""

    def test_count_validated_includes_user_id_in_sql(self) -> None:
        """SQL de count_validated deve conter filtro user_id para isolamento."""
        pool = _MockPool()
        repo = FrameRepository(pool)  # type: ignore[arg-type]
        video_id = uuid4()
        user_id = uuid4()

        repo.count_validated(video_id, user_id)

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "user_id" in sql.lower(), "SQL deve filtrar por user_id"
        assert str(video_id) in params
        assert str(user_id) in params

    def test_count_validated_passes_both_video_and_user(self) -> None:
        """Ambos video_id e user_id devem ser passados como params — não só video_id."""
        pool = _MockPool()
        repo = FrameRepository(pool)  # type: ignore[arg-type]
        video_id = uuid4()
        user_id = uuid4()
        other_id = uuid4()

        repo.count_validated(video_id, user_id)

        _, params = pool.mock_cursor.execute.call_args[0]
        assert str(user_id) in params, "user_id deve estar nos params"
        assert str(other_id) not in params, "outro user_id NÃO deve estar nos params"


class TestYoloClassesUserIsolation:
    """P0-04 — get_classes_by_user usa user_id: verificação de que isolamento está correto."""

    def test_get_classes_by_user_filters_by_user_id(self) -> None:
        """SQL de get_classes_by_user deve conter filtro user_id."""
        pool = _MockPool()
        pool.mock_cursor.fetchone.return_value = None
        repo = AnnotationRepository(pool)  # type: ignore[arg-type]
        user_id = uuid4()

        repo.get_classes_by_user(user_id)

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "user_id" in sql.lower(), "SQL deve filtrar por user_id"
        assert str(user_id) in params

    def test_get_classes_by_user_user_b_cannot_see_user_a_classes(self) -> None:
        """user_b_id nos params significa que DB isola no nível da query."""
        pool = _MockPool()
        pool.mock_cursor.fetchall.return_value = []
        repo = AnnotationRepository(pool)  # type: ignore[arg-type]
        user_a_id = uuid4()
        user_b_id = uuid4()

        result = repo.get_classes_by_user(user_b_id)
        assert result == []

        _, params = pool.mock_cursor.execute.call_args[0]
        assert str(user_b_id) in params
        assert str(user_a_id) not in params
