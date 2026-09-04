#!/usr/bin/env python3
"""montar_dataset_multiescala.py — UM dataset com TODAS as escalas ao mesmo tempo.

POR QUE ESTE SCRIPT EXISTE (o diagnóstico, medido — não hipótese)
────────────────────────────────────────────────────────────────────────────────
O A/B das três variantes reprovou as três (`docs/quality/AB-HOLDOUT-V2-VEREDITO.md`).
A causa não é a taxonomia: é ESCALA. `scripts/ops/medir_objeto_pequeno.py`, rodado
no pool de export do RVB em 2026-09-03, mede o abismo em uma linha cada:

    domínio        caixas  frames    w×h_p50   p50 da caixa APÓS o resize   %SMALL depois
    RECORTE          6003    4780    351×475            83×56 px                 0,3%
    FRAME_CHEIO       340     204   1920×1080           20×32 px                78,5%

O modelo é SERVIDO em frame cheio (`inference_engine.py` chama `predict(frame)`
com o quadro inteiro). Ou seja: **94,6% das caixas de treino vêm de um regime em
que 0,3% dos objetos são pequenos, e o produto roda num regime em que 78,5% são.**
O detector nunca viu, no treino, o tamanho de objeto que precisa achar em produção.

E a distribuição é BIMODAL: 83×56 de um lado, 20×32 do outro, e NADA no meio.
Não há de onde interpolar. É esse buraco que este script preenche.

O QUE ELE FAZ (e o que NÃO faz)
────────────────────────────────────────────────────────────────────────────────
1. Classifica cada frame do pool num DOMÍNIO de escala e reporta a distribuição.
2. Gera RECORTES SINTÉTICOS dos frames cheios anotados, em escalas intermediárias
   (`--escalas`), reprojetando a anotação com aritmética — cobre a faixa que falta
   SEM anotação humana nova. A reprojeção tem teste com caso montado à mão
   (`autoteste`): errar o offset ensinaria caixa errada, em silêncio.
3. Balanceia por domínio com FATOR DE REPETIÇÃO derivado de uma META declarada
   (`--alvo-*`), não de número escolhido a dedo. A meta e o resultado ALCANÇADO
   saem lado a lado — repetição inteira nunca bate a meta exata, e maquiar isso
   seria mentir sobre o dataset.
4. Puxa dado público para as classes famintas, com teto e com procedência
   (licença + fonte) gravada em cada imagem e cada caixa.
5. Imprime a distribuição de escala ANTES e DEPOIS. Se não melhorar, ele diz.

**NÃO dispara treino. NÃO sobe nada para o R2. NÃO toca em deployment.**
Termina no dataset montado em disco.

O QUE ELE NÃO REINVENTA
────────────────────────────────────────────────────────────────────────────────
pool ................ `montar_dataset_v2.carregar_pool` → `versioning_v2`
split ............... `montar_dataset_v2.dividir` → `_split_by_group` (UMA vez,
                      herdado por qualquer variante que saia daqui)
taxonomia ........... `converter_datasets_publicos` / `converter_variante_c`
escala .............. `medir_objeto_pequeno.apos_resize` / `classe_coco`
frame cheio ......... `FrameRepository._FULL_FRAME_MIN_REPEATS`
projeção de custo ... `disparar_treinos_v2.projetar_timeout`

⛔ TRAVA DO GABARITO. Os 246 quadros julgados pelo dono têm
`training_frames.dataset_role='holdout'` (migration 133) e a trava vive em
`versioning_v2._snapshot_labeled_frames`/`_fetch_annotations` (`= 'pool'`,
ALLOWLIST). Como o pool daqui sai DESSAS funções, a trava pega neste caminho por
construção — e `test_montar_dataset_multiescala.py` prova que pega, com mutação.
Os recortes sintéticos herdam o frame-pai: sem pai no pool, não há filho.

USO
────────────────────────────────────────────────────────────────────────────────
    python3 scripts/ops/montar_dataset_multiescala.py autoteste       # sem banco
    DATABASE_URL=... python3 scripts/ops/montar_dataset_multiescala.py medir
    DATABASE_URL=... R2_...=... python3 scripts/ops/montar_dataset_multiescala.py montar
    ... montar --saida /dados/v2-multiescala --gravar
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))


def _carrega(nome: str):
    caminho = Path(__file__).resolve().parent / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


_mdv2 = _carrega("montar_dataset_v2")
_mop = _carrega("medir_objeto_pequeno")
_vd = _mdv2._vd

TENANT_RVB = _mdv2.TENANT_RVB
MODULO = _mdv2.MODULO

#: Lado do resize QUADRADO do rfdetr no val/ONNX (`medir_objeto_pequeno`
#: documenta por que o treino usa 840 e o val 560). A escala é medida no 560
#: porque é o número do artefato servido.
LADO_MODELO = 560

#: max(W,H) a partir do qual o recorte é DOWNSCALED para entrar no modelo, isto
#: é, carrega detalhe real. Abaixo disso o recorte é AMPLIADO e todo pixel novo
#: é interpolação. O corte é o próprio lado de entrada do detector — não é número
#: de gosto. Medido no RVB: p50 de max(W,H) dos recortes = 497 px; o corte parte
#: o acervo em 62,8% pequeno / 37,2% grande.
LIMITE_RECORTE_GRANDE = LADO_MODELO

#: Escalas dos recortes sintéticos, em fração do lado do frame cheio. A escada é
#: geométrica (÷1,5 a cada degrau) e foi escolhida para LIGAR os dois regimes
#: medidos, não para preencher espaço: num 1920×1080 com caixa mediana 73×69 px,
#: o objeto sai a 21×36 px no frame inteiro (regime servido) e a 85×143 px em
#: s=0,25 (regime dos recortes de treino). 0,6 e 0,4 são os degraus do meio, hoje
#: VAZIOS no acervo.
ESCALAS_SINTETICAS = (0.6, 0.4, 0.25)

#: Fração da caixa original que precisa sobrar DENTRO da janela para a anotação
#: ser emitida. Uma luva cortada ao meio ensinada como luva inteira é caixa
#: errada — e caixa errada não some no agregado, ela vira erro sistemático.
VISIVEL_MIN = 0.6

#: METAS de composição do TREINO, em fração das CAIXAS de origem RVB. Delas sai o
#: peso de cada domínio; nenhum peso é digitado à mão.
#:
#: quadro-cheio 0,25 — é o ÚNICO domínio idêntico à entrada servida (1920×1080,
#:   78,5% das caixas pequenas após resize). Hoje ele é 5,4% das caixas (340 de
#:   6.343). Subir para 25% é o remédio direto do diagnóstico.
#: sintetico 0,25 — preenche a faixa ENTRE os dois regimes (30-90 px após
#:   resize), hoje vazia. Sem ela o modelo teria dois picos e nada entre eles.
#: recorte-grande 0,30 — é o recorte que ainda carrega detalhe real (max(W,H) ≥
#:   560, entra no modelo por REDUÇÃO). O regime de perto é real: pessoa passando
#:   junto da câmera existe em produção.
#: recorte-pequeno 0,20 — é o domínio MAIS DISTANTE do servido (objeto sai a
#:   72-196 px após o resize, contra 20-32 px do frame cheio) e hoje é 55% das
#:   caixas de recorte. É o que o modelo mais decorou e o que menos se parece com
#:   o produto. Cortá-lo para 20% é o ponto do exercício.
ALVO_DOMINIO = {
    "quadro-cheio": 0.25,
    "sintetico": 0.25,
    "recorte-grande": 0.30,
    "recorte-pequeno": 0.20,
}

#: Teto de repetição. 194 caixas vistas 20× por época é decorar, não aprender —
#: e o diagnóstico deste script é justamente sobre um modelo que decorou uma
#: faixa estreita. Domínio que bate no teto NÃO alcança a meta, e o relatório diz.
MAX_REPETICAO = 8

#: Piso de caixas por classe no treino. Abaixo disso a classe não é aprendida:
#: `Protetor auditivo`, a classe que o modelo servido de fato acerta, tem 2.829
#: caixas no pool; `Luvas` tem 255 e sai a 0,105 de confiança MÁXIMA no frame
#: cheio (§4 do veredito). O público só é chamado para levar classe faminta até
#: este piso — nunca para encher volume.
PISO_CLASSE = 800

#: Teto do público, em fração das caixas do treino. O público é FORA DE DOMÍNIO
#: (Roboflow 640×640, outro site, outra luz): ele conserta a fome de classe, não
#: o domínio. Acima deste teto o gradiente passa a vir majoritariamente de um
#: lugar que o cliente não tem.
TETO_PUBLICO = 0.35

DOMINIOS_RVB = ("recorte-grande", "recorte-pequeno", "quadro-cheio", "sintetico")
DOMINIOS = (*DOMINIOS_RVB, "publico")


# ── Domínio de escala ────────────────────────────────────────────────────────
def dominio(frame: dict[str, Any], cheios: set[str]) -> str:
    """Domínio de escala de um frame. Uma definição só, usada em todo lugar.

    `quadro-cheio` sai da heurística DO PRODUTO (repetição de dimensão,
    `FrameRepository._FULL_FRAME_MIN_REPEATS`), não de um segundo critério
    inventado aqui — duas verdades sobre "o que é frame cheio" divergiriam em
    silêncio. `crop_origin` (migration 132) seria a prova por construção, mas é
    NULL em 100% do acervo (medido).
    """
    if frame.get("__sintetico__"):
        return "sintetico"
    if str(frame["id"]) in cheios:
        return "quadro-cheio"
    lado = max(int(frame["width"]), int(frame["height"]))
    return "recorte-grande" if lado >= LIMITE_RECORTE_GRANDE else "recorte-pequeno"


def escala_da_caixa(ann: dict[str, Any], frame: dict[str, Any]) -> tuple[float, float, str]:
    """(largura, altura) da caixa APÓS o resize do detector + classe COCO.

    A conta é a de `medir_objeto_pequeno.apos_resize` — importada, não recopiada.
    """
    fw, fh = int(frame["width"]), int(frame["height"])
    rw, rh = _mop.apos_resize(
        float(ann["width"]) * fw, float(ann["height"]) * fh, fw, fh, LADO_MODELO
    )
    return rw, rh, _mop.classe_coco(rw * rh)


# ── Recorte sintético: geometria pura, testável sem banco e sem imagem ───────
def reprojetar(
    ann: dict[str, Any], janela: tuple[int, int, int, int], fw: int, fh: int
) -> dict[str, Any] | None:
    """Anotação YOLO do frame (fw,fh) → anotação YOLO da janela. None = descarta.

    `janela` é (x0, y0, largura, altura) em PIXELS do frame. A caixa é recortada
    pela janela; se sobrar menos que `VISIVEL_MIN` da área original, ela é
    DESCARTADA em vez de ensinada mutilada.

    Toda a aritmética do script mora aqui. É a única função em que um erro de
    offset produziria um dataset que parece certo e ensina errado — por isso ela
    é pura (sem I/O, sem banco) e tem caso montado à mão no `autoteste`.
    """
    jx, jy, jw, jh = janela
    if jw <= 0 or jh <= 0:
        return None

    cx, cy = float(ann["x_center"]) * fw, float(ann["y_center"]) * fh
    bw, bh = float(ann["width"]) * fw, float(ann["height"]) * fh
    x0, y0, x1, y1 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2

    vx0, vy0 = max(x0, jx), max(y0, jy)
    vx1, vy1 = min(x1, jx + jw), min(y1, jy + jh)
    if vx1 <= vx0 or vy1 <= vy0:
        return None
    if (vx1 - vx0) * (vy1 - vy0) < VISIVEL_MIN * max(bw * bh, 1e-9):
        return None

    return {
        **ann,
        "x_center": ((vx0 + vx1) / 2 - jx) / jw,
        "y_center": ((vy0 + vy1) / 2 - jy) / jh,
        "width": (vx1 - vx0) / jw,
        "height": (vy1 - vy0) / jh,
    }


def janelas(
    fw: int, fh: int, anns: list[dict[str, Any]], escala: float
) -> list[tuple[int, int, int, int]]:
    """Janelas de tamanho `escala`×frame que cobrem as caixas anotadas.

    Guloso e DETERMINÍSTICO (ordena por y,x): centra uma janela na primeira
    caixa ainda descoberta, grampeia dentro do frame, marca como cobertas todas
    as caixas que couberem inteiras, repete. Uma janela sem nenhuma caixa não é
    emitida — recorte de parede vazia não ensina escala, só engorda o dataset.
    """
    jw, jh = max(1, round(fw * escala)), max(1, round(fh * escala))
    caixas = sorted(
        (
            (
                (float(a["x_center"]) - float(a["width"]) / 2) * fw,
                (float(a["y_center"]) - float(a["height"]) / 2) * fh,
                (float(a["x_center"]) + float(a["width"]) / 2) * fw,
                (float(a["y_center"]) + float(a["height"]) / 2) * fh,
            )
        )
        for a in anns
    )
    saida: list[tuple[int, int, int, int]] = []
    cobertas: set[int] = set()
    for i, (x0, y0, x1, y1) in enumerate(caixas):
        if i in cobertas:
            continue
        jx = int(min(max(0, (x0 + x1) / 2 - jw / 2), max(0, fw - jw)))
        jy = int(min(max(0, (y0 + y1) / 2 - jh / 2), max(0, fh - jh)))
        saida.append((jx, jy, jw, jh))
        for k, (a0, b0, a1, b1) in enumerate(caixas):
            if a0 >= jx and b0 >= jy and a1 <= jx + jw and b1 <= jy + jh:
                cobertas.add(k)
    return saida


def sinteticos_do_frame(
    frame: dict[str, Any], anns: list[dict[str, Any]], escalas: tuple[float, ...]
) -> list[tuple[dict[str, Any], list[dict[str, Any]], tuple[int, int, int, int]]]:
    """(frame sintético, anotações reprojetadas, janela) para um frame cheio.

    O frame sintético herda `camera_id`/`video_id`/`captured_at` do PAI: é o que
    faz `_group_key` colocá-lo no MESMO grupo e, portanto, no MESMO split. Filho
    no train com pai no val seria leakage com cara de dado novo.
    """
    fw, fh = int(frame["width"]), int(frame["height"])
    saida = []
    for escala in escalas:
        for k, janela in enumerate(janelas(fw, fh, anns, escala)):
            reproj = [r for a in anns if (r := reprojetar(a, janela, fw, fh))]
            if not reproj:
                continue
            fid = f"sint-{frame['id']}-s{escala:g}-{k}"
            sint = {
                **frame,
                "id": fid,
                "width": janela[2],
                "height": janela[3],
                "__sintetico__": True,
                "__pai__": str(frame["id"]),
                "__janela__": list(janela),
                "__escala__": escala,
            }
            saida.append((sint, [{**a, "frame_id": fid} for a in reproj], janela))
    return saida


# ── Balanceamento por domínio ────────────────────────────────────────────────
def peso_de_dominio(
    caixas_por_dominio: dict[str, int], alvo: dict[str, float],
    max_repeticao: int = MAX_REPETICAO,
) -> dict[str, float]:
    """Peso de cada domínio no TREINO, derivado da meta — nunca digitado.

    Mantém o VOLUME total (T = soma das caixas 1×) e distribui: `w_d = alvo_d·T /
    n_d`. Sai > 1 → o domínio é REPETIDO (nada é jogado fora); sai < 1 → é
    SUBAMOSTRADO. Só repetir não resolveria: o `recorte-pequeno` já é 55% das
    caixas, e nenhuma repetição dos outros o traz para 20% sem inflar o dataset
    a um tamanho que a GPU não paga. O peso > 1 vira inteiro (repetir 1,7 vez não
    existe) e é grampeado em `max_repeticao`; a meta perdida aparece no relatório.
    """
    total = sum(caixas_por_dominio.values())
    pesos: dict[str, float] = {}
    for d, n in caixas_por_dominio.items():
        a = alvo.get(d, 0.0)
        if not n or a <= 0:
            pesos[d] = 1.0
            continue
        w = a * total / n
        pesos[d] = float(min(max_repeticao, max(1, round(w)))) if w >= 1 else w
    return pesos


def _semente(texto: str) -> int:
    return int(hashlib.sha256(texto.encode()).hexdigest()[:12], 16)


def subamostrar(
    ids: list[str], fracao: float, prioridade: dict[str, int], seed: str
) -> set[str]:
    """Escolhe `fracao` dos ids, mantendo primeiro os de maior prioridade.

    Corta por IMAGEM, nunca por caixa: descartar uma caixa de uma imagem que fica
    cria FALSO NEGATIVO — o modelo aprenderia que aquela luva é fundo. E a ordem
    é por prioridade (imagem que carrega classe escassa fica) com desempate por
    hash: sem isso o corte de domínio desfaria o piso de classe que o público
    acabou de pagar.
    """
    if fracao >= 1:
        return set(ids)
    alvo = max(1, round(len(ids) * fracao)) if ids else 0
    ordem = sorted(ids, key=lambda i: (-prioridade.get(i, 0), _semente(f"{seed}:{i}")))
    return set(ordem[:alvo])


# ── Público: só onde falta classe, com teto e com procedência ────────────────
def amostrar_publico(
    entrada: Path,
    variante: str,
    faltando: dict[str, int],
    teto_caixas: int,
    seed: str,
) -> tuple[list[dict], list[dict], dict[str, Any]]:
    """Escolhe imagens públicas que levem as classes famintas até o piso.

    Passe único sobre TODOS os datasets INTERCALADOS (ordem por hash de
    `dataset:image_id`), não um de cada vez: percorrer em ordem de dicionário
    deixaria o primeiro dataset com estoque encher a cota sozinho — 613 caixas de
    `Luvas` vindas só do r1 é um site, uma luz, um estilo de câmera. Intercalar
    espalha a cota pelas fontes disponíveis, que é o que dado público serve para
    dar. Guarda a imagem se ela contribui ao menos uma caixa de classe ainda
    ABAIXO do alvo.

    Toda imagem guardada leva licença e fonte junto (CC BY exige crédito também
    no derivado) e vai SÓ para o treino — dado público não tem gabarito de EPI e
    no val/test viraria régua inventada (mesma regra de
    `montar_dataset_v2.somar_publico`).
    """
    restante = dict(faltando)
    imagens_out: list[dict] = []
    anns_out: list[dict] = []
    contas: dict[str, Any] = {"por_dataset": {}, "por_classe": Counter(), "teto": teto_caixas}
    orcamento = teto_caixas

    candidatos: list[tuple[int, str, Any, dict, list[dict], str]] = []
    for dataset in _vd.MAPA:
        raiz = entrada / dataset
        if not raiz.is_dir():
            continue
        leitor = _vd.le_oid if dataset == "oid" else _vd.le_coco
        brutas, imagens = leitor(raiz)
        novas, _ = _vd.converter(brutas, dataset, variante) if brutas else ([], {})
        licenca = _mdv2._licenca(raiz)
        por_img: dict[Any, list[dict]] = defaultdict(list)
        for a in novas:
            por_img[a["image_id"]].append(a)
        meta = {i["id"]: i for i in imagens}
        contas["por_dataset"][dataset] = {
            "imagens": 0, "caixas": 0, "licenca": licenca,
            "disponivel_caixas": len(novas), "disponivel_imagens": len(por_img),
        }
        for img_id, grupo in por_img.items():
            img = meta.get(img_id)
            if img is not None:
                candidatos.append(
                    (_semente(f"{seed}:{dataset}:{img_id}"), dataset, img_id, img,
                     grupo, licenca)
                )

    for _h, dataset, img_id, img, grupo, licenca in sorted(candidatos):
        if orcamento <= 0:
            break
        if not any(restante.get(a["category_name"], 0) > 0 for a in grupo):
            continue
        imagens_out.append(
            {
                "id": f"pub-{dataset}-{img_id}",
                "file_name": f"{dataset}/{img['file_name']}",
                "width": img.get("width"),
                "height": img.get("height"),
                "origem": dataset,
                "dominio": "publico",
                "licenca": licenca,
                "bbox_normalizada": dataset == "oid",
            }
        )
        for a in grupo:
            anns_out.append({**a, "image_id": f"pub-{dataset}-{img_id}",
                             "origem": dataset, "licenca": licenca})
            restante[a["category_name"]] = restante.get(a["category_name"], 0) - 1
            contas["por_classe"][a["category_name"]] += 1
            contas["por_dataset"][dataset]["caixas"] += 1
            orcamento -= 1
        contas["por_dataset"][dataset]["imagens"] += 1
    contas["orcamento_sobrando"] = orcamento
    return imagens_out, anns_out, contas


# ── Relatórios ───────────────────────────────────────────────────────────────
def tabela_escala(
    titulo: str, linhas: list[tuple[str, str, float, float, str]]
) -> str:
    """classe × domínio → n, lado da caixa após resize, %SMALL. `linhas` é
    (classe, domínio, largura_apos, altura_apos, classe_coco)."""
    grupos: dict[tuple[str, str], list[tuple[float, float, str]]] = defaultdict(list)
    for c, d, w, h, k in linhas:
        grupos[(c, d)].append((w, h, k))
    if not grupos:
        return f"{titulo}\n  (vazio)"

    larg = max(len(c) for c, _ in grupos)
    out = [titulo, f"  {'classe':<{larg}} {'domínio':<16} {'n':>6} "
                   f"{'p50 após 560':>13} {'p10':>11} {'%S':>7} {'%frame':>8}"]
    for c, d in sorted(grupos):
        v = grupos[(c, d)]
        p50 = f"{_mop._p([x[0] for x in v], 0.5):.0f}×{_mop._p([x[1] for x in v], 0.5):.0f}"
        p10 = f"{_mop._p([x[0] for x in v], 0.1):.0f}×{_mop._p([x[1] for x in v], 0.1):.0f}"
        pS = 100 * sum(1 for x in v if x[2] == "S") / len(v)
        pf = 100 * sum(x[0] * x[1] for x in v) / len(v) / (LADO_MODELO**2)
        out.append(f"  {c:<{larg}} {d:<16} {len(v):>6} {p50:>13} {p10:>11} "
                   f"{pS:>6.1f}% {pf:>7.2f}%")
    return "\n".join(out)


def resumo_escala(linhas: list[tuple[str, str, float, float, str]]) -> dict[str, Any]:
    if not linhas:
        return {"n": 0, "pS": 0.0, "p50": 0.0}
    lados = [(w * h) ** 0.5 for _, _, w, h, _ in linhas]
    return {
        "n": len(linhas),
        "pS": 100 * sum(1 for x in linhas if x[4] == "S") / len(linhas),
        "p10": _mop._p(lados, 0.10),
        "p50": _mop._p(lados, 0.50),
        "p90": _mop._p(lados, 0.90),
    }


def tabela_classe_dominio(
    caixas: dict[tuple[str, str], int], imagens: dict[tuple[str, str], set], titulo: str
) -> str:
    classes = sorted({c for c, _ in caixas})
    if not classes:
        return f"{titulo}\n  (vazio)"
    larg = max(len(c) for c in classes)
    cab = f"  {'classe':<{larg}}" + "".join(f"{d:>18}" for d in DOMINIOS) + f"{'TOTAL':>10}"
    out = [titulo, cab, "  " + "─" * (larg + 18 * len(DOMINIOS) + 10)]
    for c in classes:
        cel = ""
        tot = 0
        for d in DOMINIOS:
            n = caixas.get((c, d), 0)
            ni = len(imagens.get((c, d), ()))
            tot += n
            cel += f"{(f'{n}/{ni}' if n else '·'):>18}"
        out.append(f"  {c:<{larg}}{cel}{tot:>10}")
    tot_d = {d: sum(n for (_, dd), n in caixas.items() if dd == d) for d in DOMINIOS}
    out.append(f"  {'TOTAL caixas':<{larg}}" + "".join(f"{tot_d[d]:>18}" for d in DOMINIOS)
               + f"{sum(tot_d.values()):>10}")
    total = sum(tot_d.values()) or 1
    out.append(f"  {'% das caixas':<{larg}}"
               + "".join(f"{100 * tot_d[d] / total:>17.1f}%" for d in DOMINIOS))
    out.append("  (célula = caixas/imagens · · = zero)")
    return "\n".join(out)


def alerta_desbalanceamento(caixas_por_classe: dict[str, int], piso: int) -> str:
    if not caixas_por_classe:
        return "desbalanceamento: n/a"
    com = {c: n for c, n in caixas_por_classe.items() if n}
    zeradas = sorted(c for c, n in caixas_por_classe.items() if not n)
    if not com:
        return "desbalanceamento: TODAS as classes zeradas"
    maior, menor = max(com.items(), key=lambda kv: kv[1]), min(com.items(), key=lambda kv: kv[1])
    abaixo = sorted((c, n) for c, n in caixas_por_classe.items() if n < piso)
    txt = [f"razão maior:menor = {maior[1] / menor[1]:.1f}:1 "
           f"({maior[0]} {maior[1]} × {menor[0]} {menor[1]})"]
    if abaixo:
        txt.append("ABAIXO do piso de " + str(piso) + ": "
                   + ", ".join(f"{c} {n}" for c, n in abaixo))
    if zeradas:
        txt.append("ZERO caixas: " + ", ".join(zeradas))
    return " · ".join(txt)


# ── Montagem ─────────────────────────────────────────────────────────────────
def preparar(
    dsn: str, tenant: str, escalas: tuple[float, ...], seed: str, split: dict[str, float]
) -> dict[str, Any]:
    """Pool + domínios + sintéticos + split. Sem I/O de imagem, sem escrita."""
    anotacao_repo, _ = _mdv2.abrir_repos(dsn)
    pool = _mdv2.carregar_pool(anotacao_repo, tenant, MODULO)
    frames, anns, cheios = pool["frames"], pool["anns"], pool["cheios"]

    anns_por_frame: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in anns:
        anns_por_frame[str(a["frame_id"])].append(a)

    # split UMA vez, sobre o pool REAL (o sintético herda o do pai)
    for f in frames:
        f["__cheio__"] = str(f["id"]) in cheios
    membresia = _mdv2.dividir(frames, anns, split, seed, "estratificado")
    split_de = {fid: nome for nome, ids in membresia.items() for fid in ids}

    sint_frames: list[dict[str, Any]] = []
    sint_anns: list[dict[str, Any]] = []
    for f in frames:
        if str(f["id"]) not in cheios:
            continue
        for sint, reproj, _j in sinteticos_do_frame(
            f, anns_por_frame[str(f["id"])], escalas
        ):
            sint_frames.append(sint)
            sint_anns.extend(reproj)
            split_de[sint["id"]] = split_de.get(str(f["id"]), "train")

    return {
        "frames": frames, "anns": anns, "cheios": cheios,
        "sint_frames": sint_frames, "sint_anns": sint_anns,
        "membresia": membresia, "split_de": split_de,
    }


def _linhas_escala(
    frames: list[dict[str, Any]], anns: list[dict[str, Any]], cheios: set[str]
) -> list[tuple[str, str, float, float, str]]:
    por_id = {str(f["id"]): f for f in frames}
    out = []
    for a in anns:
        f = por_id.get(str(a["frame_id"]))
        if not f:
            continue
        w, h, k = escala_da_caixa(a, f)
        out.append((a["class_name"], dominio(f, cheios), w, h, k))
    return out


def materializar(
    sint_frames: list[dict[str, Any]], frames: list[dict[str, Any]],
    destino: Path, cache: Path,
) -> dict[str, Any]:
    """Baixa os frames cheios do R2 e corta os recortes sintéticos em disco.

    Sem isto o COCO apontaria para arquivo que não existe — dataset que é
    promessa, não dataset. Idempotente: recorte já gravado não é refeito.
    """
    from PIL import Image  # noqa: PLC0415

    s3 = _carrega("amostra_variante_c_fotos")._cliente_r2()
    bucket = os.environ["R2_BUCKET"]
    por_id = {str(f["id"]): f for f in frames}
    cache.mkdir(parents=True, exist_ok=True)
    destino.mkdir(parents=True, exist_ok=True)

    feitos = pulados = falhas = 0
    bytes_saida = 0
    abertos: dict[str, Any] = {}
    for sf in sorted(sint_frames, key=lambda f: (f["__pai__"], f["id"])):
        alvo = destino / f"{sf['id']}.jpg"
        if alvo.exists():
            pulados += 1
            bytes_saida += alvo.stat().st_size
            continue
        pai = por_id.get(sf["__pai__"])
        if not pai or not pai.get("r2_key"):
            falhas += 1
            continue
        if sf["__pai__"] not in abertos:
            local = cache / f"{sf['__pai__']}.jpg"
            if not local.exists():
                try:
                    local.write_bytes(
                        s3.get_object(Bucket=bucket, Key=pai["r2_key"])["Body"].read()
                    )
                except Exception as erro:  # noqa: BLE001
                    print(f"  ⚠️  {sf['__pai__']}: {erro}")
                    falhas += 1
                    continue
            abertos = {sf["__pai__"]: Image.open(local).convert("RGB")}
        img = abertos[sf["__pai__"]]
        jx, jy, jw, jh = sf["__janela__"]
        img.crop((jx, jy, jx + jw, jy + jh)).save(alvo, "JPEG", quality=92)
        bytes_saida += alvo.stat().st_size
        feitos += 1
    return {"gravados": feitos, "ja_existiam": pulados, "falhas": falhas,
            "bytes": bytes_saida}


def _bytes_r2(frames: list[dict[str, Any]], amostra: int, seed: str) -> tuple[float, int]:
    """(bytes médios por imagem no R2, n da amostra). HEAD, nunca GET.

    Amostra porque 4.987 HEADs seriam minutos de rede para um número que só
    dimensiona disco. O n sai impresso: extrapolação declarada não é medida
    disfarçada.
    """
    com_chave = sorted((f for f in frames if f.get("r2_key")),
                       key=lambda f: _semente(f"{seed}:{f['id']}"))[:amostra]
    if not com_chave:
        return 0.0, 0
    s3 = _carrega("amostra_variante_c_fotos")._cliente_r2()
    bucket = os.environ["R2_BUCKET"]
    tam = []
    for f in com_chave:
        try:
            tam.append(s3.head_object(Bucket=bucket, Key=f["r2_key"])["ContentLength"])
        except Exception:  # noqa: BLE001, S110
            pass
    return (sum(tam) / len(tam) if tam else 0.0), len(tam)


def montar(args) -> int:  # noqa: PLR0912, PLR0915
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("ERRO: DATABASE_URL não definida.")
        return 1

    escalas = tuple(args.escalas)
    prep = preparar(dsn, args.tenant, escalas, args.seed,
                    {"train": args.train, "val": args.val, "test": args.test})
    frames, anns, cheios = prep["frames"], prep["anns"], prep["cheios"]
    sint_frames, sint_anns = prep["sint_frames"], prep["sint_anns"]
    split_de, membresia = prep["split_de"], prep["membresia"]

    todos = {str(f["id"]): f for f in (*frames, *sint_frames)}
    todas_anns = [*anns, *sint_anns]
    anns_de: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in todas_anns:
        anns_de[str(a["frame_id"])].append(a)

    dom_frames = Counter(dominio(f, cheios) for f in frames)
    print(f"POOL RVB (funções do export de produção, trava dataset_role='pool'): "
          f"{len(frames)} frames · {len(anns)} caixas")
    print("  por domínio: " + " · ".join(f"{d}={dom_frames[d]}" for d in DOMINIOS_RVB[:3]))
    print(f"SINTÉTICOS  escalas={escalas} → {len(sint_frames)} recortes · "
          f"{len(sint_anns)} caixas (de {len(cheios)} frames cheios, "
          f"{sum(1 for a in anns if str(a['frame_id']) in cheios)} caixas)")
    print("SPLIT ÚNICO (herdado por qualquer variante): "
          + " · ".join(f"{k}={len(v)}" for k, v in membresia.items())
          + f" · seed={args.seed!r}")

    # ── ANTES ────────────────────────────────────────────────────────────────
    antes = _linhas_escala(frames, anns, cheios)
    print("\n" + tabela_escala("═ ESCALA ANTES (pool RVB como está hoje) ═", antes))
    r_antes = resumo_escala(antes)
    print(f"  TOTAL {r_antes['n']} caixas · lado p10/p50/p90 = "
          f"{r_antes['p10']:.0f}/{r_antes['p50']:.0f}/{r_antes['p90']:.0f} px · "
          f"SMALL {r_antes['pS']:.1f}%")

    # ── balanceamento por domínio ────────────────────────────────────────────
    treino = [fid for fid, s in split_de.items() if s == "train" and fid in todos]
    ids_por_dom: dict[str, list[str]] = defaultdict(list)
    for fid in treino:
        ids_por_dom[dominio(todos[fid], cheios)].append(fid)
    caixas_1x = {d: sum(len(anns_de[i]) for i in ids) for d, ids in ids_por_dom.items()}
    pesos = peso_de_dominio(caixas_1x, ALVO_DOMINIO, args.max_repeticao)

    # prioridade do corte: imagem que carrega classe escassa fica primeiro
    n_classe_1x = Counter(a["class_name"] for i in treino for a in anns_de[i])
    prioridade = {
        i: max((args.piso - n_classe_1x[a["class_name"]] for a in anns_de[i]), default=0)
        for i in treino
    }
    mantidos: dict[str, set[str]] = {}
    for d, ids in ids_por_dom.items():
        mantidos[d] = subamostrar(sorted(ids), pesos[d], prioridade, args.seed)
    repeticoes = {d: int(pesos[d]) if pesos[d] >= 1 else 1 for d in ids_por_dom}
    treino_efetivo = {i: repeticoes[dominio(todos[i], cheios)]
                      for d in mantidos for i in mantidos[d]}

    caixas_apos = {
        d: sum(len(anns_de[i]) for i in mantidos[d]) * repeticoes[d] for d in ids_por_dom
    }
    tot_apos = sum(caixas_apos.values()) or 1
    print("\n═ BALANCEAMENTO POR DOMÍNIO (só no treino) ═")
    print(f"  {'domínio':<16} {'imgs 1×':>8} {'caixas 1×':>10} {'meta':>6} {'peso':>7} "
          f"{'imgs':>7} {'caixas':>8} {'alcançado':>10}")
    for d in DOMINIOS_RVB:
        if d not in ids_por_dom:
            continue
        acao = f"{repeticoes[d]}×" if pesos[d] >= 1 else f"{pesos[d]:.2f}×"
        print(f"  {d:<16} {len(ids_por_dom[d]):>8} {caixas_1x[d]:>10} "
              f"{ALVO_DOMINIO.get(d, 0):>5.0%} {acao:>7} "
              f"{len(mantidos[d]) * repeticoes[d]:>7} {caixas_apos[d]:>8} "
              f"{caixas_apos[d] / tot_apos:>9.1%}")
    descartadas = sum(len(ids_por_dom[d]) - len(mantidos[d]) for d in ids_por_dom)
    if descartadas:
        n_apos = Counter()
        for i, rep in ((i, repeticoes[dominio(todos[i], cheios)])
                       for d in mantidos for i in mantidos[d]):
            for a in anns_de[i]:
                n_apos[a["class_name"]] += rep
        perdas = sorted(((n_classe_1x[c] - n_apos[c], c) for c in n_classe_1x
                         if n_apos[c] < n_classe_1x[c]), reverse=True)
        print(f"  subamostragem descartou {descartadas} imagens do treino "
              f"(nenhuma some do banco; só não entram NESTA versão)")
        if perdas:
            print("  ⚠️  o corte de domínio CUSTA caixa de classe: "
                  + " · ".join(f"{c} −{n}" for n, c in perdas[:6])
                  + "  (o público repõe abaixo, quando existe)")

    # ── público: só até o piso de classe, com teto ───────────────────────────
    classes = _mdv2.classes_da_variante(args.variante)
    trad_treino, _ = _mdv2.anotacoes_da_variante(
        [a for i in treino_efetivo for a in anns_de[i]], args.variante
    )
    rvb_por_classe: Counter = Counter()
    for a in trad_treino:
        rvb_por_classe[a["class_name"]] += treino_efetivo[str(a["frame_id"])]
    faltando = {c: max(0, args.piso - rvb_por_classe.get(c, 0)) for c in classes}
    teto = int(args.teto_publico / (1 - args.teto_publico) * sum(rvb_por_classe.values()))

    pub_imgs, pub_anns, pub_contas = [], [], {}
    if args.publico and args.publico.is_dir():
        pub_imgs, pub_anns, pub_contas = amostrar_publico(
            args.publico, args.variante, faltando, teto, args.seed
        )
        print(f"\n═ PÚBLICO (só no treino) ═  piso/classe={args.piso} · "
              f"teto={args.teto_publico:.0%} das caixas = {teto} caixas")
        for ds, c in pub_contas["por_dataset"].items():
            print(f"  {ds:<6} {c['imagens']:>6} imgs · {c['caixas']:>6} caixas "
                  f"(disponível: {c['disponivel_imagens']} imgs / "
                  f"{c['disponivel_caixas']} caixas) · {c['licenca'][:32]}")
        for c, n in sorted(pub_contas["por_classe"].items(), key=lambda kv: -kv[1]):
            print(f"    + {c:<26} {n}")
        sem_socorro = sorted(c for c, n in faltando.items()
                             if n > 0 and not pub_contas["por_classe"].get(c))
        if sem_socorro:
            print("  ⛔ SEM socorro público (faltam no piso e nenhum dataset tem): "
                  + ", ".join(sem_socorro))
    else:
        print("\n═ PÚBLICO ═ não usado (--publico ausente ou inexistente)")

    # ── DEPOIS ───────────────────────────────────────────────────────────────
    depois: list[tuple[str, str, float, float, str]] = []
    caixas_cd: Counter = Counter()
    imgs_cd: dict[tuple[str, str], set] = defaultdict(set)
    for a in trad_treino:
        f = todos[str(a["frame_id"])]
        d = dominio(f, cheios)
        w, h, k = escala_da_caixa(a, f)
        for _ in range(treino_efetivo[str(f["id"])]):
            depois.append((a["class_name"], d, w, h, k))
            caixas_cd[(a["class_name"], d)] += 1
        imgs_cd[(a["class_name"], d)].add(str(f["id"]))
    dim_pub = {i["id"]: (i.get("width"), i.get("height")) for i in pub_imgs}
    for a in pub_anns:
        caixas_cd[(a["category_name"], "publico")] += 1
        imgs_cd[(a["category_name"], "publico")].add(a["image_id"])
        W, H = dim_pub.get(a["image_id"], (None, None))
        if W and H:
            _x, _y, bw, bh = a["bbox"]
            if a.get("origem") == "oid":  # bbox normalizada — ver le_oid
                bw, bh = bw * W, bh * H
            rw, rh = _mop.apos_resize(bw, bh, W, H, LADO_MODELO)
            depois.append((a["category_name"], "publico", rw, rh, _mop.classe_coco(rw * rh)))

    print("\n" + tabela_escala("═ ESCALA DEPOIS (treino unificado) ═", depois))
    r_dep = resumo_escala(depois)
    print(f"  TOTAL {r_dep['n']} caixas · lado p10/p50/p90 = "
          f"{r_dep['p10']:.0f}/{r_dep['p50']:.0f}/{r_dep['p90']:.0f} px · "
          f"SMALL {r_dep['pS']:.1f}%")
    print(f"\n  ESCALA: SMALL após resize {r_antes['pS']:.1f}% → {r_dep['pS']:.1f}% "
          f"· lado p10 {r_antes['p10']:.0f} → {r_dep['p10']:.0f} px "
          f"(caminho SERVIDO, frame cheio 1920×1080: SMALL 78,5%, caixa p50 20×32 px)")
    if r_dep["pS"] <= r_antes["pS"] + 1:
        print("  ⛔ NÃO MELHOROU. O dataset continua cego para objeto pequeno.")
    elif r_dep["pS"] < 40:
        print("  ⚠️  MELHOROU, mas ainda LONGE do regime servido. O teto vem do "
              "material: só existem 204 quadros cheios anotados (340 caixas).")

    # ── tabelas finais ───────────────────────────────────────────────────────
    print("\n" + tabela_classe_dominio(
        caixas_cd, imgs_cd,
        f"═ TREINO · classe × domínio · variante {args.variante.upper()} ═"))

    val_ids = [fid for fid, s in split_de.items() if s == "val" and fid in todos]
    trad_val, _ = _mdv2.anotacoes_da_variante(
        [a for i in val_ids for a in anns_de[i]], args.variante)
    val_cd: Counter = Counter()
    val_im: dict[tuple[str, str], set] = defaultdict(set)
    for a in trad_val:
        f = todos[str(a["frame_id"])]
        val_cd[(a["class_name"], dominio(f, cheios))] += 1
        val_im[(a["class_name"], dominio(f, cheios))].add(str(f["id"]))
    print("\n" + tabela_classe_dominio(
        val_cd, val_im, "═ VAL · classe × domínio (sem público, sem repetição) ═"))

    por_classe_treino = {c: sum(n for (cc, _), n in caixas_cd.items() if cc == c)
                         for c in classes}
    antes_classe = Counter(a["class_name"] for a in anns)
    print("\n═ DESBALANCEAMENTO ═")
    print("  ANTES  (pool cru): " + alerta_desbalanceamento(
        {c: antes_classe.get(c, 0) for c in classes}, args.piso))
    print("  DEPOIS (treino)  : " + alerta_desbalanceamento(por_classe_treino, args.piso))

    # ── custo e disco ────────────────────────────────────────────────────────
    n_train = sum(treino_efetivo.values()) + len(pub_imgs)
    n_val = len({str(a["frame_id"]) for a in trad_val})
    dt = _carrega("disparar_treinos_v2")
    proj = dt.projetar_timeout(n_train, n_val)
    print(f"\n═ CUSTO PROJETADO ═  train={n_train} imagens (com repetição, "
          f"{len(treino_efetivo)} distintas RVB + {len(pub_imgs)} públicas) · val={n_val}")
    print(f"  referência MEDIDA: {dt.REF_S_POR_EPOCA}s/época para {dt.REF_IMAGENS} "
          f"imagens (v15-tudo) · pior caso histórico ×{dt.FATOR_LOTERIA:.2f}")
    print(f"  s/época projetado: {proj['s_por_epoca_bom']} (bom) / "
          f"{proj['s_por_epoca_pior']} (pior)")
    print(f"  100 épocas: {proj['s_por_epoca_bom'] * 100 / 3600:.1f} h (bom) / "
          f"{proj['pior_caso_100_epocas_s'] / 3600:.1f} h (pior) · "
          f"timeout {proj['horas']} h (restrição: {proj['restricao']}) · "
          f"US$ {proj['preco_usd_h'] * proj['timeout_s'] / 3600:.2f} @ "
          f"{proj['preco_usd_h']}/h")

    if args.amostra_bytes:
        media, n_am = _bytes_r2(frames, args.amostra_bytes, args.seed)
        rvb_distintas = len(treino_efetivo) + len(val_ids) + len(
            [i for i, s in split_de.items() if s == "test" and i in todos])
        pub_bytes = sum(
            (args.publico / i["file_name"]).stat().st_size
            for i in pub_imgs if (args.publico / i["file_name"]).is_file()
        )
        print(f"\n═ DISCO ═  amostra de {n_am} objetos no R2, média "
              f"{media / 1024:.0f} KB/imagem (EXTRAPOLAÇÃO, não medida do todo)")
        print(f"  RVB {rvb_distintas} imagens ≈ {rvb_distintas * media / 1e6:.0f} MB "
              f"(já no R2; o export é cópia R2→R2)")
        print(f"  público {len(pub_imgs)} imagens = {pub_bytes / 1e6:.0f} MB (MEDIDO em disco)")
        print(f"  sintéticos {len(sint_frames)} recortes: medidos ao gravar")

    # ── escrita ──────────────────────────────────────────────────────────────
    if not (args.gravar and args.saida):
        print("\nDRY-RUN — nada foi escrito. Repita com --gravar --saida DIR.")
        return 0

    saida: Path = args.saida
    saida.mkdir(parents=True, exist_ok=True)
    mat = materializar(sint_frames, frames, saida / "sinteticos", saida / ".cache-r2")
    print(f"\nrecortes sintéticos: {mat['gravados']} gravados · "
          f"{mat['ja_existiam']} já existiam · {mat['falhas']} falhas · "
          f"{mat['bytes'] / 1e6:.0f} MB")

    id_por_classe = {c: i + 1 for i, c in enumerate(classes)}
    for nome in ("train", "val", "test"):
        ids = [i for i, s in split_de.items() if s == nome and i in todos]
        if nome == "train":
            ids = [i for i in ids if i in treino_efetivo]
            fr = [todos[i] for i in ids for _ in range(treino_efetivo[i])]
        else:
            fr = [todos[i] for i in ids]
        an, _ = _mdv2.anotacoes_da_variante(
            [a for i in ids for a in anns_de[i]], args.variante)
        coco = _mdv2.montar_coco(fr, an, args.variante)
        for img in coco["images"]:
            fid = img["file_name"][:-4]
            f = todos.get(fid)
            img["dominio"] = dominio(f, cheios) if f else "?"
            if f and f.get("__sintetico__"):
                img["file_name"] = f"sinteticos/{fid}.jpg"
                img["sintetico_de"] = f["__pai__"]
                img["janela"] = f["__janela__"]
                img["escala"] = f["__escala__"]
        if nome == "train" and pub_imgs:
            desloc = max((i["id"] for i in coco["images"]), default=0)
            prox = max((a["id"] for a in coco["annotations"]), default=0) + 1
            remap: dict[str, int] = {}
            for img in pub_imgs:
                desloc += 1
                remap[img["id"]] = desloc
                coco["images"].append({**img, "id": desloc})
            for a in pub_anns:
                coco["annotations"].append({
                    "id": prox, "image_id": remap[a["image_id"]],
                    "category_id": id_por_classe[a["category_name"]],
                    "category_name": a["category_name"], "bbox": a["bbox"],
                    "area": a["area"], "iscrowd": 0, "dominio": "publico",
                    "origem": a["origem"], "licenca": a["licenca"],
                })
                prox += 1
            coco["info"]["publico"] = {
                k: (dict(v) if isinstance(v, Counter) else v)
                for k, v in pub_contas.items()
            }
        d = saida / nome
        d.mkdir(parents=True, exist_ok=True)
        (d / "_annotations.coco.json").write_text(
            json.dumps(coco, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"  {nome:5} {len(coco['images']):>6} imagens · "
              f"{len(coco['annotations']):>6} caixas → {d / '_annotations.coco.json'}")

    (saida / "split_membership.json").write_text(
        json.dumps({k: sorted(v) for k, v in membresia.items()},
                   ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (saida / "MANIFESTO.json").write_text(json.dumps({
        "tenant": args.tenant, "modulo": MODULO, "variante": args.variante,
        "seed": args.seed, "escalas_sinteticas": list(escalas),
        "visivel_min": VISIVEL_MIN, "alvo_dominio": ALVO_DOMINIO,
        "pesos_dominio": pesos, "repeticoes": repeticoes,
        "caixas_por_dominio_1x": caixas_1x, "caixas_por_dominio_apos": caixas_apos,
        "piso_classe": args.piso, "teto_publico": args.teto_publico,
        "publico": {k: (dict(v) if isinstance(v, Counter) else v)
                    for k, v in pub_contas.items()},
        "escala_antes": r_antes, "escala_depois": r_dep,
        "lado_modelo": LADO_MODELO, "classes": classes,
        "sinteticos_gravados": mat,
    }, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    for dataset in _vd.MAPA:
        raiz = (args.publico / dataset) if args.publico else None
        if raiz and raiz.is_dir():
            alvo_p = saida / "procedencia" / dataset
            alvo_p.mkdir(parents=True, exist_ok=True)
            for arq in ("PROCEDENCIA.json", "ATRIBUICAO.txt"):
                if (raiz / arq).is_file():
                    (alvo_p / arq).write_text(
                        (raiz / arq).read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\nmanifesto → {saida / 'MANIFESTO.json'}")
    print("⛔ NENHUM treino foi disparado. As imagens do RVB seguem no R2 (o export "
          "R2→R2 é passo do disparar_treinos_v2.py); os recortes sintéticos e as "
          "imagens públicas existem só em disco local e ainda precisam subir.")
    return 0


def medir(args) -> int:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("ERRO: DATABASE_URL não definida.")
        return 1
    anotacao_repo, _ = _mdv2.abrir_repos(dsn)
    pool = _mdv2.carregar_pool(anotacao_repo, args.tenant, MODULO)
    linhas = _linhas_escala(pool["frames"], pool["anns"], pool["cheios"])
    print(tabela_escala("═ ESCALA DO POOL COMO ESTÁ HOJE ═", linhas))
    r = resumo_escala(linhas)
    print(f"  TOTAL {r['n']} caixas · lado p10/p50/p90 = "
          f"{r['p10']:.0f}/{r['p50']:.0f}/{r['p90']:.0f} px · SMALL {r['pS']:.1f}%")
    return 0


# ── Autoteste ────────────────────────────────────────────────────────────────
def autoteste() -> int:
    """Caso montado à MÃO. Errar o offset da reprojeção ensina caixa errada."""
    # frame 1000×500; caixa de 100×50 centrada em (400,200) → x0=350 y0=175
    ann = {"class_name": "Luvas", "x_center": 0.4, "y_center": 0.4,
           "width": 0.1, "height": 0.1, "frame_id": "f"}
    # janela (300,150,400,200): a caixa cai inteira dentro
    r = reprojetar(ann, (300, 150, 400, 200), 1000, 500)
    assert r is not None
    assert abs(r["x_center"] - 0.25) < 1e-9, r          # (400-300)/400
    assert abs(r["y_center"] - 0.25) < 1e-9, r          # (200-150)/200
    assert abs(r["width"] - 0.25) < 1e-9, r             # 100/400
    assert abs(r["height"] - 0.25) < 1e-9, r            # 50/200
    # o objeto CRESCE: 100px numa janela de 400 vira 140px no 560; no frame
    # inteiro de 1000 ele seria 56px. É exatamente o efeito que o script busca.
    assert 0.1 * 1000 * LADO_MODELO / 1000 == 56.0
    assert r["width"] * LADO_MODELO == 140.0

    # janela deslocada: metade da caixa fora → descartada (VISIVEL_MIN=0.6)
    assert reprojetar(ann, (400, 150, 400, 200), 1000, 500) is None
    # janela que não toca a caixa
    assert reprojetar(ann, (700, 300, 300, 200), 1000, 500) is None
    # janela que corta 20% → passa, e a caixa encolhe proporcionalmente
    r2 = reprojetar(ann, (370, 150, 400, 200), 1000, 500)
    assert r2 is not None and abs(r2["width"] - 80 / 400) < 1e-9, r2

    # janelas(): cobre as caixas, é determinístico, não emite janela vazia
    js = janelas(1000, 500, [ann], 0.4)
    assert js == janelas(1000, 500, [ann], 0.4)
    assert len(js) == 1 and js[0][2:] == (400, 200)
    assert janelas(1000, 500, [], 0.4) == []

    # peso: meta 50% num domínio com 10% das caixas → repete 5× (0,5·1000/100)
    p = peso_de_dominio({"a": 100, "b": 900}, {"a": 0.5})
    assert p["a"] == 5 and p["b"] == 1, p
    # meta ABAIXO da fatia natural → subamostra (só repetir não resolveria)
    p2 = peso_de_dominio({"a": 800, "b": 200}, {"a": 0.2})
    assert p2["a"] == 0.25, p2                 # 0,2·1000/800
    # teto de repetição respeitado
    assert peso_de_dominio({"a": 1, "b": 999}, {"a": 0.5}, max_repeticao=8)["a"] == 8
    assert peso_de_dominio({"a": 0, "b": 10}, {"a": 0.5})["a"] == 1

    # subamostragem: corta por imagem, prioridade primeiro, determinística
    ids = [f"i{n}" for n in range(10)]
    prio = {"i7": 99, "i3": 98}
    fica = subamostrar(ids, 0.3, prio, "s")
    assert len(fica) == 3 and {"i7", "i3"} <= fica, fica
    assert fica == subamostrar(ids, 0.3, prio, "s")
    assert subamostrar(ids, 1.0, {}, "s") == set(ids)

    # domínio: o corte é o lado de entrada do modelo
    assert dominio({"id": "x", "width": 600, "height": 400}, set()) == "recorte-grande"
    assert dominio({"id": "x", "width": 300, "height": 400}, set()) == "recorte-pequeno"
    assert dominio({"id": "x", "width": 1920, "height": 1080}, {"x"}) == "quadro-cheio"
    assert dominio({"id": "x", "width": 9, "height": 9, "__sintetico__": True}, set()) == "sintetico"

    # taxonomia: ausência NUNCA vira o EPI (é a mutação que este script teme)
    assert _vd.destinos("ausencia", "Luvas", "b") == ("Sem Luvas",)
    assert _vd.destinos("ausencia", "Luvas", "a") == ()
    assert _vd.MAPA["r1"]["no glove"] == ("ausencia", "Luvas")
    print("autoteste: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="modo", required=True)
    sub.add_parser("autoteste", help="checagens sem banco e sem rede")
    for nome, ajuda in (("medir", "só a escala do pool de hoje"),
                        ("montar", "monta o dataset unificado (dry-run por padrão)")):
        m = sub.add_parser(nome, help=ajuda)
        m.add_argument("--tenant", default=TENANT_RVB)
        m.add_argument("--saida", type=Path)
        m.add_argument("--publico", type=Path)
        m.add_argument("--gravar", action="store_true")
        m.add_argument("--variante", choices=_vd.VARIANTES, default="b")
        m.add_argument("--seed", default=_mdv2.SEED_PADRAO)
        m.add_argument("--train", type=float, default=_mdv2.SPLIT_PADRAO["train"])
        m.add_argument("--val", type=float, default=_mdv2.SPLIT_PADRAO["val"])
        m.add_argument("--test", type=float, default=_mdv2.SPLIT_PADRAO["test"])
        m.add_argument("--escalas", type=float, nargs="+", default=list(ESCALAS_SINTETICAS))
        m.add_argument("--piso", type=int, default=PISO_CLASSE)
        m.add_argument("--teto-publico", type=float, default=TETO_PUBLICO)
        m.add_argument("--max-repeticao", type=int, default=MAX_REPETICAO)
        m.add_argument("--alvo", nargs="+", metavar="DOMINIO=FRACAO", default=[],
                       help="sobrescreve ALVO_DOMINIO (ex.: quadro-cheio=0.35). "
                            "O peso é DERIVADO da meta — quem decide a meta é o dono.")
        m.add_argument("--amostra-bytes", type=int, default=0,
                       help="quantos objetos do R2 medir (HEAD) para dimensionar disco")
    args = p.parse_args(argv)
    if args.modo == "autoteste":
        return autoteste()
    for par in getattr(args, "alvo", []):
        chave, _, valor = par.partition("=")
        if chave not in DOMINIOS_RVB:
            print(f"ERRO: --alvo {chave!r} não é domínio (use {DOMINIOS_RVB}).")
            return 1
        ALVO_DOMINIO[chave] = float(valor)
    if args.modo == "medir":
        return medir(args)
    if args.gravar and not args.saida:
        print("ERRO: --gravar exige --saida.")
        return 1
    return montar(args)


if __name__ == "__main__":
    raise SystemExit(main())
