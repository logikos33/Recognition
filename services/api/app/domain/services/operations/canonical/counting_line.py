"""
Recognition — CountingLineOperation.

Conta objetos que cruzam uma linha virtual, com histerese por zona de
confirmação (CD-01) e voto multi-amostra (task-038):

- Ponto de referência configurável: inferior central da bbox (padrão,
  como o nvdsanalytics) ou centróide (`anchor_point`).
- `confirm_samples`: track só fica elegível para contar após ser visto
  em N frames (filtra ruído de detecção/ID novo).
- `direction_debounce_frames`: após contar um cruzamento, o mesmo track
  não conta de novo na MESMA direção por N frames.
- `confirmation_band`: banda de histerese ao redor da linha (coordenada
  normalizada, como todo o arquivo) — cruzamento só é confirmado quando
  o anchor sai da banda do outro lado; objeto oscilando sobre a linha
  não gera contagens múltiplas.
- `counted_track_ids` no estado: anti-dupla-contagem por sessão de
  avaliação, com expiração junto do track (não cresce para sempre).

Convenção de direção: "in" = cruzamento para o lado POSITIVO do vetor
A→B da linha (lado esquerdo); "out" = lado negativo. Para inverter,
basta trocar a ordem dos pontos em `line_points`.
"""
import logging

from app.domain.services.operations.base import BaseOperation

logger = logging.getLogger(__name__)

# Distância máxima (normalizada) para associar detecção sem track_id a um
# track posicional existente (tracking best-effort por posição).
_POS_MATCH_RADIUS = 0.05
# Tolerância de frames sem ver um track posicional antes de criar outro.
_POS_MATCH_MAX_GAP = 2


class CountingLineOperation(BaseOperation):
    """Conta cruzamentos de linha por track, com histerese e debounce.

    Mantém contadores cumulativos in/out no estado entre frames.
    O campo `direction` define a métrica exposta ('in', 'out' ou 'both');
    os dois sentidos são sempre acumulados no estado.
    """

    type_id = "counting_line"
    type_label = "Contagem por cruzamento de linha"
    available_modules = ["*"]
    description = (
        "Conta objetos que cruzam uma linha virtual, com zona de confirmação "
        "(histerese) e voto multi-amostra anti dupla contagem."
    )
    metric_options = ["count_in", "count_out", "count_net"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["target_class", "line_points"],
        "properties": {
            "target_class": {
                "type": "string",
                "title": "Classe monitorada",
                "description": "Classe YOLO a contar (ex: 'roll', 'person')",
            },
            "line_points": {
                "type": "array",
                "title": "Pontos da linha",
                "description": "Dois pontos [x, y] normalizados [0,1] — direção 'in' é o "
                               "lado esquerdo do vetor A→B",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 2,
                "maxItems": 2,
            },
            "direction": {
                "type": "string",
                "title": "Direção contabilizada",
                "enum": ["in", "out", "both"],
                "default": "both",
            },
            "anchor_point": {
                "type": "string",
                "title": "Ponto de referência",
                "description": "Ponto da bbox usado no cruzamento "
                               "(inferior central é o padrão do nvdsanalytics)",
                "enum": ["bottom_center", "centroid"],
                "default": "bottom_center",
            },
            "confirm_samples": {
                "type": "integer",
                "title": "Amostras de confirmação",
                "description": "Track só conta após ser visto em N frames",
                "minimum": 1,
                "default": 3,
            },
            "direction_debounce_frames": {
                "type": "integer",
                "title": "Debounce por direção (frames)",
                "description": "Mesmo track não conta de novo na mesma direção por N frames",
                "minimum": 0,
                "default": 5,
            },
            "confirmation_band": {
                "type": "number",
                "title": "Banda de confirmação (normalizada)",
                "description": "Histerese: cruzamento só confirma quando o anchor sai da "
                               "banda do outro lado da linha (0 = desligada)",
                "minimum": 0,
                "maximum": 0.5,
                "default": 0.0,
            },
            "track_memory_frames": {
                "type": "integer",
                "title": "Memória de track (frames)",
                "description": "Expira estado de tracks não vistos há N frames "
                               "(anti crescimento infinito)",
                "minimum": 1,
                "default": 300,
            },
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.5,
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        """Valida configuração — campos novos têm default (configs antigas seguem válidas)."""
        errors: list[str] = []
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")

        line = config.get("line_points", [])
        if len(line) != 2 or any(len(p) != 2 for p in line):
            errors.append("line_points precisa de exatamente 2 pontos [x, y]")
        elif line[0][0] == line[1][0] and line[0][1] == line[1][1]:
            errors.append("line_points não podem ser coincidentes")

        if config.get("direction", "both") not in ("in", "out", "both"):
            errors.append("direction deve ser 'in', 'out' ou 'both'")
        if config.get("anchor_point", "bottom_center") not in ("bottom_center", "centroid"):
            errors.append("anchor_point deve ser 'bottom_center' ou 'centroid'")

        if "confirm_samples" in config and not (
            _is_int(config["confirm_samples"]) and config["confirm_samples"] >= 1
        ):
            errors.append("confirm_samples deve ser inteiro >= 1")
        if "direction_debounce_frames" in config and not (
            _is_int(config["direction_debounce_frames"])
            and config["direction_debounce_frames"] >= 0
        ):
            errors.append("direction_debounce_frames deve ser inteiro >= 0")
        if "track_memory_frames" in config and not (
            _is_int(config["track_memory_frames"]) and config["track_memory_frames"] >= 1
        ):
            errors.append("track_memory_frames deve ser inteiro >= 1")
        if "confirmation_band" in config and not (
            _is_number(config["confirmation_band"])
            and 0 <= config["confirmation_band"] <= 0.5
        ):
            errors.append("confirmation_band deve ser número entre 0 e 0.5")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        """Avalia cruzamentos da linha pelos tracks da classe alvo.

        Args:
            detections: Detecções YOLO [{class, confidence, bbox:[x,y,w,h], track_id}, ...]
            frame_meta: Metadados do frame {camera_id, timestamp, width, height, frame_index?}
            state:      Estado persistente: frame_index, counts, tracks, counted_track_ids.
        """
        target_class = self.config.get("target_class", "")
        line_points = self.config.get("line_points", [])
        direction_cfg = self.config.get("direction", "both")
        anchor_mode = self.config.get("anchor_point", "bottom_center")
        confirm_samples = int(self.config.get("confirm_samples", 3))
        debounce = int(self.config.get("direction_debounce_frames", 5))
        band = float(self.config.get("confirmation_band", 0.0))
        memory = int(self.config.get("track_memory_frames", 300))
        threshold = self.config.get("confidence_threshold", 0.5)

        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)
        frame_index = int(frame_meta.get("frame_index", int(state.get("frame_index", 0)) + 1))

        counts: dict = {"in": 0, "out": 0}
        counts.update(state.get("counts") or {})
        tracks: dict = {k: dict(v) for k, v in (state.get("tracks") or {}).items()}
        counted: dict = {k: dict(v) for k, v in (state.get("counted_track_ids") or {}).items()}
        next_pos_id = int(state.get("next_pos_id", 0))

        matching = [
            d for d in detections
            if d.get("class", "").lower() == target_class.lower()
            and d.get("confidence", 0) >= threshold
        ]

        crossings: list[dict] = []
        matched_keys: set[str] = set()
        for det in matching:
            bbox = det.get("bbox", [0, 0, 0, 0])
            ax, ay = _anchor(bbox, anchor_mode, frame_w, frame_h)
            key, next_pos_id = _resolve_track_key(
                det, (ax, ay), tracks, matched_keys, frame_index, next_pos_id
            )
            matched_keys.add(key)

            track = tracks.get(key) or {"samples": 0, "side": None}
            track["samples"] = int(track.get("samples", 0)) + 1
            track["last_seen"] = frame_index
            track["anchor"] = [round(ax, 4), round(ay, 4)]

            dist = _signed_distance(ax, ay, line_points)
            if abs(dist) > band:
                side_now = 1 if dist > 0 else -1
                prev_side = track.get("side")
                if prev_side is None:
                    track["side"] = side_now
                elif side_now != prev_side:
                    crossed = "in" if side_now > 0 else "out"
                    entry = counted.get(key) or {"in": None, "out": None}
                    last = entry.get(crossed)
                    eligible = track["samples"] >= confirm_samples
                    debounced = last is not None and (frame_index - last) <= debounce
                    if eligible and not debounced:
                        counts[crossed] += 1
                        entry[crossed] = frame_index
                        counted[key] = entry
                        crossings.append({
                            "track_id": key,
                            "direction": crossed,
                            "anchor": [round(ax, 4), round(ay, 4)],
                        })
                        logger.debug(
                            "line_crossing_counted: track=%s direction=%s frame=%s",
                            key, crossed, frame_index,
                        )
                    # Lado sempre atualiza — cruzamento não elegível/debounced
                    # é descartado, não contado com atraso depois.
                    track["side"] = side_now
            # Dentro da banda: lado mantido (histerese) — oscilação não conta.
            tracks[key] = track

        # Expiração: tracks não vistos há mais de `memory` frames saem do estado;
        # counted_track_ids expira junto (não cresce para sempre).
        tracks = {
            k: t for k, t in tracks.items()
            if frame_index - int(t.get("last_seen", frame_index)) <= memory
        }
        counted = {
            k: v for k, v in counted.items()
            if k in tracks or _within_memory(v, frame_index, memory)
        }

        net = counts["in"] - counts["out"]
        events = [c for c in crossings if direction_cfg in ("both", c["direction"])]
        if direction_cfg == "in":
            metric_value: object = counts["in"]
        elif direction_cfg == "out":
            metric_value = counts["out"]
        else:
            metric_value = {"in": counts["in"], "out": counts["out"], "net": net}

        return {
            "result": {
                "counts": {"in": counts["in"], "out": counts["out"], "net": net},
                "crossings": crossings,
                "active_tracks": len(tracks),
            },
            "metric_value": metric_value,
            "condition_satisfied": len(events) > 0,
            "state_next": {
                "frame_index": frame_index,
                "counts": counts,
                "tracks": tracks,
                "counted_track_ids": counted,
                "next_pos_id": next_pos_id,
            },
        }


def _is_int(value) -> bool:
    """True se inteiro de verdade (bool é rejeitado — edge case Python)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    """True se int ou float (bool é rejeitado)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _anchor(bbox: list, mode: str, fw: int, fh: int) -> tuple[float, float]:
    """Ponto de referência normalizado da bbox [x, y, w, h] em pixels."""
    x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
    if mode == "centroid":
        return (x + w / 2) / fw, (y + h / 2) / fh
    return (x + w / 2) / fw, (y + h) / fh


def _signed_distance(px: float, py: float, line_points: list) -> float:
    """Distância assinada (normalizada) do ponto à linha A→B.

    Positivo = lado esquerdo do vetor A→B ('in'); negativo = direito ('out').
    """
    ax, ay = line_points[0][0], line_points[0][1]
    bx, by = line_points[1][0], line_points[1][1]
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return 0.0
    return (dx * (py - ay) - dy * (px - ax)) / length


def _resolve_track_key(
    det: dict,
    anchor: tuple[float, float],
    tracks: dict,
    matched: set,
    frame_index: int,
    next_pos_id: int,
) -> tuple[str, int]:
    """Chave do track: track_id do tracker ou fallback posicional best-effort."""
    track_id = det.get("track_id")
    if track_id is not None:
        return f"t:{track_id}", next_pos_id

    best_key = None
    best_dist = _POS_MATCH_RADIUS
    for key, tr in tracks.items():
        if not key.startswith("p:") or key in matched:
            continue
        if frame_index - int(tr.get("last_seen", 0)) > _POS_MATCH_MAX_GAP:
            continue
        pa = tr.get("anchor") or [0.0, 0.0]
        dist = ((anchor[0] - pa[0]) ** 2 + (anchor[1] - pa[1]) ** 2) ** 0.5
        if dist <= best_dist:
            best_key, best_dist = key, dist
    if best_key is not None:
        return best_key, next_pos_id
    return f"p:{next_pos_id}", next_pos_id + 1


def _within_memory(entry: dict, frame_index: int, memory: int) -> bool:
    """True se o último cruzamento contado ainda está dentro da janela de memória."""
    last = max((f for f in entry.values() if f is not None), default=None)
    return last is not None and frame_index - last <= memory
