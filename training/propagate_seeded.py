#!/usr/bin/env python3
"""
Recognition — propagate_seeded.py (runner SELF-CONTAINED da instância RunPod).

Roda NA GPU remota — ZERO imports do repositório (embutido no onstart via
heredoc por `app/infrastructure/queue/tasks/propagation.py::
_read_propagate_executor_source`, mesmo padrão de
`training/vast/remote_train.py`). Só stdlib no import-time; DINOv2
(arquitetura via torch.hub, pesos verificados à parte) + SAM
(segment-anything) + opencv/numpy são instalados via pip EM RUNTIME no pod
— NUNCA ultralytics (AGPL, fora do caminho servido e fora do caminho de
treino, ADR-0043/task "treino não pode mentir"; `scripts/check_license_gate.py`
varre este diretório por import).

Pipeline v1 — poucas sementes (caixas humanas), muito pool (sem anotação):
  1. baixa o manifesto (MANIFEST_URL, presigned GET) — sementes (frame +
     imagem + caixas humanas com classe) e pool (frame + imagem, sem
     anotação);
  2. baixa e VERIFICA sha256 dos DOIS pesos de terceiro contra o hash
     esperado (manifesto/env) ANTES de carregar qualquer um — SAM ViT-B
     vem do nosso R2 (já pinado em docs/WEIGHTS_LICENSES.md desde o PR
     #340); DINOv2 vem da URL oficial da Meta (dl.fbaipublicfiles.com).
     Hash ausente ou divergente => aborta (WeightVerificationError,
     fail-closed) — nunca "confia e carrega";
  3. recorta cada semente pela caixa humana, embeda com DINOv2 → um ou mais
     exemplares por classe (média das similaridades contra TODOS os
     exemplares da classe, não só o par mais próximo — mais robusto a um
     exemplar ruidoso isolado);
  4. por frame do pool: gera candidatos de caixa via SAM automatic mask
     generation (justificativa em `load_sam_mask_generator`), embeda cada
     candidato com DINOv2, similaridade de cosseno contra os exemplares de
     cada classe → melhor classe acima do threshold vira proposta
     {bbox normalizado, class, confidence};
  5. progresso via callback a cada PROGRESS_EVERY_N frames; resultado final
     (as propostas em si — JSON pequeno) via callback — sem upload pro R2
     (a "verificação de artefato" do fluxo de treino não se aplica aqui: o
     próprio payload do callback final É o resultado, validado pelo
     backend em `propagation_handlers.py::propagation_callback_handler`
     antes de gravar em `training_frames.pre_annotations`).

Contrato (tudo via env, injetado pelo dispatch —
`app/infrastructure/queue/tasks/propagation.py::dispatch_propagation`):
  MANIFEST_URL           presigned GET do manifesto JSON (sementes+pool)
  CALLBACK_URL            POST .../propagation/jobs/<id>/callback
  CALLBACK_TOKEN           header X-Callback-Token (token por-job, revogável)
  SAM_WEIGHTS_URL          presigned GET (nosso R2 — sam_vit_b_01ec64.pth)
  SAM_WEIGHTS_SHA256        esperado (docs/WEIGHTS_LICENSES.md)
  DINOV2_WEIGHTS_URL        URL oficial dl.fbaipublicfiles.com (Meta)
  DINOV2_WEIGHTS_SHA256      esperado (docs/WEIGHTS_LICENSES.md)
  SIMILARITY_THRESHOLD      float, default 0.65
  PROGRESS_EVERY_N           int, default 20
  MAX_RESULTS                int, opcional — cap de quantos FRAMES do pool
                             (não propostas individuais) entram no
                             resultado final, ranqueados pela maior
                             `confidence` entre suas propostas; ausente/<=0
                             = sem cap (ver `cap_proposals_to_top_frames`)

Em erro (manifesto ausente/vazio, sha256 de peso divergente, sem sementes,
sem pool, etc.): POST {status:'failed', error_message} e exit 1 — nunca
'completed' sem propostas verificáveis pelo backend.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("propagate_seeded")

MANIFEST_URL = os.environ.get("MANIFEST_URL", "")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN", "")
SAM_WEIGHTS_URL = os.environ.get("SAM_WEIGHTS_URL", "")
SAM_WEIGHTS_SHA256 = os.environ.get("SAM_WEIGHTS_SHA256", "")
DINOV2_WEIGHTS_URL = os.environ.get("DINOV2_WEIGHTS_URL", "")
DINOV2_WEIGHTS_SHA256 = os.environ.get("DINOV2_WEIGHTS_SHA256", "")
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.65"))
PROGRESS_EVERY_N = int(os.environ.get("PROGRESS_EVERY_N", "20"))
_MAX_RESULTS_RAW = os.environ.get("MAX_RESULTS", "")
MAX_RESULTS = int(_MAX_RESULTS_RAW) if _MAX_RESULTS_RAW else 0

# /root é o default do pod RunPod (container, roda como root). No box EDGE
# (systemd --user, usuário sem root) /root NÃO é gravável — o lançador
# injeta WORK_DIR apontando pra um diretório próprio do job.
WORK_DIR = Path(os.environ.get("WORK_DIR", "/root"))


# --------------------------------------------------------------------- http

def post_callback(payload: dict) -> None:
    """POSTa progresso/resultado no backend. Best-effort — o job não morre
    por causa de rede (mesmo padrão de remote_train.py)."""
    if not CALLBACK_URL:
        return
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310
            CALLBACK_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Callback-Token": CALLBACK_TOKEN,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("callback_failed: %s", exc)


def download(url: str, dest: Path, timeout: int = 600) -> None:
    logger.info("download: %s -> %s", url.split("?")[0], dest)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        dest.write_bytes(resp.read())


def download_json(url: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def download_bytes(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def pip_install(*packages: str) -> None:
    logger.info("pip install %s", " ".join(packages))
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "-q", *packages],
        check=True,
        text=True,
    )


# módulo importável -> nome do pacote pip. A instalação é POR FALTA
# (`ensure_dependencies`), nunca incondicional: no pod RunPod (imagem nua)
# instala tudo; no box EDGE (venv preparado com torch jp6/cu126 pinado)
# instala NADA — um `pip install torch` no Jetson puxaria a wheel SBSA
# genérica por cima da wheel jp6 e QUEBRARIA a iGPU inteira
# (docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.1/§3.5 — landmine já paga 2x).
_REQUIRED_MODULES: dict[str, str] = {
    "torch": "torch",
    "torchvision": "torchvision",
    "cv2": "opencv-python-headless",
    "numpy": "numpy",
    "segment_anything": "segment-anything",
}


def ensure_dependencies() -> None:
    """Instala via pip SOMENTE os módulos ausentes (`find_spec` — não
    carrega nada, só resolve se o módulo existe no ambiente)."""
    import importlib.util  # noqa: PLC0415

    missing = [
        package
        for module, package in _REQUIRED_MODULES.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        pip_install(*missing)
    else:
        logger.info("deps já presentes no ambiente — pip install pulado")


def humanize_startup_error(exc: Exception) -> "str | None":
    """Tradução LEGÍVEL dos erros de plataforma que o operador não tem como
    decifrar de um traceback — retorna None quando não há tradução (o
    caller usa str(exc) cru como antes).

    Caso real (box Jetson): torch 2.11 jp6/cu126 exige LD_LIBRARY_PATH
    apontando pro nvidia/cu12/lib do venv ANTES do `import torch`, senão
    `ImportError: libcudss.so.0: cannot open shared object file`. Quebra em
    silêncio meses depois (upgrade de JetPack, venv movido) — a mensagem
    precisa dizer O QUE procurar e ONDE, não um traceback
    (docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.5).
    """
    text = str(exc)
    if isinstance(exc, (ImportError, OSError)) and "cannot open shared object" in text:
        lib = text.split(":", 1)[0].strip()
        searched = os.environ.get("LD_LIBRARY_PATH", "") or "(vazio)"
        return (
            "não foi possível carregar o modelo no equipamento da fábrica — "
            f"biblioteca CUDA não encontrada ({lib}). Caminhos de busca "
            f"(LD_LIBRARY_PATH): {searched}. Ver docs/edge/"
            "REGRAS_PLATAFORMA_JETSON.md §3.5 (landmine libcudss)."
        )
    return None


# --------------------------------------------------------- weight integrity

class WeightVerificationError(RuntimeError):
    """Peso baixado não bate com o sha256 esperado, ou hash esperado
    ausente — aborta ANTES de carregar. Nunca "confia e carrega"."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_verify_weight(
    url: str, expected_sha256: str, dest: Path, label: str
) -> Path:
    """Baixa um peso de terceiro e verifica sha256 contra o esperado —
    guard de integridade fail-closed (⛔ mismatch/ausência = aborta).

    Aplica-se aos DOIS pesos deste executor: SAM ViT-B (nosso R2) e DINOv2
    (URL oficial da Meta) — nenhum dos dois é carregado sem essa checagem
    passar primeiro. Sem `expected_sha256` (env/manifesto não preencheu),
    o executor recusa seguir — ver docs/WEIGHTS_LICENSES.md pro processo de
    pinagem de um peso novo.
    """
    if not url:
        raise WeightVerificationError(f"{label}: URL de download ausente")
    if not expected_sha256:
        raise WeightVerificationError(
            f"{label}: sha256 esperado ausente no manifesto/env — executor "
            "recusa carregar peso sem hash pra conferir (fail-closed, ver "
            "docs/WEIGHTS_LICENSES.md — primeiro uso validado deve preencher)"
        )
    download(url, dest)
    actual = sha256_of(dest)
    if actual.lower() != expected_sha256.strip().lower():
        raise WeightVerificationError(
            f"{label}: sha256 divergente (esperado={expected_sha256!r} "
            f"obtido={actual!r}) — peso NÃO carregado"
        )
    logger.info("weight_verified: %s sha256=%s", label, actual)
    return dest


# ------------------------------------------------------------- pure matching
#
# Tudo abaixo desta seção (até "GPU pipeline") é PURO — só stdlib (math),
# sem numpy/torch/cv2 — de propósito: testável em CI sem instalar nenhuma
# dependência de ML (ver training/test_propagate_seeded.py). O caminho GPU
# real (embed_crop, load_dinov2, load_sam_mask_generator, build_pool_
# proposals) importa torch/cv2/segment_anything só dentro das próprias
# funções (lazy import — mesmo padrão de remote_train.py::train_rfdetr),
# nunca no top-level do módulo.

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno pura Python (sem numpy) — vetores de
    tamanhos diferentes ou nulos retornam 0.0 (nunca levanta)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def best_class_for_embedding(
    embedding: list[float],
    class_exemplars: dict[str, list[list[float]]],
    threshold: float,
) -> tuple[str | None, float]:
    """Classe cujo conjunto de exemplares tem a MAIOR similaridade MÉDIA
    com `embedding` — média (não só o par mais próximo) é mais robusto a
    um exemplar-semente ruidoso isolado. Retorna (None, melhor_score) se
    nenhuma classe cruza `threshold` (candidato descartado, não vira
    proposta de classe nenhuma — sem fallback pra "classe mais provável
    mesmo que fraca", ADR-0017 aplicado aqui também)."""
    best_class: str | None = None
    best_score = 0.0
    for class_name, exemplars in class_exemplars.items():
        if not exemplars:
            continue
        scores = [cosine_similarity(embedding, ex) for ex in exemplars]
        avg_score = sum(scores) / len(scores)
        if avg_score > best_score:
            best_score = avg_score
            best_class = class_name
    if best_class is None or best_score < threshold:
        return None, best_score
    return best_class, best_score


def mask_bbox_to_normalized(
    bbox_xywh: tuple[float, float, float, float], img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Converte bbox absoluto (x, y, w, h — canto superior esquerdo, formato
    de saída do SAM) para (cx, cy, w, h) normalizado [0,1] — formato
    consumido por `pre_annotations`/`build_proposal`. A caixa usada AQUI já
    é a própria máscara do SAM (candidato bem ajustado ao objeto) — não há
    passo de "refino" separado: usar a caixa da máscara SAM como proposta
    final É o refino (mais justo que uma grade fixa, sem custo extra de
    outra passada pelo SAM)."""
    x, y, w, h = bbox_xywh
    if img_w <= 0 or img_h <= 0:
        raise ValueError("dimensões de imagem inválidas (img_w/img_h <= 0)")
    cx = (x + w / 2.0) / img_w
    cy = (y + h / 2.0) / img_h
    nw = w / img_w
    nh = h / img_h
    return (
        max(0.0, min(1.0, cx)),
        max(0.0, min(1.0, cy)),
        max(0.01, min(1.0, nw)),
        max(0.01, min(1.0, nh)),
    )


def denormalize_bbox(
    bbox_cxcywh: tuple[float, float, float, float], img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    """Inverso de `mask_bbox_to_normalized` — usado pra recortar a SEMENTE
    (bbox normalizado humano, formato AnnotationInterface) em pixels antes
    de embedar com DINOv2. Retorna (x0, y0, x1, y1), sempre x1>x0, y1>y0."""
    cx, cy, w, h = bbox_cxcywh
    box_w = w * img_w
    box_h = h * img_h
    x = cx * img_w - box_w / 2.0
    y = cy * img_h - box_h / 2.0
    x0 = max(0, int(round(x)))
    y0 = max(0, int(round(y)))
    x1 = min(img_w, int(round(x + box_w)))
    y1 = min(img_h, int(round(y + box_h)))
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def build_proposal(
    class_name: str, confidence: float, bbox_cxcywh: tuple[float, float, float, float]
) -> dict[str, Any]:
    """Shape EXATO consumido por `AnnotationService.get_frame_annotations`
    (fallback pre_annotations) e pela fila de aprovação (migration 111):
    `{"bbox": [cx, cy, w, h], "class": <label>, "confidence": <float>}`.
    `class_name` precisa bater (case-insensitive) com uma classe já
    conhecida do tenant — o dispatch usa o `class_name` LITERAL da
    semente, nunca inventa um label novo."""
    cx, cy, w, h = bbox_cxcywh
    return {
        "bbox": [round(cx, 6), round(cy, 6), round(w, 6), round(h, 6)],
        "class": class_name,
        "confidence": round(float(confidence), 4),
    }


def cap_proposals_to_top_frames(
    proposals: dict[str, list[dict[str, Any]]], max_results: int
) -> dict[str, list[dict[str, Any]]]:
    """Mantém só os top-N FRAMES (nunca trunca a lista de propostas DENTRO
    de um frame mantido) ranqueados pela MAIOR `confidence` entre suas
    propostas — frames excedentes são descartados INTEIROS. `max_results`
    ausente/<=0, ou >= total de frames com proposta: sem cap, `proposals`
    retornado inalterado (mesmo objeto — nunca copiado à toa).

    Frame sem nenhuma proposta (lista vazia) tem score -1.0 — sempre no
    fim do ranking (perde pra qualquer frame com proposta real), mas ainda
    pode sobreviver ao corte se sobrar espaço. Empate de score: desempate
    determinístico por `frame_id` em ordem lexicográfica — nunca depende
    da ordem de iteração do dict (`dict` em Python preserva ordem de
    inserção, mas essa ordem vem da iteração do pool, não é um critério de
    ranking válido por si só)."""
    if max_results <= 0 or len(proposals) <= max_results:
        return proposals

    def _best_confidence(frame_id: str) -> float:
        items = proposals[frame_id]
        if not items:
            return -1.0
        return max(float(item.get("confidence", 0.0)) for item in items)

    ranked = sorted(proposals.keys(), key=lambda fid: (-_best_confidence(fid), fid))
    kept = ranked[:max_results]
    return {frame_id: proposals[frame_id] for frame_id in kept}


# --------------------------------------------------------------- GPU pipeline

def download_image(url: str):
    """Baixa e decodifica uma imagem (BGR, formato OpenCV) — lazy import."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    data = download_bytes(url)
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"falha ao decodificar imagem: {url.split('?')[0]}")
    return image


def load_dinov2(weights_path: Path):
    """Arquitetura DINOv2 ViT-S/14 via torch.hub (`pretrained=False` —
    baixa só o CÓDIGO do repositório, NUNCA o checkpoint default embutido
    no hub); os pesos usados são SEMPRE o arquivo já baixado+verificado por
    `download_and_verify_weight` — é assim que o sha256 pinado em
    docs/WEIGHTS_LICENSES.md fica sendo o que roda de fato, não um
    checkpoint resolvido às cegas pelo hub."""
    import torch  # noqa: PLC0415

    model = torch.hub.load(  # noqa: S614 — repo oficial Meta, pretrained=False (ver docstring)
        "facebookresearch/dinov2", "dinov2_vits14", pretrained=False
    )
    state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return model, device


def embed_crop(model, device, image, box_xyxy: tuple[int, int, int, int]) -> list[float]:
    """Recorta `image` (BGR) pela caixa, redimensiona pro padrão DINOv2
    (224x224, múltiplo de 14) e embeda — retorna o vetor CLS como lista de
    floats (formato que as funções puras de matching consomem). Caixa
    degenerada (crop vazio) retorna [] — caller descarta o candidato."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415

    x0, y0, x1, y1 = box_xyxy
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return []
    crop = cv2.resize(crop, (224, 224))
    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_rgb = (crop_rgb - mean) / std
    tensor = (
        torch.from_numpy(crop_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
    )
    with torch.no_grad():
        features = model(tensor)
    return features.squeeze(0).cpu().tolist()


def load_sam_mask_generator(weights_path: Path, device: str):
    """SAM AutomaticMaskGenerator — candidatos de caixa por frame do pool.

    Escolha (vs. grade fixa de propostas): uma grade de janelas fixas
    exigiria escolher escala/aspect-ratio a priori (EPI em CFTV varia MUITO
    de tamanho — capacete de perto vs. bota longe) e geraria dezenas de
    candidatos redundantes por frame, a maioria sem objeto nenhum dentro.
    O AMG do SAM propõe máscaras já ajustadas a bordas reais da cena
    (pessoa, objeto, sombra) — menos candidatos, mais próximos do objeto
    real, sem precisar calibrar escala manualmente. `points_per_side=12`
    (default do SAM é 32): reduz o número de máscaras candidatas ~7x sem
    perder recall pra objetos de porte médio/grande (EPI em corpo inteiro),
    aceitável pro v1 (throughput > recall exaustivo — thresholds de
    similaridade DINOv2 já filtram o que não bate com nenhuma semente).
    """
    from segment_anything import SamAutomaticMaskGenerator, sam_model_registry  # noqa: PLC0415,E501

    sam = sam_model_registry["vit_b"](checkpoint=str(weights_path))
    sam.to(device)
    return SamAutomaticMaskGenerator(
        sam,
        points_per_side=12,
        pred_iou_thresh=0.86,
        stability_score_thresh=0.9,
        min_mask_region_area=400,
    )


def build_seed_exemplars(
    dinov2_model, device, seeds: list[dict]
) -> dict[str, list[list[float]]]:
    """Recorta cada caixa-semente humana e embeda com DINOv2 — um exemplar
    por caixa, agrupado por classe (`class_exemplars[class_name]`)."""
    exemplars: dict[str, list[list[float]]] = {}
    for seed in seeds:
        image = download_image(seed["image_url"])
        img_h, img_w = image.shape[:2]
        for box in seed.get("boxes") or []:
            class_name = str(box.get("class") or "").strip()
            if not class_name:
                continue
            raw_bbox = box.get("bbox") or [0.5, 0.5, 0.1, 0.1]
            bbox = (
                float(raw_bbox[0]), float(raw_bbox[1]),
                float(raw_bbox[2]), float(raw_bbox[3]),
            )
            box_xyxy = denormalize_bbox(bbox, img_w, img_h)
            embedding = embed_crop(dinov2_model, device, image, box_xyxy)
            if embedding:
                exemplars.setdefault(class_name, []).append(embedding)
    return exemplars


def build_pool_proposals(
    mask_generator,
    dinov2_model,
    device,
    image,
    class_exemplars: dict[str, list[list[float]]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Gera propostas para UM frame do pool: candidatos SAM → embedding
    DINOv2 → melhor classe acima do threshold vira proposta."""
    import cv2  # noqa: PLC0415

    img_h, img_w = image.shape[:2]
    masks = mask_generator.generate(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    proposals: list[dict[str, Any]] = []
    for mask in masks:
        x, y, w, h = mask["bbox"]  # SAM: xywh absoluto, canto superior esquerdo
        if w <= 1 or h <= 1:
            continue
        box_xyxy = (int(x), int(y), int(x + w), int(y + h))
        embedding = embed_crop(dinov2_model, device, image, box_xyxy)
        if not embedding:
            continue
        class_name, confidence = best_class_for_embedding(
            embedding, class_exemplars, threshold
        )
        if class_name is None:
            continue
        bbox_norm = mask_bbox_to_normalized((x, y, w, h), img_w, img_h)
        proposals.append(build_proposal(class_name, confidence, bbox_norm))
    return proposals


# --------------------------------------------------------------------- main

def main() -> int:
    post_callback({"status": "running", "progress": 1, "metrics": {"stage": "manifest"}})
    if not MANIFEST_URL:
        raise RuntimeError("MANIFEST_URL não definido")
    manifest = download_json(MANIFEST_URL)
    seeds = manifest.get("seeds") or []
    pool = manifest.get("pool") or []
    if not seeds:
        raise RuntimeError("manifesto sem sementes — nada pra propagar")
    if not pool:
        raise RuntimeError("manifesto sem pool — nada pra processar")

    post_callback({"status": "running", "progress": 3, "metrics": {"stage": "deps"}})
    ensure_dependencies()

    post_callback({"status": "running", "progress": 5, "metrics": {"stage": "weights"}})
    sam_path = download_and_verify_weight(
        SAM_WEIGHTS_URL, SAM_WEIGHTS_SHA256, WORK_DIR / "sam_vit_b.pth", "SAM ViT-B",
    )
    dinov2_path = download_and_verify_weight(
        DINOV2_WEIGHTS_URL, DINOV2_WEIGHTS_SHA256, WORK_DIR / "dinov2_vits14.pth",
        "DINOv2 ViT-S/14",
    )

    dinov2_model, device = load_dinov2(dinov2_path)
    mask_generator = load_sam_mask_generator(sam_path, device)

    post_callback({
        "status": "running", "progress": 10,
        "metrics": {"stage": "seed_exemplars", "seed_count": len(seeds)},
    })
    class_exemplars = build_seed_exemplars(dinov2_model, device, seeds)
    if not class_exemplars:
        raise RuntimeError(
            "nenhum exemplar extraído das sementes — caixas humanas inválidas?"
        )

    all_proposals: dict[str, list[dict[str, Any]]] = {}
    total = len(pool)
    for i, item in enumerate(pool, start=1):
        frame_id = str(item["frame_id"])
        try:
            image = download_image(item["image_url"])
            proposals = build_pool_proposals(
                mask_generator, dinov2_model, device, image,
                class_exemplars, SIMILARITY_THRESHOLD,
            )
        except Exception as exc:  # noqa: BLE001 — um frame ruim não derruba o job inteiro
            logger.warning("frame_failed: frame=%s err=%s", frame_id, exc)
            proposals = []
        all_proposals[frame_id] = proposals

        if i % PROGRESS_EVERY_N == 0 or i == total:
            progress = min(95, 10 + int(85 * i / max(total, 1)))
            post_callback({
                "status": "running",
                "progress": progress,
                "metrics": {
                    "stage": "pool",
                    "frames_processed": i,
                    "frames_total": total,
                    "proposals_so_far": sum(len(v) for v in all_proposals.values()),
                },
            })

    final_proposals = (
        cap_proposals_to_top_frames(all_proposals, MAX_RESULTS)
        if MAX_RESULTS > 0
        else all_proposals
    )
    proposals_count = sum(len(v) for v in final_proposals.values())
    post_callback({
        "status": "completed",
        "progress": 100,
        "proposals": final_proposals,
        "metrics": {
            "stage": "done",
            "frames_total": total,
            "frames_analyzed": total,
            "frames_proposed": len(final_proposals),
            "proposals_count": proposals_count,
            "classes_seeded": sorted(class_exemplars.keys()),
        },
    })
    logger.info(
        "propagate_seeded_completed: frames=%d proposals=%d", total, proposals_count,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — reporta QUALQUER falha ao backend
        logger.exception("propagate_seeded_failed")
        readable = humanize_startup_error(exc)
        post_callback({
            "status": "failed",
            "error_message": (readable or str(exc))[:500],
        })
        sys.exit(1)
