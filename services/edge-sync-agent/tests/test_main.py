"""Tests for app/main.py: the minimal entrypoint wiring the real RecorderClient
+ TrustAnchor into evidence_api.create_app(). run_server() itself (which
binds a socket) is always monkeypatched — these tests only prove the wiring,
not the HTTP server lifecycle (already covered by test_evidence_api.py)."""

import pytest

from app import main as main_module
from app.evidence_auth import TrustAnchor
from app.onvif_recorder_client import OnvifRecorderClient
from app.recorder_client import RecorderError


def test_build_trust_anchor_reads_key_file(tmp_path):
    key_file = tmp_path / "trust_public_key.pem"
    key_file.write_text("-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")

    anchor = main_module.build_trust_anchor(
        {
            "EVIDENCE_TRUST_PUBLIC_KEY_PATH": str(key_file),
            "TENANT_ID": "tenant-1",
            "SITE_ID": "site-1",
        }
    )

    assert isinstance(anchor, TrustAnchor)


def test_build_trust_anchor_missing_key_file_raises():
    with pytest.raises(RecorderError):
        main_module.build_trust_anchor(
            {
                "EVIDENCE_TRUST_PUBLIC_KEY_PATH": "/nonexistent/path.pem",
                "TENANT_ID": "tenant-1",
                "SITE_ID": "site-1",
            }
        )


def test_main_exits_cleanly_on_missing_recorder_config(monkeypatch):
    monkeypatch.delenv("RECORDER_PROTOCOL", raising=False)
    monkeypatch.delenv("RECORDER_HOST", raising=False)
    monkeypatch.delenv("RECORDER_PORT", raising=False)

    called = {}
    monkeypatch.setattr(
        main_module, "run_server", lambda *a, **k: called.setdefault("ran", True)
    )

    with pytest.raises(SystemExit):
        main_module.main()

    assert "ran" not in called


def test_main_wires_real_recorder_client_into_app(monkeypatch, tmp_path):
    key_file = tmp_path / "trust_public_key.pem"
    key_file.write_text("-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")

    monkeypatch.setenv("RECORDER_PROTOCOL", "onvif")
    monkeypatch.setenv("RECORDER_HOST", "10.0.0.5")
    monkeypatch.setenv("RECORDER_PORT", "8080")
    monkeypatch.setenv("RECORDER_CHANNEL_MAP", '{"cam-1": 1}')
    monkeypatch.setenv("EVIDENCE_TRUST_PUBLIC_KEY_PATH", str(key_file))
    monkeypatch.setenv("TENANT_ID", "tenant-1")
    monkeypatch.setenv("SITE_ID", "site-1")
    monkeypatch.setenv("EVIDENCE_API_BIND_HOST", "10.8.0.1")

    captured = {}

    def _fake_run_server(app, host, port):
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(main_module, "run_server", _fake_run_server)

    main_module.main()

    assert captured["host"] == "10.8.0.1"
    recorder_client = captured["app"].config["RECORDER_CLIENT"]
    assert isinstance(recorder_client, OnvifRecorderClient)
    assert captured["app"].config["TRUST_ANCHOR"] is not None
