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

            # `yolo_classes.user_id` é NOT NULL (migration 003) e não tem default.
            # Herdamos o dono das classes que o tenant já tem, em vez de chumbar
            # um id: assim o script não inventa autoria nem quebra em outro banco.
            cur.execute(
                "SELECT user_id FROM public.yolo_classes"
                " WHERE tenant_id = %s AND user_id IS NOT NULL LIMIT 1",
                (tenant_id,),
            )
            dono = cur.fetchone()
            if not dono:
                print(
                    f"tenant '{TENANT_SLUG}' não tem nenhuma classe com dono — sem user_id para"
                    " herdar, e este script não inventa autoria. Cadastre a primeira classe pela"
                    " tela e rode de novo.",
                    file=sys.stderr,
                )
                return 1
            user_id = dono["user_id"]

            print(f"\ntenant {TENANT_SLUG} ({tenant_id})  módulo {MODULE_CODE}")
            print(f"modo: {'APLICAR' if args.aplicar else 'só mostrar (use --aplicar para valer)'}\n")

            erodiveis: list[str] = []  # conformidade gravada no TENANT — a 127 apaga essas

            for nome, alvo, porque in DECISOES:
                cur.execute(
                    "SELECT id, is_violation FROM public.yolo_classes"
                    " WHERE tenant_id = %s AND name = %s",
                    (tenant_id, nome),
                )
                atual = cur.fetchone()
                rotulo = {True: "acusa", False: "conformidade", None: "indecisa"}

                if atual is None:
                    # ⛔ NUNCA criar classe cujo nome já exista na UNIÃO. A polaridade
                    # servida é global(class_name) ∪ global(display_name) ∪ tenant, e o
                    # catálogo global casa pelos DOIS nomes. Criar uma linha de tenant
                    # homônima não muda nada na leitura e ainda PARTE a tela de Classes em
                    # duas entradas com o mesmo nome — uma com as anotações, outra zerada.
                    # Foi exatamente o que este script fez em 01/09 (ids 15/16/17, removidos):
                    # olhei só `class_name` do global e não vi que `display_name` já trazia
                    # 'Sem Óculos', 'Sem Luvas' e 'Óculos'.
                    cur.execute(
                        "SELECT class_name, display_name, is_violation"
                        "  FROM public.module_classes"
                        " WHERE module_code = %s"
                        "   AND (lower(class_name) = lower(%s) OR lower(display_name) = lower(%s))",
                        (MODULE_CODE, nome, nome),
                    )
                    global_ = cur.fetchone()
                    if global_:
                        print(
                            f"pular   {nome:<26} já vem do catálogo GLOBAL"
                            f" ({global_['class_name']} → {rotulo[global_['is_violation']]})"
                        )
                        if global_["is_violation"] is not alvo:
                            print(
                                f"        ⚠️  o global diz {rotulo[global_['is_violation']]} e a régua"
                                f" pede {rotulo[alvo]} — a união NÃO subtrai, então criar aqui não"
                                " resolveria. Rebaixar no global é ato de plataforma (ADR-0071)."
                            )
                        continue

                    if alvo is False:
                        erodiveis.append(nome)
                    acao = f"CRIAR   {nome:<26} → {rotulo[alvo]}"
                    if args.aplicar:
                        cur.execute(
                            "INSERT INTO public.yolo_classes"
                            " (tenant_id, user_id, module_code, name, is_violation)"
                            " VALUES (%s, %s, %s, %s, %s)",
                            (tenant_id, user_id, MODULE_CODE, nome, alvo),
                        )
                elif atual["is_violation"] is alvo:
                    print(f"ok      {nome:<26} já está em {rotulo[alvo]}")
                    continue
                else:
                    if alvo is False:
                        erodiveis.append(nome)
                    acao = (f"MUDAR   {nome:<26} {rotulo[atual['is_violation']]} → {rotulo[alvo]}")
                    if args.aplicar:
                        cur.execute(
                            "UPDATE public.yolo_classes SET is_violation = %s"
                            " WHERE tenant_id = %s AND name = %s",
                            (alvo, tenant_id, nome),
                        )
                print(f"{acao}\n        porque: {porque}")

        # Aviso de erosão: só CONFORMIDADE (False) gravada NO TENANT é apagada pela 127.
        # Classe que veio do catálogo global não passa por aqui — a 127 só toca
        # `yolo_classes`. Por isso a lista sai do que o loop realmente gravaria,
        # não das DECISOES: senão o script avisa de um risco que não corre.
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
