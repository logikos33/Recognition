#!/usr/bin/env python3
"""Aplica ao catálogo do tenant a decisão que a régua da ADR-0067 já tomou.

Isto NÃO é migration, de propósito. `railway_start.py` re-roda toda migration a
cada boot; polaridade de classe é dado de cliente e decisão humana, e um
backfill automático desfaria a correção de um admin a cada reinício (a própria
migration 125 registra esse cuidado). Então: script manual, env-gated, com
dry-run por padrão.

O que a régua decidiu (medido em 31/08 sobre vereditos humanos reais — rode
`calibracao_classes.py` para reconferir ANTES de aplicar; o dado se move):

  Sem protetor de ouvido    27,3%  ⛔ sai do gatilho  (a ADR-0067 já dizia isso em 25/08)
  Uso incorreto de mascara  20,0%  ⛔ sai do gatilho  (era 61,9% no dataset; despencou em campo)
  Sem Óculos                30,4%  ⛔ nasce indeciso
  Sem Luvas                 69,7%  ✅ nasce como violação
  Óculos                       —   presença (conformidade), nunca acusa

`is_violation = NULL` é o estado "registro/telemetria": o pipeline NÃO cria
alerta (inference.py `_has_violation`) e a classe não conta como conformidade
(`_nomes_por_polaridade` usa IS TRUE / IS FALSE). A detecção continua sendo
gravada — só deixa de acusar. Nada é apagado.

Uso:
    DATABASE_URL=... python3 scripts/ops/aplicar_calibracao_rvb.py            # mostra, não aplica
    DATABASE_URL=... python3 scripts/ops/aplicar_calibracao_rvb.py --aplicar
"""

import argparse
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

TENANT_SLUG = "rvb"
MODULE_CODE = "epi"

# A migration 127 (`polaridade_nao_erode`) faz, a cada boot em modo LEGADO:
#     UPDATE yolo_classes SET is_violation = NULL
#      WHERE is_violation IS FALSE AND created_at >= '2026-08-25'
# Ela existe para desfazer o backfill cego da 125, e o próprio cabeçalho dela
# avisa: "no dia em que existir uma rota que grave is_violation, esta migration
# passa a apagar decisão humana". Este script É essa rota. Então marcar uma
# classe nova como CONFORMIDADE (False) não sobrevive ao próximo deploy — e
# falhar em silêncio é justamente o que a casa não aceita. Avisamos.
EROSAO_127_A_PARTIR_DE = "2026-08-25"

# (nome, is_violation, porquê) — o porquê fica no banco? Não: fica aqui e no relatório.
# NULL = indecisa (registra, não acusa). True = acusa. False = conformidade.
DECISOES = [
    ("Sem protetor de ouvido", None, "27,3% de precisão em 22 julgados — ADR-0067 já a reprovava a 40%"),
    ("Uso incorreto de mascara", None, "20,0% em 10 julgados — passava a 61,9% no dataset, não transferiu"),
    ("Sem Óculos", None, "30,4% em 23 julgados — acusa quem cumpre em 70% dos avisos"),
    ("Sem Luvas", True, "69,7% em 33 julgados — sustenta a régua"),
    ("Óculos", False, "classe de presença: alimenta conformidade, nunca alerta"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o que mudaria")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM public.tenants WHERE slug = %s", (TENANT_SLUG,))
            row = cur.fetchone()
            if not row:
                print(f"tenant '{TENANT_SLUG}' não existe neste banco.", file=sys.stderr)
                return 1
            tenant_id = row["id"]

            print(f"\ntenant {TENANT_SLUG} ({tenant_id})  módulo {MODULE_CODE}")
            print(f"modo: {'APLICAR' if args.aplicar else 'só mostrar (use --aplicar para valer)'}\n")

            for nome, alvo, porque in DECISOES:
                cur.execute(
                    "SELECT id, is_violation FROM public.yolo_classes"
                    " WHERE tenant_id = %s AND name = %s",
                    (tenant_id, nome),
                )
                atual = cur.fetchone()
                rotulo = {True: "acusa", False: "conformidade", None: "indecisa"}

                if atual is None:
                    acao = f"CRIAR   {nome:<26} → {rotulo[alvo]}"
                    if args.aplicar:
                        cur.execute(
                            "INSERT INTO public.yolo_classes (tenant_id, module_code, name, is_violation)"
                            " VALUES (%s, %s, %s, %s)",
                            (tenant_id, MODULE_CODE, nome, alvo),
                        )
                elif atual["is_violation"] is alvo:
                    print(f"ok      {nome:<26} já está em {rotulo[alvo]}")
                    continue
                else:
                    acao = (f"MUDAR   {nome:<26} {rotulo[atual['is_violation']]} → {rotulo[alvo]}")
                    if args.aplicar:
                        cur.execute(
                            "UPDATE public.yolo_classes SET is_violation = %s"
                            " WHERE tenant_id = %s AND name = %s",
                            (alvo, tenant_id, nome),
                        )
                print(f"{acao}\n        porque: {porque}")

        # Aviso de erosão: só CONFORMIDADE (False) em linha nova é apagada pela 127.
        erodiveis = [nome for nome, alvo, _ in DECISOES if alvo is False]
        if erodiveis:
            print("\n⚠️  NÃO SOBREVIVE AO PRÓXIMO DEPLOY — a migration 127 roda a cada boot e faz")
            print(f"    is_violation=FALSE → NULL para classe criada a partir de {EROSAO_127_A_PARTIR_DE}:")
            for nome in erodiveis:
                print(f"   · {nome} volta a 'indecisa' (registra, não acusa — não vira violação)")
            print("    A própria 127 previu isto: ela precisa ganhar a condição \"e ninguém decidiu")
            print("    explicitamente\" agora que existe um escritor de polaridade. Até lá, o efeito")
            print("    é degradação para indecisa, não acusação falsa — mas é silencioso, então fica dito.")

        if args.aplicar:
            conn.commit()
            print("\n✅ aplicado.")
            print("   O worker cacheia polaridade por ~5 min (inference.py `_polaridade_do_tenant`):")
            print("   a mudança só vale para alertas novos depois desse intervalo.")
            print("   Alertas JÁ gravados mudam de rótulo na leitura, não no dado.")
        else:
            conn.rollback()
            print("\nNada foi gravado. Reconfira com calibracao_classes.py e rode com --aplicar.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
