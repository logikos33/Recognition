#!/usr/bin/env python3
"""Contagem e idade das issues abertas — a métrica de saúde da fila.

Roda local (`python3 scripts/ci/issues_report.py`) ou no workflow semanal.
Só LÊ e imprime: não abre, não fecha e não comenta nada. A jardinagem é
decisão humana; isto aqui só impede que o estoque cresça sem ninguém ver.

Stdlib + `gh` (já autenticado no runner e na máquina). Sem pip install.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone

# Faixas de idade. O ponto não é o número exato, é a forma da distribuição:
# uma fila saudável tem massa em "≤7d"; uma fila abandonada tem massa em ">90d".
FAIXAS = [(7, "≤ 7d"), (30, "8–30d"), (90, "31–90d"), (10**9, "> 90d")]


def issues_abertas():
    saida = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--limit", "1000",
         "--json", "number,title,createdAt,labels"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(saida)


def idade_em_dias(criada_em, agora):
    return (agora - datetime.fromisoformat(criada_em.replace("Z", "+00:00"))).days


def main():
    agora = datetime.now(timezone.utc)
    issues = issues_abertas()
    if not issues:
        print("Nenhuma issue aberta.")
        return 0

    baldes = {rotulo: [] for _, rotulo in FAIXAS}
    for issue in issues:
        dias = idade_em_dias(issue["createdAt"], agora)
        for limite, rotulo in FAIXAS:
            if dias <= limite:
                baldes[rotulo].append((dias, issue))
                break

    idades = sorted(idade_em_dias(i["createdAt"], agora) for i in issues)
    mediana = idades[len(idades) // 2]

    print(f"## Fila de issues — {agora:%Y-%m-%d}\n")
    print(f"**{len(issues)} abertas** · mediana de idade **{mediana}d** · mais antiga **{idades[-1]}d**\n")
    print("| Idade | Quantas |")
    print("|---|---|")
    for _, rotulo in FAIXAS:
        print(f"| {rotulo} | {len(baldes[rotulo])} |")

    # Duas fatias que mudam o que se faz a seguir, então saem nomeadas.
    def com_label(nome):
        return [i for i in issues if any(l["name"] == nome for l in i["labels"])]

    seguranca = com_label("risk:security")
    if seguranca:
        print(f"\n🔴 **`risk:security` abertas: {len(seguranca)}** — "
              + ", ".join(f"#{i['number']}" for i in seguranca))

    sem_dono = [i for i in issues if not i["labels"]]
    if sem_dono:
        print(f"\n⚠️ **Sem label nenhuma ({len(sem_dono)})** — fila sem dono nem classificação: "
              + ", ".join(f"#{i['number']}" for i in sem_dono[:20])
              + (" …" if len(sem_dono) > 20 else ""))

    velhas = sorted(baldes["> 90d"], reverse=True)[:10]
    if velhas:
        print("\n**Mais antigas:**\n")
        for dias, issue in velhas:
            print(f"- `{dias}d` #{issue['number']} {issue['title'][:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
