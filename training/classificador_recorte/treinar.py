#!/usr/bin/env python3
"""Treina o classificador de recorte v1: DINOv2 congelado + cabeça linear.

Uma cabeça POR FAMÍLIA de EPI. Cada família treina só nos frames que têm
rótulo daquela família — "não visível" não gera anotação, então rótulo
faltante é rótulo faltante, nunca negativo (mesmo princípio da ADR-0067
aplicado ao dataset).

Backbone CONGELADO de propósito. Com 27 a 95 exemplos na classe minoritária,
fine-tunar um ViT é o caminho mais curto para decorar o treino e produzir uma
régua que mente. O embedding é o mesmo de `training/propagate_seeded.py`
(DINOv2 ViT-S/14, Apache 2.0, sha256 pinado em docs/WEIGHTS_LICENSES.md), com
a MESMA preparação de imagem — se divergir, o que a régua mede não é o que a
produção veria.

Desbalanceio: `class_weight` inverso à frequência. Sem isso, `luvas` (48 com,
183 sem) aprende "sempre sem" e acerta 79% sendo inútil — exatamente o vício
que a régua existe para pegar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("treinar")

PESO_URL = (
    "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth"
)
PESO_SHA256 = "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9"

#: Mínimo de exemplos na classe minoritária para a família ser treinada.
#: Abaixo disso o resultado não é um classificador, é um gerador de maioria com
#: ruído — e a régua não teria n para reprovar honestamente.
MINORIA_MINIMA = 25


def baixa_e_verifica(destino: Path) -> Path:
    """Baixa o checkpoint e CONFERE o sha256 — fail-closed.

    Mesma política de `propagate_seeded.download_and_verify_weight`: peso que
    não bate o hash não carrega. É o que faz o "Apache 2.0" da tabela de
    licenças valer para o arquivo que roda de fato, e não para um que alguém
    supôs.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        digest = hashlib.sha256(destino.read_bytes()).hexdigest()
        if digest == PESO_SHA256:
            return destino
        log.warning("peso_local_com_hash_divergente: rebaixando")
        destino.unlink()

    log.info("baixando DINOv2 ViT-S/14 (~84 MB)…")
    urllib.request.urlretrieve(PESO_URL, destino)  # noqa: S310 — URL fixa oficial
    digest = hashlib.sha256(destino.read_bytes()).hexdigest()
    if digest != PESO_SHA256:
        destino.unlink(missing_ok=True)
        raise RuntimeError(
            f"sha256 do peso divergiu: {digest} != {PESO_SHA256} — não carregando"
        )
    return destino


def carrega_backbone(peso: Path):
    import torch

    modelo = torch.hub.load(  # noqa: S614 — repo oficial Meta, pretrained=False
        "facebookresearch/dinov2", "dinov2_vits14", pretrained=False
    )
    modelo.load_state_dict(torch.load(peso, map_location="cpu", weights_only=True))
    modelo.eval()
    return modelo


def embeddings(modelo, caminhos: list[Path], lote: int = 16):
    """Embedding CLS de cada recorte.

    Preparação IDÊNTICA à de `propagate_seeded.embed_crop`: 224×224 (múltiplo
    de 14), RGB, /255, normalização ImageNet. A imagem JÁ é o recorte de pessoa
    (o edge roda `crop_person` antes do upload), então não há recorte aqui.
    """
    import numpy as np
    import torch
    from PIL import Image

    media = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    desvio = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    saida = []
    for i in range(0, len(caminhos), lote):
        tensores = []
        for p in caminhos[i : i + lote]:
            with Image.open(p) as im:
                arr = np.asarray(im.convert("RGB").resize((224, 224)), dtype=np.float32)
            arr = (arr / 255.0 - media) / desvio
            tensores.append(torch.from_numpy(arr.transpose(2, 0, 1)))
        with torch.no_grad():
            saida.append(modelo(torch.stack(tensores)).cpu())
        log.info("  embedding %d/%d", min(i + lote, len(caminhos)), len(caminhos))
    return torch.cat(saida)


def treina_cabeca(X, y, n_classes: int, epocas: int = 300, semente: int = 20260825):
    """Regressão logística multinomial (uma `nn.Linear`), com peso por classe."""
    import torch
    from torch import nn

    torch.manual_seed(semente)
    contagem = torch.bincount(y, minlength=n_classes).float()
    # Peso inverso à frequência: sem isso a cabeça aprende a maioria e a
    # acurácia sobe enquanto a classe que importa (a minoritária, que é
    # justamente a ausência) desaparece.
    peso = torch.where(contagem > 0, contagem.sum() / (n_classes * contagem), torch.zeros(1))

    cabeca = nn.Linear(X.shape[1], n_classes)
    otim = torch.optim.AdamW(cabeca.parameters(), lr=1e-3, weight_decay=1e-2)
    perda = nn.CrossEntropyLoss(weight=peso)
    for _ in range(epocas):
        otim.zero_grad()
        saida = perda(cabeca(X), y)
        saida.backward()
        otim.step()
    return cabeca, float(saida)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--saida", type=Path, default=None)
    p.add_argument("--pesos", type=Path, default=Path.home() / ".cache" / "recognition" / "dinov2_vits14.pth")
    args = p.parse_args()
    saida = args.saida or args.dataset / "modelo"
    saida.mkdir(parents=True, exist_ok=True)

    import torch

    manifesto = json.loads((args.dataset / "manifesto.json").read_text(encoding="utf-8"))
    frames = [f for f in manifesto["frames"]
              if (args.dataset / "imagens" / f"{f['frame_id']}.jpg").exists()]
    log.info("frames com imagem: %d de %d", len(frames), len(manifesto["frames"]))

    modelo = carrega_backbone(baixa_e_verifica(args.pesos))
    caminhos = [args.dataset / "imagens" / f"{f['frame_id']}.jpg" for f in frames]
    cache = args.dataset / "embeddings.pt"
    if cache.exists():
        X_tudo = torch.load(cache, weights_only=True)
        log.info("embeddings do cache: %s", tuple(X_tudo.shape))
    else:
        X_tudo = embeddings(modelo, caminhos)
        torch.save(X_tudo, cache)
        log.info("embeddings: %s", tuple(X_tudo.shape))

    indice = {f["frame_id"]: i for i, f in enumerate(frames)}
    resumo = {}
    for familia in manifesto["familias"]:
        do_treino = [f for f in frames
                     if f["split"] == "train" and familia in f["rotulos"]]
        if not do_treino:
            continue
        classes = sorted({f["rotulos"][familia] for f in do_treino})
        alvo = torch.tensor([classes.index(f["rotulos"][familia]) for f in do_treino])
        minoria = int(torch.bincount(alvo, minlength=len(classes)).min())
        if len(classes) < 2 or minoria < MINORIA_MINIMA:
            log.warning(
                "familia_pulada: %s — %d classes, minoria=%d (< %d). "
                "Treinar aqui produziria um gerador de maioria, e a régua não "
                "teria n para reprovar honestamente.",
                familia, len(classes), minoria, MINORIA_MINIMA,
            )
            resumo[familia] = {"treinada": False, "motivo": f"minoria={minoria}"}
            continue

        X = X_tudo[[indice[f["frame_id"]] for f in do_treino]]
        cabeca, perda = treina_cabeca(X, alvo, len(classes))
        torch.save(
            {"peso": cabeca.state_dict(), "classes": classes, "dim": X.shape[1]},
            saida / f"{familia}.pt",
        )
        resumo[familia] = {
            "treinada": True, "classes": classes, "n_treino": len(do_treino),
            "minoria": minoria, "perda_final": round(perda, 4),
        }
        log.info("%s: %s n=%d minoria=%d perda=%.4f",
                 familia, classes, len(do_treino), minoria, perda)

    (saida / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    log.info("modelos em %s", saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
