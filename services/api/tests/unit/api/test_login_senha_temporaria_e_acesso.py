"""
Tests: o /login cobra a senha temporária e REGISTRA o acesso (issue #764).

Dois defeitos medidos no DEV em 05/09, os dois na mesma rota:

 1. `force_password_reset` era ESCRITA por três caminhos do admin (criação de
    tenant, POST /admin/users e a rota dedicada), aparecia no painel — e
    nenhum caminho a COBRAVA. A senha temporária entregue no papel virava a
    senha definitiva da pessoa.

 2. `last_login_at` e `login_count` eram SERVIDAS por GET /admin/users e
    nunca escritas: 14/14 usuários do DEV em NULL/0 depois de logins reais.
    Numa tela cujo rodapé diz "ACESSO REGISTRADO NA AUDITORIA", "último
    acesso: nunca" para quem acabou de entrar não é um dado faltando — é um
    dado errado.

Todo teste aqui cruza a fronteira HTTP (client.post) e observa o EFEITO:
token emitido ou não, e `register_login` chamado ou não. Checar só o status
deixaria passar exatamente o defeito 2, que devolvia 200 sem gravar nada.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
AUTH_SVC_PATH = "app.api.v1.auth.routes._get_auth_service"
REPO_PATH = "app.api.v1.auth.routes._get_user_repository"


def _user(**overrides):
    base = {
        "id": USER_ID,
        "email": "tst@rvb.com.br",
        "name": "TST RVB",
        "tenant_id": TENANT_ID,
        "tenant_schema": "tenant_rvb",
        "role": "operator",
        "modules_enabled": ["epi"],
        "is_active": True,
        "force_password_reset": False,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def ambiente():
    """AuthService e UserRepository mockados — nenhum banco é tocado."""
    svc = MagicMock()
    svc.login.return_value = _user()
    repo = MagicMock()
    repo.register_login.return_value = {
        "id": USER_ID, "last_login_at": "2026-09-07T08:00:00Z", "login_count": 1,
    }
    repo.reset_password.return_value = {"id": USER_ID, "email": "tst@rvb.com.br"}
    repo.get_by_id_with_tenant.return_value = _user()
    with patch(AUTH_SVC_PATH, return_value=svc), patch(REPO_PATH, return_value=repo):
        yield svc, repo


def _login(client, senha="senha-temporaria"):
    return client.post(
        "/api/auth/login", json={"email": "tst@rvb.com.br", "password": senha},
    )


class TestSenhaTemporariaEhCobrada:

    def test_conta_com_troca_pendente_nao_recebe_token(self, client, ambiente):
        """FALHA-ANTES: 200 com token — a senha temporária nunca expirava."""
        svc, repo = ambiente
        svc.login.return_value = _user(force_password_reset=True)

        resp = _login(client)

        assert resp.status_code == 403, resp.get_data(as_text=True)[:200]
        corpo = resp.get_json()
        assert corpo["success"] is False
        assert corpo["error_code"] == "password_change_required"
        # Nem token, nem acesso contabilizado: não houve acesso.
        assert "data" not in corpo or "token" not in corpo.get("data", {})
        repo.register_login.assert_not_called()

    def test_a_mensagem_diz_o_que_fazer(self, client, ambiente):
        """Erro que não aponta a saída trava a pessoa na tela de login."""
        svc, _repo = ambiente
        svc.login.return_value = _user(force_password_reset=True)
        erro = _login(client).get_json()["error"]
        assert "change-password" in erro

    def test_senha_errada_continua_401_mesmo_com_troca_pendente(self, client, ambiente):
        """A flag não pode virar oráculo: sem a senha certa, nada é revelado."""
        from app.core.exceptions import AuthenticationError

        svc, _repo = ambiente
        svc.login.side_effect = AuthenticationError("Credenciais inválidas")
        assert _login(client, "errada").status_code == 401

    def test_conta_normal_entra(self, client, ambiente):
        """Contraprova: sem a flag, o login segue inteiro (não quebrei o login)."""
        assert "token" in _login(client).get_json()["data"]

    def test_a_flag_interna_nao_vaza_na_resposta(self, client, ambiente):
        assert "force_password_reset" not in _login(client).get_json()["data"]["user"]

    def test_refresh_tambem_cobra(self, app, client, ambiente):
        """Sem isto, bastava renovar um token vivo para ignorar a exigência
        por mais 24h — o guard teria um bypass documentado."""
        from flask_jwt_extended import create_access_token

        _svc, repo = ambiente
        repo.get_by_id_with_tenant.return_value = _user(force_password_reset=True)
        with app.app_context():
            token = create_access_token(
                identity=USER_ID,
                additional_claims={
                    "tenant_id": TENANT_ID, "tenant_schema": "tenant_rvb",
                    "role": "operator", "modules": ["epi"],
                },
            )
        resp = client.post(
            "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error_code"] == "password_change_required"


class TestTrocaDeSenhaPelaPropriaPessoa:
    """A saída do 403. Não exige token (quem tem senha temporária não
    consegue um) nem provedor de e-mail (o DEV não tem: /forgot-password
    responde 503)."""

    def _trocar(self, client, **body):
        corpo = {
            "email": "tst@rvb.com.br",
            "current_password": "senha-temporaria",
            "new_password": "senha-nova-1",
        }
        corpo.update(body)
        return client.post("/api/auth/change-password", json=corpo)

    def test_troca_limpa_a_exigencia_e_grava_hash_novo(self, client, ambiente):
        svc, repo = ambiente
        svc.login.return_value = _user(force_password_reset=True)

        resp = self._trocar(client)

        assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
        repo.reset_password.assert_called_once()
        user_id, hash_novo = repo.reset_password.call_args[0]
        assert user_id == USER_ID
        # bcrypt, nunca a senha em claro
        assert hash_novo.startswith("$2")
        assert "senha-nova-1" not in hash_novo

    def test_senha_atual_errada_nao_troca_nada(self, client, ambiente):
        from app.core.exceptions import AuthenticationError

        svc, repo = ambiente
        svc.login.side_effect = AuthenticationError("Credenciais inválidas")
        assert self._trocar(client).status_code == 401
        repo.reset_password.assert_not_called()

    def test_repetir_a_senha_temporaria_nao_conta_como_troca(self, client, ambiente):
        """Senão a exigência viraria um clique e a senha do papel continuaria
        valendo — com a flag limpa, que é pior: ninguém mais cobra."""
        _svc, repo = ambiente
        resp = self._trocar(client, new_password="senha-temporaria")
        assert resp.status_code == 400
        repo.reset_password.assert_not_called()

    def test_senha_curta_recusada(self, client, ambiente):
        _svc, repo = ambiente
        assert self._trocar(client, new_password="123").status_code == 400
        repo.reset_password.assert_not_called()

    def test_depois_da_troca_a_pessoa_entra(self, client, ambiente):
        """O ciclo fecha: 403 → troca → login com token."""
        svc, _repo = ambiente
        svc.login.return_value = _user(force_password_reset=True)
        assert _login(client).status_code == 403
        assert self._trocar(client).status_code == 200
        # o banco agora devolve a conta sem a flag
        svc.login.return_value = _user(force_password_reset=False)
        assert "token" in _login(client, "senha-nova-1").get_json()["data"]


class TestOAcessoFicaRegistrado:

    def test_login_grava_o_acesso(self, client, ambiente):
        """FALHA-ANTES: nenhum UPDATE — 14/14 contas do DEV em NULL/0."""
        _svc, repo = ambiente
        assert _login(client).status_code == 200
        repo.register_login.assert_called_once()
        assert repo.register_login.call_args[0][0] == USER_ID

    def test_segundo_login_registra_de_novo(self, client, ambiente):
        """login_count é CONTADOR: se só o primeiro acesso gravasse, a coluna
        mentiria a partir do segundo dia."""
        _svc, repo = ambiente
        assert _login(client).status_code == 200
        assert _login(client).status_code == 200
        assert repo.register_login.call_count == 2

    def test_o_update_incrementa_em_vez_de_sobrescrever(self):
        """O contador tem de somar sobre o valor atual, tolerando NULL das
        linhas anteriores à migration 029."""
        from app.infrastructure.database.repositories.user_repository import (
            UserRepository,
        )

        repo = UserRepository(MagicMock())
        with patch.object(UserRepository, "_execute_mutation") as exec_mut:
            repo.register_login(USER_ID, "10.0.0.9")
        sql = " ".join(exec_mut.call_args[0][0].split())
        assert "login_count = COALESCE(login_count, 0) + 1" in sql
        assert "last_login_at = NOW()" in sql
        assert exec_mut.call_args[0][1] == ("10.0.0.9", USER_ID)

    def test_falha_do_registro_nao_derruba_o_login(self, client, ambiente):
        """Bookkeeping é best-effort: ninguém fica sem entrar porque o UPDATE
        de auditoria falhou."""
        _svc, repo = ambiente
        repo.register_login.side_effect = RuntimeError("banco fora")
        assert _login(client).status_code == 200
