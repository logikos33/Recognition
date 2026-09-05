#!/usr/bin/env python3
"""Aplica ao catálogo do tenant a decisão que a régua da ADR-0067 já tomou.

Isto NÃO é migration, de propósito: polaridade de classe é dado de cliente e
decisão humana. Script manual, env-gated, com dry-run por padrão.

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

A DECISÃO FICA MARCADA (migration 136). Sem a marca
(`violation_decision` + `violation_decided_at`) esta calibração era desfeita no
boot seguinte: em modo LEGADO — o da produção — o runner reexecuta TODA
migration a cada deploy, e o primeiro UPDATE da 125 casa o prefixo "Sem "/"Uso
incorreto" e devolve "Sem protetor de ouvido" para TRUE, ou seja, ela volta a
ACUSAR quem cumpre. Com a marca gravada, a 136 restaura a decisão na mesma
passagem de boot. Prova: services/api/tests/integration/
test_polaridade_decidida_sobrevive.py.

⛔ NÃO CRIA CLASSE. Duas razões, ambas medidas: (a) 'Sem Óculos', 'Sem Luvas' e
'Óculos' já existem no catálogo GLOBAL (`module_classes`, como `display_name`
de no_glasses/no_gloves/glasses) — criar homônima em `yolo_classes` duplicaria
a taxonomia e partiria o acervo em dois `class_id` (ADR-0071, e é o que
`TenantClassService._reject_if_in_global_catalog` bloqueia nas rotas); (b)
`yolo_classes.user_id` é NOT NULL com FK para users, então o INSERT anterior
deste script nem chegava a rodar. Classe que não existe é cadastro, não
calibração: o script reporta e segue.

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

# (nome, is_violation, porquê) — o porquê fica aqui e no relatório, não no banco.
# NULL = indecisa (registra, não acusa). True = acusa. False = conformidade.
DECISOES = [
    ("Sem protetor de ouvido", None, "27,3% de precisão em 22 julgados — ADR-0067 já a reprovava a 40%"),
    ("Uso incorreto de mascara", None, "20,0% em 10 julgados — passava a 61,9% no dataset, não transferiu"),
    ("Sem Óculos", None, "30,4% em 23 julgados — acusa quem cumpre em 70% dos avisos"),
    ("Sem Luvas", True, "69,7% em 33 julgados — sustenta a régua"),
    ("Óculos", False, "classe de presença: alimenta conformidade, nunca alerta"),
]

ROTULO = {True: "acusa", False: "conformidade", None: "indecisa"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o que mudaria")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 2

    pendencias: list[str] = []
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
                    "SELECT id, is_violation, violation_decided_at"
                    "  FROM public.yolo_classes"
                    " WHERE tenant_id = %s AND lower(name) = lower(%s)",
                    (tenant_id, nome),
                )
                atual = cur.fetchone()

                if atual is not None:
                    ja_no_alvo = atual["is_violation"] is alvo
                    ja_marcada = atual["violation_decided_at"] is not None
                    if ja_no_alvo and ja_marcada:
                        print(f"ok       {nome:<26} já está em {ROTULO[alvo]}, decisão marcada")
                        continue
                    if ja_no_alvo:
                        acao = f"MARCAR   {nome:<26} {ROTULO[alvo]} (valor certo, faltava a marca)"
                    else:
                        acao = f"MUDAR    {nome:<26} {ROTULO[atual['is_violation']]} → {ROTULO[alvo]}"
                    if args.aplicar:
                        cur.execute(
                            "UPDATE public.yolo_classes"
                            "   SET is_violation = %s,"
                            "       violation_decision = %s,"
                            "       violation_decided_at = NOW()"
                            " WHERE id = %s",
                            (alvo, alvo, atual["id"]),
                        )
                    print(f"{acao}\n         porque: {porque}")
                    continue

                # Não é classe do tenant. Está no catálogo GLOBAL?
                cur.execute(
                    "SELECT class_name, display_name, is_violation"
                    "  FROM public.module_classes"
                    " WHERE module_code = %s"
                    "   AND (lower(class_name) = lower(%s) OR lower(display_name) = lower(%s))",
                    (MODULE_CODE, nome, nome),
                )
                global_ = cur.fetchone()
                if global_ is not None:
                    onde = f"catálogo global ({global_['class_name']})"
                    if global_["is_violation"] is alvo:
                        print(f"ok       {nome:<26} já está em {ROTULO[alvo]} no {onde}")
                    else:
                        print(
                            f"⚠️  FORA   {nome:<26} está em {ROTULO[global_['is_violation']]} "
                            f"no {onde}, alvo é {ROTULO[alvo]}"
                        )
                        pendencias.append(
                            f"{nome}: {ROTULO[global_['is_violation']]} → {ROTULO[alvo]} "
                            f"no {onde} — o catálogo global é COMPARTILHADO entre tenants, "
                            "mudar ali é decisão de produto, não calibração de um cliente"
                        )
                    continue

                print(f"⚠️  AUSENTE {nome:<26} não existe nem no tenant nem no catálogo global")
                pendencias.append(
                    f"{nome}: classe inexistente — cadastrá-la é decisão de cadastro "
                    "(precisa de dono/user_id) e o Estúdio já exige a polaridade na criação"
                )

        if args.aplicar:
            conn.commit()
            print("\n✅ aplicado — e a decisão está MARCADA (migration 136), sobrevive ao redeploy.")
            print("   O worker cacheia polaridade por ~5 min (inference.py `_polaridade_do_tenant`):")
            print("   a mudança só vale para alertas novos depois desse intervalo.")
            print("   Alertas JÁ gravados mudam de rótulo na leitura, não no dado.")
        else:
            conn.rollback()
            print("\nNada foi gravado. Reconfira com calibracao_classes.py e rode com --aplicar.")

        if pendencias:
            print("\n⚠️  NÃO RESOLVIDO POR ESTE SCRIPT (de propósito):")
            for p in pendencias:
                print(f"   · {p}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
