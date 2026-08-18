"""`update_job_status(metrics=...)` FUNDE — não substitui (5º "dois escritores").

O apagamento era real e silencioso: o worker gravava `provenance` + `gpu_cost` no
job, o callback de progresso do pod gravava `stage`, e quem escrevesse por último
apagava o do outro. Nenhum erro, nenhum log — a proveniência simplesmente sumia.

Postgres de verdade, de propósito: o que está sob teste é a semântica do operador
`||` do jsonb. Um mock de cursor confirmaria a string do SQL e não o comportamento.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)

@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"trainmetrics-{uid[:8]}@test.dev", "x", "IntTest Training",
             "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.training_jobs WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


def _job(repo: TrainingRepository, user_id: str) -> UUID:
    return UUID(str(repo.create_job(UUID(user_id), total_epochs=12)["id"]))


def test_callback_de_stage_nao_apaga_a_proveniencia(pg_pool, user_id: str) -> None:
    """A sequência exata que apagava: worker grava proveniência, pod grava stage."""
    repo = TrainingRepository(pg_pool)
    job_id = _job(repo, user_id)

    repo.update_job_status(
        job_id, "running",
        metrics={"provenance": {"worker_commit": "abc123", "runner_sha256": "def456"}},
    )
    depois = repo.update_job_status(job_id, "running", metrics={"stage": "training"})

    assert depois is not None
    m = depois["metrics"]
    assert m["stage"] == "training"
    assert m["provenance"] == {"worker_commit": "abc123", "runner_sha256": "def456"}


def test_custo_e_proveniencia_convivem_no_fechamento(pg_pool, user_id: str) -> None:
    """Três escritores, três chaves de topo — o job fecha com as três."""
    repo = TrainingRepository(pg_pool)
    job_id = _job(repo, user_id)

    repo.update_job_status(job_id, "running", metrics={"provenance": {"worker_commit": "abc"}})
    repo.update_job_status(job_id, "running", metrics={"stage": "exporting"})
    final = repo.update_job_status(
        job_id, "completed", metrics={"gpu_cost": {"actual_usd": 0.11}}
    )

    assert final is not None
    assert set(final["metrics"]) == {"provenance", "stage", "gpu_cost"}
    assert final["metrics"]["provenance"]["worker_commit"] == "abc"


def test_mesma_chave_de_topo_e_substituida(pg_pool, user_id: str) -> None:
    """`||` é merge RASO — documenta o limite, para ninguém contar com merge fundo.

    Se um dia dois escritores disputarem o MESMO objeto aninhado, o de baixo se
    perde e a correção é `jsonb_set` por chave, não este operador.
    """
    repo = TrainingRepository(pg_pool)
    job_id = _job(repo, user_id)

    repo.update_job_status(job_id, "running", metrics={"gpu_cost": {"price_usd_h": 0.22}})
    depois = repo.update_job_status(
        job_id, "completed", metrics={"gpu_cost": {"actual_usd": 0.11}}
    )

    assert depois is not None
    assert depois["metrics"]["gpu_cost"] == {"actual_usd": 0.11}
    assert "price_usd_h" not in depois["metrics"]["gpu_cost"]
