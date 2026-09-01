#!/usr/bin/env python3
"""Calibração por classe contra a régua da ADR-0067.

Por que este script existe: a régua ("classe de ausência só gera violação
enquanto sustentar precisão >= 50% em campo virgem") depende de um dado que se
MOVE — o operador julga a fila o tempo todo. Medimos a mesma classe com minutos
de intervalo em 31/08 e a precisão saiu 27,3% e depois outra: chumbar um limiar
a partir de uma foto é como calibrar balança com o caminhão em cima.

Então a decisão nunca vira constante no código. Roda-se isto, lê-se a tabela, e
quem promove/rebaixa uma classe é uma linha de dado (`yolo_classes.is_violation`),
com o `n` visível — a ADR é explícita: "precisão sem n não é medida".

Uso:
    DATABASE_URL=... python3 scripts/ops/calibracao_classes.py [--tenant rvb]

Somente leitura. Não escreve nada, de propósito: rebaixar classe é ato humano.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

REGUA_MINIMA = 50.0  # ADR-0067: precisão mínima para uma classe de ausência alertar
N_MINIMO = 20  # abaixo disto não se promove nem se rebaixa: é sorte, não evidência

# Duas origens de violação convivem (ADR-0067):
#   caminho 1 = classe de ausência do detector  -> alerts.class_name
#   caminho 2 = classificador de recorte        -> violations[].class (class_name NULL)
CONSULTA = """
WITH v AS (
    SELECT a.verification_verdict AS vd,
           COALESCE(a.class_name, e.value->>'class') AS classe,
           CASE WHEN a.class_name IS NULL THEN 'classificador' ELSE 'detector' END AS caminho,
           a.confidence AS conf
      FROM public.alerts a
      JOIN public.tenants t ON t.id = a.tenant_id AND t.slug = %(tenant)s
      LEFT JOIN LATERAL jsonb_array_elements(
               CASE WHEN jsonb_typeof(a.violations) = 'array'
                    THEN a.violations ELSE '[]'::jsonb END) AS e ON a.class_name IS NULL
)
SELECT v.classe, v.caminho,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE v.vd IS NOT NULL) AS julgados,
       COUNT(*) FILTER (WHERE v.vd = 'approve') AS acertos,
       COUNT(*) FILTER (WHERE v.vd = 'reject') AS falsos,
       y.is_violation AS alerta_hoje
  FROM v
  LEFT JOIN public.yolo_classes y
         ON y.name = v.classe
        AND y.tenant_id = (SELECT id FROM public.tenants WHERE slug = %(tenant)s)
 WHERE v.classe IS NOT NULL
 GROUP BY v.classe, v.caminho, y.is_violation
 ORDER BY julgados DESC, total DESC
"""


def veredito(julgados: int, precisao: float | None) -> tuple[str, str]:
    """Devolve (veredito, porquê). A régua da ADR-0067, aplicada sem dó."""
    if julgados == 0:
        return "SEM DADO", "ninguém julgou ainda — não dá para afirmar nada"
    if precisao is None:
        return "SEM DADO", "sem veredito utilizável"
    if julgados < N_MINIMO:
        # n curto não PROMOVE. Mas se o pouco que há já está abaixo da régua, a
        # classe não tem direito a alertar enquanto não provar o contrário: o ônus
        # da prova é de quem acusa, não de quem cumpre.
        rumo = "e já abaixo da régua" if precisao < REGUA_MINIMA else "e ainda não provou a régua"
        return "n INSUFICIENTE", f"só {julgados} julgados (mín. {N_MINIMO}) {rumo} ({precisao:.1f}%)"
    if precisao >= REGUA_MINIMA:
        return "PASSA", f"{precisao:.1f}% ≥ {REGUA_MINIMA:.0f}% em {julgados} julgados"
    return "REPROVA", f"{precisao:.1f}% < {REGUA_MINIMA:.0f}% — acusa quem cumpre em {100 - precisao:.0f}% dos avisos"


def autoteste() -> int:
    """Régua da ADR-0067 verificada nos casos que já nos morderam de verdade."""
    # Sem julgamento humano não se afirma nada.
    assert veredito(0, None)[0] == "SEM DADO"
    # 100% sobre 1 caso é sorte: a ADR-0067 recusou "Sem Óculos" por exatamente isto.
    assert veredito(1, 100.0)[0] == "n INSUFICIENTE"
    # n curto E abaixo da régua não ganha o benefício da dúvida — o ônus é de quem acusa.
    assert veredito(10, 20.0)[0] == "n INSUFICIENTE"
    # "Sem protetor de ouvido" medido em 31/08: reprova com folga.
    assert veredito(22, 27.3)[0] == "REPROVA"
    # "Sem mascara" pelo classificador: passa.
    assert veredito(33, 63.6)[0] == "PASSA"
    # A régua é >=, não >: exatamente 50% passa.
    assert veredito(20, 50.0)[0] == "PASSA"
    assert veredito(20, 49.9)[0] == "REPROVA"
    print("autoteste ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="rvb")
    ap.add_argument("--autoteste", action="store_true", help="verifica a régua sem tocar no banco")
    args = ap.parse_args()

    if args.autoteste:
        return autoteste()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 2

    with psycopg2.connect(dsn) as conn:
        # Só leitura, explicitamente: este script nunca promove nem rebaixa classe.
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(CONSULTA, {"tenant": args.tenant})
            linhas = cur.fetchall()

    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\nCalibração por classe — tenant {args.tenant} — medido em {agora}")
    print(f"Régua ADR-0067: precisão ≥ {REGUA_MINIMA:.0f}% com n ≥ {N_MINIMO}\n")
    cab = f"{'classe':<26} {'caminho':<14} {'tot':>4} {'julg':>5} {'ok':>4} {'falso':>6} {'precisão':>9}  {'alerta hoje':<11} veredito"
    print(cab)
    print("-" * len(cab))

    divergencias = []
    fora_do_catalogo = []
    for r in linhas:
        julgados, acertos = r["julgados"], r["acertos"]
        precisao = (100.0 * acertos / julgados) if julgados else None
        vd, porque = veredito(julgados, precisao)
        alerta = {True: "sim", False: "não", None: "indeciso"}[r["alerta_hoje"]]
        p = f"{precisao:.1f}%" if precisao is not None else "—"
        print(f"{r['classe']:<26} {r['caminho']:<14} {r['total']:>4} {julgados:>5} "
              f"{acertos:>4} {r['falsos']:>6} {p:>9}  {alerta:<11} {vd}")

        # `is_violation IS NULL` = a classe não foi decidida (tipicamente: nem está
        # no catálogo do tenant). A migration 125 faz NULL cair em VIOLAÇÕES por
        # fail-loud — então ela acusa sem ninguém ter decidido que ela pode.
        acusa_hoje = r["alerta_hoje"] is not False
        if acusa_hoje and precisao is not None and precisao < REGUA_MINIMA:
            divergencias.append((r["classe"], alerta, porque))
        if r["alerta_hoje"] is None:
            fora_do_catalogo.append(r["classe"])

    if divergencias:
        print("\n🔴 ACUSAM HOJE SEM SUSTENTAR A RÉGUA — cada uma acusa quem cumpre:")
        for classe, alerta, porque in divergencias:
            print(f"   · {classe} (alerta: {alerta}): {porque}")
        print("\n   Rebaixar = UPDATE public.yolo_classes SET is_violation=false WHERE ... (ato humano,")
        print("   fora deste script). A classe continua sendo detectada e gravada — só deixa de acusar.")
    else:
        print("\n✅ Nenhuma classe que acusa hoje está abaixo da régua.")

    if fora_do_catalogo:
        print("\n⚠️  SEM DECISÃO DE POLARIDADE (is_violation NULL) — acusam por fail-loud da migration 125,")
        print("    e não aparecem na tela de escopo por câmera, que lê o catálogo do tenant:")
        for classe in sorted(set(fora_do_catalogo)):
            print(f"   · {classe}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
