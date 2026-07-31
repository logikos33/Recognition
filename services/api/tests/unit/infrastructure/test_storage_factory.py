"""
Tests: get_storage() não pode degradar em silêncio pra LocalStorage.

Bug real (auditoria da cadeia frame→R2→anotação): com qualquer credencial R2
faltando, a factory caía em LocalStorage sem um log sequer. Num container
Railway isso grava em disco EFÊMERO — o endpoint devolve 201, o edge acha que
funcionou, e as imagens somem no próximo deploy. Como a única evidência era
uma linha em `training_frames` (que continua existindo), a perda só apareceria
muito depois, na hora de treinar.

`bucket` fica fora da conta de propósito: tem default não-vazio em
`resolve_r2_credentials`, então nunca distingue configurado de não-configurado.
"""
import pytest

from app.core.exceptions import StorageError
from app.infrastructure.storage.local_storage import LocalStorage, get_storage

_PATCH_CREDS = "app.domain.services.integration_service.resolve_r2_credentials"

_FULL = {
    "endpoint": "https://acct.r2.cloudflarestorage.com",
    "bucket": "epi-monitor-dev",
    "access_key": "k" * 32,
    "secret_key": "s" * 64,
}


def _creds(**overrides):
    out = dict(_FULL)
    out.update(overrides)
    return out


def test_all_credentials_returns_r2(monkeypatch):
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds())
    monkeypatch.setattr(
        "app.infrastructure.storage.r2_storage.R2Storage.__init__",
        lambda self, **kw: None,
    )
    from app.infrastructure.storage.r2_storage import R2Storage

    assert isinstance(get_storage("tenant-1"), R2Storage)


@pytest.mark.parametrize(
    "missing", ["endpoint", "access_key", "secret_key"]
)
def test_partial_config_fails_loud(monkeypatch, missing):
    """1-2 de 3 presentes = config pela metade -> erro, nunca LocalStorage."""
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds(**{missing: ""}))

    with pytest.raises(StorageError) as exc:
        get_storage("tenant-1")

    msg = str(exc.value)
    assert "METADE" in msg
    assert "efêmero" in msg


def test_partial_config_message_names_missing_var(monkeypatch):
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds(secret_key=""))

    with pytest.raises(StorageError) as exc:
        get_storage("tenant-1")

    assert "R2_SECRET" in str(exc.value)


def test_partial_config_message_never_leaks_secret(monkeypatch):
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds(endpoint=""))

    with pytest.raises(StorageError) as exc:
        get_storage("tenant-1")

    msg = str(exc.value)
    assert "s" * 64 not in msg
    assert "k" * 32 not in msg


def test_no_credentials_on_railway_fails_loud(monkeypatch):
    """Zero credencial DENTRO do Railway também é erro: LocalStorage ali é
    disco efêmero, o pior caso silencioso."""
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "Desenvolvimento")

    with pytest.raises(StorageError, match="Railway"):
        get_storage("tenant-1")


def test_no_credentials_off_railway_uses_local_with_warning(monkeypatch, caplog):
    """Dev local segue funcionando sem config — mas com aviso visível."""
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    with caplog.at_level("WARNING"):
        storage = get_storage("tenant-1")

    assert isinstance(storage, LocalStorage)
    assert any("storage_local_fallback" in r.message for r in caplog.records)
