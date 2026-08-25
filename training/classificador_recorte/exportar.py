#!/usr/bin/env python3
"""Exporta o acervo de CLASSIFICAÇÃO (aba Classificar) para treino offline.

O exportador de detecção (`versioning_v2.build_dataset_version_v2`) DESCARTA
exatamente estas linhas: `_e_rotulo_de_frame` remove toda caixa com área ≥ 0,95
porque ela não é alvo de localização. Está certo lá e é por isso que este
exportador existe — o mesmo dado que não serve para ensinar ONDE serve para
ensinar O QUÊ.

Procedência: só `source='manual'`. Veredito de classificação é julgamento
humano; proposta de modelo não entra (D-39 / ADR-0066).

Rótulo faltante ≠ negativo: "não visível" não gera anotação, então por família
só entram os frames que TÊM rótulo daquela família. Ver o README.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("exportar")

#: Famílias de EPI e os nomes de classe que representam cada veredito.
#: Os nomes vêm do catálogo real (global + tenant) — conferidos no banco do DEV.
FAMILIAS: dict[str, dict[str, list[str]]] = {
    "mascara": {
        "com": ["mascara"],
        "sem": ["Sem mascara"],
        "incorreto": ["Uso incorreto de mascara", "Uso incorreto"],
    },
    "luvas": {"com": ["Luvas"], "sem": ["Sem Luvas"]},
    "oculos": {"com": ["Óculos"], "sem": ["Sem Óculos"]},
    # Treina, mas a régua provavelmente reprova: 27 exemplos na minoria.
    "auditiva": {
        "com": ["Protetor auditivo", "Protetor auricular"],
        "sem": ["Sem protetor de ouvido"],
    },
    # ⛔ 'botas' fica FORA: zero exemplos de ausência no acervo. Um classificador
    # aqui aprenderia "sempre com" e acertaria 100% sendo inútil.
}

#: Área a partir da qual a anotação é rótulo de frame, não caixa localizada.
#: Mesmo valor de versioning_v2._AREA_ROTULO_DE_FRAME — os dois lados têm de
#: concordar, senão uma linha cai nos dois datasets ou em nenhum.
AREA_ROTULO_DE_FRAME = 0.95

SPLITS = (("train", 0.70), ("val", 0.15), ("test", 0.15))


def _split_estavel(chave: str, semente: str) -> str:
    """Partição por hash — independente da população.

    Ordenar-e-fatiar faz o split de um frame mudar quando OUTRO frame entra no
    acervo, e aí "campo virgem" deixa de ser virgem entre duas rodadas. Com
    hash, o frame X cai sempre no mesmo lado, hoje e daqui a mil anotações.
    """
    digest = hashlib.sha256(f"{semente}\x00{chave}".encode()).digest()
    ponto = int.from_bytes(digest[:8], "big") / float(1 << 64)
    acumulado = 0.0
    for nome, fracao in SPLITS:
        acumulado += fracao
        if ponto < acumulado:
            return nome
    return SPLITS[-1][0]


def _conecta():
    import psycopg2
    import psycopg2.extras

    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        log.error("DATABASE_URL ausente")
        sys.exit(2)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def _rotulo_da_familia(nome_classe: str) -> list[tuple[str, str]]:
    achados = []
    for familia, estados in FAMILIAS.items():
        for rotulo, nomes in estados.items():
            if nome_classe in nomes:
                achados.append((familia, rotulo))
    return achados


def coleta(tenant_id: str, semente: str) -> dict:
    """Lê o acervo e monta {frame_id: {r2_key, camera, split, rotulos}}."""
    conn = _conecta()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT fa.frame_id, fa.class_name, tf.r2_key, tf.camera_id,
               COALESCE(c.name, '(sem câmera)') AS camera
          FROM frame_annotations fa
          JOIN training_frames tf ON tf.id = fa.frame_id
          LEFT JOIN cameras c ON c.id = tf.camera_id
         WHERE fa.width * fa.height >= %s
           AND fa.source = 'manual'
           AND tf.r2_key IS NOT NULL
           AND COALESCE(tf.curation_status, '') <> 'excluida'
        """,
        (AREA_ROTULO_DE_FRAME,),
    )
    frames: dict[str, dict] = {}
    for linha in cur.fetchall():
        fid = str(linha["frame_id"])
        item = frames.setdefault(
            fid,
            {
                "frame_id": fid,
                "r2_key": linha["r2_key"],
                "camera": linha["camera"],
                "camera_id": str(linha["camera_id"]) if linha["camera_id"] else None,
                "rotulos": {},
                "split": _split_estavel(fid, semente),
            },
        )
        for familia, rotulo in _rotulo_da_familia(linha["class_name"]):
            anterior = item["rotulos"].get(familia)
            if anterior and anterior != rotulo:
                # Dois vereditos conflitantes na MESMA família e MESMO frame.
                # Não escolher em silêncio: derruba o frame daquela família.
                log.warning(
                    "veredito_conflitante: frame=%s familia=%s %r vs %r — "
                    "família descartada neste frame",
                    fid, familia, anterior, rotulo,
                )
                item["rotulos"][familia] = None
            elif anterior is None and familia in item["rotulos"]:
                pass  # já marcado como conflitante; não ressuscita
            else:
                item["rotulos"][familia] = rotulo
    conn.close()

    for item in frames.values():
        item["rotulos"] = {k: v for k, v in item["rotulos"].items() if v is not None}
    return frames


def relatorio(frames: dict) -> None:
    log.info("frames com veredito: %d", len(frames))
    print(f"\n{'família':<12}{'split':<8}{'com':>6}{'sem':>6}{'incorr':>8}")
    for familia in FAMILIAS:
        for split, _ in SPLITS:
            cnt = collections.Counter(
                f["rotulos"][familia]
                for f in frames.values()
                if f["split"] == split and familia in f["rotulos"]
            )
            if sum(cnt.values()):
                print(
                    f"  {familia:<10}{split:<8}{cnt.get('com', 0):>6}"
                    f"{cnt.get('sem', 0):>6}{cnt.get('incorreto', 0):>8}"
                )
    print(f"\n{'câmera':<34}{'frames':>8}")
    for cam, n in collections.Counter(f["camera"] for f in frames.values()).most_common(8):
        print(f"  {str(cam)[:32]:<34}{n:>8}")


def baixa_imagens(frames: dict, destino: Path) -> int:
    """Baixa os recortes do R2. Os frames do pool JÁ SÃO recortes de pessoa
    (`crop_person` roda no edge antes do upload), então não há recorte a fazer
    aqui — o que veio é o que o classificador vê."""
    from concurrent.futures import ThreadPoolExecutor

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api"))
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    armazenamento = get_storage(None)
    destino.mkdir(parents=True, exist_ok=True)
    faltaram = []

    def uma(item):
        alvo = destino / f"{item['frame_id']}.jpg"
        if alvo.exists():
            return True
        try:
            alvo.write_bytes(armazenamento.download_bytes(item["r2_key"]))
            return True
        except Exception as exc:  # noqa: BLE001
            faltaram.append((item["frame_id"], str(exc)[:80]))
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        ok = sum(pool.map(uma, frames.values()))

    if faltaram:
        # Não silenciar: frame que não baixou é frame que sai do treino, e a
        # contagem do relatório passaria a mentir sobre o tamanho do acervo.
        log.warning("nao_baixaram: %d frames", len(faltaram))
        for fid, erro in faltaram[:5]:
            log.warning("  %s: %s", fid, erro)
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--saida", required=True, type=Path)
    p.add_argument("--tenant", default="63c219d8-fbef-4f3c-a7c9-058c742482e2")
    p.add_argument("--semente", default="recorte-v1")
    p.add_argument("--sem-imagens", action="store_true", help="só o manifesto")
    args = p.parse_args()

    frames = coleta(args.tenant, args.semente)
    if not frames:
        log.error("acervo vazio — nada a exportar")
        return 1
    relatorio(frames)

    args.saida.mkdir(parents=True, exist_ok=True)
    manifesto = args.saida / "manifesto.json"
    manifesto.write_text(
        json.dumps(
            {
                "semente": args.semente,
                "area_rotulo_de_frame": AREA_ROTULO_DE_FRAME,
                "familias": {k: sorted(v) for k, v in FAMILIAS.items()},
                "frames": list(frames.values()),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    log.info("manifesto: %s (%d frames)", manifesto, len(frames))

    if not args.sem_imagens:
        n = baixa_imagens(frames, args.saida / "imagens")
        log.info("imagens baixadas: %d/%d", n, len(frames))
    return 0


if __name__ == "__main__":
    sys.exit(main())
