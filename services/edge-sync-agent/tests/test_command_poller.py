"""Tests for CommandPoller: consume edge_commands, apply camera config, ack results."""

import os
import stat
import threading
from unittest.mock import MagicMock, patch

from app.command_poller import CommandPoller
from app.config_poller import ConfigPoller

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_poller(
    http, config_poller=None, *, poll_interval_s=0.0,
    snapshot_executor=None, snapshot_delay_s=2.0, sleep_fn=None,
    propagation_python=None, propagation_executor_path=None, propagation_run_dir=None,
):
    return CommandPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        token="tok",
        config_poller=config_poller or MagicMock(),
        poll_interval_s=poll_interval_s,
        snapshot_executor=snapshot_executor,
        snapshot_delay_s=snapshot_delay_s,
        sleep_fn=sleep_fn if sleep_fn is not None else MagicMock(),
        propagation_python=propagation_python,
        propagation_executor_path=propagation_executor_path,
        propagation_run_dir=propagation_run_dir,
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


# ── capture_snapshot (Bloco A: miniatura de triagem) ────────────────────────

def _snapshot_command(command_id="snap-1", camera_id="cam-1", channel=3):
    return {
        "command_id": command_id,
        "command_type": "capture_snapshot",
        "payload": {"camera_id": camera_id, "channel": channel},
    }


def test_capture_snapshot_success_acks_done():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_snapshot_command()]))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = False
    executor.capture_and_upload.return_value = {"ok": True}
    p = _make_poller(http, snapshot_executor=executor)

    handled = p._poll_once()

    assert handled == 1
    executor.capture_and_upload.assert_called_once_with("cam-1", 3)
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "done"
    assert ack_body["result"] == {"captured": True}


def test_capture_snapshot_failure_acks_failed_with_reason():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_snapshot_command()]))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = False
    executor.capture_and_upload.return_value = {
        "ok": False, "reason": "sem sinal no canal", "detail": "canal 3 mudo",
    }
    p = _make_poller(http, snapshot_executor=executor)

    p._poll_once()

    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert ack_body["result"] == {"reason": "sem sinal no canal", "detail": "canal 3 mudo"}


def test_capture_snapshot_without_camera_id_acks_invalid_payload():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([
        {"command_id": "snap-bad", "command_type": "capture_snapshot", "payload": {}}
    ]))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = False
    p = _make_poller(http, snapshot_executor=executor)

    p._poll_once()

    executor.capture_and_upload.assert_not_called()
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["result"] == {"reason": "invalid_payload"}


def test_capture_snapshot_without_executor_acks_unsupported():
    """No snapshot_executor wired (recorder_client wasn't available at boot,
    or a plain non-snapshot deployment) — never clogs the queue."""
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_snapshot_command()]))
    http.patch.return_value = _http_ok({})
    p = _make_poller(http, snapshot_executor=None)

    p._poll_once()

    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert ack_body["result"] == {"reason": "unsupported"}


# ── anti-lockout: circuit breaker skips remaining commands without trying ──

def test_circuit_open_before_batch_fails_fast_without_calling_executor():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_snapshot_command()]))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = True
    executor.circuit_reason = "onvif_soap_auth_failed status=401"
    p = _make_poller(http, snapshot_executor=executor)

    p._poll_once()

    executor.capture_and_upload.assert_not_called()
    ack_body = http.patch.call_args.kwargs["json"]
    assert ack_body["status"] == "failed"
    assert ack_body["result"]["reason"] == "auth"


def test_circuit_trips_mid_batch_fails_remaining_snapshot_commands_without_trying():
    """3 capture_snapshot commands in ONE poll batch; the executor trips the
    breaker on the FIRST — the 2nd and 3rd must never reach the recorder."""
    http = MagicMock()
    commands = [
        _snapshot_command("snap-1", "cam-1"),
        _snapshot_command("snap-2", "cam-2"),
        _snapshot_command("snap-3", "cam-3"),
    ]
    http.get.return_value = _http_ok(_envelope(commands))
    http.patch.return_value = _http_ok({})

    executor = MagicMock()
    executor.circuit_reason = None

    def _fake_capture(camera_id, channel=None):
        # First call trips the breaker (simulating a real SnapshotExecutor).
        executor.circuit_open = True
        executor.circuit_reason = "status=401"
        return {"ok": False, "reason": "auth", "detail": "status=401"}

    executor.circuit_open = False
    executor.capture_and_upload.side_effect = _fake_capture
    p = _make_poller(http, snapshot_executor=executor)

    handled = p._poll_once()

    assert handled == 3
    executor.capture_and_upload.assert_called_once()  # only cam-1 ever touched the recorder
    patch_calls = http.patch.call_args_list
    assert len(patch_calls) == 3
    for call in patch_calls:
        assert call.kwargs["json"]["status"] == "failed"
        assert call.kwargs["json"]["result"]["reason"] == "auth"


def test_other_command_types_unaffected_by_snapshot_circuit_breaker():
    """The breaker is scoped to capture_snapshot only — update_camera_config
    in the same batch must still be applied normally."""
    http = MagicMock()
    commands = [_snapshot_command(), _command()]  # snapshot + update_camera_config
    http.get.return_value = _http_ok(_envelope(commands))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = True
    executor.circuit_reason = "status=401"
    config = MagicMock()
    config.apply_camera_config.return_value = True
    p = _make_poller(http, config, snapshot_executor=executor)

    p._poll_once()

    config.apply_camera_config.assert_called_once()
    statuses = [c.kwargs["json"]["status"] for c in http.patch.call_args_list]
    assert statuses == ["failed", "done"]


# ── sequential processing: short delay between successive captures ─────────

def test_delay_inserted_between_successive_captures_not_before_first():
    http = MagicMock()
    commands = [
        _snapshot_command("snap-1", "cam-1"),
        _snapshot_command("snap-2", "cam-2"),
        _snapshot_command("snap-3", "cam-3"),
    ]
    http.get.return_value = _http_ok(_envelope(commands))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = False
    executor.capture_and_upload.return_value = {"ok": True}
    sleep_fn = MagicMock()
    p = _make_poller(http, snapshot_executor=executor, snapshot_delay_s=2.5, sleep_fn=sleep_fn)

    p._poll_once()

    # 3 captures -> 2 delays (between 1st/2nd and 2nd/3rd), never after the last.
    assert sleep_fn.call_count == 2
    sleep_fn.assert_called_with(2.5)


def test_no_delay_once_breaker_trips_mid_batch():
    """Uma vez que o breaker abre, não há mais chamada ao gravador pela
    frente — não faz sentido continuar esperando entre os acks fail-fast
    restantes."""
    http = MagicMock()
    commands = [
        _snapshot_command("snap-1", "cam-1"),
        _snapshot_command("snap-2", "cam-2"),
        _snapshot_command("snap-3", "cam-3"),
    ]
    http.get.return_value = _http_ok(_envelope(commands))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_reason = None

    def _fake_capture(camera_id, channel=None):
        executor.circuit_open = True
        executor.circuit_reason = "status=401"
        return {"ok": False, "reason": "auth", "detail": "status=401"}

    executor.circuit_open = False
    executor.capture_and_upload.side_effect = _fake_capture
    sleep_fn = MagicMock()
    p = _make_poller(http, snapshot_executor=executor, sleep_fn=sleep_fn)

    p._poll_once()

    sleep_fn.assert_not_called()


def test_no_delay_when_only_one_snapshot_in_batch():
    http = MagicMock()
    http.get.return_value = _http_ok(_envelope([_snapshot_command()]))
    http.patch.return_value = _http_ok({})
    executor = MagicMock()
    executor.circuit_open = False
    executor.capture_and_upload.return_value = {"ok": True}
    sleep_fn = MagicMock()
    p = _make_poller(http, snapshot_executor=executor, sleep_fn=sleep_fn)

    p._poll_once()

    sleep_fn.assert_not_called()


def test_no_delay_between_unrelated_command_types():
    http = MagicMock()
    commands = [
        _command("update_camera_config", "cfg-1"),
        _command("update_camera_config", "cfg-2"),
    ]
    http.get.return_value = _http_ok(_envelope(commands))
    http.patch.return_value = _http_ok({})
    config = MagicMock()
    config.apply_camera_config.return_value = True
    sleep_fn = MagicMock()
    p = _make_poller(http, config, sleep_fn=sleep_fn)

    p._poll_once()

    sleep_fn.assert_not_called()


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


# ── run_propagation (task "propagação no edge") ────────────────────────────

def _propagation_payload(**overrides) -> dict:
    payload = {
        "job_id": "11111111-2222-3333-4444-555555555555",
        "manifest_url": "https://r2.example/manifest.json?sig=1",
        "callback_url": "https://api.example/api/v1/training/propagation/jobs/j1/callback",
        "callback_token": "super-secret-callback-token",
        "sam_weights_url": "https://r2.example/sam.pth?sig=2",
        "sam_weights_sha256": "a" * 64,
        "dinov2_weights_url": "https://dl.fbaipublicfiles.com/dinov2/x.pth",
        "dinov2_weights_sha256": "b" * 64,
        "similarity_threshold": "0.65",
        "progress_every_n": 20,
        "max_results": 25,
        "mem_max": "6G",
        "cpu_quota": "400%",
    }
    payload.update(overrides)
    return payload


class TestRunPropagation:
    def test_valid_payload_launches_systemd_run_and_writes_env_file_0600(self, tmp_path) -> None:
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-p1", "command_type": "run_propagation",
             "payload": _propagation_payload()},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(
            http,
            propagation_python="/fake/envs/propagation/bin/python",
            propagation_executor_path="/fake/repo/training/propagate_seeded.py",
            propagation_run_dir=str(tmp_path),
        )

        with patch("app.command_poller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            p._poll_once()

        # ack 'done' com {launched, unit}
        ack_body = http.patch.call_args.kwargs["json"]
        assert ack_body["status"] == "done"
        assert ack_body["result"]["launched"] is True
        assert ack_body["result"]["unit"] == "propagation-11111111"

        # systemd-run chamado com os -p certos, NUNCA com o token no argv.
        # Serviço transiente (não --scope): detached + EnvironmentFile lido
        # pelo systemd LITERAL (sem shell — `&` de URL presignada não perde
        # variável, bug real da 1ª versão com wrapper `set -a; . env`).
        argv = mock_run.call_args.args[0]
        assert argv[0] == "systemd-run"
        assert "--user" in argv
        assert "--scope" not in argv
        assert "--collect" in argv
        assert "--unit=propagation-11111111" in argv
        assert "-p" in argv
        assert "MemoryMax=6G" in argv
        assert "CPUQuota=400%" in argv
        joined_argv = " ".join(argv)
        assert "super-secret-callback-token" not in joined_argv

        # arquivo de env escrito 0600, com o token dentro (nunca em argv)
        env_files = list(tmp_path.glob("propagation-*.env"))
        assert len(env_files) == 1
        env_file = env_files[0]
        mode = stat.S_IMODE(os.stat(env_file).st_mode)
        assert mode == 0o600
        content = env_file.read_text()
        assert "CALLBACK_TOKEN=super-secret-callback-token" in content
        assert "MANIFEST_URL=https://r2.example/manifest.json?sig=1" in content
        assert "SAM_WEIGHTS_SHA256=" + "a" * 64 in content
        assert "MAX_RESULTS=25" in content
        assert "LD_LIBRARY_PATH=" in content
        assert "/usr/local/cuda/lib64" in content

        # EnvironmentFile aponta pro MESMO arquivo; python/executor são os
        # dois últimos argv (exec direto, sem bash/wrapper)
        assert f"EnvironmentFile={env_file}" in argv
        assert argv[-2] == "/fake/envs/propagation/bin/python"
        assert argv[-1] == "/fake/repo/training/propagate_seeded.py"
        assert "bash" not in argv

    def test_env_file_values_are_literal_even_with_ampersand(self, tmp_path) -> None:
        """URL presignada tem `&` — o valor precisa ir LITERAL pro arquivo
        (parser do systemd), sem depender de quoting de shell. Regressão do
        bug real: com wrapper `source`, MANIFEST_URL se perdia no box."""
        url = "https://r2.example/m.json?X-Amz-Cred=abc&X-Amz-Signature=def&X-Amz-Expires=300"
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-amp", "command_type": "run_propagation",
             "payload": _propagation_payload(manifest_url=url)},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(
            http,
            propagation_python="/fake/envs/propagation/bin/python",
            propagation_executor_path="/fake/repo/training/propagate_seeded.py",
            propagation_run_dir=str(tmp_path),
        )
        with patch("app.command_poller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            p._poll_once()
        env_file = next(tmp_path.glob("propagation-*.env"))
        assert f"MANIFEST_URL={url}\n" in env_file.read_text()

    def test_payload_without_token_acks_failed_without_launching(self, tmp_path) -> None:
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-p2", "command_type": "run_propagation",
             "payload": _propagation_payload(callback_token="")},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(http, propagation_run_dir=str(tmp_path))

        with patch("app.command_poller.subprocess.run") as mock_run:
            p._poll_once()

        mock_run.assert_not_called()
        ack_body = http.patch.call_args.kwargs["json"]
        assert ack_body["status"] == "failed"
        assert "callback_token" in ack_body["result"]["reason"]
        assert list(tmp_path.glob("propagation-*.env")) == []

    def test_missing_job_id_acks_failed_without_launching(self, tmp_path) -> None:
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-p3", "command_type": "run_propagation",
             "payload": _propagation_payload(job_id="")},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(http, propagation_run_dir=str(tmp_path))

        with patch("app.command_poller.subprocess.run") as mock_run:
            p._poll_once()

        mock_run.assert_not_called()
        ack_body = http.patch.call_args.kwargs["json"]
        assert ack_body["status"] == "failed"

    def test_systemd_run_failure_acks_failed_and_removes_env_file(self, tmp_path) -> None:
        """Lançamento falhou (systemd-run devolveu erro) — o arquivo de env
        (com o callback_token) não fica pra trás no disco."""
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-p4", "command_type": "run_propagation",
             "payload": _propagation_payload()},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(http, propagation_run_dir=str(tmp_path))

        import subprocess as real_subprocess
        with patch("app.command_poller.subprocess.run") as mock_run:
            mock_run.side_effect = real_subprocess.CalledProcessError(1, ["systemd-run"])
            p._poll_once()

        ack_body = http.patch.call_args.kwargs["json"]
        assert ack_body["status"] == "failed"
        assert list(tmp_path.glob("propagation-*.env")) == []

    def test_max_results_absent_is_omitted_from_env_file(self, tmp_path) -> None:
        """`max_results` é opcional (propagate_seeded.py trata ausência
        como "sem cap") — nunca grava `MAX_RESULTS=None` no arquivo."""
        http = MagicMock()
        payload = _propagation_payload()
        del payload["max_results"]
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-p5", "command_type": "run_propagation", "payload": payload},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(http, propagation_run_dir=str(tmp_path))

        with patch("app.command_poller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            p._poll_once()

        content = list(tmp_path.glob("propagation-*.env"))[0].read_text()
        assert "MAX_RESULTS" not in content

    def test_default_propagation_python_and_executor_path(self) -> None:
        """Sem overrides no construtor, cai nos defaults documentados
        (~/envs/propagation/bin/python; training/propagate_seeded.py
        relativo ao checkout do repo no box)."""
        p = _make_poller(MagicMock())
        assert p._propagation_python.endswith("/envs/propagation/bin/python")
        assert p._propagation_executor_path.endswith("training/propagate_seeded.py")


class TestRunPropagationWorkDir:
    def test_env_file_contains_writable_work_dir(self, tmp_path) -> None:
        """O default /root do executor é do pod RunPod (root); no box o env
        precisa injetar WORK_DIR gravável dentro do run_dir."""
        http = MagicMock()
        http.get.return_value = _http_ok(_envelope([
            {"command_id": "cmd-wd", "command_type": "run_propagation",
             "payload": _propagation_payload()},
        ]))
        http.patch.return_value = _http_ok({})
        p = _make_poller(http, propagation_run_dir=str(tmp_path))

        with patch("app.command_poller.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            p._poll_once()

        content = list(tmp_path.glob("propagation-*.env"))[0].read_text()
        work_dirs = [ln for ln in content.splitlines() if ln.startswith("WORK_DIR=")]
        assert len(work_dirs) == 1
        work_dir = work_dirs[0].split("=", 1)[1]
        assert work_dir.startswith(str(tmp_path))
        assert os.path.isdir(work_dir)  # já criado antes do lançamento
