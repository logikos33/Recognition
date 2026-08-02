"""
Regression tests for serve_hls GR-6a lazy-start (task-059 bugfix).

Root bug: send_from_directory raises werkzeug.exceptions.NotFound (HTTP exception),
NOT FileNotFoundError. The original except FileNotFoundError: block never fired,
so lazy-start was silently skipped and the endpoint always returned plain 404.

Fix: replaced try/except with os.path.isfile() check before send_from_directory.
"""
import logging
from unittest.mock import MagicMock, patch

VALID_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# O enforcement do token de playback é ON por padrão: serve_hls é público
# (hls.js não manda header), então o token é a ÚNICA barreira de tenant.
# Os testes que exercitam OUTRO comportamento usam a URL tokenizada; os que
# testam o gate em si montam a URL na mão.
def _tokenized(camera_id: str = VALID_UUID, filename: str = "stream.m3u8") -> str:
    from app.core.playback_token import mint_playback_token
    return f"/api/cameras/{camera_id}/stream/s/{mint_playback_token(camera_id)}/{filename}"


HLS_URL = _tokenized()

# LocalStreamManager and send_from_directory are imported lazily INSIDE serve_hls,
# so they must be patched at their source module paths.
_PATCH_LSM = "app.api.v1.cameras.local_stream_manager.LocalStreamManager"
_PATCH_SEND = "flask.send_from_directory"
_PATCH_POOL = "app.infrastructure.database.connection.DatabasePool.get_instance"
_PATCH_SVC  = "app.domain.services.camera_service.CameraService"
_PATCH_REPO = "app.infrastructure.database.repositories.camera_repository.CameraRepository"


def _make_mgr(is_running: bool = False, start_status: str = "started") -> MagicMock:
    mgr = MagicMock()
    mgr.is_running.return_value = is_running
    mgr.start.return_value = {"status": start_status}
    mgr.status.return_value = {"running": True, "stderr_tail": None}
    return mgr


_PATCH_BINARY_REDIS = "app.api.v1.cameras.stream_handlers._get_binary_redis"
_PATCH_TEXT_REDIS = "app.api.v1.cameras.stream_handlers._get_redis"
# item 1.6 (mutirão): epi:stream:*:active renova via get_segments_redis(), não
# mais _get_redis() — _PATCH_TEXT_REDIS segue válido só para o path de
# gateway health/commands (que continua em _get_redis()).
_PATCH_SEGMENTS_REDIS = "app.api.v1.cameras.stream_handlers.get_segments_redis"


class TestServeHlsEdgePush:
    """LV-1: câmera atrás de NVR — edge empurra segmento pra Redis, serve_hls
    lê de lá ANTES de tentar gateway/LocalStreamManager (RTSP inalcançável
    da nuvem pra essa câmera)."""

    def test_playlist_served_from_edge_buffer_bypasses_local_stream_manager(self, client):
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"#EXTM3U\n#EXT-X-VERSION:3\n"
        redis_text = MagicMock()

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_SEGMENTS_REDIS, return_value=redis_text),
            patch(_PATCH_LSM) as mock_lsm_cls,
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200
        assert resp.data == b"#EXTM3U\n#EXT-X-VERSION:3\n"
        assert resp.headers.get("Content-Type") == "application/vnd.apple.mpegurl"
        redis_bin.get.assert_called_once_with(f"epi:edge_hls:{VALID_UUID}:stream.m3u8")
        redis_text.setex.assert_called_once()  # renews epi:stream:{id}:active
        mock_lsm_cls.get_instance.assert_not_called()

    def test_ts_segment_served_with_video_content_type(self, client):
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"\x47\x00binary-ts-bytes"

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
        ):
            resp = client.get(_tokenized(filename="segment3.ts"))

        assert resp.status_code == 200
        assert resp.data == b"\x47\x00binary-ts-bytes"
        assert resp.headers.get("Content-Type") == "video/mp2t"

    def test_no_edge_buffer_falls_through_to_local_disk_check(self, client):
        """Nada no Redis (edge não está empurrando essa câmera) — comportamento
        idêntico ao caminho pré-LV-1, sem regressão."""
        redis_bin = MagicMock()
        redis_bin.get.return_value = None

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=__import__("flask").Response("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200

    def test_edge_fed_camera_never_lazy_starts_cloud_ffmpeg(self, client):
        """Câmera atrás do NVR (LAN isolada): o RTSP é inalcançável da nuvem.
        O lazy-start só produzia processo condenado por request de segmento
        ('Connection timed out') e armava o watchdog. Segmento ausente ->
        425, que é a verdade: ainda não chegou do edge."""
        redis_bin = MagicMock()
        redis_bin.get.return_value = None          # o segmento pedido não está lá
        redis_bin.exists.return_value = 1          # ...mas a playlist do edge está
        mgr = _make_mgr()

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
        ):
            resp = client.get(_tokenized(filename="segment9.ts"))

        assert resp.status_code == 425
        assert resp.headers.get("Retry-After") == "1"
        # O que importa: NENHUM ffmpeg condenado é criado. (get_instance ainda
        # é chamado antes, pelo is_stalled da renovação de TTL — pré-existente.)
        mgr.start.assert_not_called()
        mgr.is_running.assert_not_called()

    def test_non_edge_camera_still_lazy_starts(self, client):
        """Sem playlist do edge = câmera normal (IP alcançável da nuvem):
        o caminho antigo segue intacto."""
        redis_bin = MagicMock()
        redis_bin.get.return_value = None
        redis_bin.exists.return_value = 0
        mgr = _make_mgr(is_running=True)

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 425
        mgr.is_running.assert_called()  # lazy-start foi consultado

    def test_redis_error_falls_through_gracefully(self, client):
        """Redis indisponível — não derruba a rota, só ignora o caminho edge."""
        with (
            patch(_PATCH_BINARY_REDIS, side_effect=ConnectionError("redis down")),
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=__import__("flask").Response("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200


class TestServeHlsLazyStart:
    """GR-6a: first .m3u8 request when FFmpeg is not running."""

    def test_rtsp_camera_returns_425_and_retry_after(self, client):
        """
        Falha-antes / passa-depois:
        Before fix: except FileNotFoundError never caught werkzeug.exceptions.NotFound
                    → lazy-start skipped → plain 404.
        After fix:  os.path.isfile() returns False → lazy-start runs → 425.
        """
        mgr = _make_mgr(is_running=False, start_status="started")
        mock_pool = MagicMock()
        mock_svc = MagicMock()
        mock_svc.build_stream_url_for_lazy_start.return_value = (
            "rtsp://user:pass@192.168.1.100:554/stream1"
        )

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=mock_pool),
            patch(_PATCH_SVC, return_value=mock_svc),
            patch(_PATCH_REPO, return_value=MagicMock()),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 425, (
            f"Expected 425 (lazy-start fired), got {resp.status_code}. "
            "Root cause: os.path.isfile check missing → lazy-start block unreachable."
        )
        assert resp.headers.get("Retry-After") == "2"

    def test_already_running_returns_425(self, client):
        """Stream already running in this worker but segments not yet on disk → 425."""
        mgr = _make_mgr(is_running=True)

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 425
        assert resp.headers.get("Retry-After") == "2"


class TestServeHlsFileExists:
    """When the HLS segment file is already on disk, serve it directly."""

    def test_segments_exist_returns_200(self, client):
        """os.path.isfile() → True: send_from_directory is called, lazy-start is skipped."""
        from flask import Response as _Resp

        with (
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=_Resp("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200


class TestServeHlsNoRtsp:
    """Camera without a valid RTSP URL → 404 with clear message."""

    def test_no_rtsp_camera_returns_404_with_message(self, client):
        """
        build_stream_url_for_lazy_start raises → lazy-start fails →
        404 returned with a non-empty error message (not a silent opaque 404).
        """
        from app.core.exceptions import NotFoundError

        mgr = _make_mgr(is_running=False)
        mock_pool = MagicMock()
        mock_svc = MagicMock()
        mock_svc.build_stream_url_for_lazy_start.side_effect = NotFoundError(
            "Câmera", VALID_UUID
        )

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=mock_pool),
            patch(_PATCH_SVC, return_value=mock_svc),
            patch(_PATCH_REPO, return_value=MagicMock()),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 404
        body = resp.get_json()
        assert body is not None
        assert body.get("success") is False
        assert body.get("error")  # non-empty message

    def test_pool_none_returns_404_and_logs_warning(self, client, caplog):
        """
        DatabasePool.get_instance() returns None → warning logged with
        reason=db_pool_not_initialized, and 404 returned (not a silent 404).
        """
        mgr = _make_mgr(is_running=False)

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=None),
            caplog.at_level(logging.WARNING),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 404
        assert any("db_pool_not_initialized" in r.message for r in caplog.records)


class TestServeHlsColdStartActiveKey:
    """Mutirão 1.1 — deadlock de cold start do live view.

    Bug: a chave `epi:stream:{id}:active` só nascia como efeito colateral do
    lazy-start local (bloco acima), que falha pra câmera edge/VLAN isolada
    (RTSP inalcançável da nuvem). Sem a chave, GET /api/v1/edge/live-view/wanted
    nunca inclui a câmera -> o edge nunca transcodifica -> nunca há segmento
    -> edge_fed nunca fica True -> 404 pra sempre.

    Fix: serve_hls agora renova a chave logo após o gate de token, ANTES de
    qualquer decisão de fonte (edge_fed / gateway / local) — incondicional a
    qualquer pedido de playlist legítimo, mesmo em estado frio (nenhum
    segmento em Redis, nenhum stream local ativo).
    """

    def test_cold_state_still_renews_active_key_even_on_404(self, client, caplog):
        """Falha-antes / passa-depois:
        Before fix: cold state (sem edge, sem local, lazy-start falha) nunca
                    chamava setex -> :active nunca nascia -> /wanted nunca
                    incluía a câmera.
        After fix:  setex é chamado incondicionalmente logo após o gate de
                    token, mesmo quando a resposta final ainda é 404.
        """
        redis_bin = MagicMock()
        redis_bin.get.return_value = None      # edge não empurrou nenhum segmento
        redis_bin.exists.return_value = 0      # nem a playlist do edge existe

        redis_text = MagicMock()
        # item 1.6 (mutirão): a renovação incondicional de :active (1.1) e a
        # renovação no fallback local usam get_segments_redis(), não mais
        # _get_redis() — _PATCH_TEXT_REDIS segue mockado só para o path de
        # gateway health check, atravessado antes do fallback local.
        redis_segments = MagicMock()

        mgr = _make_mgr(is_running=False)
        mgr.is_stalled.return_value = False

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=redis_text),
            patch(_PATCH_SEGMENTS_REDIS, return_value=redis_segments),
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=None),  # simula RTSP inalcançável -> lazy-start falha
            caplog.at_level(logging.WARNING),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 404
        redis_segments.setex.assert_any_call(f"epi:stream:{VALID_UUID}:active", 30, "1")


# ── gate de tenant (o token é a única barreira: serve_hls é público) ─────────


class TestServeHlsPlaybackToken:
    """serve_hls não tem @jwt_required (hls.js não envia header). Enquanto o
    enforcement esteve DESLIGADO, qualquer um com o UUID da câmera assistia ao
    vivo — de qualquer tenant, sem login. Agravante: com o live view do edge o
    Redis sempre tem segmento, então sempre havia vídeo a vazar."""

    def test_sem_token_devolve_404(self, client):
        """404 e não 403: responder 403 confirmaria que a câmera existe pra
        quem só tem o UUID — exatamente o que um atacante enumerando quer."""
        resp = client.get(f"/api/cameras/{VALID_UUID}/stream/stream.m3u8")
        assert resp.status_code == 404

    def test_token_adulterado_devolve_404(self, client):
        resp = client.get(f"/api/cameras/{VALID_UUID}/stream/s/9999999999.forjado/stream.m3u8")
        assert resp.status_code == 404

    def test_token_de_outra_camera_devolve_404(self, client):
        """Cross-tenant na prática: o token é assinado PARA um camera_id, então
        um token legítimo de outra câmera não abre esta."""
        from app.core.playback_token import mint_playback_token

        outra = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        tok = mint_playback_token(outra)
        resp = client.get(f"/api/cameras/{VALID_UUID}/stream/s/{tok}/stream.m3u8")
        assert resp.status_code == 404

    def test_token_expirado_devolve_404(self, client):
        import time as _t
        from app.core.playback_token import _sign

        exp = int(_t.time()) - 10
        tok = f"{exp}.{_sign(VALID_UUID, exp)}"
        resp = client.get(f"/api/cameras/{VALID_UUID}/stream/s/{tok}/stream.m3u8")
        assert resp.status_code == 404

    def test_token_valido_passa_do_gate(self, client):
        """Não vaza vídeo E não bloqueia quem tem direito."""
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"#EXTM3U\n"

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
        ):
            resp = client.get(_tokenized())

        assert resp.status_code == 200

    def test_enforcement_desligado_ainda_aceita_url_legada(self, client, monkeypatch):
        """Escape hatch de diagnóstico (HLS_REQUIRE_PLAYBACK_TOKEN=0). É um
        downgrade consciente de segurança — proibido em produção."""
        monkeypatch.setenv("HLS_REQUIRE_PLAYBACK_TOKEN", "0")
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"#EXTM3U\n"

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
        ):
            resp = client.get(f"/api/cameras/{VALID_UUID}/stream/stream.m3u8")

        assert resp.status_code == 200
