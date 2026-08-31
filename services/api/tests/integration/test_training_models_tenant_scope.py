"""Integração: GET /api/training/models escopado por TENANT, não por usuário.

Achado de segurança do ESTADO-F5 (mutirão risk:security): /novo/estudio/modelo
mostrava "Nenhum modelo treinado ainda" para usuários do tenant rvb, enquanto a
aba Escopo (GET /api/cameras/<id>/available-models, que já usa
TrainingRepository.list_for_tenant) listava ~11 jobs reais do mesmo tenant — as
duas fontes divergiam porque TrainingRepository.get_models_by_user filtrava
`WHERE tm.user_id = %s`: cada usuário só via os modelos que ELE PRÓPRIO
treinou, mesmo dentro do mesmo tenant.

Fix: get_models_by_tenant(tenant_id), WHERE COALESCE(tm.tenant_id,
u.tenant_id) = %s — mesmo padrão de ModelRegistryRepository.list_for_tenant
(cobre linhas legadas pré-090 com tm.tenant_id NULL).

Falha-antes/passa-depois: este arquivo testa a API pós-fix
(repo.get_models_by_tenant). Contra o código ANTES do fix esse método não
existe (AttributeError — a suíte inteira falha na coleta/execução); a query
antiga só devolvia o modelo para o `user_id` que o treinou.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)


@pytest.fixture
def tenant_x_two_users_and_tenant_y(pg_raw):  # type: ignore[no-untyped-def]
    """Tenant X com dois usuários (A treina, B só está no mesmo tenant) +
    tenant Y (nenhuma relação com o modelo).
    """
    tenant_x = str(uuid4())
    tenant_y = str(uuid4())
    user_a = str(uuid4())
    user_b = str(uuid4())
    with pg_raw.cursor() as cur:
        for tid, tag in ((tenant_x, "x"), (tenant_y, "y")):
            slug = f"tenant-{tag}-{tid[:8]}"
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (tid, f"IntTest {slug}", slug),
            )
        for uid, tag in ((user_a, "a"), (user_b, "b")):
            cur.execute(
                "INSERT INTO public.users "
                "(id, email, password_hash, name, role, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uid, f"user-{tag}-{uid[:8]}@test.dev", "x",
                 f"IntTest User {tag.upper()}", "operator", tenant_x),
            )
    yield tenant_x, tenant_y, user_a, user_b
    with pg_raw.cursor() as cur:
        # modelos ANTES dos users/tenants (FK não-cascata trained_models→tenants)
        cur.execute(
            "DELETE FROM public.trained_models WHERE user_id IN (%s, %s)",
            (user_a, user_b),
        )
        cur.execute("DELETE FROM public.users WHERE id IN (%s, %s)", (user_a, user_b))
        cur.execute(
            "DELETE FROM public.tenants WHERE id IN (%s, %s)", (tenant_x, tenant_y)
        )


class TestModelsScopedByTenantNotByUser:
    """get_models_by_tenant devolve modelos do TENANT inteiro (C-01)."""

    def test_i_model_trained_by_user_a_appears_under_tenant_x(
        self, pg_pool, tenant_x_two_users_and_tenant_y
    ):  # type: ignore[no-untyped-def]
        """(i) modelo criado por user A do tenant X aparece na listagem do
        tenant X — que é exatamente o que qualquer outro usuário do MESMO
        tenant (ex.: user B) recebe na rota GET /api/training/models, já
        que o escopo pós-fix é o tenant do JWT, não o id de quem treinou.
        """
        tenant_x, _tenant_y, user_a, _user_b = tenant_x_two_users_and_tenant_y
        repo = TrainingRepository(pg_pool)

        model = repo.create_model({
            "user_id": user_a,
            "name": "modelo-treinado-por-a",
            "model_path": "models/a/best.onnx",
            "tenant_id": tenant_x,
        })

        models_do_tenant = repo.get_models_by_tenant(tenant_x)
        ids = {str(m["id"]) for m in models_do_tenant}
        assert str(model["id"]) in ids

    def test_ii_model_of_tenant_x_does_not_appear_under_tenant_y(
        self, pg_pool, tenant_x_two_users_and_tenant_y
    ):  # type: ignore[no-untyped-def]
        """(ii) cross-tenant: modelo do tenant X não aparece para o tenant Y
        (C-01 — lista vazia/sem o registro, nunca vazamento)."""
        tenant_x, tenant_y, user_a, _user_b = tenant_x_two_users_and_tenant_y
        repo = TrainingRepository(pg_pool)

        model = repo.create_model({
            "user_id": user_a,
            "name": "modelo-do-tenant-x",
            "model_path": "models/x/best.onnx",
            "tenant_id": tenant_x,
        })

        models_do_tenant_y = repo.get_models_by_tenant(tenant_y)
        ids = {str(m["id"]) for m in models_do_tenant_y}
        assert str(model["id"]) not in ids
