"""Integração: persistência de class_name/module_code em anotações (task-077/079).

Reproduz o bug relatado: rotular uma caixa como "Capacete" (EPI, class_id=0)
e reler devolvia um nome trocado ("empilhadeira"), porque frame_annotations
.class_id era FK para yolo_classes(id) — tabela sem nenhuma relação com o
índice do módulo enviado pelo frontend (module_classes.class_id).

Falha-antes/passa-depois: ANTES desta task (migrations 102/103 ausentes ou
FK ainda presente), o INSERT de class_id=0 para um tenant sem yolo_classes
prévias falha com ForeignKeyViolation — confirmado manualmente durante a
investigação (task-079.md). DEPOIS (migrations aplicadas + class_name/
module_code persistidos), o save funciona e a releitura devolve o nome
correto sem depender de JOIN em yolo_classes.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.annotation_service import AnnotationService
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository

_STORAGE_PATH = "app.infrastructure.storage.local_storage.get_storage"


@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"ann-{uid[:8]}@test.dev", "x", "IntTest Annotator", "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        cur.execute(
            "DELETE FROM public.frame_annotations WHERE frame_id IN "
            "(SELECT tf.id FROM public.training_frames tf "
            " JOIN public.training_videos tv ON tv.id = tf.video_id WHERE tv.user_id = %s)",
            (uid,),
        )
        cur.execute(
            "DELETE FROM public.training_frames WHERE video_id IN "
            "(SELECT id FROM public.training_videos WHERE user_id = %s)",
            (uid,),
        )
        cur.execute("DELETE FROM public.training_videos WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def frame_id(pg_raw, user_id: str) -> str:  # type: ignore[return]
    """Vídeo + frame novos, sem nenhuma linha em yolo_classes para este usuário
    (cenário exato do bug: tenant que nunca criou custom class)."""
    vid = str(uuid4())
    fid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_videos (id, user_id, filename) VALUES (%s, %s, %s)",
            (vid, user_id, "inttest.mp4"),
        )
        cur.execute(
            "INSERT INTO public.training_frames (id, video_id, frame_number, filename) "
            "VALUES (%s, %s, %s, %s)",
            (fid, vid, 1, "frames/u/v/frame_0001.jpg"),
        )
    yield fid


@pytest.fixture
def service(pg_pool) -> AnnotationService:
    return AnnotationService(
        AnnotationRepository(pg_pool), FrameRepository(pg_pool), ModuleRepository(pg_pool)
    )


class TestAnnotationClassPersistence:
    """Falha-antes/passa-depois: class_id=0 (Capacete) nunca satisfazia a FK
    legada (yolo_classes.id é SERIAL, nunca tem id=0) — agora persiste e relê
    corretamente, sem depender de nenhuma linha pré-existente em yolo_classes."""

    def test_save_and_reread_helmet_class_id_zero(self, service, frame_id, user_id):
        annotations = [
            {"class_id": 0, "class_name": "Capacete", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with patch(_STORAGE_PATH):
            count = service.save_annotations(frame_id, annotations, user_id)
        assert count == 1

        result = service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["class_id"] == 0
        assert result[0]["class_name"] == "Capacete"
        assert result[0]["module_code"] == "epi"

    def test_multiple_classes_same_module_reread_correct_names(self, service, frame_id, user_id):
        annotations = [
            {"class_id": 0, "class_name": "Capacete", "module_code": "epi",
             "x_center": 0.2, "y_center": 0.2, "width": 0.1, "height": 0.1},
            {"class_id": 3, "class_name": "Sem Colete", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
            {"class_id": 7, "class_name": "Sem Óculos", "module_code": "epi",
             "x_center": 0.8, "y_center": 0.8, "width": 0.1, "height": 0.1},
        ]
        with patch(_STORAGE_PATH):
            count = service.save_annotations(frame_id, annotations, user_id)
        assert count == 3

        result = service.get_frame_annotations(frame_id, user_id)
        by_class_id = {r["class_id"]: r["class_name"] for r in result}
        assert by_class_id == {0: "Capacete", 3: "Sem Colete", 7: "Sem Óculos"}

    def test_empty_class_name_raises_validation_error(self, service, frame_id, user_id):
        annotations = [
            {"class_id": 0, "class_name": "  ", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with pytest.raises(ValidationError, match="class_name"):
            service.save_annotations(frame_id, annotations, user_id)

    def test_unknown_class_id_for_module_raises_validation_error(self, service, frame_id, user_id):
        """class_id=99 não existe em module_classes para 'epi' — 422, sem fallback."""
        annotations = [
            {"class_id": 99, "class_name": "Forklift", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with pytest.raises(ValidationError, match="não existe no módulo"):
            service.save_annotations(frame_id, annotations, user_id)

    def test_unknown_module_raises_validation_error(self, service, frame_id, user_id):
        annotations = [
            {"class_id": 0, "class_name": "X", "module_code": "modulo_inexistente",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with pytest.raises(ValidationError, match="Módulo desconhecido"):
            service.save_annotations(frame_id, annotations, user_id)

    def test_cross_tenant_frame_access_raises_not_found(self, service, frame_id):
        """Usuário de outro tenant não pode ler nem salvar anotações do frame."""
        other_user_id = str(uuid4())
        with pytest.raises(NotFoundError):
            service.save_annotations(
                frame_id,
                [{"class_id": 0, "class_name": "Capacete", "module_code": "epi",
                  "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}],
                other_user_id,
            )
        with pytest.raises(NotFoundError):
            service.get_frame_annotations(frame_id, other_user_id)

    def test_export_yolo_index_matches_module_classes_class_id(self, service, frame_id, user_id):
        """O .txt exportado usa o mesmo índice de module_classes.class_id —
        é o índice usado para treinar o modelo, não precisa de tradução."""
        annotations = [
            {"class_id": 5, "class_name": "Sem Luvas", "module_code": "epi",
             "x_center": 0.4, "y_center": 0.6, "width": 0.15, "height": 0.25},
        ]
        mock_storage = MagicMock()
        with patch(_STORAGE_PATH, return_value=mock_storage):
            service.save_annotations(frame_id, annotations, user_id)

        mock_storage.upload_bytes.assert_called_once()
        label_content = mock_storage.upload_bytes.call_args[0][1].decode("utf-8")
        assert label_content == "5 0.400000 0.600000 0.150000 0.250000"
