"""
Segurança — POST /api/training/models/<id>/activate escopado pelo tenant (C-01).

Achado (a), grupo TREINO/MODELOS (P0): a rota legada ativava QUALQUER
trained_models (`UPDATE ... WHERE id = %s`, training_repository.activate_model,
sem posse/tenant) com qualquer role autenticada — bypass do fluxo canônico
POST /api/v1/models/<id>/activate (gate training:approve + avaliação
campeão×desafiante + rollout sync).

Fix: a rota legada delega ao MESMO handler canônico (activate_registry_model):
posse por tenant → 404, gate approve → 403, eval, rollout sync, model:reload.

Protocolo falha-antes/passa-depois: B em modelo de A → 404 e nenhuma mutação;
role sem training:approve → 403; superadmin do tenant dono → 200 via canônico.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.models.registry_handlers as registry_handlers

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
MODEL_ID = "55555555-5555-5555-5555-555555555555"

_SVC_PATH = "app.api.v1.training.job_handlers.get_training_service"


def _auth(app, role: str, tenant_id: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _model_row(tenant_id: str = TENANT_A, **overrides) -> dict:
    row = {
        "id": MODEL_ID,
        "user_id": str(uuid4()),
        "tenant_id": tenant_id,
        "name": "rfdetr_v1",
        "model_path": "models/t/rfdetr_v1.onnx",
        "framework": "rfdetr",
        "module_code": "epi",
        "is_active": False,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# (a) POST /api/training/models/<id>/activate
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry_repos(monkeypatch):
    """Repos do fluxo canônico (registry_handlers) mockados."""
    registry = MagicMock()
    evals = MagicMock()
    rollout = MagicMock()
    monkeypatch.setattr(registry_handlers, "_get_registry_repo", lambda: registry)
    monkeypatch.setattr(registry_handlers, "_get_eval_repo", lambda: evals)
    monkeypatch.setattr(registry_handlers, "_get_rollout_repo", lambda: rollout)
    evals.get_latest_for_model.return_value = None
    rollout.pin_model.return_value = ({"id": MODEL_ID}, None)
    # Exposto para os testes que precisam simular uma avaliação real (gate
    # Funcional/Parcial/Não avaliado, model_status.py) sem mudar a
    # assinatura de retorno usada pelos demais testes desta classe.
    registry.evals = evals
    return registry


@pytest.fixture()
def legacy_training_svc():
    """Serviço legado de treino — a rota NUNCA deve voltar a ativar por ele
    (o antigo TrainingService/TrainingRepository.activate_model, UPDATE sem
    posse, foi removido junto com o fix; o mock prova que nada o substitui)."""
    svc = MagicMock()
    svc.activate_model.return_value = _model_row(is_active=True)
    with patch(_SVC_PATH, return_value=svc):
        yield svc


class TestLegacyActivateModelTenantIsolation:
    def test_tenant_b_cannot_activate_model_of_tenant_a(
        self, app, client, registry_repos, legacy_training_svc
    ):
        """FALHA-ANTES: 200 (UPDATE trained_models WHERE id sem tenant).
        PASSA-DEPOIS: 404 (posse por tenant — C-01) e nenhuma mutação."""
        registry_repos.get_for_tenant.return_value = None  # modelo é de A
        resp = client.post(
            f"/api/training/models/{MODEL_ID}/activate",
            headers=_auth(app, "superadmin", TENANT_B),
        )
        assert resp.status_code == 404, resp.get_json()
        registry_repos.activate_for_tenant_module.assert_not_called()
        legacy_training_svc.activate_model.assert_not_called()

    @pytest.mark.parametrize("role", ["operator", "admin"])
    def test_role_without_training_approve_gets_403(
        self, app, client, registry_repos, legacy_training_svc, monkeypatch, role
    ):
        """FALHA-ANTES: 200 para qualquer role autenticada.
        PASSA-DEPOIS: mesmo gate do canônico (training:approve)."""
        import app.core.auth as core_auth
        monkeypatch.setattr(core_auth, "_has_training_override", lambda *a, **k: False)
        registry_repos.get_for_tenant.return_value = _model_row()
        resp = client.post(
            f"/api/training/models/{MODEL_ID}/activate",
            headers=_auth(app, role, TENANT_A),
        )
        assert resp.status_code == 403, resp.get_json()
        registry_repos.activate_for_tenant_module.assert_not_called()
        legacy_training_svc.activate_model.assert_not_called()

    def test_superadmin_of_owner_tenant_activates_via_canonical_flow(
        self, app, client, registry_repos, legacy_training_svc
    ):
        """Superadmin do tenant dono → 200, e a ativação passa pelo
        repositório canônico escopado por tenant+módulo, nunca pelo legado."""
        registry_repos.get_for_tenant.return_value = _model_row()
        # Gate Funcional/Parcial/Não avaliado (model_status.py) exige uma
        # avaliação com cobertura completa antes do gate de tenant/role
        # importar — sem isso o teste bloquearia em 409 antes de provar o
        # que esta classe existe para provar (posse/role via canônico).
        registry_repos.evals.get_latest_for_model.return_value = {
            "verdict": "promote",
            "metrics": {
                "map50": 0.8, "images_evaluated": 100,
                "per_class": {"capacete": {"ap": 0.8, "precision": 0.8, "recall": 0.8, "n_gt": 10}},
            },
        }
        registry_repos.activate_for_tenant_module.return_value = _model_row(is_active=True)
        resp = client.post(
            f"/api/training/models/{MODEL_ID}/activate",
            headers=_auth(app, "superadmin", TENANT_A),
        )
        assert resp.status_code == 200, resp.get_json()
        args = registry_repos.activate_for_tenant_module.call_args[0]
        assert str(args[0]) == MODEL_ID
        assert args[1] == TENANT_A
        legacy_training_svc.activate_model.assert_not_called()
