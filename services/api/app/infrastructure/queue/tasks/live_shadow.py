"""
Recognition — sombra AO VIVO: mantém câmeras transmitindo e o laço consumindo.

O ao-vivo da plataforma é SOB DEMANDA: o box só transcodifica e empurra
enquanto existir `epi:stream:{camera_id}:active` no Redis de segmentos — é o
que `GET /api/v1/edge/live-view/wanted` responde ao box. Quem cria essa chave
hoje é o PLAYER humano (`stream_handlers.serve_hls`), renovando-a a cada
arquivo pedido.

Para o pipeline ver ao vivo sem ninguém com o navegador aberto, alguém precisa
ocupar esse papel. É o que esta task faz: renova a chave das câmeras da sombra
e garante um `inference_loop` consumindo cada uma.

⛔ Fica DESLIGADA sem `SHADOW_AO_VIVO_CAMERAS`. A lista é explícita de
propósito: ligar isto é fazer o box transmitir e o cliente PAGAR banda de
subida do chão de fábrica. Nada aqui começa por default — a rampa (2-4
câmeras do roteiro, medir, só então escalar) é decisão de operação, não do
código.
"""
from __future__ import annotations

import logging
import os

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

#: Mesmo TTL que o player humano usa (`stream_handlers._HLS_INACTIVITY_TTL`).
#: Duplicado e não importado: aquele módulo é de rota e puxaria Flask pro worker.
TTL_ESPECTADOR_S = int(os.environ.get("HLS_VIEWER_TTL", "90"))

#: Marca "já existe laço consumindo esta câmera". O PRÓPRIO laço a renova a
#: cada volta (ver inference_loop), então ela expirar significa laço morto —
#: e não "laço que esqueceu de avisar". É o que autoriza o redisparo.
TTL_MARCA_LACO_S = 60

CHAVE_ESPECTADOR = "epi:stream:{}:active"
CHAVE_LACO = "epi:shadow:{}:loop"


def cameras_da_sombra(env: dict | None = None) -> list[str]:
    """UUIDs em `SHADOW_AO_VIVO_CAMERAS`, separados por vírgula. Vazio = desligado."""
    fonte = env if env is not None else os.environ
    bruto = (fonte.get("SHADOW_AO_VIVO_CAMERAS") or "").strip()
    return [c.strip() for c in bruto.split(",") if c.strip()]


@celery.task(queue="inference", name="tasks.live_shadow.manter_sombra_ao_vivo")
def manter_sombra_ao_vivo() -> dict:
    """Renova o 'tem espectador' e redispara o laço que tiver morrido."""
    from app.core.segments_redis import get_segments_redis  # noqa: PLC0415

    from .inference import _FONTE_HLS_EDGE, inference_loop  # noqa: PLC0415

    cameras = cameras_da_sombra()
    if not cameras:
        return {"status": "desligado", "cameras": 0}

    r = get_segments_redis()
    renovadas, disparadas = 0, 0

    for camera_id in cameras:
        try:
            r.setex(CHAVE_ESPECTADOR.format(camera_id), TTL_ESPECTADOR_S, "1")
            renovadas += 1
        except Exception as exc:
            logger.warning("sombra_setex_falhou camera=%s err=%s", camera_id, exc)
            continue

        try:
            # `nx=True`: só dispara quem venceu a corrida. Duas batidas do beat
            # em cima uma da outra não podem virar dois laços na mesma câmera —
            # seriam dois consumidores brigando pelo mesmo segmento e o dobro
            # de inferência pelo mesmo dado.
            if r.set(CHAVE_LACO.format(camera_id), "1", nx=True, ex=TTL_MARCA_LACO_S):
                # rtsp_url vazio: a fonte HLS não usa. O parâmetro continua na
                # assinatura por retrocompatibilidade do caminho rtsp.
                inference_loop.delay(camera_id, "", fonte=_FONTE_HLS_EDGE)
                disparadas += 1
                logger.info("sombra_laco_disparado camera=%s", camera_id)
        except Exception as exc:
            logger.warning("sombra_disparo_falhou camera=%s err=%s", camera_id, exc)

    logger.info(
        "sombra_ao_vivo: cameras=%d renovadas=%d lacos_disparados=%d",
        len(cameras), renovadas, disparadas,
    )
    return {
        "status": "ok",
        "cameras": len(cameras),
        "renovadas": renovadas,
        "lacos_disparados": disparadas,
    }
