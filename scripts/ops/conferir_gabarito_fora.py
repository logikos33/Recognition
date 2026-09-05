#!/usr/bin/env python3
"""conferir_gabarito_fora.py — o gabarito do dono não pode estar no dataset.

POR QUE EXISTE, se a trava já vive no export
────────────────────────────────────────────────────────────────────────────────
`versioning_v2._snapshot_labeled_frames` filtra `dataset_role='pool'` (ALLOWLIST)
e `test_montar_dataset_multiescala.py` prova, por mutação, que a trava pega. Isso
confere o CÓDIGO. Este script confere o **ARTEFATO GRAVADO** — que é coisa
diferente: um COCO montado por outro caminho, um recorte sintético cujo pai
vazou, um arquivo copiado à mão para a pasta. O gabarito de 246 quadros é a
RÉGUA do A/B (`docs/quality/AB-HOLDOUT-V2-VEREDITO.md`); vazamento não deixa a
medida ruim, deixa a medida MENTIROSA, e ela continua com cara de medida.

Roda contra o dataset em disco, ANTES de exportar e de gastar GPU.

OS QUATRO CANAIS (nenhum sozinho basta)
────────────────────────────────────────────────────────────────────────────────
1. **frame_id** — o `file_name` do COCO do RVB é o id do banco. Pega o caso óbvio.
2. **pai do recorte** — todo sintético carrega `sintetico_de`. Um pai vazado põe
   o quadro julgado no treino recortado, e o canal 1 não veria: o id do filho é
   novo (`sint-…`).
3. **sha256** — a mesma imagem reexportada com outro nome. Cobre o que está
   materializado em disco (recortes + cache dos quadros cheios baixados do R2).
4. **dataset_role no banco** — todo id do RVB que entrou tem de ser `pool`.
   Fecha o caso em que o gabarito cresceu DEPOIS de o dataset ser montado.

O gabarito é a UNIÃO de três fontes (mais amplo = mais seguro): quem foi julgado
(`public.holdout_verdicts`), quem está marcado (`dataset_role='holdout'`) e quem
o COCO do A/B usou como prova.

USO
────────────────────────────────────────────────────────────────────────────────
    python3 scripts/ops/conferir_gabarito_fora.py autoteste
    DATABASE_URL=... python3 scripts/ops/conferir_gabarito_fora.py \\
        --dataset /dados/dataset-v2-multiescala --holdout /dados/ab/holdout

Sai 0 se os quatro canais derem ZERO. Qualquer outro resultado é 1 — e o
disparo não deve acontecer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
SPLITS = ("train", "val", "test")
COCO_JSON = "_annotations.coco.json"
PREFIXO_SINTETICO = "sinteticos/"


def identidades_do_dataset(raiz: Path) -> tuple[set[str], set[str]]:
    """(ids de imagem do RVB/sintética, pais dos recortes sintéticos).

    A imagem PÚBLICA fica de fora de propósito: ela não vem de `training_frames`
    e não tem como ser um quadro do gabarito — incluí-la só geraria ruído no
    canal 4, que pergunta ao banco pelo papel de cada id.
    """
    ids: set[str] = set()
    pais: set[str] = set()
    for split in SPLITS:
        coco = json.loads((raiz / split / COCO_JSON).read_text(encoding="utf-8"))
        for img in coco["images"]:
            nome = str(img["file_name"])
            if nome.startswith(PREFIXO_SINTETICO):
                ids.add(Path(nome).stem)
                pais.add(str(img["sintetico_de"]))
            elif "/" not in nome:
                ids.add(Path(nome).stem)
    return ids, pais


def colisoes(
    gabarito: set[str], ids: set[str], pais: set[str],
    sha_gabarito: set[str], sha_dataset: set[str],
) -> dict[str, list[str]]:
    """Os três canais que não dependem do banco. Puro — é o que o autoteste exercita."""
    return {
        "por_id": sorted(ids & gabarito),
        "por_pai": sorted(pais & gabarito),
        "por_sha256": sorted(sha_gabarito & sha_dataset),
    }


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def conferir(raiz: Path, holdout: Path, dsn: str, tenant: str) -> int:
    import psycopg2  # noqa: PLC0415 — só o caminho com banco precisa
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415

    con = psycopg2.connect(dsn)
    cur = con.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT DISTINCT frame_id::text AS f FROM public.holdout_verdicts "
        "WHERE tenant_id = %s", (tenant,))
    julgados = {r["f"] for r in cur.fetchall()}
    cur.execute(
        "SELECT id::text AS f FROM training_frames "
        "WHERE tenant_id = %s AND dataset_role = 'holdout'", (tenant,))
    marcados = {r["f"] for r in cur.fetchall()}
    coco_h = json.loads((holdout / COCO_JSON).read_text(encoding="utf-8"))
    do_ab = {str(i["frame_id"]) for i in coco_h["images"] if i.get("frame_id")}
    gabarito = julgados | marcados | do_ab
    print(f"gabarito: julgados={len(julgados)} · marcados={len(marcados)} · "
          f"COCO do A/B={len(do_ab)} · união={len(gabarito)}")

    ids, pais = identidades_do_dataset(raiz)
    arquivos = sorted((raiz / "sinteticos").glob("*.jpg")) + \
        sorted((raiz / ".cache-r2").glob("*.jpg"))
    achados = colisoes(
        gabarito, ids, pais,
        {_sha(p) for p in sorted(holdout.glob("*.jpg"))},
        {_sha(p) for p in arquivos},
    )
    print(f"dataset: {len(ids)} imagens do banco/sintéticas · {len(pais)} pais de recorte "
          f"· {len(arquivos)} arquivos materializados em disco")
    print(f"  [1] frame_id no gabarito : {len(achados['por_id'])} {achados['por_id'][:3]}")
    print(f"  [2] pai no gabarito      : {len(achados['por_pai'])} {achados['por_pai'][:3]}")
    print(f"  [3] sha256 coincidente   : {len(achados['por_sha256'])} "
          f"{achados['por_sha256'][:1]}")

    do_banco = sorted(i for i in ids if not i.startswith("sint-"))
    cur.execute(
        "SELECT dataset_role, count(*) AS n FROM training_frames "
        "WHERE tenant_id = %s AND id = ANY(%s::uuid[]) GROUP BY 1", (tenant, do_banco))
    papeis: dict[str, Any] = {r["dataset_role"]: r["n"] for r in cur.fetchall()}
    print(f"  [4] dataset_role dos ids : {papeis}")

    limpo = not any(achados.values()) and set(papeis) <= {"pool"}
    print("\n" + ("✅ GABARITO AUSENTE do dataset — os quatro canais dão zero."
                 if limpo else
                 "⛔ VAZAMENTO — o A/B seria mentira. NÃO DISPARE O TREINO."))
    return 0 if limpo else 1


def autoteste() -> int:
    """Leak PLANTADO em cada canal, um por vez. Um canal que para de olhar não
    dá erro — dá 'zero colisões', que é o resultado que se quer ver."""
    g = {"quadro-julgado"}
    assert colisoes(g, {"a"}, {"b"}, {"h1"}, {"h2"}) == {
        "por_id": [], "por_pai": [], "por_sha256": []}
    assert colisoes(g, {"quadro-julgado"}, set(), set(), set())["por_id"] == ["quadro-julgado"]
    assert colisoes(g, set(), {"quadro-julgado"}, set(), set())["por_pai"] == ["quadro-julgado"]
    assert colisoes(g, set(), set(), {"h"}, {"h"})["por_sha256"] == ["h"]
    print("autoteste OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("comando", nargs="?", default="conferir",
                    choices=["conferir", "autoteste"])
    ap.add_argument("--dataset", type=Path, help="raiz do dataset gravado")
    ap.add_argument("--holdout", type=Path,
                    help="pasta do holdout do A/B (imagens + _annotations.coco.json)")
    ap.add_argument("--tenant", default=TENANT_RVB)
    args = ap.parse_args(argv)
    if args.comando == "autoteste":
        return autoteste()
    if not (args.dataset and args.holdout):
        raise SystemExit("--dataset e --holdout são obrigatórios")
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise SystemExit("DATABASE_URL não definida — sem banco não há canais 1, 2 e 4.")
    return conferir(args.dataset, args.holdout, dsn, args.tenant)


if __name__ == "__main__":
    sys.exit(main())
