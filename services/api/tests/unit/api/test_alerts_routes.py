"""Tests: alerts/routes.py — list, export, detalhe, acknowledge, snapshot, stats."""
import re
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
ALERT_ID = str(uuid4())
_GET_REPO = "app.api.v1.alerts.routes._get_repo"
_GET_STORAGE = "app.infrastructure.storage.local_storage.get_storage"


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "test@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_repo(items=None, total=0, total_situacoes=None):
    repo = MagicMock()
    payload = {"items": items or [], "total": total}
    if total_situacoes is not None:
        payload["total_situacoes"] = total_situacoes
    repo.list_with_filters.return_value = payload
    return repo


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

class TestListAlerts:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code == 401

    def test_empty_result(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo()):
            resp = client.get("/api/alerts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["alerts"] == []
        assert data["data"]["total"] == 0

    def test_with_items(self, client, auth_headers):
        items = [{"id": ALERT_ID, "camera_name": "Cam-1", "acknowledged": False}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items, total=1)):
            resp = client.get("/api/alerts", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["count"] == 1
        assert data["data"]["total"] == 1

    def test_lista_entrega_verdict_e_verified_by_ao_cliente(self, client, auth_headers):
        """A coluna "Veredito humano" da lista depende DESTES dois campos.

        `verification_verdict` sozinho não distingue máquina de gente — a task
        Celery grava o mesmo 'approve'/'reject' com verified_by='claude-haiku'.
        A prova de humanidade é o prefixo 'user:' em `verified_by`.

        FALHA se alguém estreitar a projeção desta rota como `get_alert` já faz
        (ver o comentário "não vaza `tenant_id`/`verified_by`" em routes.py):
        a coluna degradaria em SILÊNCIO para "Não revisado" em todas as linhas,
        apresentando alertas julgados como não julgados.
        """
        items = [{
            "id": ALERT_ID, "camera_name": "Cam-1", "acknowledged": False,
            "verification_verdict": "reject", "verified_by": "user:u-42",
        }]
        with patch(_GET_REPO, return_value=_mock_repo(items=items, total=1)):
            resp = client.get("/api/alerts", headers=auth_headers)
        alerta = resp.get_json()["data"]["alerts"][0]
        assert alerta["verification_verdict"] == "reject"
        assert alerta["verified_by"] == "user:u-42"

    def test_pagination_params_forwarded(self, client, auth_headers):
        repo = _mock_repo(total=50)
        with patch(_GET_REPO, return_value=repo):
            client.get("/api/alerts?page=2&per_page=10", headers=auth_headers)
        call_kwargs = repo.list_with_filters.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 10

    def test_per_page_capped_at_100(self, client, auth_headers):
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            client.get("/api/alerts?per_page=9999", headers=auth_headers)
        call_kwargs = repo.list_with_filters.call_args[1]
        assert call_kwargs["limit"] == 100

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.list_with_filters.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts", headers=auth_headers)
        assert resp.status_code == 500

    def test_pages_calculated_correctly(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo(total=25)):
            resp = client.get("/api/alerts?per_page=10", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["pages"] == 3

    def test_total_situacoes_forwarded(self, client, auth_headers):
        """ux2/dedup: `total_situacoes` (rajadas) tem de sair no envelope,
        SEPARADO de `total` (linhas) — é o número que os badges de
        Eventos/Ações/sino usam para não confundir repetição com trabalho."""
        with patch(_GET_REPO, return_value=_mock_repo(total=66, total_situacoes=2)):
            resp = client.get("/api/alerts", headers=auth_headers)
        data = resp.get_json()["data"]
        assert data["total"] == 66
        assert data["total_situacoes"] == 2

    def test_total_situacoes_fallback_sem_repo_novo(self, client, auth_headers):
        """Repo/mock que ainda não manda `total_situacoes` degrada para
        `total` — nunca 500 por causa de um campo novo."""
        with patch(_GET_REPO, return_value=_mock_repo(total=9)):
            resp = client.get("/api/alerts", headers=auth_headers)
        data = resp.get_json()["data"]
        assert data["total_situacoes"] == 9


# ---------------------------------------------------------------------------
# GET /api/alerts/export
# ---------------------------------------------------------------------------

class TestExportAlerts:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts/export")
        assert resp.status_code == 401

    def test_returns_csv_content_type(self, client, auth_headers):
        items = [{"created_at": "2024-01-01", "camera_name": "C1",
                  "acknowledged": True, "violations": [{"class": "no_helmet", "confidence": 0.9}]}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_csv_has_header_row(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo()):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert b"Data" in resp.data

    def test_alert_without_violations_exports_one_row(self, client, auth_headers):
        items = [{"created_at": "2024-01-01", "camera_name": "C1",
                  "acknowledged": False, "violations": []}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 200

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.list_with_filters.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/alerts/<alert_id> — detalhe (deep-link do evento)
# ---------------------------------------------------------------------------

class TestGetAlert:
    """Detalhe de um alerta: frame inteiro + bbox real + hora de captura.

    FALHA antes do fix: a rota não existia — a tela só tinha um modal com bbox
    hardcoded (`left:20% top:15%`), igual para toda violação, e mostrava
    `created_at` (hora de gravação) no lugar de `timestamp` (hora do evento).
    """

    _ROW = {
        "id": ALERT_ID,
        "camera_id": "11111111-1111-1111-1111-111111111111",
        "camera_name": "Canal 8",
        "violations": [{"class": "Sem protetor de ouvido", "confidence": 0.76,
                        "bbox": [0.5, 0.5, 0.2, 0.4]}],
        "confidence": 0.76,
        "acknowledged": False,
        "evidence_key": "evidence/cam-1/123.jpg",
        "timestamp": datetime(2026, 8, 20, 14, 30, 0),
        "created_at": datetime(2026, 8, 20, 14, 31, 0),
        "tenant_id": TENANT_ID,
        "verified_by": USER_ID,
    }

    def test_without_token_returns_401(self, client):
        assert client.get(f"/api/alerts/{ALERT_ID}").status_code == 401

    def test_cross_tenant_returns_404_and_query_is_tenant_scoped(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 404
        repo.get_by_id.assert_called_once_with(UUID(ALERT_ID), tenant_id=TENANT_ID)

    def test_malformed_id_returns_404(self, client, auth_headers):
        with patch(_GET_REPO, return_value=MagicMock()):
            resp = client.get("/api/alerts/nao-e-uuid", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_frame_camera_capture_time_and_bbox(self, client, auth_headers):
        from app.infrastructure.storage.r2_storage import R2Storage

        repo = MagicMock()
        repo.get_by_id.return_value = dict(self._ROW)
        storage = MagicMock(spec=R2Storage)
        storage.generate_presigned_download_url.return_value = "https://r2/signed"
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        alert = resp.get_json()["data"]["alert"]
        assert alert["evidence_url"] == "https://r2/signed"
        assert alert["camera_name"] == "Canal 8"
        # hora REAL de captura vem de `timestamp`, não de created_at (14:31)
        assert alert["captured_at"].startswith("2026-08-20T14:30:00")
        # bbox chega intacto na tela — o backend não reinterpreta coordenada
        assert alert["violations"][0]["bbox"] == [0.5, 0.5, 0.2, 0.4]
        # projeção explícita: colunas internas não vazam
        assert "tenant_id" not in alert and "verified_by" not in alert

    def test_falls_back_to_created_at_when_timestamp_is_null(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id.return_value = dict(self._ROW, timestamp=None)
        storage = MagicMock()
        storage.generate_presigned_download_url.return_value = "https://r2/signed"
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        assert resp.get_json()["data"]["alert"]["captured_at"].startswith("2026-08-20T14:31:00")

    def test_storage_failure_still_returns_200(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id.return_value = dict(self._ROW)
        storage = MagicMock()
        storage.generate_presigned_download_url.side_effect = Exception("R2 down")
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["alert"]["evidence_url"] is None

    def test_repo_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 500

    def test_static_routes_still_win_over_the_dynamic_one(self, client, auth_headers):
        """/export e /stats não podem ser capturados por /<alert_id>."""
        repo = _mock_repo()
        repo.get_unacknowledged.return_value = []
        with patch(_GET_REPO, return_value=repo):
            assert client.get("/api/alerts/export", headers=auth_headers).status_code == 200
            assert client.get("/api/alerts/stats", headers=auth_headers).status_code == 200


# ---------------------------------------------------------------------------
# POST /api/alerts/<alert_id>/acknowledge
# ---------------------------------------------------------------------------

class TestAcknowledgeAlert:
    # A rota duplicada em training_bp foi removida (ADR-0041) — alerts_bp é a
    # única dona de /api/alerts/<id>/acknowledge. Tests patcham _GET_REPO.

    def test_without_token_returns_401(self, client):
        resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge")
        assert resp.status_code == 401

    def test_alert_found_returns_200(self, client, auth_headers):
        repo = MagicMock()
        repo.acknowledge.return_value = {"id": ALERT_ID, "acknowledged": True}
        with patch(_GET_REPO, return_value=repo):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_alert_not_found_returns_404(self, client, auth_headers):
        repo = MagicMock()
        repo.acknowledge.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        assert resp.status_code == 404

    def test_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.acknowledge.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/alerts/<alert_id>/snapshot — task-074 (achado #7)
# ---------------------------------------------------------------------------

class TestAlertSnapshot:
    """Isolamento de tenant no snapshot de alerta (task-074 / achado #7).

    FALHA antes do fix: a rota buscava o alerta com
    `SELECT evidence_key FROM alerts WHERE id = %s` — sem `tenant_id` — então
    qualquer tenant autenticado podia ler o snapshot (imagem de evidência) de
    um alerta de OUTRO tenant, bastando adivinhar/enumerar o `alert_id`.
    PASSA após o fix: a rota chama `repo.get_evidence_key(alert_id, tenant_id=...)`,
    que filtra por `tenant_id` no SQL — alerta de outro tenant nunca é
    encontrado e a rota responde 404 (idêntico ao caso "alerta inexistente",
    para não permitir enumeração cross-tenant).
    """

    def test_without_token_returns_401(self, client):
        resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot")
        assert resp.status_code == 401

    def test_cross_tenant_alert_returns_404(self, client, auth_headers):
        """Alerta existe mas pertence a outro tenant — repo (tenant-scoped) não acha a linha."""
        repo = MagicMock()
        repo.get_evidence_key.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404
        # Prova que a busca já nasce tenant-scoped — nunca busca só por id.
        repo.get_evidence_key.assert_called_once_with(UUID(ALERT_ID), tenant_id=TENANT_ID)

    def test_nonexistent_alert_returns_404(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404

    def test_alert_without_evidence_key_returns_404(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": None}
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404

    def test_same_tenant_alert_returns_snapshot_url(self, client, auth_headers):
        """Regressão: alerta do PRÓPRIO tenant continua funcionando normalmente."""
        from app.infrastructure.storage.r2_storage import R2Storage

        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": "evidence/cam-1/123.jpg"}
        mock_storage = MagicMock(spec=R2Storage)
        mock_storage.generate_presigned_download_url.return_value = "https://r2.example.com/signed"
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=mock_storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["snapshot_url"] == "https://r2.example.com/signed"
        repo.get_evidence_key.assert_called_once_with(UUID(ALERT_ID), tenant_id=TENANT_ID)
        mock_storage.generate_presigned_download_url.assert_called_once_with(
            "evidence/cam-1/123.jpg", ttl=3600, response_content_type="image/jpeg"
        )

    def test_local_storage_returns_400(self, client, auth_headers):
        from app.infrastructure.storage.local_storage import LocalStorage

        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": "evidence/cam-1/123.jpg"}
        mock_storage = MagicMock(spec=LocalStorage)
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=mock_storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 400

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/alerts/stats
# ---------------------------------------------------------------------------

class TestAlertStats:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts/stats")
        assert resp.status_code == 401

    def test_returns_total_and_unacknowledged(self, client, auth_headers):
        repo = MagicMock()
        repo.count_by_camera.return_value = 10
        repo.get_unacknowledged.return_value = [{"id": ALERT_ID}] * 3
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/stats?camera_id={ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["total"] == 10
        assert data["data"]["unacknowledged"] == 3

    def test_no_camera_id_returns_zero_total(self, client, auth_headers):
        repo = MagicMock()
        repo.get_unacknowledged.return_value = []
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["total"] == 0

    def test_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.count_by_camera.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/stats?camera_id={ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_parse_date_valid_iso(self):
        from app.api.v1.alerts.routes import _parse_date
        result = _parse_date("2024-01-15T10:30:00Z")
        assert result is not None

    def test_parse_date_none_returns_none(self):
        from app.api.v1.alerts.routes import _parse_date
        assert _parse_date(None) is None

    def test_parse_date_invalid_returns_none(self):
        from app.api.v1.alerts.routes import _parse_date
        assert _parse_date("not-a-date") is None

    def test_parse_bool_true_strings(self):
        from app.api.v1.alerts.routes import _parse_bool
        for s in ("true", "True", "1", "yes"):
            assert _parse_bool(s) is True

    def test_parse_bool_false_strings(self):
        from app.api.v1.alerts.routes import _parse_bool
        for s in ("false", "False", "0", "no"):
            assert _parse_bool(s) is False

    def test_parse_bool_none_returns_none(self):
        from app.api.v1.alerts.routes import _parse_bool
        assert _parse_bool(None) is None


# ---------------------------------------------------------------------------
# Datas: UM formato, com offset explícito, nas DUAS rotas
# ---------------------------------------------------------------------------

class TestDatasComOffsetExplicito:
    """A MESMA linha não pode ter duas horas.

    FALHA antes do fix: `GET /api/alerts` serializava datetime via jsonify
    (RFC 822 "…GMT") e `GET /api/alerts/<id>` via `isoformat()` de um TIMESTAMP
    naive (SEM offset) — o browser lê o segundo como hora LOCAL e o mesmo
    alerta aparecia 3h antes no detalhe (BRT = UTC−3).
    PASSA depois: as duas rotas emitem ISO 8601 UTC com sufixo Z.
    """

    # Regex do contrato: qualquer data sem offset (o defeito) reprova aqui.
    _ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

    _CAPTURA = datetime(2026, 8, 20, 14, 30, 0)   # naive, como o TIMESTAMP do banco
    _GRAVACAO = datetime(2026, 8, 20, 14, 31, 0)

    def _row(self):
        return {
            "id": ALERT_ID,
            "camera_id": "11111111-1111-1111-1111-111111111111",
            "camera_name": "Canal 8",
            "violations": [{"class": "Sem protetor de ouvido", "confidence": 0.76}],
            "confidence": 0.76,
            "acknowledged": False,
            "evidence_key": None,
            "timestamp": self._CAPTURA,
            "created_at": self._GRAVACAO,
        }

    def test_lista_emite_iso_utc_com_z(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo(items=[self._row()], total=1)):
            resp = client.get("/api/alerts", headers=auth_headers)
        alerta = resp.get_json()["data"]["alerts"][0]
        assert self._ISO_UTC.match(alerta["timestamp"]), alerta["timestamp"]
        assert self._ISO_UTC.match(alerta["created_at"]), alerta["created_at"]

    def test_detalhe_emite_iso_utc_com_z(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id.return_value = self._row()
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)
        alerta = resp.get_json()["data"]["alert"]
        assert self._ISO_UTC.match(alerta["captured_at"]), alerta["captured_at"]
        assert self._ISO_UTC.match(alerta["created_at"]), alerta["created_at"]

    def test_lista_e_detalhe_concordam_no_mesmo_alerta(self, client, auth_headers):
        """O defeito das 3h: mesma linha, mesmo instante, dois valores."""
        repo = _mock_repo(items=[self._row()], total=1)
        repo.get_by_id.return_value = self._row()
        with patch(_GET_REPO, return_value=repo):
            da_lista = client.get("/api/alerts", headers=auth_headers)
            do_detalhe = client.get(f"/api/alerts/{ALERT_ID}", headers=auth_headers)

        lista = da_lista.get_json()["data"]["alerts"][0]
        detalhe = do_detalhe.get_json()["data"]["alert"]
        assert lista["timestamp"] == detalhe["captured_at"] == "2026-08-20T14:30:00Z"
        assert lista["created_at"] == detalhe["created_at"] == "2026-08-20T14:31:00Z"

    def test_acknowledge_tambem_emite_iso_utc(self, client, auth_headers):
        repo = MagicMock()
        repo.acknowledge.return_value = dict(self._row(), acknowledged=True)
        with patch(_GET_REPO, return_value=repo):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        alerta = resp.get_json()["data"]["alert"]
        assert self._ISO_UTC.match(alerta["created_at"]), alerta["created_at"]

    def test_csv_usa_a_hora_de_captura_que_a_tela_mostra(self, client, auth_headers):
        """CSV exportava created_at (14:31) enquanto a tela exibe timestamp (14:30)."""
        with patch(_GET_REPO, return_value=_mock_repo(items=[self._row()], total=1)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        corpo = resp.data.decode("utf-8")
        assert "2026-08-20T14:30:00Z" in corpo
        assert "14:31" not in corpo

    def test_csv_cai_para_created_at_quando_nao_ha_captura(self, client, auth_headers):
        items = [dict(self._row(), timestamp=None)]
        with patch(_GET_REPO, return_value=_mock_repo(items=items, total=1)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert "2026-08-20T14:31:00Z" in resp.data.decode("utf-8")

    def test_iso_utc_preserva_o_instante_de_datetime_com_offset(self):
        from datetime import timedelta, timezone

        from app.api.v1.alerts.routes import _iso_utc
        brt = datetime(2026, 8, 20, 11, 30, tzinfo=timezone(timedelta(hours=-3)))
        assert _iso_utc(brt) == "2026-08-20T14:30:00Z"
        assert _iso_utc(None) is None
        assert _iso_utc("2024-01-01") == "2024-01-01"
