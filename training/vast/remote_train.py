#!/usr/bin/env python3
"""
Recognition — remote_train.py (runner SELF-CONTAINED da instância Vast.ai).

Roda NA GPU remota — ZERO imports do repositório (é embutido no onstart via
heredoc por tasks/training.py::_build_vast_onstart). Só stdlib + frameworks
instalados via pip em runtime (RF-DETR/YOLOX — Apache 2.0; onnxruntime — MIT).

Contrato (tudo via env, injetado pelo dispatch):
  DATASET_URL          presigned GET do zip COCO da dataset_version
  INIT_WEIGHTS_URL     presigned GET de um .pth NOSSO (fine-tune rfdetr);
                       ausente = treina do pretrain padrão (RFDETRBase())
  FRAMEWORK            rfdetr | yolox (default rfdetr)
  EPOCHS               int (default 50)
  BATCH                int (default 4)
  IMGSZ                int (default 560 — múltiplo de 56, padrão RF-DETR)
  CALLBACK_URL         POST /api/v1/training/jobs/<id>/progress-callback
  CALLBACK_TOKEN       header X-Callback-Token (token por-job, revogável)
  UPLOAD_URL_ONNX      presigned PUT do model.onnx
  UPLOAD_URL_WEIGHTS   presigned PUT dos pesos (.pth)
  UPLOAD_URL_METRICS   presigned PUT do metrics.json
  R2_ONNX_KEY          chave R2 final do ONNX (ecoada no callback final)

Fluxo:
  1. baixa e extrai o dataset COCO (train/valid[/test] + _annotations.coco.json)
  2. pip install do framework (runbook TRAINING_PIPELINE_WEEKEND_MVP.md)
  3. treina; POSTa progresso {progress, epoch, metrics} a cada época
  4. reconstrói o modelo do checkpoint BEST, exporta ONNX na resolução de
     treino, confere head/pesos/input, e valida com onnxruntime
  5. sobe artefatos via PUT presigned
  6. POST final {status, progress, metrics, r2_onnx_key}
Em erro: POST {status: 'failed', error_message} e exit 1.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import atexit
import threading
import time
import zipfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("remote_train")

DATASET_URL = os.environ.get("DATASET_URL", "")
INIT_WEIGHTS_URL = os.environ.get("INIT_WEIGHTS_URL", "")
FRAMEWORK = os.environ.get("FRAMEWORK", "rfdetr").strip().lower()
EPOCHS = int(os.environ.get("EPOCHS", "50"))
# Teto de épocas e paciência do early-stop andam juntos: EPOCHS é TETO, não
# alvo — quem decide o fim é a validação parando de melhorar (`PATIENCE`), e o
# artefato entregue é o `checkpoint_best_total`, nunca o último. Subir EPOCHS
# sem subir PATIENCE só gasta GPU; subir PATIENCE sem subir o timeout do pod
# repete o job 5894a860, morto no relógio na época 16 de 50.
PATIENCE = int(os.environ.get("EARLY_STOPPING_PATIENCE", "15"))
BATCH = int(os.environ.get("BATCH", "4"))
# Desliga a adaptação do batch à placa. Ligue em EXPERIMENTO (braços de um A/B
# precisam do mesmo caminho de acumulação); deixe desligado em PRODUÇÃO, onde
# aproveitar a placa que veio é o certo. Ver `_cap_de_batch`.
BATCH_FIXO = os.environ.get("BATCH_FIXO", "").strip().lower() in ("1", "true", "sim")
IMGSZ = int(os.environ.get("IMGSZ", "560"))
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN", "")
UPLOAD_URL_ONNX = os.environ.get("UPLOAD_URL_ONNX", "")
UPLOAD_URL_WEIGHTS = os.environ.get("UPLOAD_URL_WEIGHTS", "")
UPLOAD_URL_METRICS = os.environ.get("UPLOAD_URL_METRICS", "")
R2_ONNX_KEY = os.environ.get("R2_ONNX_KEY", "")
UPLOAD_URL_LOG = os.environ.get("UPLOAD_URL_LOG", "")

WORK_DIR = Path("/root")
DATASET_DIR = WORK_DIR / "dataset_coco"
OUTPUT_DIR = WORK_DIR / "train_output"

_METRIC_KEYS = (
    "map", "map50", "mAP50", "mAP50-95", "loss", "precision", "recall",
    "test_map", "val_map", "class_map",
)


# --------------------------------------------------------------------- http

def post_callback(payload: dict) -> None:
    """POSTa progresso no backend. Best-effort — treino não morre por rede."""
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
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("callback_failed: %s", exc)


def http_put(url: str, path: Path, content_type: str) -> None:
    """Sobe artefato via presigned PUT (streaming em memória — arquivos <1GB)."""
    data = path.read_bytes()
    req = urllib.request.Request(  # noqa: S310
        url, data=data, headers={"Content-Type": content_type}, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
        resp.read()
    logger.info("uploaded: %s (%d bytes)", path.name, len(data))


def download(url: str, dest: Path, *, expect_zip: bool = False) -> None:
    """Baixa e CONFERE o que veio.

    Sem conferência, um 404 do R2 (que responde XML) era gravado como se fosse
    o dataset, e o erro só aparecia páginas depois como "Could not find class
    names" — mensagem que aponta para o lugar errado. Quatro pods morreram na
    época 0 antes de alguém olhar os bytes.
    """
    logger.info("download: %s → %s", url.split("?")[0], dest)
    with urllib.request.urlopen(url, timeout=600) as resp:  # noqa: S310
        status = getattr(resp, "status", 200)
        if status >= 400:
            raise RuntimeError(f"download falhou: HTTP {status} em {url.split('?')[0]}")
        body = resp.read()

    if not body:
        raise RuntimeError(f"download vazio (0 bytes): {url.split('?')[0]}")

    if expect_zip and body[:2] != b"PK":
        # Diz O QUE veio, não só que deu errado.
        amostra = body[:200].decode("utf-8", "replace")
        raise RuntimeError(
            f"esperava um zip e vieram {len(body)} bytes começando com "
            f"{body[:8]!r} — provável resposta de erro do storage. "
            f"Início: {amostra}"
        )

    dest.write_bytes(body)


def pip_install(*packages: str) -> None:
    logger.info("pip install %s", " ".join(packages))
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "-q", *packages],
        check=True,
        text=True,
    )


# ------------------------------------------------------------------ dataset

def prepare_dataset() -> Path:
    """Baixa o zip COCO presigned e extrai para /root/dataset_coco."""
    if not DATASET_URL:
        raise RuntimeError("DATASET_URL não definido")
    archive = WORK_DIR / "dataset.zip"
    download(DATASET_URL, archive, expect_zip=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        nomes = zf.namelist()
        if not nomes:
            raise RuntimeError(
                f"dataset.zip sem nenhuma entrada ({archive.stat().st_size} bytes) "
                "— o backend empacotou de um prefixo vazio"
            )
        if not any(n.endswith("train/_annotations.coco.json") for n in nomes):
            pastas = sorted({n.split("/")[0] for n in nomes if "/" in n})
            raise RuntimeError(
                "dataset.zip sem train/_annotations.coco.json — o treino não "
                f"tem como achar as classes. Pastas no zip: {pastas}"
            )
        zf.extractall(DATASET_DIR)  # noqa: S202 — zip gerado pelo próprio backend

    # Se o zip tem um único diretório raiz, usar ele como dataset_dir
    entries = [p for p in DATASET_DIR.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return DATASET_DIR


# O RF-DETR 1.5.2 NÃO entrega mAP no dict de `on_fit_epoch_end` — ele IMPRIME.
# Por isso `_collect_metrics` sempre devolveu {} de métrica, o callback gravou
# vazio, e `trained_models` nasceu com map50=0/precision=0/recall=0. Não é um
# job azarado: NENHUM modelo deste sistema jamais gravou métrica, e o ranking
# campeão×desafiante vinha comparando zeros com zeros. Confirmado no job
# 04508616, que custou US$ 1,71 e cujo mAP 0,4386 só existia no pod.log.
#
# Os padrões abaixo são os do log REAL (lidos, não presumidos):
#   ' Average Precision  (AP) @[ IoU=0.50:0.95 | area=   all | maxDets=500 ] = 0.400'
#   'Early stopping: Current mAP (EMA): 0.4386, Best: 0.4386, Diff: ..., Min delta: 0.001'
_RE_AP = re.compile(
    r"Average Precision\s+\(AP\) @\[ IoU=(0\.50:0\.95|0\.50)\s+\| area=\s*all\s*\|"
    r"[^]]*\]\s*=\s*([0-9.]+)"
)
# `Best:` é O NÚMERO que o early-stop usa para eleger `checkpoint_best_total` —
# o mesmo arquivo que vira o ONNX servido. Ancorar aqui é o que garante que a
# métrica gravada é a DO ARTEFATO ENTREGUE, e não a de outra época qualquer.
_RE_EMA = re.compile(
    r"Current mAP \(EMA\):\s*([0-9.]+),\s*Best:\s*([0-9.]+)"
)


def _metricas_do_log() -> dict:
    """Métricas garimpadas do texto que o RF-DETR imprime nesta época.

    Lê o `_LOG_BUFFER` do auto-log (o mesmo tee que sobe o pod.log ao R2) — a
    única fonte onde essas métricas existem. Só a ÚLTIMA ocorrência de cada
    padrão importa: o buffer acumula o run inteiro.
    """
    texto = "".join(_LOG_BUFFER[-4000:])
    metrics: dict = {}
    for iou, valor in _RE_AP.findall(texto):
        try:
            metrics["map" if iou == "0.50:0.95" else "map50"] = float(valor)
        except ValueError:
            continue
    ema = _RE_EMA.findall(texto)
    if ema:
        try:
            metrics["map_ema"] = float(ema[-1][0])
            metrics["map_ema_best"] = float(ema[-1][1])
        except ValueError:
            pass
    return metrics


def _collect_metrics(source: dict) -> dict:
    """Filtra chaves numéricas de métricas conhecidas de um log dict."""
    metrics: dict = {}
    for key, value in source.items():
        if key in _METRIC_KEYS or key.startswith(("map", "mAP", "loss")):
            try:
                metrics[key] = float(value)
            except (TypeError, ValueError):
                continue
    return metrics


# ------------------------------------------------------------------- rfdetr

def _checkpoint_best() -> Path:
    """O .pth que vira o ONNX. best_total > best_ema > falha.

    O fallback antigo era `sorted(OUTPUT_DIR.glob("checkpoint_*.pth"))[-1]`:
    ordem LEXICAL (checkpoint_9 vem DEPOIS de checkpoint_40) e o glob ainda
    casava `checkpoint_best_ema.pth`. Enquanto isso só escolhia o arquivo de
    PESOS a subir, era ruim. Agora que é ELE que vira o ONNX servido, chutar é
    publicar modelo errado — então sem best o job morre em vez de adivinhar.
    """
    for nome in ("checkpoint_best_total.pth", "checkpoint_best_ema.pth"):
        alvo = OUTPUT_DIR / nome
        if alvo.exists():
            logger.info("checkpoint_escolhido: %s", nome)
            return alvo
    achados = sorted(p.name for p in OUTPUT_DIR.glob("*.pth"))
    raise RuntimeError(
        "RF-DETR não produziu checkpoint_best_total.pth nem "
        "checkpoint_best_ema.pth — nada de melhor para exportar. "
        f".pth em {OUTPUT_DIR}: {achados}"
    )


def _carregar_checkpoint(weights: Path) -> tuple:
    """(checkpoint cru, class_embed.bias) de um .pth do RF-DETR.

    head = num_classes + 1 — models/lwdetr.py:934 constrói o nn.Linear com
    args.num_classes + 1; mesma inferência que o loader do rfdetr faz
    (main.py:108). weights_only=True primeiro; o fallback weights_only=False
    (pickle arbitrário) é aceitável porque `args` (Namespace) não passa no
    modo estrito e o raio de dano é o pod do PRÓPRIO tenant: o .pth vem de
    `models/{tenant}/` (prefixo exigido no dispatch), o pod é descartável e
    só tem presigned URLs deste job — um .pth malicioso compromete no máximo
    o treino de quem o subiu, não outro tenant nem a API.
    """
    import torch  # noqa: PLC0415

    try:
        ck = torch.load(weights, map_location="cpu", weights_only=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("torch.load(weights_only=True) falhou (%s) — relendo", exc)
        ck = torch.load(weights, map_location="cpu", weights_only=False)
    estado = (ck.get("model") or ck.get("state_dict") or {}) if isinstance(ck, dict) else {}
    bias = next((v for k, v in estado.items() if k.endswith("class_embed.bias")), None)
    if bias is None:
        raise RuntimeError(
            f"{weights.name} sem class_embed.bias — sem isso não dá para saber "
            f"o tamanho da cabeça. Chaves: {sorted(estado)[:8]}"
        )
    return ck, bias


def _exportar_best_onnx(weights: Path, resolution: int) -> Path:
    """Reconstrói o modelo A PARTIR DO .pth BEST e exporta ONNX @resolution.

    `model.export()` no objeto que acabou de treinar exporta o modelo como
    CONSTRUÍDO, não como treinado: `train()` sincroniza a ÚLTIMA época de volta
    em `self.model.model` (rfdetr detr.py:1001) e `export()` serializa isso —
    não o `checkpoint_best_total.pth` que o resto do pipeline elege, e na
    resolução default do variant (560) em vez dos 616 do treino. O job
    21ea3d00 publicou exatamente esse ONNX errado (#511), e ninguém percebeu
    porque um .onnx perfeitamente VÁLIDO foi produzido.

    Não existe kwarg de checkpoint em `export()` (assinatura completa em
    detr.py:1478) — reconstruir é o único caminho.

    As três coisas que podem sair erradas são CONFERIDAS aqui. Qualquer uma
    falhando derruba o job: publicar um ONNX silenciosamente errado sai mais
    caro que refazer o treino.
    """
    import onnx  # noqa: PLC0415
    import torch  # noqa: PLC0415
    from rfdetr import RFDETRBase  # noqa: PLC0415

    _, ck_bias = _carregar_checkpoint(weights)
    # Nada de num_classes fixo: sem passar explícito, RFDETRBase monta head
    # de 91 (default COCO) e o loader REINICIALIZA a cabeça (main.py:108) —
    # o ONNX sairia aleatório.
    num_classes = int(ck_bias.shape[0]) - 1

    modelo = RFDETRBase(
        pretrain_weights=str(weights),
        resolution=resolution,
        num_classes=num_classes,
    )
    net = modelo.model.model

    # (1) o head instanciado tem o mesmo tamanho do head do checkpoint
    head_modelo = int(net.class_embed.bias.shape[0])
    if head_modelo != int(ck_bias.shape[0]):
        raise RuntimeError(
            f"head do modelo ({head_modelo}) != head do checkpoint "
            f"({int(ck_bias.shape[0])}) — os pesos treinados não entraram."
        )
    # (2) e são de FATO os pesos do checkpoint, não os pré-treinados
    if not torch.allclose(
        net.class_embed.bias.detach().cpu().float(), ck_bias.cpu().float()
    ):
        raise RuntimeError(
            f"class_embed.bias do modelo != o de {weights.name} — o construtor "
            "não carregou os pesos treinados; o ONNX seria o modelo base."
        )

    # 1.5.2: `export()` NÃO devolve o caminho (detr.py: `self.model.export(**kw)`
    # sem return). Escreve `inference_model.onnx` em output_dir — nome FIXO,
    # que SOBRESCREVE export anterior; diff de conjuntos de nomes não detecta
    # nada (provado na bancada em 20/08: segundo export → conjunto vazio).
    # Critério: arquivo com mtime posterior ao início do export.
    inicio_export = time.time()
    modelo.export(output_dir=str(OUTPUT_DIR))
    novos = sorted(
        (f for f in OUTPUT_DIR.rglob("*.onnx") if f.stat().st_mtime >= inicio_export),
        key=lambda f: f.stat().st_mtime,
    )
    if not novos:
        raise RuntimeError(
            f"RF-DETR export não produziu .onnx novo em {OUTPUT_DIR}"
        )
    onnx_path = novos[-1]

    # (3) o ONNX está na resolução de TREINO, não na default do variant
    dims = [
        d.dim_value
        for d in onnx.load(str(onnx_path)).graph.input[0].type.tensor_type.shape.dim
    ]
    if list(dims[2:]) != [resolution, resolution]:
        raise RuntimeError(
            f"input do ONNX {dims} != resolução de treino {resolution} — o edge "
            "redimensionaria errado e a acurácia cairia sem aviso nenhum."
        )

    logger.info(
        "onnx_do_best: %s (classes=%d, resolution=%d, de %s)",
        onnx_path.name, num_classes, resolution, weights.name,
    )
    return onnx_path


def _modelo_fine_tune(dataset_dir: Path, resolution: int):
    """RFDETRBase carregado do NOSSO checkpoint (INIT_WEIGHTS_URL) — fine-tune.

    Quatro coisas, todas ANTES de gastar GPU (a 4ª, resolução, no corpo):
      1. baixa o .pth — torch.save é zip desde 1.6, então o magic "PK" vale:
         o mesmo check que pegou o XML de 404 do R2 no dataset;
      2. num_classes DO CHECKPOINT (head-1): com ele explícito o loader do
         rfdetr (main.py:108) NÃO mexe na cabeça — carrega a treinada. Sem
         ele, head 91 default → cabeça fatiada → o "fine-tune" vira pretrain;
      3. taxonomia: o rfdetr 1.5.2 NÃO quebra se o dataset tiver outras
         classes — `train_from_config` (detr.py:207) redimensiona a cabeça por
         ÍNDICE (lwdetr.py:124, repeat+truncate; com as mesmas classes é
         identidade e o WARNING "Reinitializing your detection head" no log é
         inofensivo). Classe fora de ordem = cabeça treinada apontando para a
         classe errada, em silêncio. `checkpoint_best_total.pth` carrega
         `args.class_names` (strip_checkpoint preserva `args`); a leitura do
         dataset é a MESMA do rfdetr (`_load_classes`, staticmethod — API
         interna, válida porque a versão é PINADA em 1.5.2).
    """
    from rfdetr import RFDETRBase  # noqa: PLC0415

    init_pth = WORK_DIR / "init.pth"
    download(INIT_WEIGHTS_URL, init_pth, expect_zip=True)
    ck, bias = _carregar_checkpoint(init_pth)
    num_classes = int(bias.shape[0]) - 1
    # 4. resolução: o checkpoint carrega `args.resolution` (v9 = 560) e o
    #    positional embedding foi treinado nela. Fine-tune noutra resolução
    #    (IMGSZ default do dispatch 640 → 616) é confound silencioso — recusa.
    res_ck = getattr(ck.get("args"), "resolution", None)
    if res_ck is not None and int(res_ck) != resolution:
        raise RuntimeError(
            f"fine-tune recusado: checkpoint @{int(res_ck)}, IMGSZ pede "
            f"{resolution} — dispare com imgsz={int(res_ck)}."
        )
    nomes_ck = list(getattr(ck.get("args"), "class_names", None) or [])
    nomes_ds = list(RFDETRBase._load_classes(str(dataset_dir)))
    if (nomes_ck and nomes_ck != nomes_ds) or len(nomes_ds) != num_classes:
        raise RuntimeError(
            f"fine-tune recusado: checkpoint com {num_classes} classes "
            f"{nomes_ck or '(sem nomes)'} e dataset com {len(nomes_ds)} "
            f"{nomes_ds} — a cabeça treinada ficaria desalinhada. Reexporte o "
            "dataset com a mesma taxonomia ou remova init_weights_r2_key para "
            "treinar do pretrain."
        )
    logger.info("rfdetr_fine_tune: init=%s classes=%d", init_pth.name, num_classes)
    return RFDETRBase(
        pretrain_weights=str(init_pth),
        resolution=resolution,
        num_classes=num_classes,
    )


def _vram_gib() -> float | None:
    """VRAM da placa que a RunPod REALMENTE entregou, lida de dentro do pod.

    É a única fonte de verdade sobre o hardware da corrida: `create_pod` manda
    `gpuTypeIds: [tipo]` e a plataforma pode entregar outra placa sem erro, e
    `get_pod` devolve `gpuTypeIds: null`. Sem esta leitura, nada no sistema
    registra em que hardware o modelo foi treinado.
    """
    try:
        import torch  # noqa: PLC0415 — só existe dentro do pod

        return torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    except Exception as exc:  # noqa: BLE001 — sem CUDA legível, quem chama decide
        logger.warning("vram_gib: GPU ilegível (%s)", exc)
        return None


def _cap_de_batch() -> int:
    """Maior batch que a placa desta corrida aguenta, medido no pod.

    Não é escolha de performance, é guarda de OOM: o teto de 4 nasceu de um
    estouro real em 24GB (job 90946c17, 23,38 GiB com batch 16 @616). Em 48GB
    o 16 cabe com folga e o grad_accum deixa de ser necessário.

    Falha para 4 — o valor que já rodava — quando não dá para ler a GPU. Um
    palpite otimista aqui custa a corrida inteira em OOM na primeira época;
    um palpite conservador custa tempo. A casa prefere perder tempo.

    ⚠️ `BATCH_FIXO` desliga a adaptação. Existe porque adaptar-se à placa é
    certo em PRODUÇÃO e errado num EXPERIMENTO, e o código não tinha como
    distinguir os dois. Medido em 02/09: pedimos 4090 (24 GiB) nos dois braços
    do A/B e a RunPod entregou uma A6000 (47,4 GiB) no segundo, sem erro e sem
    registrar a troca (`get_pod` devolve `gpuTypeIds: null`). Este cap então
    liberou 16 num braço e 4 no outro. O batch EFETIVO ficou 16 nos dois, mas
    o caminho não: o DETR normaliza a loss por `num_boxes` a cada MICRO-lote,
    então 4×4 normaliza sobre 4 imagens e 16×1 sobre 16 — diferença pequena e
    real, que entraria na comparação disfarçada de diferença entre taxonomias.
    Com `BATCH_FIXO`, uma placa que não comporta o valor pedido ABORTA em vez
    de se adaptar: num experimento, morrer alto é melhor que divergir calado.
    """
    if BATCH_FIXO:
        gib = _vram_gib()
        cabe = 16 if (gib is None or gib >= 44) else 4
        if BATCH > cabe:
            raise RuntimeError(
                f"BATCH_FIXO={BATCH} não cabe nesta placa "
                f"({'VRAM ilegível' if gib is None else f'{gib:.1f} GiB'}, "
                f"comporta {cabe}). A RunPod entrega placa diferente da pedida "
                "sem avisar; num experimento controlado isso ABORTA em vez de "
                "virar outro hiperparâmetro em silêncio."
            )
        logger.info("cap_de_batch: BATCH_FIXO=%d (adaptação desligada)", BATCH)
        return BATCH

    gib = _vram_gib()
    if gib is None:
        return 4
    # 44 e não 48: a placa reporta menos que o nominal (uma A6000 de 48GB
    # informa ~47,4 GiB) e parte fica com o contexto de CUDA.
    cap = 16 if gib >= 44 else 4
    logger.info("cap_de_batch: %.1f GiB na GPU → batch até %d", gib, cap)
    return cap


def train_rfdetr(dataset_dir: Path) -> tuple[Path, Path | None, dict]:
    """Treina RF-DETR (Apache 2.0) e exporta ONNX.

    Passos do runbook TRAINING_PIPELINE_WEEKEND_MVP.md:
      pip install rfdetr → model.train(dataset_dir=..., epochs=N)
      pip install "rfdetr[onnx]" → model.export() → um .onnx
    """
    # transformers<5: o rfdetr importa BackboneConfigMixin, API da série 4.x
    # removida na 5.x — sem o pin, o pod resolve a 5.x e morre no import
    # (visto em produção DEV: job 9504a3a2, pods m0amcgnl4/1849fpuq).
    # `onnx` e `onnxruntime` EXPLÍCITOS: listar "rfdetr" antes de
    # "rfdetr[onnx]" na mesma chamada faz o pip considerar o requisito já
    # satisfeito pelo primeiro e PULAR o extra. O treino roda até o fim e só
    # então morre no export com "Module onnx is not installed!" — depois de
    # pagar a GPU inteira. Ambos são licenças permissivas (onnx Apache 2.0,
    # onnxruntime MIT), dentro do ADR-0043.
    # PIN: 1.5.2 é a versão que o resolver escolhe COM `transformers<5` e a que
    # treinou o job 21ea3d00 — reprodutível e provada. ⚠️ NÃO subir para 1.9.x
    # mantendo `transformers<5`: rfdetr>=1.9 exige transformers>=5.1 e o pip
    # morre em ResolutionImpossible ANTES da época 0 (verificação adversarial
    # do v9). TrainConfig é pydantic extra="forbid": kwarg que a versão não
    # conhece mata o pod pago — toda mudança aqui exige conferir os campos na
    # MESMA versão pinada, não na do venv local.
    pip_install(
        "rfdetr==1.5.2", "rfdetr[onnx]==1.5.2", "onnx", "onnxruntime",
        "supervision", "transformers<5",
    )
    from rfdetr import RFDETRBase  # noqa: PLC0415

    # RF-DETR (backbone DINOv2) exige resolution múltipla de 56 — o IMGSZ=640
    # herdado do fluxo YOLO derruba o treino no primeiro forward ("Backbone
    # requires input shape to be divisible by 56", visto no DEV: job 90946c17).
    # Ajusta para o múltiplo de 56 mais próximo (default do RFDETRBase é 560).
    resolution = max(56, round(IMGSZ / 56) * 56)
    if resolution != IMGSZ:
        logger.info("rfdetr_resolution_ajustada: %d → %d (múltiplo de 56)", IMGSZ, resolution)

    # Fine-tune (INIT_WEIGHTS_URL) parte do NOSSO checkpoint; sem ele, o
    # caminho padrão (pretrain do RF-DETR) fica exatamente como era.
    model = (
        _modelo_fine_tune(dataset_dir, resolution) if INIT_WEIGHTS_URL else RFDETRBase()
    )
    last_metrics: dict = {}
    state = {"epoch": 0}

    def _on_epoch_end(log: dict) -> None:
        # A contagem é NOSSA, não do framework. `log["epoch"]` do RF-DETR não é
        # o número da época: no job f31f5381 ele subiu a 49, VOLTOU a 32, depois
        # a 13, e fechou em 50 com total_epochs=12 — comportamento de contador de
        # passo (issue #420). Este hook é chamado uma vez por época; contar as
        # chamadas é a única fonte que não mente.
        state["epoch"] += 1
        epoch = state["epoch"]
        metrics = _collect_metrics(log if isinstance(log, dict) else {})
        # O dict do framework vem SEM mAP na 1.5.2 — o número está no texto
        # que ele imprimiu. Sem esta linha o modelo nasce com métrica zero.
        metrics.update(_metricas_do_log())
        # O número do framework não é descartado — vai para métrica com nome
        # que diz o que ele é, para o dia em que alguém precisar diagnosticá-lo.
        bruto = log.get("epoch") if isinstance(log, dict) else None
        if bruto is not None and int(bruto) != epoch:
            metrics["epoch_bruto_do_framework"] = int(bruto)
        last_metrics.update(metrics)
        progress = min(90, 5 + int(epoch / max(EPOCHS, 1) * 85))
        # Envia o ACUMULADO (last_metrics), não só o log desta época: o
        # backend faz UPDATE ... SET metrics = %s (overwrite, não merge —
        # ver TrainingRepository.update_job_status), e frameworks de treino
        # nem sempre logam a mesma chave em toda época (ex.: mAP só a cada
        # N épocas) — mandar só `metrics` fazia chaves já reportadas
        # desaparecerem do progresso ao vivo (achado da revisão adversarial).
        post_callback({
            "status": "running",
            "progress": progress,
            "epoch": epoch,
            "metrics": dict(last_metrics),
        })

    try:
        model.callbacks["on_fit_epoch_end"].append(_on_epoch_end)
    except (AttributeError, KeyError, TypeError):
        logger.warning("rfdetr sem hook on_fit_epoch_end — progresso só no final")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # RF-DETR base @616 com batch 16 estoura os 24GB da RTX 3090 (OOM real
    # no DEV, job 90946c17: 23,38 GiB em uso). Cap em 4; grad_accum preserva
    # o batch EFETIVO 16 (4 × 4) — mesma matemática, memória 1/4.
    #
    # O cap está certo PARA 24GB e vira desperdício em 48GB, onde o 16 cabe
    # inteiro e dispensa a acumulação. Quem decide é a placa que a RunPod
    # sorteou nesta corrida, não uma constante: o mesmo job pode cair numa
    # A6000 hoje e numa 3090 amanhã.
    batch_size = min(max(BATCH, 1), _cap_de_batch())
    model.train(
        dataset_dir=str(dataset_dir),
        epochs=EPOCHS,
        batch_size=batch_size,
        grad_accum_steps=max(1, 16 // batch_size),
        lr=1e-4,
        # Decay COSSENO ao longo do run. O default do RF-DETR é "step" com
        # Decay: a 1.5.2 NÃO tem `lr_scheduler` (cosine é 1.9+); o que existe
        # é o step decay por `lr_drop` (default 100 — em 50 épocas o LR nunca
        # caía e o modelo decorava: AP@50 EMA 0,366 na ép.12 → 0,290 na 44,
        # job 21ea3d00). Queda de 10× na época 15, logo após o pico observado.
        lr_drop=15,
        # Para quando a validação empaca — não paga GPU depois do pico.
        # use_ema=True: a métrica estável do harness sempre foi a EMA.
        #
        # patience 15 (era 8): com teto de 100 épocas, 8 é curto demais. O
        # `lr_drop=15` derruba o LR de 10× na época 15, e a val costuma dar um
        # SEGUNDO salto logo depois — com patience 8 o run morre na 14ª parada
        # sem nunca ver o efeito do próprio decay que este arquivo configura.
        # Tunável por env para o dia em que a curva mostrar outro platô.
        early_stopping=True,
        early_stopping_patience=PATIENCE,
        early_stopping_use_ema=True,
        resolution=resolution,
        output_dir=str(OUTPUT_DIR),
    )
    # Com early-stop o run acaba antes de EPOCHS; sem isso o callback final
    # reportaria 50 épocas para um treino que rodou 20.
    last_metrics["epochs_ran"] = float(state["epoch"])

    weights = _checkpoint_best()
    onnx_path = _exportar_best_onnx(weights, resolution)
    return onnx_path, weights, last_metrics


# -------------------------------------------------------------------- yolox

def train_yolox(dataset_dir: Path) -> tuple[Path, Path | None, dict]:
    """Treina YOLOX-s (Apache 2.0) via CLI oficial e exporta ONNX."""
    pip_install("yolox", "onnx")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # YOLOX espera datasets/COCO com annotations/ + train2017/ + val2017/;
    # o layout COCO exportado (train/valid/_annotations.coco.json) é adaptado
    # via -d/-b e exp custom simplificado. MVP: treino padrão yolox_s.
    subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "yolox.tools.train",
            "-n", "yolox-s",
            "-b", str(BATCH),
            "--fp16",
            "-o",
            "max_epoch", str(EPOCHS),
            "data_dir", str(dataset_dir),
            "output_dir", str(OUTPUT_DIR),
        ],
        check=True,
        text=True,
        cwd=str(WORK_DIR),
    )

    ckpts = sorted(OUTPUT_DIR.rglob("best_ckpt.pth"))
    if not ckpts:
        raise RuntimeError("YOLOX não produziu best_ckpt.pth")
    weights = ckpts[-1]

    onnx_path = OUTPUT_DIR / "yolox_s_recognition.onnx"
    subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "yolox.tools.export_onnx",
            "-n", "yolox-s",
            "-c", str(weights),
            "--output-name", str(onnx_path),
        ],
        check=True,
        text=True,
        cwd=str(WORK_DIR),
    )
    return onnx_path, weights, {}


# ----------------------------------------------------------------- validate

def validate_onnx(onnx_path: Path) -> None:
    """Valida o ONNX com onnxruntime: cria session e roda dummy input."""
    pip_install("onnxruntime", "numpy")
    import numpy as np  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415

    session = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    feeds = {}
    for inp in session.get_inputs():
        shape = [
            dim if isinstance(dim, int) and dim > 0 else (IMGSZ if i >= 2 else 1)
            for i, dim in enumerate(inp.shape)
        ]
        dtype = np.float16 if "float16" in inp.type else np.float32
        feeds[inp.name] = np.zeros(shape, dtype=dtype)
    outputs = session.run(None, feeds)
    logger.info(
        "onnx_validated: %s outputs=%d shapes=%s",
        onnx_path.name, len(outputs), [getattr(o, "shape", None) for o in outputs],
    )


# --------------------------------------------------------------------- main

def _hardware_da_corrida() -> dict:
    """Placa que a RunPod REALMENTE entregou — para o job registrar em que
    hardware o modelo foi treinado.

    Sem isto, NADA no sistema guarda essa informação: `create_pod` manda
    `gpuTypeIds: [tipo]` e a plataforma pode entregar outra placa sem erro, e
    `get_pod` devolve `gpuTypeIds: null`. Em 02/09 pedimos 4090 (24 GiB) nos
    dois braços de um A/B e veio uma A6000 (47,4 GiB) no segundo — só deu para
    descobrir cavando o `pod.log` no R2. Um modelo cuja placa não foi
    registrada é um modelo cuja corrida não pode ser reproduzida nem auditada.

    ⚠️ Vai DENTRO de `metrics`, como chave de primeiro nível dela. Duas razões,
    ambas verificadas no código do backend:
      - `_validate_callback_payload` (job_handlers.py) remonta o payload com um
        conjunto FIXO de chaves; um `hardware` irmão de `metrics` seria
        descartado em silêncio e nunca chegaria ao banco;
      - a gravação funde com `metrics = COALESCE(metrics,'{}') || %s::jsonb`, e
        o `||` do jsonb é RASO — gravar isto dentro de `provenance` substituiria
        o objeto inteiro e apagaria o `runner_sha256`/`worker_commit` que o
        dispatch escreveu antes do pod subir.
    """
    dados: dict = {"vram_gib": None, "gpu": None, "batch_fixo": BATCH_FIXO}
    gib = _vram_gib()
    if gib is not None:
        dados["vram_gib"] = round(gib, 1)
    try:
        import torch  # noqa: PLC0415 — só existe dentro do pod

        dados["gpu"] = torch.cuda.get_device_properties(0).name
    except Exception as exc:  # noqa: BLE001 — proveniência nunca derruba treino
        logger.warning("hardware_da_corrida: nome da GPU ilegível (%s)", exc)
    logger.info("hardware_da_corrida: %s", dados)
    return dados


def main() -> int:
    post_callback({"status": "running", "progress": 1,
                   "metrics": {"stage": 1.0, "hardware": _hardware_da_corrida()}})
    dataset_dir = prepare_dataset()
    post_callback({"status": "running", "progress": 5,
                   "metrics": {"stage": 2.0}})

    if FRAMEWORK == "yolox":
        onnx_path, weights_path, metrics = train_yolox(dataset_dir)
    else:
        onnx_path, weights_path, metrics = train_rfdetr(dataset_dir)

    post_callback({"status": "running", "progress": 92, "metrics": metrics})
    validate_onnx(onnx_path)

    if UPLOAD_URL_ONNX:
        http_put(UPLOAD_URL_ONNX, onnx_path, "application/octet-stream")
    if UPLOAD_URL_WEIGHTS and weights_path and weights_path.exists():
        http_put(UPLOAD_URL_WEIGHTS, weights_path, "application/octet-stream")

    metrics_path = WORK_DIR / "metrics.json"
    metrics_doc = {
        "framework": FRAMEWORK,
        "epochs": EPOCHS,
        "r2_key": R2_ONNX_KEY,
        **metrics,
    }
    metrics_path.write_text(json.dumps(metrics_doc, indent=2))
    if UPLOAD_URL_METRICS:
        http_put(UPLOAD_URL_METRICS, metrics_path, "application/json")

    post_callback({
        "status": "completed",
        "progress": 100,
        # EPOCHS é o orçamento pedido, não o que rodou: com early-stop o run
        # acaba antes. `epochs_ran` é a contagem NOSSA de chamadas do hook
        # por-época (issue #420 — o número do framework sobe e desce).
        "epoch": int(metrics.get("epochs_ran", EPOCHS)),
        "metrics": metrics,
        "r2_onnx_key": R2_ONNX_KEY,
    })
    logger.info("remote_train_completed: onnx=%s", onnx_path)
    return 0


# --------------------------------------------------------------- auto-log
#
# O pod sobe o PRÓPRIO stdout/stderr ao R2. A API REST do RunPod não expõe
# logs (`/v1/pods/{id}/logs` → HTTP 400), então toda falha de pod era cega:
# o log morria com o pod e o diagnóstico virava adivinhação. Nove pods e duas
# paradas do loop custaram isso.
#
# Estratégia: `tee` em memória + flush periódico ao R2 + upload final no
# encerramento. O upload final NÃO cobre SIGKILL/OOM (o processo morre sem
# rodar nada), e é justamente por isso que existe o flush periódico: se o
# kernel matar, o último flush é o que sobra — muito melhor que nada.
_LOG_BUFFER: list[str] = []
_LOG_FLUSH_SECONDS = 120


class _Tee:
    """Escreve no destino original E guarda para o R2."""

    def __init__(self, original):
        self._original = original

    def write(self, texto):
        self._original.write(texto)
        _LOG_BUFFER.append(texto)
        return len(texto)

    def flush(self):
        self._original.flush()

    def __getattr__(self, nome):
        return getattr(self._original, nome)


def _subir_log(motivo: str) -> None:
    if not UPLOAD_URL_LOG or not _LOG_BUFFER:
        return
    try:
        corpo = "".join(_LOG_BUFFER).encode("utf-8", "replace")
        req = urllib.request.Request(
            UPLOAD_URL_LOG, data=corpo, method="PUT",
            headers={"Content-Type": "text/plain"},
        )
        urllib.request.urlopen(req, timeout=120)  # noqa: S310
        logger.info("log_uploaded: %s (%d bytes)", motivo, len(corpo))
    except Exception as exc:  # noqa: BLE001 — log nunca derruba o treino
        logger.warning("log_upload_failed (%s): %s", motivo, exc)


def _flush_periodico() -> None:
    while True:
        time.sleep(_LOG_FLUSH_SECONDS)
        _subir_log("flush periodico")


def _instalar_autolog() -> None:
    if not UPLOAD_URL_LOG:
        return
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler):
            h.stream = sys.stderr
    threading.Thread(target=_flush_periodico, daemon=True).start()
    atexit.register(lambda: _subir_log("encerramento"))


if __name__ == "__main__":
    _instalar_autolog()
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — reporta QUALQUER falha ao backend
        logger.exception("remote_train_failed")
        _subir_log("falha")
        post_callback({"status": "failed", "error_message": str(exc)[:500]})
        sys.exit(1)
