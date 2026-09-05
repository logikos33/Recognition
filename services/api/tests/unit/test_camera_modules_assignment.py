"""
Unit — GET/PUT /api/cameras/modules (vínculo N:N câmera↔módulo, migration 134).

É a rota que a tela de atribuição do Estúdio usa para o dono separar o que é
EPI do que é estacionamento.

O que estes testes existem para impedir:
  · vazamento cross-tenant: câmera de outro tenant responde 404, NUNCA 403
    (403 confirmaria que ela existe — C-01);
  · módulo que o tenant não contratou entrar por payload montado à mão
    (fail-closed, a mesma regra do PATCH /<id>/module);
  · a ação em massa virar N chamadas — o corpo leva a lista inteira de câmeras
    e uma só transação;
  · `modules: []` ser recusado: "não serve a módulo nenhum" é decisão legítima,
    e sem ela o dono não consegue DESFAZER uma marcação errada.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.modules_handler as handler

TENANT = "11111111-1111-1111-1111-111111111111"
CAM_A = "44444444-4444-4444-4444-444444444444"
CAM_B = "55555555-5555-5555-5555-555555555555"
CAM_DE_OUTRO_TENANT = "99999999-9999-9999-9999-999999999999"


def _auth(app, role: str = "admin", modules: list[str] | None = None) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi", "quality"] if modules is None else modules,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _camera(cam_id: str, name: str) -> dict:
    return {
        "id": cam_id,
        "tenant_id": TENANT,
        "name": name,
        "location": None,
        "is_active": True,
    }


@pytest.fixture()
def repos(monkeypatch):
    camera_repo = MagicMock()
    link_repo = MagicMock()
    camera_repo.get_by_user.return_value = [
        _camera(CAM_A, "Corredor Segurança do trabalho"),
        _camera(CAM_B, "Qualidade 06"),
    ]
    link_repo.list_by_tenant.return_value = []
    link_repo.replace_for_cameras.return_value = 1
    monkeypatch.setattr(handler, "_get_camera_repo", lambda: camera_repo)
    monkeypatch.setattr(handler, "_get_link_repo", lambda: link_repo)
    return camera_repo, link_repo


class TestListCameraModules:

    def test_sem_auth_401(self, client, repos):
        assert client.get("/api/cameras/modules").status_code == 401

    def test_camera_sem_vinculo_vem_com_lista_vazia(self, app, client, repos):
        """A tabela nasce vazia (sem backfill): TODA câmera começa aqui.

        `modules: []` é o estado "sem módulo" — a câmera continua na lista,
        não some dela. Se sumisse, o dono não teria como declarar nenhuma.
        """
        resp = client.get("/api/cameras/modules", headers=_auth(app))
        assert resp.status_code == 200
        cams = resp.get_json()["data"]["cameras"]
        assert [c["modules"] for c in cams] == [[], []]
        assert {c["name"] for c in cams} == {
            "Corredor Segurança do trabalho", "Qualidade 06",
        }

    def test_camera_em_dois_modulos_devolve_os_dois(self, app, client, repos):
        """N:N de verdade — "Qualidade 01 EPI" é o caso de uso escrito no nome."""
        _, link_repo = repos
        link_repo.list_by_tenant.return_value = [
            {"camera_id": CAM_B, "module_code": "epi"},
            {"camera_id": CAM_B, "module_code": "quality"},
        ]
        resp = client.get("/api/cameras/modules", headers=_auth(app))
        cams = {c["id"]: c["modules"] for c in resp.get_json()["data"]["cameras"]}
        assert sorted(cams[CAM_B]) == ["epi", "quality"]
        assert cams[CAM_A] == []

    def test_modules_enabled_vem_da_claim_do_tenant(self, app, client, repos):
        resp = client.get("/api/cameras/modules", headers=_auth(app, modules=["epi"]))
        assert resp.get_json()["data"]["modules_enabled"] == ["epi"]

    def test_lista_o_tenant_inteiro_numa_consulta(self, app, client, repos):
        """Uma consulta de vínculos, não uma por câmera.

        A versão "um GET por câmera" da aba vizinha estourou o pool de conexões
        da API nas 28 câmeras do RVB.
        """
        _, link_repo = repos
        client.get("/api/cameras/modules", headers=_auth(app))
        link_repo.list_by_tenant.assert_called_once_with(TENANT)


class TestPutCameraModules:

    def test_sem_auth_401(self, client, repos):
        assert client.put("/api/cameras/modules", json={}).status_code == 401

    def test_grava_o_conjunto_pedido(self, app, client, repos):
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_B], "modules": ["quality"]},
        )
        assert resp.status_code == 200
        args = link_repo.replace_for_cameras.call_args[0]
        assert args[0] == TENANT
        assert args[1] == [CAM_B]
        assert args[2] == ["quality"]

    def test_massa_vai_num_pedido_so(self, app, client, repos):
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_A, CAM_B], "modules": ["epi"]},
        )
        assert resp.status_code == 200
        assert link_repo.replace_for_cameras.call_count == 1
        assert link_repo.replace_for_cameras.call_args[0][1] == [CAM_A, CAM_B]

    def test_lista_vazia_de_modulos_e_valida(self, app, client, repos):
        """"Não serve a módulo nenhum" é decisão, não erro de payload."""
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_A], "modules": []},
        )
        assert resp.status_code == 200
        assert link_repo.replace_for_cameras.call_args[0][2] == []

    def test_camera_de_outro_tenant_404_e_nao_grava(self, app, client, repos):
        """C-01: 404, nunca 403 — 403 confirmaria que a câmera existe."""
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_DE_OUTRO_TENANT], "modules": ["epi"]},
        )
        assert resp.status_code == 404
        link_repo.replace_for_cameras.assert_not_called()

    def test_uma_camera_alheia_no_lote_aborta_o_lote_inteiro(self, app, client, repos):
        """Nunca grava parcialmente: ou o lote todo é do tenant, ou nada acontece."""
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_A, CAM_DE_OUTRO_TENANT], "modules": ["epi"]},
        )
        assert resp.status_code == 404
        link_repo.replace_for_cameras.assert_not_called()

    def test_modulo_nao_contratado_e_recusado(self, app, client, repos):
        """Fail-closed contra a claim do tenant — mesma regra do PATCH /module."""
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app, modules=["epi"]),
            json={"camera_ids": [CAM_A], "modules": ["quality"]},
        )
        assert resp.status_code in (401, 403)
        link_repo.replace_for_cameras.assert_not_called()

    def test_camera_ids_vazio_e_400(self, app, client, repos):
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [], "modules": ["epi"]},
        )
        assert resp.status_code == 400

    def test_camera_id_que_nao_e_uuid_e_400(self, app, client, repos):
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": ["nao-e-uuid"], "modules": ["epi"]},
        )
        assert resp.status_code == 400

    def test_camera_repetida_no_payload_grava_uma_vez(self, app, client, repos):
        _, link_repo = repos
        client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_A, CAM_A], "modules": ["epi", "epi"]},
        )
        assert link_repo.replace_for_cameras.call_args[0][1] == [CAM_A]
        assert link_repo.replace_for_cameras.call_args[0][2] == ["epi"]

    def test_devolve_o_estado_relido_do_banco(self, app, client, repos):
        """Ecoar o payload esconderia divergência entre pedido e gravado."""
        _, link_repo = repos
        link_repo.list_by_tenant.return_value = [
            {"camera_id": CAM_A, "module_code": "epi"},
        ]
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app),
            json={"camera_ids": [CAM_A], "modules": ["epi", "quality"]},
        )
        assert resp.get_json()["data"]["assignments"] == {CAM_A: ["epi"]}

    def test_viewer_sem_permissao_nao_grava(self, app, client, repos):
        _, link_repo = repos
        resp = client.put(
            "/api/cameras/modules",
            headers=_auth(app, role="viewer"),
            json={"camera_ids": [CAM_A], "modules": ["epi"]},
        )
        assert resp.status_code in (401, 403)
        link_repo.replace_for_cameras.assert_not_called()
