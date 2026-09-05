#!/usr/bin/env python3
"""O DEV está rodando o código da develop? — checagem de proveniência.

POR QUE ISTO EXISTE

Em 29/08 a API do DEV passou horas rodando um build de `railway up` (upload do
laptop de alguém) enquanto a develop tinha outro código. O sinal existia — o
`/livez` devolvia `commit: "unknown"`, que é exatamente o que a D-156 diz ser a
marca de deploy sem proveniência — e ninguém estava lendo. Agora alguém lê por
ofício.

A JANELA DE CARÊNCIA

Um deploy legítimo leva alguns minutos, e durante ele o serviço ainda responde o
commit anterior. Alertar nesse intervalo geraria ruído e treinaria todo mundo a
ignorar o alerta — que é como um alarme morre. Por isso a divergência só vira
alerta quando o commit mais novo da develop já tem mais de 30 minutos: aí não é
deploy em andamento, é deploy que não aconteceu.

DECLARADO ≠ PROVADO  (a correção de 05/09)

A primeira versão desta checagem comparava `/livez.commit` com o HEAD da
develop e dava ✅ quando batiam. Mas `/livez.commit` vinha de uma ENV VAR que o
CI grava ANTES de subir o código — variável e código servido são independentes.
Se o upload falha, sobe outra árvore, ou alguém dá um `railway up` do laptop
(que não toca a variável), o serviço afirma um SHA que não está rodando — e
esta checagem confirmava, feliz. O conserto de 29/08 trocou "não sei"
(`unknown`) por "acho que sei", e isso é PIOR: desligou o único sinal honesto
que existia.

Agora há duas perguntas, e o veredito diz qual foi respondida:

  DECLARADO — o serviço diz um SHA. É a palavra de quem escreveu a variável.
  PROVADO   — o `tree_digest` do serviço casa com o digest da árvore esperada,
              derivado do próprio repositório. Ninguém escreve esse valor.

Um alarme que não distingue os dois é um alarme que mente com voz de
autoridade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime

CARENCIA_MINUTOS = 30

#: Pasta cujo conteúdo o `tree_digest` do `/livez` resume. Tem de casar com
#: `_PACOTE_SERVIDO` em services/api/app/api/v1/health/routes.py.
PACOTE_SERVIDO = "services/api/app"


#: O serviço respondeu, mas sem o campo `commit`. É DIFERENTE de não responder:
#: o processo está de pé, só não declara o que está rodando — e a ação de quem
#: recebe o alerta é outra (conferir o endpoint, não ressuscitar o serviço).
SEM_CAMPO = "__sem_campo__"


def ler_livez(url: str, timeout: int = 25) -> tuple[dict | None, str | None]:
    """`(corpo, motivo_da_falha)` — exatamente um dos dois é `None`.

    O motivo VIAJA até o veredito de propósito. A versão anterior engolia a
    exceção e dizia sempre "fora do ar, rede ou timeout": rodando este script
    num macOS sem os certificados raiz instalados, ele acusava um serviço que
    respondia em 0,4s de estar morto. Um alerta que erra o diagnóstico manda a
    pessoa reiniciar o que está saudável — o mesmo erro já registrado aqui para
    o caso de apontar a checagem para a URL errada.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            corpo = json.load(r)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return (corpo if isinstance(corpo, dict) else {}), None


def digest_da_arvore(ref: str, pacote: str = PACOTE_SERVIDO) -> str | None:
    """Digest ESPERADO de `pacote` em `ref`, direto do repositório.

    Reconstrói, sem checkout e sem rede, exatamente o que
    `_digest_da_arvore_servida()` calcula no processo servido: os hashes de
    blob que o git já guarda, uma linha por arquivo `.py`, ordenadas, sha256.

    É a metade que transforma DECLARADO em PROVADO — o outro lado do digest é
    calculado pelo processo a partir do que ele tem em disco, e ninguém pode
    escrevê-lo à mão.
    """
    try:
        saida = subprocess.run(
            ["git", "ls-tree", "-r", ref, "--", pacote],
            capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        return None

    prefixo = pacote.rstrip("/") + "/"
    entradas = []
    for linha in saida.splitlines():
        if "\t" not in linha:
            continue
        meta, caminho = linha.split("\t", 1)
        partes = meta.split()
        if len(partes) < 3 or partes[1] != "blob" or not caminho.endswith(".py"):
            continue
        entradas.append(f"{partes[2]} {caminho[len(prefixo):]}")

    if not entradas:
        return None
    return hashlib.sha256("\n".join(sorted(entradas)).encode()).hexdigest()[:16]


def head_da_branch(branch: str) -> tuple[str, datetime]:
    """SHA e data do commit mais novo da branch."""
    sha = subprocess.run(
        ["git", "rev-parse", branch], capture_output=True, text=True, check=True
    ).stdout.strip()
    quando = subprocess.run(
        ["git", "show", "-s", "--format=%cI", sha], capture_output=True, text=True, check=True
    ).stdout.strip()
    return sha, datetime.fromisoformat(quando).astimezone(UTC)


def avaliar(
    servido: str | None,
    esperado: str,
    nascido_em: datetime,
    agora: datetime | None = None,
    digest_servido: str | None = None,
    digest_esperado: str | None = None,
    carencia_min: int = CARENCIA_MINUTOS,
    erro_rede: str | None = None,
) -> tuple[bool, str]:
    """(alerta, motivo). Separada da rede para poder ser testada de verdade.

    ⚠️ `digest_servido`/`digest_esperado` são `None` por omissão de propósito:
    ausência de prova NUNCA vira prova. Sem os dois, o veredito bom é
    "DECLARADO, NÃO PROVADO" — nunca ✅ silencioso.
    """
    idade = ((agora or datetime.now(UTC)) - nascido_em).total_seconds() / 60

    if servido is None:
        # O motivo bruto entra no texto: TLS quebrado, DNS, 404 e timeout pedem
        # ações DIFERENTES, e "não respondeu" sozinho manda para a errada.
        detalhe = f" — {erro_rede}" if erro_rede else ""
        return True, f"o serviço não respondeu (fora do ar, rede ou timeout){detalhe}"

    if servido == SEM_CAMPO:
        return True, (
            "o serviço respondeu, mas SEM o campo `commit` — endpoint errado "
            "ou versão anterior à proveniência. Confira a URL antes de "
            "ressuscitar nada: o processo está de pé."
        )

    # ------------------------------------------------------------------
    # 1. Quando há digest dos DOIS lados, ele decide — é a única evidência
    #    aqui que não depende de alguém ter escrito uma variável.
    # ------------------------------------------------------------------
    if digest_servido and digest_esperado:
        if digest_servido == digest_esperado:
            # Vale mesmo com `commit` divergente ou "unknown": o que importa é
            # o código servido, e ele É o esperado. Um commit só de docs move o
            # HEAD sem mudar uma linha de `app/` — isso não é degradação.
            return False, (
                f"PROVADO — o código servido casa com {esperado[:8]} "
                f"(tree_digest {digest_servido}), declarado como "
                f"{servido[:8] if servido != 'unknown' else 'unknown'}"
            )

        if idade < carencia_min:
            return False, (
                f"código divergente, mas o commit tem {idade:.0f} min — dentro "
                f"da carência de {carencia_min} min, provavelmente é o deploy "
                "em andamento"
            )

        if servido == esperado:
            return True, (
                f"🔴 DECLARAÇÃO FALSA há {idade:.0f} min: o serviço AFIRMA "
                f"estar em {servido[:8]}, mas o código que ele tem em disco é "
                f"outro (tree_digest {digest_servido}, esperado "
                f"{digest_esperado}). O SHA vem de env var, que é escrita "
                "ANTES do upload e sobrevive a ele — deploy que não subiu, "
                "árvore diferente, ou `railway up` de fora do CI. NÃO confie "
                "no campo `commit` deste serviço."
            )

        return True, (
            f"ATRASADO há {idade:.0f} min, e PROVADO pelo digest: o código "
            f"servido não é o de {esperado[:8]} (tree_digest {digest_servido}, "
            f"esperado {digest_esperado}). O serviço declara {servido[:8]}."
        )

    # ------------------------------------------------------------------
    # 2. Sem digest não existe prova — só dá para repetir o que disseram, e
    #    o veredito precisa dizer isso em voz alta.
    # ------------------------------------------------------------------
    faltou = (
        "o serviço não devolve `tree_digest` (versão anterior a esta checagem)"
        if not digest_servido
        else "não foi possível derivar o digest esperado do repositório"
    )

    if servido == esperado:
        return False, (
            f"DECLARADO, NÃO PROVADO — {servido[:8]} bate com o esperado, mas "
            f"{faltou}. `commit` sai de env var: é a palavra de quem a "
            "escreveu, não evidência do código servido."
        )

    if idade < carencia_min:
        return False, (
            f"divergente, mas o commit tem {idade:.0f} min — dentro da carência "
            f"de {carencia_min} min, provavelmente é o deploy em andamento"
        )

    if servido == "unknown":
        return True, (
            f"PROVENIÊNCIA PERDIDA há {idade:.0f} min: o serviço responde "
            '"unknown", a marca de deploy por upload local (`railway up`). '
            f"E {faltou} — ninguém sabe que código está no ar. Ver D-156."
        )

    return True, (
        f"ATRASADO há {idade:.0f} min: o serviço declara {servido[:8]} e a "
        f"develop está em {esperado[:8]}. Sem prova do código servido: {faltou}."
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="endpoint /livez do serviço")
    p.add_argument("--branch", default="origin/develop")
    p.add_argument(
        "--carencia-min",
        type=int,
        default=CARENCIA_MINUTOS,
        help=(
            "minutos de tolerância para deploy em andamento. Use 0 logo depois "
            "de um deploy, quando a pergunta é 'subiu mesmo?' e não há o que "
            "esperar."
        ),
    )
    args = p.parse_args()

    esperado, nascido_em = head_da_branch(args.branch)
    corpo, erro_rede = ler_livez(args.url)
    servido = (
        None if corpo is None else (str(corpo.get("commit", "")).strip() or SEM_CAMPO)
    )
    digest_servido = None if corpo is None else (corpo.get("tree_digest") or None)
    digest_esperado = digest_da_arvore(args.branch)

    alerta, motivo = avaliar(
        servido,
        esperado,
        nascido_em,
        digest_servido=digest_servido,
        digest_esperado=digest_esperado,
        carencia_min=args.carencia_min,
        erro_rede=erro_rede,
    )

    print(f"esperado ({args.branch}): {esperado}  digest={digest_esperado}")
    print(f"servido  ({args.url}): {servido}  digest={digest_servido}")
    print(f"veredito: {'🔴 ALERTA' if alerta else '✅ ok'} — {motivo}")
    return 1 if alerta else 0


if __name__ == "__main__":
    sys.exit(main())
