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


# ---------------------------------------------------------------------------
# 05/09 — DECLARADO ≠ PROVADO
#
# Os testes acima provam que o `commit` sai da env var. Nenhum deles prova que
# a env var descreve o CÓDIGO SERVIDO — e não descreve: o CI grava
# `GIT_COMMIT_SHA` ANTES de subir, então basta o upload falhar, subir outra
# árvore, ou alguém dar um `railway up` de fora do CI (que não toca a variável)
# para o `/livez` afirmar, com confiança, um SHA que não está rodando.
#
# `tree_digest` é o campo que NÃO depende de ninguém: é derivado dos bytes que
# o processo tem em disco, no formato de blob do git — logo, conferível de fora
# com `git ls-tree` sem checkout. Estes testes provam que os DOIS LADOS
# (processo e repositório) calculam o mesmo número, e que o digest MUDA quando
# o código muda. Sem a segunda parte, o campo poderia ser uma constante
# decorativa e ninguém notaria.
# ---------------------------------------------------------------------------
import importlib.util
import subprocess
from pathlib import Path

import pytest

_RAIZ_REPO = Path(__file__).resolve().parents[5]
_spec = importlib.util.spec_from_file_location(
    "checa_prov", _RAIZ_REPO / "scripts" / "checa_proveniencia.py"
)
checa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checa)


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo_sintetico(tmp_path):
    """Um repositório git de verdade, minúsculo, com um 'pacote servido'."""
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "sub" / "b.py").write_text("y = 2\n")
    (pkg / "sub" / "leia.md").write_text("não é .py — fica de fora\n")
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "t@t", cwd=tmp_path)
    _git("config", "user.name", "t", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("commit", "-qm", "inicial", cwd=tmp_path)
    return tmp_path, pkg


def test_os_dois_lados_calculam_o_mesmo_digest(repo_sintetico, monkeypatch):
    """O processo e o repositório precisam chegar ao MESMO número.

    Se divergirem, o vigia nunca consegue provar nada — e cai para "declarado",
    que é o buraco que este PR fecha.
    """
    raiz, pkg = repo_sintetico
    monkeypatch.chdir(raiz)
    routes = _reload_routes()

    do_processo = routes._digest_da_arvore_servida(str(pkg))
    do_repositorio = checa.digest_da_arvore("HEAD", pacote="pkg")

    assert do_processo is not None
    assert do_processo == do_repositorio


def test_mudar_uma_linha_muda_o_digest(repo_sintetico, monkeypatch):
    """PROVA POR MUTAÇÃO: sem isto, o campo poderia ser constante e passar.

    Reintroduzir o defeito = servir código diferente do commitado. O digest do
    processo tem de descolar do digest do repositório.
    """
    raiz, pkg = repo_sintetico
    monkeypatch.chdir(raiz)
    routes = _reload_routes()

    antes = routes._digest_da_arvore_servida(str(pkg))
    (pkg / "a.py").write_text("x = 999   # árvore servida != árvore commitada\n")
    depois = routes._digest_da_arvore_servida(str(pkg))

    assert antes != depois
    assert depois != checa.digest_da_arvore("HEAD", pacote="pkg")


def test_arquivo_novo_nao_commitado_muda_o_digest(repo_sintetico, monkeypatch):
    """Upload de árvore diferente costuma ser 'sobrou/faltou arquivo', não byte."""
    raiz, pkg = repo_sintetico
    monkeypatch.chdir(raiz)
    routes = _reload_routes()

    antes = routes._digest_da_arvore_servida(str(pkg))
    (pkg / "sub" / "c.py").write_text("z = 3\n")
    assert routes._digest_da_arvore_servida(str(pkg)) != antes


def test_digest_nunca_derruba_o_livez(monkeypatch):
    """`/livez` é probe de liveness: se ele não sobe, o Railway entra em loop
    de restart. Pasta inexistente devolve None, não exceção."""
    routes = _reload_routes()
    assert routes._digest_da_arvore_servida("/caminho/que/nao/existe") is None


def test_livez_devolve_tree_digest_e_a_fonte_da_declaracao(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GIT_COMMIT_SHA", "cafebabe")
    routes = _reload_routes()
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(routes.health_bp)

    corpo = app.test_client().get("/livez").get_json()

    assert corpo["commit"] == "cafebabe"
    # QUEM declarou muda o peso: `GIT_COMMIT_SHA` é variável que alguém
    # escreveu e que sobrevive a um deploy que subiu outra coisa.
    assert corpo["commit_source"] == "GIT_COMMIT_SHA"
    assert corpo["tree_digest"] == routes._TREE_DIGEST
    assert len(corpo["tree_digest"]) == 16


def test_fonte_da_declaracao_distingue_plataforma_de_variavel(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    monkeypatch.setenv("GIT_COMMIT_SHA", "outro")
    # A da plataforma ganha: ela descreve o artefato do deploy por git.
    assert _reload_routes()._COMMIT_SOURCE == "RAILWAY_GIT_COMMIT_SHA"

    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    assert _reload_routes()._COMMIT_SOURCE is None


def test_o_pacote_servido_e_a_arvore_do_repositorio_batem_de_verdade():
    """O caminho apontado por `_PACOTE_SERVIDO` casa com `PACOTE_SERVIDO` do
    vigia NESTE repositório — não só num repo sintético.

    Pula com árvore suja porque aí os dois lados descrevem estados diferentes
    de propósito (é exatamente o que o digest existe para detectar). No CI o
    checkout é limpo e o teste roda de verdade.
    """
    sujo = subprocess.run(
        ["git", "status", "--porcelain", "--", checa.PACOTE_SERVIDO],
        cwd=_RAIZ_REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    if sujo:
        pytest.skip(f"árvore suja em {checa.PACOTE_SERVIDO} — comparação sem sentido")

    routes = _reload_routes()
    esperado = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_RAIZ_REPO,
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    import os as _os
    cwd = _os.getcwd()
    try:
        _os.chdir(_RAIZ_REPO)
        assert routes._TREE_DIGEST == checa.digest_da_arvore(esperado)
    finally:
        _os.chdir(cwd)
