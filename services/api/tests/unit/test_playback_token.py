"""
Unit — S2: token de playback HLS assinado + gate de tenant no serve_hls.

O token amarra a URL de playback a uma câmera e a uma janela curta. serve_hls
(público por design) valida o token no PATH; sem token válido → 403 (quando a
rota tokenizada é usada, ou quando o enforcement global está ligado).
"""
import time
from uuid import uuid4

import app.api.v1.cameras.stream_handlers as stream_handlers
import app.core.playback_token as pt

CAM_A = str(uuid4())
CAM_B = str(uuid4())


class TestPlaybackTokenUtil:
    def test_valid_token_roundtrips(self):
        tok = pt.mint_playback_token(CAM_A)
        assert pt.verify_playback_token(tok, CAM_A) is True

    def test_token_is_camera_bound(self):
        tok = pt.mint_playback_token(CAM_A)
        assert pt.verify_playback_token(tok, CAM_B) is False

    def test_expired_token_rejected(self):
        tok = pt.mint_playback_token(CAM_A, ttl_s=-10)
        assert pt.verify_playback_token(tok, CAM_A) is False

    def test_tampered_token_rejected(self):
        tok = pt.mint_playback_token(CAM_A)
        exp, _sig = tok.split(".", 1)
        forged = f"{exp}.AAAAtampered"
        assert pt.verify_playback_token(forged, CAM_A) is False

    def test_garbage_token_rejected(self):
        assert pt.verify_playback_token("not-a-token", CAM_A) is False
        assert pt.verify_playback_token("", CAM_A) is False

    def test_future_exp_not_yet_expired(self):
        exp = int(time.time()) + 60
        assert pt.verify_playback_token(pt.mint_playback_token(CAM_A, 60), CAM_A) is True
        assert exp  # sanity


class TestServeHlsGate:
    def _url(self, camera_id, token=None, filename="stream.m3u8"):
        if token:
            return f"/api/cameras/{camera_id}/stream/s/{token}/{filename}"
        return f"/api/cameras/{camera_id}/stream/{filename}"

    def test_tokenized_route_registered(self, app):
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert "/api/cameras/<camera_id>/stream/s/<token>/<path:filename>" in rules

    def test_invalid_token_returns_403(self, client):
        resp = client.get(self._url(CAM_A, token="123.bogus"))
        assert resp.status_code == 403

    def test_token_of_other_camera_returns_403(self, client):
        tok = pt.mint_playback_token(CAM_A)
        resp = client.get(self._url(CAM_B, token=tok))
        assert resp.status_code == 403

    def test_valid_token_passes_gate(self, client, monkeypatch):
        # Força o caminho local (sem Redis real) — o gate deixa passar; downstream
        # não acha o arquivo e devolve 404. O importante: NÃO é 403.
        monkeypatch.setattr(
            stream_handlers, "_get_redis", lambda: (_ for _ in ()).throw(RuntimeError("no redis"))
        )
        tok = pt.mint_playback_token(CAM_A)
        resp = client.get(self._url(CAM_A, token=tok))
        assert resp.status_code != 403

    def test_legacy_route_open_when_not_enforced(self, client, monkeypatch):
        monkeypatch.delenv("HLS_REQUIRE_PLAYBACK_TOKEN", raising=False)
        monkeypatch.setattr(
            stream_handlers, "_get_redis", lambda: (_ for _ in ()).throw(RuntimeError("no redis"))
        )
        resp = client.get(self._url(CAM_A))
        assert resp.status_code != 403

    def test_legacy_route_blocked_when_enforced(self, client, monkeypatch):
        monkeypatch.setenv("HLS_REQUIRE_PLAYBACK_TOKEN", "1")
        resp = client.get(self._url(CAM_A))
        assert resp.status_code == 403
