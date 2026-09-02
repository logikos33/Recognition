#!/usr/bin/env python3
"""Avaliador de AUSÊNCIA — a régua que decide entre as variantes do detector de EPI.

    VARIANTE A · PRESENÇA        5 classes. A ausência é DERIVADA: o estágio 1
                                 (detector de pessoa, já servido no edge) dá o
                                 recorte; o objeto esperado que não aparece
                                 naquele recorte vira acusação de ausência.
    VARIANTE B · PRESENÇA+AUSÊNCIA   as mesmas 5 + as classes "Sem X" COMO
                                 CLASSES DO DETECTOR.
    VARIANTE C · PARTE DO CORPO + EPI   (desenho inspirado no SH17) pessoa, mão,
                                 luva, rosto, máscara, óculos, orelha, protetor
                                 auricular, botas. A ausência sai por
                                 SOBREPOSIÇÃO GEOMÉTRICA: mão sem luva em cima,
                                 rosto sem máscara, rosto sem óculos, orelha sem
                                 protetor.

As três produzem saída de FORMATO diferente, então map50 de caixa não as compara.
O que o produto quer medir é a capacidade de ACUSAR CERTO — por isso a comparação
acontece no nível da DECISÃO: por imagem e por classe de ausência, o modelo ACUSOU
ou não, e o gabarito diz se aquela ausência era real. Isso, sim, é comparável.

Por que existe um script separado em vez de reusar a task de avaliação:
`tasks/model_evaluation.py::_resolve_holdout_split` pega o holdout da
`dataset_version` DO PRÓPRIO MODELO. Modelo diferente = prova diferente = ranking
sem sentido. Aqui o holdout é UM, entra por argumento, e vale para as três.

⚠️ A derivação da variante A é exatamente o caminho que a **ADR-0067 PROÍBE** em
produção ("violação nunca nasce do silêncio do detector de presença"). Medi-la
aqui serve para quantificar o preço dela, não para reabrir a porta. A variante C
NÃO é esse caminho: ela exige a evidência positiva da parte do corpo antes de
falar, e quando não a tem, ABSTÉM-SE — que é o que a ADR-0067 manda fazer.

Uso:
    python scripts/ops/ab_ausencia.py \\
        --holdout  /dados/rvb/holdout/test/_annotations.coco.json \\
        --modelo-a /modelos/v-presenca.onnx \\
        --modelo-b /modelos/v-presenca-ausencia.onnx \\
        --modelo-c /modelos/v-partes-corpo.onnx \\
        --pessoa   /modelos/yolox_nano_person.onnx \\
        --treino   /dados/rvb/treino-b/train/_annotations.coco.json \\
        --saida    /tmp/ab_ausencia.md

`--modelo-c` é opcional: sem ele o relatório sai só com A e B.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

# ── Taxonomia da variante C: IMPORTADA de quem a define, nunca recopiada ──────
# Duas cópias divergiram em silêncio e o resultado foi que `conferir_dicionario_c`
# RECUSAVA o dataset que `converter_variante_c.py` produz: ele emite `mao`,
# `regiao_olhos`, `regiao_boca_nariz`, `protetor_auricular`; a tabela daqui
# pedia `mão`, `rosto`, `protetor auricular`. Nenhum dos dois estava "errado" —
# eram duas verdades sobre a mesma taxonomia, e a errada era a que ninguém rodou.
_spec = importlib.util.spec_from_file_location(
    "converter_variante_c", Path(__file__).resolve().parent / "converter_variante_c.py"
)
_vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vc)

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
_MARGEM_EMPATE = 0.05  # diferença menor que 5pp entre variantes = empate técnico

# Critério de sobreposição da variante C — IoMin, ver `sobreposicao()`.
# 0,50 = a caixa MENOR precisa estar metade dentro da maior. A medida é bimodal
# (par verdadeiro ~1,0, par de pessoas diferentes ~0,0), então o veredito é pouco
# sensível ao valor exato; 0,50 é o meio do vale. O relatório varre este limiar
# junto, para a escolha não ficar escondida aqui.
_SOBREPOSICAO_PADRAO = 0.50
_VARREDURA_SOBREPOSICAO = (0.10, 0.25, 0.50, 0.75, 0.90)

# Ordem de simplicidade — empate vence a mais simples, e "simples" precisa ser
# uma ordem declarada, não intuição de quem lê a tabela:
#   A  reusa o estágio 1 que JÁ é servido, zero classe nova, zero anotação nova
#   B  mesma anotação de hoje + as classes "Sem X" que o acervo já tem
#   C  taxonomia inteiramente nova (partes do corpo) + geometria + reanotação
ORDEM_SIMPLICIDADE: tuple[str, ...] = ("A", "B", "C")
ROTULO_VARIANTE = {
    "A": "A · presença derivada",
    "B": "B · classe de ausência",
    "C": "C · sobreposição geométrica",
}

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

# Variante C — classe de ausência → (parte do corpo âncora, EPIs que a cobrem).
# A parte do corpo é a ÂNCORA: sem ela detectada, C não fala (abstenção).
#
# DERIVADO, não digitado: a âncora sai de `_vc.MAPA["Sem X"]` (a caixa de
# ausência vira exatamente a parte do corpo) e os EPIs de `_vc.PROTEGE[parte]`.
# Assim o dicionário nasce compatível com o dataset que o conversor produz, e
# `conferir_dicionario_c` deixa de reprovar por diferença de grafia.
#
# São EPIs no PLURAL porque `regiao_boca_nariz` é coberta por `mascara` E
# `mascara_incorreta`: máscara no queixo é máscara PRESENTE e mal usada — se só
# `mascara` contasse, as 219 caixas de "Uso incorreto" do RVB virariam acusação
# de "Sem mascara", que é o falso positivo que a variante C existe para evitar.
MAPA_SOBREPOSICAO: dict[str, tuple[str, tuple[str, ...]]] = {
    ausencia: (_vc.MAPA[ausencia][0], _vc.PROTEGE[_vc.MAPA[ausencia][0]])
    for ausencia in ("Sem Luvas", "Sem mascara", "Sem Óculos", "Sem protetor de ouvido")
}


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


def abstencoes_a(recortes_por_imagem: dict[int, list[list[dict]]]) -> dict[str, set[int]]:
    """A abstém-se onde o estágio 1 não achou pessoa — não há de quem falar.

    `Uso incorreto de mascara` é abstenção em TODA imagem: A não tem mecanismo
    para vê-la. É mais honesto do que registrar recall 0, que sugeriria que ela
    tentou e errou.
    """
    sem_pessoa = {i for i, recortes in recortes_por_imagem.items() if not recortes}
    abst: dict[str, set[int]] = {c: set(sem_pessoa) for c in MAPA_AUSENCIA.values()}
    abst[CLASSE_SO_DIRETA] = set(recortes_por_imagem)
    return abst


# ── Variante C: sobreposição geométrica ───────────────────────────────────────

def sobreposicao(caixa_a: list[float], caixa_b: list[float]) -> float:
    """IoMin — interseção sobre a área da caixa MENOR. Caixas em COCO [x, y, w, h].

    POR QUE NÃO IoU: a luva fica DENTRO da mão. IoU de uma caixa pequena contida
    numa grande é limitado por área_menor/área_maior, então um par perfeito de
    luva-na-mão pode dar IoU 0,3 e nunca cruzar um limiar honesto. IoU mede
    "são a mesma caixa?"; a pergunta aqui é "estão no mesmo lugar do corpo?".

    POR QUE NÃO CONTENÇÃO DE UM LADO SÓ: a relação de tamanho INVERTE de par para
    par. Luva, máscara e óculos são MENORES que mão e rosto; o abafador de ouvido
    é MAIOR que a orelha e a engole. Qualquer fração fixa "do EPI dentro da parte"
    acerta um par e erra o outro.

    IoMin resolve os dois: vale 1,0 quando a menor está inteiramente dentro da
    maior, não importa QUAL é a menor. E vale 0,0 para a luva de outra pessoa,
    que é o caso que precisa continuar acusando.

    ponytail: o teto conhecido é a caixa espúria minúscula — um falso "luva" de
    10px dentro de uma mão grande pontua 1,0 e silencia a acusação. Erra para o
    lado de NÃO acusar, que é o lado certo num produto de segurança (ADR-0067:
    não acusar quem está conforme). Piso de área na caixa do EPI resolve, quando
    houver medição que mostre que isso acontece.
    """
    ax1, ay1, aw, ah = caixa_a[:4]
    bx1, by1, bw, bh = caixa_b[:4]
    largura = min(ax1 + aw, bx1 + bw) - max(ax1, bx1)
    altura = min(ay1 + ah, by1 + bh) - max(ay1, by1)
    if largura <= 0 or altura <= 0:
        return 0.0
    menor = min(max(0.0, aw) * max(0.0, ah), max(0.0, bw) * max(0.0, bh))
    return (largura * altura) / menor if menor > 0 else 0.0


def acusacoes_c(
    dets_por_imagem: dict[int, list[dict]],
    limiar: float,
    limiar_sobreposicao: float,
) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """Variante C: acusa a parte do corpo que não tem o EPI sobreposto.

    Retorna (acusadas, abstencoes) — e as duas são MUTUAMENTE EXCLUSIVAS por
    classe: ou a âncora apareceu e houve julgamento, ou não apareceu e C se cala.

    Sem a parte do corpo detectada não há acusação NEM inocentação: é ausência de
    evidência, e vira abstenção. Isso cobre os dois casos que não podem virar
    TP/FP — nenhuma parte detectada, e EPI detectado sem a parte (falha do
    detector de parte) — porque os dois caem no mesmo ramo: `partes` vazio.
    """
    acusadas: dict[str, set[int]] = {c: set() for c in CLASSES_AUSENCIA}
    abstencoes: dict[str, set[int]] = {c: set() for c in CLASSES_AUSENCIA}

    for image_id, dets in dets_por_imagem.items():
        caixas: dict[str, list[list[float]]] = {}
        for det in dets:
            if det["confidence"] >= limiar:
                caixas.setdefault(det["class"], []).append(det["bbox"])

        for classe_ausencia, (parte, epis) in MAPA_SOBREPOSICAO.items():
            ancoras = caixas.get(parte, [])
            if not ancoras:
                abstencoes[classe_ausencia].add(image_id)
                continue
            equipamentos = [c for epi in epis for c in caixas.get(epi, [])]
            # Uma âncora descoberta basta para acusar a imagem — e a sobreposição
            # é por PAR, então a luva de uma pessoa não cobre a mão da outra.
            if any(
                not any(
                    sobreposicao(ancora, caixa_epi) >= limiar_sobreposicao
                    for caixa_epi in equipamentos
                )
                for ancora in ancoras
            ):
                acusadas[classe_ausencia].add(image_id)

        # C também não tem mecanismo para "uso incorreto": máscara sobreposta ao
        # rosto não diz se está no queixo. Abstenção, não recall 0.
        abstencoes[CLASSE_SO_DIRETA].add(image_id)

    return acusadas, abstencoes


def conferir_dicionario_c(classes: list[str]) -> None:
    """Recusa rodar C se o dicionário não tem as âncoras e os EPIs esperados.

    Sem isto, um dicionário incompatível faz C abstender-se em 100% das imagens e
    o relatório sairia dizendo "C nunca acusou" — que é indistinguível de "C é
    conservadora". Erro de fiação não pode virar resultado (#542).
    """
    exigidos = {parte for parte, _ in MAPA_SOBREPOSICAO.values()} | {
        epi for _, epis in MAPA_SOBREPOSICAO.values() for epi in epis
    }
    faltando = sorted(exigidos - set(classes))
    if faltando:
        raise SystemExit(
            "Dicionário da variante C incompatível com MAPA_SOBREPOSICAO.\n"
            f"  faltando: {faltando}\n"
            f"  recebido: {classes}\n"
            "Sem estes nomes a C se absteria em todas as imagens e o relatório "
            "leria isso como cautela. Ajuste --classes-c ou MAPA_SOBREPOSICAO."
        )


# ── Contagem ──────────────────────────────────────────────────────────────────

def _razao(numerador: int, denominador: int) -> float | None:
    """None quando não há denominador — nem 0, nem 1.

    Classe sem nenhuma acusação não tem precisão 100% ("acertou todas as zero"):
    não tem precisão nenhuma. O None é o que impede o relatório de premiar
    silêncio.
    """
    return numerador / denominador if denominador else None


def contar(
    acusadas: set[int],
    reais: set[int],
    universo: set[int],
    abstencoes: set[int] | None = None,
) -> dict[str, Any]:
    """TP/FP/FN + precisão/recall de UMA classe, restrito ao universo avaliado.

    ABSTENÇÃO não é TP nem FP: quem não acusou não pode ser julgado por acusação,
    e por isso ela fica FORA do numerador e do denominador da precisão — é assim
    que o "não vi" deixa de ser confundido com "vi e achei tudo certo".

    Ela CONTINUA valendo FN quando a ausência era real: recall responde "das
    ausências reais, quantas o sistema pegou?", e não pegar por cegueira também é
    não pegar. O que o relatório ganha é a decomposição: `fn_por_abstencao` diz
    quanto da perda é "não viu a parte do corpo" em vez de "viu e julgou errado".
    """
    abstidas = (abstencoes or set()) & universo
    acusadas = acusadas & universo
    reais = reais & universo
    tp = len(acusadas & reais)
    fp = len(acusadas - reais)
    perdidas = reais - acusadas
    return {
        "tp": tp,
        "fp": fp,
        "fn": len(perdidas),
        "precisao": _razao(tp, tp + fp),
        "recall": _razao(tp, tp + len(perdidas)),
        "n_acusacoes": tp + fp,
        "n_reais": tp + len(perdidas),
        "abstencoes": len(abstidas),
        "fn_por_abstencao": len(perdidas & abstidas),
        "taxa_abstencao": _razao(len(abstidas), len(universo)),
    }


def medir(
    acusadas: dict[str, set[int]],
    reais: dict[str, set[int]],
    universo: set[int],
    abstencoes: dict[str, set[int]] | None = None,
) -> dict[str, dict[str, Any]]:
    abstencoes = abstencoes or {}
    return {
        classe: contar(
            acusadas.get(classe, set()),
            reais.get(classe, set()),
            universo,
            abstencoes.get(classe, set()),
        )
        for classe in CLASSES_AUSENCIA
    }


def medir_todas(
    recortes_a: dict[int, list[list[dict]]],
    saidas: dict[str, dict[int, list[dict]]],
    reais: dict[str, set[int]],
    universo: set[int],
    limiar: float,
    limiar_sobreposicao: float,
) -> dict[str, dict[str, dict[str, Any]]]:
    """variante → classe → métrica, no MESMO limiar de confiança para todas.

    Um ponto de entrada só para a tabela principal e para cada passo da varredura
    — se cada uma montasse as variantes por conta própria, elas divergiriam.
    """
    medidas: dict[str, dict[str, dict[str, Any]]] = {
        "A": medir(
            acusacoes_a(recortes_a, limiar), reais, universo, abstencoes_a(recortes_a)
        )
    }
    if "B" in saidas:
        medidas["B"] = medir(acusacoes_b(saidas["B"], limiar), reais, universo)
    if "C" in saidas:
        acusadas_c, abstencoes = acusacoes_c(saidas["C"], limiar, limiar_sobreposicao)
        medidas["C"] = medir(acusadas_c, reais, universo, abstencoes)
    return medidas


# ── Veredito ──────────────────────────────────────────────────────────────────

def sustenta_acusacao(m: dict[str, Any]) -> bool:
    """Régua da ADR-0067: precisão ≥ 50% E n suficiente para a precisão significar algo."""
    return (
        m["precisao"] is not None
        and m["precisao"] >= _REGUA_PRECISAO
        and m["n_acusacoes"] >= _N_MINIMO
    )


def vencedor_classe(medidas: dict[str, dict[str, Any]]) -> tuple[str | None, str]:
    """(vencedor, motivo) para UMA classe entre N variantes. None = sem veredito.

    Devolve o vencedor estruturado em vez de uma frase, para `veredito_geral` não
    ter que reconhecer vitória por prefixo de string — decisão que se lê de texto
    é a que quebra em silêncio quando o texto muda.

    Regra do dono: empate técnico → vence a mais simples (ORDEM_SIMPLICIDADE).
    """
    ordem = [v for v in ORDEM_SIMPLICIDADE if v in medidas]
    passam = [v for v in ordem if sustenta_acusacao(medidas[v])]
    if not passam:
        if max(medidas[v]["n_acusacoes"] for v in ordem) < _N_MINIMO:
            detalhe = ", ".join(f"{v}={medidas[v]['n_acusacoes']}" for v in ordem)
            return None, f"n insuficiente ({detalhe})"
        return None, "nenhuma sustenta a régua"
    if len(passam) == 1:
        return passam[0], "única que sustenta a régua"

    finalistas = passam
    for chave in ("precisao", "recall"):
        melhor = max(medidas[v][chave] or 0.0 for v in finalistas)
        restantes = [
            v for v in finalistas if melhor - (medidas[v][chave] or 0.0) <= _MARGEM_EMPATE
        ]
        if len(restantes) == 1:
            return restantes[0], chave
        finalistas = restantes
    return finalistas[0], f"empate técnico com {', '.join(finalistas[1:])} → a mais simples"


def veredito_classe(medidas: dict[str, dict[str, Any]]) -> str:
    vencedor, motivo = vencedor_classe(medidas)
    return f"{vencedor} vence — {motivo}" if vencedor else f"sem veredito — {motivo}"


def veredito_geral(vencedores: dict[str, str | None]) -> str:
    """Conta vitórias por classe. Empate no geral também vence a mais simples."""
    vitorias = {
        v: sum(1 for venc in vencedores.values() if venc == v) for v in ORDEM_SIMPLICIDADE
    }
    placar = ", ".join(f"{v}={n}" for v, n in vitorias.items())
    if not any(vitorias.values()):
        return "SEM VEREDITO — nenhuma classe produziu comparação válida"
    melhor = max(vitorias.values())
    empatadas = [v for v in ORDEM_SIMPLICIDADE if vitorias[v] == melhor]
    if len(empatadas) == 1:
        return f"{empatadas[0]} vence ({placar})"
    return (
        f"EMPATE entre {', '.join(empatadas)} ({placar}) → vence a mais simples: "
        f"{empatadas[0]}"
    )


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
    det_pessoa: Any,
    classe_pessoa: str,
    dets_completos: dict[str, Any],
) -> tuple[set[int], dict[str, dict[int, list[dict]]], dict[int, list[list[dict]]], list[str]]:
    """Roda TODAS as variantes nas MESMAS imagens, na mesma ordem, num só laço.

    `dets_completos` é rótulo → detector que roda no frame INTEIRO (B e C). A é a
    única com pipeline próprio (estágio 1 + recorte), por isso vem separada.

    Retorna (universo, saidas, recortes_a, falhas). Imagem que falha em QUALQUER
    variante sai do universo de TODAS — comparar em provas diferentes é o defeito
    que este script existe para não repetir, e um laço só é o que garante isso
    mecanicamente em vez de por disciplina.
    """
    import cv2  # noqa: PLC0415

    universo: set[int] = set()
    saidas: dict[str, dict[int, list[dict]]] = {rotulo: {} for rotulo in dets_completos}
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
            do_frame = {r: d.predict(frame) for r, d in dets_completos.items()}
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{image['file_name']}: {exc}")
            continue
        universo.add(image["id"])
        recortes_a[image["id"]] = por_recorte
        for rotulo, saida in do_frame.items():
            saidas[rotulo][image["id"]] = saida

    return universo, saidas, recortes_a, falhas


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


def _linha_tabela(rotulo: str, m: dict[str, Any]) -> str:
    return (
        f"| {rotulo} | {m['tp']} | {m['fp']} | {m['fn']} | {_pct(m['precisao'])} "
        f"| {_pct(m['recall'])} | {m['abstencoes']} ({_pct(m['taxa_abstencao'])}) "
        f"| {m['n_acusacoes']} acus. / {m['n_reais']} reais |"
    )


def render(
    ctx: dict[str, Any],
    medidas: dict[str, dict[str, dict[str, Any]]],
    vereditos: dict[str, str],
    vencedores: dict[str, str | None],
    varredura: list[tuple[float, dict[str, dict[str, dict[str, Any]]]]],
    varredura_sobreposicao: list[tuple[float, dict[str, dict[str, Any]]]],
) -> str:
    variantes = [v for v in ORDEM_SIMPLICIDADE if v in medidas]
    p: list[str] = []
    p.append("# A/B de AUSÊNCIA — " + " × ".join(ROTULO_VARIANTE[v] for v in variantes) + "\n")
    p.append(f"- **holdout:** `{ctx['holdout']}` — {ctx['imagens_holdout']} imagens no COCO, "
             f"**{len(ctx['universo'])} avaliadas em TODAS as variantes**")
    p.append(f"- **modelo A (presença):** `{ctx['modelo_a']}` — dicionário: {ctx['classes_a']}")
    p.append(f"- **modelo B (presença+ausência):** `{ctx['modelo_b']}` — "
             f"dicionário: {ctx['classes_b']}")
    if "C" in medidas:
        p.append(f"- **modelo C (parte do corpo + EPI):** `{ctx['modelo_c']}` — "
                 f"dicionário: {ctx['classes_c']}")
        p.append(f"- **critério de sobreposição da C:** IoMin (interseção ÷ área da caixa "
                 f"MENOR) ≥ **{ctx['sobreposicao']:.2f}**. Escolhido porque a relação de "
                 "tamanho inverte de par para par — a luva é menor que a mão, o abafador é "
                 "maior que a orelha — e IoU puro nunca cruza um limiar honesto quando uma "
                 "caixa está contida na outra.")
        p.append("- **pares âncora→EPI da C:** " + "; ".join(
            f"`{parte}`→`{epi}` ⇒ {classe}"
            for classe, (parte, epi) in MAPA_SOBREPOSICAO.items()))
    p.append(f"- **estágio 1 (pessoa):** `{ctx['pessoa']}` — classe `{ctx['classe_pessoa']}`, "
             f"limiar {ctx['limiar_pessoa']:.2f}, margem de recorte "
             f"{_MARGEM_X:.0%}×{_MARGEM_Y:.0%} (a mesma do edge)")
    p.append(f"- **limiar aplicado:** {ctx['limiar']:.2f} — **o MESMO para todas as variantes**")
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

    p.append("## Como ler a coluna abstenção\n")
    p.append(
        "Abstenção é a imagem em que a variante **não tinha como falar** — a A quando o "
        "estágio 1 não achou pessoa, a C quando a parte do corpo âncora não foi detectada "
        "(inclusive quando o EPI apareceu e a parte não: falha do detector de parte). "
        "Ela **não entra em TP nem em FP**, porque não houve acusação para julgar. "
        "Continua contando FN quando a ausência era real — não pegar por cegueira também é "
        "não pegar — e `FN por abstenção` separa o quanto da perda é 'não viu' em vez de "
        "'viu e julgou errado'. A variante B não tem abstenção: o silêncio dela é "
        "indistinguível de inocentar.\n")

    p.append(f"## Por classe de ausência (limiar {ctx['limiar']:.2f})\n")
    for classe in CLASSES_AUSENCIA:
        p.append(f"### {classe}\n")
        p.append("| variante | TP | FP | FN | precisão | recall | abstenção | n |")
        p.append("|---|---:|---:|---:|---:|---:|---:|---|")
        for v in variantes:
            p.append(_linha_tabela(ROTULO_VARIANTE[v], medidas[v][classe]))
        p.append("")
        for v in variantes:
            m = medidas[v][classe]
            if sustenta_acusacao(m):
                p.append(f"- {v}: **sustenta acusação** "
                         f"(precisão {_pct(m['precisao'])} ≥ {_REGUA_PRECISAO:.0%}, "
                         f"n={m['n_acusacoes']} ≥ {_N_MINIMO}).")
            elif m["n_acusacoes"] == 0 and m["abstencoes"] == len(ctx["universo"]):
                p.append(f"- {v}: **absteve-se em 100% das imagens** — a âncora nunca "
                         "apareceu, então não houve o que julgar. Isso NÃO é cautela "
                         "medida: é ausência de medida.")
            elif m["n_acusacoes"] < _N_MINIMO:
                p.append(f"- {v}: **n insuficiente** (n={m['n_acusacoes']} < {_N_MINIMO}) — "
                         "precisão sem n não é medida (ADR-0067).")
            else:
                p.append(f"- {v}: **NÃO sustenta acusação** — precisão "
                         f"{_pct(m['precisao'])} < {_REGUA_PRECISAO:.0%} (ADR-0067).")
            if m["fn_por_abstencao"]:
                p.append(f"  - {m['fn_por_abstencao']} de {m['fn']} FN vieram de ABSTENÇÃO "
                         "(não viu a âncora), não de julgamento errado.")
        p.append(f"- **veredito:** {vereditos[classe]}\n")

    p.append("## Varredura de limiares de confiança (todas as variantes)\n")
    p.append("A regra de justiça é limiar ÚNICO. A varredura está aqui para a escolha "
             "ficar explícita — não para cada variante escolher o seu.\n")
    p.append("| limiar | classe | " + " | ".join(
        f"{v} precisão/recall (n)" for v in variantes) + " |")
    p.append("|---:|---|" + "---|" * len(variantes))
    for limiar, med in varredura:
        for classe in CLASSES_AUSENCIA:
            celulas = " | ".join(
                f"{_pct(med[v][classe]['precisao'])} / {_pct(med[v][classe]['recall'])} "
                f"({med[v][classe]['n_acusacoes']})" for v in variantes
            )
            p.append(f"| {limiar:.2f} | {classe} | {celulas} |")
    p.append("")

    if varredura_sobreposicao:
        p.append(f"## Varredura do limiar de SOBREPOSIÇÃO da variante C "
                 f"(confiança fixa em {ctx['limiar']:.2f})\n")
        p.append("O critério geométrico é um segundo botão, e um botão escolhido em silêncio "
                 "é um número escondido. Aqui está a sensibilidade dele.\n")
        p.append("| IoMin | classe | TP | FP | FN | precisão | recall |")
        p.append("|---:|---|---:|---:|---:|---:|---:|")
        for valor, med in varredura_sobreposicao:
            for classe in MAPA_SOBREPOSICAO:
                m = med[classe]
                p.append(f"| {valor:.2f} | {classe} | {m['tp']} | {m['fp']} | {m['fn']} "
                         f"| {_pct(m['precisao'])} | {_pct(m['recall'])} |")
        p.append("")

    p.append("## Veredito geral\n")
    p.append(f"**{veredito_geral(vencedores)}**\n")
    p.append(f"Empate técnico (< {_MARGEM_EMPATE:.0%} de diferença em precisão e recall) conta "
             "como empate, e empate vence a mais simples, na ordem declarada "
             f"{' < '.join(ORDEM_SIMPLICIDADE)}: A reusa o estágio 1 já servido; B só acrescenta "
             "classes ao que já se anota; C exige uma taxonomia nova de partes do corpo.\n")

    p.append("## O que este relatório NÃO mediu\n")
    p.append(
        "- **Geometria da acusação.** A comparação é por decisão (imagem × classe), não por "
        "caixa. Uma imagem com três pessoas conta TP mesmo se a variante acusou a pessoa "
        "errada. Vale inclusive para a C, que casa PARES corretamente mas é pontuada por "
        "imagem.\n"
        "- **Botas.** Não existe classe `Sem Botas` no gabarito; sem gabarito não há o que "
        "julgar, então ela ficou fora — não é omissão, é falta de verdade. A C detecta botas "
        "e mesmo assim não é pontuada nelas.\n"
        f"- **`{CLASSE_SO_DIRETA}` por A e por C.** Nenhuma das duas tem mecanismo: silêncio "
        "não distingue 'sem máscara' de 'máscara no queixo', e máscara sobreposta ao rosto "
        "também não. As duas se ABSTÊM — que é diferente de errar.\n"
        "- **Persistência temporal e zona.** A ADR-0067 exige as duas antes de qualquer "
        "acusação virar alerta. Aqui cada frame é julgado sozinho.\n"
        "- **A caixa espúria minúscula da C.** Um falso EPI de poucos pixels dentro da âncora "
        "pontua IoMin 1,0 e silencia a acusação. Erra para o lado de não acusar; um piso de "
        "área resolveria, se a medição mostrar que acontece.\n"
        "- **Custo e latência.** A e C custam mais que B por frame; isso não entra na conta.\n"
        f"- **O efeito do NMS por limiar.** A inferência rodou uma vez a {_LIMIAR_COLETA:.2f} e a "
        "varredura decidiu em cima dela; caixa suprimida na coleta não reaparece num limiar "
        "mais alto. Vale igual para todas, mas não é o mesmo que reinferir.\n"
        "- **O que o anotador não desenhou.** Imagem sem anotação `Sem X` é tratada como "
        "'não havia ausência'. Ausência real e não anotada aparece como FP da variante.\n"
        "- **A viabilidade da conversão das anotações para a taxonomia C.** Isso é medido "
        "fora daqui; se a conversão não se sustentar, a C não é usada — e nada nesta régua "
        "muda por causa disso.\n"
        f"- **{len(ctx['falhas'])} imagem(ns)** que falharam na leitura — fora do universo de "
        "TODAS as variantes.\n"
        "- **A legitimidade da variante A em produção.** A ADR-0067 já a proíbe. Este número "
        "mede o preço dela, não a autoriza.\n"
    )
    return "\n".join(p)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_classes(valor: str | None) -> list[str] | None:
    return [c.strip() for c in valor.split(",")] if valor else None


def montar_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="A/B no nível da decisão entre detector de presença (A), detector com "
                    "classes de ausência (B) e detector de parte do corpo + EPI (C).",
    )
    ap.add_argument("--holdout", required=True, type=Path,
                    help="COCO do holdout congelado (_annotations.coco.json); as imagens "
                         "ficam ao lado dele")
    ap.add_argument("--modelo-a", required=True, help="ONNX da variante A (presença)")
    ap.add_argument("--modelo-b", required=True, help="ONNX da variante B (presença+ausência)")
    ap.add_argument("--modelo-c", help="ONNX da variante C (parte do corpo + EPI) — opcional; "
                                       "sem ele o relatório sai só com A e B")
    ap.add_argument("--pessoa", required=True, help="ONNX do detector de pessoa (estágio 1)")
    ap.add_argument("--treino", required=True, nargs="+", type=Path,
                    help="COCO(s) do treino das variantes — a guarda de disjunção NÃO é "
                         "opcional: sem ela o A/B pode estar medindo o que a B decorou")
    ap.add_argument("--limiar", type=float, default=_LIMIAR_PADRAO,
                    help=f"confiança mínima, a MESMA para todas as variantes "
                         f"(padrão {_LIMIAR_PADRAO} — melhor limiar do #536, ADR-0067)")
    ap.add_argument("--sobreposicao", type=float, default=_SOBREPOSICAO_PADRAO,
                    help="IoMin mínimo (interseção ÷ área da caixa MENOR) para considerar o "
                         f"EPI sobreposto à parte do corpo na variante C (padrão "
                         f"{_SOBREPOSICAO_PADRAO}: a medida é bimodal — par verdadeiro perto "
                         "de 1,0, pessoas diferentes perto de 0,0 — então 0,50 é o meio do "
                         "vale; a varredura deste valor sai no relatório)")
    ap.add_argument("--saida", required=True, type=Path, help="caminho do relatório .md")
    ap.add_argument("--backend", default="yolox_onnx",
                    help="backend dos detectores A, B e C (yolox_onnx | rfdetr_onnx)")
    ap.add_argument("--backend-pessoa", default="yolox_onnx", help="backend do estágio 1")
    ap.add_argument("--classe-pessoa", default="person",
                    help="nome da classe de pessoa no dicionário do estágio 1")
    ap.add_argument("--limiar-pessoa", type=float, default=0.25,
                    help="confiança mínima do estágio 1 (padrão 0.25)")
    ap.add_argument("--classes-a", help="dicionário do modelo A na ORDEM DO ÍNDICE, separado "
                                       "por vírgula (padrão: categorias do holdout)")
    ap.add_argument("--classes-b", help="idem para o modelo B")
    ap.add_argument("--classes-c", help="idem para o modelo C — precisa conter os nomes de "
                                        "MAPA_SOBREPOSICAO, senão o script recusa rodar")
    ap.add_argument("--varredura", default=",".join(f"{v:.2f}" for v in _VARREDURA_PADRAO),
                    help="limiares de confiança da varredura, separados por vírgula")
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
    classes_c = _parse_classes(args.classes_c) or classes_holdout
    if args.modelo_c:
        conferir_dicionario_c(classes_c)

    det_a = _construir_detector(args.backend, args.modelo_a, classes_a, _LIMIAR_COLETA)
    det_pessoa = _construir_detector(
        args.backend_pessoa, args.pessoa, None, args.limiar_pessoa
    )
    completos = {
        "B": _construir_detector(args.backend, args.modelo_b, classes_b, _LIMIAR_COLETA)
    }
    if args.modelo_c:
        completos["C"] = _construir_detector(
            args.backend, args.modelo_c, classes_c, _LIMIAR_COLETA
        )

    universo, saidas, recortes_a, falhas = inferir_holdout(
        coco, base_dir, det_a, det_pessoa, args.classe_pessoa, completos
    )
    if not universo:
        raise SystemExit(
            "Nenhuma imagem do holdout foi avaliada — gravar isto como relatório seria "
            f"registrar ausência de medida como medida. Falhas: {falhas[:5]}"
        )

    reais = ausencias_reais(coco)
    medidas = medir_todas(
        recortes_a, saidas, reais, universo, args.limiar, args.sobreposicao
    )
    vencedores: dict[str, str | None] = {}
    vereditos: dict[str, str] = {}
    for classe in CLASSES_AUSENCIA:
        por_variante = {v: medidas[v][classe] for v in medidas}
        vencedores[classe] = vencedor_classe(por_variante)[0]
        vereditos[classe] = veredito_classe(por_variante)

    varredura = [
        (
            limiar,
            medir_todas(recortes_a, saidas, reais, universo, limiar, args.sobreposicao),
        )
        for limiar in (float(v) for v in args.varredura.split(","))
    ]
    varredura_sobreposicao = [
        (
            valor,
            medir_todas(recortes_a, saidas, reais, universo, args.limiar, valor)["C"],
        )
        for valor in _VARREDURA_SOBREPOSICAO
    ] if "C" in medidas else []

    ctx = {
        "holdout": str(args.holdout), "modelo_a": args.modelo_a, "modelo_b": args.modelo_b,
        "modelo_c": args.modelo_c, "pessoa": args.pessoa,
        "classe_pessoa": args.classe_pessoa, "limiar_pessoa": args.limiar_pessoa,
        "limiar": args.limiar, "sobreposicao": args.sobreposicao, "backend": args.backend,
        "classes_a": classes_a, "classes_b": classes_b, "classes_c": classes_c,
        "universo": universo, "imagens_holdout": len(coco.get("images", [])),
        "falhas": falhas, "guarda": guarda,
    }
    args.saida.write_text(
        render(ctx, medidas, vereditos, vencedores, varredura, varredura_sobreposicao),
        encoding="utf-8",
    )
    print(f"[ab_ausencia] relatório em {args.saida}")
    print(f"[ab_ausencia] veredito geral: {veredito_geral(vencedores)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
