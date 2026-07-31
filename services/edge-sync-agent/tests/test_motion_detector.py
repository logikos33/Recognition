"""Tests: detecção de movimento por fração de ÁREA alterada.

Regressão de campo (RVB, 2026-07-31): a versão anterior usava a diferença
MÉDIA do quadro com limiar 8.0 e enchia o bucket. Ruído de compressão e
tremulação de luz marcavam 8.19/8.70 — colados no limiar — e disparavam
rajada atrás de rajada de quadro inútil; movimento real marcava 30-43.
Contar área alterada separa os dois casos por construção.
"""

import io

from PIL import Image

from app.collector.motion_detector import (
    MotionDetector,
    MotionResult,
    frame_diff_score,
    motion_area_fraction,
)

_W, _H = 64, 48


def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _solid(level: int) -> bytes:
    return _jpeg(Image.new("RGB", (_W, _H), (level, level, level)))


def _solid_with_patch(level: int, patch_level: int, frac: float) -> bytes:
    """Cena `level` com um retângulo `patch_level` cobrindo ~frac da área —
    simula algo entrando em cena."""
    img = Image.new("RGB", (_W, _H), (level, level, level))
    patch_w = max(1, int(_W * frac))
    for x in range(patch_w):
        for y in range(_H):
            img.putpixel((x, y), (patch_level, patch_level, patch_level))
    return _jpeg(img)


_SCENE = _solid(100)


def test_identical_frames_have_zero_area():
    assert motion_area_fraction(_SCENE, _solid(100)) < 0.01


def test_global_brightness_shift_is_not_motion():
    """O caso que quebrava antes: luz do galpão oscila e TODO pixel muda um
    pouco. Na média isso passava do limiar; em área, não conta."""
    dim = _solid(108)  # +8 em todo pixel, abaixo do delta de 25
    assert motion_area_fraction(_SCENE, dim) < 0.02


def test_object_entering_scene_is_motion():
    with_object = _solid_with_patch(100, 220, frac=0.25)
    assert motion_area_fraction(_SCENE, with_object) > 0.2


def test_first_detect_call_never_reports_motion():
    detector = MotionDetector()
    assert detector.detect(_SCENE) == MotionResult(changed=False, score=0.0)


def test_detector_ignores_brightness_flicker():
    detector = MotionDetector()
    detector.detect(_SCENE)
    assert detector.detect(_solid(108)).changed is False


def test_detector_triggers_on_real_movement():
    detector = MotionDetector()
    detector.detect(_SCENE)
    result = detector.detect(_solid_with_patch(100, 220, frac=0.25))
    assert result.changed is True
    assert result.score > MotionDetector.DEFAULT_MIN_AREA


def test_detector_updates_previous_each_call():
    detector = MotionDetector()
    moved = _solid_with_patch(100, 220, frac=0.25)
    detector.detect(_SCENE)
    detector.detect(moved)
    # 3º frame igual ao 2º -> cena voltou a ficar parada
    assert detector.detect(moved).changed is False


def test_custom_threshold_is_respected():
    detector = MotionDetector(threshold=0.99)  # inatingível
    detector.detect(_SCENE)
    assert detector.detect(_solid_with_patch(100, 220, frac=0.25)).changed is False


def test_small_change_below_area_threshold_is_ignored():
    """Objeto minúsculo (1% do quadro) não vale uma rajada de frames."""
    detector = MotionDetector(threshold=0.05)
    detector.detect(_SCENE)
    assert detector.detect(_solid_with_patch(100, 220, frac=0.01)).changed is False


# frame_diff_score segue existindo, mas só pro dedup intra-burst
def test_frame_diff_score_still_available_for_dedup():
    assert frame_diff_score(_SCENE, _solid(100)) < 1.0
    assert frame_diff_score(_SCENE, _solid(255)) > 100.0
