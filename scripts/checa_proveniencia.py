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
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime

CARENCIA_MINUTOS = 30


#: O serviço respondeu, mas sem o campo `commit`. É DIFERENTE de não responder:
#: o processo está de pé, só não declara o que está rodando — e a ação de quem
#: recebe o alerta é outra (conferir o endpoint, não ressuscitar o serviço).
SEM_CAMPO = "__sem_campo__"


def commit_servido(url: str, timeout: int = 25) -> str | None:
    """SHA que o serviço declara.

    `None` = não respondeu (fora do ar, rede, timeout).
    `SEM_CAMPO` = respondeu, mas sem `commit` no corpo.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            corpo = json.load(r)
    except Exception:
        return None
    return str(corpo.get("commit", "")).strip() or SEM_CAMPO


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
    servido: str | None, esperado: str, nascido_em: datetime, agora: datetime | None = None
) -> tuple[bool, str]:
    """(alerta, motivo). Separada da rede para poder ser testada de verdade."""
    idade = ((agora or datetime.now(UTC)) - nascido_em).total_seconds() / 60

    if servido is None:
        return True, "o serviço não respondeu — fora do ar, rede ou timeout"

    if servido == SEM_CAMPO:
        return True, (
            "o serviço respondeu, mas SEM o campo `commit` — endpoint errado "
            "ou versão anterior à proveniência. Confira a URL antes de "
            "ressuscitar nada: o processo está de pé."
        )

    if servido == esperado:
        return False, f"em dia — {esperado[:8]}"

    if idade < CARENCIA_MINUTOS:
        return False, (
            f"divergente, mas o commit tem {idade:.0f} min — dentro da carência "
            f"de {CARENCIA_MINUTOS} min, provavelmente é o deploy em andamento"
        )

    if servido == "unknown":
        return True, (
            f"PROVENIÊNCIA PERDIDA há {idade:.0f} min: o serviço responde "
            '"unknown", a marca de deploy por upload local (`railway up`). '
            "Ninguém sabe que código está no ar. Ver D-156: deploy por git "
            "ganha do `railway up` quando o commit está na branch."
        )

    return True, (
        f"ATRASADO há {idade:.0f} min: o serviço está em {servido[:8]} e a "
        f"develop está em {esperado[:8]}."
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="endpoint /livez do serviço")
    p.add_argument("--branch", default="origin/develop")
    args = p.parse_args()

    esperado, nascido_em = head_da_branch(args.branch)
    servido = commit_servido(args.url)
    alerta, motivo = avaliar(servido, esperado, nascido_em)

    print(f"esperado ({args.branch}): {esperado}")
    print(f"servido  ({args.url}): {servido}")
    print(f"veredito: {'🔴 ALERTA' if alerta else '✅ ok'} — {motivo}")
    return 1 if alerta else 0


if __name__ == "__main__":
    sys.exit(main())
