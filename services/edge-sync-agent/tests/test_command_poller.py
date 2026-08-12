"""Tests for CommandPoller: consume edge_commands, apply camera config, ack results."""

import threading
from unittest.mock import MagicMock

from app.command_poller import CommandPoller
from app.config_poller import ConfigPoller

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_poller(http, config_poller=None, *, poll_interval_s=0.0):
    return CommandPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        token="tok",
        config_poller=config_poller or MagicMock(),
        poll_interval_s=poll_interval_s,
    )


def _http_ok(body: dict):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body
    return resp


def _http_err(status: int = 503):
    resp = MagicMock()
    resp.status_code = status
    return resp


def _command(command_type="update_camera_config", command_id="cmd-1", payload=None):
    return {
        "command_id": command_id,
        "command_type": command_type,
        "payload": payload if payload is not None else {
            "camera_id": "cam-1", "fps_target": 10, "quality_preset": "high",
        },
    }


def _envelope(commands):
    """API envelope real: success({'commands': rows, 'count': n})."""
    return {"status": "success", "data": {"commands": commands, "count": len(commands)}}


# ── consumo e aplicação ──────────────────────────────────────────────────────

def test_applies_update_camera_config_and_acks_done():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_command()]))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = _make_poller(http, config)

    handled = p._poll_once()

    assert handled == 1
    config.apply_camera_config.assert_called_once_with("cam-1", 10, "high", None)
    ack_url = http.patch.call_args[0][0]
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_url.endswith("/api/v1/edge/commands/cmd-1")
    assert ack_body["status"] == "done"
    assert ack_body["result"] == {"applied": True}


def test_apply_exception_acks_failed():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_command()]))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.side_effect = RuntimeError("boom")
    p = _make_poller(http, config)

    p._poll_once()

    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert "boom" in ack_body["result"]["reason"]


def test_unknown_command_type_acks_failed_unsupported():
    """Tipo desconhecido não entope a fila: ack failed com reason=unsupported."""
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_command(command_type="reboot")]))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    p = _make_poller(http, config)

    p._poll_once()

    config.apply_camera_config.assert_not_called()
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert ack_body["result"] == {"reason": "unsupported"}


def test_top_level_commands_body_also_supported():
    """Robustez: body sem envelope ({commands: [...]}) também é aceito."""
    http = MagicMock()
    http.get.return_value = _http_ok({"commands": [_command()]})
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = _make_poller(http, config)

    assert p._poll_once() == 1


def test_poll_error_returns_zero_and_does_not_raise():
    http = MagicMock()
    http.get.side_effect = ConnectionError("offline")
    p = _make_poller(http)

    assert p._poll_once() == 0


def test_non_200_returns_zero():
    http = MagicMock()
    http.get.return_value = _http_err(401)
    p = _make_poller(http)

    assert p._poll_once() == 0


def test_command_without_id_is_ignored():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([{"command_type": "update_camera_config"}]))
    p = _make_poller(http)

    p._poll_once()

    http.patch.assert_not_called()


def test_ack_failure_does_not_raise():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_command()]))
    http.patch.side_effect = ConnectionError("offline")
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = _make_poller(http, config)

    p._poll_once()  # não levanta


def test_applies_collection_subtype_from_payload():
    """Eixo COLETA (migration 114): payload com collection_subtype repassa
    ao ConfigPoller."""
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([
        _command(payload={
            "camera_id": "cam-1", "fps_target": 10, "quality_preset": "high",
            "collection_subtype": 1,
        })
    ]))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = _make_poller(http, config)

    p._poll_once()

    config.apply_camera_config.assert_called_once_with("cam-1", 10, "high", 1)


# ── integração com ConfigPoller real ─────────────────────────────────────────

def test_updates_config_poller_state_in_memory():
    """Fluxo real: config chega pelo poll, comando atualiza fps em memória."""
    cfg_http = MagicMock()
    cfg_http.get.return_value = _http_ok(
        {"cameras": [{"id": "cam-1", "name": "Doca", "fps_target": 5}]}
    )
    config = ConfigPoller(
        http_client=cfg_http, cloud_url="http://cloud.test",
        device_id="dev-1", token="tok",
    )
    config._poll_once()

    cmd_http = MagicMock()
    cmd_http.get.return_value = _http_ok(_envelope([_command()]))
    cmd_http.patch.return_value = _http_ok({})
    p = _make_poller(cmd_http, config)

    p._poll_once()

    cam = config.get_cameras()[0]
    assert cam["fps_target"] == 10
    assert cam["quality_preset"] == "high"


def test_apply_camera_config_unknown_camera_returns_false():
    config = ConfigPoller(
        http_client=MagicMock(), cloud_url="http://cloud.test",
        device_id="dev-1", token="tok",
    )
    assert config.apply_camera_config("ghost", 10, "low") is False


def test_run_stops_on_stop_event():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([]))
    p = _make_poller(http, poll_interval_s=0.01)
    stop = threading.Event()

    t = threading.Thread(target=p.run, args=(stop,), daemon=True)
    t.start()
    stop.set()
    t.join(timeout=2.0)

    assert not t.is_alive()


# ── monitoring.* + burst mode (/monitoring) ──────────────────────────────────


def _make_monitoring_poller(http, handler, **kwargs):
    return CommandPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        token="tok",
        config_poller=MagicMock(),
        monitoring_handler=handler,
        **kwargs,
    )


def test_monitoring_command_dispatches_to_handler_and_acks_done():
    http = MagicMock()
    http.get.return_value = _http_ok(
        _envelope([_command(command_type="monitoring.query", payload={"window": "2h"})])
    )
    http.patch.return_value = _http_ok({})
    handler = MagicMock()
    handler.handle.return_value = {"samples": [], "schema": 1}
    p = _make_monitoring_poller(http, handler)

    p._poll_once()

    handler.handle.assert_called_once_with("monitoring.query", {"window": "2h"})
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "done"
    assert ack_body["result"]["schema"] == 1


def test_monitoring_handler_error_acks_failed():
    http = MagicMock()
    http.get.return_value = _http_ok(
        _envelope([_command(command_type="monitoring.query", payload={"window": "9h"})])
    )
    http.patch.return_value = _http_ok({})
    handler = MagicMock()
    handler.handle.side_effect = ValueError("janela inválida")
    p = _make_monitoring_poller(http, handler)

    p._poll_once()

    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert "janela inválida" in ack_body["result"]["reason"]


def test_monitoring_without_handler_acks_unsupported():
    """Sem handler injetado (release antigo do wiring), monitoring.* não
    entope a fila: cai no ack failed genérico."""
    http = MagicMock()
    http.get.return_value = _http_ok(
        _envelope([_command(command_type="monitoring.query", payload={})])
    )
    http.patch.return_value = _http_ok({})
    p = _make_poller(http)

    p._poll_once()

    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["result"] == {"reason": "unsupported"}


def test_monitoring_command_activates_burst_interval():
    """Sessão de /monitoring ativa → poll acelera; sem sessão → 60s de sempre.
    O burst expira sozinho (TTL) — página fechada volta ao regime idle."""
    http = MagicMock()
    http.get.return_value = _http_ok(
        _envelope([_command(command_type="monitoring.snapshot", payload={})])
    )
    http.patch.return_value = _http_ok({})
    handler = MagicMock()
    handler.handle.return_value = {}
    p = _make_monitoring_poller(
        http, handler, poll_interval_s=60.0, burst_interval_s=2.0, burst_ttl_s=180.0
    )

    assert p._current_interval() == 60.0
    p._poll_once()
    assert p._current_interval() == 2.0


def test_burst_expires_back_to_idle_interval():
    http = MagicMock()
    handler = MagicMock()
    p = _make_monitoring_poller(
        http, handler, poll_interval_s=60.0, burst_interval_s=2.0, burst_ttl_s=0.0
    )
    p._burst_until = 0.0  # TTL zero: nunca em burst
    assert p._current_interval() == 60.0


def test_non_monitoring_command_does_not_activate_burst():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_command()]))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = CommandPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        token="tok",
        config_poller=config,
        monitoring_handler=MagicMock(),
        poll_interval_s=60.0,
    )

    p._poll_once()

    assert p._current_interval() == 60.0
