#!/usr/bin/env python3
"""Régua do classificador de recorte: precisão, recall e ABSTENÇÃO por classe.

A ADR-0067 exige precisão ≥ 50% em campo virgem para uma classe entrar em
produção. Esta régua é quem decide, e ela reporta três números por classe, não
um:

  · precisão — dos que o modelo chamou de X, quantos eram X;
  · recall   — dos que eram X, quantos o modelo pegou;
  · abstenção— quantos ele se recusou a julgar.

Sem a terceira coluna a régua mente por omissão: um modelo que se abstém em 90%
dos casos e acerta os 10% restantes teria precisão excelente e utilidade zero.
É o mesmo vício do limiar alto que o A/B do #536 pegou — "prever menos erra
menos" não é qualidade.

E reporta POR CÂMERA. 58% dos frames vêm de 3 câmeras; a média esconde isso.
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("regua")

#: Limiares de confiança varridos. Abaixo do limiar, o veredito é ABSTENÇÃO.
LIMIARES = (0.00, 0.50, 0.60, 0.70, 0.80, 0.90)

#: Piso da ADR-0067 para uma classe poder gerar violação em produção.
PRECISAO_MINIMA = 0.50

#: Abaixo disto o `n` não sustenta afirmação nenhuma sobre a classe. Uma
#: precisão de 100% sobre 3 exemplos é sorte, não evidência — foi por isso que
#: 'Sem Óculos' (66,7% sobre n=3) não virou aprovação no A/B do #536.
N_MINIMO_PARA_AFIRMAR = 10

#: Similaridade de cosseno acima da qual um frame de teste é considerado
#: QUASE-DUPLICATA de um frame de treino, e sai do campo.
#:
#: Medido no acervo em 25/08: 2 dos 62 frames de teste tinham similaridade
#: **1,000** com um frame de treino — a MESMA imagem, subida duas vezes com
#: `frame_id` diferente. Mais 17% acima de 0,90. Sem este corte, a régua mede
#: memorização junto com generalização e devolve um número que a produção não
#: reproduz.
#:
#: 0,95 e não 0,98: acima de 0,95 já são recortes do mesmo instante/pessoa
#: (frames consecutivos do coletor), não só arquivos idênticos.
SIMILARIDADE_DUPLICATA = 0.95


def avalia(logits, alvo, classes: list[str], limiar: float) -> dict:
    import torch

    prob = torch.softmax(logits, dim=1)
    conf, previsto = prob.max(dim=1)
    absteve = conf < limiar

    por_classe = {}
    for i, nome in enumerate(classes):
        era = alvo == i
        disse = (previsto == i) & ~absteve
        acerto = int((era & disse).sum())
        n_disse = int(disse.sum())
        n_era = int(era.sum())
        por_classe[nome] = {
            "n_verdade": n_era,
            "n_previsto": n_disse,
            "acertos": acerto,
            "precisao": acerto / n_disse if n_disse else None,
            "recall": acerto / n_era if n_era else None,
            "abstencao": float((era & absteve).sum()) / n_era if n_era else None,
        }
    return {
        "limiar": limiar,
        "abstencao_geral": float(absteve.float().mean()),
        "por_classe": por_classe,
    }


def _quase_duplicatas(frames, X, indice, split: str) -> set[str]:
    """`frame_id`s do campo que têm gêmeo no treino.

    Cosseno sobre o MESMO embedding que a cabeça consome: se dois recortes têm
    a mesma representação, a cabeça não tem como distingui-los, e acertar um
    porque viu o outro é decorar, não generalizar.
    """
    import torch

    treino = [f for f in frames if f["split"] == "train"]
    campo = [f for f in frames if f["split"] == split]
    if not treino or not campo:
        return set()
    Xn = torch.nn.functional.normalize(X, dim=1)
    sim = Xn[[indice[f["frame_id"]] for f in campo]] @ Xn[
        [indice[f["frame_id"]] for f in treino]
    ].T
    melhor = sim.max(dim=1).values
    return {
        f["frame_id"]
        for f, s in zip(campo, melhor.tolist(), strict=True)
        if s > SIMILARIDADE_DUPLICATA
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--modelo", type=Path, default=None)
    p.add_argument("--split", default="test")
    p.add_argument(
        "--com-duplicatas", action="store_true",
        help="NÃO remover quase-duplicatas do treino (número otimista, para comparação)",
    )
    args = p.parse_args()
    modelo_dir = args.modelo or args.dataset / "modelo"

    import torch
    from torch import nn

    manifesto = json.loads((args.dataset / "manifesto.json").read_text(encoding="utf-8"))
    frames = [f for f in manifesto["frames"]
              if (args.dataset / "imagens" / f"{f['frame_id']}.jpg").exists()]
    indice = {f["frame_id"]: i for i, f in enumerate(frames)}
    X_tudo = torch.load(args.dataset / "embeddings.pt", weights_only=True)

    # Quem do campo tem gêmeo no treino — calculado UMA vez, vale para todas
    # as famílias (a duplicata é do FRAME, não do rótulo).
    gemeos = _quase_duplicatas(frames, X_tudo, indice, args.split)
    if gemeos and not args.com_duplicatas:
        log.warning(
            "quase_duplicatas: %d frame(s) do campo '%s' têm gêmeo no treino "
            "(cosseno > %.2f) e saem da régua", len(gemeos), args.split,
            SIMILARIDADE_DUPLICATA,
        )

    veredito_final = {}
    for arquivo in sorted(modelo_dir.glob("*.pt")):
        familia = arquivo.stem
        estado = torch.load(arquivo, weights_only=False)
        classes = estado["classes"]
        cabeca = nn.Linear(estado["dim"], len(classes))
        cabeca.load_state_dict(estado["peso"])
        cabeca.eval()

        campo = [f for f in frames
                 if f["split"] == args.split and familia in f["rotulos"]]
        if not campo:
            log.warning("%s: campo '%s' vazio", familia, args.split)
            continue
        if not args.com_duplicatas:
            antes = len(campo)
            campo = [f for f in campo if f["frame_id"] not in gemeos]
            if antes != len(campo):
                log.info("%s: %d quase-duplicata(s) fora do campo (de %d)",
                         familia, antes - len(campo), antes)
        if not campo:
            log.warning("%s: campo vazio depois de tirar as duplicatas", familia)
            continue
        X = X_tudo[[indice[f["frame_id"]] for f in campo]]
        alvo = torch.tensor([classes.index(f["rotulos"][familia]) for f in campo])
        with torch.no_grad():
            logits = cabeca(X)

        print(f"\n{'═'*74}")
        print(f"{familia.upper()} — campo '{args.split}': {len(campo)} recortes, "
              f"verdade 100% humana")
        print(f"{'limiar':>7}{'abst.geral':>12}", end="")
        for c in classes:
            print(f"{('  ' + c)[:12]:>13}", end="")
        print()
        print(f"{'':>19}", end="")
        for _ in classes:
            print(f"{'prec/rec/abst':>13}", end="")
        print()

        melhor = None
        for limiar in LIMIARES:
            r = avalia(logits, alvo, classes, limiar)
            print(f"{limiar:>7.2f}{r['abstencao_geral']:>11.0%} ", end="")
            for c in classes:
                v = r["por_classe"][c]
                pr = f"{v['precisao']:.0%}" if v["precisao"] is not None else "—"
                rc = f"{v['recall']:.0%}" if v["recall"] is not None else "—"
                ab = f"{v['abstencao']:.0%}" if v["abstencao"] is not None else "—"
                print(f"{pr+'/'+rc+'/'+ab:>13}", end="")
            print()
            if melhor is None or r["abstencao_geral"] < 0.5:
                melhor = r

        # Veredito da ADR-0067, por classe: precisão ≥ 50% COM n que sustente,
        # E acima da LINHA DE BASE.
        #
        # A linha de base é a precisão de quem chuta sempre a mesma classe: se
        # 78% do campo é 'sem', dizer "sem" para tudo já dá 78% de precisão sem
        # olhar a imagem. Sem esta coluna, um número alto numa classe
        # majoritária parece competência e é só a distribuição.
        print(f"\n  veredito ADR-0067 (limiar {melhor['limiar']:.2f}):")
        total_campo = len(campo)
        for c in classes:
            v = melhor["por_classe"][c]
            base = v["n_verdade"] / total_campo if total_campo else 0.0
            if v["n_previsto"] < N_MINIMO_PARA_AFIRMAR:
                estado_txt = f"⚠️  n={v['n_previsto']} insuficiente — não afirma nada"
            elif (v["precisao"] or 0) < PRECISAO_MINIMA:
                estado_txt = (
                    f"⛔ NÃO passa ({v['precisao']:.0%} sobre n={v['n_previsto']}, "
                    f"base {base:.0%})"
                )
            elif (v["precisao"] or 0) <= base + 0.05:
                # Empatar com o chute cego não é passar: o modelo não está
                # acrescentando informação, só reproduzindo a distribuição.
                estado_txt = (
                    f"⛔ NÃO passa — {v['precisao']:.0%} não supera a base "
                    f"{base:.0%} (n={v['n_previsto']})"
                )
            else:
                estado_txt = (
                    f"✅ passa ({v['precisao']:.0%} sobre n={v['n_previsto']}, "
                    f"base {base:.0%}, ganho +{v['precisao'] - base:.0%})"
                )
            print(f"    {c:<14}{estado_txt}")
            veredito_final[f"{familia}/{c}"] = {
                "precisao": v["precisao"], "recall": v["recall"],
                "abstencao": v["abstencao"],
                "n_previsto": v["n_previsto"], "n_verdade": v["n_verdade"],
                "linha_de_base": round(base, 4),
                "limiar": melhor["limiar"],
                "passa": (
                    v["n_previsto"] >= N_MINIMO_PARA_AFIRMAR
                    and (v["precisao"] or 0) >= PRECISAO_MINIMA
                    and (v["precisao"] or 0) > base + 0.05
                ),
            }

        # Por câmera — a média esconde a concentração.
        with torch.no_grad():
            conf, previsto = torch.softmax(logits, dim=1).max(dim=1)
        por_cam = collections.defaultdict(lambda: [0, 0])
        for i, f in enumerate(campo):
            por_cam[f["camera"]][1] += 1
            if int(previsto[i]) == int(alvo[i]) and conf[i] >= melhor["limiar"]:
                por_cam[f["camera"]][0] += 1
        print(f"\n  por câmera (acertos/n, limiar {melhor['limiar']:.2f}):")
        for cam, (ok, n) in sorted(por_cam.items(), key=lambda x: -x[1][1])[:6]:
            print(f"    {str(cam)[:32]:<34}{ok:>3}/{n:<4} {ok/n:>5.0%}")

    destino = args.dataset / "regua.json"
    destino.write_text(json.dumps(veredito_final, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    aprovadas = [k for k, v in veredito_final.items() if v["passa"]]
    print(f"\n{'═'*74}\nclasses que PASSAM a régua: {len(aprovadas)} — {aprovadas}")
    print(f"régua em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
