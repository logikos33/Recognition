"""O /livez precisa dizer QUAL commit está servindo.

Sem isso não há como provar o que está no ar, e um `railway up` que sobrescreve
um deploy por git passa despercebido — aconteceu duas vezes numa semana.
"""
import importlib
import os


def _reload_routes():
    import app.api.v1.health.routes as routes
    return importlib.reload(routes)


def test_commit_vem_da_env_do_railway(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "b769ede5b737477dabedc58902930e2f54c7b095")
    assert _reload_routes()._COMMIT_SHA.startswith("b769ede5")


def test_sem_env_devolve_unknown_explicito(monkeypatch):
    # Deploy por upload local não carrega proveniência: "unknown" é o SINAL
    # disso, não um degradado silencioso.
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    assert _reload_routes()._COMMIT_SHA == "unknown"


def test_env_vazia_tambem_vira_unknown(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "   ")
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    assert _reload_routes()._COMMIT_SHA == "unknown"


def test_livez_expoe_o_commit_sem_autenticacao(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "deadbeef")
    routes = _reload_routes()
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(routes.health_bp)
    resp = app.test_client().get("/livez")  # sem header Authorization
    assert resp.status_code == 200
    assert resp.get_json()["commit"] == "deadbeef"


def teardown_module(_m):
    os.environ.pop("RAILWAY_GIT_COMMIT_SHA", None)
    _reload_routes()
