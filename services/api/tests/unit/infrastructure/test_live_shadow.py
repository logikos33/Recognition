"""Sombra ao vivo — desligada por default, sem laço duplicado, constantes travadas.

O risco que estes testes guardam não é de lógica, é de CONTA: ligar a sombra
faz o box transmitir e o cliente pagar banda de subida. Começar ligada, ou
disparar dois laços na mesma câmera, custa dinheiro de verdade no chão de
fábrica.
"""
from unittest.mock import MagicMock, patch

from app.infrastructure.queue.tasks import live_shadow


def test_desligada_sem_a_variavel():
    assert live_shadow.cameras_da_sombra({}) == []
    assert live_shadow.cameras_da_sombra({"SHADOW_AO_VIVO_CAMERAS": ""}) == []
    assert live_shadow.cameras_da_sombra({"SHADOW_AO_VIVO_CAMERAS": "   "}) == []


def test_le_a_lista_e_ignora_espaco_e_vazio():
    env = {"SHADOW_AO_VIVO_CAMERAS": " cam-a , cam-b ,, cam-c "}
    assert live_shadow.cameras_da_sombra(env) == ["cam-a", "cam-b", "cam-c"]


def test_sem_cameras_nao_toca_no_redis():
    """Desligado tem de ser desligado de verdade: nenhuma chave, nenhum
    disparo. É o estado em que o cliente não paga banda nenhuma."""
    with patch.dict("os.environ", {"SHADOW_AO_VIVO_CAMERAS": ""}, clear=False), \
         patch("app.core.segments_redis.get_segments_redis") as get_r:
        assert live_shadow.manter_sombra_ao_vivo()["status"] == "desligado"
        get_r.assert_not_called()


def test_renova_espectador_e_dispara_laco_uma_vez_so():
    r = MagicMock()
    r.set.return_value = True          # venceu o NX -> dispara
    with patch.dict("os.environ", {"SHADOW_AO_VIVO_CAMERAS": "cam-a"}, clear=False), \
         patch("app.core.segments_redis.get_segments_redis", return_value=r), \
         patch("app.infrastructure.queue.tasks.inference.inference_loop") as loop:
        out = live_shadow.manter_sombra_ao_vivo()

    r.setex.assert_called_once_with("epi:stream:cam-a:active", live_shadow.TTL_ESPECTADOR_S, "1")
    # NX é o que impede dois laços na mesma câmera
    r.set.assert_called_once_with(
        "epi:shadow:cam-a:loop", "1", nx=True, ex=live_shadow.TTL_MARCA_LACO_S
    )
    loop.delay.assert_called_once()
    assert out["renovadas"] == 1 and out["lacos_disparados"] == 1


def test_laco_ja_vivo_renova_espectador_mas_nao_dispara_de_novo():
    r = MagicMock()
    r.set.return_value = False         # marca existe -> alguém já consome
    with patch.dict("os.environ", {"SHADOW_AO_VIVO_CAMERAS": "cam-a"}, clear=False), \
         patch("app.core.segments_redis.get_segments_redis", return_value=r), \
         patch("app.infrastructure.queue.tasks.inference.inference_loop") as loop:
        out = live_shadow.manter_sombra_ao_vivo()

    r.setex.assert_called_once()        # o box tem de continuar transmitindo
    loop.delay.assert_not_called()      # mas sem um segundo consumidor
    assert out["lacos_disparados"] == 0


def test_falha_numa_camera_nao_derruba_as_outras():
    r = MagicMock()
    r.setex.side_effect = [RuntimeError("redis caiu"), None]
    r.set.return_value = True
    with patch.dict("os.environ", {"SHADOW_AO_VIVO_CAMERAS": "cam-a,cam-b"}, clear=False), \
         patch("app.core.segments_redis.get_segments_redis", return_value=r), \
         patch("app.infrastructure.queue.tasks.inference.inference_loop"):
        out = live_shadow.manter_sombra_ao_vivo()

    assert out["renovadas"] == 1        # cam-b seguiu apesar do erro em cam-a


def test_constantes_da_marca_batem_com_as_do_laco():
    """A marca é escrita pelo laço (inference) e lida pelo beat (live_shadow),
    em módulos diferentes por causa de import circular. Se os pares
    divergirem, o beat dispara laço duplicado ou nunca ressuscita — e nada
    acusa. Este teste é a costura."""
    from app.infrastructure.queue.tasks import inference

    assert inference._CHAVE_LACO_SOMBRA == live_shadow.CHAVE_LACO
    assert inference._TTL_MARCA_LACO_S == live_shadow.TTL_MARCA_LACO_S


def test_ttl_do_segmento_bate_com_o_da_rota_de_upload():
    """Mesma costura, outro par: a fonte HLS calcula idade por
    `TTL_total - ttl_restante`. Se a rota mudar o TTL e a fonte não, a
    latência EXIBIDA fica errada em silêncio."""
    from app.api.v1.edge import routes
    from app.infrastructure.queue.tasks import hls_frame_source

    assert hls_frame_source.TTL_SEGMENTO_S == routes._HLS_SEGMENT_TTL
