"""Gate de `npm audit` com allowlist EXPLÍCITA e DATADA.

O problema que isto resolve (#421)
----------------------------------
O job de `npm audit` rodava com `continue-on-error: true`. Ele executava,
imprimia as 5 vulnerabilidades da landing — e o workflow reportava **success**.
`security-scan` verde com `astro 4.16.19` vulnerável no lock: o verde não era
prova de segurança, era a **ausência da pergunta**.

Tirar o `continue-on-error` sozinho traria de volta o motivo dele: um advisory
que cruza o limiar pinta de vermelho TODO PR do repositório, inclusive PR só de
Python. Vermelho que aparece em tudo deixa de ser sinal.

A saída é a exceção ser explícita, ter DONO (a issue) e ter PRAZO:

- advisory conhecido, na allowlist, dentro do prazo e dentro do teto → passa
- advisory NOVO                                                      → ⛔ reprova
- advisory que PIOROU acima do teto triado                           → ⛔ reprova
- allowlist com prazo VENCIDO                                        → ⛔ reprova

⚠️ É o prazo que impede a exceção de virar mordaça permanente por esquecimento —
que é exatamente como a #421 nasceu.

Por que este arquivo existe em vez de um heredoc no workflow: gate embutido em
YAML não roda em pytest. Um gate de segurança sem teste é a próxima #421.

Uso:
    npm audit --package-lock-only --json > audit.json || true
    python3 scripts/ci/check_npm_audit.py <app> < audit.json
"""
from __future__ import annotations

import json
import sys
from datetime import date

# pacote -> (issue que rastreia, prazo ISO, severidade TRIADA)
#
# A severidade é TETO, não rótulo. O que foi triado foi aquele nível: se o
# pacote piorar (high -> critical), a allowlist não cobre e o gate reprova
# pedindo triagem nova. Sem esse teto o gate imprimiria "nenhum high/critical
# fora da allowlist" sentado em cima de um critical — a mesma mentira que este
# workflow acabou de perder, só que menor.
ALLOWLIST: dict[str, dict[str, tuple[str, str, str]]] = {
    "frontend": {
        "browserslist": ("#655", "2026-10-06", "high"),
    },
    "landing": {
        # árvore do astro 4.16.19 — migração 4→7, não bump (#421). Nenhuma é
        # exposição de runtime: `astro.config` tem output 'static', o site é
        # HTML gerado no build e servido estático.
        "astro": ("#421", "2026-10-06", "high"),
        "sharp": ("#421", "2026-10-06", "high"),
        "vite": ("#421", "2026-10-06", "high"),
        "browserslist": ("#655", "2026-10-06", "high"),
    },
}

NIVEL = {"high": 1, "critical": 2}
BLOQUEIA = set(NIVEL)


def avaliar(app: str, relatorio: dict, hoje: str) -> tuple[int, str]:
    """Devolve (codigo_de_saida, texto). Pura — é o que o teste exercita."""
    permitido = ALLOWLIST.get(app, {})
    vulns = relatorio["vulnerabilities"]
    linhas: list[str] = []

    bloqueando, tolerado, vencido = [], [], []
    for nome, v in sorted(vulns.items()):
        if v["severity"] not in BLOQUEIA:
            continue
        if nome not in permitido:
            bloqueando.append(f"{v['severity']:8} {nome}")
            continue
        issue, prazo, teto = permitido[nome]
        if NIVEL[v["severity"]] > NIVEL[teto]:
            bloqueando.append(
                f"{v['severity']:8} {nome:22} PIOROU — allowlist triou "
                f"{teto} ({issue}); reveja antes de tolerar")
            continue
        linha = f"{v['severity']:8} {nome:22} {issue} ate {prazo}"
        (vencido if hoje > prazo else tolerado).append(linha)

    if tolerado:
        linhas.append("TOLERADO (allowlist datada):")
        linhas += ["  " + x for x in tolerado]

    # Exceção que já não é necessária também é ruído: avisa, ⛔ não reprova.
    nao_vistos = sorted(set(permitido) - set(vulns))
    if nao_vistos:
        linhas.append("allowlist sem advisory correspondente (pode remover): "
                      + ", ".join(nao_vistos))

    if vencido:
        linhas.append("")
        linhas.append("PRAZO VENCIDO — a allowlist expirou:")
        linhas += ["  " + x for x in vencido]
    if bloqueando:
        linhas.append("")
        linhas.append("ADVISORY NAO PREVISTA (high/critical):")
        linhas += ["  " + x for x in bloqueando]
        linhas.append("")
        linhas.append("Trate, ou registre na ALLOWLIST com issue + prazo no mesmo PR.")

    if vencido or bloqueando:
        return 1, "\n".join(linhas)
    linhas.append("")
    linhas.append(f"OK — nenhum high/critical fora da allowlist em apps/{app}.")
    return 0, "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("uso: check_npm_audit.py <app> < audit.json")
        return 2
    app = argv[0]

    bruto = sys.stdin.read().strip()
    try:
        relatorio = json.loads(bruto)
        relatorio["vulnerabilities"]
    except Exception as e:
        # audit.json inválido/vazio = o `npm audit` falhou (rede, 400, tree).
        # Isso é problema de verdade e tem de aparecer vermelho, ⛔ nunca passar
        # por omissão.
        print(f"npm audit nao produziu relatorio utilizavel: {e}")
        return 1

    codigo, texto = avaliar(app, relatorio, date.today().isoformat())
    print(texto)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
