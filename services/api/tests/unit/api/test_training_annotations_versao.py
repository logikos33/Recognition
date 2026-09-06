"""O token de concorrência tem de ATRAVESSAR a fronteira HTTP (#801).

Valor que o cliente ecoa de volta precisa de teste PELA ROTA, não só no
service — foi assim que um cursor quebrado passou por review e por CI.

Aqui: `version` sai no GET, volta no POST, chega ao service como
`versao_esperada`, e o `ConflictError` do repository vira **409 com a frase do
servidor** (não 200, não 500) — o mesmo desenho do 409 da fila de Verificação.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from app.core.exceptions import ConflictError

TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.annotation_handlers"

CAIXA = {"class_id": 1, "class_name": "Luvas", "module_code": "epi",
         "x_center": 0.3, "y_center": 0.4, "width": 0.1, "height": 0.12}


def _token(app, role="admin"):
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": role, "tenant_id": TENANT_ID},
        )


def _service(version="v-atual", saved=1):
    svc = MagicMock()
    svc.get_frame_annotations.return_value = []
    svc.save_annotations.return_value = saved
    svc.annotations_version.return_value = version
    return svc


class TestVersaoNaRota:
    def test_get_devolve_a_versao_junto_das_caixas(self, client, app):
        """Sem isso o cliente não tem o que ecoar — a guarda não existe."""
        svc = _service(version="abc123")
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.get(
                f"/api/training/frames/{uuid4()}/annotations",
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.status_code == 200
        assert res.get_json()["version"] == "abc123"

    def test_post_repassa_a_versao_lida_pelo_cliente(self, client, app):
        svc = _service()
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.post(
                f"/api/training/frames/{uuid4()}/annotations",
                json={"annotations": [CAIXA], "version": "a-que-eu-li"},
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.status_code == 200
        assert svc.save_annotations.call_args.kwargs["versao_esperada"] == "a-que-eu-li"

    def test_post_devolve_a_versao_nova(self, client, app):
        """Sem devolver, o cliente ficaria com a versão que ele mesmo acabou
        de invalidar — e o próximo autosave do MESMO frame bateria em 409
        contra o próprio trabalho."""
        svc = _service(version="depois-do-save")
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.post(
                f"/api/training/frames/{uuid4()}/annotations",
                json={"annotations": [CAIXA], "version": "antes"},
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.get_json()["version"] == "depois-do-save"

    def test_conflito_vira_409_com_a_frase_do_servidor(self, client, app):
        """O bug do #801 medido no DEV: este POST voltava **200 {"saved":1}**
        e a caixa do primeiro anotador sumia."""
        svc = _service()
        svc.save_annotations.side_effect = ConflictError(
            "Ana salvou anotações neste frame há 2 minutos. Nada foi sobrescrito."
        )
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.post(
                f"/api/training/frames/{uuid4()}/annotations",
                json={"annotations": [CAIXA], "version": "vazio"},
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.status_code == 409, "save concorrente voltando 200 é o #801"
        corpo = res.get_json()
        assert "Ana" in corpo["error"]
        assert "2 minutos" in corpo["error"]

    def test_sem_versao_continua_aceito(self, client, app):
        """Cliente antigo/chamada interna não quebra (guarda é opt-in)."""
        svc = _service()
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.post(
                f"/api/training/frames/{uuid4()}/annotations",
                json={"annotations": [CAIXA]},
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.status_code == 200
        assert svc.save_annotations.call_args.kwargs["versao_esperada"] is None

    def test_versao_que_nao_e_string_e_recusada_na_fronteira(self, client, app):
        """Validação no limite de confiança: `{"version": 123}` compararia
        diferente de qualquer versão real e viraria 409 eterno — 400 honesto."""
        svc = _service()
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=svc):
            res = client.post(
                f"/api/training/frames/{uuid4()}/annotations",
                json={"annotations": [CAIXA], "version": 123},
                headers={"Authorization": f"Bearer {_token(app)}"},
            )
        assert res.status_code == 400
        svc.save_annotations.assert_not_called()
