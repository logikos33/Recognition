"""Regressão da estabilidade do live view (queda a cada ~90s).

Dois bugs, um sintoma: a imagem caía sozinha e só voltava quando o usuário
reabria a tela.

BUG 1 — TTL do sinal de espectador curto demais
`epi:stream:{id}:active` é o sinal lido por GET /edge/live-view/wanted para
decidir se o edge transmite, e só é renovado quando o PLAYER pede um arquivo.
O TTL era o mesmo `HLS_INACTIVITY_TIMEOUT` (30s) do ócio do FFmpeg local —
dois relógios diferentes no mesmo valor. Mas o CameraPlayer tem watchdog de
stall de 14s + backoff de 1/2/5s e, nesse intervalo, chama `stopLoad()` (para
de pedir). Somado às retentativas de 425, a janela sem request passava de 30s
com a TELA ABERTA: a chave expirava, /wanted voltava vazio, o edge parava.

BUG 2 — bootstrap circular da guarda edge_fed
`_is_edge_fed_camera` decidia só pela presença de segmento no Redis. Antes do
primeiro segmento chegar não existe segmento, então concluía "não é edge-fed"
e subia um FFmpeg local que jamais conecta (RTSP em VLAN isolada, ADR-0020).
A condição dependia do estado que ela deveria produzir.
"""
from unittest.mock import MagicMock, patch

import app.api.v1.cameras.stream_handlers as sh

CAM = "eb1501db-82ad-485a-a441-5c665b4e5a28"


class TestViewerTtlSeparadoDoWatchdog:
    def test_ttl_de_espectador_cobre_o_ciclo_de_reconexao_do_player(self):
        """O pior ciclo do player (stall 14s + backoff 5s + 425s) tem que caber
        no TTL, senão o edge é desligado com a tela aberta."""
        pior_ciclo_do_player_s = 14 + 5 + 5  # stall + backoff + margem de 425
        assert sh._HLS_INACTIVITY_TTL > pior_ciclo_do_player_s

    def test_ttl_de_espectador_nao_e_o_ocio_do_ffmpeg_local(self):
        """Guard-rail do bug: os dois relógios voltaram a ser o mesmo valor?"""
        from app.api.v1.cameras import local_stream_manager as lsm

        assert sh._HLS_INACTIVITY_TTL != lsm._INACTIVITY_TIMEOUT


class TestEdgeFedBootstrap:
    """A guarda tem que reconhecer a câmera edge ANTES do primeiro segmento."""

    def test_reconhece_por_configuracao_sem_nenhum_segmento_no_redis(self):
        redis = MagicMock()
        redis.exists.return_value = 0   # nada empurrado ainda (estado frio)
        redis.get.return_value = None   # cache vazio

        with patch.object(sh, "_edge_fed_by_config", return_value=True) as cfg:
            assert sh._is_edge_fed_camera(CAM, redis) is True

        cfg.assert_called_once_with(CAM)

    def test_segmento_presente_e_atalho_e_dispensa_o_banco(self):
        redis = MagicMock()
        redis.exists.return_value = 1  # playlist do edge já está lá

        with patch.object(sh, "_edge_fed_by_config") as cfg:
            assert sh._is_edge_fed_camera(CAM, redis) is True

        cfg.assert_not_called()

    def test_camera_sem_edge_continua_usando_ffmpeg_local(self):
        """Guard-rail: site cloud_only não pode virar edge-fed por engano."""
        redis = MagicMock()
        redis.exists.return_value = 0
        redis.get.return_value = None

        with patch.object(sh, "_edge_fed_by_config", return_value=False):
            assert sh._is_edge_fed_camera(CAM, redis) is False

    def test_resultado_da_configuracao_vai_pro_cache(self):
        redis = MagicMock()
        redis.exists.return_value = 0
        redis.get.return_value = None

        with patch.object(sh, "_edge_fed_by_config", return_value=True):
            sh._is_edge_fed_camera(CAM, redis)

        redis.setex.assert_called_once()
        args = redis.setex.call_args[0]
        assert args[0] == f"epi:camera:{CAM}:edge_fed"
        assert args[2] == "1"

    def test_cache_evita_ida_ao_banco(self):
        redis = MagicMock()
        redis.exists.return_value = 0
        redis.get.return_value = b"1"

        with patch.object(sh, "_edge_fed_by_config") as cfg:
            assert sh._is_edge_fed_camera(CAM, redis) is True

        cfg.assert_not_called()

    def test_redis_fora_do_ar_nao_derruba_a_decisao(self):
        redis = MagicMock()
        redis.exists.side_effect = RuntimeError("redis down")
        redis.get.side_effect = RuntimeError("redis down")

        with patch.object(sh, "_edge_fed_by_config", return_value=True):
            assert sh._is_edge_fed_camera(CAM, redis) is True
