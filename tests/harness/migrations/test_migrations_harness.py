"""
Harness de migrations — Fase D1 (Eval-Driven Development).

EVAL: migrations-harness
Fonte de verdade: infra/migrations/*.sql aplicadas em Postgres 15 efêmero.
Critério pass: runner 2x exit 0 + todos os asserts verdes.
Princípios protegidos: C-02 (idempotência), C-04 (schema real), C-08 (eval antes de merge).

Contexto: run.sh/CI já executou runner --pass 1 e --pass 2 antes deste arquivo rodar.
Os testes de idempotência (test_runner_*) executam passadas adicionais para confirmar estabilidade.
Os testes de schema verificam o estado resultante de TODAS as migrations em
infra/migrations/ (atualmente 001→106), incluindo o pipeline de treinamento (093–101).
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
    """C-04: tabelas da Fase 1 existem em public após aplicar todas as migrations."""
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
    """C-04: coluna site_id existe em public.{table_name} (adicionada pela migration 067)."""
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
    """C-04: função create_tenant_schema (069) referencia site_id (adicionado à Fase 1)."""
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
        "(esperado após migration 069_create_tenant_schema_site_id.sql)"
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


# ---------------------------------------------------------------------------
# Schema — Pipeline de treinamento: tabelas novas 093-101 (C-01, C-04)
# ---------------------------------------------------------------------------


TRAINING_PIPELINE_TABLES = [
    "datasets",            # 096
    "recorders",           # 099
    "model_deployments",   # 100
    "model_evaluations",   # 101
    "model_drift_metrics", # 101
]


@pytest.mark.parametrize("table_name", TRAINING_PIPELINE_TABLES)
def test_training_pipeline_tables_in_public(pg_conn, table_name):
    """C-04: tabelas do pipeline de treinamento (093-101) existem em public."""
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


@pytest.mark.parametrize("table_name", TRAINING_PIPELINE_TABLES)
def test_training_pipeline_tables_tenant_id_not_null(pg_conn, table_name):
    """C-01: toda tabela nova do pipeline tem tenant_id UUID NOT NULL."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT udt_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = 'tenant_id'
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"viola C-01: coluna tenant_id ausente em public.{table_name}"
    assert row["udt_name"] == "uuid", (
        f"viola C-01: tenant_id em public.{table_name} deveria ser uuid, é {row['udt_name']}"
    )
    assert row["is_nullable"] == "NO", (
        f"viola C-01: tenant_id em public.{table_name} deveria ser NOT NULL"
    )


@pytest.mark.parametrize("table_name", TRAINING_PIPELINE_TABLES)
def test_training_pipeline_tables_tenant_id_fk(pg_conn, table_name):
    """C-01: tenant_id nas tabelas novas do pipeline referencia public.tenants(id)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            JOIN pg_class ft ON c.confrelid = ft.oid
            JOIN pg_namespace fn ON ft.relnamespace = fn.oid
            JOIN unnest(c.conkey) AS ck(attnum) ON TRUE
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ck.attnum
            WHERE n.nspname = 'public'
              AND t.relname = %s
              AND c.contype = 'f'
              AND fn.nspname = 'public'
              AND ft.relname = 'tenants'
              AND a.attname = 'tenant_id'
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row["cnt"] >= 1, (
        f"viola C-01: FK tenant_id → public.tenants(id) ausente em public.{table_name}"
    )


# ---------------------------------------------------------------------------
# Schema — Pipeline de treinamento: colunas novas 093-101 (C-04)
# ---------------------------------------------------------------------------


TRAINING_PIPELINE_COLUMNS = [
    # 094 — training_frames: múltiplas fontes de imagens
    ("training_frames", "source"),
    ("training_frames", "r2_key"),
    ("training_frames", "camera_id"),
    ("training_frames", "recorder_id"),
    ("training_frames", "width"),
    ("training_frames", "height"),
    ("training_frames", "model_confidence"),
    ("training_frames", "captured_at"),
    ("training_frames", "tenant_id"),
    # 093 — yolo_classes: escopo tenant+módulo
    ("yolo_classes", "tenant_id"),
    ("yolo_classes", "module_code"),
    # 095 — frame_annotations: proveniência
    ("frame_annotations", "source"),
    ("frame_annotations", "created_by"),
    ("frame_annotations", "reviewed_by"),
    # 096 — dataset_versions: linhagem e build
    ("dataset_versions", "dataset_id"),
    ("dataset_versions", "tenant_id"),
    ("dataset_versions", "module_code"),
    ("dataset_versions", "split"),
    ("dataset_versions", "augmentations"),
    ("dataset_versions", "coco_r2_key"),
    ("dataset_versions", "export_format"),
    ("dataset_versions", "status"),
    # 097 — training_jobs: pipeline MLOps
    ("training_jobs", "dataset_version_id"),
    ("training_jobs", "framework"),
    ("training_jobs", "base_model"),
    ("training_jobs", "hyperparams"),
    ("training_jobs", "gpu_provider"),
    ("training_jobs", "gpu_instance_ref"),
    ("training_jobs", "callback_token"),
    # 098 — trained_models: registry + linhagem
    ("trained_models", "framework"),
    ("trained_models", "r2_onnx_key"),
    ("trained_models", "r2_weights_key"),
    ("trained_models", "metrics"),
    ("trained_models", "dataset_version_id"),
    ("trained_models", "module_code"),
]


@pytest.mark.parametrize(
    ("table_name", "column_name"),
    TRAINING_PIPELINE_COLUMNS,
    ids=[f"{t}.{c}" for t, c in TRAINING_PIPELINE_COLUMNS],
)
def test_training_pipeline_columns(pg_conn, table_name, column_name):
    """C-04: colunas do pipeline de treinamento (093-098) existem no schema final."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        row = cur.fetchone()
    assert row["cnt"] == 1, (
        f"viola C-04: coluna {column_name} ausente em public.{table_name} "
        f"(esperada após migrations 093-101)"
    )


# ---------------------------------------------------------------------------
# Schema — Pipeline de treinamento: CHECKs e FK (C-04)
# ---------------------------------------------------------------------------


TRAINING_PIPELINE_CHECKS = [
    # (tabela, constraint, valores que o CHECK precisa cobrir)
    ("training_frames", "chk_training_frames_source", ("auto", "nvr", "upload", "video")),
    ("recorders", "chk_recorders_protocol", ("onvif", "hikvision", "dahua", "intelbras", "rtsp")),
]


@pytest.mark.parametrize(
    ("table_name", "constraint_name", "expected_values"),
    TRAINING_PIPELINE_CHECKS,
    ids=[c for _, c, _ in TRAINING_PIPELINE_CHECKS],
)
def test_training_pipeline_check_constraints(pg_conn, table_name, constraint_name, expected_values):
    """C-04: CHECK constraints do pipeline (094/099) existem e cobrem os valores esperados."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(c.oid) AS def
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname = 'public'
              AND t.relname = %s
              AND c.contype = 'c'
              AND c.conname = %s
            """,
            (table_name, constraint_name),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"viola C-04: CHECK {constraint_name} ausente em public.{table_name}"
    )
    definition = row["def"]
    for value in expected_values:
        assert value in definition, (
            f"viola C-04: valor '{value}' ausente no CHECK {constraint_name}: {definition}"
        )


def test_training_frames_recorder_fk(pg_conn):
    """C-04: FK fk_training_frames_recorder existe (099) e aponta para public.recorders."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ft.relname AS ref_table
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            JOIN pg_class ft ON c.confrelid = ft.oid
            WHERE n.nspname = 'public'
              AND t.relname = 'training_frames'
              AND c.contype = 'f'
              AND c.conname = 'fk_training_frames_recorder'
            """
        )
        row = cur.fetchone()
    assert row is not None, (
        "viola C-04: FK fk_training_frames_recorder ausente em public.training_frames — "
        "a guarda de existência da 099 pode ter pulado o FK (coluna recorder_id ausente na 094?)"
    )
    assert row["ref_table"] == "recorders", (
        f"viola C-04: fk_training_frames_recorder referencia {row['ref_table']}, "
        "esperado public.recorders"
    )
