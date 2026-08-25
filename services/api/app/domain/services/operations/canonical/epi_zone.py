"""
Recognition — EpiZoneOperation.

Zona de vigilância EPI: alerta quando classe de não-conformidade (no_*) é detectada
dentro de um polígono configurado. Específico do módulo 'epi'.

Tuning por câmera:
  exclude_zones     — lista de polígonos de exclusão; detecções com centro dentro são ignoradas.
  day_night_profile — threshold diferente por período: dia 6h-18h, noite 0h-6h e 18h-24h.
                      Requer frame_meta['hour'] (int 0-23). Sem perfil: usa confidence_threshold fixo.
"""
import logging

from app.constants import EpiClass
from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)

_VALID_EPI_CLASSES = {e.value for e in EpiClass}

# Período de dia: 6h (inclusive) a 18h (exclusive). Fora deste intervalo = noite.
_DAY_HOUR_START = 6
_DAY_HOUR_END = 18


class EpiZoneOperation(BaseOperation):
    """Zona EPI: alerta se classe de não-conformidade for detectada dentro da zona."""

    type_id = "epi_zone"
    type_label = "Zona EPI"
    available_modules = ["epi"]
    description = "Alerta quando classe de EPI negativo é detectada dentro de uma zona definida."
    metric_options = ["violation_detected", "violation_count"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["zone_points", "watch_classes"],
        "properties": {
            "zone_points": {
                "type": "array",
                "title": "Pontos da zona",
                "description": "Polígono da zona de vigilância — mínimo 3 pontos [x,y] normalizados [0,1]",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "watch_classes": {
                "type": "array",
                "title": "Classes a vigiar",
                # ⛔ SEM `enum` de propósito. O enum era `EpiClass`
                # (helmet/no_helmet/vest/…), a taxonomia de demonstração da era
                # COCO, e a tela oferecia SÓ aquelas 8 — nenhuma existe no
                # cadastro de cliente real. Medido: um admin do RVB tentando
                # `['Sem protetor de ouvido']` levava
                # "classe inválida: não pertence ao módulo epi".
                #
                # As classes válidas são as do CADASTRO do tenant e mudam por
                # cliente, então não cabem num esquema estático. Quem valida é
                # `validate_config` (com o tenant em mãos); quem preenche a tela
                # é GET /api/modules/epi/classes, que já devolve
                # catálogo global ∪ classes do tenant.
                "description": (
                    "Classes de EPI a monitorar nesta zona. As opções vêm do "
                    "cadastro do cliente (GET /api/modules/epi/classes)."
                ),
                "items": {"type": "string"},
                "minItems": 1,
            },
            "confidence_threshold": {
                "type": "number",
                "title": "Confiança mínima",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.5,
            },
            "exclude_zones": {
                "type": "array",
                "title": "Zonas de exclusão",
                "description": (
                    "Lista de polígonos de exclusão. Detecções cujo centro cair dentro de qualquer "
                    "zona são ignoradas. Cada polígono: lista de pontos [x,y] normalizados [0,1], "
                    "mínimo 3 pontos. Default [] (sem exclusão)."
                ),
                "default": [],
                "items": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number", "minimum": 0, "maximum": 1},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "minItems": 3,
                },
            },
            "day_night_profile": {
                "type": "object",
                "title": "Perfil dia/noite",
                "description": (
                    "Threshold de confiança diferente por período. "
                    "Dia: 6h-18h; Noite: 0h-6h e 18h-24h. "
                    "Requer frame_meta['hour'] (int 0-23). "
                    "Se ausente ou sem 'hour' no frame: usa confidence_threshold fixo."
                ),
                "default": None,
                "properties": {
                    "day": {
                        "type": "object",
                        "properties": {
                            "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                        },
                        "required": ["confidence"],
                    },
                    "night": {
                        "type": "object",
                        "properties": {
                            "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                        },
                        "required": ["confidence"],
                    },
                },
                "required": ["day", "night"],
            },
        },
    }

    def _classes_validas(self) -> set[str]:
        """Classes (lower) que existem para ESTE cliente.

        Catálogo global ∪ classes do tenant — a mesma fonte que a polaridade
        usa (ADR-0065). Sem `tenant_id` cai no enum histórico: caller antigo e
        teste continuam funcionando, e a lista fixa deixa de ser a regra para
        virar só o último recurso.
        """
        if not self.tenant_id:
            return {c.lower() for c in _VALID_EPI_CLASSES}
        try:
            from app.infrastructure.database.connection import (  # noqa: PLC0415
                DatabasePool,
            )
            from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
                AlertRepository,
            )

            pool = DatabasePool.get_instance()
            if pool is None:
                return {c.lower() for c in _VALID_EPI_CLASSES}
            repo = AlertRepository(pool)
            do_cadastro = set(repo.presence_class_names(self.tenant_id, "epi")) | set(
                repo.violation_class_names(self.tenant_id, "epi")
            )
        except Exception as exc:  # noqa: BLE001
            # Falha de leitura NÃO pode virar "nada é válido" — isso travaria a
            # configuração inteira. Cai no enum histórico e avisa.
            logger.warning(
                "epi_zone_classes_do_cadastro_falhou: tenant=%s err=%s — "
                "usando a lista histórica", self.tenant_id, exc,
            )
            return {c.lower() for c in _VALID_EPI_CLASSES}
        # União com o enum: nome técnico do catálogo global continua aceito.
        return do_cadastro | {c.lower() for c in _VALID_EPI_CLASSES}

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        zone = config.get("zone_points", [])
        if len(zone) < 3:
            errors.append("zone_points precisa ter ao menos 3 pontos")
        watch = config.get("watch_classes") or []
        if not watch:
            errors.append("watch_classes é obrigatório e não pode ser vazio")
        validas = self._classes_validas()
        for cls in watch:
            if cls.strip().lower() not in validas:
                errors.append(
                    f"classe inválida: {cls!r} não pertence ao módulo epi "
                    f"deste cliente"
                )

        # Validar exclude_zones
        exclude_zones = config.get("exclude_zones") or []
        for idx, ez in enumerate(exclude_zones):
            if len(ez) < 3:
                errors.append(f"exclude_zones[{idx}] precisa ter ao menos 3 pontos")
                continue
            for pidx, pt in enumerate(ez):
                if len(pt) != 2:
                    errors.append(f"exclude_zones[{idx}][{pidx}] deve ser [x, y]")
                else:
                    x, y = pt
                    if not (0 <= x <= 1) or not (0 <= y <= 1):
                        errors.append(
                            f"exclude_zones[{idx}][{pidx}] coordenadas devem estar em [0,1]"
                        )

        # Validar day_night_profile
        profile = config.get("day_night_profile")
        if profile is not None:
            for period in ("day", "night"):
                p = profile.get(period)
                if p is None:
                    errors.append(f"day_night_profile.{period} é obrigatório")
                else:
                    c = p.get("confidence")
                    if c is None or not (0.1 <= float(c) <= 1.0):
                        errors.append(
                            f"day_night_profile.{period}.confidence deve estar em [0.1, 1.0]"
                        )

        return errors

    def _get_threshold(self, frame_meta: dict) -> float:
        """Retorna threshold de confiança considerando day_night_profile.

        Dia: 6h-18h (inclusive início, exclusive fim).
        Noite: 0h-6h e 18h-24h.
        Sem perfil configurado ou sem 'hour' em frame_meta: usa confidence_threshold fixo.
        """
        profile = self.config.get("day_night_profile")
        hour = frame_meta.get("hour")
        if profile and hour is not None:
            period = "day" if _DAY_HOUR_START <= int(hour) < _DAY_HOUR_END else "night"
            return float(profile[period]["confidence"])
        return float(self.config.get("confidence_threshold", 0.5))

    def _in_any_exclude_zone(self, cx: float, cy: float) -> bool:
        """Retorna True se ponto (cx, cy) está dentro de alguma zona de exclusão."""
        for zone in self.config.get("exclude_zones") or []:
            if _point_in_polygon(cx, cy, zone):
                return True
        return False

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        zone_points = self.config.get("zone_points", [])
        watch_classes = set(self.config.get("watch_classes", []))
        threshold = self._get_threshold(frame_meta)
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        violations = []
        for det in detections:
            cls = det.get("class", "").lower()
            if cls not in watch_classes or det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if self._in_any_exclude_zone(cx, cy):
                continue
            if _point_in_polygon(cx, cy, zone_points):
                violations.append({"class": cls, "cx": cx, "cy": cy, "confidence": det["confidence"]})

        detected = len(violations) > 0
        return {
            "result": {"violations": violations, "count": len(violations)},
            "metric_value": len(violations),
            "condition_satisfied": detected,
            "state_next": state,
        }
