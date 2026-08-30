"""
Tests: PATCH /api/alerts/<id>/violations — correção de caixa com proveniência.

Prova o que o item (b) da rodada exige: a caixa só pode ser MOVIDA (nunca a
classe reescrita), a unidade é carimbada pelo servidor, o tenant do JWT é o que
escopa a escrita, e cross-tenant/id malformado devolvem o MESMO 404 (C-01).
Cobre também os dois campos novos da projeção do detalhe SEM reintroduzir o
vazamento de `verified_by`.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
ALERT_ID = str(uuid4())
USER_NAME = "Ana Souza"
_GET_REPO = "app.api.v1.alerts.routes._get_repo"
_GET_STORAGE = "app.infrastructure.storage.local_storage.get_storage"
_USER_REPOSITORY = "app.api.v1.alerts.routes.UserRepository"
_POOL_INSTANCE = "app.api.v1.alerts.routes.DatabasePool.get_instance"

_BBOX_OK = {"correcoes": [{"index": 0, "bbox": [10, 20, 30, 40]}]}


@contextmanager
def _patch_user_lookup(name=USER_NAME):  # type: ignore[no-untyped-def]
    """Mocka o lookup de nome do usuário (`_nome_usuario_atual`) na rota.

    Patcha `DatabasePool.get_instance` (pool pode não estar inicializado no
    processo de teste) e `UserRepository` juntos, para o lookup nunca tocar
    banco real independente da ordem de execução dos testes.
    """
    users = MagicMock()
    users.get_by_id.return_value = {"name": name} if name is not None else None
    with patch(_POOL_INSTANCE, return_value=MagicMock()), \
            patch(_USER_REPOSITORY, return_value=users):
        yield users


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "test@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _repo_ok():
    repo = MagicMock()
    repo.corrigir_bboxes.return_value = {
        "violations": [{"class": "Sem protetor de ouvido", "bbox": [10.0, 20.0, 30.0, 40.0]}],
        "violations_historico": [
            {"em": "2026-08-24T10:00:00+00:00", "por": USER_ID, "por_nome": USER_NAME, "tipo": "bbox",
             "violations_anteriores": [{"class": "Sem protetor de ouvido", "bbox": [1, 2, 3, 4]}]},
        ],
    }
    return repo


def _patch(client, headers, body, repo=None):
    with patch(_GET_REPO, return_value=repo if repo is not None else _repo_ok()), _patch_user_lookup():
        return client.patch(
            f"/api/alerts/{ALERT_ID}/violations", headers=headers, json=body
        )


class TestCorrigirViolations:

    def test_without_token_returns_401(self, client):
        resp = client.patch(f"/api/alerts/{ALERT_ID}/violations", json=_BBOX_OK)
        assert resp.status_code == 401

    def test_success_passes_jwt_tenant_and_user_to_repo(self, client, auth_headers):
        repo = _repo_ok()
        resp = _patch(client, auth_headers, _BBOX_OK, repo)
        assert resp.status_code == 200
        kwargs = repo.corrigir_bboxes.call_args[1]
        # tenant e autor saem do TOKEN, nunca do corpo — senão o cliente
        # escolheria de quem é o alerta e quem assinou a correção.
        assert kwargs["tenant_id"] == TENANT_ID
        assert kwargs["por"] == USER_ID
        assert kwargs["por_nome"] == USER_NAME
        assert kwargs["correcoes"] == [{"index": 0, "bbox": [10.0, 20.0, 30.0, 40.0]}]

    def test_success_returns_new_violations_and_provenance(self, client, auth_headers):
        resp = _patch(client, auth_headers, _BBOX_OK)
        data = resp.get_json()["data"]
        assert data["violations"][0]["bbox"] == [10.0, 20.0, 30.0, 40.0]
        # Só quem/quando trafega — o array anterior inteiro fica no banco.
        # `por_nome` é o nome (badge nunca mostra o UUID de `por` cru).
        assert data["correcao_ultima"] == {
            "por": USER_ID, "por_nome": USER_NAME, "em": "2026-08-24T10:00:00+00:00",
        }
        assert "violations_anteriores" not in data["correcao_ultima"]

    def test_user_lookup_falha_grava_por_nome_none_sem_quebrar_a_correcao(self, client, auth_headers):
        """Usuário não encontrado → `por_nome=None` passado ao repo, mas a
        correção segue gravando (id em `por` já é auditoria suficiente)."""
        repo = _repo_ok()
        with patch(_GET_REPO, return_value=repo), _patch_user_lookup(name=None):
            resp = client.patch(
                f"/api/alerts/{ALERT_ID}/violations", headers=auth_headers, json=_BBOX_OK
            )
        assert resp.status_code == 200
        assert repo.corrigir_bboxes.call_args[1]["por_nome"] is None

    def test_only_bbox_is_taken_from_client(self, client, auth_headers):
        """Corrigir POSIÇÃO não pode virar porta para reescrever CLASSE."""
        repo = _repo_ok()
        _patch(client, auth_headers, {
            "correcoes": [{
                "index": 0, "bbox": [1, 2, 3, 4],
                "class": "Capacete", "confidence": 1.0, "tipo": "conformidade",
            }],
        }, repo)
        enviado = repo.corrigir_bboxes.call_args[1]["correcoes"][0]
        assert set(enviado) == {"index", "bbox"}

    def test_cross_tenant_returns_404(self, client, auth_headers):
        """Repo devolve None (alerta de outro tenant OU inexistente) → 404."""
        repo = MagicMock()
        repo.corrigir_bboxes.return_value = None
        resp = _patch(client, auth_headers, _BBOX_OK, repo)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Alerta não encontrado"

    def test_malformed_id_returns_same_404(self, client, auth_headers):
        """Mesma mensagem do cross-tenant — não vaza existência por diferença."""
        with patch(_GET_REPO, return_value=_repo_ok()) as repo_factory:
            resp = client.patch(
                "/api/alerts/nao-e-uuid/violations", headers=auth_headers, json=_BBOX_OK
            )
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Alerta não encontrado"
        repo_factory.assert_not_called()

    def test_index_out_of_range_returns_400(self, client, auth_headers):
        repo = MagicMock()
        repo.corrigir_bboxes.side_effect = IndexError(9)
        resp = _patch(client, auth_headers, {"correcoes": [{"index": 9, "bbox": [1, 2, 3, 4]}]}, repo)
        assert resp.status_code == 400
        assert "index" in resp.get_json()["error"]

    @pytest.mark.parametrize("body", [
        {},                                                       # sem correcoes
        {"correcoes": []},                                        # lista vazia
        {"correcoes": "0"},                                       # nem lista
        {"correcoes": [{"index": 0, "bbox": [1, 2, 3]}]},         # 3 números
        {"correcoes": [{"index": 0, "bbox": [1, 2, 3, 4, 5]}]},   # 5 números
        {"correcoes": [{"index": 0, "bbox": [1, 2, 0, 4]}]},      # largura zero
        {"correcoes": [{"index": 0, "bbox": [1, 2, 3, -4]}]},     # altura negativa
        {"correcoes": [{"index": 0, "bbox": [-1, 2, 3, 4]}]},     # x negativo
        {"correcoes": [{"index": 0, "bbox": [1, 2, "3", 4]}]},    # string
        {"correcoes": [{"index": 0, "bbox": [1, 2, True, 4]}]},   # bool não é número
        {"correcoes": [{"index": -1, "bbox": [1, 2, 3, 4]}]},     # index negativo
        {"correcoes": [{"index": "0", "bbox": [1, 2, 3, 4]}]},    # index não-int
        {"correcoes": [{"bbox": [1, 2, 3, 4]}]},                  # sem index
        {"correcoes": ["nao é objeto"]},                          # item errado
        {"correcoes": [{"index": 0, "bbox": [1, 2, 3, 4]}] * 21},  # acima do teto
    ])
    def test_invalid_bodies_return_400_without_touching_repo(self, client, auth_headers, body):
        repo = MagicMock()
        resp = _patch(client, auth_headers, body, repo)
        assert resp.status_code == 400
        repo.corrigir_bboxes.assert_not_called()


class TestDetalheExpoeVeredito:
    """GET /api/alerts/<id> ganhou veredito + proveniência, sem vazar verified_by."""

    _ROW = {
        "id": ALERT_ID,
        "camera_id": str(uuid4()),
        "camera_name": "Canal 8",
        "violations": [{"class": "Sem protetor de ouvido", "confidence": 0.76}],
        "confidence": 0.76,
        "acknowledged": True,
        "evidence_key": "k",
        "timestamp": None,
        "created_at": None,
        "tenant_id": TENANT_ID,
        "verification_verdict": "reject",
        "verified_at": None,
        "verified_by": f"user:{USER_ID}",
        "violations_historico": [
            {"em": "2026-08-24T10:00:00+00:00", "por": USER_ID, "tipo": "bbox",
             "violations_anteriores": []},
        ],
    }

    def _get(self, client, headers, row):
        repo = MagicMock()
        repo.get_by_id.return_value = dict(row)
        storage = MagicMock()
        storage.generate_presigned_download_url.return_value = "https://r2/signed"
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=storage):
            return client.get(f"/api/alerts/{ALERT_ID}", headers=headers)

    def test_exposes_verdict_and_last_correction(self, client, auth_headers):
        alert = self._get(client, auth_headers, self._ROW).get_json()["data"]["alert"]
        assert alert["verification_verdict"] == "reject"
        # Entrada do ledger é ANTERIOR ao `por_nome` (sem a chave) — vira
        # None, nunca o UUID de `por` (é o defeito provado no DEV).
        assert alert["correcao_ultima"] == {
            "por": USER_ID, "por_nome": None, "em": "2026-08-24T10:00:00+00:00",
        }
        # Regressão do assert de vazamento em test_alerts_routes.py:194.
        assert "verified_by" not in alert and "tenant_id" not in alert

    def test_alert_without_history_has_null_correction(self, client, auth_headers):
        alert = self._get(
            client, auth_headers, dict(self._ROW, violations_historico=[], verification_verdict=None)
        ).get_json()["data"]["alert"]
        assert alert["correcao_ultima"] is None
        assert alert["verification_verdict"] is None
