"""CollectorLoop — motion-triggered continuous frame collector (Onda 2, task-093).

Polls each configured camera's LIVE feed via RecorderClient.capture_frame()
(task-092), runs it through MotionDetector, and on a motion trigger captures
a short burst of frames (spaced burst_interval_s apart, deduped against the
last uploaded frame) and uploads each kept frame via POST /api/v1/edge/frames
(task-089) — building the initial training pool from RVB's 2 real cameras.

No ONVIF motion events are used (task-092's investigation found none
confirmed available on RVB's Intelbras hardware) — frame-diffing is the only
signal.

Sequential per-tick polling across all configured cameras, single thread, no
per-camera concurrency — correct and simple for the pilot's 2 cameras. A
slow/hung capture_frame() call on one camera delays the others' poll tick by
up to rtsp_frame_capture's timeout (10s default); this would matter at RVB's
eventual full ~28-camera scale but is explicitly out of scope here (this is
the 2-camera shadow-mode pilot — scale is a documented future concern, not
solved speculatively).

Deliberately its OWN process (`python -m app.collector`), NOT a 5th thread in
main.py's run_daemon() — explicit product decision at Onda 2 kickoff: this
workload is bursty/CPU-heavier (JPEG decode + diff every poll tick) and
independently restartable/stoppable without touching the identity/heartbeat/
config-sync daemon. Own systemd --user unit
(deploy/edge-frame-collector.service), same Type=simple/Restart=always shape
as edge-sync-agent.service.

Per-camera "target frames reached" counters are PERSISTED across restarts
(collector_state.py, D-86): the in-memory-only counter was an acceptable
simplification for the 2-camera pilot, but at campaign scale (29 channels) a
restart mid-campaign silently re-armed every camera's quota and doubled the
collection. Counters are loaded at boot from COLLECTOR_STATE_PATH and saved
after every burst; a missing/corrupt state file degrades to zeroed counters
(collect-too-much is recoverable, blocking the boot is not).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from ..recorder_client import RecorderClient, RecorderError
from ..recorder_factory import resolve_channel_map
from .collector_state import DEFAULT_STATE_PATH, load_counts, save_counts
from .frame_uploader import FrameUploadError, upload_frame
from .motion_detector import MotionDetector, frame_diff_score
from .person_detector import PersonDetector, build_person_detector_from_env, crop_person

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
_DEFAULT_POLL_INTERVAL_S = 3.0
_DEFAULT_BURST_COUNT = 8
_DEFAULT_BURST_INTERVAL_S = 1.0
_DEFAULT_COOLDOWN_S = 30.0
_DEFAULT_TARGET_FRAMES_PER_CAMERA = 1000
_DEFAULT_MODULE_CODE = "epi"
# Much stricter than MotionDetector's own trigger threshold — burst frames
# are already time-spaced (burst_interval_s apart), this only catches a
# near-exact repeat (e.g. the scene went still mid-burst), not "similar".
_DEDUP_THRESHOLD = 2.0


class TokenSource(Protocol):
    def get_bearer(self, ttl_s: int = 300) -> str: ...


@dataclass
class _CameraState:
    detector: MotionDetector
    frames_uploaded: int = 0
    cooldown_until: float | None = None
    last_uploaded_bytes: bytes | None = None
    #: Quantos ticks o frame-diff acusou movimento — junto com frames_uploaded
    #: dá a taxa "movimento que virou pessoa", que é o que diz se o pré-filtro
    #: está bem calibrado.
    motion_ticks: int = 0


class CollectorLoop:
    """Runs the motion→burst→cooldown state machine for every configured camera."""

    def __init__(
        self,
        recorder: RecorderClient,
        camera_ids: list[str],
        api_base_url: str,
        recorder_id: str,
        token_source: TokenSource,
        http_client: Any = None,
        module_code: str = _DEFAULT_MODULE_CODE,
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        burst_count: int = _DEFAULT_BURST_COUNT,
        burst_interval_s: float = _DEFAULT_BURST_INTERVAL_S,
        cooldown_s: float = _DEFAULT_COOLDOWN_S,
        target_frames_per_camera: int = _DEFAULT_TARGET_FRAMES_PER_CAMERA,
        motion_threshold: float = MotionDetector.DEFAULT_MIN_AREA,
        upload_fn: Any = upload_frame,
        clock: Any = time.monotonic,
        person_detector: PersonDetector | None = None,
        state_path: str | None = None,
    ) -> None:
        self._recorder = recorder
        self._camera_ids = list(camera_ids)
        self._api_base_url = api_base_url
        self._recorder_id = recorder_id
        self._token_source = token_source
        self._http = http_client if http_client is not None else httpx.Client()
        self._module_code = module_code
        self._poll_interval_s = poll_interval_s
        self._burst_count = burst_count
        self._burst_interval_s = burst_interval_s
        self._cooldown_s = cooldown_s
        self._target = target_frames_per_camera
        self._upload_fn = upload_fn
        self._clock = clock
        self._person = person_detector
        # state_path=None = sem persistência (testes que não a exercitam).
        # Contadores persistidos (D-86): carregados no boot, salvos após cada
        # rajada — restart não re-arma a cota. Câmera fora do mapa atual NÃO
        # perde a contagem gravada: _persisted_counts preserva as chaves que
        # este processo não monitora e as regrava no save (câmera desativada
        # na triagem e religada depois continua de onde parou).
        self._state_path = state_path
        self._persisted_counts: dict[str, int] = (
            load_counts(state_path) if state_path else {}
        )
        self._states: dict[str, _CameraState] = {
            camera_id: _CameraState(
                detector=MotionDetector(threshold=motion_threshold),
                frames_uploaded=self._persisted_counts.get(camera_id, 0),
            )
            for camera_id in self._camera_ids
        }

    @property
    def camera_ids(self) -> list[str]:
        return list(self._camera_ids)

    # ── upload ───────────────────────────────────────────────────────────────

    def _upload(self, camera_id: str, frame_bytes: bytes) -> bool:
        try:
            bearer = self._token_source.get_bearer()
            frame_id = self._upload_fn(
                self._http,
                self._api_base_url,
                bearer,
                camera_id,
                self._recorder_id,
                frame_bytes,
                self._module_code,
                datetime.now(timezone.utc),
            )
        except FrameUploadError as exc:
            logger.warning("collector_upload_failed camera=%s err=%s", camera_id, exc)
            return False
        logger.info("collector_frame_uploaded camera=%s frame_id=%s", camera_id, frame_id)
        return True

    # ── gatilho de coleta por pessoa ─────────────────────────────────────────

    def _payload_para_upload(self, camera_id: str, frame_bytes: bytes) -> bytes | None:
        """Decide se o frame vira upload e COMO. NÃO é detecção de EPI.

        Devolve os bytes a subir, ou None pra descartar. Desfecho C (fase 1c):
        com pessoa detectada, sobe o RECORTE dela em resolução nativa, não o
        frame inteiro — 10 KB com cabeça de ~40px, contra 157 KB com ~17px do
        substream antigo.

        Sem detector (desligado, modelo ausente, erro de inferência) devolve o
        frame inteiro — degrada pro comportamento antigo (gatilho por
        movimento). Coletar demais é recuperável; não coletar durante uma falha
        silenciosa custa a janela inteira.
        """
        if self._person is None:
            return frame_bytes
        result = self._person.detect(frame_bytes)
        if result.undetermined:
            logger.warning(
                "collector_person_indeterminado camera=%s — subindo o frame "
                "inteiro (fallback pro gatilho por movimento)",
                camera_id,
            )
            return frame_bytes
        if not result.found:
            logger.debug("collector_sem_pessoa camera=%s", camera_id)
            return None
        # Maior pessoa do quadro: garante 1 upload por frame, mantendo a
        # contagem do lote previsível. Quem estiver ao fundo entra noutro
        # frame — decisão do piloto, revisível quando o lote crescer.
        maior = max(result.boxes, key=lambda b: b.h * b.w)
        try:
            recorte = crop_person(frame_bytes, maior)
        except Exception as exc:
            logger.warning(
                "collector_recorte_falhou camera=%s err=%s — subindo o frame inteiro",
                camera_id, exc,
            )
            return frame_bytes
        logger.info(
            "collector_pessoa_detectada camera=%s n=%d conf=%.2f "
            "bbox=%dx%d recorte=%dB (frame=%dB)",
            camera_id, len(result.boxes), result.max_confidence,
            maior.w, maior.h, len(recorte), len(frame_bytes),
        )
        return recorte

    # ── burst ────────────────────────────────────────────────────────────────

    def _run_burst(
        self,
        camera_id: str,
        state: _CameraState,
        first_frame: bytes,
        stop_event: threading.Event,
        first_payload: bytes | None = None,
    ) -> int:
        """*first_payload* é o recorte que o tick() já calculou pro frame que
        disparou — evita rodar a inferência duas vezes no mesmo quadro."""
        uploaded = 0
        frame = first_frame
        for i in range(self._burst_count):
            if state.frames_uploaded + uploaded >= self._target:
                break
            if i > 0:
                if stop_event.wait(timeout=self._burst_interval_s):
                    break  # shutdown requested mid-burst
                try:
                    frame = self._recorder.capture_frame(camera_id)
                except RecorderError as exc:
                    logger.warning(
                        "collector_burst_capture_failed camera=%s err=%s", camera_id, exc
                    )
                    continue
            if state.last_uploaded_bytes is not None:
                score = frame_diff_score(frame, state.last_uploaded_bytes)
                if score < _DEDUP_THRESHOLD:
                    logger.debug(
                        "collector_burst_frame_deduped camera=%s score=%.2f", camera_id, score
                    )
                    continue
            # O gate roda em CADA frame do burst, não só no que disparou: a
            # pessoa pode sair de cena no meio da rajada, e o objetivo é que
            # todo frame do pool seja anotável.
            payload = (
                first_payload
                if i == 0 and first_payload is not None
                else self._payload_para_upload(camera_id, frame)
            )
            if payload is None:
                continue
            if self._upload(camera_id, payload):
                # dedup compara o FRAME capturado, não o recorte: recortes de
                # posições diferentes teriam sempre bytes diferentes e o dedup
                # nunca pegaria a cena parada.
                state.last_uploaded_bytes = frame
                uploaded += 1
        return uploaded

    # ── main loop ────────────────────────────────────────────────────────────

    def tick(self, stop_event: threading.Event) -> None:
        now = self._clock()
        for camera_id in self._camera_ids:
            state = self._states[camera_id]
            if state.frames_uploaded >= self._target:
                continue
            if state.cooldown_until is not None and now < state.cooldown_until:
                continue
            try:
                frame = self._recorder.capture_frame(camera_id)
            except RecorderError as exc:
                logger.warning("collector_capture_failed camera=%s err=%s", camera_id, exc)
                continue
            motion = state.detector.detect(frame)
            if not motion.changed:
                # Score dos ticks que NÃO dispararam é o que permite calibrar
                # o limiar sem adivinhar (debug pra não poluir o log normal).
                logger.debug(
                    "collector_no_motion camera=%s area=%.4f", camera_id, motion.score
                )
                continue
            state.motion_ticks += 1
            logger.info(
                "collector_motion_detected camera=%s area=%.4f (limiar=%.4f)",
                camera_id, motion.score, state.detector._threshold,
            )
            # Movimento é só o pré-filtro barato. O gatilho de coleta é a
            # pessoa: sem ela, nem vale pagar a rajada (8 capturas RTSP).
            payload = self._payload_para_upload(camera_id, frame)
            if payload is None:
                # Sem cooldown aqui de propósito: cooldown depois de "movimento
                # sem gente" cegaria a câmera por 30s justamente quando alguém
                # está prestes a entrar (porta abrindo, sombra, empilhadeira).
                continue
            uploaded = self._run_burst(
                camera_id, state, frame, stop_event, first_payload=payload
            )
            state.frames_uploaded += uploaded
            if uploaded:
                self._persist_counts()
            state.cooldown_until = self._clock() + self._cooldown_s
            if state.frames_uploaded >= self._target:
                logger.info(
                    "collector_target_reached camera=%s frames_com_pessoa=%d "
                    "(ticks_com_movimento=%d)",
                    camera_id, state.frames_uploaded, state.motion_ticks,
                )

    def _persist_counts(self) -> None:
        """Grava contadores no state file (no-op sem state_path; best-effort).

        Granularidade de rajada: um crash no meio de um burst perde no máximo
        burst_count incrementos — re-coletar ≤8 frames é recuperável.
        """
        if self._state_path is None:
            return
        self._persisted_counts.update(
            {camera_id: st.frames_uploaded for camera_id, st in self._states.items()}
        )
        save_counts(self._state_path, self._persisted_counts)

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.tick(stop_event)
            stop_event.wait(timeout=self._poll_interval_s)


def build_collector_loop_from_env(
    recorder: RecorderClient,
    token_source: TokenSource,
    env: dict[str, str] | None = None,
) -> CollectorLoop:
    """Reads the same channel-map resolution recorder_factory.py uses
    (ADR-0058: cloud-polled config cache, falling back to RECORDER_CHANNEL_MAP
    in .env) — its keys ARE the camera_id list this collector monitors, no
    separate list to keep in sync. Also reads RECORDER_CLOUD_ID (the
    public.recorders UUID in the cloud DB — a different identity than
    RECORDER_HOST/PORT's edge-local connection details), EDGE_API_URL, and
    the COLLECTOR_* tuning knobs (all optional, sensible defaults)."""
    source = env if env is not None else os.environ

    channel_map, channel_map_source, _config_version = resolve_channel_map(source)
    camera_ids = list(channel_map.keys())
    if not camera_ids:
        raise ValueError(
            "Nenhuma câmera configurada: nem config polled da nuvem (ADR-0058) nem "
            "RECORDER_CHANNEL_MAP no .env definem ao menos uma câmera — o coletor "
            "usa as chaves (camera_id) como lista de câmeras a monitorar."
        )
    logger.info(
        "collector_camera_ids_source=%s cameras=%d", channel_map_source, len(camera_ids)
    )

    recorder_id = source.get("RECORDER_CLOUD_ID", "")
    if not recorder_id:
        raise ValueError(
            "RECORDER_CLOUD_ID é obrigatório (UUID do public.recorders na nuvem) "
            "— sem ele o upload não sabe a qual gravador associar o frame."
        )

    api_base_url = (source.get("EDGE_API_URL") or _DEFAULT_API_URL).rstrip("/")

    return CollectorLoop(
        recorder=recorder,
        camera_ids=camera_ids,
        api_base_url=api_base_url,
        recorder_id=recorder_id,
        token_source=token_source,
        module_code=source.get("COLLECTOR_MODULE_CODE", _DEFAULT_MODULE_CODE),
        poll_interval_s=float(
            source.get("COLLECTOR_POLL_INTERVAL_S", str(_DEFAULT_POLL_INTERVAL_S))
        ),
        burst_count=int(source.get("COLLECTOR_BURST_COUNT", str(_DEFAULT_BURST_COUNT))),
        burst_interval_s=float(
            source.get("COLLECTOR_BURST_INTERVAL_S", str(_DEFAULT_BURST_INTERVAL_S))
        ),
        cooldown_s=float(source.get("COLLECTOR_COOLDOWN_S", str(_DEFAULT_COOLDOWN_S))),
        target_frames_per_camera=int(
            source.get(
                "COLLECTOR_TARGET_FRAMES_PER_CAMERA", str(_DEFAULT_TARGET_FRAMES_PER_CAMERA)
            )
        ),
        motion_threshold=float(
            source.get("COLLECTOR_MOTION_THRESHOLD", str(MotionDetector.DEFAULT_MIN_AREA))
        ),
        person_detector=build_person_detector_from_env(env),
        state_path=source.get("COLLECTOR_STATE_PATH", DEFAULT_STATE_PATH),
    )


def log_configuracao_efetiva(loop: CollectorLoop) -> None:
    """Ecoa a config em termos humanos e grita quando ela é auto-sabotadora.

    Existe porque a MESMA família de falha já ocorreu três vezes, sempre em
    silêncio — sem erro, sem log, só coleta parada:
      1. limiar 8.0 na diferença MÉDIA contra ruído que marcava 8.19  (rajada
         infinita de quadro inútil)
      2. limiar 2.0 herdado numa variável que virou FRAÇÃO 0-1  (nunca dispara)
      3. config de encenação (alvo 17, cooldown 2s) esquecida depois do
         experimento  (para em 17 por restart, pra sempre)

    Nenhuma das três dá exceção. O runbook não resolveu — quem lê o runbook já
    sabe. Então o processo passa a dizer, toda vez que sobe, o que vai fazer.
    """
    lim = loop._states[loop.camera_ids[0]].detector._threshold if loop.camera_ids else 0.0
    logger.info(
        "collector_config alvo=%d/camera burst=%d cooldown=%.0fs poll=%.1fs "
        "limiar_movimento=%.4f cameras=%d detector=%s",
        loop._target, loop._burst_count, loop._cooldown_s, loop._poll_interval_s,
        lim, len(loop.camera_ids),
        "ligado" if loop._person is not None else "desligado",
    )
    # Estado persistido (D-86): dizer de onde a contagem partiu — "partiu de
    # zero" depois de meses de coleta é o sintoma de state file perdido.
    ja_no_alvo = sum(1 for st in loop._states.values() if st.frames_uploaded >= loop._target)
    logger.info(
        "collector_estado_persistido frames_ja_contados=%d cameras_no_alvo=%d/%d path=%s",
        sum(st.frames_uploaded for st in loop._states.values()),
        ja_no_alvo, len(loop.camera_ids), loop._state_path or "(sem persistência)",
    )
    if lim > 1.0:
        logger.error(
            "COLLECTOR_MOTION_THRESHOLD=%.2f é IMPOSSÍVEL: a métrica é fração "
            "de área (0.0-1.0), então nada vai disparar nunca. Provavelmente é "
            "o limiar antigo (diferença média, 0-255) herdado da config. "
            "Valor medido em campo: ~0.02.", lim,
        )
    if loop._target <= 20 and loop._cooldown_s <= 5:
        logger.warning(
            "config parece ser de ENCENAÇÃO (alvo=%d, cooldown=%.0fs), não de "
            "coleta contínua — a coleta vai parar em %d frames por restart. "
            "Se o experimento acabou, restaure o .env.pre-encenacao.",
            loop._target, loop._cooldown_s, loop._target,
        )
    if loop._person is None:
        logger.warning(
            "detector de pessoa DESLIGADO — o pool vai encher de quadro sem "
            "gente, que não treina EPI (COLLECTOR_PERSON_TRIGGER)",
        )
    elif not getattr(loop._person, "is_ready", True):
        # getattr defensivo: o detector é injetável, e derrubar o boot dentro
        # do próprio diagnóstico de config seria a pior falha possível aqui.
        logger.warning(
            "detector de pessoa NÃO CARREGOU — coletando pelo gatilho de "
            "movimento apenas; confira COLLECTOR_PERSON_MODEL_PATH",
        )


