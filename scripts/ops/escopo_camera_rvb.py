#!/usr/bin/env python3
"""Mostra (e opcionalmente ajusta) o ESCOPO DE CLASSES por câmera do RVB.

Por que existe: em 01/09 o retroativo processou 46 frames sem erro nenhum e
criou ZERO alerta — `sem_deteccao_violacao=46`. O modelo detectava e o escopo
descartava. Medido: 13 das 14 câmeras com deployment ativo têm escopo composto
SÓ de classes de conformidade (Botas, Luvas, mascara, Óculos, Protetor
auditivo). As duas únicas classes que hoje acusam — `Sem Luvas` (69,7%) e
`Sem mascara` (63,6%) — não estão no escopo de NENHUMA câmera.

Ou seja: por construção, nenhuma câmera podia gerar violação. O log do worker
já dizia (`camera_escopo_descartou_tudo: ... 100% fora costuma ser dicionário
de classe errado, não turno limpo`) — faltava alguém ler.

O escopo vive em `model_deployments.config->>'classes'` e é o que a aba
"Modelos por câmera" edita. `_no_escopo_da_camera` (inference.py) o aplica; sem
escopo gravado (NULL) nada é filtrado.

⚠️ Isto altera CONFIGURAÇÃO DE PRODUÇÃO de um cliente. Dry-run por padrão, e
`--aplicar` exige `CONFIRM_OPS=1`. Rode o dry-run e leia antes.

Uso:
    DATABASE_URL=... python3 scripts/ops/escopo_camera_rvb.py            # só mostra
    DATABASE_URL=... python3 scripts/ops/escopo_camera_rvb.py --adicionar "Sem Luvas" "Sem mascara" --camera 17bbada9 2a683620
    DATABASE_URL=... CONFIRM_OPS=1 python3 scripts/ops/escopo_camera_rvb.py --adicionar "Sem Luvas" --camera 17bbada9 --aplicar
"""

import argparse
import json
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

TENANT_SLUG = "rvb"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adicionar", nargs="*", default=[], metavar="CLASSE",
                    help="classes a acrescentar ao escopo (nome exato do catálogo)")
    ap.add_argument("--camera", nargs="*", default=[], metavar="PREFIXO",
                    help="prefixos de id de câmera; vazio = todas as ativas")
    ap.add_argument("--aplicar", action="store_true", help="sem isto, só mostra")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 2
    if args.aplicar and os.environ.get("CONFIRM_OPS") != "1":
        print("--aplicar exige CONFIRM_OPS=1 (isto muda config de produção).", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Quais classes REALMENTE acusam hoje: união global ∪ tenant, casando
            # pelos dois nomes do catálogo global (ADR-0071 — foi o display_name
            # que ninguém olhou da última vez).
            cur.execute(
                """
                SELECT lower(class_name) AS n FROM public.module_classes
                 WHERE module_code = 'epi' AND is_violation IS TRUE
                UNION
                SELECT lower(display_name) FROM public.module_classes
                 WHERE module_code = 'epi' AND is_violation IS TRUE AND display_name IS NOT NULL
                UNION
                SELECT lower(name) FROM public.yolo_classes
                 WHERE module_code = 'epi' AND is_violation IS TRUE
                   AND tenant_id = (SELECT id FROM public.tenants WHERE slug = %s)
                """,
                (TENANT_SLUG,),
            )
            acusam = {r["n"] for r in cur.fetchall()}

            cur.execute(
                """
                SELECT md.id, md.camera_id, md.config
                  FROM public.model_deployments md
                  JOIN public.tenants t ON t.id = md.tenant_id AND t.slug = %s
                 WHERE md.status = 'active'
                 ORDER BY md.camera_id
                """,
                (TENANT_SLUG,),
            )
            deploys = cur.fetchall()

            print(f"\ntenant {TENANT_SLUG} — {len(deploys)} deployments ativos")
            print(f"classes que ACUSAM hoje: {sorted(acusam)}")
            print(f"modo: {'APLICAR' if args.aplicar else 'só mostrar'}\n")

            mudados = 0
            for d in deploys:
                cam = str(d["camera_id"])
                if args.camera and not any(cam.startswith(p) for p in args.camera):
                    continue
                cfg = d["config"] or {}
                escopo = list(cfg.get("classes") or [])
                # Uma câmera só consegue gerar violação se o escopo tiver ao menos
                # uma classe que acusa. Escopo vazio (None) não filtra nada.
                pode = [c for c in escopo if c.lower() in acusam]
                marca = "  " if pode else "⛔"
                print(f"{marca} {cam[:8]}  {escopo}")
                if not pode:
                    print("     └─ nenhuma classe que acusa: esta câmera NÃO pode gerar violação")

                novas = [c for c in args.adicionar if c not in escopo]
                if not novas:
                    continue
                fora = [c for c in novas if c.lower() not in acusam]
                if fora:
                    print(f"     ⚠️  {fora} não acusa(m) hoje — acrescentar não gera violação")
                print(f"     → acrescentaria {novas}")
                mudados += 1
                if args.aplicar:
                    cfg["classes"] = escopo + novas
                    cur.execute(
                        "UPDATE public.model_deployments SET config = %s WHERE id = %s",
                        (json.dumps(cfg), d["id"]),
                    )

        if args.aplicar and mudados:
            conn.commit()
            print(f"\n✅ {mudados} deployment(s) atualizado(s).")
            print("   O worker cacheia o escopo por câmera — pode levar alguns minutos.")
            print("   Reverter = rodar de novo com o escopo antigo (está impresso acima).")
        else:
            conn.rollback()
            print("\nNada gravado." if not args.aplicar else "\nNada a mudar.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
