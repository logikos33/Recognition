"""
Integração: união catálogo (module_classes) ∪ tenant (yolo_classes) na
leitura do anotador + validação/persistência de anotação com classe custom.

Reproduz o bug relatado: uma classe nova criada pelo tenant (POST /classes →
TenantClassService.create_class → yolo_classes) "não salva"/some no anotador.
Causa raiz: o anotador lê classes de GET /modules/<code>/classes
(ModuleService.get_classes → só module_classes, catálogo GLOBAL) — a classe
do tenant nunca entrava nessa lista. E mesmo que entrasse, o save era
rejeitado: AnnotationService._validate_class só validava class_id contra
module_classes.

Falha-antes/passa-depois: ANTES desta correção, ModuleService.get_classes(
tenant_id=...) não existia (só listava o catálogo global) e
AnnotationService.save_annotations rejeitava qualquer class_id fora de
module_classes com "class_id X não existe no módulo" — mesmo para uma classe
que o próprio tenant acabara de criar. DEPOIS, a classe aparece na união com
`source='tenant'` e um id namespaced (class_namespace.py) que nunca colide
com o índice 0-based do catálogo, e o save aceita esse id.

Cross-tenant (C-01): uma classe custom de um tenant nunca aparece nem valida
sob o contexto de OUTRO tenant — o namespacing desambigua o espaço de id,
mas o isolamento por tenant_id continua sendo a query real.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.domain.services.annotation_service import AnnotationService
from app.domain.services.class_namespace import namespace_tenant_class_id
from app.domain.services.module_service import ModuleService
from app.domain.services.tenant_class_service import TenantClassService
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository

_STORAGE_PATH = "app.infrastructure.storage.local_storage.get_storage"


@pytest.fixture
def other_tenant_id(pg_raw):  # type: ignore[return]
    """Segundo tenant efêmero — usado nos testes de isolamento cross-tenant."""
    tid = str(uuid4())
    slug = f"inttest-other-{tid[:8]}"
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid, f"IntTest Other {slug}", slug),
        )
    yield tid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid,))


def _make_user(pg_raw, tenant_id: str, tag: str) -> str:
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"clsunion-{tag}-{uid[:8]}@test.dev", "x",
             f"IntTest ClassUnion {tag}", "operator", tenant_id),
        )
    return uid


def _cleanup_user(pg_raw, uid: str) -> None:
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
        cur.execute("DELETE FROM public.yolo_classes WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


def _make_frame(pg_raw, user_id: str, tag: str) -> str:
    vid = str(uuid4())
    fid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_videos (id, user_id, filename) VALUES (%s, %s, %s)",
            (vid, user_id, f"inttest-clsunion-{tag}.mp4"),
        )
        cur.execute(
            "INSERT INTO public.training_frames (id, video_id, frame_number, filename) "
            "VALUES (%s, %s, %s, %s)",
            (fid, vid, 1, f"frames/{tag}/v/frame_0001.jpg"),
        )
    return fid


@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    uid = _make_user(pg_raw, tenant_id, "a")
    yield uid
    _cleanup_user(pg_raw, uid)


@pytest.fixture
def user_id_b(pg_raw, other_tenant_id: str) -> str:  # type: ignore[return]
    uid = _make_user(pg_raw, other_tenant_id, "b")
    yield uid
    _cleanup_user(pg_raw, uid)


@pytest.fixture
def frame_id(pg_raw, user_id: str) -> str:  # type: ignore[return]
    yield _make_frame(pg_raw, user_id, "a")


@pytest.fixture
def frame_id_b(pg_raw, user_id_b: str) -> str:  # type: ignore[return]
    yield _make_frame(pg_raw, user_id_b, "b")


@pytest.fixture
def tenant_class_service(pg_pool) -> TenantClassService:
    return TenantClassService(AnnotationRepository(pg_pool))


@pytest.fixture
def module_service_instance() -> ModuleService:
    return ModuleService()


@pytest.fixture
def annotation_service(pg_pool) -> AnnotationService:
    return AnnotationService(
        AnnotationRepository(pg_pool), FrameRepository(pg_pool), ModuleRepository(pg_pool)
    )


class TestClassUnionWriteThenRead:
    """Escreve sob o contexto de um tenant, lê de volta pelo endpoint que o
    anotador usa, e valida/persiste uma anotação — tudo sob o mesmo
    get_tenant_id() do contexto assumido (nunca o tenant "de casa" do
    usuário, mesmo achado dos #302/#313)."""

    def test_tenant_class_appears_in_annotator_union(
        self, tenant_class_service, module_service_instance, tenant_id, user_id
    ) -> None:
        created = tenant_class_service.create_class(
            user_id=user_id, tenant_id=tenant_id, name="Protetor Auricular",
            is_violation=False,
        )
        classes = module_service_instance.get_classes("epi", tenant_id=tenant_id)

        namespaced = namespace_tenant_class_id(created["id"])
        tenant_matches = [c for c in classes if c.get("class_id") == namespaced]
        assert len(tenant_matches) == 1
        assert tenant_matches[0]["source"] == "tenant"
        assert tenant_matches[0]["class_name"] == "Protetor Auricular"

        # Catálogo global (EPI: class_id 0-7) continua presente na união.
        module_ids = {c["class_id"] for c in classes if c["source"] == "module"}
        assert module_ids == set(range(8))

    def test_tenant_class_validates_and_saves_annotation(
        self, tenant_class_service, annotation_service, tenant_id, user_id, frame_id
    ) -> None:
        created = tenant_class_service.create_class(
            user_id=user_id, tenant_id=tenant_id, name="Protetor Auditivo",
            is_violation=False,
        )
        class_id = namespace_tenant_class_id(created["id"])
        annotations = [
            {"class_id": class_id, "class_name": "Protetor Auditivo", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with patch(_STORAGE_PATH):
            count = annotation_service.save_annotations(
                frame_id, annotations, user_id, tenant_id=tenant_id
            )
        assert count == 1

        result = annotation_service.get_frame_annotations(frame_id, user_id, tenant_id=tenant_id)
        assert len(result) == 1
        assert result[0]["class_id"] == class_id
        assert result[0]["class_name"] == "Protetor Auditivo"
        assert result[0]["module_code"] == "epi"

    def test_cross_tenant_class_not_visible_and_rejected(
        self,
        tenant_class_service,
        module_service_instance,
        annotation_service,
        tenant_id,
        other_tenant_id,
        user_id,
        user_id_b,
        frame_id_b,
    ) -> None:
        """Classe criada no tenant A: some da união do tenant B, e o save do
        tenant B usando o mesmo id namespaced é rejeitado (C-01) — mesmo o
        frame/usuário do B sendo legítimos (isola a checagem de CLASSE da
        checagem de posse de FRAME)."""
        created = tenant_class_service.create_class(
            user_id=user_id, tenant_id=tenant_id, name="Classe Exclusiva Tenant A",
            is_violation=True,
        )
        class_id = namespace_tenant_class_id(created["id"])

        classes_b = module_service_instance.get_classes("epi", tenant_id=other_tenant_id)
        assert all(c.get("class_id") != class_id for c in classes_b)

        annotations = [
            {"class_id": class_id, "class_name": "Classe Exclusiva Tenant A",
             "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with pytest.raises(ValidationError, match="não existe no módulo"):
            annotation_service.save_annotations(
                frame_id_b, annotations, user_id_b, tenant_id=other_tenant_id
            )
