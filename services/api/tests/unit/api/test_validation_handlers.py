"""
Tests: validate_frame_handler e get_frame_validation_stats_handler (item-21).

Cobre os dois handlers de validação humana de frames:
- validate_frame_handler: marca frame como validado
- get_frame_validation_stats_handler: retorna contagem de frames validados

Usa Flask test client com JWT e mocks para repositório.
"""
import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(app, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        return create_access_token(
            identity=str(uid),
            additional_claims={"role": "operator"},
        ), uid


def _mock_frame(is_annotated=True):
    return {
        "id": uuid4(),
        "is_annotated": is_annotated,
        "is_validated": False,
    }


def _mock_updated_frame():
    return {
        "id": uuid4(),
        "is_validated": True,
        "validated_at": datetime.datetime(2026, 1, 1, 12, 0, 0),
    }


# ---------------------------------------------------------------------------
# Tests: validate_frame_handler
# ---------------------------------------------------------------------------

class TestValidateFrameHandler:

    def test_validate_annotated_frame_returns_200(self, client, app):
        """Frame anotado deve ser marcado como validado com sucesso."""
        frame_id = uuid4()
        token, user_id = _make_token(app)
        updated = _mock_updated_frame()

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id_and_user.return_value = _mock_frame(is_annotated=True)
            mock_repo.mark_validated.return_value = updated

            res = client.post(
                f"/api/training/frames/{frame_id}/validate",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["frame_id"] == str(frame_id)
        assert data["validated_at"] == "2026-01-01T12:00:00"

    def test_validate_frame_not_found_raises_404(self, client, app):
        """Frame inexistente ou não pertencente ao usuário deve retornar 404."""
        frame_id = uuid4()
        token, user_id = _make_token(app)

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id_and_user.return_value = None

            res = client.post(
                f"/api/training/frames/{frame_id}/validate",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 404

    def test_validate_unannotated_frame_returns_400(self, client, app):
        """Frame não anotado deve retornar 400 (precisa ser anotado antes)."""
        frame_id = uuid4()
        token, user_id = _make_token(app)

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id_and_user.return_value = _mock_frame(is_annotated=False)

            res = client.post(
                f"/api/training/frames/{frame_id}/validate",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        data = res.get_json()
        assert "anotado" in data.get("message", "").lower() or "anotado" in str(data).lower()

    def test_validate_frame_no_jwt_returns_401(self, client):
        """Sem JWT deve retornar 401 ou 422."""
        res = client.post(f"/api/training/frames/{uuid4()}/validate")
        assert res.status_code in (401, 422)

    def test_validate_frame_mark_validated_called_with_correct_ids(self, client, app):
        """mark_validated deve ser chamado com frame_id e user_id corretos."""
        frame_id = uuid4()
        token, user_id = _make_token(app)
        updated = _mock_updated_frame()

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id_and_user.return_value = _mock_frame(is_annotated=True)
            mock_repo.mark_validated.return_value = updated

            client.post(
                f"/api/training/frames/{frame_id}/validate",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_args = mock_repo.mark_validated.call_args[0]
        assert str(call_args[0]) == str(frame_id)
        assert str(call_args[1]) == str(user_id)


# ---------------------------------------------------------------------------
# Tests: get_frame_validation_stats_handler
# ---------------------------------------------------------------------------

class TestGetFrameValidationStatsHandler:

    def test_returns_stats_for_video(self, client, app):
        """Deve retornar estatísticas de validação de um vídeo."""
        video_id = uuid4()
        token, user_id = _make_token(app)
        expected_stats = {"annotated": 10, "validated": 7, "total": 15}

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.count_validated.return_value = expected_stats

            res = client.get(
                f"/api/training/videos/{video_id}/validation-stats",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["stats"]["validated"] == 7

    def test_stats_no_jwt_returns_401(self, client):
        """Sem JWT deve retornar 401 ou 422."""
        res = client.get(f"/api/training/videos/{uuid4()}/validation-stats")
        assert res.status_code in (401, 422)

    def test_stats_count_validated_called_with_correct_ids(self, client, app):
        """count_validated deve ser chamado com video_id e user_id corretos."""
        video_id = uuid4()
        token, user_id = _make_token(app)

        with patch("app.api.v1.training.validation_handlers.get_current_user_id", return_value=user_id), \
             patch("app.api.v1.training.validation_handlers.DatabasePool") as mock_pool_cls, \
             patch("app.api.v1.training.validation_handlers.FrameRepository") as mock_repo_cls:
            mock_pool_cls.get_instance.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.count_validated.return_value = {"annotated": 0, "validated": 0}

            client.get(
                f"/api/training/videos/{video_id}/validation-stats",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_args = mock_repo.count_validated.call_args[0]
        assert str(call_args[0]) == str(video_id)
        assert str(call_args[1]) == str(user_id)
