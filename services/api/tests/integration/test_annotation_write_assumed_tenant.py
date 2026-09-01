"""Integração: escreve-e-lê classe/anotação sob CONTEXTO DE TENANT ASSUMIDO.

Fecha a lacuna deixada por test_model_tag_assumed_tenant.py (PR #314, cobre
só modelo/job de treino) e pelo report estático docs/security/
tenant-context-sweep.md (PR #315): o sweep classificou create_class
(annotation_repository.py:30) como **CORRETO no caminho vivo** (veredito F —
`tenant_class_service` já recebe `get_tenant_id()` do handler) e a posse de
frame/anotação (AnnotationService.save_annotations/get_frame_annotations via
FrameRepository.get_by_id_and_user) como corrigida por #313. Nenhum dos dois
tinha teste de integração write-then-read sob contexto assumido — só
inspeção estática + testes de frame puro (test_frame_ownership_assumed_
tenant.py, que não grava classe nem anotação).

Por que escreve-e-lê, não só "não dá 404": o pior caso deste bug NÃO
levanta exceção — grava com um tenant e lê com outro (mis-tag silencioso).
Só round-trip pega isso; um teste que só chama get_for_tenant/get_by_id_and_
user com um tenant fixo não prova que a ESCRITA sob contexto assumido usou o
tenant certo.

Como funciona o contexto assumido (mesmo mecanismo do sweep e do #313/#314):
superadmin com tenant de casa A assume tenant B via
POST /tenants/<B>/assume → JWT novo com identity=user(A) (get_current_user_
id()=A), claims tenant_id=B (get_tenant_id()=B), tenant_schema=schema(B),
role=superadmin, tenant_ctx=True. Aqui isso é forjado passando o `user_id`
de casa (A) + o `tenant_id` alvo (B) explicitamente aos services — o mesmo
shape que annotation_handlers.py monta a partir de get_current_user_id()/
get_tenant_id() antes de chamar TenantClassService/AnnotationService.

Cenários (caminho vivo — service, não SQL direto; SQL só em asserção/
fixture):
  a) CLASSE: cria sob contexto assumido (identidade A, tenant B) →
     tenant_id gravado é B (não A) → list_classes(B) presente →
     list_classes(A) ausente → update_class(A) (endpoint de item) 404.
  b) ANOTAÇÃO: frame NVR taggeado B (mesmo padrão de test_frame_ownership_
     assumed_tenant.py) → save_annotations sob contexto assumido (identidade
     A, tenant B) → get_frame_annotations(B) presente → get_frame_
     annotations(A) 404 → save_annotations(A) também 404 e NÃO grava
     (contagem em frame_annotations inalterada).
  c) Anti-mis-tag: nada escrito sob B é recuperável a partir de A por
     nenhum caminho exercitado acima (list, item, leitura, tentativa de
     escrita).

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL
(mesma fixture `pg_raw`/`pg_pool` de tests/integration/conftest.py).
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.domain.services.annotation_service import AnnotationService
from app.domain.services.tenant_class_service import TenantClassService
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository

_STORAGE_PATH = "app.infrastructure.storage.local_storage.get_storage"


@pytest.fixture
def two_tenants_and_superadmin(pg_raw):  # type: ignore[no-untyped-def]
    """Tenant A (casa do superadmin) + tenant B (alvo assumido) + superadmin em A.

    Fixture única (mesmo racional de two_tenants_and_user em
    test_model_tag_assumed_tenant.py) para controlar a ORDEM de teardown:
    yolo_classes e training_frames carregam FK NÃO-cascata para tenants
    (migrations 093/094) — precisam sumir antes dos tenants. frame_
    annotations cai em cascata ao apagar training_frames (FK ON DELETE
    CASCADE, migration 003), então não precisa de DELETE próprio.
    """
    home_a = str(uuid4())
    target_b = str(uuid4())
    user_id = str(uuid4())
    with pg_raw.cursor() as cur:
        for tid, tag in ((home_a, "home"), (target_b, "target")):
            slug = f"{tag}-{tid[:8]}"
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (tid, f"IntTest {slug}", slug),
            )
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, f"sa-{user_id[:8]}@test.dev", "x", "IntTest SA",
             "superadmin", home_a),
        )
    yield home_a, target_b, user_id
    with pg_raw.cursor() as cur:
        # training_frames ANTES dos tenants (FK training_frames_tenant_id_fkey
        # não-cascata) — cascade cuida de frame_annotations.
        cur.execute(
            "DELETE FROM public.training_frames WHERE tenant_id IN (%s, %s)",
            (home_a, target_b),
        )
        # yolo_classes ANTES dos tenants (FK yolo_classes_tenant_id_fkey
        # não-cascata, migration 093) — explícito em vez de confiar no
        # ON DELETE CASCADE de user_id, mesma cautela do mirror.
        cur.execute(
            "DELETE FROM public.yolo_classes WHERE tenant_id IN (%s, %s) "
            "OR user_id = %s",
            (home_a, target_b, user_id),
        )
        cur.execute("DELETE FROM public.users WHERE id = %s", (user_id,))
        cur.execute(
            "DELETE FROM public.tenants WHERE id IN (%s, %s)", (home_a, target_b)
        )


@pytest.fixture
def nvr_frame_in_target(pg_raw, two_tenants_and_superadmin):  # type: ignore[no-untyped-def]
    """Frame NVR (video_id NULL) taggeado com o tenant ALVO (B) — mesmo
    padrão de nvr_frame_in_target em test_frame_ownership_assumed_tenant.py
    (é assim que nvr_extraction tageia: tenant_id = get_tenant_id() do
    contexto, não o de casa)."""
    _, target_b, _ = two_tenants_and_superadmin
    fid = str(uuid4())
    key = f"training-images/{target_b}/nvr/{fid}.jpg"
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, video_id, frame_number, filename, source, r2_key, tenant_id) "
            "VALUES (%s, NULL, %s, %s, %s, %s, %s)",
            (fid, 0, key, "nvr", key, target_b),
        )
    yield fid
    # Teardown coberto por two_tenants_and_superadmin (DELETE por tenant_id);
    # DELETE aqui seria redundante (no-op se já sumiu).


def _annotation_payload() -> list[dict]:
    """Uma anotação válida contra o catálogo GLOBAL do módulo epi
    (module_classes: class_id=0='helmet', migration 009) — não depende de
    nenhuma classe custom do tenant, mantendo o cenário de anotação
    independente do cenário de classe."""
    return [{
        "class_id": 0,
        "class_name": "helmet",
        "module_code": "epi",
        "x_center": 0.5,
        "y_center": 0.5,
        "width": 0.2,
        "height": 0.2,
    }]


class TestClassWriteReadUnderAssumedTenant:
    """Classe criada pelo caminho vivo (TenantClassService, ver
    annotation_handlers.py:186-199) sob contexto assumido tageia com o
    tenant do CONTEXTO (B) — write-then-read prova que a escrita não
    vazou pro tenant de casa (A) do superadmin."""

    def test_class_created_under_assumed_context_tags_and_scopes_to_target(
        self, pg_pool, pg_raw, two_tenants_and_superadmin
    ):  # type: ignore[no-untyped-def]
        home_a, target_b, user_id = two_tenants_and_superadmin
        service = TenantClassService(AnnotationRepository(pg_pool))
        class_name = f"AssumedClass-{uuid4().hex[:8]}"

        # Sob contexto assumido: identidade = user_id de CASA (A), tenant do
        # CONTEXTO = target_b — mesmo shape que create_class_handler monta a
        # partir de get_current_user_id()/get_tenant_id().
        created = service.create_class(
            user_id=UUID(user_id),
            tenant_id=target_b,
            name=class_name,
            module_code="epi",
            is_violation=True,
        )

        # ESCRITA: a tag gravada no banco é o tenant do CONTEXTO (B), nunca
        # a casa (A) — o pior caso deste bug é gravar com um tenant errado
        # sem erro nenhum.
        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT tenant_id FROM yolo_classes WHERE id = %s", (created["id"],)
            )
            row = cur.fetchone()
        assert row is not None
        assert str(row["tenant_id"]) == target_b
        assert str(row["tenant_id"]) != home_a

        # LEITURA de volta sob B: presente.
        under_b = service.list_classes(
            target_b, user_id=UUID(user_id), module_code="epi"
        )
        assert any(c["id"] == created["id"] for c in under_b)

        # LEITURA sob a casa A (contexto puro, sem assumir nada): ausente —
        # cross-tenant não vaza pela listagem (C-01).
        under_a = service.list_classes(
            home_a, user_id=UUID(user_id), module_code="epi"
        )
        assert all(c["id"] != created["id"] for c in under_a)

        # Endpoint de ITEM (update_class_handler) sob A: 404 — nunca 403,
        # nunca revela que a classe existe em outro tenant (C-01, ADR-0017).
        with pytest.raises(NotFoundError):
            service.update_class(
                created["id"], home_a, user_id=UUID(user_id), name="ShouldNotWork"
            )

        # Simetria: sob B (contexto certo) o mesmo endpoint de item enxerga
        # e edita a classe normalmente.
        updated = service.update_class(
            created["id"], target_b, user_id=UUID(user_id), color="#112233"
        )
        assert updated["id"] == created["id"]
        assert updated["color"] == "#112233"


class TestAnnotationWriteReadUnderAssumedTenant:
    """Anotação salva pelo caminho vivo (AnnotationService.save_annotations,
    ver annotation_handlers.py:104-117) sob contexto assumido só é lida de
    volta sob o MESMO tenant (B) — e uma tentativa de ler/gravar sob a casa
    (A) nem enxerga o frame, nem grava nada."""

    @staticmethod
    def _service(pg_pool) -> AnnotationService:
        return AnnotationService(
            AnnotationRepository(pg_pool),
            FrameRepository(pg_pool),
            ModuleRepository(pg_pool),
        )

    def test_annotation_saved_under_assumed_context_readable_under_target_only(
        self, pg_pool, pg_raw, two_tenants_and_superadmin, nvr_frame_in_target
    ):  # type: ignore[no-untyped-def]
        home_a, target_b, user_id = two_tenants_and_superadmin
        service = self._service(pg_pool)

        # ESCRITA sob contexto assumido: identidade = user_id de CASA (A),
        # tenant do CONTEXTO = target_b — mesmo shape que save_annotations_
        # handler monta a partir de get_current_user_id()/get_tenant_id().
        with patch(_STORAGE_PATH):
            count = service.save_annotations(
                UUID(nvr_frame_in_target),
                _annotation_payload(),
                user_id=UUID(user_id),
                tenant_id=target_b,
            )
        assert count == 1

        # LEITURA de volta sob B: presente.
        under_b = service.get_frame_annotations(
            UUID(nvr_frame_in_target), user_id=UUID(user_id), tenant_id=target_b
        )
        assert len(under_b) == 1
        assert under_b[0]["class_name"] == "helmet"

        # LEITURA sob a casa A (contexto puro): 404 — o ownership check
        # (FrameRepository.get_by_id_and_user) nem acha o frame, mesmo
        # padrão do fix de #313.
        with pytest.raises(NotFoundError):
            service.get_frame_annotations(
                UUID(nvr_frame_in_target), user_id=UUID(user_id), tenant_id=home_a
            )

        # Tentativa de ESCRITA sob A: também 404 — e não grava nada. Prova
        # o caso c) anti-mis-tag: nem escrita nem leitura cross-tenant
        # recuperam/adicionam dado sob o tenant errado.
        with pytest.raises(NotFoundError):
            with patch(_STORAGE_PATH):
                service.save_annotations(
                    UUID(nvr_frame_in_target),
                    _annotation_payload(),
                    user_id=UUID(user_id),
                    tenant_id=home_a,
                )

        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM frame_annotations WHERE frame_id = %s",
                (nvr_frame_in_target,),
            )
            n = cur.fetchone()["n"]
        assert n == 1  # inalterado — a tentativa sob A não grava nem duplica
