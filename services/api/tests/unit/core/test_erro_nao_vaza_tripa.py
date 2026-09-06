"""
Issues #799/#800 — a resposta de erro que chega ao cliente não pode carregar
SQL cru, o nome interno do schema do tenant, traceback ou string de conexão.

MEDIDO no DEV, numa janela de deploy (a develop autodeploya, e todo deploy é
uma janela de 500/502): qualquer uma das 8 telas do EPI imprimia na tela o
SELECT que falhou e o nome do schema `rvb_isolantes`, além de um
`503 connection pool exhausted` em inglês.

Os testes CRUZAM a fronteira HTTP de propósito: o que importa não é o que a
função devolve, é o que sai no corpo da resposta — e a maior parte das rotas
responde erro por `responses.error(...)`, sem nunca passar por um errorhandler.

PROVA POR MUTAÇÃO (reintroduzindo o defeito):
  - apagando o bloco `if scrubbed:` de `scrub_error_body` (middleware.py), ou
  - trocando `sanitize_client_message` por `return message` (exceptions.py),
  os testes de vazamento ficam VERMELHOS. Rodado antes de commitar.
"""
import logging
import re

import pytest
from flask import Flask, Response, jsonify

from app.core.exceptions import (
    AuthorizationError,
    DatabaseError,
    ValidationError,
    sanitize_client_message,
)
from app.core.middleware import register_error_handlers
from app.core.responses import error

# Tripa que nunca pode aparecer no corpo de uma resposta.
PROIBIDO = re.compile(
    r"select\s|insert\s+into|update\s+\w+\s+set|delete\s+from|relation\s+\"|"
    r"column\s+\"|psycopg|traceback|connection\s+pool|search_path|"
    r"postgres(?:ql)?://|rvb_isolantes",
    re.IGNORECASE,
)

# Textos reais colhidos no DEV.
SQL_CRU = (
    'ERRO: relation "rvb_isolantes.alerts" does not exist\n'
    "LINE 1: SELECT id, camera_id FROM rvb_isolantes.alerts WHERE tenant_id = %s"
)
POOL_CRU = "psycopg2.OperationalError: connection pool exhausted"
CONNSTR_CRU = (
    "could not connect to server: postgresql://recognition:s3nh4@db.internal:5432/rec"
)


@pytest.fixture
def app_com_rotas():
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_error_handlers(app)

    @app.route("/excecao-de-dominio")
    def excecao_de_dominio():
        # O caminho por errorhandler: repository levanta DatabaseError com o
        # texto do psycopg2 dentro.
        raise DatabaseError(SQL_CRU)

    @app.route("/erro-direto")
    def erro_direto():
        # O caminho SEM errorhandler — `return error(...)` na rota. É por aqui
        # que a maior parte do backend responde, e é o que os handlers não
        # cobriam.
        return error(f"Erro ao ler progresso: {POOL_CRU}", 503)

    @app.route("/erro-schema")
    def erro_schema():
        raise AuthorizationError("Schema inválido: rvb_isolantes")

    @app.route("/erro-connstr")
    def erro_connstr():
        return error(CONNSTR_CRU, 500)

    @app.route("/erro-jwt")
    def erro_jwt():
        # flask-jwt-extended responde no campo "msg", não "error".
        return jsonify({"msg": SQL_CRU}), 422

    @app.route("/erro-de-gente")
    def erro_de_gente():
        raise ValidationError("Arquivo excede o limite de 25MB")

    @app.route("/crash")
    def crash():
        raise RuntimeError(SQL_CRU)

    @app.route("/streaming")
    def streaming():
        # HLS e afins respondem em passthrough: o scrubber não pode encostar
        # (ler o corpo aqui consumiria o gerador).
        res = Response((c for c in [b"segmento"]), status=503)
        res.direct_passthrough = True
        return res

    return app


@pytest.fixture
def client(app_com_rotas):
    return app_com_rotas.test_client()


class TestNadaDeTripaNaResposta:
    @pytest.mark.parametrize(
        "rota",
        ["/excecao-de-dominio", "/erro-direto", "/erro-schema", "/erro-connstr", "/crash"],
    )
    def test_corpo_sem_padrao_proibido(self, client, rota):
        res = client.get(rota)
        corpo = res.get_data(as_text=True)
        achado = PROIBIDO.search(corpo)
        assert achado is None, f"{rota} vazou {achado.group(0)!r} → {corpo}"

    def test_campo_msg_do_jwt_tambem_e_raspado(self, client):
        res = client.get("/erro-jwt")
        assert PROIBIDO.search(res.get_json()["msg"]) is None

    def test_nao_engole_o_erro(self, client):
        """O usuário PRECISA saber que falhou — só não precisa saber SELECT nenhum."""
        res = client.get("/erro-direto")
        assert res.status_code == 503
        corpo = res.get_json()
        assert corpo["success"] is False
        assert corpo["error"], "resposta de erro sem mensagem = usuário sem saber o que houve"

    def test_mensagem_sem_numero_de_http(self, client):
        for rota in ("/excecao-de-dominio", "/erro-direto", "/erro-connstr", "/crash"):
            msg = client.get(rota).get_json()["error"]
            assert not re.search(r"\b[45]\d\d\b", msg), f"{rota}: número de HTTP na tela → {msg}"

    def test_mensagem_de_gente_passa_intacta(self, client):
        """A guarda é cirúrgica: não pode transformar mensagem boa em genérica."""
        res = client.get("/erro-de-gente")
        assert res.get_json()["error"] == "Arquivo excede o limite de 25MB"
        assert res.status_code == 400

    def test_detalhe_tecnico_vai_pro_log(self, client, caplog):
        """O time precisa do SQL — no log, não na tela."""
        with caplog.at_level(logging.WARNING, logger="app.core.middleware"):
            client.get("/erro-direto")
        assert any(
            "error_body_scrubbed" in r.message and "connection pool exhausted" in r.getMessage()
            for r in caplog.records
        ), "o detalhe sumiu da tela E do log — isso é engolir o erro"

    def test_log_nao_carrega_senha_da_connection_string(self, client, caplog):
        """Log vaza pra todo lado (Railway, print em ticket) — senha nunca vai junto."""
        with caplog.at_level(logging.WARNING, logger="app.core.middleware"):
            client.get("/erro-connstr")
        linhas = [r.getMessage() for r in caplog.records if "error_body_scrubbed" in r.message]
        assert linhas, "nada foi raspado — o teste não está medindo o que acha"
        assert not any("s3nh4" in linha for linha in linhas)

    def test_streaming_passthrough_intacto(self, client):
        res = client.get("/streaming")
        assert res.status_code == 503
        assert res.get_data() == b"segmento"


class TestSanitizador:
    @pytest.mark.parametrize(
        "cru",
        [
            SQL_CRU,
            POOL_CRU,
            CONNSTR_CRU,
            "Schema inválido: rvb_isolantes",
            "set_search_path failed",
            'duplicate key value violates unique constraint "training_jobs_pkey"',
            'Traceback (most recent call last):\n  File "/app/app/api/v1/epi/routes.py", line 42',
            'column "polaridade" of relation "classes" does not exist',
            "INSERT INTO rvb_isolantes.frames (id) VALUES (%s)",
        ],
    )
    def test_troca_mensagem_com_tripa(self, cru):
        assert sanitize_client_message(cru, 500) != cru
        assert PROIBIDO.search(sanitize_client_message(cru, 500)) is None

    @pytest.mark.parametrize(
        "boa",
        [
            "Câmera não encontrada (abc-123)",
            "Credenciais inválidas",
            "Muitas requisições. Tente novamente mais tarde.",
            "Maria já avaliou este alerta há 2 minutos",
            "Arquivo excede o limite de 25MB",
            "Mínimo 10 frames anotados necessários. Atual: 4",
            "Host não permitido (endereço reservado): 10.0.0.1",
            "Módulo inválido. Use: ['epi', 'qualidade']",
            "camera_ids inválido (esperado UUID): 'xyz'",
        ],
    )
    def test_nao_mexe_em_mensagem_de_gente(self, boa):
        assert sanitize_client_message(boa, 400) == boa
