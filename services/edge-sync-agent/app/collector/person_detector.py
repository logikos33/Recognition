"""Gatilho de coleta por PESSOA — YOLOX ONNX (Apache 2.0), só a classe `person`.

ESCOPO: isto é **gatilho de coleta**, NÃO a detecção de EPI do produto. A única
pergunta que responde é "tem gente neste quadro?", pra decidir se vale subir o
frame pro pool de treino. O detector de EPI (capacete/óculos/protetor) é outro
modelo, treinado por cliente, e não passa por aqui.

POR QUÊ: medido em campo na RVB (2026-07-31), o ruído da cena marca mediana
0.39 / máx 0.87 de área alterada e movimento real é raro. Com gatilho só por
movimento o pool enche de corredor vazio — e quadro sem pessoa não treina EPI.
Com o gate de pessoa, todo frame coletado é anotável, e a métrica deixa de ser
"1000 frames" pra ser "N frames COM pessoa".

DUAS ETAPAS: o frame-diff (barato, Pillow puro) continua sendo o pré-filtro —
só quando ele acusa mudança é que o detector roda. Movimento deixa de ser
gatilho final e vira redutor de custo.

LICENÇA: YOLOX é Apache 2.0 (github.com/Megvii-BaseDetection/YOLOX). ZERO
ultralytics/AGPL no caminho servido (ADR-0043). O pré/pós-processamento aqui
espelha `services/api/app/domain/detectors/onnx_yolox.py`, que é a referência
do projeto — reescrito (não importado) porque o edge-sync-agent é um serviço
com deploy próprio, sem dependência do pacote da API.

CPU POR PADRÃO: a wheel `onnxruntime` do PyPI para aarch64 não traz
CUDAExecutionProvider (medido no box: só CPU/Azure disponíveis). Isso é
desejável aqui — 25ms por inferência com poll de 3s é ~1% de ocupação, e a GPU
fica livre pro live view/DeepStream. Não vale trocar por TensorRT enquanto o
custo for esse.

DEGRADAÇÃO: sem onnxruntime, sem numpy ou sem o arquivo do modelo, `is_ready`
fica False e o coletor volta ao gatilho por movimento — nunca para de coletar.

MODELO FORA DO REPO: `.gitignore` linha 45 é política do projeto (pesos vão pra
R2/download). O caminho vem de COLLECTOR_PERSON_MODEL_PATH; o default aponta
pra fora do diretório da release, que rotaciona a cada OTA.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Índice da classe `person` no COCO (o modelo é COCO 80 classes).
_PERSON_CLASS_ID = 0
_DEFAULT_MODEL_PATH = "/home/pandora/recognition/models/yolox_nano.onnx"
_DEFAULT_CONFIDENCE = 0.35
_DEFAULT_NMS_IOU = 0.45
# yolox_nano exportado SEM --decode_in_inference: entrada 416x416, saída
# [1, 3549, 85] com cx/cy/w/h ainda relativos ao grid (verificado no box —
# cx cru varia -2.6..3.4, não 0..416). Por isso `_decode_positions`.
_DEFAULT_INPUT_SIZE = (416, 416)
_STRIDES = (8, 16, 32)
# Ladrilhamento 2x2 com sobreposição — MEDIDO, não escolhido por gosto.
# O substream entrega 704x480; encolher isso pra 416x416 reduz a pessoa a ~59%
# e o YOLOX-nano perde quem está curvado/agachado. Nos 40 frames reais da RVB
# (21 com pessoa, conferidos a olho):
#     quadro inteiro -> recall 52%, precisão 100%,  31 ms
#     2x2 ladrilhado -> recall 90%, precisão  95%,  77 ms
# Baixar o limiar NÃO resolve (0.10 -> 67%; só chega a 86% em 0.05, aí a
# precisão despenca): o problema é escala, não confiança. 77ms com poll de 3s
# é 2,5% de ocupação, e roda em CPU — não disputa GPU com o live view.
# COLLECTOR_PERSON_TILES="1x1" desliga e volta ao quadro inteiro.
_DEFAULT_TILE_GRID = (2, 2)
_TILE_OVERLAP = 0.2  # evita cortar a pessoa exatamente na emenda
# Margem do recorte da pessoa (desfecho C). Generosa acima/abaixo porque o alvo
# desta câmera é EPI de CABEÇA — bbox justo corta o que se quer anotar.
_CROP_MARGIN_X = 0.25
_CROP_MARGIN_Y = 0.08
_CROP_JPEG_QUALITY = 92


@dataclass(frozen=True)
class PersonBox:
    """Bbox em coordenadas do frame ORIGINAL: x, y, largura, altura."""

    x: int
    y: int
    w: int
    h: int
    confidence: float


@dataclass(frozen=True)
class PersonResult:
    found: bool
    boxes: tuple[PersonBox, ...] = ()
    max_confidence: float = 0.0
    #: True quando o detector não pôde opinar (não carregado / erro de
    #: inferência). O chamador usa isso pra cair no gatilho por movimento em vez
    #: de tratar como "não tem pessoa" — silenciar a coleta por falha de infra
    #: seria pior que coletar demais.
    undetermined: bool = False


@dataclass(frozen=True)
class PersonCrop:
    """O JPEG do recorte E de onde ele saiu — os dois juntos, sempre.

    Antes desta classe `crop_person` devolvia só os bytes, e o retângulo que ela
    tinha acabado de calcular (margem aplicada, borda aparada) morria na função.
    Foi assim que os 5.259 recortes anotados do RVB viraram órfãos: sem a caixa
    em coordenadas do frame original, nenhuma anotação feita no recorte volta
    pro quadro cheio — que é justamente onde o modelo é SERVIDO.

    `origin` já sai no formato de `training_frames.crop_origin` (migration 132):
    {"box": [x, y, w, h], "source_size": [W, H]}. Dict e não dataclass porque o
    único destino é um campo de form JSON no upload — converter duas vezes seria
    cerimônia sem leitor.
    """

    jpeg: bytes
    origin: dict[str, Any]


class PersonDetector:
    """Responde "tem pessoa neste JPEG?" — só isso.

    Recebe os bytes JPEG que o coletor já capturou; NÃO abre stream RTSP
    próprio (o canal 1 tem teto de 2 conexões: live view + coletor).
    """

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        confidence: float = _DEFAULT_CONFIDENCE,
        nms_iou: float = _DEFAULT_NMS_IOU,
        input_size: tuple[int, int] = _DEFAULT_INPUT_SIZE,
        tile_grid: tuple[int, int] = _DEFAULT_TILE_GRID,
    ) -> None:
        self._model_path = model_path
        self._confidence = confidence
        self._nms_iou = nms_iou
        self._input_h, self._input_w = input_size
        self._tile_nx, self._tile_ny = tile_grid
        self._session: Any = None
        self._input_name = ""
        self._np: Any = None
        self._load()

    # ── carga ────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not os.path.isfile(self._model_path):
            logger.warning(
                "person_detector_model_ausente path=%s — coleta cai no gatilho "
                "por movimento (COLLECTOR_PERSON_MODEL_PATH ajusta o caminho)",
                self._model_path,
            )
            return
        try:
            import numpy as np  # noqa: PLC0415
            import onnxruntime as ort  # noqa: PLC0415
        except ImportError as exc:
            logger.warning(
                "person_detector_dependencia_ausente err=%s — coleta cai no "
                "gatilho por movimento",
                exc,
            )
            return
        try:
            opts = ort.SessionOptions()
            opts.log_severity_level = 3  # só ERROR
            self._session = ort.InferenceSession(
                self._model_path, sess_options=opts, providers=["CPUExecutionProvider"]
            )
            self._input_name = self._session.get_inputs()[0].name
            self._np = np
        except Exception as exc:
            logger.warning(
                "person_detector_load_falhou path=%s err=%s — coleta cai no "
                "gatilho por movimento",
                self._model_path,
                exc,
            )
            self._session = None
            return
        logger.info(
            "person_detector_pronto path=%s entrada=%dx%d limiar=%.2f",
            self._model_path,
            self._input_w,
            self._input_h,
            self._confidence,
        )

    @property
    def is_ready(self) -> bool:
        return self._session is not None

    # ── inferência ───────────────────────────────────────────────────────────

    def detect(self, frame_bytes: bytes) -> PersonResult:
        if self._session is None:
            return PersonResult(found=False, undetermined=True)
        try:
            return self._detect(frame_bytes)
        except Exception as exc:
            # Falha de inferência é `undetermined`, não "sem pessoa": o
            # chamador precisa distinguir "olhei e não tem" de "não consegui
            # olhar" pra não parar de coletar por um erro transitório.
            logger.warning("person_detector_inferencia_falhou err=%s", exc)
            return PersonResult(found=False, undetermined=True)

    def _detect(self, frame_bytes: bytes) -> PersonResult:
        """Roda o modelo em cada ladrilho e une o resultado em coords do frame."""
        from PIL import Image  # noqa: PLC0415

        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
        boxes: list[PersonBox] = []
        for crop, off_x, off_y in self._tiles(img):
            boxes.extend(self._detect_one(crop, off_x, off_y))
        if not boxes:
            return PersonResult(found=False)
        # Uma pessoa na sobreposição aparece em dois ladrilhos — dedup por IoU
        # sobre as caixas já em coordenadas do frame inteiro.
        boxes = self._dedupe(boxes)
        return PersonResult(
            found=True,
            boxes=tuple(boxes),
            max_confidence=max(b.confidence for b in boxes),
        )

    def _tiles(self, img: Any) -> list[tuple[Any, int, int]]:
        """Recorta o frame em nx*ny ladrilhos sobrepostos. 1x1 = frame inteiro."""
        w, h = img.size
        if self._tile_nx <= 1 and self._tile_ny <= 1:
            return [(img, 0, 0)]
        tw = min(w, int(w / self._tile_nx * (1 + _TILE_OVERLAP)))
        th = min(h, int(h / self._tile_ny * (1 + _TILE_OVERLAP)))
        out: list[tuple[Any, int, int]] = []
        for iy in range(self._tile_ny):
            for ix in range(self._tile_nx):
                x = min(int(ix * w / self._tile_nx), w - tw)
                y = min(int(iy * h / self._tile_ny), h - th)
                out.append((img.crop((x, y, x + tw, y + th)), x, y))
        return out

    def _dedupe(self, boxes: list[PersonBox]) -> list[PersonBox]:
        np = self._np
        arr = np.array(
            [[b.x, b.y, b.x + b.w, b.y + b.h] for b in boxes], dtype=np.float32
        )
        scores = np.array([b.confidence for b in boxes], dtype=np.float32)
        return [boxes[i] for i in self._nms(arr, scores)]

    def _detect_one(self, img: Any, off_x: int, off_y: int) -> list[PersonBox]:
        np = self._np
        blob, scale = self._preprocess(img)
        raw = self._session.run(None, {self._input_name: blob})[0]
        preds = self._decode_positions(raw)[0]  # [N, 85]

        obj_conf = preds[:, 4]
        cls_conf = preds[:, 5:]
        person_conf = cls_conf[:, _PERSON_CLASS_ID]
        # Só interessa `person`: se outra classe pontua mais neste anchor, não
        # é uma pessoa — evita contar o "melhor palpite" como gente.
        best_is_person = np.argmax(cls_conf, axis=1) == _PERSON_CLASS_ID
        scores = obj_conf * person_conf

        mask = (scores >= self._confidence) & best_is_person
        if not bool(np.any(mask)):
            return []

        kept = preds[mask]
        kept_scores = scores[mask]

        cx, cy, bw, bh = kept[:, 0], kept[:, 1], kept[:, 2], kept[:, 3]
        x1 = (cx - bw / 2) / scale
        y1 = (cy - bh / 2) / scale
        x2 = (cx + bw / 2) / scale
        y2 = (cy + bh / 2) / scale
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = self._nms(boxes_xyxy, kept_scores)
        # off_x/off_y devolvem a caixa pro sistema de coordenadas do frame
        # inteiro — sem isso, a bbox de um ladrilho apontaria pro lugar errado.
        return [
            PersonBox(
                x=max(0, int(boxes_xyxy[i, 0]) + off_x),
                y=max(0, int(boxes_xyxy[i, 1]) + off_y),
                w=int(boxes_xyxy[i, 2] - boxes_xyxy[i, 0]),
                h=int(boxes_xyxy[i, 3] - boxes_xyxy[i, 1]),
                confidence=round(float(kept_scores[i]), 3),
            )
            for i in keep
        ]

    # ── pré/pós-processamento ────────────────────────────────────────────────

    def _preprocess(self, img: Any) -> tuple[Any, float]:
        """Imagem PIL → blob float32 [1,3,H,W] em 0-255, com letterbox.

        Sem divisão por 255: o YOLOX oficial NÃO normaliza a entrada (ver
        demo/ONNXRuntime/onnx_inference.py do repo upstream). Dividir aqui
        derruba a confiança silenciosamente — é o tipo de erro que aparece como
        "recall ruim" e manda calibrar limiar à toa.
        """
        from PIL import Image  # noqa: PLC0415

        np = self._np
        w, h = img.size
        scale = min(self._input_h / h, self._input_w / w)
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        resized = img.resize((new_w, new_h), Image.BILINEAR)

        padded = np.full((self._input_h, self._input_w, 3), 114, dtype=np.float32)
        padded[:new_h, :new_w] = np.asarray(resized, dtype=np.float32)

        blob = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)
        return blob[np.newaxis], scale

    def _decode_positions(self, raw: Any) -> Any:
        """Aplica offset de grid e stride — o modelo exporta cx/cy/w/h crus."""
        np = self._np
        grids, strides = [], []
        for stride in _STRIDES:
            hs, ws = self._input_h // stride, self._input_w // stride
            xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
            grids.append(np.stack([xv, yv], axis=2).reshape(1, -1, 2))
            strides.append(np.full((1, hs * ws, 1), stride, dtype=np.float32))
        all_grids = np.concatenate(grids, axis=1)
        all_strides = np.concatenate(strides, axis=1)

        out = raw.copy()
        out[..., :2] = (out[..., :2] + all_grids) * all_strides
        out[..., 2:4] = np.exp(np.clip(out[..., 2:4], -10, 10)) * all_strides
        return out

    def _nms(self, boxes_xyxy: Any, scores: Any) -> list[int]:
        np = self._np
        if len(boxes_xyxy) == 0:
            return []
        x1, y1, x2, y2 = (
            boxes_xyxy[:, 0],
            boxes_xyxy[:, 1],
            boxes_xyxy[:, 2],
            boxes_xyxy[:, 3],
        )
        areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            union = areas[i] + areas[order[1:]] - inter
            iou = np.where(union > 0, inter / union, 0.0)
            order = order[1:][iou <= self._nms_iou]
        return keep


def crop_person(
    frame_bytes: bytes,
    box: PersonBox,
    margin_x: float = _CROP_MARGIN_X,
    margin_y: float = _CROP_MARGIN_Y,
    quality: int = _CROP_JPEG_QUALITY,
) -> PersonCrop:
    """Recorta a pessoa em resolução NATIVA e devolve o JPEG **com a origem**.

    É o desfecho C da medição de resolução (fase 1b). Medido num frame real da
    RVB, pessoa de 54x282px em 1920x1080:

        frame inteiro do substream 704x480 .... 157 KB, cabeça ~17px
        frame inteiro do principal 1920x1080 .. 789 KB, cabeça ~40px
        RECORTE da pessoa, 1080p nativo .......  10 KB, cabeça ~40px

    16x menor que o que já subíamos, com 2,4x mais pixel na cabeça — melhor nos
    dois eixos, não é troca. A margem existe porque o alvo desta câmera é EPI de
    CABEÇA (protetor auricular, óculos): um bbox justo demais corta exatamente o
    que se quer anotar.

    O retângulo devolvido em `.origin` é o EFETIVAMENTE recortado — margem já
    somada, borda já aparada — porque é ele, e não a bbox da pessoa, que define
    o sistema de coordenadas em que o anotador vai desenhar. Este é o único
    lugar do sistema que sabe as duas coisas ao mesmo tempo (o retângulo e o
    tamanho do frame original); recalcular isso no chamador exigiria decodificar
    o JPEG de novo e duplicar o aparo de borda — dois lugares para a mesma
    regra, que é como se produz o segundo bug.
    """
    from PIL import Image  # noqa: PLC0415

    img = Image.open(io.BytesIO(frame_bytes))
    mx = int(box.w * margin_x)
    my = int(box.h * margin_y)
    x1 = max(0, box.x - mx)
    y1 = max(0, box.y - my)
    x2 = min(img.width, box.x + box.w + mx)
    y2 = min(img.height, box.y + box.h + my)
    buf = io.BytesIO()
    img.crop((x1, y1, x2, y2)).convert("RGB").save(buf, format="JPEG", quality=quality)
    return PersonCrop(
        jpeg=buf.getvalue(),
        origin={
            "box": [x1, y1, x2 - x1, y2 - y1],
            "source_size": [img.width, img.height],
        },
    )


def build_person_detector_from_env(
    env: dict[str, str] | None = None,
) -> PersonDetector | None:
    """Constrói o detector a partir do ambiente.

    Retorna None quando COLLECTOR_PERSON_TRIGGER está explicitamente desligado
    — aí o coletor usa o gatilho por movimento, como antes desta mudança.
    """
    source = env if env is not None else os.environ
    if (source.get("COLLECTOR_PERSON_TRIGGER", "1").strip().lower()
            in ("0", "false", "no", "off")):
        logger.info("person_detector_desligado por COLLECTOR_PERSON_TRIGGER")
        return None
    return PersonDetector(
        model_path=source.get("COLLECTOR_PERSON_MODEL_PATH", _DEFAULT_MODEL_PATH),
        confidence=float(
            source.get("COLLECTOR_PERSON_CONFIDENCE", str(_DEFAULT_CONFIDENCE))
        ),
        nms_iou=float(source.get("COLLECTOR_PERSON_NMS_IOU", str(_DEFAULT_NMS_IOU))),
        tile_grid=_parse_tile_grid(source.get("COLLECTOR_PERSON_TILES", "")),
    )


def _parse_tile_grid(raw: str) -> tuple[int, int]:
    """"2x2" -> (2, 2). Vazio/inválido cai no padrão medido em campo.

    1x1 é REJEITADO desde a fase 1c. Com a captura em 1920x1080 (desfecho C),
    o quadro inteiro reduzido a 416 transforma uma pessoa de 54px de largura em
    12px e o detector simplesmente não a encontra — medido no Orin: 1x1 -> não
    achou; 2x2 -> achou. Aceitar 1x1 aqui seria oferecer uma config que desliga
    a coleta em silêncio.
    """
    if not raw.strip():
        return _DEFAULT_TILE_GRID
    try:
        nx, ny = (int(p) for p in raw.lower().split("x", 1))
        if nx < 1 or ny < 1:
            raise ValueError
    except ValueError:
        logger.warning(
            "COLLECTOR_PERSON_TILES inválido (%r) — usando %dx%d",
            raw, *_DEFAULT_TILE_GRID,
        )
        return _DEFAULT_TILE_GRID
    if (nx, ny) == (1, 1):
        logger.warning(
            "COLLECTOR_PERSON_TILES=1x1 não é suportado com captura em 1080p "
            "(a pessoa vira ~12px na entrada do modelo e não é detectada) — "
            "usando %dx%d",
            *_DEFAULT_TILE_GRID,
        )
        return _DEFAULT_TILE_GRID
    return nx, ny
