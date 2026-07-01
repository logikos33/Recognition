"""
Tests: exclude_zones + day_night_profile — tuning por câmera (task-039).

Cobre EpiZoneOperation e DefectTriggerOperation.

Período de dia: 6h-18h (inclusive início, exclusive fim).
Noite: 0h-6h e 18h-24h.
"""
from app.domain.services.operations.canonical.defect_trigger import DefectTriggerOperation
from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation

# ── Cenas de teste ────────────────────────────────────────────────────────────

FRAME_META = {"width": 100, "height": 100}

# Zona de vigilância EPI: quadrado central [0.3-0.7] x [0.3-0.7]
EPI_ZONE = [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]

# ROI da esteira: quadrado inferior [0.2-0.8] x [0.5-0.9]
ROI_POINTS = [[0.2, 0.5], [0.8, 0.5], [0.8, 0.9], [0.2, 0.9]]

# Zona de exclusão: quadrado pequeno canto superior esquerdo [0.0-0.2] x [0.0-0.2]
EXCLUDE_ZONE = [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]]

# Configs base
EPI_CONFIG_BASE = {
    "zone_points": EPI_ZONE,
    "watch_classes": ["no_helmet"],
    "confidence_threshold": 0.5,
}

DEFECT_CONFIG_BASE = {
    "roi_points": ROI_POINTS,
    "trigger_class": "trigger_obj",
    "defect_classes": ["scratch"],
    "confidence_threshold": 0.5,
}

DAY_NIGHT_PROFILE = {
    "day": {"confidence": 0.5},
    "night": {"confidence": 0.7},
}


def _det_epi(cx: float, cy: float, cls: str = "no_helmet", conf: float = 0.8) -> dict:
    """Detecção com centro normalizado para EpiZone (bbox=[x1,y1,w,h] com w=h=0)."""
    fw, fh = FRAME_META["width"], FRAME_META["height"]
    return {"class": cls, "confidence": conf, "bbox": [cx * fw, cy * fh, 0, 0]}


def _det_defect(
    cx: float, cy: float, cls: str = "scratch", conf: float = 0.8
) -> dict:
    """Detecção com centro normalizado para DefectTrigger."""
    fw, fh = FRAME_META["width"], FRAME_META["height"]
    return {"class": cls, "confidence": conf, "bbox": [cx * fw, cy * fh, 0, 0]}


# ═══════════════════════════════════════════════════════════════════════════════
# EpiZoneOperation — exclude_zones
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpiZoneExcludeZones:
    def test_exclude_zone_filters_detection(self):
        """Detecção cujo centro está dentro da exclude_zone não gera alerta."""
        # Usa zona de vigilância que cobre a tela inteira para garantir que
        # a exclusão é o único motivo de a detecção ser filtrada.
        config2 = {
            "zone_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
            "exclude_zones": [EXCLUDE_ZONE],
        }
        op2 = EpiZoneOperation(config2)
        det = _det_epi(0.1, 0.1)  # centro dentro da exclude_zone
        result = op2.evaluate([det], FRAME_META, {})
        assert result["condition_satisfied"] is False
        assert result["result"]["count"] == 0

    def test_exclude_zone_outside_passes(self):
        """Detecção fora da exclude_zone é processada normalmente."""
        config = {
            "zone_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
            "exclude_zones": [EXCLUDE_ZONE],
        }
        op = EpiZoneOperation(config)
        det = _det_epi(0.5, 0.5)  # centro fora da exclude_zone
        result = op.evaluate([det], FRAME_META, {})
        assert result["condition_satisfied"] is True
        assert result["result"]["count"] == 1

    def test_no_exclude_zones_default_behavior(self):
        """Sem exclude_zones configurada, comportamento é idêntico ao original."""
        op = EpiZoneOperation(EPI_CONFIG_BASE)
        det = _det_epi(0.5, 0.5)  # centro dentro do EPI_ZONE
        result = op.evaluate([det], FRAME_META, {})
        assert result["condition_satisfied"] is True

    def test_multiple_exclude_zones(self):
        """Detecção em qualquer das exclude_zones é filtrada."""
        config = {
            "zone_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
            "exclude_zones": [
                EXCLUDE_ZONE,  # canto superior esquerdo
                [[0.8, 0.8], [1.0, 0.8], [1.0, 1.0], [0.8, 1.0]],  # canto inferior direito
            ],
        }
        op = EpiZoneOperation(config)
        det_excluded1 = _det_epi(0.1, 0.1)   # na primeira exclude_zone
        det_excluded2 = _det_epi(0.9, 0.9)   # na segunda exclude_zone
        det_passes = _det_epi(0.5, 0.5)      # fora de ambas

        result = op.evaluate([det_excluded1, det_excluded2, det_passes], FRAME_META, {})
        assert result["result"]["count"] == 1  # só det_passes passa


# ═══════════════════════════════════════════════════════════════════════════════
# EpiZoneOperation — day_night_profile
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpiZoneDayNightProfile:
    def test_day_threshold_applied_at_hour_14(self):
        """Hora=14 (dia) usa threshold do perfil 'day'."""
        config = {
            **EPI_CONFIG_BASE,
            "day_night_profile": DAY_NIGHT_PROFILE,
        }
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 14}
        # conf=0.6 >= day threshold=0.5 → viola
        det = _det_epi(0.5, 0.5, conf=0.6)
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is True

    def test_night_threshold_applied_at_hour_2(self):
        """Hora=2 (noite) usa threshold do perfil 'night' (0.7)."""
        config = {
            **EPI_CONFIG_BASE,
            "day_night_profile": DAY_NIGHT_PROFILE,
        }
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 2}
        # conf=0.6 < night threshold=0.7 → não viola
        det = _det_epi(0.5, 0.5, conf=0.6)
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is False

    def test_night_threshold_at_hour_20(self):
        """Hora=20 (noite) usa threshold do perfil 'night' (0.7)."""
        config = {
            **EPI_CONFIG_BASE,
            "day_night_profile": DAY_NIGHT_PROFILE,
        }
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 20}
        det = _det_epi(0.5, 0.5, conf=0.75)  # conf >= 0.7 → viola
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is True

    def test_day_boundary_hour_6(self):
        """Hora=6 é o início do dia (inclusive) — usa threshold 'day'."""
        config = {**EPI_CONFIG_BASE, "day_night_profile": DAY_NIGHT_PROFILE}
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 6}
        det = _det_epi(0.5, 0.5, conf=0.51)  # conf > day=0.5 → viola
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is True

    def test_night_boundary_hour_18(self):
        """Hora=18 é início da noite (exclusive do dia) — usa threshold 'night'."""
        config = {**EPI_CONFIG_BASE, "day_night_profile": DAY_NIGHT_PROFILE}
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 18}
        det = _det_epi(0.5, 0.5, conf=0.6)  # conf < night=0.7 → não viola
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is False

    def test_no_profile_falls_back_to_confidence_threshold(self):
        """Sem day_night_profile, usa confidence_threshold fixo."""
        config = {**EPI_CONFIG_BASE}  # sem day_night_profile
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META, "hour": 2}  # noite, mas sem perfil → ignora hora
        det = _det_epi(0.5, 0.5, conf=0.6)  # conf >= 0.5 → viola
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is True

    def test_profile_without_hour_falls_back(self):
        """Com day_night_profile mas sem 'hour' em frame_meta → usa confidence_threshold fixo."""
        config = {**EPI_CONFIG_BASE, "day_night_profile": DAY_NIGHT_PROFILE}
        op = EpiZoneOperation(config)
        frame_meta = {**FRAME_META}  # sem 'hour'
        det = _det_epi(0.5, 0.5, conf=0.6)  # conf >= 0.5 → viola
        result = op.evaluate([det], frame_meta, {})
        assert result["condition_satisfied"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# EpiZoneOperation — validate_config (exclude_zones + day_night_profile)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpiZoneValidateConfig:
    def _valid_base(self, **extra) -> dict:
        return {**EPI_CONFIG_BASE, **extra}

    def test_valid_without_new_fields(self):
        op = EpiZoneOperation(self._valid_base())
        assert op.validate_config(op.config) == []

    def test_valid_with_exclude_zones(self):
        op = EpiZoneOperation(self._valid_base(exclude_zones=[EXCLUDE_ZONE]))
        assert op.validate_config(op.config) == []

    def test_valid_with_day_night_profile(self):
        op = EpiZoneOperation(self._valid_base(day_night_profile=DAY_NIGHT_PROFILE))
        assert op.validate_config(op.config) == []

    def test_exclude_zones_too_few_points(self):
        """Polígono com < 3 pontos deve gerar erro."""
        config = self._valid_base(exclude_zones=[[[0.0, 0.0], [0.1, 0.0]]])
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("exclude_zones[0]" in e for e in errors)

    def test_exclude_zones_invalid_coord_gt_1(self):
        """Coordenada > 1 deve gerar erro."""
        config = self._valid_base(
            exclude_zones=[[[0.0, 0.0], [1.5, 0.0], [1.0, 1.0]]]
        )
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("coordenadas" in e for e in errors)

    def test_exclude_zones_invalid_coord_negative(self):
        """Coordenada negativa deve gerar erro."""
        config = self._valid_base(
            exclude_zones=[[[-0.1, 0.0], [0.2, 0.0], [0.1, 0.2]]]
        )
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("coordenadas" in e for e in errors)

    def test_day_night_profile_missing_night_key(self):
        """Perfil sem 'night' deve gerar erro."""
        config = self._valid_base(day_night_profile={"day": {"confidence": 0.5}})
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("night" in e for e in errors)

    def test_day_night_profile_confidence_out_of_range(self):
        """Confidence > 1.0 deve gerar erro."""
        config = self._valid_base(
            day_night_profile={"day": {"confidence": 1.5}, "night": {"confidence": 0.7}}
        )
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("day.confidence" in e for e in errors)

    def test_day_night_profile_confidence_too_low(self):
        """Confidence < 0.1 deve gerar erro."""
        config = self._valid_base(
            day_night_profile={"day": {"confidence": 0.5}, "night": {"confidence": 0.05}}
        )
        op = EpiZoneOperation(config)
        errors = op.validate_config(op.config)
        assert any("night.confidence" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# DefectTriggerOperation — exclude_zones
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefectTriggerExcludeZones:
    def test_exclude_zone_filters_trigger_and_defect(self):
        """Trigger e defeito dentro de exclude_zone são ignorados — nenhuma detecção."""
        config = {
            "roi_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "trigger_class": "trigger_obj",
            "defect_classes": ["scratch"],
            "confidence_threshold": 0.5,
            "exclude_zones": [EXCLUDE_ZONE],
        }
        op = DefectTriggerOperation(config)
        trigger_det = {"class": "trigger_obj", "confidence": 0.9,
                       "bbox": [5, 5, 0, 0]}   # cx=0.05, cy=0.05 → dentro da exclude_zone
        defect_det = {"class": "scratch", "confidence": 0.9,
                      "bbox": [10, 10, 0, 0]}  # cx=0.1, cy=0.1 → dentro da exclude_zone
        result = op.evaluate([trigger_det, defect_det], FRAME_META, {})
        assert result["result"]["trigger_in_roi"] is False
        assert result["result"]["defect_count"] == 0
        assert result["condition_satisfied"] is False

    def test_exclude_zone_outside_passes_defect(self):
        """Detecções fora da exclude_zone são processadas normalmente."""
        config = {
            "roi_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "trigger_class": "trigger_obj",
            "defect_classes": ["scratch"],
            "confidence_threshold": 0.5,
            "exclude_zones": [EXCLUDE_ZONE],
        }
        op = DefectTriggerOperation(config)
        trigger_det = {"class": "trigger_obj", "confidence": 0.9,
                       "bbox": [50, 50, 0, 0]}  # cx=0.5, cy=0.5 → fora da exclude_zone
        defect_det = {"class": "scratch", "confidence": 0.9,
                      "bbox": [60, 60, 0, 0]}   # cx=0.6, cy=0.6 → fora da exclude_zone
        result = op.evaluate([trigger_det, defect_det], FRAME_META, {})
        assert result["result"]["trigger_in_roi"] is True
        assert result["result"]["defect_count"] == 1
        assert result["condition_satisfied"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# DefectTriggerOperation — day_night_profile
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefectTriggerDayNightProfile:
    def _make_op(self, profile: dict | None = None) -> DefectTriggerOperation:
        config = {
            "roi_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "trigger_class": "trigger_obj",
            "defect_classes": ["scratch"],
            "confidence_threshold": 0.5,
        }
        if profile is not None:
            config["day_night_profile"] = profile
        return DefectTriggerOperation(config)

    def _make_dets(self, conf: float) -> list[dict]:
        return [
            {"class": "trigger_obj", "confidence": conf, "bbox": [50, 50, 0, 0]},
            {"class": "scratch", "confidence": conf, "bbox": [60, 60, 0, 0]},
        ]

    def test_day_threshold_applied_at_hour_14(self):
        """Hora=14 (dia) usa threshold 'day' (0.5) — conf=0.6 passa."""
        op = self._make_op(DAY_NIGHT_PROFILE)
        result = op.evaluate(self._make_dets(0.6), {**FRAME_META, "hour": 14}, {})
        assert result["condition_satisfied"] is True

    def test_night_threshold_applied_at_hour_2(self):
        """Hora=2 (noite) usa threshold 'night' (0.7) — conf=0.6 é filtrado."""
        op = self._make_op(DAY_NIGHT_PROFILE)
        result = op.evaluate(self._make_dets(0.6), {**FRAME_META, "hour": 2}, {})
        assert result["condition_satisfied"] is False

    def test_no_profile_falls_back_to_confidence_threshold(self):
        """Sem perfil, hora=2 não importa — usa confidence_threshold=0.5."""
        op = self._make_op(profile=None)
        result = op.evaluate(self._make_dets(0.6), {**FRAME_META, "hour": 2}, {})
        assert result["condition_satisfied"] is True

    def test_profile_without_hour_falls_back(self):
        """Com perfil mas sem 'hour' em frame_meta → usa confidence_threshold fixo."""
        op = self._make_op(DAY_NIGHT_PROFILE)
        result = op.evaluate(self._make_dets(0.6), {**FRAME_META}, {})
        assert result["condition_satisfied"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# DefectTriggerOperation — validate_config (exclude_zones + day_night_profile)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefectTriggerValidateConfig:
    def _valid_base(self, **extra) -> dict:
        return {**DEFECT_CONFIG_BASE, **extra}

    def test_valid_without_new_fields(self):
        op = DefectTriggerOperation(self._valid_base())
        assert op.validate_config(op.config) == []

    def test_valid_with_exclude_zones(self):
        op = DefectTriggerOperation(self._valid_base(exclude_zones=[EXCLUDE_ZONE]))
        assert op.validate_config(op.config) == []

    def test_valid_with_day_night_profile(self):
        op = DefectTriggerOperation(self._valid_base(day_night_profile=DAY_NIGHT_PROFILE))
        assert op.validate_config(op.config) == []

    def test_exclude_zones_too_few_points(self):
        config = self._valid_base(exclude_zones=[[[0.0, 0.0], [0.1, 0.1]]])
        op = DefectTriggerOperation(config)
        errors = op.validate_config(op.config)
        assert any("exclude_zones[0]" in e for e in errors)

    def test_exclude_zones_invalid_coord_gt_1(self):
        config = self._valid_base(
            exclude_zones=[[[0.0, 0.0], [2.0, 0.0], [1.0, 1.0]]]
        )
        op = DefectTriggerOperation(config)
        errors = op.validate_config(op.config)
        assert any("coordenadas" in e for e in errors)

    def test_day_night_profile_missing_day_key(self):
        config = self._valid_base(day_night_profile={"night": {"confidence": 0.7}})
        op = DefectTriggerOperation(config)
        errors = op.validate_config(op.config)
        assert any("day" in e for e in errors)

    def test_day_night_profile_confidence_out_of_range(self):
        config = self._valid_base(
            day_night_profile={"day": {"confidence": 0.5}, "night": {"confidence": 1.2}}
        )
        op = DefectTriggerOperation(config)
        errors = op.validate_config(op.config)
        assert any("night.confidence" in e for e in errors)
