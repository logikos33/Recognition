#!/usr/bin/env python3
"""converter_variante_c.py — VARIANTE C: parte-do-corpo + EPI, ausência por sobreposição.

A ideia (do dono): uma anotação de AUSÊNCIA marca, na prática, uma PARTE DO CORPO
DESPROTEGIDA. Se ela virar detecção de coisa VISÍVEL, a violação sai depois, por
geometria: parte detectada SEM o EPI correspondente sobreposto = violação.

    Variante A  presença (5 classes), ausência derivada do recorte de pessoa
    Variante B  presença + "Sem X" como classe do detector
    Variante C  parte do corpo + EPI; ausência = parte sem EPI sobreposto   ← aqui

⛔ NÃO ALTERA NENHUMA ANOTAÇÃO ORIGINAL. Este script lê o COCO **já exportado**
pelo produto e escreve um COCO NOVO noutro diretório. O banco não é tocado no
modo `coco` — nem para leitura. O dado do cliente é intocável.

Por que a entrada é o COCO do produto e não o banco: o export
(`app/infrastructure/queue/tasks/versioning_v2.py`) já aplica os filtros de
proveniência, o descarte de rótulo-de-frame (:254), o split por grupo sem
leakage (`_group_key`) e o esvaziamento de frame. Reimplementar isso aqui daria
uma prova DIFERENTE da que A e B veem — e o A/B só vale sobre o MESMO holdout.
Convertendo o COCO, C herda exatamente o mesmo recorte de dado.

    # ver o que mudaria (padrão — não escreve nada)
    python3 scripts/ops/converter_variante_c.py coco --entrada /dados/rvb/v15-tudo

    # gravar
    python3 scripts/ops/converter_variante_c.py coco \\
        --entrada /dados/rvb/v15-tudo --saida /dados/rvb/v15-variante-c --gravar

    # amostra visual para o dono validar o remapeamento a olho
    DATABASE_URL=postgresql://... python3 scripts/ops/converter_variante_c.py \\
        amostra --saida docs/quality/AMOSTRA-VARIANTE-C.html

    # autoteste (não precisa de banco nem de dataset)
    python3 scripts/ops/converter_variante_c.py autoteste

────────────────────────────────────────────────────────────────────────────────
O MAPEAMENTO, E POR QUE ELE NÃO É O QUE FOI PEDIDO

Medido no RVB em 2026-09-02 (as queries estão no relatório da tarefa e no HTML
da amostra). Três achados mudaram o desenho proposto:

1. A caixa de ausência TEM a geometria do EPI que falta — não a da pessoa.
   KS de 2 amostras (área da caixa) entre ausência e a presença PAR: D entre
   0,135 e 0,225. Contra uma classe ERRADA (controle): D entre 0,405 e 0,882.
   Ou seja: "Sem Luvas" tem o tamanho de uma luva, não o de um tronco. A ideia
   se sustenta geometricamente.

2. "rosto" NÃO fecha. O pedido era "Sem mascara"→rosto e "Sem Óculos"→rosto.
   As duas regiões são geometricamente DISTINTAS (KS na razão de aspecto entre
   elas: D=0,518 — maior que qualquer par ausência↔presença correto), e em 63
   frames as duas caixas existem no MESMO rosto com IoU médio 0,078. Colapsar
   as duas em "rosto" cria uma classe bimodal e dois alvos para uma cara só.
   Então as partes ficam separadas: `regiao_olhos` e `regiao_boca_nariz`.

3. A conversão precisa valer também para a PRESENÇA, senão é a variante B com
   outro nome. Presença e ausência do mesmo EPI quase nunca coexistem
   (Sem Luvas ∩ Luvas = 0 frames de 122/204; Sem Óculos ∩ Óculos = 0 de
   111/512). Se só a ausência virar `mao`, `mao` passa a significar "mão nua" e
   "mão sem luva sobreposta" vira tautologia. Por isso `Luvas` também emite
   `mao` — a caixa da luva marca a mesma mão (KS D_área=0,146 entre elas).

"Uso incorreto de mascara": NÃO vira ausência. A máscara ESTÁ lá, mal usada.
Se virasse só `regiao_boca_nariz`, a derivação por sobreposição a leria como
violação genérica de "sem máscara" e o produto perderia a distinção que o
cliente pediu; se virasse `mascara`, viraria conformidade — 222 falsos
negativos. Fica como EPI próprio (`mascara_incorreta`) sobre a mesma região,
e a derivação passa a ter três estados: com máscara / com máscara incorreta /
sem nada.

"Botas": segue classe de presença pura. Não há parte "pé" anotada e "Sem botas"
tem n=1 — não dá para derivar ausência de calçado.

"pessoa": ZERO anotações no RVB (medido: nenhuma classe de parte do corpo ou de
pessoa existe em frame_annotations do tenant). A classe `pessoa` do desenho SH17
só poderia vir de pseudo-rótulo do estágio 1 — a mesma origem que o A/B do v11
mediu como PIOR (IoU 0,67 contra 0,84; versioning_v2.py:196-200). Este script
não a inventa.

CAIXAS FULL-FRAME: FICAM DE FORA. São o placeholder [0,0,1,1] da aba Classificar
(veredito de cena, não localização) — 494 das 1.656 caixas de ausência do RVB
(29,8%): Sem Luvas 183, Sem mascara 158, Sem Óculos 95, Uso incorreto 31,
Sem protetor 27.
Convertê-las diria que "mão" é o quadro inteiro. O export do produto já as
descarta (versioning_v2.py:_e_rotulo_de_frame, :254); o filtro é repetido aqui
porque um COCO montado à mão pode trazê-las de volta, e o script CONTA quantas
tirou em vez de fingir que não existiam.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

# ── Taxonomia ────────────────────────────────────────────────────────────────
#: Categoria âncora id:0 do COCO do produto (versioning_v2.py:41). Sem ela o
#: RF-DETR treina com o espaço de classes deslocado de 1.
ANCORA = "recognition"

#: Área (fração do frame) a partir da qual a caixa é rótulo de cena, não alvo.
#: Mesmo valor de versioning_v2.py:_AREA_ROTULO_DE_FRAME.
AREA_ROTULO_DE_FRAME = 0.95

#: classe RVB → classes da variante C que aquela MESMA caixa passa a emitir.
#: Uma caixa de EPI vira DUAS: a parte do corpo que ela cobre e o EPI em si.
MAPA: dict[str, tuple[str, ...]] = {
    "Sem Luvas": ("mao",),
    "Luvas": ("mao", "luva"),
    "Sem protetor de ouvido": ("orelha",),
    "Protetor auditivo": ("orelha", "protetor_auricular"),
    "Sem Óculos": ("regiao_olhos",),
    "Óculos": ("regiao_olhos", "oculos"),
    "Sem mascara": ("regiao_boca_nariz",),
    "mascara": ("regiao_boca_nariz", "mascara"),
    "Uso incorreto de mascara": ("regiao_boca_nariz", "mascara_incorreta"),
    "Botas": ("botas",),
}

#: parte do corpo → EPI que a protege. É ISTO que a derivação por sobreposição
#: consulta em inferência: parte sem nenhum destes sobreposto = violação.
PROTEGE: dict[str, tuple[str, ...]] = {
    "mao": ("luva",),
    "orelha": ("protetor_auricular",),
    "regiao_olhos": ("oculos",),
    "regiao_boca_nariz": ("mascara", "mascara_incorreta"),
}

#: fora do mapa de propósito, com o motivo — some do dataset e é CONTADO.
FORA = {
    "Capacete": "n=3, abaixo de qualquer n mínimo",
    "Sem Capacete": "n=1",
    "Sem botas": "n=1 — não sustenta a parte 'pé'",
    "incluir blur": "não é classe de objeto",
}

CLASSES = sorted({c for destinos in MAPA.values() for c in destinos})


# ── Conversão (a única lógica; os dois modos abaixo só fazem I/O) ─────────────
def converter(
    anotacoes: list[dict], area_imagem: dict[int, float]
) -> tuple[list[dict], dict[str, int]]:
    """COCO annotations da taxonomia RVB → taxonomia da variante C.

    `anotacoes` já vem com a chave 'class_name' resolvida. `area_imagem` mapeia
    image_id → largura*altura em pixels, para julgar o rótulo de frame.
    Devolve (anotações novas, contadores).
    """
    saida: list[dict] = []
    contas = {"entrada": len(anotacoes), "full_frame": 0, "fora_do_mapa": 0, "emitidas": 0}
    proximo_id = 1
    for ann in anotacoes:
        nome = ann["class_name"]
        area_img = area_imagem.get(ann["image_id"], 0.0)
        _, _, w, h = ann["bbox"]
        if area_img > 0 and (w * h) / area_img >= AREA_ROTULO_DE_FRAME:
            contas["full_frame"] += 1
            continue
        destinos = MAPA.get(nome)
        if not destinos:
            contas["fora_do_mapa"] += 1
            continue
        for destino in destinos:
            saida.append(
                {
                    "id": proximo_id,
                    "image_id": ann["image_id"],
                    "category_id": CLASSES.index(destino) + 1,  # +1: id 0 é a âncora
                    "bbox": list(ann["bbox"]),
                    "area": round(w * h, 2),
                    "iscrowd": 0,
                }
            )
            proximo_id += 1
            contas["emitidas"] += 1
    return saida, contas


def categorias() -> list[dict]:
    """Categorias COCO da variante C, com a âncora id:0 do produto."""
    return [{"id": 0, "name": ANCORA, "supercategory": "none"}] + [
        {"id": i + 1, "name": c, "supercategory": ANCORA} for i, c in enumerate(CLASSES)
    ]


# ── Modo `coco` ──────────────────────────────────────────────────────────────
def modo_coco(entrada: Path, saida: Path | None, gravar: bool) -> int:
    splits = [p for p in ("train", "val", "test") if (entrada / p / "_annotations.coco.json").is_file()]
    if not splits:
        print(f"ERRO: nenhum <split>/_annotations.coco.json em {entrada}")
        return 1
    total: dict[str, int] = {}
    por_classe: dict[str, int] = {}
    for split in splits:
        doc = json.loads((entrada / split / "_annotations.coco.json").read_text())
        nome_por_cat = {c["id"]: c["name"] for c in doc.get("categories", [])}
        area_img = {img["id"]: float(img["width"]) * float(img["height"]) for img in doc["images"]}
        anns = [
            {**a, "class_name": nome_por_cat.get(a["category_id"], "")}
            for a in doc.get("annotations", [])
        ]
        novas, contas = converter(anns, area_img)
        for k, v in contas.items():
            total[k] = total.get(k, 0) + v
        for a in novas:
            nome = CLASSES[a["category_id"] - 1]
            por_classe[nome] = por_classe.get(nome, 0) + 1
        print(
            f"  {split:5} imagens={len(doc['images']):5d} "
            f"entrada={contas['entrada']:5d} full_frame={contas['full_frame']:4d} "
            f"fora_do_mapa={contas['fora_do_mapa']:4d} emitidas={contas['emitidas']:5d}"
        )
        if gravar and saida:
            destino = saida / split
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "_annotations.coco.json").write_text(
                json.dumps(
                    {
                        "info": {"description": "Recognition variante C (parte do corpo + EPI)"},
                        "licenses": [],
                        "categories": categorias(),
                        "images": doc["images"],
                        "annotations": novas,
                    }
                )
            )
    print(f"\nTOTAL {total}")
    print("caixas por classe da variante C:")
    for nome in CLASSES:
        print(f"  {nome:20} {por_classe.get(nome, 0):6d}")
    if not gravar:
        print("\nDRY-RUN — nada foi escrito. Repita com --gravar --saida DIR.")
        print("As imagens NÃO são copiadas: aponte o treino para o mesmo diretório de imagens da entrada.")
    return 0


# ── Modo `amostra` ───────────────────────────────────────────────────────────
_SQL_AMOSTRA = """
WITH alvo AS (
  SELECT an.id, an.frame_id, an.class_name, an.x_center, an.y_center,
         an.width, an.height, an.source, f.width AS fw, f.height AS fh,
         f.r2_key, f.camera_id,
         row_number() OVER (PARTITION BY an.class_name ORDER BY an.id) AS rn
  FROM public.frame_annotations an
  JOIN public.training_frames f ON f.id = an.frame_id
  WHERE f.tenant_id = %(tenant)s
    AND an.width * an.height < %(area)s
    AND an.class_name = ANY(%(classes)s)
)
SELECT * FROM alvo WHERE rn <= %(por_classe)s ORDER BY class_name, rn
"""

_SQL_VIZINHAS = """
SELECT an.frame_id, an.class_name, an.x_center, an.y_center, an.width, an.height
FROM public.frame_annotations an
WHERE an.frame_id = ANY(%(frames)s::uuid[]) AND an.width * an.height < %(area)s
"""


def modo_amostra(saida: Path, tenant: str, por_classe: int) -> int:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - ambiente
        print(f"ERRO: {exc} — pip install psycopg2-binary")
        return 1
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERRO: DATABASE_URL não definida.")
        return 1
    classes = [c for c in MAPA if c.startswith("Sem ") or c.startswith("Uso ")]
    params = {
        "tenant": tenant,
        "area": AREA_ROTULO_DE_FRAME,
        "classes": classes,
        "por_classe": por_classe,
    }
    with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(_SQL_AMOSTRA, params)
        alvos = [dict(r) for r in cur.fetchall()]
        cur.execute(
            _SQL_VIZINHAS,
            {"frames": [a["frame_id"] for a in alvos], "area": AREA_ROTULO_DE_FRAME},
        )
        vizinhas = [dict(r) for r in cur.fetchall()]
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(_html_amostra(alvos, vizinhas))
    print(f"amostra: {len(alvos)} exemplos → {saida}")
    return 0


def _caixa_svg(a: dict, fw: int, fh: int, cor: str, rotulo: str, traco: str = "") -> str:
    """Caixa em coordenadas de PIXEL do quadro — a proporção tem de ser a real.

    O viewBox é o quadro inteiro em pixels, então uma caixa quadrada aparece
    quadrada. Normalizar para 100×100 achataria justamente o que se quer
    conferir a olho (proporção de uma mão, de uma banda de óculos).
    """
    x = (float(a["x_center"]) - float(a["width"]) / 2) * fw
    y = (float(a["y_center"]) - float(a["height"]) / 2) * fh
    w, h = float(a["width"]) * fw, float(a["height"]) * fh
    esc, fonte = max(fw, fh) / 100, max(fw, fh) / 28
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="none" stroke="{cor}" stroke-width="{0.7 * esc:.2f}" {traco}/>'
        f'<text x="{x:.1f}" y="{max(y - 1.2 * esc, fonte):.1f}" fill="{cor}" '
        f'font-size="{fonte:.1f}">{html.escape(rotulo)}</text>'
    )


def _html_amostra(alvos: list[dict], vizinhas: list[dict]) -> str:
    por_frame: dict[str, list[dict]] = {}
    for v in vizinhas:
        por_frame.setdefault(str(v["frame_id"]), []).append(v)
    cartoes = []
    for a in alvos:
        destinos = MAPA[a["class_name"]]
        parte = destinos[0]
        epi_extra = destinos[1] if len(destinos) > 1 else None
        irmas = [
            v for v in por_frame.get(str(a["frame_id"]), [])
            if not (
                abs(float(v["x_center"]) - float(a["x_center"])) < 1e-9
                and abs(float(v["width"]) - float(a["width"])) < 1e-9
            )
        ]
        fw, fh = int(a["fw"]), int(a["fh"])
        tracejado = f'stroke-dasharray="{1.5 * max(fw, fh) / 100:.2f}"'
        svg = "".join(
            _caixa_svg(v, fw, fh, "#8a8a8a", v["class_name"], tracejado) for v in irmas
        ) + _caixa_svg(a, fw, fh, "#d92b2b", a["class_name"], "")
        px_w = float(a["width"]) * fw
        px_h = float(a["height"]) * fh
        cartoes.append(f"""
<figure class="c">
  <svg viewBox="0 0 {fw} {fh}" role="img"
       aria-label="caixa {html.escape(a['class_name'])} sobre o quadro">
    <rect x="0" y="0" width="{fw}" height="{fh}" fill="var(--quadro)" stroke="var(--borda)" stroke-width="{max(fw, fh) / 250:.2f}"/>
    {svg}
  </svg>
  <figcaption>
    <p class="de">{html.escape(a['class_name'])}</p>
    <p class="para">→ <b>{html.escape(parte)}</b>{
        f' + <b>{html.escape(epi_extra)}</b>' if epi_extra else ''}</p>
    <dl>
      <dt>frame</dt><dd><code>{html.escape(str(a['frame_id']))}</code></dd>
      <dt>quadro</dt><dd>{a['fw']}×{a['fh']} px</dd>
      <dt>caixa</dt><dd>{px_w:.0f}×{px_h:.0f} px &middot; área {float(a['width'])*float(a['height'])*100:.2f}% &middot; proporção {(px_w/px_h if px_h else 0):.2f}</dd>
      <dt>r2_key</dt><dd><code>{html.escape(str(a['r2_key'] or '—'))}</code></dd>
    </dl>
  </figcaption>
</figure>""")
    linhas_mapa = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{' + '.join(html.escape(d) for d in v)}</td></tr>"
        for k, v in MAPA.items()
    ) + "".join(
        f'<tr class="fora"><td>{html.escape(k)}</td><td>fora — {html.escape(m)}</td></tr>'
        for k, m in FORA.items()
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amostra Variante C</title>
<style>
:root {{ --fg:#1a1a1a; --fg2:#666; --bg:#faf9f7; --card:#fff; --borda:#d8d4cc;
        --quadro:#efece6; --acento:#d92b2b; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18; --borda:#3a382f;
  --quadro:#26241c; --acento:#ff6b5e; }} }}
:root[data-theme="dark"] {{ --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18;
  --borda:#3a382f; --quadro:#26241c; --acento:#ff6b5e; }}
body {{ background:var(--bg); color:var(--fg); margin:0; padding:2rem 1.25rem 4rem;
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1120px; margin:0 auto; }}
h1 {{ font-size:1.7rem; margin:0 0 .3rem; letter-spacing:-.02em; }}
.sub {{ color:var(--fg2); margin:0 0 1.5rem; max-width:62ch; }}
.aviso {{ border-left:3px solid var(--acento); background:var(--card); padding:.85rem 1rem;
  margin:0 0 2rem; border-radius:0 4px 4px 0; max-width:62ch; }}
.aviso b {{ color:var(--acento); }}
table {{ border-collapse:collapse; margin:0 0 2.5rem; font-size:.9rem; }}
th,td {{ text-align:left; padding:.32rem .9rem .32rem 0; border-bottom:1px solid var(--borda); }}
tr.fora td {{ color:var(--fg2); }}
.grid {{ display:grid; gap:1.1rem; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); }}
.c {{ margin:0; background:var(--card); border:1px solid var(--borda); border-radius:6px;
  overflow:hidden; }}
.c svg {{ display:block; width:100%; height:auto; background:var(--quadro); }}
figcaption {{ padding:.7rem .8rem .8rem; }}
.de {{ margin:0; font-size:.82rem; color:var(--fg2); }}
.para {{ margin:.1rem 0 .6rem; font-size:1rem; }}
dl {{ display:grid; grid-template-columns:auto 1fr; gap:.1rem .5rem; margin:0; font-size:.76rem; }}
dt {{ color:var(--fg2); }} dd {{ margin:0; overflow-wrap:anywhere; }}
code {{ font-size:.72rem; }}
</style></head><body>
<main>
<h1>Amostra — Variante C</h1>
<p class="sub">Cada cartão mostra UMA anotação de ausência do RVB e o rótulo de
parte-do-corpo que o remapeamento propõe para ela. O retângulo grande é o quadro
inteiro, na proporção real; a caixa vermelha é a anotação; as cinzas tracejadas
são as outras caixas do mesmo frame, para dar contexto espacial.</p>
<p class="aviso"><b>Sem a foto.</b> Esta sessão não tem credencial de R2, então
as imagens não foram baixadas — o desenho é esquemático, na posição e na escala
reais da caixa sobre o quadro. O <code>r2_key</code> de cada exemplo está no
cartão para quem tiver a credencial abrir a imagem e conferir a olho.</p>
<h2>Mapeamento</h2>
<table><thead><tr><th>classe RVB</th><th>variante C</th></tr></thead>
<tbody>{linhas_mapa}</tbody></table>
<h2>Exemplos ({len(alvos)})</h2>
<div class="grid">{''.join(cartoes)}</div>
</main></body></html>"""


# ── Autoteste ────────────────────────────────────────────────────────────────
def autoteste() -> int:
    area = {1: 1000.0 * 1000.0}
    anns = [
        {"image_id": 1, "bbox": [10, 10, 50, 50], "class_name": "Sem Luvas"},
        {"image_id": 1, "bbox": [10, 10, 50, 50], "class_name": "Luvas"},
        {"image_id": 1, "bbox": [0, 0, 1000, 1000], "class_name": "Sem Luvas"},  # full frame
        {"image_id": 1, "bbox": [10, 10, 50, 50], "class_name": "Capacete"},  # fora do mapa
        {"image_id": 1, "bbox": [10, 10, 50, 50], "class_name": "Uso incorreto de mascara"},
    ]
    novas, c = converter(anns, area)
    assert c == {"entrada": 5, "full_frame": 1, "fora_do_mapa": 1, "emitidas": 5}, c
    nomes = [CLASSES[a["category_id"] - 1] for a in novas]
    assert nomes == ["mao", "mao", "luva", "regiao_boca_nariz", "mascara_incorreta"], nomes
    # a caixa é copiada sem deformação
    assert all(a["bbox"] == [10, 10, 50, 50] for a in novas), novas
    # ids únicos e alinhados com as categorias
    assert len({a["id"] for a in novas}) == len(novas)
    cats = {c["name"]: c["id"] for c in categorias()}
    assert cats[ANCORA] == 0 and min(v for k, v in cats.items() if k != ANCORA) == 1
    assert all(CLASSES[cats[n] - 1] == n for n in CLASSES)
    # toda parte tem EPI que a protege, e todo EPI protetor existe como classe
    partes = set(PROTEGE)
    assert partes <= set(CLASSES), partes - set(CLASSES)
    for epis in PROTEGE.values():
        assert set(epis) <= set(CLASSES), epis
    # nenhuma caixa de ausência emite EPI (senão a derivação leria conformidade)
    for origem, destinos in MAPA.items():
        if origem.startswith("Sem "):
            assert all(d in PROTEGE for d in destinos), (origem, destinos)
    print("autoteste: OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="modo", required=True)
    c = sub.add_parser("coco", help="converte um COCO exportado (dry-run por padrão)")
    c.add_argument("--entrada", type=Path, required=True, help="dir com <split>/_annotations.coco.json")
    c.add_argument("--saida", type=Path, help="dir de destino (obrigatório com --gravar)")
    c.add_argument("--gravar", action="store_true", help="escreve de verdade")
    a = sub.add_parser("amostra", help="página HTML de validação a olho (lê o banco)")
    a.add_argument("--saida", type=Path, required=True)
    a.add_argument("--tenant", default="63c219d8-fbef-4f3c-a7c9-058c742482e2")
    a.add_argument("--por-classe", type=int, default=4)
    sub.add_parser("autoteste", help="checa a conversão sem banco nem dataset")
    args = p.parse_args()
    if args.modo == "autoteste":
        return autoteste()
    if args.modo == "amostra":
        return modo_amostra(args.saida, args.tenant, args.por_classe)
    if args.gravar and not args.saida:
        print("ERRO: --gravar exige --saida.")
        return 1
    if args.gravar and args.saida and args.saida.resolve() == args.entrada.resolve():
        print("ERRO: --saida não pode ser a --entrada (o dataset original é intocável).")
        return 1
    return modo_coco(args.entrada, args.saida, args.gravar)


if __name__ == "__main__":
    sys.exit(main())
