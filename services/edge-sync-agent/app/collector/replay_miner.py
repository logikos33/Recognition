"""ReplayMiner — DVR historical-recording miner (replay mode), Jetson-side.

Pulls RECORDED footage (not live) off the site's gravador by channel + time
window, via the SAME `RecorderClient.stream_clip()` contract the evidence API
already uses (recorder_client.py, rtsp_timestamp_recorder_client.py) — no new
RTSP transport is invented here. Frames are extracted from the clip, gated to
`person` (person_detector.py, same YOLOX-nano/Apache-2.0 gate the live
collector uses), cropped, filtered (blur + near-duplicate), and uploaded as
training frames via the SAME `POST /api/v1/edge/frames` route the live
collector already calls (frame_uploader.py) — that route already tags every
edge-originated frame `source='nvr'` server-side
(services/api/app/api/v1/edge/routes.py, `FrameSource.NVR`), so nothing here
needs to pass a "source" field.

WHY REPLAY MODE, DISTINCT FROM collector_loop.py: the live collector watches
cameras go-forward, in real time, motion-triggered. This module instead mines
the gravador's OWN recording history for a chosen set of (channel, day,
shift) windows — a one-shot campaign to backfill the training pool from
footage that already exists on the DVR, run manually by an operator, not a
long-running daemon.

ANTI-LOCKOUT (CLAUDE.md, RVB's Intelbras iNVD 3032 locks out repeated failed
auth): mirrors snapshot_executor.py's circuit breaker exactly — ANY
RecorderAuthError (401/403, detected the same way get_snapshot() does today
via `is_auth_failure_message` on ffmpeg stderr) trips `circuit_open` and ENDS
THE WHOLE run immediately, no retry, no partial continue. stream_clip() on
RtspTimestampRecorderClient does NOT itself reclassify RecorderError into
RecorderAuthError (only get_snapshot() does) — `_pull_clip_bytes` below does
that reclassification for the replay path, same heuristic, same
is_auth_failure_message() import.

DISK (ADR-0033/0045 — the Orin's 128GB is SO+app only, never a storage
target): clip bytes from stream_clip() are held in memory only long enough to
decode+crop+upload — never written to disk. `has_disk_reserve()` is a guard
against the REST of the box (buffer.db, OTA staging, logs) eating the
reserve during a long campaign; it is not guarding against this module's own
writes, which are zero by design.

CHANNEL POLICY (Vitor, decisão 15/08 — ver briefing da task): a tabela
explícita abaixo SUBSTITUI qualquer ranking automático por "quantidade já
coletada" ou heurística de cobertura — é uma decisão de produto, não um
cálculo.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from datetime import time as dtime
from enum import Enum
from typing import Any

from ..recorder_client import (
    RecorderAuthError,
    RecorderClient,
    RecorderError,
    is_auth_failure_message,
)
from ..redact import redact_bytes
from .collector_state import load_counts, save_counts
from .frame_uploader import FrameUploadError, upload_frame
from .person_detector import PersonDetector, crop_person

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = "/var/edge-sync/replay_miner_state.json"

# ---------------------------------------------------------------------------
# Channel policy — decisão do Vitor, 15/08. Ver módulo docstring: isto
# SUBSTITUI qualquer ranking automático. Mudar só com uma decisão nova.
# ---------------------------------------------------------------------------


class ChannelPolicy(str, Enum):
    FULL = "full"                  # mineração completa, sem teto de quantidade
    CEILING = "ceiling"            # minerar, mas com teto de concentração
    ABSENCE = "absence"            # fonte de exemplos de AUSÊNCIA de EPI
    EXCLUDED = "excluded"          # não extrai nada
    QUALITY_ONLY = "quality_only"  # fora do dataset EPI (módulo Qualidade)
    REDUCED = "reduced"            # captura reduzida, nunca zerada


@dataclass(frozen=True)
class ChannelRule:
    policy: ChannelPolicy
    note: str
    priority: int = 0
    # CEILING only: teto de crops para a campanha INTEIRA neste canal.
    # ponytail: proxy grosseiro por QUANTIDADE, não fração real da classe no
    # dataset todo — o miner não sabe a classe EPI do recorte (isso só existe
    # depois da anotação/classificação). Ceiling de fração por classe
    # (40-50%, conforme pedido) exige contagem total do dataset por classe,
    # que hoje não é servida de volta ao edge. Upgrade: expor
    # /api/v1/edge/training-stats com contagem por classe e recalcular aqui.
    campaign_max_crops: int | None = None
    # REDUCED only: teto de crops por JANELA pulled (não zera, so reduz).
    per_window_cap: int | None = None


_FULL_CHANNELS: dict[int, int] = {1: 100, 4: 50, 11: 50, 12: 50, 19: 50, 23: 50, 28: 50}
_EXCLUDED_CHANNELS = frozenset({13, 14, 17, 18, 22, 25})
_QUALITY_ONLY_CHANNELS = frozenset({3, 27})
_CEILING_CHANNEL = 8
_ABSENCE_CHANNEL = 10

# Canal 8: já tem 194 frames, 82% Botas / 48% Protetor auditivo (medido
# 15/08). Teto de CAMPANHA propositalmente conservador — ver campo
# campaign_max_crops acima sobre a limitação de não saber a classe aqui.
_CH8_CAMPAIGN_MAX_CROPS = 60
# 1/janela (não 2+): com o intervalo de pull default, um teto frouxo demais
# deixa REDUCED quase empatado com FULL (medido no dry-run: cap=2 dava 384
# vs FULL=466, "reduzido" só de nome). 1/janela mantém a intenção do Vitor
# ("capta menos, mas não zera") visivelmente distinta de FULL.
_REDUCED_PER_WINDOW_CAP = 1

_CHANNEL_TABLE: dict[int, ChannelRule] = {}
for _ch, _prio in _FULL_CHANNELS.items():
    _CHANNEL_TABLE[_ch] = ChannelRule(
        ChannelPolicy.FULL, "mineração completa (decisão Vitor 15/08)", priority=_prio
    )
_CHANNEL_TABLE[_CEILING_CHANNEL] = ChannelRule(
    ChannelPolicy.CEILING,
    "teto de concentração — já tem 194 frames (82% Botas, 48% Protetor "
    "auditivo); não deixar dominar nenhuma classe",
    priority=40,
    campaign_max_crops=_CH8_CAMPAIGN_MAX_CROPS,
)
_CHANNEL_TABLE[_ABSENCE_CHANNEL] = ChannelRule(
    ChannelPolicy.ABSENCE,
    "convivência — fonte de exemplos de AUSÊNCIA de EPI",
    priority=60,
)
for _ch in _EXCLUDED_CHANNELS:
    _CHANNEL_TABLE[_ch] = ChannelRule(ChannelPolicy.EXCLUDED, "excluído — não extrai nada")
for _ch in _QUALITY_ONLY_CHANNELS:
    _CHANNEL_TABLE[_ch] = ChannelRule(
        ChannelPolicy.QUALITY_ONLY, "módulo Qualidade — fora do dataset EPI"
    )


def policy_for_channel(channel: int) -> ChannelRule:
    """Canal não listado explicitamente -> REDUCED (Vitor: "capta menos
    imagem mas mantém no modelo, depois seleciono") — nunca EXCLUDED por
    omissão, só os 6 canais explicitamente listados são zerados."""
    return _CHANNEL_TABLE.get(
        channel,
        ChannelRule(
            ChannelPolicy.REDUCED,
            "não listado — captura reduzida (não zerada)",
            priority=10,
            per_window_cap=_REDUCED_PER_WINDOW_CAP,
        ),
    )


# ---------------------------------------------------------------------------
# Plano de amostragem dia x turno — espalha a campanha (task: puxar tudo de
# um dia só recria a concentração do canal 8 de outra forma).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShiftWindow:
    label: str
    start: dtime
    end: dtime
    # Intervalo entre pulls SÓ deste turno. None = usa o do minerador.
    # É o que permite um turno "leve mas nunca zero": mesma janela, menos
    # amostras — em vez de tirar a faixa do plano, que a zeraria de vez.
    pull_interval_min: float | None = None


DEFAULT_SHIFTS: tuple[ShiftWindow, ...] = (
    ShiftWindow("manha", dtime(7, 0), dtime(11, 0)),
    ShiftWindow("tarde", dtime(13, 0), dtime(17, 0)),
)

# Estratificação RVB — ladrilha 05:00→24:00 sem buraco, e deixa 00:00–05:00 de
# fora (a madrugada 01–03h não tem operação; minerar ali gasta janela do DVR
# para colher pátio vazio).
#
# O crepúsculo (17–19h) é LEVE, não ausente: foi a faixa com a MENOR mediana de
# nitidez (477 contra ~700 do resto) e a MAIOR rejeição pelo limiar de blur
# (9,2% contra 3,8% de dia) — medido em 834 recortes, D-173. Luz de transição é
# difícil, e é exatamente por isso que o modelo precisa ver essa faixa. Menos
# amostras, nunca zero.
SHIFTS_RVB: tuple[ShiftWindow, ...] = (
    ShiftWindow("dia", dtime(5, 0), dtime(17, 0)),
    ShiftWindow("crepusculo", dtime(17, 0), dtime(20, 0), pull_interval_min=60.0),
    ShiftWindow("noite", dtime(20, 0), dtime(23, 59)),
)


@dataclass(frozen=True)
class MiningTask:
    channel: int
    camera_id: str
    day: date
    shift: ShiftWindow
    rule: ChannelRule


def build_sampling_plan(
    camera_by_channel: dict[int, str],
    days: list[date],
    shifts: Iterable[ShiftWindow] = DEFAULT_SHIFTS,
) -> list[MiningTask]:
    """Um MiningTask por (canal ativo x dia x turno). Pula EXCLUDED/
    QUALITY_ONLY inteiramente (não geram task, não pesam na campanha EPI).
    Ordenado por prioridade (FULL/ABSENCE primeiro), depois canal/dia/turno —
    determinístico, para dois runs com o mesmo input gerarem o mesmo plano.
    """
    tasks: list[MiningTask] = []
    for day in days:
        for channel, camera_id in camera_by_channel.items():
            rule = policy_for_channel(channel)
            if rule.policy in (ChannelPolicy.EXCLUDED, ChannelPolicy.QUALITY_ONLY):
                continue
            for shift in shifts:
                tasks.append(MiningTask(channel, camera_id, day, shift, rule))
    tasks.sort(key=lambda t: (-t.rule.priority, t.channel, t.day, t.shift.label))
    return tasks


def _sub_windows(
    day: date, shift: ShiftWindow, clip_seconds: float, pull_interval_min: float
) -> list[tuple[datetime, datetime]]:
    """Recorta um turno em pulls curtos e espaçados (ex.: 6s a cada 20min),
    em vez de um clipe contínuo do turno inteiro — mantém cada chamada a
    stream_clip() pequena (cabe em memória, ADR-0033/0045) e amostra o turno
    inteiro em vez de só o começo."""
    shift_start = datetime.combine(day, shift.start)
    shift_end = datetime.combine(day, shift.end)
    step = timedelta(minutes=shift.pull_interval_min or pull_interval_min)
    windows = []
    cursor = shift_start
    while cursor + timedelta(seconds=clip_seconds) <= shift_end:
        windows.append((cursor, cursor + timedelta(seconds=clip_seconds)))
        cursor += step
    return windows


# ---------------------------------------------------------------------------
# Qualidade do recorte: blur (variância do Laplaciano, PIL puro — mesma
# disciplina de motion_detector.py, sem numpy/opencv) + near-duplicate
# (dHash perceptual, timeline-aware).
# ---------------------------------------------------------------------------

_LAPLACIAN_KERNEL = (0.0, 1.0, 0.0, 1.0, -4.0, 1.0, 0.0, 1.0, 0.0)
# Calibrado contra RECORTE REAL da RVB (n=224 crops active do acervo, medido
# 2026-08-17 com esta mesma blur_variance): distribuição min=56 · p05=199 ·
# p10=265 · mediana=693 · p75=1151 · max=4642. O antigo 3000.0 (só de fixtures
# sintéticos) rejeitava 220/224 = 98% de recorte real bom — DOA. Em crop JPEG
# pequeno a variância do Laplaciano tem piso de artefato de bloco (~200-950),
# então o sinal útil vive na cauda baixa: 150 derruba só ~3% (os 56-150, os
# genuinamente ilegíveis) e mantém ~97%. Mesmo espírito da calibração de campo
# do MotionDetector. Re-medir se a câmera/resolução mudar.
_DEFAULT_BLUR_VARIANCE_MIN = 150.0
_DEFAULT_DEDUP_HAMMING_MAX = 6     # de 64 bits do dHash 8x8 — "quase idêntico", não "mesmo dia"
_DEFAULT_DEDUP_WINDOW = 64         # hashes recentes mantidos por câmera (custo limitado)


def blur_variance(jpeg_bytes: bytes) -> float:
    """Variância do Laplaciano — quanto menor, mais borrado. PIL puro (sem
    numpy/opencv, mesma razão do motion_detector.py: wheel opencv-python no
    Jetson conflita com o build do JetPack)."""
    from PIL import Image, ImageFilter, ImageStat  # noqa: PLC0415

    img = Image.open(io.BytesIO(jpeg_bytes)).convert("L")
    edges = img.filter(ImageFilter.Kernel((3, 3), _LAPLACIAN_KERNEL, scale=1))
    return ImageStat.Stat(edges).var[0]


def is_blurry(jpeg_bytes: bytes, min_variance: float = _DEFAULT_BLUR_VARIANCE_MIN) -> bool:
    return blur_variance(jpeg_bytes) < min_variance


def _dhash(jpeg_bytes: bytes, hash_size: int = 8) -> int:
    """Perceptual hash (difference hash) — 64 bits pra hash_size=8. Duas
    imagens quase idênticas têm poucos bits diferentes; imagens diferentes,
    muitos (~32, aleatório)."""
    from PIL import Image  # noqa: PLC0415

    img = (
        Image.open(io.BytesIO(jpeg_bytes))
        .convert("L")
        .resize((hash_size + 1, hash_size), Image.BILINEAR)
    )
    pixels = list(img.getdata())
    bits = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            bits = (bits << 1) | (1 if pixels[offset + col] > pixels[offset + col + 1] else 0)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class NearDuplicateFilter:
    """dHash near-duplicate, por câmera, timeline-aware (recortes chegam em
    ordem de captura). Compara só contra uma janela recente de hashes JÁ
    MANTIDOS da MESMA câmera — "mesmo dia/mesma câmera" NUNCA é motivo de
    descarte por si só; só um recorte quase idêntico (poucos bits de
    diferença) é.
    """

    def __init__(
        self,
        hamming_threshold: int = _DEFAULT_DEDUP_HAMMING_MAX,
        window: int = _DEFAULT_DEDUP_WINDOW,
    ) -> None:
        self._threshold = hamming_threshold
        self._window = window
        self._recent: dict[str, list[int]] = {}

    def is_duplicate(self, camera_id: str, jpeg_bytes: bytes) -> bool:
        h = _dhash(jpeg_bytes)
        recent = self._recent.setdefault(camera_id, [])
        if any(_hamming(h, other) <= self._threshold for other in recent):
            return True
        recent.append(h)
        if len(recent) > self._window:
            del recent[0]
        return False


# ---------------------------------------------------------------------------
# Reserva de disco (ADR-0033/0045) — mesmo teto de 8GB do resto do edge
# (monitoring/store.py's _DEFAULT_MIN_FREE_GB). Guarda contra o RESTO do box
# encher o disco durante uma campanha longa; este módulo não escreve nada.
# ---------------------------------------------------------------------------

_DEFAULT_MIN_FREE_GB = 8.0


def has_disk_reserve(path: str = "/", min_free_gb: float = _DEFAULT_MIN_FREE_GB) -> bool:
    try:
        free = shutil.disk_usage(path).free
    except OSError:
        return True  # não conseguiu medir -> não bloqueia a campanha por isso
    return free >= min_free_gb * 1024**3


# ---------------------------------------------------------------------------
# Pull do clipe + extração de frames. stream_clip() (RtspTimestampRecorderClient)
# entrega MP4 fragmentado remuxado por ffmpeg (-c copy); um SEGUNDO estágio de
# ffmpeg decodifica esses bytes (via stdin, tudo em memória) em JPEGs
# amostrados a `sample_fps`. Mesmo padrão de DI (`popen` injetável) de
# rtsp_clip_stream.py/rtsp_frame_capture.py — testável sem ffmpeg real.
# ---------------------------------------------------------------------------

_DECODE_TIMEOUT_S = 30.0
_STDERR_TAIL = 500


def _pull_clip_bytes(
    recorder: RecorderClient, camera_id: str, start: datetime, end: datetime
) -> bytes:
    """Consome o Iterator[bytes] de stream_clip() inteiro (clipes curtos por
    desenho — ver _sub_windows). Reclassifica RecorderError em
    RecorderAuthError quando o texto bate 401/403 (is_auth_failure_message) —
    stream_clip() do RtspTimestampRecorderClient NÃO faz essa reclassificação
    sozinho (só get_snapshot() faz); replicado aqui para o breaker de
    anti-lockout do ReplayMiner reagir do mesmo jeito. Janela vazia (sem
    gravação) não bate nesse texto -> RecorderError comum, não trava nada."""
    try:
        return b"".join(recorder.stream_clip(camera_id, start, end))
    except RecorderAuthError:
        raise
    except RecorderError as exc:
        if is_auth_failure_message(str(exc)):
            raise RecorderAuthError(str(exc)) from exc
        raise


def _split_mjpeg(data: bytes) -> list[bytes]:
    """Corte puro por marcador JPEG SOI/EOI — sem ffmpeg, testável isolado."""
    frames: list[bytes] = []
    start = data.find(b"\xff\xd8")
    while start != -1:
        end = data.find(b"\xff\xd9", start)
        if end == -1:
            break
        end += 2
        frames.append(data[start:end])
        start = data.find(b"\xff\xd8", end)
    return frames


def extract_frames_from_clip(
    clip_bytes: bytes,
    sample_fps: float,
    popen: Any = subprocess.Popen,
    timeout_seconds: float = _DECODE_TIMEOUT_S,
) -> list[bytes]:
    """Decodifica bytes MP4 fragmentados (de stream_clip) em JPEGs amostrados
    a `sample_fps`, inteiramente em memória (ADR-0033/0045 — nunca grava em
    disco): segundo estágio ffmpeg, entrada por stdin (pipe:0), saída MJPEG
    em stdout (pipe:1), cortada por _split_mjpeg. Não é uma conexão RTSP —
    não há autenticação neste estágio (a auth já aconteceu, ou falhou, dentro
    de stream_clip/_pull_clip_bytes)."""
    if not clip_bytes:
        return []
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error",
        "-i", "pipe:0",
        "-vf", f"fps={sample_fps:.4f}",
        "-q:v", "3",
        "-f", "image2pipe", "-vcodec", "mjpeg",
        "pipe:1",
    ]
    try:
        proc = popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError as exc:
        raise RecorderError(f"ffmpeg indisponível para decodificar o clipe: {exc}") from exc

    try:
        stdout, stderr = proc.communicate(input=clip_bytes, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RecorderError(
            f"ffmpeg não respondeu em {timeout_seconds}s ao decodificar o clipe"
        ) from None

    if not stdout:
        stderr_tail = redact_bytes(stderr)[:_STDERR_TAIL] if stderr else ""
        logger.warning("replay_miner_decode_empty stderr_tail=%s", stderr_tail)
        return []
    return _split_mjpeg(stdout)


# ---------------------------------------------------------------------------
# ReplayMiner — orquestra plano -> pull -> gate de pessoa -> filtros -> upload
# ---------------------------------------------------------------------------


@dataclass
class MiningStats:
    tasks_planned: int = 0
    tasks_attempted: int = 0
    windows_pulled: int = 0
    windows_empty: int = 0
    frames_scanned: int = 0
    crops_kept: int = 0
    crops_dropped_no_person: int = 0
    crops_dropped_undetermined: int = 0
    crops_dropped_blurry: int = 0
    crops_dropped_duplicate: int = 0
    crops_dropped_cap: int = 0
    uploads_failed: int = 0
    aborted_reason: str | None = None
    per_channel_kept: dict[int, int] = field(default_factory=dict)


class TokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str: ...  # noqa: D102 — Protocol-shaped, mirrors CollectorLoop.TokenSource


class ReplayMiner:
    """Executa um MiningStats.mine(plan) inteiro. Aborta o RUN TODO (não só a
    task corrente) em: RecorderAuthError (anti-lockout) ou reserva de disco
    violada. Janela vazia (sem gravação) é normal e apenas pulada.
    """

    def __init__(
        self,
        recorder: RecorderClient,
        api_base_url: str,
        recorder_id: str,
        token_source: Any,
        person_detector: PersonDetector,
        http_client: Any = None,
        module_code: str = "epi",
        clip_seconds: float = 6.0,
        pull_interval_min: float = 20.0,
        sample_fps: float = 2.0,
        min_free_gb: float = _DEFAULT_MIN_FREE_GB,
        pacing_s: float = 4.0,
        upload_fn: Any = upload_frame,
        frame_extractor: Any = extract_frames_from_clip,
        dedup_filter: NearDuplicateFilter | None = None,
        blur_min_variance: float = _DEFAULT_BLUR_VARIANCE_MIN,
        sleep_fn: Callable[[float], None] = time.sleep,
        disk_check_fn: Callable[[], bool] | None = None,
        state_path: str | None = DEFAULT_STATE_PATH,
    ) -> None:
        self._recorder = recorder
        self._api_base_url = api_base_url
        self._recorder_id = recorder_id
        self._token_source = token_source
        self._person = person_detector
        import httpx  # noqa: PLC0415 — mesmo padrão lazy-import de CollectorLoop

        self._http = http_client if http_client is not None else httpx.Client()
        self._module_code = module_code
        self._clip_seconds = clip_seconds
        self._pull_interval_min = pull_interval_min
        self._sample_fps = sample_fps
        self._min_free_gb = min_free_gb
        self._pacing_s = pacing_s
        self._upload_fn = upload_fn
        self._extract = frame_extractor
        self._dedup = dedup_filter or NearDuplicateFilter()
        self._blur_min_variance = blur_min_variance
        self._sleep = sleep_fn
        self._disk_ok = disk_check_fn or (lambda: has_disk_reserve(min_free_gb=min_free_gb))
        self._state_path = state_path
        self._campaign_counts: dict[str, int] = load_counts(state_path) if state_path else {}
        self._circuit_open = False
        self._circuit_reason: str | None = None

    @property
    def circuit_open(self) -> bool:
        return self._circuit_open

    def mine(self, plan: list[MiningTask]) -> MiningStats:
        stats = MiningStats(tasks_planned=len(plan))
        last_channel: int | None = None
        for task in plan:
            if self._circuit_open:
                stats.aborted_reason = f"auth_circuit_open: {self._circuit_reason}"
                logger.error(
                    "replay_miner_run_abortado reason=%s tasks_restantes=%d",
                    stats.aborted_reason, stats.tasks_planned - stats.tasks_attempted,
                )
                break
            if not self._disk_ok():
                stats.aborted_reason = "disk_reserve"
                logger.error(
                    "replay_miner_run_abortado reason=disk_reserve min_free_gb=%.1f",
                    self._min_free_gb,
                )
                break

            stats.tasks_attempted += 1
            if last_channel is not None and last_channel != task.channel:
                self._sleep(self._pacing_s)
            last_channel = task.channel

            try:
                self._run_task(task, stats)
            except RecorderAuthError as exc:
                self._circuit_open = True
                self._circuit_reason = str(exc)
                logger.error(
                    "replay_miner_circuit_breaker_open reason=%s — TODA a mineração "
                    "suspensa até restart do processo (anti-lockout, CLAUDE.md)",
                    exc,
                )
                stats.aborted_reason = f"auth_circuit_open: {exc}"
                break

        self._persist_counts()
        return stats

    def _run_task(self, task: MiningTask, stats: MiningStats) -> None:
        rule = task.rule
        campaign_key = f"ch{task.channel}"
        for start, end in _sub_windows(
            task.day, task.shift, self._clip_seconds, self._pull_interval_min
        ):
            if rule.campaign_max_crops is not None:
                if self._campaign_counts.get(campaign_key, 0) >= rule.campaign_max_crops:
                    break  # teto de campanha do canal batido — nada mais a puxar aqui

            try:
                clip_bytes = _pull_clip_bytes(self._recorder, task.camera_id, start, end)
            except RecorderAuthError:
                raise  # propaga pro breaker em mine()
            except RecorderError as exc:
                # Janela vazia/sem gravação: normal, não é falha de auth. Loga e segue.
                stats.windows_empty += 1
                logger.info(
                    "replay_miner_janela_vazia canal=%d dia=%s janela=%s..%s err=%s",
                    task.channel, task.day, start.time(), end.time(), exc,
                )
                continue

            stats.windows_pulled += 1
            frames = self._extract(clip_bytes, self._sample_fps)
            stats.frames_scanned += len(frames)

            window_kept = 0
            for frame in frames:
                if rule.per_window_cap is not None and window_kept >= rule.per_window_cap:
                    break
                if rule.campaign_max_crops is not None and (
                    self._campaign_counts.get(campaign_key, 0) >= rule.campaign_max_crops
                ):
                    break
                crop = self._gate_and_crop(frame, task, stats)
                if crop is None:
                    continue
                if self._upload(task.camera_id, crop):
                    window_kept += 1
                    stats.crops_kept += 1
                    stats.per_channel_kept[task.channel] = (
                        stats.per_channel_kept.get(task.channel, 0) + 1
                    )
                    self._campaign_counts[campaign_key] = (
                        self._campaign_counts.get(campaign_key, 0) + 1
                    )
                else:
                    stats.uploads_failed += 1

    def _gate_and_crop(
        self, frame_bytes: bytes, task: MiningTask, stats: MiningStats
    ) -> bytes | None:
        """Gate de pessoa + recorte + filtros de qualidade. Diferente de
        CollectorLoop._payload_para_upload: aqui, indeterminado/sem-pessoa
        DESCARTA (não sobe o frame inteiro) — mineração de replay existe
        especificamente para produzir recorte de pessoa; um frame inteiro
        ambíguo não serve ao propósito e o dataset já tem ruído suficiente
        (ver PersonDetector docstring)."""
        result = self._person.detect(frame_bytes)
        if result.undetermined:
            stats.crops_dropped_undetermined += 1
            return None
        if not result.found:
            stats.crops_dropped_no_person += 1
            return None
        maior = max(result.boxes, key=lambda b: b.h * b.w)
        try:
            crop = crop_person(frame_bytes, maior)
        except Exception as exc:  # noqa: BLE001 — decode ruim de um frame não pode derrubar a campanha
            logger.warning("replay_miner_recorte_falhou canal=%d err=%s", task.channel, exc)
            return None
        if is_blurry(crop, self._blur_min_variance):
            stats.crops_dropped_blurry += 1
            return None
        if self._dedup.is_duplicate(task.camera_id, crop):
            stats.crops_dropped_duplicate += 1
            return None
        return crop

    def _upload(self, camera_id: str, crop_bytes: bytes) -> bool:
        try:
            bearer = self._token_source.get_bearer()
            self._upload_fn(
                self._http,
                self._api_base_url,
                bearer,
                camera_id,
                self._recorder_id,
                crop_bytes,
                self._module_code,
                datetime.now(),
            )
        except FrameUploadError as exc:
            logger.warning("replay_miner_upload_failed camera=%s err=%s", camera_id, exc)
            return False
        return True

    def _persist_counts(self) -> None:
        if self._state_path is None:
            return
        save_counts(self._state_path, self._campaign_counts)


# ---------------------------------------------------------------------------
# DRY-RUN estimate — o que este módulo REALMENTE executa sem hardware.
# Matemática pura sobre parâmetros assumidos (rotulados como tal); não
# infla números, não substitui a coleta real.
# ---------------------------------------------------------------------------


# Retencao do DVR MEDIDA no gravador da RVB em 2026-08-18 (CGI mediaFileFind,
# leitura pura): o arquivo mais antigo que ainda existia era de 14/08 06:55 —
# **4 dias**. Uniforme nos 7 canais amostrados (1,4,6,8,12,20,27), todos dentro
# de 23 minutos entre si, porque o disco e um pool compartilhado e a frente de
# sobrescrita anda em ordem de tempo, nao por canal.
#
# Nao e configuracao, e capacidade: as 4 particoes do gravador estao com
# UsedBytes == TotalBytes (~3,9 TB, 100% cheias) — FIFO real, ~1 TB/dia para as
# ~28 cameras. A janela de 25/07 a 05/08 devolve "Error/Bad Request": vazia.
#
# O default de 8 dias era ASSUMIDO e OTIMISTA POR 2x: metade de qualquer plano
# de mineracao caia num vazio, sem erro nenhum — so rendimento menor que o
# esperado, atribuivel a qualquer outra coisa.
#
# ⚠️ Re-medir quando mudar numero de cameras, bitrate ou disco. A retencao e
# consequencia dessas tres coisas, nao um numero fixo.
_RETENCAO_DVR_DIAS_MEDIDA = 4


@dataclass(frozen=True)
class EstimateParams:
    days: int = _RETENCAO_DVR_DIAS_MEDIDA
    shifts_per_day: int = 2
    shift_hours: float = 4.0
    pull_interval_min: float = 20.0
    clip_seconds: float = 6.0
    sample_fps: float = 2.0
    substream_kbps: float = 512.0       # ASSUMIDO — mesma ordem do FFMPEG_VIDEO_BITRATE típico
    person_hit_rate: float = 0.30       # ASSUMIDO — fração de frames escaneados com >=1 pessoa
    # ASSUMIDO — canal 10 (convivência) tende a ter mais gente que a média
    absence_person_hit_rate: float = 0.45
    # ASSUMIDO — fração das pessoas do canal 10 sem EPI aparente
    absence_fraction: float = 0.30
    blur_rate: float = 0.10             # ASSUMIDO
    # ASSUMIDO — clipes curtos amostram frames próximos no tempo
    dedup_rate: float = 0.25
    # MEDIDO em campo (PersonDetector docstring, recorte 1080p nativo)
    avg_crop_kb: float = 10.0


@dataclass(frozen=True)
class DryRunEstimate:
    channels_mined: int
    channels_excluded: int
    windows_total: int
    frames_scanned_total: int
    crops_kept_estimate: int
    bandwidth_mb: float
    disk_delta_mb: float
    absence_crops_estimate: int
    absence_yield_low: bool
    per_channel: dict[int, dict[str, float]]


def run_mining(
    miner: ReplayMiner,
    camera_by_channel: dict[int, str],
    days: list[date],
    shifts: Iterable[ShiftWindow] = DEFAULT_SHIFTS,
) -> MiningStats:
    """Entrypoint de operação real: monta o plano determinístico (canal ativo x
    dia x turno; EXCLUDED/QUALITY_ONLY ficam de fora) e roda `mine()` inteiro.

    O `miner` chega com o RecorderClient real JÁ INJETADO — este módulo nunca
    constrói recorder nem lê credencial (presença/ausência via env do caller,
    jamais em argv). Roda SÓ do Orin (VLAN isolada, ADR-0020), nunca da nuvem.
    Anti-lockout (401/403 encerra o run) e reserva de disco são do próprio
    `mine()`. Disparo é decisão do operador — nada aqui roda por import.
    """
    plan = build_sampling_plan(camera_by_channel, days=days, shifts=shifts)
    logger.info(
        "run_mining: %d tasks (%d canais ativos x %d dias) — iniciando",
        len(plan),
        len({t.channel for t in plan}),
        len(days),
    )
    return miner.mine(plan)


def _windows_per_channel(params: EstimateParams) -> int:
    per_shift = int((params.shift_hours * 60) // params.pull_interval_min)
    return params.days * params.shifts_per_day * per_shift


def estimate_dry_run(
    camera_by_channel: dict[int, str], params: EstimateParams = EstimateParams()
) -> DryRunEstimate:
    """Estimativa pura (sem I/O) do que uma campanha com esses parâmetros
    produziria. Todo parâmetro sem fonte de campo está marcado ASSUMIDO em
    EstimateParams — isto é material de planejamento, não uma medição."""
    windows_per_channel = _windows_per_channel(params)
    frames_per_window = params.clip_seconds * params.sample_fps
    keep_fraction = (1 - params.blur_rate) * (1 - params.dedup_rate)

    per_channel: dict[int, dict[str, float]] = {}
    frames_scanned_total = 0
    crops_kept_total = 0
    windows_total = 0
    channels_mined = 0
    channels_excluded = 0
    absence_crops = 0.0

    for channel in sorted(camera_by_channel):
        rule = policy_for_channel(channel)
        if rule.policy in (ChannelPolicy.EXCLUDED, ChannelPolicy.QUALITY_ONLY):
            channels_excluded += 1
            continue
        channels_mined += 1
        windows = windows_per_channel
        windows_total += windows
        frames_scanned = int(windows * frames_per_window)
        frames_scanned_total += frames_scanned

        hit_rate = (
            params.absence_person_hit_rate
            if channel == _ABSENCE_CHANNEL
            else params.person_hit_rate
        )
        raw_kept = frames_scanned * hit_rate * keep_fraction

        if rule.per_window_cap is not None:
            raw_kept = min(raw_kept, windows * rule.per_window_cap)
        if rule.campaign_max_crops is not None:
            raw_kept = min(raw_kept, rule.campaign_max_crops)
        kept = int(raw_kept)
        crops_kept_total += kept

        if channel == _ABSENCE_CHANNEL:
            absence_crops = kept * params.absence_fraction

        per_channel[channel] = {
            "policy": rule.policy.value,
            "windows": windows,
            "frames_scanned": frames_scanned,
            "crops_kept_estimate": kept,
        }

    bandwidth_mb = (
        windows_total * params.clip_seconds * params.substream_kbps / 8.0 / 1024.0
    )

    return DryRunEstimate(
        channels_mined=channels_mined,
        channels_excluded=channels_excluded,
        windows_total=windows_total,
        frames_scanned_total=frames_scanned_total,
        crops_kept_estimate=crops_kept_total,
        bandwidth_mb=round(bandwidth_mb, 1),
        # Disco: ~0 por desenho (ADR-0033/0045, pipeline todo em memória) —
        # ver módulo docstring. Reportado explicitamente em vez de inflar um
        # número que não existe nesta arquitetura.
        disk_delta_mb=0.0,
        absence_crops_estimate=int(absence_crops),
        absence_yield_low=absence_crops < 50,
        per_channel=per_channel,
    )


def format_estimate_report(estimate: DryRunEstimate, params: EstimateParams) -> str:
    lines = [
        "=== DVR Replay Miner — DRY-RUN ESTIMATE (planejamento, não medição) ===",
        f"Parâmetros assumidos: {params}",
        "",
        f"Canais minerados: {estimate.channels_mined}  |  "
        f"excluídos/quality: {estimate.channels_excluded}",
        f"Janelas (clip pulls) totais: {estimate.windows_total}",
        f"Frames escaneados (estimado): {estimate.frames_scanned_total}",
        f"Crops mantidos (estimado, pós blur+dedup+teto): {estimate.crops_kept_estimate}",
        f"Banda off-recorder (estimada): {estimate.bandwidth_mb:.1f} MB",
        f"Delta de disco no Orin: {estimate.disk_delta_mb:.1f} MB "
        "(pipeline em memória por desenho, ADR-0033/0045 — o guard de 8GB "
        "protege o RESTO do box, não este módulo)",
        f"Rendimento projetado de exemplos de AUSÊNCIA (canal 10): "
        f"{estimate.absence_crops_estimate} crops",
    ]
    if estimate.absence_yield_low:
        lines.append(
            "  ATENÇÃO: rendimento de ausência projetado é BAIXO (<50) — "
            "considerar mais dias/turnos ou revisar absence_fraction assumido."
        )
    lines.append("")
    lines.append("Por canal:")
    for channel, info in sorted(estimate.per_channel.items()):
        lines.append(
            f"  canal {channel:>2} [{info['policy']:<10}] janelas={info['windows']:>4} "
            f"frames_escaneados={info['frames_scanned']:>6} "
            f"crops_estimados={info['crops_kept_estimate']:>4}"
        )
    return "\n".join(lines)


def _default_camera_by_channel() -> dict[int, str]:
    """29 canais RVB (D-85) com camera_id sintético — só para o dry-run
    quando nenhum channel_map real é passado via CLI."""
    return {ch: f"cam-ch{ch}" for ch in range(1, 30)}


def _dias_a_minerar(quantos: int, hoje: date | None = None) -> list[date]:
    """Os `quantos` dias mais recentes, do mais antigo para o mais novo.

    Sempre DENTRO da retenção medida (D-172: 4 dias). Pedir mais dias que a
    retenção não dá erro no DVR — dá janela vazia, que é o modo de falha
    silencioso que o `days=8` produzia. Aqui isso vira aviso.
    """
    hoje = hoje or date.today()
    if quantos > _RETENCAO_DVR_DIAS_MEDIDA:
        logger.warning(
            "dias_pedidos=%d excede a retencao MEDIDA do DVR (%d dias, D-172) — "
            "os dias mais antigos vao voltar VAZIOS, nao com erro",
            quantos, _RETENCAO_DVR_DIAS_MEDIDA,
        )
    return [hoje - timedelta(days=n) for n in range(quantos - 1, -1, -1)]


def _minerar_de_verdade(dias: int) -> int:  # pragma: no cover — I/O de campo
    """Uma passada de mineração, com a fiação do coletor ao vivo reusada.

    Roda no Orin por systemd timer (não pelo beat da nuvem: mineração é edge, e
    o beat nunca foi provisionado). Cada ciclo LOGA o resultado — coleta
    silenciosa que falha é o `days=8` de novo, só que sem ninguém perceber.
    """
    from ..auth.token_manager import build_token_manager_from_env
    from ..recorder_factory import build_recorder_client_from_env
    from .person_detector import build_person_detector_from_env

    env = os.environ
    token_manager = build_token_manager_from_env()
    if not token_manager.has_valid_identity():
        logger.error("mineracao_sem_identidade: device nao enrolado — nada a fazer")
        return 2

    recorder = build_recorder_client_from_env()
    camera_by_channel = {
        int(canal): camera_id
        for camera_id, canal in json.loads(env.get("RECORDER_CHANNEL_MAP", "{}")).items()
    }
    if not camera_by_channel:
        logger.error("mineracao_sem_channel_map: RECORDER_CHANNEL_MAP vazio")
        return 2

    miner = ReplayMiner(
        recorder=recorder,
        api_base_url=env["EDGE_API_URL"],
        recorder_id=env["RECORDER_CLOUD_ID"],
        token_source=token_manager,
        person_detector=build_person_detector_from_env(env),
        module_code=env.get("COLLECTOR_MODULE_CODE", "epi"),
    )

    janela = _dias_a_minerar(dias)
    logger.info(
        "mineracao_inicio dias=%s canais=%d turnos=%s",
        [d.isoformat() for d in janela], len(camera_by_channel),
        [t.label for t in SHIFTS_RVB],
    )
    stats = run_mining(miner, camera_by_channel, days=janela, shifts=SHIFTS_RVB)
    logger.info("mineracao_fim %s", stats)
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover — I/O de CLI
    import argparse
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO)
    p = argparse.ArgumentParser(description="DVR replay miner")
    p.add_argument("--executar", action="store_true",
                   help="minera de verdade (padrao: so estima, sem tocar no DVR)")
    p.add_argument("--dias", type=int, default=_RETENCAO_DVR_DIAS_MEDIDA - 1,
                   help=f"dias a minerar (padrao {_RETENCAO_DVR_DIAS_MEDIDA - 1}: uma "
                        f"margem dentro da retencao medida de "
                        f"{_RETENCAO_DVR_DIAS_MEDIDA} dias)")
    args = p.parse_args(argv)

    if not args.executar:
        print(format_estimate_report(
            estimate_dry_run(_default_camera_by_channel()), EstimateParams()))
        return 0
    return _minerar_de_verdade(args.dias)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
