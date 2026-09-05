#!/usr/bin/env python3
"""Amostra VISUAL da variante C — 20 anotações de ausência do RVB, sobre a FOTO real.

É o gate humano da conversão: o dono olha 20 exemplos e aprova (ou não) o
remapeamento antes das 1.656 anotações de ausência do RVB serem convertidas —
na prática 1.162, porque as 494 de frame inteiro já ficam de fora.

Difere da amostra esquemática anterior em duas coisas que importam:

1. A FOTO. O esquema mostrava onde a caixa cai no quadro; só a foto mostra o que
   está DENTRO dela. É a foto que responde a pergunta — "a caixa de 'Sem mascara'
   marca o rosto ou o tronco?" — e a única que pode DERRUBAR a conversão.

2. A SELEÇÃO É ADVERSARIAL, não uma vitrine. De cada classe entram
   obrigatoriamente a MAIOR caixa, a MENOR e a de proporção mais estranha
   (|log(aspecto)| máximo). Se o remapeamento tem ponto fraco, é onde ele aparece.
   Só depois disso o resto das vagas é distribuído por proporção de volume, e
   sorteado com semente fixa dentro do miolo (IQR) — a amostra é reproduzível.

Só caixas LOCALIZADAS (área < 0,5). As de área ≥ 0,95 são veredito de cena da
aba Classificar (494 delas), não candidatas a virar parte do corpo; a
distribuição é bimodal, não há nada entre 0,5 e 0,95.

Credencial: lida do ambiente, nunca impressa, nunca escrita no HTML.

    export DATABASE_URL=...
    eval "$(railway variables -s API-V3 -e Desenvolvimento --kv | grep ^R2_ | sed 's/^/export /')"
    python3 scripts/ops/amostra_variante_c_fotos.py --saida docs/quality/AMOSTRA-VARIANTE-C.html
    python3 scripts/ops/amostra_variante_c_fotos.py --autoteste
"""

from __future__ import annotations

import argparse
import base64
import io
import math
import os
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from converter_variante_c import MAPA  # noqa: E402

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

#: teto de área da caixa localizada. O corte real do produto é 0,95
#: (versioning_v2), mas entre 0,5 e 0,95 não existe NENHUMA caixa — a
#: distribuição é bimodal. 0,5 é o corte conservador e dá no mesmo conjunto.
AREA_LOCALIZADA = 0.5

#: as classes de ausência que a conversão vai tocar.
AUSENCIAS = [c for c in MAPA if c.startswith("Sem ") or c.startswith("Uso ")]

#: ausência → a classe de PRESENÇA correspondente. Ver as duas no mesmo frame é
#: o que mostra se a conversão faz sentido (mesma região do corpo?).
PAR_PRESENCA = {
    "Sem Luvas": "Luvas",
    "Sem protetor de ouvido": "Protetor auditivo",
    "Sem Óculos": "Óculos",
    "Sem mascara": "mascara",
    "Uso incorreto de mascara": "mascara",
}

SEMENTE = 20260902
TOTAL = 20
LARGURA_SAIDA = 800
JPEG_Q = 80

COR_ALVO = (217, 43, 43)
COR_PAR = (32, 160, 96)
COR_OUTRA = (150, 150, 150)

_SQL = """
SELECT an.id::text AS id, an.frame_id::text AS frame_id, an.class_name,
       an.x_center, an.y_center, an.width, an.height, an.source,
       f.width AS fw, f.height AS fh, f.r2_key,
       f.camera_id::text AS camera_id,
       COALESCE(f.captured_at, f.created_at) AS quando
FROM public.frame_annotations an
JOIN public.training_frames f ON f.id = an.frame_id
WHERE f.tenant_id = %(tenant)s
  AND an.class_name = ANY(%(classes)s)
  AND an.width * an.height < %(area)s
  AND f.r2_key IS NOT NULL
ORDER BY an.id
"""

_SQL_VIZINHAS = """
SELECT an.frame_id::text AS frame_id, an.id::text AS id, an.class_name,
       an.x_center, an.y_center, an.width, an.height
FROM public.frame_annotations an
WHERE an.frame_id = ANY(%(frames)s::uuid[])
  AND an.width * an.height < %(area)s
"""


# ── Seleção (a única lógica com risco; o resto é I/O) ─────────────────────────
def selecionar(linhas: list[dict], total: int = TOTAL) -> list[dict]:
    """Escolhe ~`total` exemplos: casos difíceis primeiro, resto proporcional.

    Por classe, em ordem: MAIOR área, MENOR área, proporção mais extrema.
    As vagas que sobram vão para as classes por volume (maior resto), sorteadas
    com semente fixa dentro do IQR de área — o "típico", para contraste.
    """
    por_classe: dict[str, list[dict]] = {}
    for r in linhas:
        por_classe.setdefault(r["class_name"], []).append(r)

    escolhidos: list[dict] = []
    vistos: set[str] = set()

    def marcar(r: dict, motivo: str) -> None:
        if r["id"] in vistos:
            return
        vistos.add(r["id"])
        escolhidos.append({**r, "motivo": motivo})

    for classe in sorted(por_classe):
        grupo = sorted(por_classe[classe], key=lambda r: (_area(r), r["id"]))
        marcar(grupo[-1], "maior caixa da classe")
        marcar(grupo[0], "menor caixa da classe")
        extremo = max(grupo, key=lambda r: (abs(math.log(_aspecto(r))), r["id"]))
        marcar(extremo, "proporção mais extrema da classe")

    # vagas restantes por volume (maior resto), o "típico" de cada classe
    sobra = total - len(escolhidos)
    if sobra > 0:
        n_total = sum(len(v) for v in por_classe.values())
        quotas = sorted(
            ((len(v) * sobra / n_total, c) for c, v in por_classe.items()), reverse=True
        )
        rng = random.Random(SEMENTE)
        restantes = sobra
        for _, classe in quotas:
            if restantes <= 0:
                break
            grupo = sorted(por_classe[classe], key=lambda r: (_area(r), r["id"]))
            miolo = [r for r in grupo[len(grupo) // 4 : 3 * len(grupo) // 4 + 1] if r["id"] not in vistos]
            if not miolo:
                continue
            marcar(rng.choice(miolo), "típico (miolo da distribuição)")
            restantes -= 1

    escolhidos.sort(key=lambda r: (r["class_name"], _area(r)))
    return escolhidos


def _area(r: dict) -> float:
    return float(r["width"]) * float(r["height"])


def _aspecto(r: dict) -> float:
    """Aspecto em PIXEL, não em fração — 0,1×0,1 num 16:9 não é quadrado."""
    fw = float(r.get("fw") or 16)
    fh = float(r.get("fh") or 9)
    return max((float(r["width"]) * fw) / max(float(r["height"]) * fh, 1e-9), 1e-9)


# ── Imagem ───────────────────────────────────────────────────────────────────
def _cliente_r2():
    import boto3
    from botocore.config import Config

    faltando = [k for k in ("R2_ENDPOINT", "R2_KEY", "R2_SECRET", "R2_BUCKET") if not os.environ.get(k)]
    if faltando:
        raise RuntimeError(f"faltam no ambiente: {', '.join(faltando)}")
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _fonte(px: int):
    from PIL import ImageFont

    for caminho in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(caminho).exists():
            try:
                return ImageFont.truetype(caminho, px)
            except OSError:
                continue
    return ImageFont.load_default()


def desenhar(bruto: bytes, alvo: dict, vizinhas: list[dict]) -> tuple[str, int, int]:
    """Redimensiona para LARGURA_SAIDA, desenha as caixas, devolve data URI."""
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(bruto)).convert("RGB")
    orig_w, orig_h = img.size
    # sobe TAMBÉM os pequenos: metade dos frames do RVB são recortes de pessoa
    # (170–800 px). O navegador ia esticá-los de qualquer jeito pela coluna do
    # grid; subindo aqui, o traço e o rótulo ficam proporcionais e legíveis.
    img = img.resize(
        (LARGURA_SAIDA, max(1, round(img.height * LARGURA_SAIDA / img.width))), Image.LANCZOS
    )
    w, h = img.size
    d = ImageDraw.Draw(img)
    fonte = _fonte(max(13, w // 48))
    traco = max(2, w // 300)
    par = PAR_PRESENCA.get(alvo["class_name"])

    def caixa(a: dict, cor, rotulo: str, tracejado: bool) -> None:
        x0 = (float(a["x_center"]) - float(a["width"]) / 2) * w
        y0 = (float(a["y_center"]) - float(a["height"]) / 2) * h
        x1 = x0 + float(a["width"]) * w
        y1 = y0 + float(a["height"]) * h
        if tracejado:
            for i in range(0, int(x1 - x0), 12):
                d.line([x0 + i, y0, min(x0 + i + 6, x1), y0], fill=cor, width=traco)
                d.line([x0 + i, y1, min(x0 + i + 6, x1), y1], fill=cor, width=traco)
            for i in range(0, int(y1 - y0), 12):
                d.line([x0, y0 + i, x0, min(y0 + i + 6, y1)], fill=cor, width=traco)
                d.line([x1, y0 + i, x1, min(y0 + i + 6, y1)], fill=cor, width=traco)
        else:
            d.rectangle([x0, y0, x1, y1], outline=cor, width=traco)
        cx0, cy0, cx1, cy1 = d.textbbox((0, 0), rotulo, font=fonte)
        ty = y0 - (cy1 - cy0) - 6 if y0 > (cy1 - cy0) + 8 else y1 + 3
        d.rectangle([x0, ty, x0 + (cx1 - cx0) + 8, ty + (cy1 - cy0) + 6], fill=cor)
        d.text((x0 + 4, ty + 2), rotulo, fill=(255, 255, 255), font=fonte)

    for v in vizinhas:
        if v["id"] == alvo["id"]:
            continue
        e_par = par is not None and v["class_name"] == par
        caixa(v, COR_PAR if e_par else COR_OUTRA, v["class_name"], not e_par)
    # só a PARTE DO CORPO no rótulo desenhado — é o que está em julgamento, e o
    # rótulo completo não cabe na largura da imagem sem ser cortado.
    caixa(alvo, COR_ALVO, f'{alvo["class_name"]} → {MAPA[alvo["class_name"]][0]}', False)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
    return (
        "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
        orig_w,
        orig_h,
    )


# ── HTML ─────────────────────────────────────────────────────────────────────
_ESTILO = """
:root { --fg:#1a1a1a; --fg2:#666; --bg:#faf9f7; --card:#fff; --borda:#d8d4cc;
        --acento:#d92b2b; --ok:#20a060; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18; --borda:#3a382f;
  --acento:#ff6b5e; --ok:#4fd18b; } }
:root[data-theme="dark"] { --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18;
  --borda:#3a382f; --acento:#ff6b5e; --ok:#4fd18b; }
body { background:var(--bg); color:var(--fg); margin:0; padding:2rem 1.25rem 4rem;
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1200px; margin:0 auto; }
h1 { font-size:1.7rem; margin:0 0 .3rem; letter-spacing:-.02em; }
h2 { font-size:1.15rem; margin:2.5rem 0 .8rem; }
p { max-width:70ch; }
.sub { color:var(--fg2); margin:0 0 1.5rem; }
.aviso { border-left:3px solid var(--acento); background:var(--card); padding:.85rem 1rem;
  margin:0 0 1.2rem; border-radius:0 4px 4px 0; max-width:70ch; }
.aviso b { color:var(--acento); }
.leg { display:flex; gap:1.2rem; flex-wrap:wrap; font-size:.85rem; margin:0 0 1.5rem;
  color:var(--fg2); }
.leg i { display:inline-block; width:22px; height:0; border-top:3px solid; margin-right:.35rem;
  vertical-align:middle; font-style:normal; }
table { border-collapse:collapse; margin:0 0 1.5rem; font-size:.88rem; }
th,td { text-align:left; padding:.32rem .9rem .32rem 0; border-bottom:1px solid var(--borda); }
th { color:var(--fg2); font-weight:600; }
.grid { display:grid; gap:1.4rem; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }
figure.c { margin:0; background:var(--card); border:1px solid var(--borda);
  border-radius:6px; overflow:hidden; display:flex; flex-direction:column; }
figure.c img { display:block; width:100%; height:auto; background:#111; }
.semfoto { padding:2.5rem 1rem; text-align:center; color:var(--acento); font-size:.85rem;
  background:var(--card); border-bottom:1px solid var(--borda); }
figcaption { padding:.7rem .8rem .8rem; display:flex; flex-direction:column; flex:1; }
.n { font-size:.72rem; color:var(--fg2); letter-spacing:.06em; text-transform:uppercase; }
.para { margin:.15rem 0 .1rem; font-size:1.02rem; }
.para b { color:var(--acento); }
.motivo { margin:.1rem 0 .6rem; font-size:.78rem; color:var(--fg2); font-style:italic; }
dl { display:grid; grid-template-columns:auto 1fr; gap:.08rem .55rem; margin:0 0 .7rem;
  font-size:.75rem; }
dt { color:var(--fg2); } dd { margin:0; overflow-wrap:anywhere; }
.veredito { margin-top:auto; padding-top:.6rem; border-top:1px dashed var(--borda);
  font-size:.8rem; color:var(--fg2); }
.veredito b { color:var(--fg); }
ol.resp { columns:2; font-size:.9rem; max-width:40rem; }
.box { background:var(--card); border:1px solid var(--borda); border-radius:6px;
  padding:1rem 1.2rem; max-width:70ch; }
.box.ok { border-left:3px solid var(--ok); }
"""


def _esc(s) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def montar_html(cartoes: list[dict], leitura: str, falhas: int) -> str:
    linhas_mapa = "".join(
        f"<tr><td>{_esc(c)}</td><td>{_esc(' + '.join(MAPA[c]))}</td>"
        f"<td>{len([x for x in cartoes if x['alvo']['class_name'] == c])}</td></tr>"
        for c in AUSENCIAS
    )
    cards = []
    for i, ct in enumerate(cartoes, 1):
        a = ct["alvo"]
        area = _area(a)
        quando = a["quando"]
        quando = quando.strftime("%d/%m/%Y %H:%M") if isinstance(quando, datetime) else str(quando)
        if ct.get("img"):
            visual = f'<img src="{ct["img"]}" alt="frame com a caixa de {_esc(a["class_name"])}">'
        else:
            visual = (
                f'<div class="semfoto"><b>FOTO NÃO VEIO</b><br>{_esc(ct.get("erro", "?"))}<br>'
                f'<code>{_esc(a["r2_key"])}</code></div>'
            )
        par = PAR_PRESENCA.get(a["class_name"])
        tem_par = any(v["class_name"] == par for v in ct["vizinhas"] if v["id"] != a["id"])
        cards.append(
            f"""<figure class="c">
  {visual}
  <figcaption>
    <p class="n">#{i}</p>
    <p class="para">{_esc(a["class_name"])} → <b>{_esc(" + ".join(MAPA[a["class_name"]]))}</b></p>
    <p class="motivo">{_esc(ct["motivo"])}</p>
    <dl>
      <dt>área da caixa</dt><dd>{area * 100:.2f}% do frame</dd>
      <dt>caixa (px)</dt><dd>{float(a["width"]) * ct["fw"]:.0f} × {float(a["height"]) * ct["fh"]:.0f}</dd>
      <dt>frame</dt><dd>{ct["fw"]} × {ct["fh"]}</dd>
      <dt>par de presença</dt><dd>{_esc(par) + (" — presente no frame" if tem_par else " — ausente no frame")}</dd>
      <dt>camera_id</dt><dd>{_esc(a["camera_id"] or "—")}</dd>
      <dt>data</dt><dd>{_esc(quando)}</dd>
      <dt>origem</dt><dd>{_esc(a["source"])}</dd>
      <dt>r2_key</dt><dd><code>{_esc(a["r2_key"])}</code></dd>
    </dl>
    <p class="veredito"><b>Veredito #{i}:</b> certo &nbsp;/&nbsp; errado &nbsp;/&nbsp; duvidoso</p>
  </figcaption>
</figure>"""
        )
    resp = "".join(
        f'<li>{_esc(c["alvo"]["class_name"])} — ______</li>' for c in cartoes
    )
    nota_falha = (
        f'<p class="aviso"><b>{falhas} foto(s) não vieram do R2.</b> Estão marcadas '
        f"no próprio cartão, com o motivo. Nenhum exemplo foi omitido para esconder "
        f"falha.</p>"
        if falhas
        else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amostra Variante C — fotos reais</title>
<style>{_ESTILO}</style></head><body>
<main>
<h1>Amostra — Variante C, com as fotos</h1>
<p class="sub">Gate humano da conversão. {len(cartoes)} anotações reais do RVB,
com a foto do frame e a caixa desenhada em cima.</p>

<div class="box ok">
<p style="margin-top:0"><b>O que você está aprovando.</b> Hoje "Sem Luvas" é uma
CLASSE do detector: a rede tem de aprender a enxergar uma coisa que não está lá.
A variante C troca isso — a mesma caixa passa a marcar a <b>parte do corpo</b>
que está desprotegida (a mão), e a violação passa a sair por
<b>sobreposição geométrica</b>: mão sem nenhuma luva em cima = "sem luva".</p>
<p><b>A pergunta, e só ela:</b> em cada foto abaixo, a caixa vermelha está
mesmo em cima da parte do corpo que o rótulo novo diz? Se "Sem Luvas" está na
mão, certo. Se está no tronco, na pessoa inteira, ou em lugar nenhum, errado.</p>
<p style="margin-bottom:0"><b>Se você aprovar:</b> as 1.656 anotações de ausência do RVB
são convertidas — na prática <b>1.162</b>, porque as 494 de frame inteiro são veredito
de cena da aba Classificar e já ficam de fora — e a variante C entra no A/B contra a
variante atual. <b>Se não:</b> a variante C não entra, e nada no dataset de hoje é
tocado (a conversão nunca escreve no banco — ela lê o COCO exportado e escreve um
COCO novo).</p>
</div>

{nota_falha}

<h2>Leitura honesta de quem gerou a amostra</h2>
<div class="box">{leitura}</div>

<h2>Como ler a imagem</h2>
<p class="leg">
  <span><i style="border-color:#d92b2b"></i>caixa da anotação em julgamento (rótulo atual → rótulo novo)</span>
  <span><i style="border-color:#20a060"></i>o EPI correspondente, quando existe no mesmo frame</span>
  <span><i style="border-color:#969696;border-top-style:dashed"></i>outras anotações do frame, contexto</span>
</p>
<p class="sub" style="max-width:70ch">Uma observação importante para julgar:
presença e ausência quase nunca coexistem no mesmo frame nesse dataset, então a
caixa verde vai aparecer em poucos cartões. Onde ela aparecer, compare: as duas
deveriam estar na MESMA região do corpo.</p>

<h2>Mapeamento e cobertura desta amostra</h2>
<table><thead><tr><th>classe RVB (ausência)</th><th>vira</th><th>exemplos aqui</th></tr></thead>
<tbody>{linhas_mapa}</tbody></table>
<p class="sub" style="max-width:70ch">Seleção adversarial e determinística: de cada
classe entram a MAIOR caixa, a MENOR e a de proporção mais extrema — os casos onde
a conversão tem mais chance de estar errada. As vagas restantes vão por volume,
sorteadas com semente fixa ({SEMENTE}) no miolo da distribuição. Só caixas
localizadas (área &lt; 50% do frame); as 494 de frame inteiro são veredito de cena
da aba Classificar e não entram.</p>

<h2>Os {len(cartoes)} exemplos</h2>
<div class="grid">
{"".join(cards)}
</div>

<h2>Sua resposta</h2>
<p>Marque só o que não estiver certo — o resto eu considero aprovado.
Formato: <code>3 errado, 7 duvidoso</code>.</p>
<ol class="resp">{resp}</ol>
</main></body></html>
"""


# ── Autoteste ────────────────────────────────────────────────────────────────
def autoteste() -> int:
    def falso(i: int, classe: str, w: float, h: float) -> dict:
        return {
            "id": f"{classe}-{i:03d}",
            "class_name": classe,
            "width": w,
            "height": h,
            "fw": 1920,
            "fh": 1080,
        }

    linhas = []
    for classe in AUSENCIAS:
        for i in range(1, 41):
            linhas.append(falso(i, classe, 0.01 * i, 0.01 * i))
        linhas.append(falso(90, classe, 0.30, 0.004))  # proporção extrema

    sel = selecionar(linhas, TOTAL)
    assert len(sel) == TOTAL, f"esperado {TOTAL}, veio {len(sel)}"
    assert len({s["id"] for s in sel}) == len(sel), "exemplo repetido"
    por_classe: dict[str, list[dict]] = {}
    for s in sel:
        por_classe.setdefault(s["class_name"], []).append(s)
    assert set(por_classe) == set(AUSENCIAS), "classe de ausência ficou de fora"
    for classe, grupo in por_classe.items():
        ids = {s["id"] for s in grupo}
        assert f"{classe}-040" in ids, f"{classe}: maior caixa não entrou"
        assert f"{classe}-001" in ids, f"{classe}: menor caixa não entrou"
        assert f"{classe}-090" in ids, f"{classe}: proporção extrema não entrou"
    assert [s["id"] for s in selecionar(linhas, TOTAL)] == [
        s["id"] for s in sel
    ], "seleção não é determinística"
    # nenhuma caixa de frame inteiro pode passar pelo filtro do SQL
    assert AREA_LOCALIZADA < 0.95
    print("autoteste: ok")
    return 0


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--saida", type=Path, default=Path("docs/quality/AMOSTRA-VARIANTE-C.html"))
    p.add_argument("--tenant", default=TENANT_RVB)
    p.add_argument("--total", type=int, default=TOTAL)
    p.add_argument(
        "--leitura",
        type=Path,
        default=Path("docs/quality/AMOSTRA-VARIANTE-C.leitura.html"),
        help="trecho HTML com a leitura honesta de quem gerou a amostra",
    )
    p.add_argument("--fotos-em", type=Path, help="também grava os JPEGs anotados aqui")
    p.add_argument("--autoteste", action="store_true")
    args = p.parse_args()
    if args.autoteste:
        return autoteste()

    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERRO: DATABASE_URL não definida.")
        return 1

    with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            _SQL, {"tenant": args.tenant, "classes": AUSENCIAS, "area": AREA_LOCALIZADA}
        )
        linhas = [dict(r) for r in cur.fetchall()]
        print(f"candidatas localizadas: {len(linhas)}")
        sel = selecionar(linhas, args.total)
        cur.execute(
            _SQL_VIZINHAS,
            {"frames": [s["frame_id"] for s in sel], "area": 0.95},
        )
        vizinhas: dict[str, list[dict]] = {}
        for r in cur.fetchall():
            vizinhas.setdefault(r["frame_id"], []).append(dict(r))

    s3 = _cliente_r2()
    bucket = os.environ["R2_BUCKET"]
    if args.fotos_em:
        args.fotos_em.mkdir(parents=True, exist_ok=True)
    cartoes, falhas, baixados = [], 0, 0
    for n, a in enumerate(sel, 1):
        ct = {"alvo": a, "motivo": a["motivo"], "vizinhas": vizinhas.get(a["frame_id"], [])}
        ct["fw"], ct["fh"] = a["fw"], a["fh"]
        try:
            bruto = s3.get_object(Bucket=bucket, Key=a["r2_key"])["Body"].read()
            ct["img"], ow, oh = desenhar(bruto, a, ct["vizinhas"])
            ct["fw"], ct["fh"] = ow, oh
            baixados += 1
            if args.fotos_em:
                (args.fotos_em / f"{n:02d}.jpg").write_bytes(
                    base64.b64decode(ct["img"].split(",", 1)[1])
                )
            print(f"  ok {a['class_name'][:22]:22} {len(bruto) // 1024:5d} KB  {ow}x{oh}")
        except Exception as exc:  # noqa: BLE001 - o motivo VAI para a página
            falhas += 1
            ct["erro"] = f"{type(exc).__name__}: {exc}"[:200]
            print(f"  FALHA {a['class_name']}: {ct['erro']}")
        cartoes.append(ct)

    texto = (
        args.leitura.read_text()
        if args.leitura.exists()
        else "<p>(a leitura de quem gerou a amostra ainda não foi escrita)</p>"
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(montar_html(cartoes, texto, falhas))
    kb = args.saida.stat().st_size / 1024
    print(f"\n{len(cartoes)} exemplos, {baixados} fotos ok, {falhas} falhas")
    print(f"{args.saida} — {kb / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
