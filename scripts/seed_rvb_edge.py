#!/usr/bin/env python3
"""seed_rvb_edge.py — embarque RVB no edge (task-113 FASE 3).

Complementa `seed_rvb.py` (tenant + admin + 28 câmeras + módulo epi). Aqui fazemos
o VÍNCULO sistema↔edge do cenário multi-módulo:

  1. edge_site RVB em public.edge_sites (deployment_mode configurável).
  2. Atribuição de módulo + modelo POR CÂMERA (active_module + model_<módulo>_id),
     mapeando as 28 câmeras aos 3 grupos do CENARIO_RVB.

⚠️ DISCREPÂNCIAS DE SCHEMA A VALIDAR NO BOX (C-04 — este script NÃO foi rodado
   contra o banco real do edge; a sessão de nuvem não alcança o box):
  - deployment_mode: a MISSÃO pede "dual"; o SCHEMA REAL (migrations 065/067) só
    aceita 'cloud' | 'edge' | 'hybrid'. Usamos **'hybrid'** (LAN+cloud) = o "dual"
    pretendido. NÃO existe valor 'dual' — não invente (quebraria o CHECK).
  - tabela de câmeras: CLAUDE.md diz que câmeras vivem em {tenant_schema}.cameras;
    seed_rvb.py insere em public.cameras (com tenant_id). Este script segue o
    seed_rvb.py (mesma tabela, mesmos UUIDs determinísticos) para ser consistente.
    CONFERIR no banco real qual tabela tem os dados antes de rodar em produção.

Hard gate igual ao seed_rvb.py: só roda com RVB_SEED_ENABLED=true. Idempotente.

Uso:
    RVB_SEED_ENABLED=true DATABASE_URL=postgresql://... \
    RVB_DEPLOYMENT_MODE=hybrid \
    [RVB_MODEL_EPI_ID=<uuid> RVB_MODEL_QUALITY_ID=<uuid> RVB_MODEL_COUNTING_ID=<uuid>] \
    python3 scripts/seed_rvb_edge.py
"""
import os
import sys
import uuid

if os.environ.get("RVB_SEED_ENABLED") != "true":
    print("ERROR: RVB_SEED_ENABLED != 'true'. Aborting to prevent accidental seed.")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

DEPLOYMENT_MODE = os.environ.get("RVB_DEPLOYMENT_MODE", "hybrid")
if DEPLOYMENT_MODE not in ("cloud", "edge", "hybrid"):
    print(f"ERROR: deployment_mode inválido {DEPLOYMENT_MODE!r} "
          "(schema aceita só cloud|edge|hybrid — 'dual' NÃO existe).")
    sys.exit(1)

# Modelos por módulo (UUIDs registrados no box). Opcionais: se ausentes, só o
# roteamento de módulo (active_module) é fixado; o pin de modelo fica pendente.
MODEL_EPI_ID = os.environ.get("RVB_MODEL_EPI_ID")
MODEL_QUALITY_ID = os.environ.get("RVB_MODEL_QUALITY_ID")
MODEL_COUNTING_ID = os.environ.get("RVB_MODEL_COUNTING_ID")

try:
    import psycopg2
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}\n  pip install psycopg2-binary")
    sys.exit(1)

# Mesmos UUIDs determinísticos do seed_rvb.py (idempotência entre os dois scripts).
RVB_TENANT_ID = "11111111-0000-0000-0000-000000000001"
RVB_SITE_ID = "11111111-0000-0000-0000-0000000000e1"  # edge_site RVB

# Mapa câmera(1-based, ordem do seed_rvb.py) -> grupo do CENARIO_RVB.
# EPI 16 · Estacionamento(counting) 8 · Qualidade(aux+principal) 4.
def group_for(idx: int) -> str:
    if 1 <= idx <= 16:
        return "epi"
    if 17 <= idx <= 24:
        return "counting"   # Estacionamento = módulo counting (valor válido do schema)
    return "quality"        # 25..28: Qualidade aux (25-26) + principal (27-28)


MODEL_COL = {"epi": "model_epi_id", "counting": "model_counting_id",
             "quality": "model_quality_id"}
MODEL_VAL = {"epi": MODEL_EPI_ID, "counting": MODEL_COUNTING_ID,
             "quality": MODEL_QUALITY_ID}


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1. edge_site (public.edge_sites — schema verificado em migration 065)
        print(f"Upserting edge_site RVB (deployment_mode={DEPLOYMENT_MODE})...")
        cur.execute(
            """
            INSERT INTO public.edge_sites (id, tenant_id, name, location, deployment_mode, status)
            VALUES (%s, %s, 'RVB Blumenau', 'Blumenau/SC', %s, 'provisioning')
            ON CONFLICT (id) DO UPDATE SET deployment_mode = EXCLUDED.deployment_mode
            """,
            (RVB_SITE_ID, RVB_TENANT_ID, DEPLOYMENT_MODE),
        )

        # 2. Atribuição de módulo + modelo por câmera (colunas verificadas em migration 026)
        counts = {"epi": 0, "counting": 0, "quality": 0}
        for i in range(1, 29):
            cam_id = str(uuid.uuid5(uuid.UUID(RVB_TENANT_ID), f"cam-{i:03d}"))
            g = group_for(i)
            counts[g] += 1
            model_id = MODEL_VAL[g]
            if model_id:
                cur.execute(
                    f"""
                    UPDATE cameras SET active_module = %s, {MODEL_COL[g]} = %s
                    WHERE id = %s AND tenant_id = %s
                    """,
                    (g, model_id, cam_id, RVB_TENANT_ID),
                )
            else:
                cur.execute(
                    "UPDATE cameras SET active_module = %s WHERE id = %s AND tenant_id = %s",
                    (g, cam_id, RVB_TENANT_ID),
                )

        conn.commit()
        print("\nDone.")
        print(f"  edge_site: RVB Blumenau (id={RVB_SITE_ID}, mode={DEPLOYMENT_MODE})")
        print(f"  câmeras por módulo: {counts}")
        pending = [m for m, v in MODEL_VAL.items() if not v]
        if pending:
            print(f"  PENDENTE: pin de modelo para {pending} — passe RVB_MODEL_*_ID "
                  "com os UUIDs registrados no box (só active_module foi fixado).")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
