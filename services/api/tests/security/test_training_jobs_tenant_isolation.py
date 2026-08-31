"""
Segurança — GET /api/training/jobs/<id>/status e /progress escopados pelo
tenant do JWT (C-01).

Achado (b), grupo TREINO/MODELOS (P0):
  - /status devolvia training_jobs de QUALQUER tenant (TrainingService.get_job →
    get_job_by_id sem tenant), incluindo callback_token (segredo da GPU);
  - /progress lia o Redis `training_progress:{job_id}` sem validar posse.

Fix: posse por tenant_id do JWT (get_job_for_tenant → 404) antes de devolver
ou ler qualquer coisa; callback_token nunca sai na resposta.

Protocolo falha-antes/passa-depois: B em job de A → 404 (Redis nem consultado);
tenant dono → 200 sem callback_token.
"""
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from app.domain.services.training_service import TrainingService

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
JOB_ID = "66666666-6666-6666-6666-666666666666"

_SVC_PATH = "app.api.v1.training.job_handlers.get_training_service"


def _auth(app, role: str, tenant_id: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _job_row(tenant_id: str = TENANT_A) -> dict:
    return {
        "id": JOB_ID,
        "user_id": str(uuid4()),
        "tenant_id": tenant_id,
        "status": "running",
        "progress": 40,
        "callback_token": "segredo-da-gpu",
    }


# ---------------------------------------------------------------------------
# (b) GET /api/training/jobs/<id>/status  e  /progress
# ---------------------------------------------------------------------------

@pytest.fixture()
def training_repo():
    """TrainingService REAL com repositório mockado (padrão do mutirão)."""
    repo = MagicMock()
    repo.get_job_by_id.return_value = _job_row()          # caminho antigo (sem tenant)
    repo.get_job_for_tenant.return_value = None           # job é de A, JWT é de B
    with patch(_SVC_PATH, return_value=TrainingService(repo)):
        yield repo


class TestJobStatusTenantIsolation:
    def test_tenant_b_cannot_read_job_status_of_tenant_a(self, app, client, training_repo):
        """FALHA-ANTES: 200 com o job inteiro (callback_token incluso).
        PASSA-DEPOIS: 404."""
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/status",
            headers=_auth(app, "admin", TENANT_B),
        )
        assert resp.status_code == 404, resp.get_json()
        assert "segredo-da-gpu" not in resp.get_data(as_text=True)

    def test_owner_tenant_reads_status_without_callback_token(self, app, client, training_repo):
        training_repo.get_job_for_tenant.return_value = _job_row()
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/status",
            headers=_auth(app, "operator", TENANT_A),
        )
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()["data"]
        assert body["id"] == JOB_ID
        assert "callback_token" not in body
        args = training_repo.get_job_for_tenant.call_args[0]
        assert str(args[0]) == JOB_ID
        assert args[1] == TENANT_A


class TestListJobsCallbackTokenLeak:
    """(iii) GET /api/training/jobs — achado de segurança do mutirão
    (ESTADO-F5): a listagem usa `SELECT *` (get_jobs_by_user) e devolvia o
    callback_token de CADA job na resposta — get_job_status_handler/
    stop_job_handler já filtravam, list_jobs_handler não.

    Protocolo falha-antes/passa-depois: FALHA-ANTES = 200 com
    "segredo-da-gpu" no corpo; PASSA-DEPOIS = 200 sem o token.
    """

    def test_list_jobs_response_never_contains_callback_token(self, app, client):
        repo = MagicMock()
        repo.get_jobs_by_user.return_value = [
            _job_row(), _job_row(tenant_id=TENANT_A),
        ]
        with patch(_SVC_PATH, return_value=TrainingService(repo)):
            resp = client.get(
                "/api/training/jobs", headers=_auth(app, "operator", TENANT_A)
            )
        assert resp.status_code == 200, resp.get_json()
        body_text = resp.get_data(as_text=True)
        assert "segredo-da-gpu" not in body_text
        for job in resp.get_json()["data"]:
            assert "callback_token" not in job


class TestCurrentJobStatusCallbackTokenLeak:
    """Mesmo achado, rota GET /api/training/jobs/current/status
    (get_current_running_job também usa SELECT * — mesmo vazamento)."""

    def test_current_job_status_response_never_contains_callback_token(
        self, app, client
    ):
        repo = MagicMock()
        repo.get_current_running_job.return_value = _job_row()
        with patch(_SVC_PATH, return_value=TrainingService(repo)):
            resp = client.get(
                "/api/training/jobs/current/status",
                headers=_auth(app, "operator", TENANT_A),
            )
        assert resp.status_code == 200, resp.get_json()
        body_text = resp.get_data(as_text=True)
        assert "segredo-da-gpu" not in body_text
        assert "callback_token" not in resp.get_json()["data"]["job"]


class TestJobProgressTenantIsolation:
    @pytest.fixture()
    def redis_from_url(self):
        r = MagicMock()
        r.get.return_value = json.dumps({"job_id": JOB_ID, "progress": 40})
        r.exists.return_value = 0  # blocklist de JWT (session_service) usa o mesmo from_url
        with patch("redis.from_url", return_value=r):
            yield r

    def test_tenant_b_cannot_read_progress_of_tenant_a(
        self, app, client, training_repo, redis_from_url
    ):
        """FALHA-ANTES: 200 lendo o Redis direto (sem posse).
        PASSA-DEPOIS: 404 e o Redis nem é consultado."""
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/progress",
            headers=_auth(app, "admin", TENANT_B),
        )
        assert resp.status_code == 404, resp.get_json()
        redis_from_url.get.assert_not_called()

    def test_owner_tenant_reads_progress(self, app, client, training_repo, redis_from_url):
        training_repo.get_job_for_tenant.return_value = _job_row()
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/progress",
            headers=_auth(app, "operator", TENANT_A),
        )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["data"]["progress"] == 40
        redis_from_url.get.assert_called_once_with(f"training_progress:{JOB_ID}")


class TestTrainingRepositoryGetJobForTenant:
    """SQL do repositório filtra por tenant_id (nunca só por id)."""

    def test_sql_filters_by_tenant_id(self):
        from contextlib import contextmanager
        from uuid import UUID

        from app.infrastructure.database.repositories.training_repository import (
            TrainingRepository,
        )

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cursor

        class _Pool:
            @contextmanager
            def get_connection(self):  # type: ignore[no-untyped-def]
                yield conn

        TrainingRepository(_Pool()).get_job_for_tenant(UUID(JOB_ID), TENANT_B)  # type: ignore[arg-type]
        query, params = cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert params == (JOB_ID, TENANT_B)


class TestSuperadminAssumedContext:
    """Override por role preservado: superadmin em contexto assumido (claims
    tenant_ctx/impersonated_by, tenant_id = tenant alvo) lê o job do tenant
    do CONTEXTO; o tenant efetivo é sempre o do JWT (get_tenant_id), nunca
    bypass por role — superadmin no contexto de B não vê job de A (404)."""

    @staticmethod
    def _ctx_auth(app, tenant_id: str) -> dict[str, str]:
        with app.app_context():
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={
                    "tenant_id": tenant_id,
                    "tenant_schema": "tenant_test",
                    "role": "superadmin",
                    "modules": ["epi"],
                    "tenant_ctx": True,
                    "impersonated_by": str(uuid4()),
                },
            )
        return {"Authorization": f"Bearer {token}"}

    def test_superadmin_in_owner_context_reads_status(self, app, client, training_repo):
        training_repo.get_job_for_tenant.return_value = _job_row()
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/status",
            headers=self._ctx_auth(app, TENANT_A),
        )
        assert resp.status_code == 200, resp.get_json()
        assert "callback_token" not in resp.get_json()["data"]
        assert training_repo.get_job_for_tenant.call_args[0][1] == TENANT_A

    def test_superadmin_in_other_context_gets_404(self, app, client, training_repo):
        """Role superadmin NÃO é bypass de tenant: contexto B → job de A → 404."""
        resp = client.get(
            f"/api/training/jobs/{JOB_ID}/status",
            headers=self._ctx_auth(app, TENANT_B),
        )
        assert resp.status_code == 404, resp.get_json()
        assert training_repo.get_job_for_tenant.call_args[0][1] == TENANT_B
