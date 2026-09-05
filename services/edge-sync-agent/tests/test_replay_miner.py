"""Self-check for the DVR replay miner: channel policy table, dedup/blur
filters, and — most important — that the anti-lockout circuit breaker aborts
the WHOLE run (zero retries, zero further recorder access) the instant a
401/403 surfaces, same discipline as snapshot_executor.py's breaker.

No real ffmpeg/ONNX model/network: PersonDetector is stubbed (duck-typed,
same Protocol collector_loop.py already relies on), stream_clip() is a
MockRecorderClient yielding synthetic JPEG bytes, and frame extraction is
injected as the pure `_split_mjpeg` (no subprocess).
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from datetime import time as dtime

from PIL import Image, ImageFilter

from app.collector.person_detector import PersonBox, PersonResult
from app.collector.replay_miner import (
    _DEFAULT_BLUR_VARIANCE_MIN,
    _MAX_TRANSPORTE_SEGUIDOS,
    ChannelPolicy,
    MiningTask,
    NearDuplicateFilter,
    ReplayMiner,
    ShiftWindow,
    _split_mjpeg,
    blur_variance,
    build_sampling_plan,
    is_blurry,
    policy_for_channel,
    run_mining,
)
from app.recorder_client import RecorderError

_EXCLUDED = {13, 14, 17, 18, 22, 25}
_QUALITY_ONLY = {3, 27}


def _gradient_jpeg(quality: int = 90, flip: bool = False) -> bytes:
    img = Image.new("RGB", (80, 60))
    pixels = img.load()
    for x in range(80):
        for y in range(60):
            v = (x * 3) % 256
            pixels[x, y] = (255 - v, 255 - v, 255 - v) if flip else (v, v, v)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _checkerboard_jpeg() -> bytes:
    """High-frequency pattern — sharp, should NOT be flagged as blurry."""
    img = Image.new("L", (64, 48))
    pixels = img.load()
    for x in range(64):
        for y in range(48):
            pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _flat_jpeg() -> bytes:
    """Solid color — zero edge energy, should be flagged as blurry."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(120, 120, 120)).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ── channel policy table ────────────────────────────────────────────────────


def test_excluded_channels_extract_nothing():
    for ch in _EXCLUDED:
        assert policy_for_channel(ch).policy == ChannelPolicy.EXCLUDED


def test_quality_channels_route_out_of_epi_dataset():
    for ch in _QUALITY_ONLY:
        assert policy_for_channel(ch).policy == ChannelPolicy.QUALITY_ONLY


def test_channel_8_gets_concentration_ceiling():
    rule = policy_for_channel(8)
    assert rule.policy == ChannelPolicy.CEILING
    assert rule.campaign_max_crops is not None and rule.campaign_max_crops > 0


def test_channel_10_is_absence_source():
    assert policy_for_channel(10).policy == ChannelPolicy.ABSENCE


def test_full_priority_channels():
    for ch in (1, 4, 11, 12, 19, 23, 28):
        assert policy_for_channel(ch).policy == ChannelPolicy.FULL


def test_unlisted_channel_is_reduced_not_zeroed():
    rule = policy_for_channel(999)
    assert rule.policy == ChannelPolicy.REDUCED
    assert rule.per_window_cap is not None and rule.per_window_cap > 0


def test_sampling_plan_skips_excluded_and_quality_channels():
    cameras = {ch: f"cam-{ch}" for ch in list(_EXCLUDED) + list(_QUALITY_ONLY) + [1, 8, 10, 999]}
    plan = build_sampling_plan(cameras, days=[date(2026, 8, 3)])
    planned_channels = {t.channel for t in plan}
    assert planned_channels.isdisjoint(_EXCLUDED)
    assert planned_channels.isdisjoint(_QUALITY_ONLY)
    assert {1, 8, 10, 999} <= planned_channels


# ── blur filter (Laplacian variance, PIL-only) ──────────────────────────────


# Nota de calibração: fixture JPEG pequeno tem piso de artefato de bloco
# (flat ~957, desfoque gaussiano ~1085 nesta função) — ACIMA do default real de
# 150. Por isso a DISCRIMINAÇÃO é testada com min_variance explícito, e o valor
# do default (calibrado contra recorte real) tem seu próprio teste abaixo.
_DISCRIM_THRESHOLD = 2000.0


def test_sharp_crop_is_not_blurry():
    assert blur_variance(_checkerboard_jpeg()) > blur_variance(_flat_jpeg())
    assert not is_blurry(_checkerboard_jpeg(), min_variance=_DISCRIM_THRESHOLD)


def test_flat_crop_is_blurry():
    assert is_blurry(_flat_jpeg(), min_variance=_DISCRIM_THRESHOLD)


def test_defocused_crop_is_blurry():
    """More faithful stand-in for a real out-of-focus crop than a flat
    color block: Gaussian-blur the sharp checkerboard and confirm it drops
    below the sharp image's variance by an order of magnitude."""
    sharp = Image.open(io.BytesIO(_checkerboard_jpeg()))
    buf = io.BytesIO()
    sharp.filter(ImageFilter.GaussianBlur(radius=3)).save(buf, format="JPEG", quality=90)
    defocused = buf.getvalue()

    assert blur_variance(defocused) < blur_variance(_checkerboard_jpeg()) / 5
    assert is_blurry(defocused, min_variance=_DISCRIM_THRESHOLD)


def test_default_blur_threshold_keeps_real_crops():
    """Regressão da calibração de campo (2026-08-17, n=224 crops RVB reais):
    mediana real = 693, p05 = 199. O default DEVE ficar abaixo da mediana (para
    não descartar recorte bom — o antigo 3000 rejeitava 98%) e acima de 0 (para
    ainda cortar a cauda ilegível). Re-medir se a fonte de crop mudar."""
    assert 0 < _DEFAULT_BLUR_VARIANCE_MIN < 693


# ── near-duplicate filter (dHash, timeline-aware) ───────────────────────────


def test_near_duplicate_dropped_but_different_crop_kept():
    dedup = NearDuplicateFilter()
    base = _gradient_jpeg(quality=95)
    recompressed = _gradient_jpeg(quality=40)  # same content, different JPEG bytes
    different = _gradient_jpeg(quality=95, flip=True)  # inverted gradient

    assert dedup.is_duplicate("cam-1", base) is False  # first sighting, always kept
    assert dedup.is_duplicate("cam-1", recompressed) is True  # near-identical -> dropped
    assert dedup.is_duplicate("cam-1", different) is False  # genuinely different -> kept


def test_same_camera_same_day_alone_is_not_a_duplicate_reason():
    """Two crops from the same camera on the same day that are NOT visually
    near-identical must both survive — "same day/same camera" alone is never
    the drop reason (task spec)."""
    dedup = NearDuplicateFilter()
    a = _gradient_jpeg(quality=95)
    b = _gradient_jpeg(quality=95, flip=True)

    assert dedup.is_duplicate("cam-1", a) is False
    assert dedup.is_duplicate("cam-1", b) is False


def test_split_mjpeg_pure_byte_split():
    data = b"\xff\xd8AAA\xff\xd9\xff\xd8BBB\xff\xd9"
    frames = _split_mjpeg(data)
    assert frames == [b"\xff\xd8AAA\xff\xd9", b"\xff\xd8BBB\xff\xd9"]


# ── ReplayMiner orchestration: anti-lockout breaker ─────────────────────────


class _FakePersonDetector:
    """Always finds one person covering the whole frame — the gate/crop path
    is exercised without needing the real ONNX model (absent in this env)."""

    def detect(self, frame_bytes: bytes) -> PersonResult:
        img = Image.open(io.BytesIO(frame_bytes))
        w, h = img.size
        box = PersonBox(x=0, y=0, w=w, h=h, confidence=0.9)
        return PersonResult(found=True, boxes=(box,), max_confidence=0.9)


class _FakeTokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str:
        return "fake-bearer"


class _MockRecorderClient:
    """stream_clip() yields one synthetic JPEG "clip" per call; raises a
    401-flavored RecorderError on the call index given by *trip_on_call*
    (None = never). Records every call for the zero-further-access assertion.
    """

    def __init__(self, trip_on_call: int | None = None) -> None:
        self.calls: list[str] = []
        self._trip_on = trip_on_call

    def stream_clip(self, camera_id: str, start: datetime, end: datetime):
        idx = len(self.calls)
        self.calls.append(camera_id)
        if self._trip_on is not None and idx == self._trip_on:
            raise RecorderError("gravador respondeu 401 Unauthorized ao playback")
        yield _gradient_jpeg(quality=90, flip=(idx % 2 == 0))


def _one_window_shift() -> ShiftWindow:
    # 6s de turno == exatamente 1 sub-janela para clip_seconds=6 — mantém o
    # teste determinístico (1 stream_clip() por task) sem depender de
    # aritmética de _sub_windows além do caso trivial.
    return ShiftWindow("teste", dtime(7, 0, 0), dtime(7, 0, 6))


def _make_plan(n_tasks: int) -> list[MiningTask]:
    day = date(2026, 8, 3)
    shift = _one_window_shift()
    channels = [1, 4, 11, 12][:n_tasks]
    return [
        MiningTask(ch, f"cam-{ch}", day, shift, policy_for_channel(ch)) for ch in channels
    ]


def _make_miner(recorder, uploads: list, **overrides) -> ReplayMiner:
    def _upload_fn(http, api_base_url, bearer, camera_id, recorder_id, frame_bytes,
                    module_code, captured_at, crop_origin=None):
        uploads.append({
            "camera_id": camera_id,
            "frame_bytes": frame_bytes,
            "crop_origin": crop_origin,
            "captured_at": captured_at,
        })
        return f"frame-{len(uploads)}"

    defaults = dict(
        recorder=recorder,
        api_base_url="https://api.example",
        recorder_id="recorder-1",
        token_source=_FakeTokenSource(),
        person_detector=_FakePersonDetector(),
        http_client=object(),
        upload_fn=_upload_fn,
        frame_extractor=lambda clip, fps: _split_mjpeg(clip),
        disk_check_fn=lambda: True,
        sleep_fn=lambda s: None,
        state_path=None,
        blur_min_variance=0.0,  # blur filter not under test here
        pull_interval_min=60.0,
        clip_seconds=6.0,
    )
    defaults.update(overrides)
    return ReplayMiner(**defaults)


def test_happy_path_uploads_one_crop_per_task():
    recorder = _MockRecorderClient()
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(3)

    stats = miner.mine(plan)

    assert stats.aborted_reason is None
    assert miner.circuit_open is False
    assert stats.crops_kept == 3
    assert len(uploads) == 3
    assert recorder.calls == ["cam-1", "cam-4", "cam-11"]


def test_captured_at_e_o_instante_da_gravacao_nao_o_da_mineracao():
    """O carimbo tem de ser a hora do DVR, não a hora em que colhemos.

    Já foi `datetime.now()`: um lote minerado hoje de gravação de 3 dias atrás
    nascia inteiro com a data de hoje, e o dataset perdia turno, luz e a
    ligação com o roteiro. Aqui o turno é 07:00:00..07:00:06 de 2026-08-03, e
    o frame de índice 0 tem de sair exatamente em 07:00:00 daquele dia.
    """
    recorder = _MockRecorderClient()
    uploads: list = []
    miner = _make_miner(recorder, uploads, sample_fps=2.0)

    miner.mine(_make_plan(1))

    assert len(uploads) == 1
    assert uploads[0]["captured_at"] == datetime(2026, 8, 3, 7, 0, 0)


def test_run_mining_builds_plan_skips_excluded_and_runs():
    # Operator entrypoint: builds the plan itself (canal x dia x turno) and
    # runs mine(). ch13 is EXCLUDED → must not generate a task nor touch the
    # recorder. Proves plan-build + exclusion + mine wiring in one shot.
    recorder = _MockRecorderClient()
    uploads: list = []
    miner = _make_miner(recorder, uploads)

    stats = run_mining(
        miner,
        camera_by_channel={1: "cam-1", 4: "cam-4", 13: "cam-13"},
        days=[date(2026, 8, 3)],
        shifts=(_one_window_shift(),),
    )

    assert stats.aborted_reason is None
    assert recorder.calls == ["cam-1", "cam-4"]  # ch13 EXCLUDED, never pulled
    assert stats.crops_kept == 2


def test_anti_lockout_breaker_aborts_whole_run_with_zero_retries():
    # Trips on the SECOND stream_clip() call: proves the FIRST task completed
    # normally (breaker doesn't trip preemptively) and that NOTHING after the
    # trip touches the recorder again (zero retries, whole session ends).
    recorder = _MockRecorderClient(trip_on_call=1)
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(4)

    stats = miner.mine(plan)

    assert miner.circuit_open is True
    assert stats.aborted_reason is not None and "auth_circuit_open" in stats.aborted_reason
    # Só a 1a task (cam-1) completou upload; a 2a task disparou o breaker e
    # abortou ANTES de qualquer upload seu; a 3a/4a nunca foram tentadas.
    assert len(uploads) == 1
    assert recorder.calls == ["cam-1", "cam-4"]  # nunca chega em cam-11/cam-12
    assert stats.tasks_attempted == 2
    assert stats.tasks_planned == 4


def test_empty_window_is_not_an_auth_failure_and_does_not_trip_breaker():
    class _EmptyWindowRecorder:
        def __init__(self):
            self.calls: list[str] = []

        def stream_clip(self, camera_id, start, end):
            self.calls.append(camera_id)
            raise RecorderError("ffmpeg não produziu bytes para o clipe: sem sinal no canal")
            yield b""  # pragma: no cover — makes this a generator function

    recorder = _EmptyWindowRecorder()
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(2)

    stats = miner.mine(plan)

    assert miner.circuit_open is False
    assert stats.aborted_reason is None
    assert stats.windows_empty == 2
    assert stats.tasks_attempted == 2  # ambas as tasks tentadas — janela vazia não aborta


# ---------------------------------------------------------------------------
# Estratificação RVB (M6) — as faixas de hora e a janela dentro da retenção.
# ---------------------------------------------------------------------------


class TestShiftsRVB:
    """O que estes testes protegem: uma faixa virar zero sem ninguém notar.

    O crepúsculo é a faixa mais difícil (menor mediana de nitidez, maior
    rejeição por blur — D-173) e por isso é a mais tentadora de cortar. Cortar
    é o erro: o modelo precisa ver luz de transição. 'Leve' e 'ausente' são
    coisas diferentes, e é essa diferença que está fixada aqui.
    """

    def test_ladrilha_das_05h_a_meia_noite_sem_buraco(self) -> None:
        from app.collector.replay_miner import SHIFTS_RVB

        turnos = sorted(SHIFTS_RVB, key=lambda t: t.start)
        assert turnos[0].start == dtime(5, 0)
        for anterior, seguinte in zip(turnos, turnos[1:]):
            assert anterior.end == seguinte.start, (
                f"buraco entre {anterior.label} e {seguinte.label}"
            )
        assert turnos[-1].end >= dtime(23, 59)

    def test_madrugada_fora(self) -> None:
        from app.collector.replay_miner import SHIFTS_RVB

        for hora in (dtime(1, 0), dtime(2, 0), dtime(3, 0)):
            assert not any(t.start <= hora < t.end for t in SHIFTS_RVB), (
                f"{hora} deveria estar fora do plano"
            )

    def test_crepusculo_e_leve_mas_NUNCA_zero(self) -> None:
        from app.collector.replay_miner import SHIFTS_RVB, _sub_windows

        por_label = {t.label: t for t in SHIFTS_RVB}
        crepusculo = por_label["crepusculo"]
        dia = por_label["dia"]

        janelas_crep = _sub_windows(date(2026, 8, 17), crepusculo, 6.0, 20.0)
        janelas_dia = _sub_windows(date(2026, 8, 17), dia, 6.0, 20.0)

        assert len(janelas_crep) > 0, "crepúsculo NUNCA pode ser zero"
        # densidade por hora: leve de verdade, não só 'menos horas'
        dens_crep = len(janelas_crep) / 3.0
        dens_dia = len(janelas_dia) / 12.0
        assert dens_crep < dens_dia

    def test_intervalo_proprio_do_turno_vence_o_do_minerador(self) -> None:
        from app.collector.replay_miner import ShiftWindow, _sub_windows

        curto = ShiftWindow("x", dtime(10, 0), dtime(12, 0))
        longo = ShiftWindow("y", dtime(10, 0), dtime(12, 0), pull_interval_min=60.0)
        assert len(_sub_windows(date(2026, 8, 17), curto, 6.0, 20.0)) == 6
        assert len(_sub_windows(date(2026, 8, 17), longo, 6.0, 20.0)) == 2


class TestJanelaDentroDaRetencao:
    def test_dias_sao_os_mais_recentes_em_ordem(self) -> None:
        from app.collector.replay_miner import _dias_a_minerar

        assert _dias_a_minerar(3, hoje=date(2026, 8, 18)) == [
            date(2026, 8, 16), date(2026, 8, 17), date(2026, 8, 18),
        ]

    def test_pedir_alem_da_retencao_AVISA(self, caplog) -> None:
        """Passar da retenção não dá erro no DVR — dá janela vazia.

        Era exatamente esse o modo de falha do antigo `days=8`: metade do plano
        caía no nada, sem erro, e o rendimento baixo era atribuído a outra
        coisa. Silêncio aqui é o defeito; o aviso é o conserto.
        """
        import logging

        from app.collector.replay_miner import _RETENCAO_DVR_DIAS_MEDIDA, _dias_a_minerar

        with caplog.at_level(logging.WARNING):
            _dias_a_minerar(_RETENCAO_DVR_DIAS_MEDIDA + 4, hoje=date(2026, 8, 18))
        assert "excede a retencao MEDIDA" in caplog.text

    def test_default_do_cli_cabe_na_retencao(self) -> None:
        from app.collector.replay_miner import _RETENCAO_DVR_DIAS_MEDIDA

        assert _RETENCAO_DVR_DIAS_MEDIDA - 1 < _RETENCAO_DVR_DIAS_MEDIDA


# ---------------------------------------------------------------------------
# Taxonomia por janela (#436) — o conserto do silêncio de 2601 janelas.
# ---------------------------------------------------------------------------


def _mjpeg_de_teste() -> bytes:
    return _checkerboard_jpeg()


def _miner_de_teste(pull, **overrides):
    """Minerador com um gravador que sempre levanta o erro dado — o único
    eixo sob teste aqui é COMO a falha por janela é classificada."""
    class _RecorderQueFalha:
        def stream_clip(self, *a, **k):
            return pull(*a, **k)

    return _make_miner(_RecorderQueFalha(), [], **overrides)


class TestTaxonomiaDeFalhaDeJanela:
    """Vazia é o caso NORMAL. Confundir infra com vazia esconde o defeito.

    Caso real de 2026-08-18: `ffmpeg` fora do PATH, 2601 janelas registradas
    como vazias em nível INFO, exit 0, log com cara de domingo tranquilo.
    """

    def test_erro_do_ffmpeg_ausente_e_INFRA(self) -> None:
        """A mensagem exata que enganou todo mundo."""
        from app.collector.replay_miner import _classifica_falha_de_janela

        real = RecorderError(
            "ffmpeg indisponível para extrair clipe: "
            "[Errno 2] No such file or directory: 'ffmpeg'"
        )
        assert _classifica_falha_de_janela(real) == "falha_infra"

    def test_404_do_gravador_e_TRANSPORTE(self) -> None:
        from app.collector.replay_miner import _classifica_falha_de_janela

        assert _classifica_falha_de_janela(
            RecorderError("rtsp_clip_pull_empty: DESCRIBE failed: 404 (Not Found)")
        ) == "erro_transporte"

    def test_clipe_vazio_e_SEM_GRAVACAO(self) -> None:
        from app.collector.replay_miner import _classifica_falha_de_janela

        assert _classifica_falha_de_janela(
            RecorderError("clipe vazio para a janela solicitada")
        ) == "sem_gravacao"

    def test_infra_ABORTA_o_run_em_vez_de_seguir(self) -> None:
        """O coração do #436: 2601 tentativas viram 1 erro legível."""
        import pytest

        from app.collector.replay_miner import InfraIndisponivel

        chamadas = {"n": 0}

        def recorder_sem_ffmpeg(*_a: object, **_k: object) -> bytes:
            chamadas["n"] += 1
            raise RecorderError(
                "ffmpeg indisponível para extrair clipe: "
                "[Errno 2] No such file or directory: 'ffmpeg'"
            )

        miner = _miner_de_teste(pull=recorder_sem_ffmpeg)
        with pytest.raises(InfraIndisponivel) as erro:
            run_mining(
                miner,
                {1: "cam-1"},
                days=[date(2026, 8, 17)],
                shifts=(ShiftWindow("t", dtime(9, 0), dtime(12, 0)),),
            )

        assert chamadas["n"] == 1, "deveria parar na PRIMEIRA, não tentar as outras"
        assert "ffmpeg" in str(erro.value)
        assert "falha de infraestrutura" in str(erro.value)

    def test_sem_gravacao_NAO_aborta(self) -> None:
        """Domingo inteiro sem gravação continua sendo caso normal."""
        chamadas = {"n": 0}

        def recorder_vazio(*_a: object, **_k: object) -> bytes:
            chamadas["n"] += 1
            raise RecorderError("clipe vazio para a janela solicitada")

        miner = _miner_de_teste(pull=recorder_vazio)
        stats = run_mining(
            miner, {1: "cam-1"}, days=[date(2026, 8, 17)],
            shifts=(ShiftWindow("t", dtime(9, 0), dtime(12, 0)),),
        )
        assert chamadas["n"] > 1
        assert stats.windows_sem_gravacao == chamadas["n"]
        assert stats.windows_falha_infra == 0
        assert stats.windows_empty == chamadas["n"]  # compatibilidade preservada


class TestResumoDoCiclo:
    def test_zero_extraidas_grita(self) -> None:
        from app.collector.replay_miner import MiningStats, _resumo_do_ciclo

        texto = _resumo_do_ciclo(MiningStats(windows_empty=2601, windows_sem_gravacao=2601))
        assert "ZERO janelas extraídas" in texto
        assert "não é um dia parado, é um defeito" in texto

    def test_cada_categoria_aparece_separada(self) -> None:
        from app.collector.replay_miner import MiningStats, _resumo_do_ciclo

        texto = _resumo_do_ciclo(MiningStats(
            windows_pulled=10, windows_empty=7,
            windows_sem_gravacao=4, windows_erro_transporte=3, crops_kept=5,
        ))
        assert "sem_gravacao ...: 4" in texto
        assert "erro_transporte : 3" in texto
        assert "falha_infra ....: 0" in texto


class TestNaoMinerarOFuturo:
    """Hoje não terminou. Pedir hora futura devolve 404 — e o 404 já matou uma run."""

    def test_corta_janelas_depois_de_agora(self) -> None:
        from app.collector.replay_miner import _sub_windows

        turno = ShiftWindow("dia", dtime(5, 0), dtime(17, 0))
        agora = datetime(2026, 8, 18, 11, 0, 0)
        janelas = _sub_windows(date(2026, 8, 18), turno, 6.0, 20.0, agora=agora)

        assert janelas, "o passado do dia continua sendo minerado"
        assert all(fim <= agora for _, fim in janelas)
        assert max(fim for _, fim in janelas) <= agora

    def test_dia_passado_fica_inteiro(self) -> None:
        from app.collector.replay_miner import _sub_windows

        turno = ShiftWindow("dia", dtime(5, 0), dtime(17, 0))
        agora = datetime(2026, 8, 18, 11, 0, 0)
        assert len(_sub_windows(date(2026, 8, 17), turno, 6.0, 20.0, agora=agora)) == 36


class TestPonteiroNaoAbreDisjuntor:
    """O falso positivo que matou a run de 18/08 na tarefa 8 de 162."""

    def test_endereco_de_memoria_do_ffmpeg_NAO_e_auth(self) -> None:
        from app.recorder_client import is_auth_failure_message

        real = (
            "ffmpeg não produziu bytes para o clipe: "
            "[in#0 @ 0xaaaad4033a80] method DESCRIBE failed: 404 (Not Found)"
        )
        assert "403" in real, "o ponteiro 0xaaaad4033a80 realmente contém '403'"
        assert is_auth_failure_message(real) is False

    def test_401_e_403_de_verdade_continuam_sendo_auth(self) -> None:
        from app.recorder_client import is_auth_failure_message

        assert is_auth_failure_message("RTSP/1.0 401 Unauthorized") is True
        assert is_auth_failure_message("server returned 403") is True
        assert is_auth_failure_message("Forbidden") is True
        assert is_auth_failure_message("404 Not Found") is False


class TestLimiarDeTransporteNaoMataDomingo:
    """404 é ambíguo: dialeto errado E ausência de gravação devolvem o mesmo.

    O desempate não está na mensagem — está em se ALGUMA janela já saiu. Uma só
    prova que o dialeto está certo; daí em diante 404 é domingo, não defeito.
    """

    def test_muitos_404_com_zero_extraidas_ABORTA(self) -> None:
        import pytest

        from app.collector.replay_miner import InfraIndisponivel

        def so_404(*_a: object, **_k: object) -> bytes:
            raise RecorderError("DESCRIBE failed: 404 (Not Found)")

        miner = _miner_de_teste(pull=so_404, pull_interval_min=1.0)
        with pytest.raises(InfraIndisponivel) as erro:
            run_mining(
                miner, {1: "cam-1"}, days=[date(2026, 8, 17)],
                shifts=(ShiftWindow("t", dtime(0, 0), dtime(2, 0)),),
            )
        assert "NENHUMA extraída" in str(erro.value)
        # A mensagem precisa admitir a leitura legítima: domingo/feriado.
        assert "domingo" in str(erro.value)
        assert "comportamento CERTO" in str(erro.value)

    def test_404_DEPOIS_de_uma_janela_boa_nao_aborta(self) -> None:
        """O domingo legítimo: o dialeto já se provou, o resto é ausência."""
        estado = {"n": 0}

        def uma_boa_depois_404(*_a: object, **_k: object):
            estado["n"] += 1
            if estado["n"] == 1:
                return [_mjpeg_de_teste()]  # stream_clip devolve BLOCOS, nao bytes
            raise RecorderError("DESCRIBE failed: 404 (Not Found)")

        miner = _miner_de_teste(pull=uma_boa_depois_404, pull_interval_min=1.0)
        stats = run_mining(
            miner, {1: "cam-1"}, days=[date(2026, 8, 17)],
            shifts=(ShiftWindow("t", dtime(0, 0), dtime(2, 0)),),
        )
        assert stats.windows_pulled == 1
        assert stats.windows_erro_transporte > _MAX_TRANSPORTE_SEGUIDOS
        assert stats.aborted_reason is None


class TestEstimadorUsaTaxaMedida:
    """Medido vence assumido — e o relatório diz qual dos dois foi usado.

    O 1º ciclo real mediu 7,9% contra os 30% assumidos. Trocar o default por
    7,9% seria o mesmo erro com o sinal trocado: foi UM canal, num domingo.
    Taxa é por canal; número global mente nas duas direções.
    """

    def test_canal_medido_usa_o_medido(self) -> None:
        from app.collector.replay_miner import EstimateParams, estimate_dry_run

        mapa = {1: "cam-1", 4: "cam-4"}
        base = estimate_dry_run(mapa, EstimateParams())
        com_medida = estimate_dry_run(mapa, EstimateParams(person_hit_rate_medido={1: 0.079}))

        assert com_medida.per_channel[1]["hit_rate"] == 0.079
        assert com_medida.per_channel[1]["hit_rate_origem"] == "medido"
        assert (
            com_medida.per_channel[1]["crops_kept_estimate"]
            < base.per_channel[1]["crops_kept_estimate"]
        )

    def test_canal_sem_medida_segue_assumido_e_DIZ_que_e_assumido(self) -> None:
        from app.collector.replay_miner import EstimateParams, estimate_dry_run

        est = estimate_dry_run({1: "cam-1", 4: "cam-4"},
                               EstimateParams(person_hit_rate_medido={1: 0.079}))
        assert est.per_channel[4]["hit_rate_origem"] == "ASSUMIDO"

    def test_relatorio_marca_a_origem(self) -> None:
        from app.collector.replay_miner import (
            EstimateParams,
            estimate_dry_run,
            format_estimate_report,
        )

        params = EstimateParams(person_hit_rate_medido={1: 0.079})
        texto = format_estimate_report(estimate_dry_run({1: "cam-1", 4: "cam-4"}, params), params)
        assert "(medido)" in texto
        assert "(ASSUMIDO)" in texto


class TestTravaDeCiclo:
    """~35h de ciclo contra 48h de timer: 13h de margem. Dois mineradores no
    mesmo DVR é o que o anti-lockout existe para evitar."""

    def test_segundo_ciclo_nao_pega_a_trava(self, tmp_path, monkeypatch) -> None:
        from app.collector import replay_miner as rm

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        primeiro = rm._trava_de_ciclo()
        assert primeiro is not None
        assert rm._trava_de_ciclo() is None, "dois ciclos simultâneos"
        primeiro.close()
        assert rm._trava_de_ciclo() is not None, "trava deve liberar ao fechar"

    def test_trava_vale_para_a_coleta_MANUAL_tambem(self, tmp_path, monkeypatch) -> None:
        """systemd já não inicia a unit duas vezes — mas a coleta manual passa
        por fora dele, e foi assim que a missão inteira rodou até o OTA."""
        from app.collector import replay_miner as rm

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        manual = rm._trava_de_ciclo()
        assert manual is not None
        assert rm._trava_de_ciclo() is None
        manual.close()

    def test_escopo_padrao_cabe_no_intervalo_do_timer(self) -> None:
        """2 dias por ciclo × timer de 2 dias = cobertura sem buraco."""
        import argparse

        from app.collector.replay_miner import _RETENCAO_DVR_DIAS_MEDIDA

        p = argparse.ArgumentParser()
        p.add_argument("--dias", type=int, default=2)
        assert p.parse_args([]).dias == 2
        assert 2 <= _RETENCAO_DVR_DIAS_MEDIDA


class TestMarcaDagua:
    """Escopo fixo não sobrevive a um ciclo pulado. A conta que quebra:

        t=0  cobre [-2, 0]
        t=2  PULADO pela trava
        t=4  cobre [2, 4]        <- [0, 2] nunca coberto
        t=6  [0,2] tem 4-6 dias  <- FIFO comeu. Buraco PERMANENTE.
    """

    def test_o_cenario_do_furo_nao_deixa_buraco_permanente(self) -> None:
        """t=0 cobre, t=2 é pulado, t=4 roda: [0,2] TEM de estar no escopo de t=4.

        Com janela fixa de 2 dias, t=4 cobriria só [2,4] e [0,2] morreria no
        FIFO. Com marca-d'água, t=4 parte de onde t=0 parou.
        """
        from app.collector.replay_miner import dias_desde_marca

        t0 = datetime(2026, 8, 14, 3, 30)          # último ciclo BEM-SUCEDIDO
        dias, buraco = dias_desde_marca(t0, t0 + timedelta(days=3))

        assert buraco is None, "3 dias cabem no teto de 3,5"
        assert dias[0] == t0.date(), "parte da marca, não de 'hoje menos N'"
        assert len(dias) == 4, "cobre os 3 dias pulados + hoje"

    def test_pulado_dentro_do_teto_cobre_o_DOBRO(self) -> None:
        from app.collector.replay_miner import dias_desde_marca

        t0 = datetime(2026, 8, 10, 3, 30)
        normal, _ = dias_desde_marca(t0, t0 + timedelta(days=2))
        apos_pulo, _ = dias_desde_marca(t0, t0 + timedelta(days=3))

        assert len(apos_pulo) > len(normal), "ciclo pulado tem de cobrir mais, não o mesmo"
        assert normal[0] == apos_pulo[0], "os dois partem da MESMA marca — é esse o ponto"

    def test_marca_velha_demais_declara_o_BURACO(self) -> None:
        from app.collector.replay_miner import _TETO_MARCA_DAGUA_DIAS, dias_desde_marca

        agora = datetime(2026, 8, 18, 3, 30)
        marca = agora - timedelta(days=6)
        dias, buraco = dias_desde_marca(marca, agora)

        assert buraco is not None, "perda tem de ser DITA, nunca silenciosa"
        assert abs(buraco - (6 - _TETO_MARCA_DAGUA_DIAS)) < 0.01
        assert dias[0] >= (agora - timedelta(days=_TETO_MARCA_DAGUA_DIAS)).date()

    def test_primeiro_ciclo_nao_inventa_buraco(self) -> None:
        from app.collector.replay_miner import dias_desde_marca

        dias, buraco = dias_desde_marca(None, datetime(2026, 8, 18, 3, 30))
        assert buraco is None, "não havia nada antes — não há perda a declarar"
        assert len(dias) >= 4

    def test_marca_ida_e_volta(self, tmp_path) -> None:
        from app.collector.replay_miner import gravar_marca_dagua, ler_marca_dagua

        alvo = str(tmp_path / "m.json")
        assert ler_marca_dagua(alvo) is None
        quando = datetime(2026, 8, 18, 3, 30, 15)
        gravar_marca_dagua(quando, alvo)
        assert ler_marca_dagua(alvo) == quando

    def test_arquivo_corrompido_vira_primeiro_ciclo(self, tmp_path) -> None:
        """Marca ilegível não pode travar a coleta — vira 'sem marca'."""
        from app.collector.replay_miner import ler_marca_dagua

        alvo = tmp_path / "m.json"
        alvo.write_text("{lixo")
        assert ler_marca_dagua(str(alvo)) is None


class TestEstadoPersisteNoMeio:
    """A prova de retomabilidade reprovou aqui: o estado só gravava no FIM.

    Medido em campo: 19 recortes subidos em 5 min e o arquivo de estado ainda
    não existia. Morto no meio, o ciclo perdia tudo e o seguinte recomeçava do
    zero — refazendo o mesmo trabalho contra o mesmo DVR.
    """

    def test_grava_a_cada_tarefa_nao_so_no_fim(self, tmp_path) -> None:
        gravacoes: list[dict] = []

        miner = _make_miner(_MockRecorderClient(), [], state_path=str(tmp_path / "s.json"))
        miner._persist_counts = lambda: gravacoes.append(dict(miner._campaign_counts))  # type: ignore[method-assign]

        run_mining(
            miner, {1: "cam-1", 4: "cam-4"}, days=[date(2026, 8, 17)],
            shifts=(ShiftWindow("t", dtime(7, 0), dtime(7, 0, 6)),),
        )

        # 2 tarefas => 2 gravações no laço + 1 final. Antes: só a final.
        assert len(gravacoes) >= 3, (
            f"gravou {len(gravacoes)}x — estado tem de persistir POR TAREFA"
        )

    def test_marca_dagua_e_escrita_ATOMICA(self, tmp_path) -> None:
        """162 escritas por ciclo = 162 chances de morrer no meio de uma.

        Truncado, `ler_marca_dagua` degrada para "primeiro ciclo" e o próximo
        ciclo re-minera tudo contra o DVR. Com rename atômico, truncado vira
        impossível — a degradação fica como cinto, não como plano A.
        """
        from app.collector.replay_miner import gravar_marca_dagua, ler_marca_dagua

        alvo = tmp_path / "m.json"
        gravar_marca_dagua(datetime(2026, 8, 18, 3, 30), str(alvo))
        # nenhum temporário sobrevive: rename consumiu, finally limpou
        assert [f.name for f in tmp_path.iterdir()] == ["m.json"]
        assert ler_marca_dagua(str(alvo)) is not None


# ---------------------------------------------------------------------------
# Modo FRAME CHEIO (REPLAY_MINER_FULL_FRAME=1) — o domínio que é SERVIDO.
#
# O caminho servido é single-stage sobre o quadro inteiro (inference_engine.py
# `_run_detector(frame)` -> `predict(frame)`; não há recorte de pessoa em lugar
# nenhum do que é servido), mas 95,9% do dado de treino é recorte. Este modo
# colhe o domínio de produção sem abrir mão do gate de pessoa.
#
# O teste que mais importa aqui NÃO é o do modo novo: é o de NÃO-REGRESSÃO do
# default. O modo recorte é o que roda em produção hoje.
# ---------------------------------------------------------------------------


class _PessoaPequena:
    """Pessoa num pedaço do quadro — é o que separa "subiu recorte" de "subiu
    frame cheio" por TAMANHO, não só por bytes diferentes."""

    def __init__(self, undetermined: bool = False, found: bool = True) -> None:
        self._undetermined = undetermined
        self._found = found

    def detect(self, frame_bytes: bytes) -> PersonResult:
        if self._undetermined:
            return PersonResult(found=False, undetermined=True)
        if not self._found:
            return PersonResult(found=False)
        return PersonResult(
            found=True,
            boxes=(PersonBox(x=10, y=10, w=20, h=20, confidence=0.9),),
            max_confidence=0.9,
        )


class _GravadorQueRegistra:
    """Guarda os bytes exatos que entregou — a asserção "mesmos bytes que
    entraram" só vale contra o que de fato saiu do gravador."""

    def __init__(self, quadros: int = 1) -> None:
        self.emitidos: list[bytes] = []
        self._quadros = quadros

    def stream_clip(self, camera_id, start, end):
        clip = b"".join(
            _gradient_jpeg(quality=90, flip=(i % 2 == 0)) for i in range(self._quadros)
        )
        self.emitidos.extend(_split_mjpeg(clip))
        yield clip


def _tamanho(jpeg: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(jpeg)).size


class TestModoFrameCheio:
    def test_DEFAULT_continua_subindo_RECORTE(self) -> None:
        """NÃO-REGRESSÃO. Este é o teste mais importante do arquivo novo: o
        modo que roda em produção hoje não muda em nada."""
        gravador = _GravadorQueRegistra()
        uploads: list = []
        miner = _make_miner(gravador, uploads, person_detector=_PessoaPequena())

        stats = miner.mine(_make_plan(1))

        assert stats.modo == "recorte"
        assert len(uploads) == 1
        subido = uploads[0]["frame_bytes"]
        assert subido != gravador.emitidos[0], "default subiu o frame cheio — regressão"
        # recorte da caixa 20x20 com margem (0.25 x, 0.08 y) sobre um frame 80x60
        assert _tamanho(subido) == (30, 22)
        assert _tamanho(gravador.emitidos[0]) == (80, 60)

    def test_frame_cheio_sobe_o_quadro_INTEIRO_com_os_MESMOS_bytes(self) -> None:
        """Inteiro E intacto: sem re-encode, os bytes que entraram são os que
        sobem. Re-encodar aqui reintroduziria perda no dado de treino."""
        gravador = _GravadorQueRegistra()
        uploads: list = []
        miner = _make_miner(
            gravador, uploads, person_detector=_PessoaPequena(), full_frame=True
        )

        stats = miner.mine(_make_plan(1))

        assert stats.modo == "frame_cheio"
        assert len(uploads) == 1
        assert uploads[0]["frame_bytes"] == gravador.emitidos[0]
        assert _tamanho(uploads[0]["frame_bytes"]) == (80, 60)
        assert stats.bytes_uploaded == len(gravador.emitidos[0])

    def test_sem_pessoa_DESCARTA_nos_dois_modos(self) -> None:
        """O gate é o mesmo. Sem ele, o modo frame-cheio vira coletor de
        corredor vazio — que é exatamente o que o gate de pessoa existe para
        não ser (person_detector docstring)."""
        for full_frame in (False, True):
            uploads: list = []
            miner = _make_miner(
                _GravadorQueRegistra(), uploads,
                person_detector=_PessoaPequena(found=False), full_frame=full_frame,
            )
            stats = miner.mine(_make_plan(1))
            assert uploads == [], f"full_frame={full_frame} subiu quadro sem pessoa"
            assert stats.crops_dropped_no_person == 1
            assert stats.crops_kept == 0

    def test_undetermined_DESCARTA_nos_dois_modos(self) -> None:
        """Diferente do CollectorLoop, que sobe o frame inteiro quando o
        detector não opina: replay não tem janela perecível para justificar
        quadro ambíguo."""
        for full_frame in (False, True):
            uploads: list = []
            miner = _make_miner(
                _GravadorQueRegistra(), uploads,
                person_detector=_PessoaPequena(undetermined=True), full_frame=full_frame,
            )
            stats = miner.mine(_make_plan(1))
            assert uploads == [], f"full_frame={full_frame} subiu quadro indeterminado"
            assert stats.crops_dropped_undetermined == 1

    def test_blur_vale_no_modo_frame_cheio(self) -> None:
        uploads: list = []
        miner = _make_miner(
            _GravadorQueRegistra(), uploads, person_detector=_PessoaPequena(),
            full_frame=True, blur_min_variance=10**9,  # nada passa
        )
        stats = miner.mine(_make_plan(1))
        assert uploads == []
        assert stats.crops_dropped_blurry == 1

    def test_dedup_vale_no_modo_frame_cheio(self) -> None:
        """Dois quadros IDÊNTICOS na mesma janela: o segundo cai, mesmo com o
        limiar 0 do modo — cena congelada de verdade continua sendo duplicata."""
        class _DoisIguais(_GravadorQueRegistra):
            def stream_clip(self, camera_id, start, end):
                quadro = _gradient_jpeg(quality=90)
                self.emitidos.extend([quadro, quadro])
                yield quadro + quadro

        uploads: list = []
        miner = _make_miner(
            _DoisIguais(), uploads, person_detector=_PessoaPequena(), full_frame=True
        )
        stats = miner.mine(_make_plan(1))
        assert len(uploads) == 1
        assert stats.crops_dropped_duplicate == 1

    def test_reserva_de_disco_insuficiente_nao_sobe_NADA_nos_dois_modos(self) -> None:
        for full_frame in (False, True):
            gravador = _GravadorQueRegistra()
            uploads: list = []
            miner = _make_miner(
                gravador, uploads, person_detector=_PessoaPequena(),
                full_frame=full_frame, disk_check_fn=lambda: False,
            )
            stats = miner.mine(_make_plan(2))
            assert uploads == [], f"full_frame={full_frame} subiu com o disco no piso"
            assert gravador.emitidos == [], "nem chegou a falar com o gravador"
            assert stats.aborted_reason == "disk_reserve"

    def test_frame_cheio_confere_o_disco_por_JANELA_o_default_por_TAREFA(self) -> None:
        """Mesmo piso, cadência diferente — e a diferença é de propósito.

        Uma tarefa cobre dezenas de janelas; no modo frame-cheio cada janela
        move ~4x mais bytes (medido, ver EstimateParams.avg_full_frame_kb).
        Conferir só na virada de tarefa deixaria o resto do box cruzar a
        reserva e ficar horas sem ninguém olhar. O default NÃO ganha a
        checagem extra: seu caminho fica byte a byte o de hoje.
        """
        def _disco_acaba_depois_da_primeira_pergunta():
            respostas = [True]

            def _check() -> bool:
                return respostas.pop(0) if respostas else False

            return _check

        cheio_uploads: list = []
        gravador_cheio = _GravadorQueRegistra()
        cheio = _make_miner(
            gravador_cheio, cheio_uploads, person_detector=_PessoaPequena(),
            full_frame=True, disk_check_fn=_disco_acaba_depois_da_primeira_pergunta(),
        )
        stats_cheio = cheio.mine(_make_plan(2))
        assert gravador_cheio.emitidos == [], "janela puxada com o disco no piso"
        assert cheio_uploads == []
        assert stats_cheio.aborted_reason == "disk_reserve"

        # Mesmo gravador, mesmo disco, modo default: a primeira tarefa roda
        # inteira, porque a checagem por janela é EXCLUSIVA do modo novo.
        rec_uploads: list = []
        recorte = _make_miner(
            _GravadorQueRegistra(), rec_uploads, person_detector=_PessoaPequena(),
            disk_check_fn=_disco_acaba_depois_da_primeira_pergunta(),
        )
        recorte.mine(_make_plan(2))
        assert len(rec_uploads) == 1, "o caminho do default mudou — regressão"


class TestDedupNoFrameCheioEDiferente:
    """MEDIDO 2026-09-02: o dHash de um frame cheio é quase cego a uma pessoa.

    A grade do dHash é 9x8 sobre a imagem toda, então uma pessoa ocupa menos que
    uma célula e pode ANDAR sem virar bit nenhum. Com o limiar calibrado para
    recorte (<=6 de 64), a colheita de uma câmera fixa cairia quase inteira como
    "duplicata" — silenciosamente, que é o modo de falha que este módulo já
    pagou caro (2601 janelas vazias com cara de domingo).
    """

    @staticmethod
    def _cena(pessoa_x: int) -> bytes:
        """640x360, fundo fixo texturado, 'pessoa' de 20x90 na posição dada."""
        img = Image.new("RGB", (640, 360), (128, 128, 128))
        px = img.load()
        for x in range(0, 640, 4):
            for y in range(360):
                px[x, y] = (90, 95, 100)
        for y in range(200, 360, 8):
            for x in range(640):
                px[x, y] = (150, 148, 145)
        for x in range(pessoa_x, min(640, pessoa_x + 20)):
            for y in range(230, 320):
                px[x, y] = (30, 30, 35)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def test_limiar_do_RECORTE_apagaria_a_colheita_de_frame_cheio(self) -> None:
        from app.collector.replay_miner import _DEFAULT_DEDUP_HAMMING_MAX

        antes, depois = self._cena(150), self._cena(180)  # pessoa andou 30px
        com_limiar_de_recorte = NearDuplicateFilter(
            hamming_threshold=_DEFAULT_DEDUP_HAMMING_MAX
        )
        assert com_limiar_de_recorte.is_duplicate("cam-1", antes) is False
        assert com_limiar_de_recorte.is_duplicate("cam-1", depois) is True, (
            "pessoa andou 30px e o frame passou por duplicata — se ISTO parar de "
            "valer, o limiar do modo frame-cheio pode voltar a ser o do recorte"
        )

    def test_limiar_do_MODO_mantem_o_mesmo_par(self) -> None:
        from app.collector.replay_miner import _DEFAULT_DEDUP_HAMMING_FULL_FRAME

        antes, depois = self._cena(150), self._cena(180)
        do_modo = NearDuplicateFilter(hamming_threshold=_DEFAULT_DEDUP_HAMMING_FULL_FRAME)
        assert do_modo.is_duplicate("cam-1", antes) is False
        assert do_modo.is_duplicate("cam-1", depois) is False
        # ...e continua descartando cena REALMENTE congelada
        assert do_modo.is_duplicate("cam-1", antes) is True

    def test_o_default_do_modo_frame_cheio_e_mais_frouxo_que_o_do_recorte(self) -> None:
        from app.collector.replay_miner import (
            _DEFAULT_DEDUP_HAMMING_FULL_FRAME,
            _DEFAULT_DEDUP_HAMMING_MAX,
        )

        assert _DEFAULT_DEDUP_HAMMING_FULL_FRAME < _DEFAULT_DEDUP_HAMMING_MAX


class TestResumoGritaQuandoOFiltroComeAColheita:
    """Sem isto o modo novo pode voltar vazio parecendo normal — o defeito que
    custou 2601 janelas silenciosas em 18/08, com outra roupa."""

    def test_duplicata_dominante_aparece_no_resumo(self) -> None:
        from app.collector.replay_miner import MiningStats, _resumo_do_ciclo

        texto = _resumo_do_ciclo(MiningStats(
            modo="frame_cheio", windows_pulled=10, crops_kept=2,
            crops_dropped_duplicate=98,
        ))
        assert "frame_cheio" in texto
        assert "REPLAY_MINER_DEDUP_HAMMING" in texto
        assert "98%" in texto or "98/100" in texto

    def test_colheita_saudavel_nao_grita(self) -> None:
        from app.collector.replay_miner import MiningStats, _resumo_do_ciclo

        texto = _resumo_do_ciclo(MiningStats(
            modo="frame_cheio", windows_pulled=10, crops_kept=80,
            crops_dropped_duplicate=20, bytes_uploaded=80 * 157 * 1024,
        ))
        assert "comendo a colheita" not in texto
        assert "157.0 KB/frame" in texto  # custo medido, não estimado


class TestVinculoComOFrameDeOrigem:
    """O recorte minerado sobe com a caixa de onde saiu (migration 132).

    A mineração de replay produz RECORTE por definição; sem o vínculo, cada
    recorte minerado nasce órfão do frame cheio — que é onde o modelo é
    SERVIDO. Foi assim que 5.259 recortes anotados do RVB se perderam.
    """

    def test_recorte_leva_a_caixa_em_coordenadas_do_frame_original(self) -> None:
        """Conta à mão: pessoa 20x20 em (10,10) num frame 80x60, margem
        0.25x/0.08y -> mx=5, my=1 -> caixa (5, 9) de 30x22, que é exatamente o
        tamanho do JPEG que sobe."""
        gravador = _GravadorQueRegistra()
        uploads: list = []
        miner = _make_miner(gravador, uploads, person_detector=_PessoaPequena())

        miner.mine(_make_plan(1))

        origem = uploads[0]["crop_origin"]
        assert origem == {"box": [5, 9, 30, 22], "source_size": [80, 60]}
        assert _tamanho(uploads[0]["frame_bytes"]) == tuple(origem["box"][2:])

    def test_modo_frame_cheio_sobe_sem_vinculo(self) -> None:
        """Não houve recorte: a imagem já É o quadro inteiro. NULL é a leitura
        certa, não um dado faltando."""
        gravador = _GravadorQueRegistra()
        uploads: list = []
        miner = _make_miner(
            gravador, uploads, person_detector=_PessoaPequena(), full_frame=True
        )

        miner.mine(_make_plan(1))

        assert uploads[0]["crop_origin"] is None
