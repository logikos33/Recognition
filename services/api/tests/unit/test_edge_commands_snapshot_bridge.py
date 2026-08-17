"""
Unit — bridge best-effort em PATCH /api/v1/edge/commands/<id>: um ack failed
de um comando `capture_snapshot` espelha o motivo no cache Redis que
GET /api/cameras/<id>/snapshot lê (Bloco A — sem isso a UI de triagem
ficaria presa em "pending" para sempre após uma falha, já que o sucesso é
escrito pelo endpoint de upload, mas a falha não passa por lá).
"""
import json
from unittest.mock import MagicMock

import app.api.v1.edge_commands.routes as cmd_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "device-abc123"
CMD_ID = "cmd-0001"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"

COMMANDS_WRITE = "commands:write"


def _authed(*scopes: str):
    granted = list(scopes) or [COMMANDS_WRITE]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _patch(client, status="failed", result=None):
    return client.patch(
        f"/api/v1/edge/commands/{CMD_ID}",
        json={"status": status, "result": result},
        headers={"Authorization": "Bearer device-token"},
    )


def test_capture_snapshot_failure_writes_redis_cache(client, monkeypatch):
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "failed",
        "command_type": "capture_snapshot",
        "payload": {"camera_id": CAMERA_ID, "channel": 3},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())

    redis_client = MagicMock()
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    resp = _patch(client, result={"reason": "sem sinal no canal", "detail": "canal 3 mudo"})

    assert resp.status_code == 200
    redis_client.setex.assert_called_once()
    key, _ttl, raw = redis_client.setex.call_args[0]
    assert key == f"epi:camera_snapshot:{TENANT}:{CAMERA_ID}"
    state = json.loads(raw)
    assert state["status"] == "failed"
    assert state["error_reason"] == "Canal sem sinal"


def test_capture_snapshot_auth_failure_humanizes_reason(client, monkeypatch):
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "failed",
        "command_type": "capture_snapshot",
        "payload": {"camera_id": CAMERA_ID},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())
    redis_client = MagicMock()
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    _patch(client, result={"reason": "auth", "detail": "status=401"})

    raw = redis_client.setex.call_args[0][2]
    state = json.loads(raw)
    assert "autenticação" in state["error_reason"].lower()


def test_done_status_does_not_touch_redis_cache(client, monkeypatch):
    """Sucesso já é escrito pelo endpoint de upload (com os bytes reais) —
    o bridge só cobre o caminho de falha."""
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "done",
        "command_type": "capture_snapshot",
        "payload": {"camera_id": CAMERA_ID},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())
    redis_client = MagicMock()
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    resp = _patch(client, status="done", result={"captured": True})

    assert resp.status_code == 200
    redis_client.setex.assert_not_called()


def test_other_command_types_are_not_bridged(client, monkeypatch):
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "failed",
        "command_type": "update_camera_config",
        "payload": {"camera_id": CAMERA_ID},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())
    redis_client = MagicMock()
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    resp = _patch(client, result={"reason": "boom"})

    assert resp.status_code == 200
    redis_client.setex.assert_not_called()


def test_bridge_failure_never_fails_the_ack(client, monkeypatch):
    """Best-effort (mesmo padrão de _bridge_heartbeat_to_telemetry): erro no
    Redis não pode derrubar o PATCH — o comando JÁ foi persistido no banco."""
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "failed",
        "command_type": "capture_snapshot",
        "payload": {"camera_id": CAMERA_ID},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())
    redis_client = MagicMock()
    redis_client.setex.side_effect = ConnectionError("redis down")
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    resp = _patch(client, result={"reason": "timeout"})

    assert resp.status_code == 200


def test_missing_camera_id_in_payload_is_a_no_op(client, monkeypatch):
    repo = MagicMock()
    repo.update_status.return_value = {
        "command_id": CMD_ID, "status": "failed",
        "command_type": "capture_snapshot",
        "payload": {},
    }
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed())
    redis_client = MagicMock()
    import app.api.v1.cameras.helpers as cam_helpers
    monkeypatch.setattr(cam_helpers, "_get_redis", lambda: redis_client)

    resp = _patch(client, result={"reason": "timeout"})

    assert resp.status_code == 200
    redis_client.setex.assert_not_called()
