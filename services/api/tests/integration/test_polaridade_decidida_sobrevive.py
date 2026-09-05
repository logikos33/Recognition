"""A polaridade decidida por gente sobrevive ao boot seguinte (migration 136).

POR QUE ESTE TESTE EXISTE. Em modo LEGADO — `MIGRATIONS_LEDGER_CUTOVER`
ausente, que é o da produção hoje — `runner_core.run_legacy` reexecuta TODO
`infra/migrations/*.sql` a cada boot da API. A 125 e a 127 escrevem
`yolo_classes.is_violation` sem perguntar se alguém já decidiu, então a
calibração da RVB (ADR-0067: "Sem protetor de ouvido" e "Uso incorreto de
mascara" saem do gatilho) era desfeita no deploy seguinte — e pelo pior lado:
o primeiro UPDATE da 125 casa o prefixo "Sem "/"Uso incorreto" e devolve as
duas para TRUE, ou seja, voltam a ACUSAR quem cumpre.

O QUE ELE RODA. Não é leitura de texto de SQL: aplica os arquivos .sql de
verdade, na ordem do boot, contra um Postgres de verdade — e DUAS vezes, que é
o que a produção faz a cada deploy. Tudo dentro de uma transação que sofre
rollback no fim: o teste não deixa linha nem apaga nada.

Como o filtro é "migration que menciona yolo_classes e is_violation", qualquer
migration FUTURA que volte a mexer em polaridade entra aqui sozinha — e quebra
este teste se reescrever decisão humana.
"""

from __future__ import annotations

import glob
import os
import uuid
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import pytest

_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_MIGRACOES = os.path.join(_RAIZ, "infra", "migrations")


def _migracoes_de_polaridade() -> list[str]:
    """Migrations que escrevem polaridade de classe do tenant, em ordem de boot."""
    achadas = []
    for caminho in sorted(glob.glob(os.path.join(_MIGRACOES, "*.sql"))):
        texto = open(caminho, encoding="utf-8").read()
        if "yolo_classes" in texto and "is_violation" in texto:
            achadas.append(caminho)
    return achadas


def _uma_passada_de_boot(cur) -> None:
    for caminho in _migracoes_de_polaridade():
        cur.execute(open(caminho, encoding="utf-8").read())


@pytest.fixture
def conn(integration_dsn: str):
    """Conexão em transação — rollback no fim. Zero resíduo, zero DELETE."""
    c = psycopg2.connect(integration_dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _semeia_classe(cur, nome: str, is_violation, decidido_por_gente: bool) -> int:
    """Cria tenant + usuário + classe do tenant. Devolve o id da classe."""
    sufixo = uuid.uuid4().hex[:8]
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
        (tenant_id, f"T136 {sufixo}", f"t136-{sufixo}"),
    )
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name)"
        " VALUES (%s, %s, %s, %s)",
        (user_id, f"t136-{sufixo}@teste.local", "x", f"T136 {sufixo}"),
    )
    cur.execute(
        "INSERT INTO public.yolo_classes (user_id, name, tenant_id, module_code, is_violation)"
        " VALUES (%s, %s, %s, 'epi', %s) RETURNING id",
        (user_id, f"{nome} {sufixo}", tenant_id, is_violation),
    )
    class_id = cur.fetchone()["id"]
    if decidido_por_gente:
        # A marca que as portas vivas gravam (AnnotationRepository.create_class /
        # patch_class) e que o script de calibração grava.
        cur.execute(
            "UPDATE public.yolo_classes"
            "   SET violation_decision = %s, violation_decided_at = NOW()"
            " WHERE id = %s",
            (is_violation, class_id),
        )
    return class_id


def _polaridade(cur, class_id: int):
    cur.execute("SELECT is_violation FROM public.yolo_classes WHERE id = %s", (class_id,))
    return cur.fetchone()["is_violation"]


def test_marca_de_decisao_humana_existe(conn) -> None:
    """A 136 cria as duas colunas da marca — sem elas nada mais aqui é possível."""
    with conn.cursor() as cur:
        _uma_passada_de_boot(cur)
        cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'public' AND table_name = 'yolo_classes'"
            "   AND column_name IN ('violation_decision', 'violation_decided_at')"
        )
        colunas = {r["column_name"] for r in cur.fetchall()}
    assert colunas == {"violation_decision", "violation_decided_at"}, (
        "sem a marca de decisão humana em yolo_classes não há como distinguir "
        f"'ninguém decidiu' de 'decidiram que é indecisa' — achei {colunas}"
    )


def test_calibracao_rvb_nao_volta_a_acusar(conn) -> None:
    """O caso da RVB: classe rebaixada para INDECISA continua indecisa.

    Sem a 136, o primeiro UPDATE da 125 casa 'Sem %' e devolve TRUE — a classe
    de 27,3% de precisão volta a acusar quem cumpre no deploy seguinte.
    """
    with conn.cursor() as cur:
        _uma_passada_de_boot(cur)  # garante as colunas da marca
        class_id = _semeia_classe(cur, "Sem protetor de ouvido", None, decidido_por_gente=True)

        _uma_passada_de_boot(cur)
        depois_do_boot_1 = _polaridade(cur, class_id)
        _uma_passada_de_boot(cur)
        depois_do_boot_2 = _polaridade(cur, class_id)

    assert depois_do_boot_1 is None, (
        "a calibração não sobreviveu ao 1º boot: 'Sem protetor de ouvido' saiu "
        f"de INDECISA para is_violation={depois_do_boot_1!r} "
        "(True = voltou a acusar quem cumpre)"
    )
    assert depois_do_boot_2 is None, (
        f"a calibração não sobreviveu ao 2º boot (is_violation={depois_do_boot_2!r}) "
        "— o efeito não é idempotente"
    )


def test_conformidade_decidida_pela_tela_nao_vira_indecisa(conn) -> None:
    """O caso que a 127 apaga: classe nova marcada como CONFORMIDADE pelo dono.

    `PATCH /classes/<id>` grava is_violation (whitelist do repository), e a 127
    faz FALSE -> NULL para toda classe criada a partir de 2026-08-25.
    """
    with conn.cursor() as cur:
        _uma_passada_de_boot(cur)
        class_id = _semeia_classe(cur, "Protetor auditivo", False, decidido_por_gente=True)

        _uma_passada_de_boot(cur)
        depois_do_boot_1 = _polaridade(cur, class_id)
        _uma_passada_de_boot(cur)
        depois_do_boot_2 = _polaridade(cur, class_id)

    assert depois_do_boot_1 is False, (
        "a decisão de CONFORMIDADE não sobreviveu ao 1º boot: virou "
        f"is_violation={depois_do_boot_1!r}"
    )
    assert depois_do_boot_2 is False, (
        f"a decisão de CONFORMIDADE não sobreviveu ao 2º boot ({depois_do_boot_2!r})"
    )


def test_sem_marca_o_padrao_das_migrations_continua_valendo(conn) -> None:
    """A 136 não inventa decisão: linha sem marca segue o padrão da 125.

    Isto é o outro lado da condição — "só aplica o padrão onde ninguém decidiu".
    Uma classe 'Sem ...' que ninguém julgou continua nascendo como violação.
    """
    with conn.cursor() as cur:
        _uma_passada_de_boot(cur)
        class_id = _semeia_classe(cur, "Sem capacete", None, decidido_por_gente=False)

        _uma_passada_de_boot(cur)
        depois = _polaridade(cur, class_id)

    assert depois is True, (
        "classe sem decisão humana deveria continuar recebendo o padrão da 125 "
        f"(prefixo 'Sem ' = violação), mas virou {depois!r}"
    )


class _PoolDeUmaTransacao:
    """DatabasePool de mentira: entrega sempre a MESMA conexão, em transação
    aberta, e nunca commita (quem commita de verdade é o `get_connection` do
    pool real). Assim o teste exercita o SQL REAL do repository e o rollback do
    fixture apaga tudo — sem DELETE, sem resíduo no banco de integração."""

    def __init__(self, conn) -> None:
        self._conn = conn

    @contextmanager
    def get_connection(self):
        yield self._conn


def test_porta_viva_marca_a_decisao_e_ela_sobrevive(conn) -> None:
    """O caminho do produto: Estúdio cria a classe, dono corrige pelo PATCH.

    Exercita `AnnotationRepository.create_class` e `patch_class` de verdade —
    é onde a marca precisa nascer, senão a decisão de quem usa o sistema é
    desfeita pelo próximo deploy e ninguém fica sabendo.
    """
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )

    with conn.cursor() as cur:
        _uma_passada_de_boot(cur)
        sufixo = uuid.uuid4().hex[:8]
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tenant_id, f"T136 {sufixo}", f"t136-porta-{sufixo}"),
        )
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name)"
            " VALUES (%s, %s, %s, %s)",
            (user_id, f"t136-porta-{sufixo}@teste.local", "x", f"T136 {sufixo}"),
        )

        repo = AnnotationRepository(_PoolDeUmaTransacao(conn))  # type: ignore[arg-type]

        criada = repo.create_class(
            user_id,
            f"Protetor de ouvido {sufixo}",
            tenant_id=tenant_id,
            module_code="epi",
            is_violation=False,
        )
        assert criada is not None
        assert criada["violation_decided_at"] is not None, (
            "create_class não marcou a decisão — a polaridade que o Estúdio "
            "gravou seria desfeita no próximo boot"
        )

        _uma_passada_de_boot(cur)
        assert _polaridade(cur, criada["id"]) is False, (
            "a polaridade gravada na criação não sobreviveu ao boot"
        )

        # O dono muda de ideia pela tela (PATCH /classes/<id>).
        repo.patch_class(criada["id"], tenant_id, {"is_violation": True})
        _uma_passada_de_boot(cur)
        depois = _polaridade(cur, criada["id"])

    assert depois is True, (
        f"a correção feita pelo PATCH não sobreviveu ao boot: virou {depois!r}"
    )
