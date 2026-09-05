#!/usr/bin/env python3
"""Mede o tamanho REAL das caixas do pool de export, em pixels absolutos.

Responde três perguntas, com número, antes de mexer em resolução ou augmentation:

  1. Que fração das nossas caixas é SMALL no critério COCO (área < 32²=1024 px²)?
  2. Os frames anotados são recorte de pessoa ou frame cheio do NVR? Em que proporção?
  3. Depois do resize de entrada do detector, quantos pixels sobram do objeto?

O pool é o MESMO de `versioning_v2.py` (`_snapshot_labeled_frames` +
`_fetch_annotations` + `_e_rotulo_de_frame`): tenant+módulo, is_annotated,
curation_status != 'excluida', classe tenant não arquivada, procedência humana
(source='manual' OU reviewed_by), e sem os rótulos de frame [0,0,1,1] (área
normalizada >= 0.95). Medir fora desse recorte dá um número que o treino nunca vê.

⚠️ O RESIZE NÃO É O QUE `IMGSZ` DIZ. O rfdetr 1.5.2 monta o pipeline de treino em
`datasets/coco.py` com `multi_scale=True` e `expanded_scales=True` (defaults de
`TrainConfig`), e passa `skip_random_resize=not do_random_resize_via_padding` —
que com o default `False` vira `True`, e `scales = [scales[-1]]` (coco.py:465-471).
Ou seja: o treino usa SÓ A MAIOR escala do leque, 840 para IMGSZ=560, e o
val/test/ONNX usa 560. Por isso este script reporta as duas.

Uso:
    DATABASE_URL=... python3 scripts/ops/medir_objeto_pequeno.py
    DATABASE_URL=... python3 scripts/ops/medir_objeto_pequeno.py --tenant <uuid> --modulo epi
    python3 scripts/ops/medir_objeto_pequeno.py --self-check   # sem banco
"""

from __future__ import annotations

import argparse
import os
import sys

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

# Critério COCO, em px² de área absoluta.
COCO_SMALL = 32 * 32  # 1024
COCO_MEDIUM = 96 * 96  # 9216

# Área normalizada a partir da qual a caixa é rótulo de frame, não localização.
# Espelha versioning_v2.py::_AREA_ROTULO_DE_FRAME — se mudar lá, muda aqui.
AREA_ROTULO_DE_FRAME = 0.95

# Uma dimensão w×h repetida por >= este número de frames é resolução de sensor
# (frame cheio); dimensão quase-única é recorte de pessoa, que sai com o
# tamanho da caixa da pessoa + margem (person_detector.py::crop_person).
# ponytail: heurística por repetição — training_frames.source diz 'nvr' para os
# dois domínios (medido: 100% do pool), então a coluna não serve de discriminador.
# Se um dia a ingestão gravar a origem de verdade, troque por ela.
MIN_FRAMES_POR_DIM_CANONICA = 5

SQL = """
SELECT a.class_name,
       tf.id AS frame_id,
       tf.width  AS fw,
       tf.height AS fh,
       a.width  * tf.width  AS bw,
       a.height * tf.height AS bh
  FROM frame_annotations a
  JOIN training_frames tf ON tf.id = a.frame_id
  LEFT JOIN yolo_classes c
    ON a.class_id >= 100000
   AND c.id = a.class_id - 100000
   AND c.tenant_id = tf.tenant_id
 WHERE tf.tenant_id = %s
   AND tf.module_code = %s
   AND tf.is_annotated = TRUE
   AND tf.curation_status != 'excluida'
   AND (a.class_id < 100000 OR (c.id IS NOT NULL AND c.archived_at IS NULL))
   AND (a.source = 'manual' OR a.reviewed_by IS NOT NULL)
   AND a.width * a.height < %s
"""


def escalas_de_treino_rfdetr(
    resolution: int, expanded_scales: bool, patch_size: int, num_windows: int
) -> list[int]:
    """Cópia fiel de rfdetr 1.5.2 `datasets/coco.py::compute_multi_scale_scales`.

    Reproduzida aqui (em vez de importada) porque o rfdetr só existe no pod de
    treino — importar puxaria torch para um script de medição.
    """
    base = resolution // (patch_size * num_windows)
    offsets = (
        [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
        if expanded_scales
        else [-3, -2, -1, 0, 1, 2, 3, 4]
    )
    proposta = [(base + o) * patch_size * num_windows for o in offsets]
    return [s for s in proposta if s >= patch_size * num_windows * 2]


def resolucao_efetiva_de_treino(imgsz: int, patch_size: int = 14, num_windows: int = 4) -> int:
    """A resolução que o treino REALMENTE usa — a maior do leque, não `imgsz`.

    `RFDETRBase` é patch_size=14, num_windows=4 (config.py::RFDETRBaseConfig).
    """
    resolution = max(56, round(imgsz / 56) * 56)  # remote_train.py:424
    return escalas_de_treino_rfdetr(resolution, True, patch_size, num_windows)[-1]


def apos_resize(bw: float, bh: float, fw: int, fh: int, lado: int) -> tuple[float, float]:
    """Caixa depois do resize QUADRADO do rfdetr (A.Resize h=s w=s — distorce aspecto).

    Não é letterbox: cada eixo escala pelo seu próprio fator. Um recorte em
    retrato (mediana 349×473) é ESTICADO na horizontal ao virar 560×560 — o
    objeto ganha pixels, não perde. Frame cheio 1920×1080 encolhe nos dois eixos.
    """
    return bw * lado / fw, bh * lado / fh


def classe_coco(area_px: float) -> str:
    if area_px < COCO_SMALL:
        return "S"
    return "M" if area_px < COCO_MEDIUM else "L"


def _pct(parte: int, total: int) -> str:
    return f"{100.0 * parte / total:5.1f}%" if total else "    n/a"


def _p(valores: list[float], q: float) -> float:
    """Percentil por interpolação linear (mesma convenção do percentile_cont)."""
    if not valores:
        return 0.0
    ordenado = sorted(valores)
    pos = q * (len(ordenado) - 1)
    baixo = int(pos)
    alto = min(baixo + 1, len(ordenado) - 1)
    return ordenado[baixo] + (ordenado[alto] - ordenado[baixo]) * (pos - baixo)


def _par(grupo: list[dict], chave: str, q: float) -> str:
    """'larguraxaltura' no percentil q das caixas já redimensionadas."""
    return (f"{_p([r[chave][0] for r in grupo], q):.0f}"
            f"×{_p([r[chave][1] for r in grupo], q):.0f}")


def relatorio(linhas: list[dict], lado_val: int, lado_treino: int) -> None:
    total = len(linhas)
    if not total:
        print("pool vazio — nada a medir.")
        return

    # Domínio: dimensão de frame repetida por muitos frames = resolução de sensor.
    por_dim: dict[tuple[int, int], set] = {}
    for r in linhas:
        por_dim.setdefault((r["fw"], r["fh"]), set()).add(r["frame_id"])
    canonicas = {d for d, ids in por_dim.items() if len(ids) >= MIN_FRAMES_POR_DIM_CANONICA}
    for r in linhas:
        r["dominio"] = "FRAME_CHEIO" if (r["fw"], r["fh"]) in canonicas else "RECORTE"
        r["area_px"] = r["bw"] * r["bh"]
        r["v"] = apos_resize(r["bw"], r["bh"], r["fw"], r["fh"], lado_val)
        r["t"] = apos_resize(r["bw"], r["bh"], r["fw"], r["fh"], lado_treino)

    print(f"\nPOOL: {total} caixas em {len({r['frame_id'] for r in linhas})} frames\n")

    print("1) TAMANHO NATIVO — critério COCO (S<1024px², M<9216px², L acima)")
    print(f"{'classe':<26}{'n':>6}{'S':>7}{'M':>7}{'L':>7}{'%S':>8}{'lado_p50':>10}")
    classes = sorted({r["class_name"] for r in linhas},
                     key=lambda c: -sum(1 for r in linhas if r["class_name"] == c))
    for c in classes:
        g = [r for r in linhas if r["class_name"] == c]
        cont = {k: sum(1 for r in g if classe_coco(r["area_px"]) == k) for k in "SML"}
        lado = _p([r["area_px"] ** 0.5 for r in g], 0.5)
        print(f"{c:<26}{len(g):>6}{cont['S']:>7}{cont['M']:>7}{cont['L']:>7}"
              f"{_pct(cont['S'], len(g)):>8}{lado:>10.1f}")
    s_total = sum(1 for r in linhas if classe_coco(r["area_px"]) == "S")
    print(f"{'TOTAL':<26}{total:>6}{s_total:>7}{'':>7}{'':>7}{_pct(s_total, total):>8}")

    print("\n2) DOMÍNIO DO FRAME")
    print(f"{'domínio':<14}{'caixas':>8}{'frames':>8}{'w×h_p50':>12}{'fator_w':>9}"
          f"{f'p50@{lado_val}':>12}{f'p10@{lado_val}':>12}{'%S_depois':>11}")
    for dom in ("RECORTE", "FRAME_CHEIO"):
        g = [r for r in linhas if r["dominio"] == dom]
        if not g:
            continue
        s_dep = sum(1 for r in g if r["v"][0] * r["v"][1] < COCO_SMALL)
        frame_p50 = f"{_p([r['fw'] for r in g], 0.5):.0f}×{_p([r['fh'] for r in g], 0.5):.0f}"
        depois_50 = _par(g, "v", 0.5)
        depois_10 = _par(g, "v", 0.1)
        print(f"{dom:<14}{len(g):>8}{len({r['frame_id'] for r in g}):>8}{frame_p50:>12}"
              f"{_p([lado_val / r['fw'] for r in g], 0.5):>9.2f}"
              f"{depois_50:>12}{depois_10:>12}{_pct(s_dep, len(g)):>11}")

    print(f"\n3) PIXELS APÓS RESIZE  (val/ONNX={lado_val}²  ·  treino real={lado_treino}²)")
    print(f"{'classe':<26}{'n':>6}{'p50_val':>11}{'p10_val':>11}{'p50_trn':>11}{'p10_trn':>11}")
    for c in classes:
        g = [r for r in linhas if r["class_name"] == c]
        print(f"{c:<26}{len(g):>6}{_par(g, 'v', 0.5):>11}{_par(g, 'v', 0.1):>11}"
              f"{_par(g, 't', 0.5):>11}{_par(g, 't', 0.1):>11}")


def self_check() -> None:
    # A escala de treino real do nosso dispatch: IMGSZ=560 → 840, não 560.
    assert escalas_de_treino_rfdetr(560, True, 14, 4) == [
        280, 336, 392, 448, 504, 560, 616, 672, 728, 784, 840
    ]
    assert resolucao_efetiva_de_treino(560) == 840
    assert resolucao_efetiva_de_treino(616) == 896
    # Sem expanded_scales o leque é outro — a flag importa.
    assert escalas_de_treino_rfdetr(560, False, 14, 4)[-1] == 784
    # Resize quadrado: recorte retrato ESTICA na largura, frame cheio ENCOLHE.
    assert apos_resize(60, 60, 349, 473, 560) == (60 * 560 / 349, 60 * 560 / 473)
    assert apos_resize(60, 60, 349, 473, 560)[0] > 60          # recorte: ganha px
    assert apos_resize(60, 60, 1920, 1080, 560)[0] < 60        # frame cheio: perde
    assert classe_coco(1023) == "S" and classe_coco(1024) == "M"
    assert classe_coco(9215) == "M" and classe_coco(9216) == "L"
    assert _p([1, 2, 3, 4], 0.5) == 2.5 and _p([1, 2, 3, 4], 0.0) == 1
    print("self-check ok")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default=TENANT_RVB)
    ap.add_argument("--modulo", default="epi")
    ap.add_argument("--imgsz", type=int, default=560, help="IMGSZ do dispatch (remote_train.py)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return 0

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 1

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL, (args.tenant, args.modulo, AREA_ROTULO_DE_FRAME))
            linhas = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    lado_val = max(56, round(args.imgsz / 56) * 56)
    relatorio(linhas, lado_val, resolucao_efetiva_de_treino(args.imgsz))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
