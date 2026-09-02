"""
Tests: POST /api/v1/quality/training/jobs — gate training:approve (achado
irmão do mutirão de segurança).

Antes desta task, `create_training_job` (services/api/app/api/v1/quality/
routes.py) não tinha NENHUM decorator de rota — nem @jwt_required() — só
chamava `_require_jwt()` dentro do corpo, que autentica mas não checa papel.
Qualquer usuário autenticado disparava treino real (GPU paga) via módulo
quality, mesmo buraco já fechado no irmão EPI
(training/routes.py::create_job, ver TestTrainingJobsPlatformGate em
tests/integration/test_authenticated_routes.py).

Falha-antes/passa-depois: sem @require_training_role("approve") na rota,
`test_create_job_denied_for_non_platform_role` passaria (201) em vez de 403
— mutação provada manualmente (remover o decorator localmente e rodar este
arquivo torna os 403 em 201/500).
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_TENANT_SCHEMA = "tenant_rvb"
_NAO_PLATAFORMA = ["admin", "trainer", "operator", "analyst", "viewer"]


def _pool_with_cursor(mock_cursor: MagicMock) -> MagicMock:
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _role_headers(app, role: str) -> dict[str, str]:
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": str(uuid4()),
                "tenant_schema": _TENANT_SCHEMA,
                "role": role,
                "modules": ["quality"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _post_job(client, headers):
    cur = MagicMock()
    cur.fetchone.return_value = {"id": str(uuid4()), "status": "queued"}
    pool = _pool_with_cursor(cur)
    with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp, \
         patch("app.core.auth._has_training_override", return_value=False), \
         patch(
             "app.infrastructure.queue.tasks.quality_training.run_quality_training_pipeline.delay"
         ) as mock_delay:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/quality/training/jobs",
            json={"name": "job-teste", "source_video_r2_key": "videos/x.mp4"},
            headers=headers,
        )
    return resp, mock_delay


class TestCreateQualityTrainingJobRequiresTrainingApprove:

    @pytest.mark.parametrize("role", _NAO_PLATAFORMA)
    def test_create_job_denied_for_non_platform_role(self, app, client, role) -> None:
        resp, mock_delay = _post_job(client, _role_headers(app, role))
        assert resp.status_code == 403, resp.get_json()
        mock_delay.assert_not_called()

    def test_create_job_still_works_for_superadmin(self, app, client) -> None:
        """Não quebrar o caminho legítimo — a Logikos treina como superadmin."""
        resp, mock_delay = _post_job(client, _role_headers(app, "superadmin"))
        assert resp.status_code == 201, resp.get_json()
        mock_delay.assert_called_once()

    def test_create_job_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/v1/quality/training/jobs",
            json={"name": "job-teste", "source_video_r2_key": "videos/x.mp4"},
        )
        assert resp.status_code == 401
