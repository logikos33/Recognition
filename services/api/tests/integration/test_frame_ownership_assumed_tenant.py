"""Integração: posse de frame NVR/upload sob CONTEXTO DE TENANT ASSUMIDO.

Reproduz o bug relatado pelo Vitor: o anotador devolvia 404 em
`GET /api/training/frames/<id>/annotations` para todo frame coletado do
gravador, embora a galeria listasse os frames normalmente.

Causa raiz (file:line): FrameRepository.get_by_id_and_user resolvia a posse
de frame sem vídeo (video_id NULL — fontes nvr/upload/auto) por
`(SELECT tenant_id FROM users WHERE id = user_id)` — o tenant DE CASA do
usuário. Quando um superadmin opera sob contexto assumido
(POST /tenants/<id>/assume, tenant_context_routes.py), a identidade do token
continua sendo o superadmin (tenant de casa A), mas o tenant efetivo é o do
alvo (B). A coleta (nvr_extraction) e a galeria (list_images_filtered) já
tageiam/filtram pelo tenant do CONTEXTO (get_tenant_id() = B); só o ownership
check divergia, olhando o tenant de casa (A) → nenhum frame batia → 404. Mesmo
bug do live view pré-#302.

Falha-antes/passa-depois:
  - ANTES: get_by_id_and_user(frame, superadmin) usava o tenant de casa (A);
    frame taggeado B ficava invisível → 404 no anotador.
  - DEPOIS: get_by_id_and_user recebe o tenant do CONTEXTO; com B o frame é
    acessível, com A (cross-tenant) continua None → 404 (C-01, ADR-0017).

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.infrastructure.database.repositories.frame_repository import FrameRepository


@pytest.fixture
def two_tenants(pg_raw):  # type: ignore[no-untyped-def]
    """tenant_home (A) = onde vive o superadmin; tenant_target (B) = contexto assumido."""
    home_a, target_b = str(uuid4()), str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (home_a, f"HomeA {home_a[:8]}", f"home-{home_a[:8]}"),
        )
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (target_b, f"TargetB {target_b[:8]}", f"target-{target_b[:8]}"),
        )
    yield home_a, target_b
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.tenants WHERE id = %s", (home_a,))
        cur.execute("DELETE FROM public.tenants WHERE id = %s", (target_b,))


@pytest.fixture
def superadmin_id(pg_raw, two_tenants) -> str:  # type: ignore[return]
    """Superadmin cujo tenant DE CASA é A (a query antiga derivava este)."""
    home_a, _ = two_tenants
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"sa-{uid[:8]}@test.dev", "x", "IntTest SA", "superadmin", home_a),
        )
    yield uid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def nvr_frame_in_target(pg_raw, two_tenants) -> str:  # type: ignore[return]
    """Frame NVR (video_id NULL) taggeado com o tenant ALVO (B) — exatamente
    como nvr_extraction tagueia (tenant_id = get_tenant_id() = contexto)."""
    _, target_b = two_tenants
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
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.training_frames WHERE id = %s", (fid,))


class TestFrameOwnershipUnderAssumedTenant:
    """get_by_id_and_user segue o tenant do CONTEXTO da requisição, não o de casa."""

    def test_nvr_frame_accessible_under_assumed_target_tenant(
        self, pg_pool, superadmin_id, nvr_frame_in_target, two_tenants
    ):
        """PASSA-DEPOIS: sob contexto assumido B, o superadmin (casa A) acessa
        o frame NVR taggeado B — o mesmo tenant que a galeria e a coleta usam."""
        _, target_b = two_tenants
        repo = FrameRepository(pg_pool)
        frame = repo.get_by_id_and_user(
            UUID(nvr_frame_in_target), UUID(superadmin_id), target_b
        )
        assert frame is not None
        assert str(frame["id"]) == nvr_frame_in_target

    def test_nvr_frame_blocked_under_home_tenant_context(
        self, pg_pool, superadmin_id, nvr_frame_in_target, two_tenants
    ):
        """FALHA-ANTES + C-01: com o tenant de casa A (o que a query ANTIGA
        derivava de users.tenant_id), o frame taggeado B fica INVISÍVEL — era
        exatamente o 404 do anotador. Cross-tenant → None → 404, nunca 403."""
        home_a, _ = two_tenants
        repo = FrameRepository(pg_pool)
        frame = repo.get_by_id_and_user(
            UUID(nvr_frame_in_target), UUID(superadmin_id), home_a
        )
        assert frame is None

    def test_unrelated_tenant_context_also_blocked(
        self, pg_pool, superadmin_id, nvr_frame_in_target
    ):
        """Contexto de um terceiro tenant (nem casa nem alvo) também não vê."""
        repo = FrameRepository(pg_pool)
        frame = repo.get_by_id_and_user(
            UUID(nvr_frame_in_target), UUID(superadmin_id), str(uuid4())
        )
        assert frame is None
