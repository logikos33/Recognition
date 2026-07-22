"""Bridge heartbeat → dashboard integrado (Pilha A→B).

Cobre `_heartbeat_to_telemetry_payload` (payload JSON-safe) e a garantia de que
`_bridge_heartbeat_to_telemetry` é best-effort: um erro NUNCA propaga para o
caminho de ingest do heartbeat (Pilha A é a fonte da verdade).
"""
import json
from decimal import Decimal

from recognition_shared.heartbeat import Heartbeat

from app.api.v1.edge import routes as edge_routes


def _hb() -> Heartbeat:
    return Heartbeat(
        device_id="pandora-orin-rvb",
        status="healthy",
        cpu_pct=Decimal("12.5"),
        gpu_pct=Decimal("45.0"),
        gpu_temp_c=Decimal("61.3"),
        inference_fps=Decimal("28.4"),
        cameras_online=28,
        cameras_total=28,
        dropped_frames=0,
        edge_version="task-100-mvp",
    )


def test_payload_is_json_safe_and_has_fields():
    payload = edge_routes._heartbeat_to_telemetry_payload(_hb())
    # Serializável sem TypeError de Decimal
    dumped = json.dumps(payload)
    assert isinstance(dumped, str)
    # Decimals viraram float; ints seguem int; status string
    assert payload["cpu_pct"] == 12.5
    assert isinstance(payload["cpu_pct"], float)
    assert payload["gpu_temp_c"] == 61.3
    assert payload["cameras_online"] == 28
    assert isinstance(payload["cameras_online"], int)
    assert payload["status"] == "healthy"
    assert payload["edge_version"] == "task-100-mvp"


def test_payload_omits_none_fields():
    hb = Heartbeat(device_id="d", status="healthy")  # sem métricas
    payload = edge_routes._heartbeat_to_telemetry_payload(hb)
    assert "cpu_pct" not in payload
    assert payload["status"] == "healthy"


def test_bridge_is_best_effort_never_raises(monkeypatch):
    # Força o pool a explodir — o bridge deve engolir e não propagar.
    class _Boom:
        @staticmethod
        def get_instance():
            raise RuntimeError("pool indisponível")

    monkeypatch.setattr(edge_routes, "DatabasePool", _Boom)
    # Não deve levantar
    edge_routes._bridge_heartbeat_to_telemetry(
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        _hb(),
        "2026-07-21T00:00:00Z",
    )
