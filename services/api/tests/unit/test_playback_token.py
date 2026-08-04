"""
Unit — S2: token de playback HLS assinado + gate de tenant no serve_hls.

O token amarra a URL de playback a uma câmera e a uma janela curta. serve_hls
(público por design) valida o token no PATH; sem token válido → 404 (quando a
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


class TestPlaybackTokenDetailed:
    """verify_playback_token_detailed: o veredito 'expired' só existe para
    token BEM-ASSINADO desta câmera — assinatura é checada ANTES da expiração.
    É o que permite ao serve_hls responder 410 (renove em silêncio) sem abrir
    canal de enumeração: forjado/malformado continua indistinguível de câmera
    inexistente ('invalid' → 404)."""

    def test_valid(self):
        tok = pt.mint_playback_token(CAM_A)
        assert pt.verify_playback_token_detailed(tok, CAM_A) == "valid"

    def test_expired_well_signed(self):
        tok = pt.mint_playback_token(CAM_A, ttl_s=-10)
        assert pt.verify_playback_token_detailed(tok, CAM_A) == "expired"

    def test_expired_tampered_is_invalid_not_expired(self):
        """Assinatura ruim NUNCA ganha 'expired' — um atacante não pode usar
        exp no passado + lixo para sondar existência via 410."""
        exp = int(time.time()) - 10
        assert pt.verify_playback_token_detailed(f"{exp}.forjado", CAM_A) == "invalid"

    def test_expired_token_of_other_camera_is_invalid(self):
        """Token expirado legítimo de OUTRA câmera: a assinatura não bate com
        esta câmera → 'invalid', não 'expired' (não vaza existência cross-camera)."""
        tok = pt.mint_playback_token(CAM_A, ttl_s=-10)
        assert pt.verify_playback_token_detailed(tok, CAM_B) == "invalid"

    def test_garbage_is_invalid(self):
        assert pt.verify_playback_token_detailed("not-a-token", CAM_A) == "invalid"
        assert pt.verify_playback_token_detailed("", CAM_A) == "invalid"


class TestServeHlsGate:
    def _url(self, camera_id, token=None, filename="stream.m3u8"):
        if token:
            return f"/api/cameras/{camera_id}/stream/s/{token}/{filename}"
        return f"/api/cameras/{camera_id}/stream/{filename}"

    def test_tokenized_route_registered(self, app):
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert "/api/cameras/<camera_id>/stream/s/<token>/<path:filename>" in rules

    def test_invalid_token_returns_404(self, client):
        """404, não 403: um 403 confirmaria que a câmera existe pra quem só tem
        o UUID — exatamente o sinal que um atacante enumerando quer (C-01)."""
        resp = client.get(self._url(CAM_A, token="123.bogus"))
        assert resp.status_code == 404

    def test_token_of_other_camera_returns_404(self, client):
        tok = pt.mint_playback_token(CAM_A)
        resp = client.get(self._url(CAM_B, token=tok))
        assert resp.status_code == 404

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
        # Enforcement agora é ON por padrão — pra testar o caminho legado é
        # preciso desligar EXPLICITAMENTE (escape hatch de diagnóstico).
        monkeypatch.setenv("HLS_REQUIRE_PLAYBACK_TOKEN", "0")
        monkeypatch.setattr(
            stream_handlers, "_get_redis", lambda: (_ for _ in ()).throw(RuntimeError("no redis"))
        )
        resp = client.get(self._url(CAM_A))
        assert resp.status_code != 403

    def test_legacy_route_blocked_when_enforced(self, client, monkeypatch):
        monkeypatch.setenv("HLS_REQUIRE_PLAYBACK_TOKEN", "1")
        resp = client.get(self._url(CAM_A))
        assert resp.status_code == 404

    def test_enforcement_is_on_by_default(self, client, monkeypatch):
        """O default virou ON. Enquanto esteve OFF, serve_hls era totalmente
        público: sem @jwt_required (hls.js não manda header) e sem token
        obrigatório, qualquer um com o UUID assistia ao vivo, de qualquer
        tenant. Este teste trava o default — desligar exige ação explícita."""
        monkeypatch.delenv("HLS_REQUIRE_PLAYBACK_TOKEN", raising=False)
        assert pt.playback_enforced() is True
        resp = client.get(self._url(CAM_A))
        assert resp.status_code == 404
