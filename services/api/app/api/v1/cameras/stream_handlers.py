"""
Recognition — Stream handlers for camera routes.

Handlers: start_stream, stop_stream, stream_status, serve_hls.
"""
import json as _json
import logging
import os
import re
import uuid as _uuid

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.playback_token import (
    mint_playback_token,
    playback_enforced,
    verify_playback_token,
)
from app.core.responses import success, error
from app.core.segments_redis import get_segments_redis

from .helpers import _get_binary_redis, _get_camera_service, _is_admin, _get_redis, _is_gateway_online

logger = logging.getLogger(__name__)

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+$')
# Aligns with HLS_INACTIVITY_TIMEOUT in local_stream_manager — watchdog kills
# streams whose active key expired.  Old default (3600s) kept streams alive for
# an hour after the last viewer left; 30s matches the watchdog intent.
_HLS_INACTIVITY_TTL = int(os.environ.get("HLS_INACTIVITY_TIMEOUT", "30"))


def _is_edge_fed_camera(camera_id: str, redis_client=None) -> bool:  # type: ignore[no-untyped-def]
    """Câmera atrás de NVR numa LAN isolada (ADR-0020), alimentada pelo edge.

    O FFmpeg roda no device edge, que empurra a playlist HLS pra
    `epi:edge_hls:{camera_id}:stream.m3u8` (TTL 20s — ver edge/routes.py e o
    bloco LV-1 abaixo, em `serve_hls`). A existência dessa chave é o sinal
    canônico de "esta câmera é servida pelo edge, não por FFmpeg local".

    Reutilizado por dois chamadores:
      - `serve_hls`, que passa o cliente Redis binário já aberto (evita abrir
        uma segunda conexão por request de segmento);
      - `start_stream` (mutirão 1.4), que não tem cliente aberto ainda e deixa
        `redis_client=None` para que a função abra o seu.
    """
    try:
        r_edge = redis_client if redis_client is not None else _get_binary_redis()
        return bool(r_edge.exists(f"epi:edge_hls:{camera_id}:stream.m3u8"))
    except Exception as exc:
        logger.debug("edge_fed_check_failed: camera=%s: %s", camera_id, exc)
        return False


# Mutirão 1.7 — par simétrico do 1.5 (upload em chunks). Tamanho arbitrário
# mas comum para chunking de resposta HTTP; não é tunável por env porque não
# há motivo operacional pra mudar (não é um limite de protocolo, só o
# tamanho de cada `yield`).
_HLS_STREAM_CHUNK_SIZE = 65536


def _iter_chunks(data: bytes, chunk_size: int = _HLS_STREAM_CHUNK_SIZE):  # type: ignore[no-untyped-def]
    """Fatia `data` (já inteiro em memória) em pedaços de `chunk_size` bytes.

    Não fatiar não seria incorreto — o conteúdo final é idêntico —, mas com
    N espectadores simultâneos pedindo o mesmo segmento, `Response(bytes)`
    força o WSGI server a manter uma cópia do buffer completo por request em
    voo. Gerar em chunks deixa o envio (não a leitura, que já é síncrona e
    veio do Redis) sair aos pedaços.
    """
    for offset in range(0, len(data), chunk_size):
        yield data[offset:offset + chunk_size]


def _stream_bytes_response(data: bytes, content_type: str):  # type: ignore[no-untyped-def]
    """Response HTTP com `data` (bytes já em memória) fatiado em chunks.

    Content-Length é preservado explicitamente: os bytes já estão todos em
    memória (vieram de um GET síncrono no Redis), então o tamanho total é
    conhecido de antemão — fatiar o ENVIO não torna o Content-Length
    desconhecido, só evita que o corpo inteiro vire uma única string grande
    passada pro Response de uma vez.
    """
    from flask import Response, stream_with_context  # noqa: PLC0415
    return Response(
        stream_with_context(_iter_chunks(data)),
        status=200,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        },
    )


@jwt_required()
def start_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Iniciar stream HLS + inferência YOLO
    security:
      - Bearer: []
    parameters:
      - in: path
        name: camera_id
        type: string
        required: true
    responses:
      200:
        description: Stream iniciado
        schema:
          properties:
            camera_id: {type: string}
            hls_url: {type: string, example: /api/cameras/{id}/stream/stream.m3u8}
            status: {type: string, example: starting}
    """
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        # task-067: live view prefers the substream (live_view_subtype) for
        # lower latency. Does not affect /api/cameras/test (connectivity
        # check), which still calls build_stream_url without for_live_view.
        rtsp_url = service.build_stream_url(UUID(camera_id), user_id, _is_admin(user_id), for_live_view=True)

        r = _get_redis()
        # epi:stream:*:active é segmento (SEGMENTS_REDIS_URL isola do Redis de
        # segurança) — client dedicado; `r` segue só para gateway health/commands.
        get_segments_redis().setex(f"epi:stream:{camera_id}:active", _HLS_INACTIVITY_TTL, "1")

        if _is_gateway_online(r):
            cmd = {
                "action": "start_stream",
                "camera_id": camera_id,
                "rtsp_url": rtsp_url,
                "hls_segment_time": int(os.environ.get("HLS_SEGMENT_TIME", "1")),
                "hls_list_size": int(os.environ.get("HLS_LIST_SIZE", "3")),
            }
            r.publish("gateway:commands", _json.dumps(cmd))
            dispatch_mode = "gateway"
            logger.info("start_stream: gateway dispatch, camera=%s", camera_id)
        elif _is_edge_fed_camera(camera_id):
            # Mutirão 1.4: câmera atrás de NVR numa LAN isolada (ADR-0020) — o
            # FFmpeg já roda no device edge e empurra os segmentos pro Redis
            # (epi:edge_hls:*, consumido por serve_hls). Disparar o
            # LocalStreamManager aqui só produziria mais um processo FFmpeg
            # condenado tentando discar RTSP através da VLAN isolada — com
            # 25 câmeras, 25 FFmpeg mortos de uma vez na abertura da grade.
            # O live view do edge não depende de FFmpeg local: serve_hls já
            # lê os segmentos direto do Redis (bloco LV-1), então basta
            # devolver a URL HLS — o player faz a primeira requisição normal.
            #
            # cloud_only (sem edge nenhum): `_is_edge_fed_camera` nunca acha a
            # chave `epi:edge_hls:*` (nada a empurrá-la), então este ramo
            # nunca é tomado e o comportamento abaixo (FFmpeg local) permanece
            # o único caminho — sem mudança de comportamento nesse modo.
            dispatch_mode = "edge"
            logger.info("start_stream: câmera edge-fed, sem FFmpeg local, camera=%s", camera_id)
        else:
            # Run FFmpeg locally so serve_hls can find /tmp/hls/ in this same container.
            # Dispatching to Celery would write to the inference container's /tmp/hls/,
            # which is invisible to the API container — causing 404 on serve_hls.
            from .local_stream_manager import LocalStreamManager  # noqa: PLC0415

            # task-067: cheap string-only computation (no I/O/FFmpeg) of the main
            # stream URL, passed as runtime fallback in case the substream isn't
            # actually configured on the camera hardware. Only used if it differs
            # from the primary URL (e.g. rtsp_url_override makes both identical).
            fallback_rtsp_url = None
            try:
                candidate = service.build_stream_url(
                    UUID(camera_id), user_id, _is_admin(user_id), subtype_override=0
                )
                if candidate != rtsp_url:
                    fallback_rtsp_url = candidate
            except EpiMonitorError:
                fallback_rtsp_url = None

            LocalStreamManager.get_instance().start(
                camera_id=camera_id, rtsp_url=rtsp_url, fallback_rtsp_url=fallback_rtsp_url
            )
            dispatch_mode = "local"
            logger.info("start_stream: local ffmpeg dispatch, camera=%s", camera_id)

        # S2: quando o enforcement está ligado, entregar URL tokenizada (o token
        # viaja no path → segmentos .ts relativos herdam o token). Default OFF
        # devolve a URL legada, sem mudar o comportamento do player atual.
        if playback_enforced():
            token = mint_playback_token(camera_id)
            hls_url = f"/api/cameras/{camera_id}/stream/s/{token}/stream.m3u8"
        else:
            hls_url = f"/api/cameras/{camera_id}/stream/stream.m3u8"

        return success({
            "camera_id": camera_id,
            "rtsp_url_validated": True,
            "hls_url": hls_url,
            "status": "starting",
            "dispatch_mode": dispatch_mode,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("start_stream_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def stop_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """Para stream de uma câmera."""
    try:
        get_segments_redis().delete(f"epi:stream:{camera_id}:active")
        try:
            _get_redis().publish("gateway:commands", _json.dumps({"action": "stop_stream", "camera_id": camera_id}))
        except Exception as exc:
            logger.warning("stop_stream_gateway_publish_failed: %s", exc)
        from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
        LocalStreamManager.get_instance().stop(camera_id)
        return success({"camera_id": camera_id, "status": "stopped"})
    except Exception as exc:
        logger.error("stop_stream_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def stream_status(camera_id: str):  # type: ignore[no-untyped-def]
    """Status em tempo real do stream."""
    try:
        r = get_segments_redis()
        active = bool(r.exists(f"epi:stream:{camera_id}:active"))
        gateway_online = _is_gateway_online(_get_redis())
        ttl = r.ttl(f"epi:stream:{camera_id}:active") if active else -1

        # Guard-rail 1: surface FFmpeg error when local process is dead
        ffmpeg_info: dict = {}  # type: ignore[type-arg]
        if not gateway_online:
            try:
                from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
                ffmpeg_info = LocalStreamManager.get_instance().status(camera_id)
            except Exception:
                pass

        return success({
            "camera_id": camera_id,
            "streaming": active,
            "gateway_online": gateway_online,
            "ttl_seconds": ttl,
            "ffmpeg_running": ffmpeg_info.get("running"),
            "ffmpeg_error": ffmpeg_info.get("stderr_tail") if not ffmpeg_info.get("running") else None,
        })
    except Exception as exc:
        logger.error("stream_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def serve_hls(camera_id: str, filename: str, token: str | None = None):  # type: ignore[no-untyped-def]
    """Serve HLS segments. No JWT — hls.js cannot send auth headers.

    Proxies to camera-gateway when it is online (FFmpeg runs there).
    Falls back to local /tmp/hls/ for single-process dev setups.

    S2 — isolamento por tenant via token de playback assinado no PATH:
      - rota tokenizada `/stream/s/<token>/<file>`: token é validado contra o
        camera_id; token inválido/expirado/de outra câmera → 403.
      - rota legada `/stream/<file>` (sem token): quando HLS_REQUIRE_PLAYBACK_TOKEN
        está ligada, exige token → 403; caso contrário (default) serve como antes
        (compat até o frontend consumir a URL tokenizada de /stream/start).
    """
    try:
        _uuid.UUID(camera_id)
    except ValueError:
        return error("Camera ID inválido", 400)
    if not _SAFE_FILENAME.match(filename):
        return error("Filename inválido", 400)

    # Gate de tenant. Este endpoint é PÚBLICO por design (hls.js não envia
    # header de auth), então o token de playback é a ÚNICA barreira: ele é
    # emitido por /stream/start e /stream/info, que validam o tenant do JWT
    # antes de assinar. Token válido == alguém do tenant certo autorizou.
    #
    # 404 (não 403) em todos os casos — C-01: responder 403 confirmaria que a
    # câmera existe pra quem só tem o UUID, que é exatamente o que um atacante
    # enumerando UUIDs quer saber. 404 não distingue "não existe" de "não é
    # sua", nem de "seu token expirou".
    if token is not None:
        if not verify_playback_token(token, camera_id):
            logger.warning("serve_hls: token de playback inválido camera=%s", camera_id)
            return error("Stream não disponível", 404)
    elif playback_enforced():
        logger.warning("serve_hls: acesso sem token com enforcement ligado camera=%s", camera_id)
        return error("Stream não disponível", 404)

    # Mutirão 1.1 (cold start / deadlock do live view): pedir a playlist É a
    # declaração de que existe espectador. Renovar/criar a chave :active AQUI,
    # incondicionalmente e ANTES de qualquer decisão de fonte (edge_fed /
    # gateway / local) — sem ela, GET /api/v1/edge/live-view/wanted nunca
    # inclui a câmera e o edge nunca transcodifica. Antes desta mudança, a
    # chave só nascia como efeito colateral do lazy-start local (linha ~330),
    # que falha para câmeras edge/VLAN isolada — causando 404 perpétuo.
    # Posicionado após o gate de token (linha acima) para que, com
    # HLS_REQUIRE_PLAYBACK_TOKEN ligado, um request não autorizado não acorde
    # o stream.
    #
    # Mutirão 1.6: epi:stream:*:active é chave de segmento (SEGMENTS_REDIS_URL
    # isola do Redis de segurança) — client dedicado.
    try:
        get_segments_redis().setex(f"epi:stream:{camera_id}:active", _HLS_INACTIVITY_TTL, "1")
    except Exception as exc:
        logger.debug("serve_hls_active_key_setex_failed: camera=%s: %s", camera_id, exc)

    # LV-1 (live view via push do edge): câmera atrás de NVR numa LAN isolada
    # (ADR-0020) — a nuvem nunca alcança a câmera direto, então o edge roda o
    # FFmpeg e empurra os segmentos pra POST /api/v1/edge/live-view/<id>/segment
    # (edge/routes.py). Checado ANTES do proxy/LocalStreamManager: se o edge
    # está empurrando, é a fonte autoritativa — tentar LocalStreamManager
    # também é inofensivo (falha silenciosa em background, RTSP inalcançável),
    # mas não precisa ser esperado.
    edge_fed = False
    try:
        _r_edge = _get_binary_redis()
        edge_content = _r_edge.get(f"epi:edge_hls:{camera_id}:{filename}")
        # A existência da playlist do edge (mutirão 1.4 — mesma checagem
        # `_is_edge_fed_camera` reutilizada por `start_stream`) é o sinal de
        # "esta câmera é alimentada pelo edge". Curto-circuito: se o segmento
        # pedido já veio, nem precisa checar a playlist.
        edge_fed = edge_content is not None or _is_edge_fed_camera(camera_id, _r_edge)
    except Exception as exc:
        logger.debug("serve_hls_edge_check_failed: %s", exc)
        edge_content = None
    if edge_content is not None:
        # Renovação da chave :active já aconteceu incondicionalmente acima
        # (Mutirão 1.1) — nada a repetir aqui.
        #
        # Mutirão 1.7 (par simétrico do 1.5, upload em chunks): o segmento já
        # veio inteiro pra memória (GET no Redis), então não há I/O a
        # economizar aqui — o ganho é não duplicar esse buffer por
        # espectador simultâneo no envio. Content-Length é conhecido de
        # antemão (len(edge_content)), então o corpo entregue ao player é
        # bit-a-bit idêntico ao anterior; só o envio é fatiado.
        return _stream_bytes_response(edge_content, content_type=(
            "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
        ))

    # Try gateway proxy first (production: separate containers)
    try:
        r = _get_redis()
        if _is_gateway_online(r):
            gateway_url = os.environ.get(
                "GATEWAY_INTERNAL_URL", "http://camera-gateway.railway.internal:8080"
            )
            import requests as _requests
            resp = _requests.get(
                f"{gateway_url}/hls/{camera_id}/{filename}",
                timeout=5,
                stream=True,
            )
            if resp.status_code == 200:
                from flask import Response
                headers = {}
                ct = resp.headers.get("Content-Type")
                if ct:
                    headers["Content-Type"] = ct
                return Response(
                    resp.iter_content(chunk_size=8192),
                    status=200,
                    headers=headers,
                )
    except Exception as exc:
        logger.debug("serve_hls_proxy_failed: %s", exc)

    # Fallback: local filesystem (dev or co-located FFmpeg)
    # Renew activity key so the watchdog keeps this stream alive while a viewer is watching.
    #
    # task-068 (defense in depth): if the stream is already known to be stalled
    # (segment sequence stuck — see LocalStreamManager._check_stall, the primary
    # detection mechanism run by the watchdog), skip renewing the TTL. A client
    # stuck polling a dead stream must not keep it "active" forever — that was
    # exactly the GR-2 bug this task fixes. The watchdog kills the process on its
    # own cadence regardless of this skip; this only avoids masking the stall.
    try:
        from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
        _stalled = LocalStreamManager.get_instance().is_stalled(camera_id)
    except Exception:
        _stalled = False

    if not _stalled:
        try:
            _inactivity_timeout = int(os.environ.get("HLS_INACTIVITY_TIMEOUT", "30"))
            r_local = get_segments_redis()
            r_local.setex(f"epi:stream:{camera_id}:active", _inactivity_timeout, "1")
        except Exception:
            pass  # Redis unavailable — watchdog will eventually time out

    hls_dir = f"/tmp/hls/{camera_id}"
    hls_path = os.path.join(hls_dir, filename)

    # serve_hls is unauthenticated (hls.js can't send auth headers).
    # send_from_directory raises werkzeug.exceptions.NotFound — not FileNotFoundError —
    # so we must check with os.path.isfile() before attempting to serve.
    if os.path.isfile(hls_path):
        from flask import send_from_directory
        return send_from_directory(hls_dir, filename)

    # Câmera alimentada pelo EDGE: nunca dispare o FFmpeg da nuvem.
    #
    # A câmera está atrás do NVR numa LAN isolada (ADR-0020) — o RTSP é
    # inalcançável daqui e o lazy-start abaixo só produz processo condenado
    # ("Connection to tcp://...:554 failed: Connection timed out"), um por
    # request de segmento, além de armar o watchdog que depois faz
    # `local_stream_cleaned` em /tmp/hls/{camera_id}.
    #
    # (Os segmentos do edge vivem no REDIS, não em /tmp/hls/, então essa
    # limpeza nunca chegou a apagar stream bom — mas o processo inútil e o
    # ruído de log são reais.)
    #
    # 425 diz ao player "tenta de novo já já", que é a verdade: o segmento
    # pedido ainda não chegou do edge ou já saiu da janela de TTL.
    if edge_fed:
        from flask import Response  # noqa: PLC0415
        logger.debug(
            "serve_hls_edge_fed_miss: camera=%s file=%s (sem lazy-start local)",
            camera_id, filename,
        )
        return Response("Aguardando segmento do edge", status=425, headers={"Retry-After": "1"})

    # GR-6a — Lazy-start: auto-start FFmpeg on first .m3u8 request.
    # The camera_id UUID was served via a JWT-authenticated request, so the caller
    # has already proved ownership. The ownership re-check is intentionally skipped here.
    _lazy_started = False
    try:
        from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
        mgr = LocalStreamManager.get_instance()
        if not mgr.is_running(camera_id):
            try:
                from uuid import UUID as _UUID  # noqa: PLC0415
                from app.domain.services.camera_service import CameraService  # noqa: PLC0415
                from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
                from app.infrastructure.database.repositories.camera_repository import CameraRepository  # noqa: PLC0415
                pool = DatabasePool.get_instance()
                if pool is not None:
                    fernet_key = os.environ.get("CAMERA_SECRET_KEY", "")
                    svc = CameraService(CameraRepository(pool), fernet_key)
                    rtsp_url = svc.build_stream_url_for_lazy_start(_UUID(camera_id))

                    # task-067: cheap string-only computation (no I/O/FFmpeg) of
                    # the main stream URL as runtime fallback in case the
                    # substream isn't actually configured on the hardware.
                    fallback_rtsp_url = None
                    try:
                        candidate = svc.build_stream_url_for_lazy_start(
                            _UUID(camera_id), subtype_override=0
                        )
                        if candidate != rtsp_url:
                            fallback_rtsp_url = candidate
                    except EpiMonitorError:
                        fallback_rtsp_url = None

                    result = mgr.start(
                        camera_id=camera_id, rtsp_url=rtsp_url, fallback_rtsp_url=fallback_rtsp_url
                    )
                    _lazy_started = result.get("status") in (
                        "started", "already_starting", "already_running"
                    )
                    logger.info(
                        "serve_hls_lazy_start: camera=%s result=%s",
                        camera_id, result.get("status"),
                    )
                else:
                    logger.warning(
                        "serve_hls_lazy_start_failed: camera=%s reason=db_pool_not_initialized",
                        camera_id,
                    )
            except Exception as exc:
                logger.warning("serve_hls_lazy_start_failed: camera=%s error=%s", camera_id, exc)
        else:
            _lazy_started = True

        st = mgr.status(camera_id)
        if not st.get("running") and st.get("stderr_tail"):
            logger.warning(
                "serve_hls_ffmpeg_error: camera=%s error=%s",
                camera_id, st["stderr_tail"][-200:],
            )
    except Exception as exc:
        logger.debug("serve_hls_lazy_start_error: camera=%s: %s", camera_id, exc)

    if _lazy_started:
        # FFmpeg is initialising — tell hls.js to retry in 2 seconds.
        from flask import Response  # noqa: PLC0415
        return Response("Stream initializing", status=425, headers={"Retry-After": "2"})

    return error("Stream não disponível", 404)


@jwt_required()
def stream_info(camera_id: str):  # type: ignore[no-untyped-def]
    """
    Retorna o tipo de feed da câmera e a URL correspondente.

    Para superadmin com vídeo demo associado: type='demo_video', url=r2_url (loop MP4).
    Para todos os outros casos: type='hls', url=hls_url.

    ISOLAMENTO CRÍTICO: demo_video_service.get_for_camera() retorna None para
    qualquer role != superadmin, garantindo que clientes jamais recebam vídeos demo.
    """
    try:
        from app.core.auth import get_role
        from app.domain.services import demo_video_service

        role = get_role()

        # Módulo passado pelo frontend via ?module=fueling — evita lookup de schema
        camera_module: str | None = request.args.get("module") or None

        # Tenta obter vídeo demo (retorna None se não for superadmin)
        try:
            demo = demo_video_service.get_for_camera(camera_id, role, module=camera_module)
        except Exception as exc:
            logger.warning("stream_info_demo_check_failed camera=%s: %s", camera_id, exc)
            demo = None

        if demo:
            return success({
                "type": "demo_video",
                "url": demo["r2_url"],
                "label": demo.get("label"),
            })

        # C-01: a câmera precisa ser do tenant do token. Antes esta checagem só
        # decidia o rótulo do feed e engolia qualquer erro; agora ela também é
        # o PORTÃO que autoriza emitir o token de playback — o `serve_hls` é
        # público (hls.js não manda header), então quem valida tenant é quem
        # emite o token. Cross-tenant -> 404, nunca 403 (não vaza existência).
        from app.core.auth import get_tenant_id
        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.camera_repository import CameraRepository
        from app.infrastructure.database.repositories.edge_site_repository import EdgeSiteRepository

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.error("stream_info: db pool indisponível camera=%s", camera_id)
            return error("Serviço indisponível", 503)

        tenant_id = get_tenant_id()
        cam = CameraRepository(pool).get_by_id_and_tenant(camera_id, tenant_id)
        if cam is None:
            logger.warning(
                "stream_info: câmera fora do tenant do token camera=%s tenant=%s",
                camera_id, str(tenant_id)[:8],
            )
            return error("Câmera não encontrada", 404)

        # A6: dual-mode — site com deployment_mode='edge' ganha tipo próprio pro
        # frontend rotular o feed. Falha aqui não é fatal: cai pro 'hls' padrão.
        stream_type = "hls"
        try:
            if cam.get("site_id"):
                site = EdgeSiteRepository(pool).get_site_by_id(str(cam["site_id"]), tenant_id)
                if site and site.get("deployment_mode") == "edge":
                    stream_type = "edge_hls"
        except Exception as exc:
            logger.warning("stream_info_site_check_failed camera=%s: %s", camera_id, exc)

        # O token viaja no PATH pra que os .ts relativos da playlist o herdem
        # sem o player precisar reescrever nada.
        if playback_enforced():
            token = mint_playback_token(camera_id)
            url = f"/api/cameras/{camera_id}/stream/s/{token}/stream.m3u8"
        else:
            url = f"/api/cameras/{camera_id}/stream/stream.m3u8"

        return success({"type": stream_type, "url": url})

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("stream_info_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
