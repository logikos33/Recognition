"""Tests: a triagem do gabarito (GET fila / PUT veredito) — migration 135.

O que estas rotas não podem errar:

 · perder um dos TRÊS estados (sim/nao/nao_sei). O "não sei" é o que separa
   "o modelo errou" de "a imagem não dava para saber"; se a rota o recusasse,
   quem julga seria empurrado ao chute e o gabarito mediria o chute;
 · aceitar veredito inventado (o CHECK do banco viraria 500);
 · responder 403 (ou 404 diferente) para quadro de OUTRO tenant — 403
   confirmaria que o id existe em algum lugar (C-01);
 · deixar um quadro do POOL ser julgado como se fosse gabarito;
 · gravar em `frame_annotations` (a prova estrutural disso está em
   tests/integration/test_gabarito_nao_vaza_para_treino.py, contra Postgres
   real — aqui garante-se apenas que a rota escreve pelo repositório certo).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT_ID = "00000000-0000-0000-0000-000000000001"
FRAME_ID = "11111111-1111-1111-1111-111111111111"


def _auth_header(app, role="admin", tenant_id=TENANT_ID):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": None,
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _repo_mock(holdout: bool = True) -> MagicMock:
    repo = MagicMock()
    repo.is_holdout_frame.return_value = holdout
    repo.upsert_verdicts.return_value = 1
    repo.list_fila.return_value = []
    return repo


class TestFilaGabarito:
    def test_sem_auth_401(self, client):
        assert client.get("/api/training/gabarito/fila").status_code == 401

    def test_fila_traz_classes_com_foco_e_quadros(self, app, client):
        repo = _repo_mock()
        repo.list_fila.return_value = [
            {
                "id": FRAME_ID,
                "filename": "training-images/t/nvr/x.jpg",
                "camera_id": None,
                "camera_name": "Entrada Preparação",
                "captured_at": "2026-09-02T07:30:02+00:00",
                "width": 1920,
                "height": 1080,
                "verdicts": {"5": "sim"},
                "reason": None,
            }
        ]
        classes = [
            {"class_id": 5, "class_name": "no_gloves", "display_name": "Sem Luvas"},
            {"class_id": 100009, "class_name": "Sem mascara", "display_name": "Sem mascara"},
            {"class_id": 7, "class_name": "no_glasses", "display_name": "Sem Óculos"},
        ]
        with (
            patch(
                "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
            ),
            patch(
                "app.api.v1.training.gabarito_handlers.ModuleService"
            ) as servico,
        ):
            servico.return_value.get_classes.return_value = classes
            resp = client.get(
                "/api/training/gabarito/fila", headers=_auth_header(app)
            )

        assert resp.status_code == 200
        dados = resp.get_json()["data"]
        assert dados["total"] == 1
        assert dados["frames"][0]["verdicts"] == {"5": "sim"}
        # As duas primeiras são o FOCO — é o que trava o A/B, e a tela precisa
        # dessa hierarquia para não apresentar cinco perguntas de peso igual.
        assert [(c["nome"], c["foco"]) for c in dados["classes"]] == [
            ("Sem Luvas", True),
            ("Sem mascara", True),
            ("Sem Óculos", False),
        ]

    def test_classe_ausente_no_ambiente_nao_vira_botao(self, app, client):
        """Classe que não existe neste ambiente sai da triagem em silêncio.

        O contrário — oferecer o botão — daria um toque que nunca grava:
        a resposta iria para um class_id inventado, ou o save falharia.
        """
        repo = _repo_mock()
        with (
            patch("app.api.v1.training.gabarito_handlers._get_repo", return_value=repo),
            patch("app.api.v1.training.gabarito_handlers.ModuleService") as servico,
        ):
            servico.return_value.get_classes.return_value = [
                {"class_id": 5, "class_name": "no_gloves", "display_name": "Sem Luvas"}
            ]
            resp = client.get("/api/training/gabarito/fila", headers=_auth_header(app))

        assert [c["nome"] for c in resp.get_json()["data"]["classes"]] == ["Sem Luvas"]


class TestVeredito:
    def test_sem_auth_401(self, client):
        resp = client.put(f"/api/training/gabarito/frames/{FRAME_ID}", json={})
        assert resp.status_code == 401

    def test_os_tres_estados_sao_aceitos(self, app, client):
        """sim, nao e nao_sei — os três, na mesma requisição."""
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "sim", "100009": "nao", "7": "nao_sei"}},
                headers=_auth_header(app),
            )

        assert resp.status_code == 200
        gravados = repo.upsert_verdicts.call_args.kwargs["verdicts"]
        assert gravados == {5: "sim", 100009: "nao", 7: "nao_sei"}

    def test_nao_sei_sozinho_e_resposta_valida(self, app, client):
        """O "não sei" não é rascunho — é veredito, e grava como tal.

        Se a rota o tratasse como ausência de resposta, o quadro voltaria à
        fila para sempre e quem julga acabaria chutando para se livrar dele.
        """
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "nao_sei"}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert repo.upsert_verdicts.call_args.kwargs["verdicts"] == {5: "nao_sei"}

    def test_veredito_invalido_400_sem_escrever(self, app, client):
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "talvez"}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 400
        repo.upsert_verdicts.assert_not_called()

    def test_class_id_nao_numerico_400_sem_escrever(self, app, client):
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"hackeado": "sim"}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 400
        repo.upsert_verdicts.assert_not_called()

    def test_verdicts_vazio_400(self, app, client):
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 400

    def test_reason_invalido_400(self, app, client):
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "nao"}, "reason": "inventado"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 400
        repo.upsert_verdicts.assert_not_called()

    def test_sem_pessoa_grava_nao_em_todas_com_o_motivo(self, app, client):
        """O atalho de um toque não é caminho separado no backend.

        Chega como 'nao' em todas as classes + reason='sem_pessoa'. Um
        endpoint próprio seria uma segunda forma de escrever o mesmo fato, e
        as duas divergiriam no dia em que alguém mudasse só uma.
        """
        repo = _repo_mock()
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={
                    "verdicts": {"5": "nao", "100009": "nao"},
                    "reason": "sem_pessoa",
                },
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        chamada = repo.upsert_verdicts.call_args.kwargs
        assert chamada["reason"] == "sem_pessoa"
        assert set(chamada["verdicts"].values()) == {"nao"}

    def test_quadro_de_outro_tenant_404_e_nao_403(self, app, client):
        """Cross-tenant responde 404 (C-01) — 403 confirmaria que o id existe.

        O repositório é quem escopa por tenant; aqui prova-se que a rota
        traduz "não achei neste tenant" para 404, e não para 403 nem 500.
        """
        repo = _repo_mock(holdout=False)
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "sim"}},
                headers=_auth_header(app, tenant_id=str(uuid4())),
            )
        assert resp.status_code == 404
        repo.upsert_verdicts.assert_not_called()

    def test_quadro_do_pool_nao_pode_ser_julgado(self, app, client):
        """Mesma resposta do cross-tenant: 404.

        Distinguir "existe mas é pool" de "não existe" contaria ao chamador
        que o id existe neste tenant — e um quadro do pool não é gabarito, o
        veredito dele não mediria nada.
        """
        repo = _repo_mock(holdout=False)
        with patch(
            "app.api.v1.training.gabarito_handlers._get_repo", return_value=repo
        ):
            resp = client.put(
                f"/api/training/gabarito/frames/{FRAME_ID}",
                json={"verdicts": {"5": "sim"}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 404
