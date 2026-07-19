"""
Segurança — validação de segredos em ProductionConfig realmente executa (achado P1).

Bug: a validação vivia em `ProductionConfig.__init_subclass__`, um hook que só
dispara quando uma classe HERDA de ProductionConfig. Como nada herda dela —
`get_config()` instancia `ProductionConfig` diretamente — o hook nunca rodava.
Um deploy de produção com `JWT_SECRET_KEY` ausente ou fraco (<32 chars) subia
normalmente, sem erro.

Fix: validação movida para `__init__`, que roda em toda instanciação.

Testes falha-antes/passa-depois:
  ANTES do fix: nenhum destes três casos levantava exceção.
  DEPOIS do fix: os três levantam ValueError; um config válido não levanta.
"""
import importlib

import pytest


def _reload_config(monkeypatch, **env):
    """Seta env vars e recarrega app.config — classe lê os.environ no import."""
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import app.config as config_module
    importlib.reload(config_module)
    return config_module


def test_missing_jwt_secret_key_raises(monkeypatch):
    config_module = _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY=None)
    try:
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            config_module.get_config("production")
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)


def test_short_jwt_secret_key_raises(monkeypatch):
    config_module = _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="short")
    try:
        with pytest.raises(ValueError, match="mínimo 32 caracteres"):
            config_module.get_config("production")
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)


def test_missing_secret_key_raises(monkeypatch):
    config_module = _reload_config(monkeypatch, SECRET_KEY=None, JWT_SECRET_KEY="y" * 40)
    try:
        with pytest.raises(ValueError, match="SECRET_KEY"):
            config_module.get_config("production")
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)


def test_valid_production_secrets_do_not_raise(monkeypatch):
    config_module = _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)
    cfg = config_module.get_config("production")
    assert cfg.JWT_SECRET_KEY == "y" * 40


def test_development_config_unaffected(monkeypatch):
    """Dev/testing continuam com defaults fracos — validação é só de produção."""
    config_module = _reload_config(monkeypatch, JWT_SECRET_KEY=None)
    try:
        cfg = config_module.get_config("development")
        assert cfg.JWT_SECRET_KEY == "dev-jwt-change-in-prod"
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)

