"""
Recognition — Celery Tasks: Inferência ONNX + HLS Streaming.

Tasks:
  - inference_loop: Loop contínuo de inferência por câmera.
  - start_hls_stream: FFmpeg RTSP→HLS transcoding.

Detector backend selecionável via env:
  DETECTOR_BACKEND = yolox_onnx | rfdetr_onnx | ultralytics  (padrão: yolox_onnx)
  DETECTOR_MODEL_PATH = /path/to/model.onnx  (padrão: models/yolox_s.onnx)
  VIOLATION_CLASSES = no_helmet,no_vest,no_gloves  (classes que geram alerta)
  DETECTION_CONFIDENCE_THRESHOLD = 0.5
  MODEL_CACHE_DIR = /tmp/models  (cache local dos ONNX baixados do R2 — WS-A6)

Resolução de modelo efetivo por câmera (WS-A6):
  1. model_deployments ativo da câmera+módulo (registry-level)
  2. cameras.model_{module}_id (override direto na câmera)
  3. trained_models.r2_onnx_key → download p/ MODEL_CACHE_DIR (skip se existe)
  Sem deployment/modelo → fallback env acima (comportamento atual intacto).
  Invalidação de cache via canal Redis camera:model_change:{camera_id}.

Task-055a: caminho de inferência servido NÃO usa ultralytics (AGPL-3.0).
"""
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

#: Unidade do `bbox` gravado em alerts.violations — o contrato do Detector
#: (domain/detectors/base.py). Explicito no payload para a tela de evidencia
#: nao precisar adivinhar a convencao.
_BBOX_UNIDADE = "pixels_xywh_frame_original"

# ── Configuração do detector ──────────────────────────────────────────────────

_DETECTOR_BACKEND: str = os.environ.get("DETECTOR_BACKEND", "yolox_onnx")
_DETECTOR_MODEL_PATH: str = os.environ.get(
    "DETECTOR_MODEL_PATH",
    os.environ.get("YOLO_MODEL_PATH", "models/yolox_s.onnx"),
)
_DETECTION_CONFIDENCE: float = float(
    os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5")
)
# Classes que geram alerta de violação.
# Para modelos EPI: "no_helmet,no_vest,no_gloves".
# Para teste com COCO pré-treinado: setar VIOLATION_CLASSES=person.
# ⛔ NÃO é a fonte de verdade da polaridade — essa é `yolo_classes.is_violation`
# (ADR-0065), lida por `_polaridade_do_tenant`. Este set só decide quando não há
# tenant resolvido, e o default abaixo é da era COCO: `no_helmet/no_vest/
# no_gloves` não existem na taxonomia de nenhum cliente real (no RVB as classes
# de ausência começam com "Sem "). A variável não está setada em nenhum serviço,
# e enquanto ela decidia sozinha `has_violation` era SEMPRE falso.
_VIOLATION_CLASSES: set[str] = {
    c.strip()
    for c in os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves").split(",")
    if c.strip()
}
_INFERENCE_EVERY_N: int = int(os.environ.get("YOLO_INFERENCE_EVERY_N_FRAMES", "5"))

# Abaixo disto o alerta vai para revisão por IA. Mesmo nome de env que o
# socket_bridge usava antes de #132 — o comportamento migrou de lugar, não de
# configuração.
_VERIFICATION_THRESHOLD: float = float(os.environ.get("VERIFICATION_THRESHOLD", "0.85"))

# ── Auto-captura de frames de treino (WS-B3) ──────────────────────────────────
# Feature flags por tenant (tenants.feature_flags JSONB, mesmo padrão do
# módulo fueling — ver FUELING_MOCK_FLAG em api/v1/fueling/routes.py), com
# fallback env global.
_AUTO_CAPTURE_ENABLED_FLAG = "auto_capture_enabled"
_AUTO_CAPTURE_DAILY_CAP_FLAG = "auto_capture_daily_cap"
_AUTO_CAPTURE_RATE_LIMIT_TTL = 86400  # 24h — janela do teto diário
_AUTO_CAPTURE_DEDUP_TTL_SECONDS = int(os.environ.get("AUTO_CAPTURE_DEDUP_TTL_SECONDS", "30"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_redis_client():
    import redis  # noqa: PLC0415
    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )


def _is_stream_active(camera_id: str, r) -> bool:
    return bool(r.exists(f"epi:stream:{camera_id}:active"))


#: Polaridade por tenant, com TTL curto. {tenant: (expira_em, violacao, presenca)}
_polaridade_cache: dict[str, tuple[float, frozenset[str], frozenset[str]]] = {}
_POLARIDADE_TTL_S = 300.0
#: Classes já reportadas como sem polaridade — avisa uma vez por nome.
_sem_polaridade_avisadas: set[str] = set()


def _polaridade_do_tenant(pool, tenant_id: str, module_code: str | None):
    """(violação, presença) do tenant — de `yolo_classes`, a fonte da ADR-0065.

    TTL de 5 min: polaridade é decisão de taxonomia, muda raramente, e um
    admin que virar uma classe vê o efeito no próximo ciclo sem precisar de
    restart do worker.

    Falha de leitura NÃO vira "nada é violação" — devolve o último valor bom
    se houver, e (vazio, vazio) só quando nunca leu. Quem chama trata vazio
    como "não sei".
    """
    import time  # noqa: PLC0415

    agora = time.monotonic()
    cache = _polaridade_cache.get(tenant_id)
    if cache and cache[0] > agora:
        return cache[1], cache[2]

    from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
        AlertRepository,
    )

    try:
        repo = AlertRepository(pool)
        violacao = frozenset(repo.violation_class_names(tenant_id, module_code))
        presenca = frozenset(repo.presence_class_names(tenant_id, module_code))
    except Exception as exc:
        logger.error(
            "polaridade_leitura_falhou: tenant=%s modulo=%s err=%s — mantendo "
            "o último valor conhecido; sem ele nenhuma classe é decidida",
            tenant_id, module_code, exc,
        )
        return (cache[1], cache[2]) if cache else (frozenset(), frozenset())

    _polaridade_cache[tenant_id] = (agora + _POLARIDADE_TTL_S, violacao, presenca)
    return violacao, presenca


def _polaridade_da_camera(camera_id: str):
    """(violação, presença, tenant, módulo) da câmera. violação=None ⇒ sem tenant.

    Um único ponto de resolução para as DUAS decisões que dependem de
    polaridade — criar o alerta e enfileirar a verificação. Elas já divergiram
    antes (uma usava `class.startswith("no_")`, a outra o env) e o alerta
    nascia por uma regra e era verificado por outra.
    """
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        return None, None, None, None
    tenant_id, module_code = _camera_tenant_module(pool, camera_id)
    if not tenant_id:
        return None, None, None, None
    violacao, presenca = _polaridade_do_tenant(pool, tenant_id, module_code)
    return violacao, presenca, tenant_id, module_code


#: Regras de persistência por tenant, com TTL curto — mesmo padrão da
#: polaridade. {tenant: (expira_em, {classe_lower: (min_ocorrencias, janela_s)})}
_regras_cache: dict[str, tuple[float, dict[str, tuple[int, int]]]] = {}
_REGRAS_TTL_S = 300.0

#: Janela padrão quando a regra define `min_occurrences` mas não a janela.
_JANELA_PADRAO_S = 30


def _regras_de_persistencia(pool, tenant_id: str) -> dict[str, tuple[int, int]]:
    """`{classe: (min_ocorrências, janela_s)}` de `alert_rules`, por tenant.

    Só entram regras HABILITADAS e com `min_occurrences > 1` — uma regra que
    exige uma ocorrência é o comportamento de sempre e não precisa de contador.

    ⚠️ Estado do cadastro em 25/08: a tabela tem 3.270 linhas e TODAS as
    semeadas são `no_helmet`/`no_vest`, a taxonomia de demonstração da era COCO
    — inclusive as do RVB. Nenhuma casa com classe real, então hoje este mapa
    sai vazio para todo mundo e o comportamento fica idêntico ao anterior.
    Isso é deliberado: o mecanismo entra PRONTO, e ligar por classe é criar a
    regra com o nome que o modelo realmente emite.
    """
    import time  # noqa: PLC0415

    agora = time.monotonic()
    cache = _regras_cache.get(tenant_id)
    if cache and cache[0] > agora:
        return cache[1]

    try:
        from app.infrastructure.database.repositories.base import (  # noqa: PLC0415
            BaseRepository,
        )

        linhas = BaseRepository(pool)._execute(  # noqa: SLF001
            "SELECT lower(violation_type) AS classe, min_occurrences, "
            "       time_window_seconds "
            "  FROM alert_rules "
            " WHERE tenant_id = %s AND enabled IS TRUE AND create_alert IS TRUE "
            "   AND min_occurrences IS NOT NULL AND min_occurrences > 1",
            (str(tenant_id),),
        )
    except Exception as exc:
        # Falha de leitura NÃO pode virar "exige 999 ocorrências" (silenciaria
        # tudo) nem "exige 1" sem avisar. Mantém o último valor bom e grita.
        logger.error(
            "regras_persistencia_falharam: tenant=%s err=%s — mantendo o último "
            "valor conhecido", tenant_id, exc,
        )
        return cache[1] if cache else {}

    regras = {
        r["classe"]: (
            int(r["min_occurrences"]),
            int(r["time_window_seconds"] or _JANELA_PADRAO_S),
        )
        for r in linhas
        if r.get("classe")
    }
    _regras_cache[tenant_id] = (agora + _REGRAS_TTL_S, regras)
    return regras


def _persistencia_satisfeita(
    camera_id: str, detections: list[dict], redis_client
) -> bool:
    """ADR-0067: veredito num frame só não é violação — tem de se SUSTENTAR.

    Conta ocorrências por (câmera, classe) numa janela deslizante no Redis. A
    violação só nasce quando a classe bate `min_occurrences` dentro de
    `time_window_seconds`.

    Sem regra para a classe → True (uma ocorrência basta), que é o
    comportamento histórico. O mecanismo fica PRONTO e desligado; ligar é
    cadastrar a regra.

    Falha de Redis → True. Um contador indisponível não pode APAGAR alerta:
    num produto de segurança, perder evento é o erro caro. Fail OPEN aqui é o
    oposto do fail closed do `/health` de propósito — lá a dúvida é "está
    saudável?", aqui é "houve violação?".
    """
    if not detections:
        return True

    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        return True
    tenant_id, _modulo = _camera_tenant_module(pool, camera_id)
    if not tenant_id:
        return True
    regras = _regras_de_persistencia(pool, tenant_id)
    if not regras:
        return True

    import time  # noqa: PLC0415

    algum_sem_regra = False
    for d in detections:
        classe = str(d.get("class", "")).lower()
        regra = regras.get(classe)
        if regra is None:
            algum_sem_regra = True
            continue
        minimo, janela = regra
        chave = f"epi:persist:{camera_id}:{classe}"
        try:
            agora = time.time()
            pipe = redis_client.pipeline()
            pipe.zadd(chave, {f"{agora}": agora})
            pipe.zremrangebyscore(chave, 0, agora - janela)
            pipe.zcard(chave)
            pipe.expire(chave, janela + 5)
            vistas = pipe.execute()[2]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "persistencia_redis_falhou: camera=%s classe=%s err=%s — "
                "deixando passar (perder evento é o erro caro)",
                camera_id, classe, exc,
            )
            return True
        if vistas >= minimo:
            logger.info(
                "persistencia_satisfeita: camera=%s classe=%s %d/%d em %ds",
                camera_id, classe, vistas, minimo, janela,
            )
            return True
        logger.debug(
            "persistencia_aguardando: camera=%s classe=%s %d/%d em %ds",
            camera_id, classe, vistas, minimo, janela,
        )

    # Nenhuma classe com regra bateu o mínimo. Se havia classe SEM regra, ela
    # alerta na hora — a regra é por classe, não por frame.
    return algum_sem_regra


def _has_violation(camera_id: str, detections: list[dict]) -> bool:
    """True se alguma detecção é de classe marcada como VIOLAÇÃO para o tenant.

    Antes isto lia `_VIOLATION_CLASSES`, um `set` montado da variável de
    ambiente `VIOLATION_CLASSES` com default `{no_helmet, no_vest, no_gloves}`.
    A variável não está setada em nenhum serviço, e esses três nomes não
    existem na taxonomia de nenhum cliente real (no RVB as classes de ausência
    começam com "Sem "). Resultado medido: `has_violation` era **sempre falso**,
    nenhum alerta chegava a `submit_for_verification`, e a fila de revisão
    humana ficava vazia por construção — o que a tela lia como "nada pendente".

    A polaridade tem uma fonte de verdade e é `yolo_classes.is_violation`
    (ADR-0065). O env virou apenas escape de teste, e só vale se explicitamente
    setado.

    Classe que não está NEM em violação NEM em presença é **indecidida**: não
    alerta (não inventar violação), mas avisa uma vez — uma classe que o modelo
    emite e que ninguém classificou é invisível para o produto inteiro.
    """
    if not detections:
        return False  # frame limpo não precisa consultar polaridade nenhuma

    violacao, presenca, tenant_id, module_code = _polaridade_da_camera(camera_id)
    if violacao is None:
        # Sem tenant não há polaridade possível. Cai no env SÓ se alguém o
        # setou de propósito; o default da era COCO não decide nada.
        return any(d.get("class") in _VIOLATION_CLASSES for d in detections)

    achou = False
    for d in detections:
        nome = str(d.get("class", "")).lower()
        if nome in violacao:
            achou = True
        elif nome not in presenca and nome not in _sem_polaridade_avisadas:
            _sem_polaridade_avisadas.add(nome)
            logger.warning(
                "classe_sem_polaridade: '%s' é emitida pelo modelo mas não está "
                "marcada como violação nem como conformidade em yolo_classes "
                "(tenant=%s modulo=%s) — não gera alerta e ninguém sabe disso",
                d.get("class"), tenant_id, module_code,
            )
    return achou


def _camera_tenant_module(pool, camera_id: str) -> tuple[str | None, str | None]:
    """Resolve (tenant_id, module_code) da câmera para alertas tenant-scoped.

    Best-effort: câmera não encontrada ou erro de lookup → (None, None)
    (AlertRepository.create usa defaults do schema — ajuste #8).
    """
    try:
        from app.infrastructure.database.repositories.camera_repository import (  # noqa: PLC0415
            CameraRepository,
        )

        camera = CameraRepository(pool).get_by_id(UUID(camera_id))
        if not camera:
            return None, None
        tenant_id = str(camera["tenant_id"]) if camera.get("tenant_id") else None
        module_code = camera.get("module_code") or "epi"
        return tenant_id, module_code
    except Exception as exc:
        logger.warning("camera_tenant_lookup_failed: camera=%s error=%s", camera_id, exc)
        return None, None


def _auto_capture_daily_cap(pool, tenant_id: str | None) -> int:
    """Teto diário de auto-captura por câmera (feature_flags > env, default 20)."""
    if tenant_id:
        try:
            from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
                TenantSettingsRepository,
            )
            flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
            if _AUTO_CAPTURE_DAILY_CAP_FLAG in flags:
                return max(0, int(flags[_AUTO_CAPTURE_DAILY_CAP_FLAG]))
        except Exception as exc:
            logger.warning("auto_capture_cap_read_failed: tenant=%s err=%s", tenant_id, exc)
    return max(0, int(os.environ.get("AUTO_CAPTURE_DAILY_CAP", "20")))


def _auto_capture_enabled(pool, tenant_id: str | None) -> bool:
    """Auto-captura ligada por padrão (custo marginal — reusa frame já
    decodificado pro alerta); feature_flags permite desligar por tenant."""
    if tenant_id:
        try:
            from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
                TenantSettingsRepository,
            )
            flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
            if _AUTO_CAPTURE_ENABLED_FLAG in flags:
                return bool(flags[_AUTO_CAPTURE_ENABLED_FLAG])
        except Exception as exc:
            logger.warning("auto_capture_flag_read_failed: tenant=%s err=%s", tenant_id, exc)
    return os.environ.get("AUTO_CAPTURE_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _try_reserve_auto_capture_slot(camera_id: str, cap: int) -> bool:
    """Reserva atômica de 1 slot do teto diário (INCR+EXPIRE — sem race de
    check-then-act, mesmo padrão de core/quality_video_security.py).

    cap<=0 desliga a auto-captura sem tocar Redis.
    """
    if cap <= 0:
        return False
    try:
        r = _get_redis_client()
        key = f"epi:autocapture:{camera_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, _AUTO_CAPTURE_RATE_LIMIT_TTL)
        return count <= cap
    except Exception as exc:
        logger.warning("auto_capture_rate_limit_failed: camera=%s err=%s", camera_id, exc)
        return False


def _try_acquire_auto_capture_dedup_lock(camera_id: str) -> bool:
    """Debounce (SET NX EX) por câmera — colapsa N chamadas consecutivas da
    MESMA violação em andamento (amostrada em frames consecutivos pelo
    inference_loop) em no máximo 1 captura por janela de
    _AUTO_CAPTURE_DEDUP_TTL_SECONDS. Roda ANTES do teto diário
    (_try_reserve_auto_capture_slot) pra recapturas do mesmo evento não
    consumirem reserva do teto.

    Fail-closed (mesma convenção de _try_reserve_auto_capture_slot): erro de
    Redis nega a captura — o risco aqui é custo/storage, não disponibilidade
    do stream, então negar é mais seguro que capturar sem coordenação.
    """
    try:
        r = _get_redis_client()
        key = f"epi:autocapture:dedup:{camera_id}"
        return bool(r.set(key, "1", nx=True, ex=_AUTO_CAPTURE_DEDUP_TTL_SECONDS))
    except Exception as exc:
        logger.warning("auto_capture_dedup_lock_failed: camera=%s err=%s", camera_id, exc)
        return False


def _auto_capture_frame(
    camera_id: str,
    tenant_id: str | None,
    module_code: str | None,
    frame_bytes: bytes,
    frame,
    avg_confidence: float,
    pool,
) -> None:
    """Grava o frame de violação como amostra de treino (source=auto, WS-B3).

    Best-effort: qualquer falha aqui NUNCA deve derrubar o salvamento do
    alerta (chamado depois dele, nunca antes) nem propagar exceção.
    """
    from app.constants import FrameSource, R2Prefix  # noqa: PLC0415
    from app.infrastructure.database.repositories.frame_repository import (  # noqa: PLC0415
        FrameRepository,
    )
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    try:
        if not _auto_capture_enabled(pool, tenant_id):
            return
        if not _try_acquire_auto_capture_dedup_lock(camera_id):
            logger.debug("auto_capture_dedup_skip: camera=%s", camera_id)
            return
        cap = _auto_capture_daily_cap(pool, tenant_id)
        if not _try_reserve_auto_capture_slot(camera_id, cap):
            return

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        r2_key = f"{R2Prefix.TRAINING_IMAGES}/{tenant_id or 'unknown'}/auto/{timestamp}.jpg"
        get_storage(tenant_id).upload_bytes(r2_key, frame_bytes, "image/jpeg")

        height, width = frame.shape[0], frame.shape[1]
        FrameRepository(pool).create(
            video_id=None,
            frame_number=0,
            filename=r2_key,
            source=FrameSource.AUTO,
            r2_key=r2_key,
            camera_id=UUID(camera_id),
            width=width,
            height=height,
            model_confidence=round(avg_confidence, 3),
            captured_at=datetime.utcnow(),
            tenant_id=tenant_id,
            module_code=module_code,
        )
        logger.info("auto_capture_saved: camera=%s r2_key=%s", camera_id, r2_key)
    except Exception as exc:
        logger.error("auto_capture_failed: camera=%s err=%s", camera_id, exc, exc_info=True)


def _queue_verification_if_low_confidence(
    alert_row: dict, camera_id: str, detections: list[dict], module_code: "str | None"
) -> None:
    """Enfileira a revisão por IA quando a violação é de baixa confiança.

    Mora AQUI, ao lado do único INSERT, e não mais no bridge do SocketIO: era
    lá que nascia o alerta DUPLICADO do #132 — dois processos gravando a mesma
    detecção, sem coordenação entre si.

    ⚠️ Uma diferença de comportamento que vem de graça e é conserto, não
    regressão: o bridge escolhia as violações por `class.startswith("no_")`,
    heurística que ⛔ não é a mesma coisa que `VIOLATION_CLASSES`. Com a
    configuração documentada para teste com COCO (`VIOLATION_CLASSES=person`)
    o alerta era criado por uma regra e verificado por outra. Agora as duas
    decisões usam o MESMO conjunto que decidiu que havia violação.

    Best-effort: falhar aqui ⛔ não pode desfazer o alerta que já foi gravado.
    """
    try:
        alert_id = (alert_row or {}).get("id")
        if not alert_id:
            return

        violacao, _presenca, _t, _m = _polaridade_da_camera(camera_id)
        # Mesma fonte que decidiu que havia violação (yolo_classes.is_violation).
        # Sem tenant resolvido cai no env, que só decide se alguém o setou.
        def _e_violacao(d: dict) -> bool:
            if violacao is None:
                return d.get("class") in _VIOLATION_CLASSES
            return str(d.get("class", "")).lower() in violacao

        baixa_confianca = [
            d for d in detections
            if _e_violacao(d)
            and d.get("confidence", 1.0) < _VERIFICATION_THRESHOLD
        ]
        if not baixa_confianca:
            return

        det = max(baixa_confianca, key=lambda d: d.get("confidence", 0))

        from app.infrastructure.queue.tasks.verification import verify_alert  # noqa: PLC0415

        verify_alert.delay(
            alert_id=str(alert_id),
            camera_id=camera_id,
            class_name=det.get("class", ""),
            confidence=det.get("confidence", 0.0),
            module_code=module_code or "epi",
        )
        logger.info(
            "alert_queued_for_verification: id=%s class=%s conf=%.2f",
            alert_id, det.get("class", ""), det.get("confidence", 0.0),
        )
    except Exception as exc:  # noqa: BLE001 — alerta já gravado; verificação é extra
        logger.error(
            "alert_verification_enqueue_failed: camera=%s err=%s", camera_id, exc
        )


def _save_alert(camera_id: str, detections: list[dict], frame) -> None:
    """Salva alerta: frame no storage + registro no banco (tenant-scoped).

    ÚNICO ponto do sistema que grava alerta a partir de uma detecção ao vivo
    (#132). Até agosto/2026 o `socket_bridge` também inseria, por SQL cru, na
    thread da API — a mesma detecção virava duas linhas em `alerts` sempre que
    a confiança ficava abaixo do limiar de verificação. Aquele caminho foi
    removido e o disparo de `verify_alert`, que só ele fazia, mudou para cá.

    Por ser o escritor único, é também o único lugar correto pro hook de
    auto-captura de frame de treino (WS-B3): duplicar o hook em outro caminho
    duplicaria o frame e a reserva do teto diário.
    """
    try:
        import cv2  # noqa: PLC0415

        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
        from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
            AlertRepository,
        )
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        evidence_key = f"evidence/{camera_id}/{timestamp}.jpg"

        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            logger.error("alert_frame_encode_failed: camera=%s", camera_id)
            return
        frame_bytes = buf.tobytes()

        storage = get_storage()
        storage.upload_bytes(evidence_key, frame_bytes, "image/jpeg")

        avg_confidence = (
            sum(d["confidence"] for d in detections) / len(detections)
            if detections else 0.0
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("alert_db_skip: DatabasePool not initialized")
            return

        tenant_id, module_code = _camera_tenant_module(pool, camera_id)

        alert_row = AlertRepository(pool).create(
            camera_id=UUID(camera_id),
            violations=detections,
            confidence=round(avg_confidence, 3),
            evidence_key=evidence_key,
            tenant_id=tenant_id,
            module_code=module_code,
        )
        logger.info(
            "alert_saved: camera=%s evidence=%s violations=%d",
            camera_id, evidence_key, len(detections),
        )

        _queue_verification_if_low_confidence(
            alert_row, camera_id, detections, module_code
        )

        _auto_capture_frame(
            camera_id, tenant_id, module_code, frame_bytes, frame, avg_confidence, pool,
        )
    except Exception as exc:
        logger.error("alert_save_failed: camera=%s error=%s", camera_id, exc, exc_info=True)


# ── Cache do detector (singleton por processo) ────────────────────────────────

_detector_instance = None
_detector_lock = None


def _get_detector():
    """Retorna o detector singleton para este processo (lazy init, thread-safe)."""
    global _detector_instance, _detector_lock  # noqa: PLW0603
    import threading  # noqa: PLC0415

    if _detector_lock is None:
        _detector_lock = threading.Lock()

    with _detector_lock:
        if _detector_instance is None:
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            _detector_instance = get_detector(
                backend=_DETECTOR_BACKEND,
                model_path=_DETECTOR_MODEL_PATH,
                confidence=_DETECTION_CONFIDENCE,
            )
            logger.info(
                "detector_initialized: backend=%s model=%s ready=%s",
                _DETECTOR_BACKEND, _DETECTOR_MODEL_PATH,
                _detector_instance.is_ready,
            )
    return _detector_instance


# ── Modelo efetivo por câmera (WS-A6) ─────────────────────────────────────────

_MODEL_CACHE_DIR: str = os.environ.get("MODEL_CACHE_DIR", "/tmp/models")

# Cache por processo: camera_id → {"model_id": str, "detector": Detector}.
# Invalidado via canal Redis camera:model_change:{camera_id} (publicado por
# cameras/model_handlers._notify_model_assignment e pelo model-config WS-C2).
_camera_detector_lock = threading.Lock()
_camera_detectors: dict[str, dict] = {}


def _fetch_trained_model(pool, model_id: str, tenant_id: str) -> dict | None:
    """Busca campos do registry (framework, r2_onnx_key) validando o tenant.

    Posse validada via JOIN com users — cobre linhas legadas com tenant_id
    NULL (mesmo padrão de TrainingRepository.get_model_for_tenant).

    NOTA: query local temporária — mover para TrainingRepository quando o
    cluster WS-A5 consolidar o acesso ao registry (pendência registrada).
    """
    from app.infrastructure.database.repositories.training_repository import (  # noqa: PLC0415
        TrainingRepository,
    )

    return TrainingRepository(pool)._execute_one(  # noqa: SLF001
        """
        SELECT tm.id, tm.framework, tm.r2_onnx_key, tm.model_path,
               tm.dataset_version_id
        FROM trained_models tm
        JOIN users u ON u.id = tm.user_id
        WHERE tm.id = %s AND u.tenant_id = %s
        """,
        (str(model_id), str(tenant_id)),
    )


def _taxonomia_do_modelo(pool, dataset_version_id, tenant_id: str) -> list[str] | None:
    """Nomes de classe do modelo, NA ORDEM em que ele os indexa.

    O ONNX devolve um índice inteiro; quem traduz índice→nome é o detector, a
    partir desta lista. Sem ela o detector cai em `COCO_CLASSES_91` e um modelo
    de EPI passa a chamar "Sem protetor de ouvido" de "truck": geometria certa,
    rótulo de outro domínio.

    O caminho de AVALIAÇÃO já resolvia isso (`model_evaluation`
    ._class_names_from_coco, cujo docstring descreve exatamente este perigo). O
    caminho SERVIDO não resolvia — e por isso ninguém via: o filtro de escopo
    (#519, `_no_escopo_da_camera`) compara o nome contra as classes da câmera,
    com dicionário COCO nada casa, e as detecções somem sem erro nenhum. Zero
    alertas lê igual a "não houve violação".

    A ordem é a do split de TREINO: é o diretório que o treinador leu para
    dimensionar a cabeça (`remote_train.py`, `RFDETRBase._load_classes`), logo é
    ele que define a correspondência índice→classe gravada nos pesos. `val`/
    `test` só entram como último recurso — o exportador OMITE categoria com
    zero caixas, então um split pode ter menos classes que o outro e deslocar
    tudo a partir do buraco.

    None = não deu para resolver. O caller então NÃO serve o modelo do tenant
    com um dicionário inventado.
    """
    if not dataset_version_id:
        return None

    import json as _json  # noqa: PLC0415

    from app.infrastructure.database.repositories.dataset_repository import (  # noqa: PLC0415
        DatasetRepository,
    )

    from .model_evaluation import _class_names_from_coco, _get_storage  # noqa: PLC0415

    dsv = DatasetRepository(pool).get_by_id(dataset_version_id)
    coco_key = (dsv or {}).get("coco_r2_key")
    if not coco_key:
        return None

    storage = _get_storage(tenant_id)
    for split in ("train", "val", "test"):
        try:
            bruto = storage.download_bytes(f"{coco_key}/{split}/_annotations.coco.json")
        except Exception:  # noqa: BLE001 — split ausente é normal; só o último importa
            continue
        nomes = _class_names_from_coco(_json.loads(bruto))
        if nomes:
            if split != "train":
                logger.warning(
                    "taxonomia_sem_split_train: dataset_version=%s usando '%s' — "
                    "classe com zero caixas some do export e desloca os índices",
                    dataset_version_id, split,
                )
            return nomes
    return None


def _resolve_camera_model(camera_id: str) -> dict | None:
    """Resolve o modelo efetivo da câmera (cascata WS-A6).

    1. model_deployments ativo da câmera+módulo (registry-level)
    2. cameras.model_{module}_id (override direto na câmera)
    → trained_models (framework + r2_onnx_key)

    Retorna {"model_id", "framework", "r2_onnx_key"} ou None — None faz o
    caller usar o fallback env (DETECTOR_BACKEND/DETECTOR_MODEL_PATH),
    preservando o comportamento atual quando não há deployment.
    """
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.camera_repository import (  # noqa: PLC0415
        CameraRepository,
    )
    from app.infrastructure.database.repositories.model_deployment_repository import (  # noqa: PLC0415
        ModelDeploymentRepository,
    )

    pool = DatabasePool.get_instance()
    if pool is None:
        return None

    camera = CameraRepository(pool).get_by_id(UUID(camera_id))
    if not camera or not camera.get("tenant_id"):
        return None

    tenant_id = str(camera["tenant_id"])
    module_code = str(
        camera.get("active_module") or camera.get("module_code") or "epi"
    ).strip()

    model_id: str | None = None
    deployment = ModelDeploymentRepository(pool).get_active_for_camera(
        tenant_id, UUID(camera_id), module_code
    )
    if deployment and deployment.get("model_id"):
        model_id = str(deployment["model_id"])
    else:
        column = CameraRepository.MODEL_COLUMNS.get(module_code)
        if column and camera.get(column):
            model_id = str(camera[column])

    if model_id is None:
        return None

    model = _fetch_trained_model(pool, model_id, tenant_id)
    if not model:
        logger.warning(
            "camera_model_not_found: camera=%s model=%s tenant=%s — fallback env",
            camera_id, model_id, tenant_id,
        )
        return None
    if not model.get("r2_onnx_key"):
        logger.warning(
            "camera_model_no_onnx: camera=%s model=%s — fallback env",
            camera_id, model_id,
        )
        return None

    # Sem a ordem das classes o detector rotula com COCO ("bus", "truck") e o
    # escopo abaixo descarta 100% — a câmera fica muda sem uma linha de erro.
    # Servir o modelo do tenant com dicionário de outro domínio é pior do que
    # não servir: cai para o baseline do env, que É de fato um modelo COCO.
    class_names = _taxonomia_do_modelo(
        pool, model.get("dataset_version_id"), tenant_id
    )
    if not class_names:
        logger.error(
            "camera_model_sem_taxonomia: camera=%s model=%s dataset_version=%s — "
            "recusando servir (índice viraria rótulo COCO e o escopo apagaria "
            "tudo em silêncio); fallback env",
            camera_id, model_id, model.get("dataset_version_id"),
        )
        return None

    return {
        "model_id": model_id,
        "framework": model.get("framework"),
        "r2_onnx_key": model["r2_onnx_key"],
        # Ordem índice→nome gravada nos pesos. Não confundir com "classes"
        # abaixo, que é o RECORTE escolhido pelo admin (subconjunto, sem ordem).
        "class_names": class_names,
        # Escopo de classes da câmera (#519). None = sem escopo gravado, e aí
        # nada é filtrado — não inventar restrição onde o dono não pôs nenhuma.
        "classes": _escopo_do_deployment(deployment),
    }


def _escopo_do_deployment(deployment: dict | None) -> frozenset[str] | None:
    """Classes que valem nesta câmera, de `model_deployments.config.classes`.

    Devolve None quando não há escopo gravado — e None significa "tudo passa",
    não "nada passa": um deployment sem a chave é o estado normal de quem
    nunca abriu a aba, e silenciar a câmera inteira por isso apagaria a
    detecção de 28 câmeras de uma vez.

    Lista vazia é diferente de ausente: `[]` é uma escolha explícita do dono
    ("esta câmera não reconhece nada") e é respeitada como tal.
    """
    if not deployment:
        return None
    config = deployment.get("config") or {}
    classes = config.get("classes")
    if classes is None:
        return None
    return frozenset(str(c) for c in classes)


def _ensure_local_model(model_id: str, r2_key: str) -> str:
    """Garante cópia local do ONNX em {MODEL_CACHE_DIR}/{model_id}.onnx.

    Skip se já existe (cache warm entre tasks do mesmo worker). Escrita
    atômica (tmp + os.replace) — evita leitura de download parcial por
    processos concorrentes do worker.
    """
    local_path = os.path.join(_MODEL_CACHE_DIR, f"{model_id}.onnx")
    if os.path.exists(local_path):
        return local_path

    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)
    data = get_storage().download_bytes(r2_key)
    tmp_path = f"{local_path}.{os.getpid()}.tmp"
    with open(tmp_path, "wb") as fh:
        fh.write(data)
    os.replace(tmp_path, local_path)
    logger.info(
        "model_downloaded: model=%s key=%s bytes=%d", model_id, r2_key, len(data)
    )
    return local_path


def _no_escopo_da_camera(camera_id: str, detections: list[dict]) -> list[dict]:
    """Descarta o que a câmera não reconhece (#519, primeiro elo).

    Até aqui o `config.classes` da aba "Modelos por câmera" só era lido para
    tirar o `model_id`: o admin marcava 3 classes, salvava, e o worker
    continuava alertando as 6 — a tela prometia um escopo que o pipeline não
    cumpria. O filtro fecha esse elo do lado da nuvem; o box edge ainda não
    recebe classe por câmera, e isso continua aberto no #519.

    Sem escopo gravado (None) nada é filtrado.
    """
    with _camera_detector_lock:
        cached = _camera_detectors.get(camera_id)
    escopo = cached.get("classes") if cached else None
    if escopo is None:
        return detections

    dentro = [d for d in detections if str(d.get("class")) in escopo]
    if detections and not dentro:
        # Descartar TUDO não é um escopo apertado, é quase sempre taxonomia
        # trocada: o detector rotulando em COCO ("bus") contra um escopo em
        # nomes do tenant. Era `debug`, e foi assim que a câmera muda passou
        # despercebida — zero alerta lê exatamente como "não houve violação".
        logger.warning(
            "camera_escopo_descartou_tudo: camera=%s n=%d vistas=%s escopo=%s — "
            "100%% fora costuma ser dicionário de classe errado, não turno limpo",
            camera_id, len(detections),
            sorted({str(d.get("class")) for d in detections})[:6],
            sorted(escopo)[:6],
        )
    elif len(dentro) != len(detections):
        logger.debug(
            "camera_escopo_filtrou: camera=%s de=%d para=%d",
            camera_id, len(detections), len(dentro),
        )
    return dentro


def _invalidate_camera_detector(camera_id: str) -> None:
    """Remove o detector cacheado da câmera (evento camera:model_change)."""
    with _camera_detector_lock:
        removed = _camera_detectors.pop(camera_id, None)
    if removed is not None:
        logger.info(
            "camera_detector_invalidated: camera=%s model=%s",
            camera_id, removed.get("model_id"),
        )


def _get_detector_for_camera(camera_id: str):
    """Detector efetivo da câmera (WS-A6), com cache keyed por model_id.

    Qualquer falha na cascata (sem pool, sem modelo, R2 indisponível, init
    do backend) → fallback ao singleton env (_get_detector) — zero regressão
    sobre o comportamento atual quando não há deployment.
    """
    try:
        resolved = _resolve_camera_model(camera_id)
    except Exception as exc:
        logger.warning(
            "camera_model_resolution_failed: camera=%s error=%s — fallback env",
            camera_id, exc,
        )
        resolved = None

    if resolved is None:
        return _get_detector()

    model_id = resolved["model_id"]
    with _camera_detector_lock:
        cached = _camera_detectors.get(camera_id)
        if cached is not None and cached["model_id"] == model_id:
            return cached["detector"]

        try:
            local_path = _ensure_local_model(model_id, resolved["r2_onnx_key"])
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415

            detector = get_detector(
                backend=resolved.get("framework") or _DETECTOR_BACKEND,
                model_path=local_path,
                # Sem isto o detector usa COCO_CLASSES_91 e todo rótulo sai
                # trocado — o caminho de avaliação já passava, o servido não.
                class_names=resolved.get("class_names"),
                confidence=_DETECTION_CONFIDENCE,
            )
        except Exception as exc:
            logger.error(
                "camera_detector_init_failed: camera=%s model=%s error=%s — "
                "fallback env",
                camera_id, model_id, exc, exc_info=True,
            )
            return _get_detector()

        _camera_detectors[camera_id] = {
            "model_id": model_id, "detector": detector,
            "classes": resolved.get("classes"),
        }
        logger.info(
            "camera_detector_ready: camera=%s model=%s backend=%s ready=%s",
            camera_id, model_id,
            resolved.get("framework") or _DETECTOR_BACKEND, detector.is_ready,
        )
        return detector


def _subscribe_model_change(redis_client, camera_id: str):
    """Assina camera:model_change:{camera_id}. Best-effort — None se falhar."""
    try:
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(f"camera:model_change:{camera_id}")
        return pubsub
    except Exception as exc:
        logger.warning(
            "model_change_subscribe_failed: camera=%s error=%s", camera_id, exc
        )
        return None


def _drain_model_change(pubsub) -> bool:
    """Drena mensagens pendentes do canal camera:model_change (non-blocking).

    Retorna True se houve pelo menos uma mudança de modelo publicada.
    """
    if pubsub is None:
        return False
    changed = False
    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if message is None:
                break
            if message.get("type") == "message":
                changed = True
    except Exception as exc:
        logger.warning("model_change_poll_failed: error=%s", exc)
    return changed


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery.task(
    bind=True,
    queue="inference",
    max_retries=5,
    name="tasks.inference.inference_loop",
)
def inference_loop(
    self,
    camera_id: str,
    rtsp_url: str,
    model_path: str | None = None,
) -> dict:
    """
    Loop de inferência ONNX por câmera.

    1. Resolve o detector efetivo da câmera (WS-A6: deployment ativo →
       cameras.model_{module}_id → ONNX do registry no R2), com fallback
       ao singleton env (DETECTOR_BACKEND/DETECTOR_MODEL_PATH).
    2. Conecta stream RTSP via OpenCV.
    3. A cada N frames: roda inferência (recarrega o detector se houver
       evento no canal Redis camera:model_change:{camera_id}).
    4. Publica detecções no Redis (canal det:{camera_id}).
    5. Salva alertas no banco + storage em caso de violação.
    6. Para quando a chave epi:stream:{camera_id}:active sumir do Redis.

    model_path (obsoleto): ignorado — use DETECTOR_MODEL_PATH env.
    """
    import cv2  # noqa: PLC0415
    from app.core.segments_redis import get_segments_redis  # noqa: PLC0415

    redis_client = _get_redis_client()
    # epi:stream:*:active é segmento — client dedicado (SEGMENTS_REDIS_URL
    # isola do Redis de segurança); redis_client segue para pubsub/publish
    # (camera:model_change:*, det:*), que não são chaves de segmento.
    segments_client = get_segments_redis()
    detector = _get_detector_for_camera(camera_id)
    model_change = _subscribe_model_change(redis_client, camera_id)

    logger.info(
        "inference_start: camera=%s backend=%s every_n=%d",
        camera_id, _DETECTOR_BACKEND, _INFERENCE_EVERY_N,
    )

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    frames_processed = 0

    try:
        while _is_stream_active(camera_id, segments_client):
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame_count += 1
            if frame_count % _INFERENCE_EVERY_N != 0:
                continue

            frames_processed += 1

            # Recarrega o detector se o modelo da câmera mudou (WS-A6).
            if _drain_model_change(model_change):
                _invalidate_camera_detector(camera_id)
                detector = _get_detector_for_camera(camera_id)

            detections: list[dict] = []
            has_violation = False
            # Três estados, não dois. `has_violation: false` significava tanto
            # "olhei e está tudo certo" quanto "não consegui olhar" — e a grade
            # ao vivo pintava os dois de verde. Num produto de segurança, o
            # silêncio da falha é o erro caro.
            inferencia_ok = bool(detector.is_ready)

            if detector.is_ready:
                detector.ultimo_erro = None
                detections = detector.predict(frame)
                if detector.ultimo_erro is not None:
                    # `[]` veio de exceção, não de frame limpo.
                    inferencia_ok = False
                # Carimba a UNIDADE do bbox no proprio payload. O contrato do
                # Detector (domain/detectors/base.py) e [x, y, w, h] em PIXELS
                # do frame original — mas quem le (tela de evidencia, export,
                # outro produtor) nao tem como ADIVINHAR isso olhando quatro
                # numeros: [100, 50, 40, 30] e um bbox valido em pixels e um
                # bbox invalido em normalizado, e a caixa sai no lugar errado
                # sem erro nenhum. Achado de 24/08: dois produtores gravaram
                # convencoes diferentes na mesma coluna `violations`.
                for _det in detections:
                    _det.setdefault("bbox_unidade", _BBOX_UNIDADE)
                detections = _no_escopo_da_camera(camera_id, detections)
                has_violation = _has_violation(camera_id, detections)

            payload = {
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "detections": detections,
                "has_violation": has_violation,
                # False = a inferência NÃO rodou neste frame (detector não
                # carregado ou predict falhou). Quem consome tem de mostrar
                # "sem inferência", nunca o verde de conformidade.
                "inferencia_ok": inferencia_ok,
            }
            if not inferencia_ok:
                logger.warning(
                    "inferencia_indisponivel: camera=%s pronto=%s erro=%s",
                    camera_id, detector.is_ready, detector.ultimo_erro,
                )
            redis_client.publish(f"det:{camera_id}", json.dumps(payload))

            if has_violation:
                # ADR-0067: veredito num frame não é violação — tem de se
                # sustentar. Sem regra cadastrada para a classe isto devolve
                # True e o comportamento é o de sempre.
                if _persistencia_satisfeita(camera_id, detections, redis_client):
                    _save_alert(camera_id, detections, frame)

        logger.info(
            "inference_stopped: camera=%s frames_processed=%d",
            camera_id, frames_processed,
        )
        return {
            "camera_id": camera_id,
            "frames_processed": frames_processed,
            "status": "completed",
        }

    except Exception as exc:
        logger.error("inference_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30)

    finally:
        cap.release()
        if model_change is not None:
            try:
                model_change.close()
            except Exception as exc:
                logger.warning(
                    "model_change_close_failed: camera=%s error=%s", camera_id, exc
                )


@celery.task(
    bind=True,
    queue="inference",
    name="tasks.inference.start_hls_stream",
)
def start_hls_stream(self, camera_id: str, rtsp_url: str) -> dict:
    """
    Inicia FFmpeg convertendo RTSP → HLS.
    Salva em /tmp/hls/{camera_id}/stream.m3u8
    """
    try:
        hls_dir = f"/tmp/hls/{camera_id}"
        os.makedirs(hls_dir, exist_ok=True)

        hls_segment_time = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
        hls_list_size = int(os.environ.get("HLS_LIST_SIZE", "3"))

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-f", "hls",
            "-hls_time", str(hls_segment_time),
            "-hls_list_size", str(hls_list_size),
            "-hls_flags", "delete_segments",
            f"{hls_dir}/stream.m3u8",
        ]

        logger.info("hls_stream_start: camera=%s", camera_id)
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        return {
            "camera_id": camera_id,
            "pid": process.pid,
            "hls_path": f"{hls_dir}/stream.m3u8",
            "status": "started",
        }

    except Exception as exc:
        logger.error("hls_stream_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=15)
