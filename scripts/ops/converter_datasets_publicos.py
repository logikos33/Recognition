#!/usr/bin/env python3
"""converter_datasets_publicos.py — classes dos datasets públicos → taxonomia RVB.

Insumo: o que `scripts/ops/baixar_datasets_publicos.py` deixou no disco.
Saída: UM COCO POR VARIANTE, do MESMO download. As três não se misturam.

    Variante A  presença (5 classes). Ausência NÃO é classe do detector.
    Variante B  presença + ausência como classe ("Sem Luvas", ...).
    Variante C  parte do corpo + EPI; ausência sai depois por sobreposição.

────────────────────────────────────────────────────────────────────────────────
ONDE ESTE TRABALHO PODE MENTIR EM SILÊNCIO, E AS TRÊS TRAVAS

1. **Encher volume com "parecido".** Classe pública sem correspondente nosso é
   DESCARTADA, com motivo escrito, e o descarte é CONTADO e aparece no
   relatório. Nunca some sem número.

   Regra que decidiu os casos duvidosos: **quando o próprio dataset público
   distingue duas classes, colapsar as duas numa nossa destrói a distinção que
   ele pagou para fazer.** O R6 tem `boots` E `shoes` separados, e `glasses` E
   `goggles` separados. Então `Shoe`/`shoes`/`glasses` são descartados e só
   `boots`/`goggles` entram. É por isso que Botas ganha pouco do público — e
   isso corrige a §4 da auditoria, que contava `Shoe` como cobertura de Botas.

2. **Misturar as variantes.** `no glove` é AUSÊNCIA. Sob ADR-0065/0067 ela não é
   classe de detector na A, é classe na B, e é PARTE DO CORPO na C. O mesmo
   arquivo baixado produz três saídas diferentes; `--variante` é obrigatório e
   não tem padrão.

3. **Inventar nome de classe.** A ausência no RVB NÃO é "Sem " + o nome do EPI:
   `Protetor auditivo` vira `Sem protetor de ouvido`. Um f-string ingênuo
   produziria `Sem Protetor auditivo`, que não existe no banco e criaria uma
   6ª classe fantasma. Por isso `AUSENCIA` é tabela explícita, medida:

       select class_name, count(*) from public.frame_annotations group by 1;
       -- 3087 Protetor auditivo · 972 mascara · 829 Botas · 635 Óculos
       -- 536 Sem protetor de ouvido · 363 Sem Luvas · 304 Luvas
       -- 294 Sem mascara · 253 Uso incorreto de mascara · 210 Sem Óculos
       -- 1 Sem botas   (medido no DEV em 2026-09-02)

A taxonomia da variante C é IMPORTADA de `converter_variante_c.py`, não
recopiada: se lá mudar, aqui muda junto. Duas cópias divergem em silêncio.

────────────────────────────────────────────────────────────────────────────────
USO

    # a tabela de mapeamento proposta (não precisa de dado nenhum)
    python3 scripts/ops/converter_datasets_publicos.py mapa

    # converter (dry-run por padrão)
    python3 scripts/ops/converter_datasets_publicos.py converter \\
        --entrada /dados/publicos --variante a
    ... --saida /dados/publicos-variante-a --gravar

    python3 scripts/ops/converter_datasets_publicos.py autoteste
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

# ── Taxonomia da variante C: importada, nunca recopiada ──────────────────────
_spec = importlib.util.spec_from_file_location(
    "converter_variante_c", Path(__file__).resolve().parent / "converter_variante_c.py"
)
_vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vc)

#: nossas 5 classes de PRESENÇA, grafadas como estão no banco.
PRESENCA = ("Protetor auditivo", "mascara", "Botas", "Óculos", "Luvas")

#: EPI → nome EXATO da classe de ausência no RVB. Irregular de propósito: é o
#: que o banco tem, não o que seria bonito. (`Sem botas` tem n=1 no RVB; entra
#: porque o público a alimenta, e é justamente onde o público serve.)
AUSENCIA = {
    "Protetor auditivo": "Sem protetor de ouvido",
    "mascara": "Sem mascara",
    "Botas": "Sem botas",
    "Óculos": "Sem Óculos",
    "Luvas": "Sem Luvas",
}

#: classes de PARTE DO CORPO que só o dado público tem. NÃO existem no RVB —
#: são de pré-treino, e o fino no RVB não as reforça. Declarado, não escondido.
PARTES_SO_PUBLICAS = {
    "pessoa": "o RVB tem ZERO anotação de pessoa (medido); aqui a caixa é real",
    "rosto": (
        "`Human face` é o rosto INTEIRO. NÃO é `regiao_olhos` nem "
        "`regiao_boca_nariz`: converter_variante_c.py mediu as duas como "
        "geometricamente distintas (KS D=0,518 na razão de aspecto; IoU médio "
        "0,078 em 63 frames com as duas no mesmo rosto). Colapsar mentiria."
    ),
}

VARIANTES = ("a", "b", "c")


def classes_da_variante(variante: str) -> list[str]:
    if variante == "a":
        return sorted(PRESENCA)
    if variante == "b":
        return sorted([*PRESENCA, *AUSENCIA.values()])
    return sorted([*_vc.CLASSES, *PARTES_SO_PUBLICAS])


# ── O mapeamento, por dataset ────────────────────────────────────────────────
# Cada entrada é (tipo, alvo):
#   ("presenca", <EPI nosso>)  ("ausencia", <EPI nosso>)
#   ("parte",    <classe de parte da variante C>)
#   ("fora",     <motivo do descarte>)
#
# O que cada tipo emite POR VARIANTE é regra única (`destinos()`), não uma
# terceira coluna por classe — três colunas escritas à mão é onde uma delas fica
# errada sem ninguém ver.

MAPA: dict[str, dict[str, tuple[str, str]]] = {
    "r1": {  # Detector_EPP_Earmuff_Gloves_Mask — 17.359 img, CC BY 4.0
        "mask": ("presenca", "mascara"),
        "earmuff": ("presenca", "Protetor auditivo"),
        "gloves": ("presenca", "Luvas"),
        "no mask": ("ausencia", "mascara"),
        "no earmuff": ("ausencia", "Protetor auditivo"),
        "no glove": ("ausencia", "Luvas"),
    },
    "r2": {  # Safety_PPE — 6.629 img, CC BY 4.0
        "Glove": ("presenca", "Luvas"),
        "Goggles": ("presenca", "Óculos"),
        "No_Glove": ("ausencia", "Luvas"),
        "No_Goggles": ("ausencia", "Óculos"),
        "Person": ("parte", "pessoa"),
        "Helmet": ("fora", "capacete está FORA da taxonomia RVB de 6 classes"),
        "No_Helmet": ("fora", "idem Helmet"),
        "Shoe": (
            "fora",
            "`Shoe` genérico ≠ `Botas` de segurança. O R6 separa `boots` de "
            "`shoes`, provando que a distinção existe; colapsar encheria Botas "
            "de sapato comum. Reverter só depois de olhar o dado.",
        ),
        "No_Shoe": ("fora", "par do `Shoe`, descartado junto"),
        "Safety_Harness": ("fora", "cinto/talabarte fora da taxonomia RVB"),
        "No_Harness": ("fora", "idem Safety_Harness"),
        "No_BreathingApparatus": (
            "fora",
            "respirador/SCBA não é a `mascara` do RVB e não dá para confirmar "
            "sem ver o dado; mapear seria adivinhar",
        ),
    },
    "r3": {  # Safety Gloves — CC BY 4.0
        "Gloves": ("presenca", "Luvas"),
        "NO-Gloves": ("ausencia", "Luvas"),
    },
    "r6": {  # HAND NO GLOVES — 200 img, CC0
        "hand_glove": ("presenca", "Luvas"),
        "hand_noglove": ("ausencia", "Luvas"),
        "face_mask": ("presenca", "mascara"),
        "face_nomask": ("ausencia", "mascara"),
        "goggles": ("presenca", "Óculos"),
        "boots": ("presenca", "Botas"),
        "person": ("parte", "pessoa"),
        "glasses": (
            "fora",
            "óculos comuns ≠ `Óculos` de segurança; o R6 separa `glasses` de "
            "`goggles`, então colapsar destrói a distinção que ele fez",
        ),
        "shoes": ("fora", "mesma regra do `Shoe`: sapato comum ≠ Botas"),
        "vest": ("fora", "colete está FORA da taxonomia RVB de 6 classes"),
        "head_helmet": ("fora", "capacete fora da taxonomia RVB"),
        "head_nohelmet": ("fora", "capacete fora da taxonomia RVB"),
    },
    "oid": {  # Open Images V7 — anotações CC BY 4.0 (Google)
        "Human hand": ("parte", "mao"),
        "Human ear": ("parte", "orelha"),
        "Human face": ("parte", "rosto"),
    },
}


def destinos(tipo: str, alvo: str, variante: str) -> tuple[str, ...]:
    """A regra ADR-0065/0067 escrita UMA vez. Devolve () = descarta.

    presença de X : A→(X)  B→(X)  C→ o que converter_variante_c emite para X
    ausência de X : A→()   B→("Sem X" grafado como no banco)  C→ a parte do corpo
    parte P       : A→()   B→()   C→(P)
    fora          : ()     em todas
    """
    if tipo == "fora":
        return ()
    if tipo == "presenca":
        if variante in ("a", "b"):
            return (alvo,)
        return _vc.MAPA[alvo]
    if tipo == "ausencia":
        if variante == "a":
            return ()  # ausência NÃO é classe do detector na variante A
        nome = AUSENCIA[alvo]
        if variante == "b":
            return (nome,)
        return _vc.MAPA.get(nome, ())  # C: só a parte do corpo, nunca o EPI
    if tipo == "parte":
        return (alvo,) if variante == "c" else ()
    raise ValueError(f"tipo desconhecido: {tipo!r}")


# ── Conversão (única lógica; os modos abaixo só fazem I/O) ───────────────────
def converter(
    anotacoes: list[dict], dataset: str, variante: str
) -> tuple[list[dict], dict]:
    """Anotações de um dataset público → taxonomia RVB da `variante`.

    `anotacoes`: [{'class_name', 'image_id', 'bbox'[x,y,w,h]}].
    Devolve (anotações novas, contas). `contas['por_classe']` traz, POR CLASSE
    PÚBLICA, quantas entraram, quantas saíram e quantas foram descartadas — o
    descarte é contado sempre, inclusive o descarte "legítimo" da variante.
    """
    if variante not in VARIANTES:
        raise ValueError(f"variante deve ser uma de {VARIANTES}, veio {variante!r}")
    mapa = MAPA[dataset]
    classes = classes_da_variante(variante)

    saida: list[dict] = []
    por_classe: dict[str, dict] = {}
    desconhecidas: dict[str, int] = {}
    proximo = 1

    for ann in anotacoes:
        nome = ann["class_name"]
        regra = mapa.get(nome)
        if regra is None:
            # classe que o dataset tem e a nossa tabela não conhece. Não é
            # descarte silencioso: é sinal de que o export mudou.
            desconhecidas[nome] = desconhecidas.get(nome, 0) + 1
            continue
        tipo, alvo = regra
        alvos = destinos(tipo, alvo, variante)
        conta = por_classe.setdefault(
            nome, {"tipo": tipo, "alvo": alvo, "entrada": 0, "emitidas": 0, "descartadas": 0}
        )
        conta["entrada"] += 1
        if not alvos:
            conta["descartadas"] += 1
            conta["motivo"] = (
                alvo if tipo == "fora" else f"tipo `{tipo}` não é classe da variante {variante.upper()}"
            )
            continue
        for destino in alvos:
            saida.append(
                {
                    "id": proximo,
                    "image_id": ann["image_id"],
                    "category_id": classes.index(destino) + 1,  # +1: id 0 é a âncora
                    "category_name": destino,
                    "bbox": list(ann["bbox"]),
                    "area": round(ann["bbox"][2] * ann["bbox"][3], 2),
                    "iscrowd": 0,
                }
            )
            proximo += 1
            conta["emitidas"] += 1

    contas = {
        "dataset": dataset,
        "variante": variante,
        "entrada": len(anotacoes),
        "emitidas": len(saida),
        "descartadas": sum(c["descartadas"] for c in por_classe.values()),
        "por_classe": por_classe,
        "classes_desconhecidas": desconhecidas,
    }
    return saida, contas


def categorias(variante: str) -> list[dict]:
    """Categorias COCO, com a âncora id:0 que o RF-DETR do produto espera."""
    return [{"id": 0, "name": _vc.ANCORA, "supercategory": "none"}] + [
        {"id": i + 1, "name": c, "supercategory": _vc.ANCORA}
        for i, c in enumerate(classes_da_variante(variante))
    ]


# ── Leitura dos formatos baixados ────────────────────────────────────────────
def le_coco(raiz: Path) -> tuple[list[dict], list[dict]]:
    """Export COCO do Roboflow: <split>/_annotations.coco.json. Resolve class_name."""
    anotacoes, imagens = [], []
    desloc = 0
    for arq in sorted(raiz.rglob("_annotations.coco.json")):
        doc = json.loads(arq.read_text(encoding="utf-8"))
        nome_de = {c["id"]: c["name"] for c in doc.get("categories", [])}
        remap = {}
        for img in doc.get("images", []):
            novo = img["id"] + desloc
            remap[img["id"]] = novo
            imagens.append({**img, "id": novo, "file_name": f"{arq.parent.name}/{img['file_name']}"})
        for a in doc.get("annotations", []):
            anotacoes.append(
                {
                    "class_name": nome_de.get(a["category_id"], f"<id {a['category_id']}>"),
                    "image_id": remap.get(a["image_id"], a["image_id"]),
                    "bbox": a["bbox"],
                }
            )
        desloc += max((i["id"] for i in doc.get("images", [])), default=0) + 1
    return anotacoes, imagens


def le_oid(raiz: Path) -> tuple[list[dict], list[dict]]:
    """CSVs já filtrados por baixar_datasets_publicos.py (*-3classes.csv).

    O Open Images guarda a caixa NORMALIZADA (XMin..YMax em 0..1). Sem o tamanho
    real da imagem não dá para converter para pixel — então a bbox sai
    normalizada e o COCO sai com `bbox_normalizada: true`. Fingir pixel aqui
    seria inventar geometria.
    """
    anotacoes, imagens, vistos = [], [], {}
    for arq in sorted(raiz.glob("*-3classes.csv")):
        with arq.open(newline="") as fh:
            for linha in csv.DictReader(fh):
                chave = f"{linha['Split']}/{linha['ImageID']}"
                if chave not in vistos:
                    vistos[chave] = len(vistos) + 1
                    imagens.append({"id": vistos[chave], "file_name": f"images/{chave}.jpg"})
                x0, x1 = float(linha["XMin"]), float(linha["XMax"])
                y0, y1 = float(linha["YMin"]), float(linha["YMax"])
                anotacoes.append(
                    {
                        "class_name": linha["ClassName"],
                        "image_id": vistos[chave],
                        "bbox": [x0, y0, x1 - x0, y1 - y0],
                    }
                )
    return anotacoes, imagens


# ── Modos ────────────────────────────────────────────────────────────────────
def _linha(nome: str, conta: dict, largura: int) -> str:
    alvos = destinos(conta["tipo"], conta["alvo"], conta["variante"])
    destino = " + ".join(alvos) if alvos else "— DESCARTADA —"
    return (
        f"  {nome:<{largura}} → {destino:<34} "
        f"n={conta['entrada']:<7} emitidas={conta['emitidas']:<7} "
        f"descartadas={conta['descartadas']}"
    )


def relatorio(contas: dict) -> str:
    """Tabela classe_publica → nossa_classe | n_caixas | descartadas."""
    linhas = [
        f"── {contas['dataset']} · variante {contas['variante'].upper()} "
        f"─ entrada {contas['entrada']} · emitidas {contas['emitidas']} "
        f"· descartadas {contas['descartadas']}"
    ]
    largura = max((len(n) for n in contas["por_classe"]), default=10)
    for nome, c in sorted(contas["por_classe"].items(), key=lambda kv: -kv[1]["entrada"]):
        linhas.append(_linha(nome, {**c, "variante": contas["variante"]}, largura))
        if c.get("motivo"):
            linhas.append(f"  {'':<{largura}}   motivo: {c['motivo']}")
    for nome, n in sorted(contas["classes_desconhecidas"].items(), key=lambda kv: -kv[1]):
        linhas.append(f"  ⚠️  {nome!r}: {n} caixas — CLASSE FORA DA TABELA, revisar o mapa")
    return "\n".join(linhas)


def modo_mapa() -> int:
    """A tabela proposta, sem precisar de dado. É a entrega revisável."""
    for variante in VARIANTES:
        print(f"\n{'=' * 78}\nVARIANTE {variante.upper()} — {len(classes_da_variante(variante))} classes")
        print(f"  {', '.join(classes_da_variante(variante))}\n")
        for dataset, mapa in MAPA.items():
            largura = max(len(n) for n in mapa)
            print(f"  [{dataset}]")
            for nome, (tipo, alvo) in mapa.items():
                alvos = destinos(tipo, alvo, variante)
                d = " + ".join(alvos) if alvos else "— DESCARTADA —"
                sufixo = f"   ({alvo})" if tipo == "fora" else ""
                print(f"    {nome:<{largura}} [{tipo:<8}] → {d}{sufixo}")
            print()
    print("\nSó a licença é gate; as contagens acima são 0 até o download existir.")
    return 0


def modo_converter(entrada: Path, saida: Path | None, variante: str, gravar: bool) -> int:
    if gravar and not saida:
        print("ERRO: --gravar exige --saida.")
        return 1
    if gravar and saida and saida.resolve() == entrada.resolve():
        print("ERRO: --saida não pode ser a --entrada (o download é intocável).")
        return 1

    total = {"entrada": 0, "emitidas": 0, "descartadas": 0}
    achou = False
    for dataset in MAPA:
        raiz = entrada / dataset
        if not raiz.is_dir():
            print(f"[{dataset}] não baixado — pulando (rode baixar_datasets_publicos.py)")
            continue
        anotacoes, imagens = (le_oid if dataset == "oid" else le_coco)(raiz)
        if not anotacoes:
            print(f"[{dataset}] diretório existe mas sem anotações legíveis — pulando")
            continue
        achou = True
        novas, contas = converter(anotacoes, dataset, variante)
        print(relatorio(contas), "\n")
        for k in total:
            total[k] += contas[k]

        if gravar:
            alvo = saida / dataset
            alvo.mkdir(parents=True, exist_ok=True)
            doc = {
                "info": {
                    "description": f"{dataset} remapeado para a taxonomia RVB, variante {variante.upper()}",
                    "origem": str(raiz),
                    "bbox_normalizada": dataset == "oid",
                },
                "images": imagens,
                "annotations": novas,
                "categories": categorias(variante),
            }
            (alvo / "_annotations.coco.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8"
            )
            (alvo / "RELATORIO_CONVERSAO.txt").write_text(relatorio(contas) + "\n", encoding="utf-8")
            # a procedência anda junto do derivado: CC BY exige crédito também
            # no derivado, e um COCO órfão de licença é um COCO inutilizável.
            for nome in ("PROCEDENCIA.json", "ATRIBUICAO.txt"):
                if (raiz / nome).exists():
                    (alvo / nome).write_text((raiz / nome).read_text(encoding="utf-8"), encoding="utf-8")
                else:
                    print(f"    ⚠️  {dataset}: sem {nome} na entrada — derivado sai SEM atribuição")

    if not achou:
        print("\nNada convertido: nenhum dataset no disco.")
        return 1
    print(f"TOTAL variante {variante.upper()}: entrada {total['entrada']} · "
          f"emitidas {total['emitidas']} · descartadas {total['descartadas']}")
    if not gravar:
        print("(dry-run — nada foi escrito. Use --gravar --saida DIR)")
    return 0


def autoteste() -> int:
    """Checagem que não precisa de download nem de banco."""
    # a variante C daqui é a MESMA de converter_variante_c, mais as extras declaradas
    assert set(classes_da_variante("c")) == set(_vc.CLASSES) | set(PARTES_SO_PUBLICAS)
    # ausência nunca emite o EPI na C (senão a derivação leria conformidade)
    for nossa in AUSENCIA:
        assert destinos("ausencia", nossa, "c") == _vc.MAPA.get(AUSENCIA[nossa], ())
        for d in destinos("ausencia", nossa, "c"):
            assert d in _vc.PROTEGE, (nossa, d)
    # todo alvo de todo dataset existe na variante de destino
    for dataset, mapa in MAPA.items():
        for nome, (tipo, alvo) in mapa.items():
            for variante in VARIANTES:
                for d in destinos(tipo, alvo, variante):
                    assert d in classes_da_variante(variante), (dataset, nome, variante, d)
    print("autoteste: OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="modo", required=True)
    sub.add_parser("mapa", help="imprime a tabela de mapeamento das 3 variantes")
    c = sub.add_parser("converter", help="converte o que está no disco (dry-run por padrão)")
    c.add_argument("--entrada", type=Path, required=True, help="destino do baixar_datasets_publicos")
    c.add_argument("--variante", choices=VARIANTES, required=True)
    c.add_argument("--saida", type=Path)
    c.add_argument("--gravar", action="store_true")
    sub.add_parser("autoteste")
    args = p.parse_args()
    if args.modo == "mapa":
        return modo_mapa()
    if args.modo == "autoteste":
        return autoteste()
    return modo_converter(args.entrada, args.saida, args.variante, args.gravar)


if __name__ == "__main__":
    sys.exit(main())
