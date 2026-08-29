"""Gate de `npm audit` com lista de exceções DATADA.

O problema que isto resolve
---------------------------
O job de `npm audit` rodava com `continue-on-error: true`. Ele executava,
imprimia as 5 vulnerabilidades da landing — e o workflow reportava **success**.
`security-scan` verde com `astro 4.16.19` vulnerável no lock: o verde não era
prova de segurança, era a **ausência da pergunta** (issue #421).

Tirar o `continue-on-error` sozinho traria de volta o problema que o motivou:
um advisory que cruza o limiar pinta de vermelho TODO PR do repositório,
inclusive PR só de Python. Vermelho que aparece em tudo deixa de ser sinal.

A saída é a exceção ser EXPLÍCITA e ter PRAZO:

- advisory conhecido, escrito no allowlist com motivo e data de validade → passa
- advisory NOVO → ⛔ reprova
- allowlist VENCIDO → ⛔ reprova, mesmo que nada tenha mudado

⚠️ A validade é o que impede a exceção de virar permanente por esquecimento —
que é como esta issue nasceu.

Uso:
  npm audit --json | python scripts/ci/check_npm_audit.py apps/landing
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

GRAVES = {"high", "critical"}
ARQUIVO = ".audit-allowlist.json"


def carregar_allowlist(base: pathlib.Path) -> tuple[dict, list[str]]:
    caminho = base / ARQUIVO
    if not caminho.exists():
        return {}, []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    problemas = []
    vence = dados.get("expires")
    if not vence:
        problemas.append(f"{caminho}: sem campo `expires` — exceção sem prazo é exceção eterna")
    else:
        hoje = dt.date.today()
        prazo = dt.date.fromisoformat(vence)
        if prazo < hoje:
            problemas.append(
                f"{caminho}: allowlist VENCEU em {vence} — reavalie os advisories "
                f"e renove a data, ou conserte"
            )
    return dados, problemas


def main() -> int:
    base = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    bruto = sys.stdin.read().strip()
    if not bruto:
        print("ERRO: nada no stdin — o `npm audit --json` não produziu saída")
        return 1

    relatorio = json.loads(bruto)
    allowlist, problemas = carregar_allowlist(base)
    permitidos = set(allowlist.get("allowed", []))

    graves, inesperados = [], []
    for nome, v in (relatorio.get("vulnerabilities") or {}).items():
        if v.get("severity") not in GRAVES:
            continue
        graves.append(nome)
        if nome not in permitidos:
            inesperados.append(nome)

    resumo = (relatorio.get("metadata") or {}).get("vulnerabilities", {})
    print(f"{base}: {resumo}")
    if graves:
        print(f"  graves: {sorted(graves)}")
    if permitidos:
        print(f"  no allowlist (vence {allowlist.get('expires')}): {sorted(permitidos)}")

    # Exceção que não é mais necessária também é ruído: avisa, ⛔ não reprova.
    obsoletos = sorted(permitidos - set(graves))
    if obsoletos:
        print(f"  ⚠️ no allowlist e JÁ NÃO aparecem — remova: {obsoletos}")

    for p in problemas:
        print(f"  ⛔ {p}")
    for nome in sorted(inesperados):
        print(f"  ⛔ advisory NOVO fora do allowlist: {nome}")

    if problemas or inesperados:
        print("\nNPM AUDIT GATE: REPROVADO")
        return 1
    print("\nNPM AUDIT GATE: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
