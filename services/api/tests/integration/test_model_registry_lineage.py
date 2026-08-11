"""Integração: ModelRegistryRepository.get_training_lineage contra Postgres real.

Responde a pergunta operacional "este modelo foi treinado em quê, anotado
por quem e quando" — modelo → dataset_version → frames → anotações
(created_by/reviewed_by/source). Ver docstring do método para a aproximação
documentada (sem tabela de junção persistindo os frames exatos de um
snapshot — reconstrução por tenant_id+module_code+is_annotated+created_at
<= dataset_version.created_at).

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.model_registry_repository import (
    ModelRegistryRepository,
)


@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"lineage-{uid[:8]}@test.dev", "x", "IntTest Lineage", "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.trained_models WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.dataset_versions WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def reviewer_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"reviewer-{uid[:8]}@test.dev", "x", "IntTest Reviewer", "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        # Ordem de teardown do pytest é LIFO por fixture — reviewer_id é
        # resolvido DEPOIS de user_id (assinatura de frames_and_annotations),
        # logo desmonta ANTES: training_frames (cujo cascade libera
        # frame_annotations.reviewed_by) precisa ser limpo aqui também, não
        # só no teardown de user_id — senão o DELETE deste usuário esbarra
        # na FK frame_annotations_reviewed_by_fkey (idempotente: repetir no
        # teardown de user_id é no-op).
        cur.execute("DELETE FROM public.trained_models WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.dataset_versions WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def dataset_version_id(pg_raw, tenant_id: str, user_id: str) -> str:  # type: ignore[return]
    dv_id = str(uuid4())
    build_time = datetime.now(timezone.utc)
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.dataset_versions "
            "(id, user_id, version, tenant_id, module_code, status, created_at) "
            "VALUES (%s, %s, 'v1', %s, 'epi', 'ready', %s)",
            (dv_id, user_id, tenant_id, build_time),
        )
    return dv_id


@pytest.fixture
def frames_and_annotations(
    pg_raw, tenant_id: str, user_id: str, reviewer_id: str, dataset_version_id: str
) -> dict[str, str]:
    """2 frames: um ANTES do build (entra na linhagem) com 1 anotação
    (created_by=user_id, reviewed_by=reviewer_id, source='pre_annotation'),
    outro DEPOIS do build (não deveria entrar — aproximação por corte
    temporal)."""
    with pg_raw.cursor() as cur:
        cur.execute(
            "SELECT created_at FROM public.dataset_versions WHERE id = %s",
            (dataset_version_id,),
        )
        build_time = cur.fetchone()["created_at"]

    before_frame = str(uuid4())
    after_frame = str(uuid4())
    before_time = build_time - timedelta(hours=1)
    after_time = build_time + timedelta(hours=1)

    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, created_at) "
            "VALUES (%s, 1, %s, %s, 'epi', TRUE, 'nvr', %s)",
            (before_frame, "frames/lineage/before.jpg", tenant_id, before_time),
        )
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, created_at) "
            "VALUES (%s, 2, %s, %s, 'epi', TRUE, 'nvr', %s)",
            (after_frame, "frames/lineage/after.jpg", tenant_id, after_time),
        )
        cur.execute(
            "INSERT INTO public.frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, class_name, "
            " source, created_by, reviewed_by) "
            "VALUES (%s, 1, 0.5, 0.5, 0.2, 0.2, %s, 'pre_annotation', %s, %s)",
            (before_frame, "Capacete", user_id, reviewer_id),
        )
    return {"before": before_frame, "after": after_frame}


@pytest.fixture
def model_id(
    pg_raw, tenant_id: str, user_id: str, dataset_version_id: str
) -> str:  # type: ignore[return]
    mid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.trained_models "
            "(id, user_id, name, model_path, tenant_id, module_code, dataset_version_id) "
            "VALUES (%s, %s, 'lineage-test-model', 'models/t/v1.onnx', %s, 'epi', %s)",
            (mid, user_id, tenant_id, dataset_version_id),
        )
    return mid


@pytest.fixture
def repo(pg_pool) -> ModelRegistryRepository:
    return ModelRegistryRepository(pg_pool)


class TestGetTrainingLineage:

    def test_full_chain_model_to_annotations(
        self,
        repo: ModelRegistryRepository,
        tenant_id: str,
        model_id: str,
        dataset_version_id: str,
        frames_and_annotations: dict[str, str],
        user_id: str,
        reviewer_id: str,
    ) -> None:
        lineage = repo.get_training_lineage(model_id, tenant_id)

        assert lineage is not None
        assert str(lineage["model"]["id"]) == model_id
        assert str(lineage["dataset_version"]["id"]) == dataset_version_id

        frame_ids = {str(r["frame_id"]) for r in lineage["frames"]}
        assert frames_and_annotations["before"] in frame_ids
        # frame criado DEPOIS do build não entra (corte temporal)
        assert frames_and_annotations["after"] not in frame_ids

        before_rows = [
            r for r in lineage["frames"]
            if str(r["frame_id"]) == frames_and_annotations["before"]
        ]
        assert len(before_rows) == 1
        row = before_rows[0]
        assert row["class_name"] == "Capacete"
        assert row["annotation_source"] == "pre_annotation"
        assert str(row["created_by"]) == user_id
        assert str(row["reviewed_by"]) == reviewer_id
        assert row["created_by_email"] is not None
        assert row["reviewed_by_email"] is not None

    def test_cross_tenant_returns_none(
        self, repo: ModelRegistryRepository, model_id: str
    ) -> None:
        other_tenant = str(uuid4())
        assert repo.get_training_lineage(model_id, other_tenant) is None

    def test_model_without_dataset_version_returns_empty_lineage(
        self, pg_raw, repo: ModelRegistryRepository, tenant_id: str, user_id: str
    ) -> None:
        mid = str(uuid4())
        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.trained_models "
                "(id, user_id, name, model_path, tenant_id, module_code) "
                "VALUES (%s, %s, 'no-dataset-model', 'models/t/v2.onnx', %s, 'epi')",
                (mid, user_id, tenant_id),
            )
        lineage = repo.get_training_lineage(mid, tenant_id)
        assert lineage == {"model": lineage["model"], "dataset_version": None, "frames": []}
        assert str(lineage["model"]["id"]) == mid

    def test_unknown_model_returns_none(
        self, repo: ModelRegistryRepository, tenant_id: str
    ) -> None:
        assert repo.get_training_lineage(str(uuid4()), tenant_id) is None
