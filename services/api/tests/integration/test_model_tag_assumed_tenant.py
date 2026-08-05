"""Integração: modelo treinado sob contexto assumido fica visível na registry
do tenant assumido — não 404 (lacuna do contexto assumido, pós-#302/#313).

Reproduz o bug no nível do banco: um trained_model taggeado com o tenant DE
CASA do dono (comportamento pré-fix, quando o caller omitia o tenant) fica 404
em ModelRegistryRepository.get_for_tenant() sob o contexto assumido — exatamente
como o modelo recém-treinado sumia da registry quando um superadmin assumia
outro tenant (POST /tenants/<B>/assume) e treinava. `get_for_tenant` escopa por
`COALESCE(tm.tenant_id, u.tenant_id) = get_tenant_id()`; se o modelo nasce
taggeado com o tenant de casa A, sob contexto B (get_tenant_id()=B) A != B →
None → 404.

Falha-antes/passa-depois (no nível do banco, sem depender de stash):
  - caso 'buggy'  (create_model SEM tenant_id → fallback
    `(SELECT tenant_id FROM users WHERE id=user_id)` = casa A) → get_for_tenant
    sob o tenant assumido B devolve None (o 404 latente).
  - caso 'fixed'  (create_model COM o tenant do contexto = B) → get_for_tenant
    sob B devolve o modelo, e sob a casa A devolve None (cross-tenant → None, C-01).
A correção real nos callers (job_handlers/training_service/socket_bridge)
garante que o caminho de produção sempre passe o tenant do CONTEXTO, não o de
casa — coberto por unit tests em test_training_service.py / test_socket_bridge.py.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.model_registry_repository import (
    ModelRegistryRepository,
)
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)


@pytest.fixture
def two_tenants_and_user(pg_raw):  # type: ignore[no-untyped-def]
    """Tenant A (casa do dono) + tenant B (alvo assumido) + usuário em A.

    Cria os DOIS tenants aqui (não reusa a fixture `tenant_id`) para controlar a
    ORDEM de teardown: trained_models tem FK não-cascata para tenants, então
    os modelos precisam sumir ANTES dos tenants. Fixture única = um só teardown,
    ordem garantida (modelos → user → tenants).
    """
    home_tenant = str(uuid4())
    assumed_tenant = str(uuid4())
    user_id = str(uuid4())
    with pg_raw.cursor() as cur:
        for tid, tag in ((home_tenant, "home"), (assumed_tenant, "assumed")):
            slug = f"{tag}-{tid[:8]}"
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (tid, f"IntTest {slug}", slug),
            )
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, f"train-{user_id[:8]}@test.dev", "x", "IntTest Trainer",
             "operator", home_tenant),
        )
    yield home_tenant, assumed_tenant, user_id
    with pg_raw.cursor() as cur:
        # modelos ANTES dos tenants (FK trained_models_tenant_id_fkey não-cascata)
        cur.execute("DELETE FROM public.trained_models WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (user_id,))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s)",
                    (home_tenant, assumed_tenant))


class TestModelTagAssumedContext:
    """O tenant do modelo escopa a registry — deve ser o do CONTEXTO, não o de casa."""

    def test_home_tagged_model_is_404_under_assumed_context(
        self, pg_pool, two_tenants_and_user
    ):  # type: ignore[no-untyped-def]
        home_tenant, assumed_tenant, user_id = two_tenants_and_user

        training_repo = TrainingRepository(pg_pool)
        registry = ModelRegistryRepository(pg_pool)

        # BUG pré-fix: sem tenant_id → repository cai no fallback do tenant de
        # casa (A). Sob o contexto assumido B, o modelo some da registry.
        buggy = training_repo.create_model({
            "user_id": user_id,
            "name": "buggy-home-tagged",
            "model_path": "models/buggy.onnx",
        })
        assert registry.get_for_tenant(buggy["id"], assumed_tenant) is None

        # FIX: tenant do CONTEXTO da requisição (get_tenant_id() = B).
        fixed = training_repo.create_model({
            "user_id": user_id,
            "name": "fixed-context-tagged",
            "model_path": "models/fixed.onnx",
            "tenant_id": assumed_tenant,
        })
        # Visível sob o tenant assumido B...
        assert registry.get_for_tenant(fixed["id"], assumed_tenant) is not None
        # ...e invisível a partir do tenant de casa A (cross-tenant → None, C-01).
        assert registry.get_for_tenant(fixed["id"], home_tenant) is None
