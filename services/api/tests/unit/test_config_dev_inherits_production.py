"""
Config — DevelopmentConfig herda de ProductionConfig (passo 2 de 3 do PR).

Antes: DevelopmentConfig e ProductionConfig herdavam separadamente de Config,
cada uma repetindo (ou podendo silenciosamente esquecer de repetir) os ~50
campos comuns. Agora DevelopmentConfig(ProductionConfig) — alta fidelidade
por construção: qualquer campo que não seja uma das 4 divergências
documentadas em app/config.py é, por herança, idêntico entre os dois
ambientes.

Este arquivo cobre especificamente a herança e as 4 divergências. A
validação de segurança de ProductionConfig (ValueError sem secret / secret
curto) já é coberta por test_config_production_validation.py — não
duplicada aqui, só reforçada via issubclass.
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


def test_development_config_is_subclass_of_production_config(monkeypatch):
    """A relação de herança em si é o que garante alta fidelidade — se isto
    quebrar, os ~50 campos comuns voltam a poder divergir em silêncio."""
    config_module = _reload_config(monkeypatch)
    assert issubclass(config_module.DevelopmentConfig, config_module.ProductionConfig)


def test_development_config_boots_without_any_secret_env_vars(monkeypatch):
    """(a) DevelopmentConfig precisa bootar mesmo sem SECRET_KEY/JWT_SECRET_KEY
    no ambiente — são as divergências 2 e 3, defaults fracos só de dev."""
    config_module = _reload_config(
        monkeypatch, SECRET_KEY=None, JWT_SECRET_KEY=None
    )
    try:
        cfg = config_module.get_config("development")
        assert cfg.SECRET_KEY == "dev-only-change-in-prod"
        assert cfg.JWT_SECRET_KEY == "dev-jwt-change-in-prod"
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)


def test_production_config_still_requires_secrets(monkeypatch):
    """(b) Herança não pode enfraquecer a validação de produção — continua
    falhando sem secret e continua exigindo JWT_SECRET_KEY >= 32 chars."""
    config_module = _reload_config(
        monkeypatch, SECRET_KEY=None, JWT_SECRET_KEY=None
    )
    try:
        with pytest.raises(ValueError, match="SECRET_KEY"):
            config_module.get_config("production")

        config_module = _reload_config(
            monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="short"
        )
        with pytest.raises(ValueError, match="mínimo 32 caracteres"):
            config_module.get_config("production")
    finally:
        _reload_config(monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40)


def test_debug_diverges_dev_vs_prod(monkeypatch):
    """(c) DEBUG é a divergência 1 — False em produção, True em dev."""
    config_module = _reload_config(
        monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40
    )
    assert config_module.get_config("production").DEBUG is False
    assert config_module.get_config("development").DEBUG is True


def test_staging_maps_to_production_config_with_debug_false(monkeypatch):
    """Seleção de ambiente (passo 1 do PR) não pode ter sido afetada pela
    mudança de herança — staging continua sendo ProductionConfig puro."""
    config_module = _reload_config(
        monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40
    )
    cfg = config_module.get_config("staging")
    assert type(cfg) is config_module.ProductionConfig
    assert cfg.DEBUG is False


@pytest.mark.parametrize(
    "field",
    [
        "DB_POOL_MIN",
        "DB_POOL_MAX",
        "JWT_ALGORITHM",
        "HLS_SEGMENT_TIME",
        "CELERY_TASK_MAX_RETRIES",
    ],
)
def test_inherited_base_fields_are_identical_dev_vs_prod(monkeypatch, field):
    """(d) Fora das 4 divergências documentadas, DevelopmentConfig e
    ProductionConfig devem expor exatamente o mesmo valor — são o mesmo
    campo da base Config, herdado, não redefinido."""
    config_module = _reload_config(
        monkeypatch, SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40
    )
    dev = config_module.get_config("development")
    prod = config_module.get_config("production")
    assert getattr(dev, field) == getattr(prod, field)
