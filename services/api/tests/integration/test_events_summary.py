"""
Integration tests: GET /api/v1/events/summary (mutirão WS3).

Cobertura:
  - 401 sem JWT
  - 400 sem from/to; 400 to < from; 400 janela > 92 dias
  - 200 com shape {total, by_class, by_camera}
  - filtros module_code/camera_id[]/class_name[] aceitos
  - isolamento por tenant: tenant do JWT sempre nos params SQL

Estratégia idêntica à de test_events_routes.py: DatabasePool mockado.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
CAM_ID = str(uuid4())

_POOL = "app.api.v1.events.routes.DatabasePool.get_instance"


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(fetchone=None, fetchall=None):
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = fetchone if fetchone is not None else {"count": 0}
    cur.fetchall.return_value = fetchall or []
    conn.cursor.return_value = cur
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool, cur


_RANGE = "from=2026-06-01T00:00:00&to=2026-06-08T00:00:00"


class TestEventsSummary:

    def test_requires_jwt(self, client) -> None:
        res = client.get(f"/api/v1/events/summary?{_RANGE}")
        assert res.status_code in (401, 422)

    def test_400_without_from_to(self, client, operator_headers) -> None:
        res = client.get("/api/v1/events/summary", headers=operator_headers)
        assert res.status_code == 400

    def test_400_when_to_before_from(self, client, operator_headers) -> None:
        res = client.get(
            "/api/v1/events/summary?from=2026-06-08T00:00:00&to=2026-06-01T00:00:00",
            headers=operator_headers,
        )
        assert res.status_code == 400

    def test_400_when_window_exceeds_92_days(self, client, operator_headers) -> None:
        res = client.get(
            "/api/v1/events/summary?from=2026-01-01T00:00:00&to=2026-06-01T00:00:00",
            headers=operator_headers,
        )
        assert res.status_code == 400

    def test_200_shape(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(
            fetchone={"count": 42},
            fetchall=[],
        )
        with patch(_POOL, return_value=pool):
            res = client.get(
                f"/api/v1/events/summary?{_RANGE}", headers=operator_headers
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        data = body["data"]
        assert data["total"] == 42
        assert data["by_class"] == []
        assert data["by_camera"] == []

    def test_by_class_and_by_camera_serialization(self, client, operator_headers) -> None:
        cam_uuid = uuid4()
        pool, cur = _mock_pool(fetchone={"count": 3})
        # ORDEM DAS CONSULTAS (ADR-0063): a 1ª é `presence_class_names` — o
        # predicado que separa CONFORMIDADE (presença de EPI) de VIOLAÇÃO
        # (ausência). Sem ela o agregado contava presença como violação, e a
        # taxa de conformidade saía invertida: quanto mais gente usava EPI,
        # pior o número. Depois vêm by_class e by_camera.
        cur.fetchall.side_effect = [
            [{"n": "protetor auditivo"}, {"n": "mascara"}],
            [{"class": "no_helmet", "count": 2}, {"class": "no_vest", "count": 1}],
            [{"camera_id": cam_uuid, "camera_name": "Portaria", "count": 3}],
        ]
        with patch(_POOL, return_value=pool):
            res = client.get(
                f"/api/v1/events/summary?{_RANGE}", headers=operator_headers
            )

        data = res.get_json()["data"]
        assert data["by_class"][0] == {"class": "no_helmet", "count": 2}
        assert data["by_camera"][0]["camera_id"] == str(cam_uuid)
        assert data["by_camera"][0]["camera_name"] == "Portaria"
        assert data["by_camera"][0]["count"] == 3

    def test_accepts_filters(self, client, operator_headers) -> None:
        pool, _ = _mock_pool()
        with patch(_POOL, return_value=pool):
            res = client.get(
                f"/api/v1/events/summary?{_RANGE}"
                f"&module_code=epi&camera_id[]={CAM_ID}&class_name[]=no_helmet",
                headers=operator_headers,
            )
        assert res.status_code == 200

    def test_tenant_isolation(self, client, operator_headers) -> None:
        """tenant_id do JWT presente nos params de TODAS as queries do summary."""
        pool, cur = _mock_pool()
        with patch(_POOL, return_value=pool):
            res = client.get(
                f"/api/v1/events/summary?{_RANGE}", headers=operator_headers
            )

        assert res.status_code == 200
        calls = cur.execute.call_args_list
        # 4 desde a ADR-0063: presence_class_names + count + by_class + by_camera.
        assert len(calls) == 4, "presence_class_names entrou como 1ª query"
        for call in calls:
            sql, params = call[0]
            # TODA query carrega o tenant do JWT nos parâmetros — inclusive a de
            # presence_class_names, cujo ramo de yolo_classes é escopado (o outro
            # ramo é o catálogo GLOBAL module_classes, que não tem tenant_id por
            # natureza; por isso a asserção é sobre o parâmetro, não sobre o texto).
            assert TENANT_ID in [str(x) for x in params], (
                f"query sem o tenant do JWT nos params: {sql[:80]}"
            )
        # o vazamento clássico continua coberto: as 3 queries de agregação
        # filtram por tenant no WHERE, não só recebem o parâmetro.
        for call in calls[1:]:
            assert "tenant_id = %s" in call[0][0]
