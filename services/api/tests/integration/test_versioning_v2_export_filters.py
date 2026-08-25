"""Integração: filtros do export de dataset (versioning_v2.py) contra Postgres real.

Reproduz, com dados semeados, o cenário achado no DEV para o tenant RVB:
5 anotações de classe custom do tenant (class_id namespaced, migration 093 +
class_namespace.TENANT_CLASS_ID_OFFSET=100000), uma delas em classe
arquivada ("incluir blur", archived_at setado). O JOIN original
(`yolo_classes c ON c.id = a.class_id`, SEM desfazer o offset) devolvia
ZERO linhas para qualquer classe custom — confirmado manualmente contra o
Postgres de DEV antes deste fix (nenhuma anotação de classe custom do
tenant RVB entrava em NENHUM dataset export). Este teste prova, contra um
Postgres real (não mock — os testes unitários de versioning_v2.py mockam
annotation_repo._execute e não exercitam o SQL de verdade):

  1. falha-antes: `c.id = a.class_id` sem CASE de offset → 0 linhas para
     class_id >= 100000 (comportamento documentado no commit, não repetido
     aqui como asserção — reproduzido manualmente durante a investigação).
  2. passa-depois: `c.id = CASE WHEN a.class_id >= 100000 THEN
     a.class_id - 100000 ELSE a.class_id END` resolve a classe corretamente
     E o filtro `archived_at IS NULL` exclui a anotação arquivada.

Cobre também o filtro de curation_status='excluida' no pool de frames
(_snapshot_labeled_frames) — frame descartado na curadoria nunca entra no
export; 'duvida' continua entrando (sem teste negativo aqui — comportamento
é "não excluir", já é o caminho padrão sem filtro extra).

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.queue.tasks.versioning_v2 import (
    _fetch_annotations,
    _snapshot_labeled_frames,
)

_TENANT_CLASS_ID_OFFSET = 100_000


@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"vfilters-{uid[:8]}@test.dev", "x", "IntTest Filters", "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        # training_frames -> frame_annotations é ON DELETE CASCADE (schema);
        # yolo_classes -> users também é ON DELETE CASCADE.
        cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def classes(pg_raw, tenant_id: str, user_id: str) -> dict[str, int]:
    """Duas classes custom do tenant: uma ativa, uma arquivada (migration 110)."""
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.yolo_classes (user_id, name, tenant_id, module_code) "
            "VALUES (%s, %s, %s, 'epi') RETURNING id",
            (user_id, "Protetor auditivo", tenant_id),
        )
        active_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO public.yolo_classes "
            "(user_id, name, tenant_id, module_code, archived_at) "
            "VALUES (%s, %s, %s, 'epi', NOW()) RETURNING id",
            (user_id, "incluir blur", tenant_id),
        )
        archived_id = cur.fetchone()["id"]
    return {"active": active_id, "archived": archived_id}


@pytest.fixture
def frames(pg_raw, tenant_id: str) -> dict[str, str]:
    """Um frame NVR ativo (curation 'active') e um excluído (curation 'excluida')."""
    active_frame = str(uuid4())
    excluded_frame = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, curation_status) "
            "VALUES (%s, 1, %s, %s, 'epi', TRUE, 'nvr', 'active')",
            (active_frame, "frames/vfilters/f1.jpg", tenant_id),
        )
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, curation_status) "
            "VALUES (%s, 2, %s, %s, 'epi', TRUE, 'nvr', 'excluida')",
            (excluded_frame, "frames/vfilters/f2.jpg", tenant_id),
        )
    return {"active": active_frame, "excluded": excluded_frame}


@pytest.fixture
def seeded_annotations(pg_raw, frames: dict[str, str], classes: dict[str, int]) -> None:
    """3 anotações: válida, classe arquivada, frame excluído da curadoria."""
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, class_name) "
            "VALUES (%s, %s, 0.5, 0.5, 0.2, 0.2, %s)",
            (frames["active"], _TENANT_CLASS_ID_OFFSET + classes["active"], "Protetor auditivo"),
        )
        cur.execute(
            "INSERT INTO public.frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, class_name) "
            "VALUES (%s, %s, 0.3, 0.3, 0.1, 0.1, %s)",
            (frames["active"], _TENANT_CLASS_ID_OFFSET + classes["archived"], "incluir blur"),
        )
        cur.execute(
            "INSERT INTO public.frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, class_name) "
            "VALUES (%s, %s, 0.5, 0.5, 0.2, 0.2, %s)",
            (
                frames["excluded"],
                _TENANT_CLASS_ID_OFFSET + classes["active"],
                "Protetor auditivo",
            ),
        )


class TestFramePoolCurationFilter:
    """_snapshot_labeled_frames exclui frames curation_status='excluida'."""

    def test_excluded_curation_frame_not_in_pool(
        self, pg_pool, tenant_id: str, frames: dict[str, str], seeded_annotations: None
    ) -> None:
        repo = AnnotationRepository(pg_pool)
        rows = _snapshot_labeled_frames(repo, tenant_id, "epi")
        ids = {str(r["id"]) for r in rows}
        assert frames["active"] in ids
        assert frames["excluded"] not in ids


class TestArchivedClassAnnotationFilter:
    """_fetch_annotations resolve o offset namespaced (100000+yolo_classes.id)
    e exclui anotações de classe arquivada."""

    def test_archived_class_annotation_excluded(
        self,
        pg_pool,
        tenant_id: str,
        classes: dict[str, int],
        frames: dict[str, str],
        seeded_annotations: None,
    ) -> None:
        repo = AnnotationRepository(pg_pool)
        # `_fetch_annotations` devolve (linhas, universo_pre_filtro) desde o gate
        # de procedência: o segundo elemento é o conjunto de frames ANTES do
        # filtro, que `_sem_rotulos_de_frame` usa para decidir quem sai do
        # dataset por ter ficado sem caixa. Estes testes só olham as linhas.
        rows, _universo = _fetch_annotations(repo, tenant_id, "epi")
        class_names = {r["class_name"] for r in rows}
        assert "incluir blur" not in class_names

    def test_valid_custom_class_annotation_resolved_via_offset(
        self,
        pg_pool,
        tenant_id: str,
        classes: dict[str, int],
        frames: dict[str, str],
        seeded_annotations: None,
    ) -> None:
        """Falha-antes/passa-depois: sem o CASE de offset no JOIN, esta
        anotação (class_id=100000+id) nunca era resolvida contra
        yolo_classes — 0 linhas. Com o fix, entra corretamente."""
        repo = AnnotationRepository(pg_pool)
        # `_fetch_annotations` devolve (linhas, universo_pre_filtro) desde o gate
        # de procedência: o segundo elemento é o conjunto de frames ANTES do
        # filtro, que `_sem_rotulos_de_frame` usa para decidir quem sai do
        # dataset por ter ficado sem caixa. Estes testes só olham as linhas.
        rows, _universo = _fetch_annotations(repo, tenant_id, "epi")
        valid = [
            r for r in rows
            if r["class_name"] == "Protetor auditivo" and str(r["frame_id"]) == frames["active"]
        ]
        assert len(valid) == 1
        assert valid[0]["class_id"] == _TENANT_CLASS_ID_OFFSET + classes["active"]

    def test_annotation_on_excluded_curation_frame_not_returned(
        self,
        pg_pool,
        tenant_id: str,
        classes: dict[str, int],
        frames: dict[str, str],
        seeded_annotations: None,
    ) -> None:
        repo = AnnotationRepository(pg_pool)
        # `_fetch_annotations` devolve (linhas, universo_pre_filtro) desde o gate
        # de procedência: o segundo elemento é o conjunto de frames ANTES do
        # filtro, que `_sem_rotulos_de_frame` usa para decidir quem sai do
        # dataset por ter ficado sem caixa. Estes testes só olham as linhas.
        rows, _universo = _fetch_annotations(repo, tenant_id, "epi")
        frame_ids = {str(r["frame_id"]) for r in rows}
        assert frames["excluded"] not in frame_ids
