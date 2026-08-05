"""
Tests: FrameRepository — uncovered methods.

Covers: get_pre_annotations, get_annotated_by_video, get_by_id_and_user,
mark_validated, count_validated.
"""
from contextlib import contextmanager
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.frame_repository import FrameRepository


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return FrameRepository(_pool_with_cursor(cur)), cur


class TestGetPreAnnotations:

    def test_returns_annotations_list(self):
        frame_id = uuid4()
        annotations = [{"x": 10, "y": 20, "label": "helmet"}]
        cur = MagicMock()
        cur.fetchone.return_value = {"pre_annotations": annotations}
        repo, _ = _repo(cur)
        result = repo.get_pre_annotations(frame_id)
        assert result == annotations

    def test_returns_none_when_frame_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_pre_annotations(uuid4()) is None

    def test_returns_none_when_pre_annotations_absent(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"pre_annotations": None}
        repo, _ = _repo(cur)
        assert repo.get_pre_annotations(uuid4()) is None

    def test_frame_id_in_params(self):
        frame_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_pre_annotations(frame_id)
        params = cur.execute.call_args[0][1]
        assert str(frame_id) in params


class TestGetAnnotatedByVideo:

    def test_returns_annotated_frames(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"id": "f-1", "is_annotated": True, "annotation_count": 3},
        ]
        repo, _ = _repo(cur)
        result = repo.get_annotated_by_video(uuid4(), uuid4())
        assert len(result) == 1
        assert result[0]["is_annotated"] is True

    def test_video_id_and_user_id_in_params(self):
        video_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_annotated_by_video(video_id, user_id)
        params = cur.execute.call_args[0][1]
        assert str(video_id) in params
        assert str(user_id) in params

    def test_query_joins_training_videos(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_annotated_by_video(uuid4(), uuid4())
        query = cur.execute.call_args[0][0]
        assert "training_videos" in query


class TestGetByIdAndUser:

    def test_returns_frame_when_owner_matches(self):
        frame_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "is_annotated": False}
        repo, _ = _repo(cur)
        result = repo.get_by_id_and_user(frame_id, uuid4(), uuid4())
        assert result["id"] == str(frame_id)

    def test_returns_none_when_not_found_or_wrong_owner(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_by_id_and_user(uuid4(), uuid4(), uuid4()) is None

    def test_frame_user_and_tenant_in_params(self):
        frame_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_by_id_and_user(frame_id, user_id, tenant_id)
        params = cur.execute.call_args[0][1]
        assert str(frame_id) in params
        assert str(user_id) in params
        assert str(tenant_id) in params

    def test_uses_left_join_with_tenant_fallback_for_frames_without_video(self):
        """Achado da validacao E2E Fase A: o JOIN original era INNER contra
        training_videos -- frame sem video (upload/auto/nvr, video_id NULL)
        nunca batia, entao save_annotations quebrava pra 100% das imagens
        enviadas via upload (WS-A2). Fix: LEFT JOIN + fallback por tenant."""
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "video_id": None}
        repo, cur = _repo(cur)
        result = repo.get_by_id_and_user(frame_id, user_id, uuid4())
        assert result is not None
        query = cur.execute.call_args[0][0]
        assert "LEFT JOIN" in query
        assert "tf.video_id IS NULL" in query
        assert "tenant_id" in query

    def test_ownership_uses_request_tenant_not_home_tenant_subquery(self):
        """REGRESSAO (contexto assumido de superadmin, #302): a posse de
        frame sem video usa o tenant do CONTEXTO da requisicao (bind param),
        NAO o tenant de casa do user via `(SELECT tenant_id FROM users WHERE
        id=..)`. Sob contexto assumido, o subquery voltava o tenant de casa
        (!= tenant alvo) e todo frame NVR/upload dava 404 no anotador embora
        aparecesse na galeria (que ja escopa por get_tenant_id()).

        Fail-before/pass-after: no codigo antigo a query continha o subquery
        e o tenant do contexto nao era param -> ambos os asserts falhavam."""
        frame_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_by_id_and_user(frame_id, user_id, tenant_id)
        query = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        # tenant do contexto entra como bind param
        assert str(tenant_id) in params
        # e NAO e derivado do tenant de casa do user dentro do SQL
        assert "SELECT tenant_id FROM users" not in query


class TestMarkValidated:

    def test_returns_validated_frame(self):
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "validated_at": "2026-01-01"}
        repo, _ = _repo(cur)
        result = repo.mark_validated(frame_id, user_id, uuid4())
        assert result["validated_at"] == "2026-01-01"

    def test_returns_none_when_not_owned(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.mark_validated(uuid4(), uuid4(), uuid4()) is None

    def test_user_id_twice_and_tenant_once_in_params(self):
        frame_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.mark_validated(frame_id, user_id, tenant_id)
        params = cur.execute.call_args[0][1]
        # user_id: validated_by + check de dono do video. O 3o slot (posse de
        # frame sem video) agora e o tenant do CONTEXTO da requisicao, nao mais
        # o tenant de casa derivado do user (fix contexto assumido, #302).
        assert params.count(str(user_id)) == 2
        assert str(tenant_id) in params
        assert "SELECT tenant_id FROM users" not in cur.execute.call_args[0][0]

    def test_frame_without_video_validated_via_tenant_ownership(self):
        """Frame de upload (video_id NULL) e validado via tenant do CONTEXTO
        da requisicao, nao via training_videos (fix: JOIN original nunca batia
        pra esse caso) nem via tenant de casa do user (fix contexto assumido)."""
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "validated_at": "2026-01-01"}
        repo, cur = _repo(cur)
        result = repo.mark_validated(frame_id, user_id, uuid4())
        assert result is not None
        query = cur.execute.call_args[0][0]
        assert "tf.video_id IS NULL" in query
        assert "tenant_id" in query


class TestCountValidated:

    def test_returns_counts_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": 5, "validated": 3, "total": 10}
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result["annotated"] == 5
        assert result["validated"] == 3
        assert result["total"] == 10

    def test_returns_zeros_when_no_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result == {"annotated": 0, "validated": 0, "total": 0}

    def test_handles_none_values_from_db(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": None, "validated": None, "total": 5}
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result["annotated"] == 0
        assert result["validated"] == 0

    def test_both_ids_in_params(self):
        video_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": 0, "validated": 0, "total": 0}
        repo, cur = _repo(cur)
        repo.count_validated(video_id, user_id)
        params = cur.execute.call_args[0][1]
        assert str(video_id) in params
        assert str(user_id) in params

    def test_query_joins_training_videos_for_ownership(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.count_validated(uuid4(), uuid4())
        query = cur.execute.call_args[0][0]
        assert "training_videos" in query


class TestListUnlabeledByUncertainty:
    """WS-B2 — fila de active learning: COM e SEM score, intercalados.

    Era `ORDER BY model_confidence ASC NULLS LAST` puro. A justificativa
    (frame sem score não é "mais urgente" que um de baixa confiança conhecida)
    é válida, mas num pool MISTO afundava o dado novo pra sempre: frame de
    NVR/upload nunca tem score e ficava eternamente atrás de qualquer frame
    `auto`. Isso trava o bootstrap de cliente novo, onde a coleta do gravador
    É o dataset e ainda não existe modelo pra pontuar nada.
    """

    def test_interleaves_scored_and_unscored(self):
        """1:1 enquanto os dois lados têm frame — o dado novo não afunda."""
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [{"id": "s1", "model_confidence": 0.2}, {"id": "s2", "model_confidence": 0.4}],
            [{"id": "u1", "model_confidence": None}, {"id": "u2", "model_confidence": None}],
        ]
        repo, _ = _repo(cur)
        result = repo.list_unlabeled_by_uncertainty(uuid4(), "epi", limit=20)
        assert [r["id"] for r in result] == ["s1", "u1", "s2", "u2"]

    def test_only_scored_behaves_like_before(self):
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [{"id": "s1", "model_confidence": 0.1}, {"id": "s2", "model_confidence": 0.9}],
            [],
        ]
        repo, _ = _repo(cur)
        result = repo.list_unlabeled_by_uncertainty(uuid4(), "epi", limit=20)
        assert [r["id"] for r in result] == ["s1", "s2"]

    def test_only_unscored_returns_all(self):
        """Caso do bootstrap (RVB): nenhum frame tem score ainda."""
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [],
            [{"id": "u1", "model_confidence": None}, {"id": "u2", "model_confidence": None}],
        ]
        repo, _ = _repo(cur)
        result = repo.list_unlabeled_by_uncertainty(uuid4(), "epi", limit=20)
        assert [r["id"] for r in result] == ["u1", "u2"]

    def test_respects_limit_across_both_buckets(self):
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [{"id": f"s{i}", "model_confidence": 0.1} for i in range(5)],
            [{"id": f"u{i}", "model_confidence": None} for i in range(5)],
        ]
        repo, _ = _repo(cur)
        result = repo.list_unlabeled_by_uncertainty(uuid4(), "epi", limit=3)
        assert len(result) == 3

    def test_both_queries_filter_unannotated_and_split_by_score(self):
        cur = MagicMock()
        cur.fetchall.side_effect = [[], []]
        repo, cur = _repo(cur)
        repo.list_unlabeled_by_uncertainty(uuid4(), "epi", limit=20)
        queries = [c[0][0] for c in cur.execute.call_args_list]
        assert all("tf.is_annotated = FALSE" in q for q in queries)
        assert any("model_confidence IS NOT NULL" in q for q in queries)
        assert any("model_confidence IS NULL" in q for q in queries)

    def test_params_include_tenant_module_and_limit(self):
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchall.side_effect = [[], []]
        repo, cur = _repo(cur)
        repo.list_unlabeled_by_uncertainty(tenant_id, "quality", limit=7)
        for call in cur.execute.call_args_list:
            assert call[0][1] == (str(tenant_id), "quality", 7)
