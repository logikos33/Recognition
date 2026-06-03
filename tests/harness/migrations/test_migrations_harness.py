"""
Harness de migrations — Fase D1 (Eval-Driven Development).

EVAL: migrations-harness
Fonte de verdade: infra/migrations/*.sql aplicadas em Postgres 15 efêmero.
Critério pass: runner 2x exit 0 + todos os asserts verdes.
Princípios protegidos: C-02 (idempotência), C-04 (schema real), C-08 (eval antes de merge).

Contexto: run.sh/CI já executou runner --pass 1 e --pass 2 antes deste arquivo rodar.
Os testes de idempotência (test_runner_*) executam passadas adicionais para confirmar estabilidade.
Os testes de schema verificam o estado resultante das 54 migrations.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # repo root
RUNNER = ROOT / "tests" / "harness" / "migrations" / "runner.py"


def _run_runner(pass_n: int) -> subprocess.CompletedProcess:
    env = {**os.environ, "HARNESS_DATABASE_URL": os.environ.get("HARNESS_DATABASE_URL", "")}
    return subprocess.run(
        [sys.executable, str(RUNNER), "--pass", str(pass_n)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# EVAL CENTRAL — Idempotência (C-02)
# ---------------------------------------------------------------------------


def test_first_pass_clean_db(pg_conn):
    """C-02: passada adicional do runner num banco já migrado retorna exit 0.

    Em run.sh/CI, a 1ª passada num banco limpo e a 2ª (idempotência) foram
    verificadas pelo exit code da shell antes de pytest rodar. Este teste confirma
    que o runner permanece estável em passadas subsequentes (convergência).
    """
    result = _run_runner(3)
    assert result.returncode == 0, (
        "viola C-02: runner não é idempotente em passada adicional\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_second_pass_idempotent(pg_conn):
    """C-02: segunda passada adicional confirma estabilidade total (zero ❌ não-idempotentes)."""
    result = _run_runner(4)
    assert result.returncode == 0, (
        "viola C-02: runner falhou em segunda passada adicional\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Schema — Tabelas da Fase 1 em public (C-04)
# ---------------------------------------------------------------------------


PHASE1_TABLES = ["edge_sites", "device_tokens", "enrollment_tokens", "edge_heartbeats"]


@pytest.mark.parametrize("table_name", PHASE1_TABLES)
def test_phase1_tables_in_public(pg_conn, table_name):
    """C-04: tabelas da Fase 1 existem em public após aplicar as 54 migrations."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row["cnt"] == 1, f"viola C-04: tabela public.{table_name} não existe no schema final"


# ---------------------------------------------------------------------------
# Schema — site_id nas tabelas core (C-04)
# ---------------------------------------------------------------------------


TABLES_WITH_SITE_ID = ["cameras", "alerts", "counting_events", "operations"]


@pytest.mark.parametrize("table_name", TABLES_WITH_SITE_ID)
def test_site_id_columns(pg_conn, table_name):
    """C-04: coluna site_id existe em public.{table_name} (adicionada pela migration 052)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = 'site_id'
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"viola C-04: coluna site_id ausente em public.{table_name}"
    assert row["udt_name"] == "uuid", (
        f"viola C-04: site_id em public.{table_name} deveria ser uuid, é {row['udt_name']}"
    )


# ---------------------------------------------------------------------------
# Schema — tenants.deployment_mode (C-04)
# ---------------------------------------------------------------------------


def test_tenants_deployment_mode_column(pg_conn):
    """C-04: coluna deployment_mode existe em public.tenants com default 'cloud'."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'tenants'
              AND column_name = 'deployment_mode'
            """
        )
        row = cur.fetchone()
    assert row is not None, "viola C-04: coluna deployment_mode ausente em public.tenants"
    default = row["column_default"] or ""
    assert "'cloud'" in default, (
        f"viola C-04: deployment_mode deveria ter default 'cloud', encontrado: {default}"
    )


def test_tenants_deployment_mode_check(pg_conn):
    """C-04: CHECK constraint de deployment_mode inclui cloud, edge, hybrid."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(c.oid) AS def
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname = 'public'
              AND t.relname = 'tenants'
              AND c.contype = 'c'
              AND pg_get_constraintdef(c.oid) LIKE '%deployment_mode%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "viola C-04: CHECK constraint de deployment_mode não encontrado"
    definition = row["def"]
    for mode in ("cloud", "edge", "hybrid"):
        assert mode in definition, (
            f"viola C-04: modo '{mode}' ausente no CHECK constraint: {definition}"
        )


# ---------------------------------------------------------------------------
# Schema — create_tenant_schema referencia site_id (C-04)
# ---------------------------------------------------------------------------


def test_create_tenant_schema_has_site_id(pg_conn):
    """C-04: função create_tenant_schema (054) referencia site_id (adicionado à Fase 1)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_functiondef(p.oid) AS def
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND p.proname = 'create_tenant_schema'
            """
        )
        row = cur.fetchone()
    assert row is not None, "viola C-04: função public.create_tenant_schema não encontrada"
    assert "site_id" in row["def"], (
        "viola C-04: create_tenant_schema não referencia site_id "
        "(esperado após migration 054_create_tenant_schema_site_id.sql)"
    )


# ---------------------------------------------------------------------------
# Anti-regressão — ip_cameras NÃO deve existir (anti-padrão)
# ---------------------------------------------------------------------------


def test_anti_regression_ip_cameras(pg_conn):
    """Anti-padrão: public.ip_cameras NÃO deve existir no schema final.

    ip_cameras foi renomeada para cameras na migration 013_consolidate_cameras.sql.
    Referenciar ip_cameras é um bug (ver seção Anti-padrões do CLAUDE.md).
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'ip_cameras'
            """
        )
        row = cur.fetchone()
    assert row["cnt"] == 0, (
        "anti-padrão: public.ip_cameras existe no schema final — "
        "use public.cameras (renomeada na migration 013)"
    )


# ---------------------------------------------------------------------------
# Paridade com produção — schema_migrations é parte do schema legítimo (001)
# ---------------------------------------------------------------------------


def test_schema_migrations_created_by_001(pg_conn):
    """Paridade com prod: public.schema_migrations existe porque 001_initial_schema.sql a cria.

    Nota: este é um artefato do schema histórico, não do tracker de migrations.
    railway_start.run_migrations() não usa esta tabela para rastrear execuções.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'schema_migrations'
            """
        )
        row = cur.fetchone()
    assert row["cnt"] == 1, (
        "public.schema_migrations não existe — 001_initial_schema.sql deve criá-la"
    )


# ---------------------------------------------------------------------------
# Regressão — escopo da tolerância de erro legado (sem banco)
# ---------------------------------------------------------------------------


def test_legacy_tolerance_is_scoped_to_038():
    """Garante que _is_known_legacy não tem blind spot global.

    A tolerância de ip_cameras deve ser escopada APENAS à 038_operations.sql.
    Qualquer outro arquivo que referencie ip_cameras (ou marcador similar) deve
    ser erro FATAL (❌, exit 1) — exatamente o bug que o harness existe pra pegar.

    Não requer banco (sem pg_conn) — testa a função pura diretamente.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from runner import _is_known_legacy  # função pura, sem banco

    # 038 + ip_cameras: tolerado (legado conhecido, corrigido pela 047)
    assert _is_known_legacy("038_operations.sql", 'relation "ip_cameras" does not exist') is True
    # OUTRO arquivo com ip_cameras: NÃO tolerado (seria erro fatal real)
    assert _is_known_legacy("055_qualquer.sql", 'relation "ip_cameras" does not exist') is False
    # erro não-legado na própria 038: NÃO tolerado
    assert _is_known_legacy("038_operations.sql", 'column "foo" does not exist') is False


# ---------------------------------------------------------------------------
# Autocorreção — migrations legadas toleradas (038/039) convertem estado final (C-04)
# ---------------------------------------------------------------------------


LEGACY_TOLERATED_TABLES = ["operations", "operation_results"]


@pytest.mark.parametrize("table_name", LEGACY_TOLERATED_TABLES)
def test_legacy_tolerated_migrations_autocorrect(pg_conn, table_name):
    """Migrations 038/039 falham em banco virgem (toleradas), mas o estado final
    tem que existir — 047 cria operations, 048 cria operation_results.

    Se este teste falhar, a tolerância em KNOWN_LEGACY_ERRORS está mascarando
    um bug real: o estado não autocorrige.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row["cnt"] == 1, (
        f"viola C-04: public.{table_name} ausente — a tolerância de erro legado "
        f"em runner.KNOWN_LEGACY_ERRORS está mascarando bug real (não autocorrige)."
    )
