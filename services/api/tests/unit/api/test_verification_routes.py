"""Tests: verification/routes.py — fila de verificação humana de alertas.

Isolamento de tenant (achado #14 do docs/API_CONTRACT_MAP.md): estas rotas
não recebiam tenant_id na assinatura. VerificationService.get_human_queue,
get_queue_count e human_review confirmam o vazamento/fix a nível de SQL
(services/api/tests/unit/domain/test_verification_service.py e
services/api/tests/security/test_verification_tenant_isolation.py) — os
testes aqui garantem que a rota extrai tenant_id do JWT via get_tenant_id()
e o repassa ao service em toda chamada.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
OTHER_TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
ALERT_ID = str(uuid4())
_SVC_PATH = "app.api.v1.verification.routes._svc"


def _make_token(app, tenant_id, role="operator"):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        return create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "public",
                "role": role,
                "modules": ["epi"],
            },
        )


@pytest.fixture
def auth_headers(app):
    return {"Authorization": f"Bearer {_make_token(app, TENANT_ID)}"}


@pytest.fixture
def auth_headers_other_tenant(app):
    return {"Authorization": f"Bearer {_make_token(app, OTHER_TENANT_ID)}"}


@pytest.fixture
def auth_headers_no_tenant_claim(app):
    """Token válido mas sem claim tenant_id — deve ser rejeitado com 401,
    nunca cair no fallback silencioso de tenant default (ADR-0017)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={"role": "operator", "modules": ["epi"]},
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/verification/queue
# ---------------------------------------------------------------------------

class TestGetQueue:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/verification/queue").status_code == 401

    def test_empty_queue_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["items"] == []
        assert data["data"]["count"] == 0
        assert data["data"]["total"] == 0

    def test_returns_items_with_correct_count(self, client, auth_headers):
        items = [{"id": ALERT_ID, "camera_id": "cam1"}, {"id": str(uuid4()), "camera_id": "cam2"}]
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = items
        mock_svc.get_queue_count.return_value = 2
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["count"] == 2
        assert len(data["data"]["items"]) == 2

    def test_total_vem_de_get_queue_count_nao_de_len_items(self, client, auth_headers):
        """`total` (achado do cético, item d) é a verdade do servidor —
        precisa poder DIVERGIR de `count`/`len(items)` quando `limit` corta a
        página. Sem isso, a tela não teria como saber "quanto falta de
        verdade" além do lote carregado."""
        items = [{"id": ALERT_ID, "camera_id": "cam1"}]
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = items
        mock_svc.get_queue_count.return_value = 366
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["count"] == 1
        assert data["data"]["total"] == 366

    def test_total_usa_get_queue_count_escopado_pelo_mesmo_camera_id(self, client, auth_headers):
        """Achado do cético (item d): contagem e lista tinham WHERE
        divergente porque `get_queue_count` não aceitava `camera_id` — o
        `total` de uma tela filtrada por câmera contava OUTRAS câmeras
        também. Alinhado agora: mesmo filtro para as duas chamadas."""
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            client.get(f"/api/verification/queue?camera_id={ALERT_ID}", headers=auth_headers)
        count_kwargs = mock_svc.get_queue_count.call_args[1]
        assert count_kwargs["camera_id"] == ALERT_ID

    def test_limit_capped_at_100(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue?limit=9999", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["limit"] == 100

    def test_default_limit_is_50(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["limit"] == 50

    def test_camera_id_filter_forwarded(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get(f"/api/verification/queue?camera_id={ALERT_ID}", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["camera_id"] == ALERT_ID

    def test_service_error_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        assert resp.status_code == 500

    def test_tenant_id_forwarded_from_jwt(self, client, auth_headers):
        """Achado #14: a rota deve extrair tenant_id do JWT e repassá-lo ao
        service — sem isso a fila vazava alertas needs_human de todos os
        tenants."""
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["tenant_id"] == TENANT_ID

    def test_different_tenant_forwards_its_own_tenant_id(self, client, auth_headers_other_tenant):
        """Outro tenant autenticado repassa o PRÓPRIO tenant_id, não o de TENANT_ID."""
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue", headers=auth_headers_other_tenant)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["tenant_id"] == OTHER_TENANT_ID
        assert call_kwargs["tenant_id"] != TENANT_ID

    def test_no_tenant_claim_returns_401(self, client, auth_headers_no_tenant_claim):
        """JWT sem claim tenant_id não pode cair em fallback silencioso (ADR-0017)."""
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers_no_tenant_claim)
        assert resp.status_code == 401
        mock_svc.get_human_queue.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/verification/queue/count
# ---------------------------------------------------------------------------

class TestQueueCount:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/verification/queue/count").status_code == 401

    def test_returns_count(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 7
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["count"] == 7

    def test_zero_count(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.get_json()["data"]["count"] == 0

    def test_service_error_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.status_code == 500

    def test_tenant_id_forwarded_from_jwt(self, client, auth_headers):
        """Achado #14: contagem deve ser escopada ao tenant do JWT, nunca global."""
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue/count", headers=auth_headers)
        call_kwargs = mock_svc.get_queue_count.call_args[1]
        assert call_kwargs["tenant_id"] == TENANT_ID

    def test_no_tenant_claim_returns_401(self, client, auth_headers_no_tenant_claim):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers_no_tenant_claim)
        assert resp.status_code == 401
        mock_svc.get_queue_count.assert_not_called()

    def test_camera_id_filter_forwarded(self, client, auth_headers):
        """Endpoint dedicado também aceita `camera_id`, mesma semântica de
        `/queue` — achado do cético (item d): antes, só a lista filtrava."""
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            client.get(f"/api/verification/queue/count?camera_id={ALERT_ID}", headers=auth_headers)
        call_kwargs = mock_svc.get_queue_count.call_args[1]
        assert call_kwargs["camera_id"] == ALERT_ID


# ---------------------------------------------------------------------------
# POST /api/verification/<alert_id>/review
# ---------------------------------------------------------------------------

class TestReviewAlert:

    def test_no_token_returns_401(self, client):
        resp = client.post(
            f"/api/verification/{ALERT_ID}/review",
            json={"verdict": "approve"},
        )
        assert resp.status_code == 401

    def test_invalid_verdict_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "invalid"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_missing_verdict_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_approve_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 1
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["verdict"] == "approve"
        assert data["data"]["alert_id"] == ALERT_ID

    def test_reject_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 1
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "reject"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["verdict"] == "reject"

    def test_not_found_or_already_reviewed_returns_404(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_value_error_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.side_effect = ValueError("Invalid alert state")
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_generic_exception_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "reject"},
                headers=auth_headers,
            )
        assert resp.status_code == 500

    def test_tenant_id_forwarded_from_jwt(self, client, auth_headers):
        """Achado #14: review deve escopar o UPDATE ao tenant do JWT — sem
        isso um operador podia aprovar/rejeitar alerta de outro tenant."""
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 1
        with patch(_SVC_PATH, mock_svc):
            client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        call_kwargs = mock_svc.human_review.call_args[1]
        assert call_kwargs["tenant_id"] == TENANT_ID

    def test_no_tenant_claim_returns_401(self, client, auth_headers_no_tenant_claim):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers_no_tenant_claim,
            )
        assert resp.status_code == 401
        mock_svc.human_review.assert_not_called()

    def test_cross_tenant_review_returns_404_not_200(self, client, auth_headers_other_tenant):
        """Simula o comportamento real pós-fix: o service (VerificationService.human_review,
        coberto em test_verification_service.py / test_verification_tenant_isolation.py) inclui
        `tenant_id` no WHERE do UPDATE; um alerta de outro tenant nunca bate a condição,
        rowcount fica 0 e a rota mapeia isso para 404 — nunca 200 (achado #14).
        """
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 0  # tenant_id no WHERE não bateu
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers_other_tenant,
            )
        assert resp.status_code == 404
        call_kwargs = mock_svc.human_review.call_args[1]
        assert call_kwargs["tenant_id"] == OTHER_TENANT_ID
