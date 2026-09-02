#!/usr/bin/env python3
"""Avaliador de AUSÊNCIA — a régua que decide entre duas variantes do detector de EPI.

    VARIANTE A · PRESENÇA        5 classes. A ausência é DERIVADA: o estágio 1
                                 (detector de pessoa, já servido no edge) dá o
                                 recorte; o objeto esperado que não aparece
                                 naquele recorte vira acusação de ausência.
    VARIANTE B · PRESENÇA+AUSÊNCIA   as mesmas 5 + as classes "Sem X" COMO
                                 CLASSES DO DETECTOR.

As duas produzem saída de FORMATO diferente, então map50 de caixa não as compara.
O que o produto quer medir é a capacidade de ACUSAR CERTO — por isso a comparação
acontece no nível da DECISÃO: por imagem e por classe de ausência, o modelo ACUSOU
ou não, e o gabarito diz se aquela ausência era real. Isso, sim, é comparável.

Por que existe um script separado em vez de reusar a task de avaliação:
`tasks/model_evaluation.py::_resolve_holdout_split` pega o holdout da
`dataset_version` DO PRÓPRIO MODELO. Modelo diferente = prova diferente = ranking
sem sentido. Aqui o holdout é UM, entra por argumento, e vale para os dois.

⚠️ A derivação da variante A é exatamente o caminho que a **ADR-0067 PROÍBE** em
produção ("violação nunca nasce do silêncio do detector de presença"). Medi-la
aqui serve para quantificar o preço dela, não para reabrir a porta.

Uso:
    python scripts/ops/ab_ausencia.py \\
        --holdout  /dados/rvb/holdout/test/_annotations.coco.json \\
        --modelo-a /modelos/v-presenca.onnx \\
        --modelo-b /modelos/v-presenca-ausencia.onnx \\
        --pessoa   /modelos/yolox_nano_person.onnx \\
        --treino   /dados/rvb/treino-b/train/_annotations.coco.json \\
        --saida    /tmp/ab_ausencia.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# ── Régua e limiares ──────────────────────────────────────────────────────────
# 0,30 é o "melhor limiar" da medição do #536 registrada na ADR-0067 — é de lá
# que vem o default, não de gosto. A varredura reporta os vizinhos para que a
# escolha continue explícita.
_LIMIAR_PADRAO = 0.30
_VARREDURA_PADRAO = (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)
# Piso de coleta: a inferência roda UMA vez neste limiar e guarda as confianças;
# cada limiar da varredura é decidido depois, sobre a MESMA coleta. Isso é o que
# garante a regra de justiça 1 (mesmas imagens, mesma ordem, mesmo preproc) — e
# vale igual para as DUAS variantes, então não favorece nenhuma.
# ponytail: o NMS roda na coleta, não por limiar varrido; caixa suprimida a 0,05
# não reaparece a 0,30. Reinferir por limiar corrige, ao preço de 7× de GPU.
_LIMIAR_COLETA = 0.05
_REGUA_PRECISAO = 0.50  # ADR-0067: abaixo disto a classe não sustenta acusação
_N_MINIMO = 30  # ADR-0067: "Sem Óculos, 66,7% sobre 3" — n insuficiente não é medida
_MARGEM_EMPATE = 0.05  # diferença menor que 5pp entre A e B = empate técnico

# Margens do recorte de pessoa — as MESMAS do edge
# (services/edge-sync-agent/app/collector/person_detector.py::crop_person).
# EPI de cabeça sai fora de um bbox justo demais.
_MARGEM_X, _MARGEM_Y = 0.25, 0.08

# ── Taxonomia RVB ─────────────────────────────────────────────────────────────
# objeto de presença → classe de ausência correspondente no gabarito.
# "Botas" fica de fora de propósito: não existe "Sem Botas" no holdout, então
# não há gabarito para julgar acusação nenhuma sobre ela.
MAPA_AUSENCIA: dict[str, str] = {
    "Luvas": "Sem Luvas",
    "mascara": "Sem mascara",
    "Óculos": "Sem Óculos",
    "Protetor auditivo": "Sem protetor de ouvido",
}
# Não é ausência de objeto, é objeto presente e mal usado — a variante A não tem
# como derivá-la (silêncio não distingue "sem máscara" de "máscara no queixo").
CLASSE_SO_DIRETA = "Uso incorreto de mascara"
CLASSES_AUSENCIA: tuple[str, ...] = (*MAPA_AUSENCIA.values(), CLASSE_SO_DIRETA)


# ── Gabarito ──────────────────────────────────────────────────────────────────

def carregar_coco(caminho: Path) -> dict[str, Any]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def ausencias_reais(coco: dict[str, Any]) -> dict[str, set[int]]:
    """classe de ausência → ids das imagens em que ela é REAL (tem anotação)."""
    nome_por_id = {c["id"]: c["name"] for c in coco.get("categories", [])}
    reais: dict[str, set[int]] = {c: set() for c in CLASSES_AUSENCIA}
    for ann in coco.get("annotations", []):
        nome = nome_por_id.get(ann.get("category_id"))
        if nome in reais:
            reais[nome].add(ann["image_id"])
    return reais


# ── Acusação ──────────────────────────────────────────────────────────────────

def acusacoes_b(
    dets_por_imagem: dict[int, list[dict]], limiar: float
) -> dict[str, set[int]]:
    """Variante B: acusa quando emite a classe "Sem X" acima do limiar."""
    acusadas: dict[str, set[int]] = {c: set() for c in CLASSES_AUSENCIA}
    for image_id, dets in dets_por_imagem.items():
        for det in dets:
            if det["class"] in acusadas and det["confidence"] >= limiar:
                acusadas[det["class"]].add(image_id)
    return acusadas


def acusacoes_a(
    recortes_por_imagem: dict[int, list[list[dict]]], limiar: float
) -> dict[str, set[int]]:
    """Variante A: acusa por DERIVAÇÃO — objeto esperado que não apareceu no recorte.

    `recortes_por_imagem[image_id]` é uma lista por pessoa detectada; cada item é
    a lista de detecções do modelo A naquele recorte. Imagem sem pessoa detectada
    não acusa nada (não há de quem falar) — e é isso que a ADR-0067 chama de
    abstenção, ao contrário do recorte vazio, que aqui acusa TUDO.
    """
    acusadas: dict[str, set[int]] = {c: set() for c in CLASSES_AUSENCIA}
    for image_id, recortes in recortes_por_imagem.items():
        for dets in recortes:
            presentes = {d["class"] for d in dets if d["confidence"] >= limiar}
            for objeto, classe_ausencia in MAPA_AUSENCIA.items():
                if objeto not in presentes:
                    acusadas[classe_ausencia].add(image_id)
    return acusadas


# ── Contagem ──────────────────────────────────────────────────────────────────

def _razao(numerador: int, denominador: int) -> float | None:
    """None quando não há denominador — nem 0, nem 1.

    Classe sem nenhuma acusação não tem precisão 100% ("acertou todas as zero"):
    não tem precisão nenhuma. O None é o que impede o relatório de premiar
    silêncio.
    """
    return numerador / denominador if denominador else None


def contar(
    acusadas: set[int], reais: set[int], universo: set[int]
) -> dict[str, Any]:
    """TP/FP/FN + precisão/recall de UMA classe, restrito ao universo avaliado."""
    acusadas = acusadas & universo
    reais = reais & universo
    tp = len(acusadas & reais)
    fp = len(acusadas - reais)
    fn = len(reais - acusadas)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precisao": _razao(tp, tp + fp),
        "recall": _razao(tp, tp + fn),
        "n_acusacoes": tp + fp,
        "n_reais": tp + fn,
    }


def medir(
    acusadas: dict[str, set[int]], reais: dict[str, set[int]], universo: set[int]
) -> dict[str, dict[str, Any]]:
    return {
        classe: contar(acusadas.get(classe, set()), reais.get(classe, set()), universo)
        for classe in CLASSES_AUSENCIA
    }


# ── Veredito ──────────────────────────────────────────────────────────────────

def sustenta_acusacao(m: dict[str, Any]) -> bool:
    """Régua da ADR-0067: precisão ≥ 50% E n suficiente para a precisão significar algo."""
    return (
        m["precisao"] is not None
        and m["precisao"] >= _REGUA_PRECISAO
        and m["n_acusacoes"] >= _N_MINIMO
    )


def veredito_classe(a: dict[str, Any], b: dict[str, Any]) -> str:
    """A / B / empate / nenhuma — nunca inventa vencedor.

    Regra do dono: empate técnico → vence a mais simples (A).
    """
    passa_a, passa_b = sustenta_acusacao(a), sustenta_acusacao(b)
    if not passa_a and not passa_b:
        if max(a["n_acusacoes"], b["n_acusacoes"]) < _N_MINIMO:
            return f"n insuficiente (A={a['n_acusacoes']}, B={b['n_acusacoes']}) — sem veredito"
        return "nenhuma sustenta a régua"
    if passa_a and not passa_b:
        return "A vence"
    if passa_b and not passa_a:
        return "B vence"

    for chave in ("precisao", "recall"):
        delta = (a[chave] or 0.0) - (b[chave] or 0.0)
        if abs(delta) > _MARGEM_EMPATE:
            return f"A vence ({chave})" if delta > 0 else f"B vence ({chave})"
    return "empate → A (mais simples)"


def veredito_geral(por_classe: dict[str, str]) -> str:
    vitorias_a = sum(1 for v in por_classe.values() if v.startswith("A vence"))
    vitorias_b = sum(1 for v in por_classe.values() if v.startswith("B vence"))
    if vitorias_a == vitorias_b == 0:
        return "SEM VEREDITO — nenhuma classe produziu comparação válida"
    if vitorias_a > vitorias_b:
        return f"A vence ({vitorias_a} classe(s) contra {vitorias_b})"
    if vitorias_b > vitorias_a:
        return f"B vence ({vitorias_b} classe(s) contra {vitorias_a})"
    return f"EMPATE ({vitorias_a} a {vitorias_b}) → vence a mais simples: A"


# ── Guarda de vazamento ───────────────────────────────────────────────────────

def _identidades(caminho_coco: Path) -> tuple[set[str], set[str], int]:
    """(nomes de arquivo, sha256 das imagens achadas no disco, quantas foram hasheadas).

    Dois canais porque nenhum sozinho basta: o nome pega o export repetido, o
    hash pega a mesma imagem reexportada com outro nome. Imagem que não está no
    disco só entra pelo nome — e o relatório diz quantas ficaram sem hash, para
    ninguém confundir "não achei vazamento" com "não procurei".
    """
    coco = carregar_coco(caminho_coco)
    base = Path(caminho_coco).parent
    nomes: set[str] = set()
    hashes: set[str] = set()
    hasheadas = 0  # ARQUIVOS lidos, não `len(hashes)`: duplicata colapsa no set
    for img in coco.get("images", []):
        nomes.add(Path(img["file_name"]).name)
        arquivo = base / img["file_name"]
        if arquivo.is_file():
            hashes.add(hashlib.sha256(arquivo.read_bytes()).hexdigest())
            hasheadas += 1
    return nomes, hashes, hasheadas


def verificar_vazamento(
    caminho_holdout: Path, caminhos_treino: list[Path]
) -> dict[str, Any]:
    """Falha RUIDOSAMENTE se alguma imagem do holdout está no treino.

    Sem esta guarda a variante B é avaliada no que decorou e o A/B mente a favor
    dela. Levanta SystemExit — o script não continua com um resultado inválido.
    """
    nomes_h, hashes_h, hasheadas_h = _identidades(caminho_holdout)
    colisoes_nome: set[str] = set()
    colisoes_hash: set[str] = set()
    hasheadas_t = 0
    for caminho in caminhos_treino:
        nomes_t, hashes_t, n = _identidades(caminho)
        hasheadas_t += n
        colisoes_nome |= nomes_h & nomes_t
        colisoes_hash |= hashes_h & hashes_t

    resultado = {
        "colisoes_nome": sorted(colisoes_nome),
        "colisoes_hash": sorted(colisoes_hash),
        "holdout_imagens": len(nomes_h),
        "holdout_hasheadas": hasheadas_h,
        "treino_hasheadas": hasheadas_t,
    }
    if colisoes_nome or colisoes_hash:
        raise SystemExit(
            "VAZAMENTO DE HOLDOUT — o A/B seria mentira e por isso não roda.\n"
            f"  imagens do holdout com o MESMO NOME no treino: {len(colisoes_nome)}\n"
            f"  imagens do holdout com o MESMO CONTEÚDO no treino: {len(colisoes_hash)}\n"
            f"  exemplos: {sorted(colisoes_nome)[:5] or sorted(colisoes_hash)[:5]}\n"
            "Refaça o split antes de comparar as variantes."
        )
    if hasheadas_h < len(nomes_h):
        print(
            f"[ab_ausencia] AVISO: {len(nomes_h) - hasheadas_h} imagem(ns) do holdout "
            "não estão no disco — a guarda de vazamento cobriu essas SÓ pelo nome."
        )
    return resultado


# ── Inferência ────────────────────────────────────────────────────────────────

def recortar(frame: Any, bbox: list[float]) -> Any:
    """Recorte da pessoa com a margem do edge. None se degenerar."""
    x, y, w, h = (int(v) for v in bbox[:4])
    mx, my = int(w * _MARGEM_X), int(h * _MARGEM_Y)
    alt, larg = frame.shape[:2]
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(larg, x + w + mx), min(alt, y + h + my)
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1]


def inferir_holdout(
    coco: dict[str, Any],
    base_dir: Path,
    det_a: Any,
    det_b: Any,
    det_pessoa: Any,
    classe_pessoa: str,
) -> tuple[set[int], dict[int, list[dict]], dict[int, list[list[dict]]], list[str]]:
    """Roda A, B e o estágio 1 nas MESMAS imagens, na mesma ordem.

    Retorna (universo, dets_b, recortes_a, falhas). Imagem que falha em QUALQUER
    variante sai do universo das DUAS — comparar em provas diferentes é o defeito
    que este script existe para não repetir.
    """
    import cv2  # noqa: PLC0415

    universo: set[int] = set()
    dets_b: dict[int, list[dict]] = {}
    recortes_a: dict[int, list[list[dict]]] = {}
    falhas: list[str] = []

    for image in coco.get("images", []):
        caminho = base_dir / image["file_name"]
        try:
            frame = cv2.imread(str(caminho))
            if frame is None:
                raise ValueError("cv2.imread retornou None")
            pessoas = [
                d for d in det_pessoa.predict(frame) if d["class"] == classe_pessoa
            ]
            por_recorte: list[list[dict]] = []
            for pessoa in pessoas:
                recorte = recortar(frame, pessoa["bbox"])
                if recorte is not None:
                    por_recorte.append(det_a.predict(recorte))
            saida_b = det_b.predict(frame)
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{image['file_name']}: {exc}")
            continue
        universo.add(image["id"])
        recortes_a[image["id"]] = por_recorte
        dets_b[image["id"]] = saida_b

    return universo, dets_b, recortes_a, falhas


def _construir_detector(
    backend: str, caminho: str, classes: list[str] | None, limiar: float
) -> Any:
    from app.domain.detectors.factory import get_detector  # noqa: PLC0415

    return get_detector(
        backend=backend, model_path=caminho, class_names=classes, confidence=limiar
    )


# ── Relatório ─────────────────────────────────────────────────────────────────

def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _linhas_tabela(rotulo: str, m: dict[str, Any]) -> str:
    return (
        f"| {rotulo} | {m['tp']} | {m['fp']} | {m['fn']} | {_pct(m['precisao'])} "
        f"| {_pct(m['recall'])} | {m['n_acusacoes']} acus. / {m['n_reais']} reais |"
    )


def render(
    ctx: dict[str, Any],
    metricas_a: dict[str, dict[str, Any]],
    metricas_b: dict[str, dict[str, Any]],
    vereditos: dict[str, str],
    varredura: list[tuple[float, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]],
) -> str:
    p: list[str] = []
    p.append("# A/B de AUSÊNCIA — presença derivada (A) × classe de ausência (B)\n")
    p.append(f"- **holdout:** `{ctx['holdout']}` — {ctx['imagens_holdout']} imagens no COCO, "
             f"**{len(ctx['universo'])} avaliadas nas duas variantes**")
    p.append(f"- **modelo A (presença):** `{ctx['modelo_a']}` — dicionário: {ctx['classes_a']}")
    p.append(f"- **modelo B (presença+ausência):** `{ctx['modelo_b']}` — "
             f"dicionário: {ctx['classes_b']}")
    p.append(f"- **estágio 1 (pessoa):** `{ctx['pessoa']}` — classe `{ctx['classe_pessoa']}`, "
             f"limiar {ctx['limiar_pessoa']:.2f}, margem de recorte "
             f"{_MARGEM_X:.0%}×{_MARGEM_Y:.0%} (a mesma do edge)")
    p.append(f"- **limiar aplicado:** {ctx['limiar']:.2f} — **o MESMO para as duas variantes**")
    p.append(f"- **backend:** {ctx['backend']}")
    if ctx["falhas"]:
        p.append(f"- ⚠️ **{len(ctx['falhas'])} imagem(ns) fora do universo** (falha de leitura): "
                 f"{ctx['falhas'][:3]}")
    p.append("")

    guarda = ctx["guarda"]
    p.append("## Guarda de vazamento holdout×treino\n")
    p.append(f"Passou: 0 colisão de nome, 0 colisão de conteúdo. "
             f"{guarda['holdout_hasheadas']}/{guarda['holdout_imagens']} imagens do holdout "
             f"conferidas também por sha256; {guarda['treino_hasheadas']} imagens de treino "
             "hasheadas.\n")

    p.append(f"## Por classe de ausência (limiar {ctx['limiar']:.2f})\n")
    for classe in CLASSES_AUSENCIA:
        p.append(f"### {classe}\n")
        p.append("| variante | TP | FP | FN | precisão | recall | n |")
        p.append("|---|---:|---:|---:|---:|---:|---|")
        p.append(_linhas_tabela("A · presença derivada", metricas_a[classe]))
        p.append(_linhas_tabela("B · classe de ausência", metricas_b[classe]))
        p.append("")
        for rotulo, m in (("A", metricas_a[classe]), ("B", metricas_b[classe])):
            if sustenta_acusacao(m):
                p.append(f"- {rotulo}: **sustenta acusação** "
                         f"(precisão {_pct(m['precisao'])} ≥ {_REGUA_PRECISAO:.0%}, "
                         f"n={m['n_acusacoes']} ≥ {_N_MINIMO}).")
            elif m["n_acusacoes"] < _N_MINIMO:
                p.append(f"- {rotulo}: **n insuficiente** (n={m['n_acusacoes']} < {_N_MINIMO}) — "
                         "precisão sem n não é medida (ADR-0067).")
            else:
                p.append(f"- {rotulo}: **NÃO sustenta acusação** — precisão "
                         f"{_pct(m['precisao'])} < {_REGUA_PRECISAO:.0%} (ADR-0067).")
        p.append(f"- **veredito:** {vereditos[classe]}\n")

    p.append("## Varredura de limiares (as duas variantes, todos os limiares)\n")
    p.append("A regra de justiça é limiar ÚNICO. A varredura está aqui para a escolha "
             "ficar explícita — não para cada variante escolher o seu.\n")
    p.append("| limiar | classe | A precisão/recall (n) | B precisão/recall (n) |")
    p.append("|---:|---|---|---|")
    for limiar, ma, mb in varredura:
        for classe in CLASSES_AUSENCIA:
            a, b = ma[classe], mb[classe]
            p.append(
                f"| {limiar:.2f} | {classe} | {_pct(a['precisao'])} / {_pct(a['recall'])} "
                f"({a['n_acusacoes']}) | {_pct(b['precisao'])} / {_pct(b['recall'])} "
                f"({b['n_acusacoes']}) |"
            )
    p.append("")

    p.append("## Veredito geral\n")
    p.append(f"**{veredito_geral(vereditos)}**\n")
    p.append("Empate técnico (< 5pp de diferença em precisão e recall) conta como empate, "
             "e empate vence a mais simples: A.\n")

    p.append("## O que este relatório NÃO mediu\n")
    p.append(
        "- **Geometria.** A comparação é por decisão (imagem × classe), não por caixa. "
        "Uma imagem com três pessoas conta TP mesmo se a variante acusou a pessoa errada.\n"
        "- **Botas.** Não existe classe `Sem Botas` no gabarito; sem gabarito não há o que "
        "julgar, então ela ficou fora — não é omissão, é falta de verdade.\n"
        f"- **`{CLASSE_SO_DIRETA}` pela variante A.** A não tem como derivá-la: silêncio não "
        "distingue 'sem máscara' de 'máscara no queixo'. O recall 0 dela é estrutural, não "
        "desempenho.\n"
        "- **Persistência temporal e zona.** A ADR-0067 exige as duas antes de qualquer "
        "acusação virar alerta. Aqui cada frame é julgado sozinho.\n"
        "- **Abstenção.** O caminho 2 da ADR-0067 (classificador de recorte com veredito "
        "`não visível`) não está neste A/B. `não visível` aqui vira acusação na variante A.\n"
        "- **Custo e latência.** A tem duas inferências por frame; isso não entra na conta.\n"
        f"- **O efeito do NMS por limiar.** A inferência rodou uma vez a {_LIMIAR_COLETA:.2f} e a "
        "varredura decidiu em cima dela; caixa suprimida na coleta não reaparece num limiar "
        "mais alto. Vale igual para as duas variantes, mas não é o mesmo que reinferir.\n"
        "- **O que o anotador não desenhou.** Imagem sem anotação `Sem X` é tratada como "
        "'não havia ausência'. Ausência real e não anotada aparece como FP da variante.\n"
        f"- **{len(ctx['falhas'])} imagem(ns)** que falharam na leitura — fora do universo das "
        "duas variantes.\n"
        "- **A legitimidade da variante A em produção.** A ADR-0067 já a proíbe. Este número "
        "mede o preço dela, não a autoriza.\n"
    )
    return "\n".join(p)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_classes(valor: str | None) -> list[str] | None:
    return [c.strip() for c in valor.split(",")] if valor else None


def montar_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="A/B no nível da decisão entre detector de presença (A) e "
                    "detector com classes de ausência (B).",
    )
    ap.add_argument("--holdout", required=True, type=Path,
                    help="COCO do holdout congelado (_annotations.coco.json); as imagens "
                         "ficam ao lado dele")
    ap.add_argument("--modelo-a", required=True, help="ONNX da variante A (presença)")
    ap.add_argument("--modelo-b", required=True, help="ONNX da variante B (presença+ausência)")
    ap.add_argument("--pessoa", required=True, help="ONNX do detector de pessoa (estágio 1)")
    ap.add_argument("--treino", required=True, nargs="+", type=Path,
                    help="COCO(s) do treino das variantes — a guarda de disjunção NÃO é "
                         "opcional: sem ela o A/B pode estar medindo o que a B decorou")
    ap.add_argument("--limiar", type=float, default=_LIMIAR_PADRAO,
                    help=f"confiança mínima, a MESMA para as duas variantes "
                         f"(padrão {_LIMIAR_PADRAO} — melhor limiar do #536, ADR-0067)")
    ap.add_argument("--saida", required=True, type=Path, help="caminho do relatório .md")
    ap.add_argument("--backend", default="yolox_onnx",
                    help="backend dos detectores A e B (yolox_onnx | rfdetr_onnx)")
    ap.add_argument("--backend-pessoa", default="yolox_onnx", help="backend do estágio 1")
    ap.add_argument("--classe-pessoa", default="person",
                    help="nome da classe de pessoa no dicionário do estágio 1")
    ap.add_argument("--limiar-pessoa", type=float, default=0.25,
                    help="confiança mínima do estágio 1 (padrão 0.25)")
    ap.add_argument("--classes-a", help="dicionário do modelo A na ORDEM DO ÍNDICE, separado "
                                       "por vírgula (padrão: categorias do holdout)")
    ap.add_argument("--classes-b", help="idem para o modelo B")
    ap.add_argument("--varredura", default=",".join(f"{v:.2f}" for v in _VARREDURA_PADRAO),
                    help="limiares da varredura, separados por vírgula")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)

    coco = carregar_coco(args.holdout)
    base_dir = args.holdout.parent

    # A guarda vem ANTES de qualquer inferência: gastar meia hora de GPU para
    # depois descobrir que a prova estava contaminada é o pior dos mundos.
    guarda = verificar_vazamento(args.holdout, args.treino)
    print(f"[ab_ausencia] guarda de vazamento OK ({guarda['holdout_imagens']} imagens "
          f"do holdout conferidas)")

    classes_holdout = [c["name"] for c in sorted(
        coco.get("categories", []), key=lambda c: c["id"])]
    classes_a = _parse_classes(args.classes_a) or classes_holdout
    classes_b = _parse_classes(args.classes_b) or classes_holdout

    det_a = _construir_detector(args.backend, args.modelo_a, classes_a, _LIMIAR_COLETA)
    det_b = _construir_detector(args.backend, args.modelo_b, classes_b, _LIMIAR_COLETA)
    det_pessoa = _construir_detector(
        args.backend_pessoa, args.pessoa, None, args.limiar_pessoa
    )

    universo, dets_b, recortes_a, falhas = inferir_holdout(
        coco, base_dir, det_a, det_b, det_pessoa, args.classe_pessoa
    )
    if not universo:
        raise SystemExit(
            "Nenhuma imagem do holdout foi avaliada — gravar isto como relatório seria "
            f"registrar ausência de medida como medida. Falhas: {falhas[:5]}"
        )

    reais = ausencias_reais(coco)
    metricas_a = medir(acusacoes_a(recortes_a, args.limiar), reais, universo)
    metricas_b = medir(acusacoes_b(dets_b, args.limiar), reais, universo)
    vereditos = {
        classe: veredito_classe(metricas_a[classe], metricas_b[classe])
        for classe in CLASSES_AUSENCIA
    }

    varredura = [
        (
            limiar,
            medir(acusacoes_a(recortes_a, limiar), reais, universo),
            medir(acusacoes_b(dets_b, limiar), reais, universo),
        )
        for limiar in (float(v) for v in args.varredura.split(","))
    ]

    ctx = {
        "holdout": str(args.holdout), "modelo_a": args.modelo_a, "modelo_b": args.modelo_b,
        "pessoa": args.pessoa, "classe_pessoa": args.classe_pessoa,
        "limiar_pessoa": args.limiar_pessoa, "limiar": args.limiar, "backend": args.backend,
        "classes_a": classes_a, "classes_b": classes_b, "universo": universo,
        "imagens_holdout": len(coco.get("images", [])), "falhas": falhas, "guarda": guarda,
    }
    args.saida.write_text(
        render(ctx, metricas_a, metricas_b, vereditos, varredura), encoding="utf-8"
    )
    print(f"[ab_ausencia] relatório em {args.saida}")
    print(f"[ab_ausencia] veredito geral: {veredito_geral(vereditos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
