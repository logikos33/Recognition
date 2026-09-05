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


# Os cinco arquivos que existiam quando a guarda foi escrita. Congelado de
# propósito: migration NOVA nesta lista significa que alguém escreveu um
# DROP/DELETE/TRUNCATE novo — proibido pelo CLAUDE.md e, pior, ele NÃO rodaria
# em produção (a guarda o pula). O check de CI
# (scripts/ci/check_migrations_hygiene.py) dá o mesmo sinal, sem banco.
_OFENSORES_CONHECIDOS = {
    "013_consolidate_cameras.sql",
    "027_superadmin_vitor.sql",
    "040_reset_superadmin_password.sql",
    "046_deactivate_default_tenant.sql",
    "049_counting_deepsort_rebuild.sql",
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
