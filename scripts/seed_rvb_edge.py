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

# RVB_SITE_ID é determinístico (edge_site — o SITE_ID do enrollment). O tenant é
# resolvido por slug em runtime (robusto a tenant pré-existente com outro id), igual
# ao seed_rvb.py — os dois scripts convergem no MESMO tenant real.
RVB_TENANT_SLUG = "rvb"
RVB_TENANT_ID_OVERRIDE = os.environ.get("RVB_TENANT_ID")  # opcional: forçar tenant por id
RVB_SITE_ID = "11111111-0000-0000-0000-0000000000e1"  # edge_site RVB


def _resolve_tenant_id(cur) -> str:
    """Resolve o id real do tenant RVB por slug (ou RVB_TENANT_ID se setado).

    Não cria o tenant — ele deve existir (rode scripts/seed_rvb.py antes).
    """
    if RVB_TENANT_ID_OVERRIDE:
        cur.execute("SELECT id FROM tenants WHERE id = %s", (RVB_TENANT_ID_OVERRIDE,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"RVB_TENANT_ID={RVB_TENANT_ID_OVERRIDE} não existe.")
        return str(row[0])
    cur.execute("SELECT id FROM tenants WHERE slug = %s", (RVB_TENANT_SLUG,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(
            f"Tenant slug='{RVB_TENANT_SLUG}' não existe — rode scripts/seed_rvb.py primeiro."
        )
    return str(row[0])

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
        # ── FASE 1 (CRÍTICA) — edge_site em transação PRÓPRIA, commitada e VERIFICADA
        # dentro do script antes de tocar em câmera. Motivo: no seed antigo o insert
        # do edge_site dividia transação com os 28 UPDATEs de câmera; qualquer UPDATE
        # que falhasse (ex.: public.cameras sem a coluna active_module) abortava a
        # transação e fazia ROLLBACK do edge_site junto — o "Done" nunca saía, mas o
        # erro passava despercebido → banco vazio "reportado como criado". Agora é
        # impossível reportar sucesso sem a linha (SELECT de verificação abaixo).
        tenant_id = _resolve_tenant_id(cur)
        print(f"Tenant RVB: {tenant_id}")

        print(f"Upserting edge_site RVB (deployment_mode={DEPLOYMENT_MODE})...")
        cur.execute(
            """
            INSERT INTO public.edge_sites (id, tenant_id, name, location, deployment_mode, status)
            VALUES (%s, %s, 'RVB Blumenau', 'Blumenau/SC', %s, 'provisioning')
            ON CONFLICT (id) DO UPDATE SET deployment_mode = EXCLUDED.deployment_mode
            """,
            (RVB_SITE_ID, tenant_id, DEPLOYMENT_MODE),
        )
        conn.commit()

        # Verificação intra-script (C-04): a linha TEM que existir após o commit.
        cur.execute(
            "SELECT id, tenant_id, status, deployment_mode "
            "FROM public.edge_sites WHERE id = %s",
            (RVB_SITE_ID,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                "edge_site não persistiu após COMMIT — abortando sem falso sucesso."
            )
        print(f"  edge_site VERIFICADO: id={row[0]} tenant_id={row[1]} "
              f"status={row[2]} mode={row[3]}")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR (edge_site — FASE CRÍTICA): {exc}")
        cur.close()
        conn.close()
        raise

    # ── FASE 2 (NÃO-CRÍTICA) — atribuição de módulo por câmera. Transação separada:
    # uma falha aqui (schema de public.cameras) loga WARNING e NÃO derruba o edge_site,
    # que já está criado e verificado. Não é pré-requisito do enrollment/heartbeat.
    counts = {"epi": 0, "counting": 0, "quality": 0}
    try:
        for i in range(1, 29):
            cam_id = str(uuid.uuid5(uuid.UUID(tenant_id), f"cam-{i:03d}"))
            g = group_for(i)
            counts[g] += 1
            model_id = MODEL_VAL[g]
            if model_id:
                cur.execute(
                    f"""
                    UPDATE cameras SET active_module = %s, {MODEL_COL[g]} = %s
                    WHERE id = %s AND tenant_id = %s
                    """,
                    (g, model_id, cam_id, tenant_id),
                )
            else:
                cur.execute(
                    "UPDATE cameras SET active_module = %s WHERE id = %s AND tenant_id = %s",
                    (g, cam_id, tenant_id),
                )
        conn.commit()
        print(f"  câmeras por módulo: {counts}")
        pending = [m for m, v in MODEL_VAL.items() if not v]
        if pending:
            print(f"  PENDENTE: pin de modelo para {pending} — passe RVB_MODEL_*_ID "
                  "com os UUIDs registrados no box (só active_module foi fixado).")
    except Exception as exc:
        conn.rollback()
        print(f"WARNING: atribuição de módulo por câmera falhou (NÃO-crítico): {exc}")
        print("  → o edge_site JÁ está criado e verificado; refaça a atribuição depois "
              "quando o schema de public.cameras estiver alinhado.")
    finally:
        cur.close()
        conn.close()

    print("\nDone.")
    print(f"  edge_site: RVB Blumenau (id={RVB_SITE_ID}, mode={DEPLOYMENT_MODE})")


if __name__ == "__main__":
    main()
