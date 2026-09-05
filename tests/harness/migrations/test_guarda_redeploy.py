"""Unidade da guarda de redeploy (issues #683 / #694) — sem banco, roda em ~10ms.

O teste de ponta a ponta é `test_redeploy_nao_apaga_dado.py`; estes aqui fixam o
detector, que é a peça que decide o que roda em produção e o que não roda. Um
falso NEGATIVO devolve a perda de dado; um falso POSITIVO faz uma migration
legítima nunca rodar em banco estabelecido — as duas direções têm teste.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MIGRACOES = Path(__file__).resolve().parents[3] / "infra" / "migrations"
sys.path.insert(0, str(_MIGRACOES))

import runner_core  # noqa: E402


# Os arquivos históricos que o detector pega. Congelado de propósito: migration
# NOVA nesta lista significa que alguém escreveu um DROP/DELETE/TRUNCATE novo,
# reescreveu senha ou reescreveu configuração de tenant — proibido pelo
# CLAUDE.md e, pior, o arquivo NÃO rodaria em produção (a guarda o pula). O
# check de CI (scripts/ci/check_migrations_hygiene.py) dá o mesmo sinal, sem
# banco.
#
# 023 e 034 entraram em 2026-09-05 (#743), quando o detector ganhou a terceira
# cara — "reescreve configuração". Elas sempre fizeram isso; o que mudou foi
# passarem a ser vistas.
_OFENSORES_CONHECIDOS = {
    "013_consolidate_cameras.sql",
    "023_tenant_schema_fields.sql",
    "027_superadmin_vitor.sql",
    "034_add_quality_module_to_tenants.sql",
    "040_reset_superadmin_password.sql",
    "046_deactivate_default_tenant.sql",
    "049_counting_deepsort_rebuild.sql",
}

# As três caras da mesma família, por arquivo — o que cada uma desfaz.
_FAMILIA_REESCREVE_CONFIG = {
    "023_tenant_schema_fields.sql",
    "027_superadmin_vitor.sql",
    "034_add_quality_module_to_tenants.sql",
}


def test_o_conjunto_de_ofensores_nao_cresceu():
    achados = {
        f.name
        for f in _MIGRACOES.glob("*.sql")
        if runner_core.destructive_reason(f.read_text(encoding="utf-8"))
    }
    assert achados == _OFENSORES_CONHECIDOS, (
        "mudou o conjunto de migrations que apagam dado/reescrevem credencial. "
        f"novas={sorted(achados - _OFENSORES_CONHECIDOS)} "
        f"sumiram={sorted(_OFENSORES_CONHECIDOS - achados)}"
    )


def test_baseline_de_ci_bate_com_os_ofensores():
    """O arquivo que o CI lê e o que o detector acha não podem divergir."""
    baseline = {
        linha.strip()
        for linha in (_MIGRACOES / ".destructive-baseline").read_text().splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    }
    assert baseline == _OFENSORES_CONHECIDOS


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE public.counting_sessions CASCADE;",
        "drop table if exists public.session_events;",
        "DELETE FROM public.alerts WHERE tenant_id = '...';",
        "TRUNCATE public.frames;",
        "ALTER TABLE users DROP COLUMN telefone;",
        "DROP SCHEMA rvb CASCADE;",
        "UPDATE users SET password_hash = '$2b$12$x' WHERE email = 'a@b.c';",
        "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash",
        # Terceira cara (#743): reescreve a escolha de módulos do admin.
        "UPDATE tenants SET modules_enabled = modules_enabled || '[\"quality\"]'::jsonb;",
        "ON CONFLICT (slug) DO UPDATE SET modules_enabled = EXCLUDED.modules_enabled",
        "update public.tenants set modules_enabled='[\"epi\"]'::jsonb where slug='rvb';",
    ],
)
def test_pega_o_que_e_irreversivel(sql):
    assert runner_core.destructive_reason(sql) is not None


@pytest.mark.parametrize(
    "sql",
    [
        # Definição de coluna não é atribuição — o "=" é o que distingue.
        "CREATE TABLE users (id UUID PRIMARY KEY, password_hash VARCHAR(255));",
        "CREATE TABLE IF NOT EXISTS public.frames (id BIGSERIAL PRIMARY KEY);",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS fps INTEGER DEFAULT 5;",
        "CREATE INDEX IF NOT EXISTS idx_x ON public.frames (tenant_id);",
        "DROP INDEX IF EXISTS idx_velho;",  # índice não é linha de cliente
        "ALTER TABLE users DROP CONSTRAINT users_role_check;",
        "UPDATE yolo_classes SET is_violation = NULL WHERE is_violation = FALSE;",
        # #743: definir/listar a coluna não é reescrever a escolha — é o "=" que
        # distingue, igual à regra de password_hash. A 137 é exatamente isto e
        # PRECISA rodar em banco estabelecido.
        "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS modules_enabled JSONB "
        "DEFAULT '[\"epi\",\"counting\",\"basic\"]';",
        "INSERT INTO tenants (slug, modules_enabled) VALUES ('x', '[]'::jsonb) "
        "ON CONFLICT (slug) DO NOTHING;",
        "SELECT modules_enabled FROM tenants WHERE is_active = true;",
    ],
)
def test_nao_pega_ddl_idempotente_nem_backfill(sql):
    assert runner_core.destructive_reason(sql) is None


def test_comentario_nao_dispara_a_guarda():
    """As migrations 104 e 108 PROMETEM no cabeçalho não usar DELETE/TRUNCATE.

    Sem tirar comentário, a guarda pularia justo as duas que seguem a regra —
    e a 104 redefine create_tenant_schema, então pulá-la quebraria tenant novo.
    """
    for nome in ("104_inspection_sessions.sql", "108_tenant_context_audit.sql"):
        arquivo = _MIGRACOES / nome
        assert "TRUNCATE" in arquivo.read_text(encoding="utf-8"), (
            f"{nome} não menciona mais TRUNCATE — este teste perdeu o alvo"
        )
        assert runner_core.destructive_reason(arquivo.read_text(encoding="utf-8")) is None


def test_guarda_e_inerte_em_banco_virgem():
    """Instalação do zero PRECISA rodar a 049 — senão counting_sessions nasce
    com o schema errado da 015."""
    sql = (_MIGRACOES / "049_counting_deepsort_rebuild.sql").read_text(encoding="utf-8")
    import logging

    log = logging.getLogger("teste")
    assert runner_core._guarda_pula("049_counting_deepsort_rebuild.sql", sql, False, log) is False
    assert runner_core._guarda_pula("049_counting_deepsort_rebuild.sql", sql, True, log) is True


def test_isencao_da_013_esta_documentada():
    assert "013_consolidate_cameras.sql" in runner_core.GUARDA_ISENTAS
    assert runner_core.GUARDA_ISENTAS["013_consolidate_cameras.sql"].strip()


# ---------------------------------------------------------------------------
# #743 — a terceira cara da família: "reescreve configuração"
# ---------------------------------------------------------------------------


def test_a_familia_que_reescreve_config_esta_toda_pega():
    """023, 027 e 034 escrevem por cima de `modules_enabled` — a MESMA coluna que
    a tela do admin edita (app/api/v1/admin/routes.py: "UPDATE tenants SET
    modules_enabled = %s::jsonb WHERE id = %s"). Em banco estabelecido, nenhuma
    delas pode rodar: o deploy devolveria a escolha que o admin desfez."""
    import logging

    log = logging.getLogger("teste")
    for nome in sorted(_FAMILIA_REESCREVE_CONFIG):
        sql = (_MIGRACOES / nome).read_text(encoding="utf-8")
        assert runner_core.destructive_reason(sql) is not None, nome
        assert runner_core._guarda_pula(nome, sql, True, log) is True, nome
        # Instalação virgem PRECISA delas: é lá que os módulos nascem.
        assert runner_core._guarda_pula(nome, sql, False, log) is False, nome


def test_137_repoe_o_schema_que_a_023_pulada_deixaria_de_fora():
    """A 023 carrega DDL junto do UPDATE, e a guarda pula por ARQUIVO. A 137
    existe para que pular a 023 nunca signifique banco sem as colunas."""
    sql = (_MIGRACOES / "137_config_de_modulos_decidida_sobrevive.sql").read_text(
        encoding="utf-8"
    )
    assert runner_core.destructive_reason(sql) is None, (
        "a 137 não pode ser pulada pela guarda — ela é a que repõe o schema"
    )
    for coluna in ("schema_name", "plan", "modules_enabled"):
        assert f"ADD COLUMN IF NOT EXISTS {coluna}" in sql, coluna
    corpo = runner_core.strip_sql_comments(sql)
    for proibido in ("DROP ", "DELETE FROM", "TRUNCATE", "modules_enabled ="):
        assert proibido not in corpo, f"a 137 não pode conter {proibido!r}"


def test_uma_quarta_migration_desta_familia_reprova_no_ci(tmp_path):
    """O guard-rail de CI tem que ficar VERMELHO se alguém escrever a próxima.

    Roda o check de verdade (scripts/ci/check_migrations_hygiene.py) contra um
    diretório de migrations sintético, com a baseline histórica vazia: o arquivo
    novo é a única coisa que ele pode acusar.
    """
    import importlib.util

    raiz = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "check_migrations_hygiene", raiz / "scripts" / "ci" / "check_migrations_hygiene.py"
    )
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)

    inocente = tmp_path / "200_coluna_nova.sql"
    inocente.write_text(
        "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS apelido VARCHAR(50);\n",
        encoding="utf-8",
    )
    check.REPO_ROOT = tmp_path  # só para a mensagem de erro (relative_to)
    check.MIGRATIONS_DIR = tmp_path
    check.DESTRUCTIVE_BASELINE_FILE = tmp_path / ".destructive-baseline"
    assert check.check_no_new_destructive_migration() == [], (
        "migration inocente não pode reprovar — falso positivo aqui trava PR legítimo"
    )

    quarta = tmp_path / "201_religa_qualidade_de_novo.sql"
    quarta.write_text(
        "UPDATE public.tenants\n"
        "   SET modules_enabled = modules_enabled || '[\"quality\"]'::jsonb\n"
        " WHERE NOT (modules_enabled @> '[\"quality\"]'::jsonb);\n",
        encoding="utf-8",
    )
    erros = check.check_no_new_destructive_migration()
    assert len(erros) == 1 and "201_religa_qualidade_de_novo.sql" in erros[0], erros
    assert "modules_enabled" in erros[0]
