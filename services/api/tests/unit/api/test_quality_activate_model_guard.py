"""
Tests: POST /api/v1/quality/training/models/<id>/activate — guard de status
(task "treino não pode mentir").

Antes desta task, `activate_model` só checava que o job EXISTIA
(`SELECT id FROM quality_training_jobs WHERE id = %s`) — um job 'queued',
'running' ou 'failed' podia ser "ativado" e atribuído a câmeras, apontando
`model_quality_id` pra um treino que nunca terminou (ou terminou em erro).
Agora exige status='completed', senão 404 (nunca vaza o status real — mesmo
padrão cross-tenant/inexistente do resto da casa).

Falha-antes/passa-depois: sem o guard, `test_activate_running_job_404s` e
`test_activate_failed_job_404s` passariam (ativariam o job) em vez de 404.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

_TENANT_SCHEMA = "tenant_rvb"
_MODEL_ID = str(uuid4())
_CAMERA_ID = str(uuid4())


def _pool_with_cursor(mock_cursor: MagicMock) -> MagicMock:
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _auth_headers(app) -> dict:
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_schema": _TENANT_SCHEMA,
                "role": "admin",
                "modules": ["quality"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _activate(client, app, *, job_row: dict | None):
    cur = MagicMock()
    cur.fetchone.return_value = job_row
    pool = _pool_with_cursor(cur)
    with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            f"/api/v1/quality/training/models/{_MODEL_ID}/activate",
            json={"camera_ids": [_CAMERA_ID]},
            headers=_auth_headers(app),
        )
    return resp, cur


class TestActivateModelRequiresCompleted:
    def test_activate_completed_job_succeeds(self, client, app) -> None:
        resp, cur = _activate(
            client, app, job_row={"id": _MODEL_ID, "status": "completed"},
        )
        assert resp.status_code == 200
        # UPDATE cameras foi de fato executado (ativação seguiu em frente)
        update_calls = [
            c for c in cur.execute.call_args_list
            if "UPDATE cameras" in str(c.args[0])
        ]
        assert update_calls

    def test_activate_running_job_404s(self, client, app) -> None:
        resp, cur = _activate(
            client, app, job_row={"id": _MODEL_ID, "status": "running"},
        )
        assert resp.status_code == 404
        update_calls = [
            c for c in cur.execute.call_args_list
            if "UPDATE cameras" in str(c.args[0])
        ]
        assert update_calls == []

    def test_activate_failed_job_404s(self, client, app) -> None:
        resp, cur = _activate(
            client, app, job_row={"id": _MODEL_ID, "status": "failed"},
        )
        assert resp.status_code == 404

    def test_activate_queued_job_404s(self, client, app) -> None:
        resp, _cur = _activate(
            client, app, job_row={"id": _MODEL_ID, "status": "queued"},
        )
        assert resp.status_code == 404

    def test_activate_missing_job_404s(self, client, app) -> None:
        resp, _cur = _activate(client, app, job_row=None)
        assert resp.status_code == 404
