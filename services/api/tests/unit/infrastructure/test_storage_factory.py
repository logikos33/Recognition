"""
Tests: get_storage() não pode degradar em silêncio pra LocalStorage, e
ensure_storage_ready() mata o PROCESSO (SystemExit(78)) quando a config é
insegura demais pra seguir vivo.

Bug original (auditoria da cadeia frame→R2→anotação): com qualquer credencial
R2 faltando, a factory caía em LocalStorage sem um log sequer. Num container
Railway isso grava em disco EFÊMERO — o endpoint devolve 201, o edge acha que
funcionou, e as imagens somem no próximo deploy. Como a única evidência era
uma linha em `training_frames` (que continua existindo), a perda só apareceria
muito depois, na hora de treinar.

Mutirão 2.1 (D-03) foi além do "erro em vez de silêncio": inverteu o default
do modo efêmero (agora exige ALLOW_EPHEMERAL_STORAGE=1 explícito, proibido em
produção via RAILWAY_ENVIRONMENT_NAME) e separou DUAS responsabilidades:

  - `get_storage()`      -> levanta `StorageError` (Exception normal). Roda
    em 11+ call sites de request/task (ex.: GET /api/v1/storage/health),
    quase todos com `except Exception` esperando isso — nunca pode matar o
    worker inteiro por causa de 1 request.
  - `ensure_storage_ready()` -> chamado 1x no BOOT (app.create_app e no boot
    do worker Celery), converte StorageError em `SystemExit(78)` e ainda
    roda um preflight de conectividade real (head_bucket) quando resolveu R2.

`bucket` fica fora da conta de propósito: tem default não-vazio em
`resolve_r2_credentials`, então nunca distingue configurado de não-configurado.
"""
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import StorageError
from app.infrastructure.storage.local_storage import (
    LocalStorage,
    ensure_storage_ready,
    get_storage,
)

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


@pytest.fixture(autouse=True)
def _clean_ephemeral_env(monkeypatch):
    """Toda env de decisão parte de um estado limpo — cada teste seta só o
    que precisa. Sem isso, o ambiente real do dev/CI vazaria pro teste."""
    monkeypatch.delenv("ALLOW_EPHEMERAL_STORAGE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)


# ---------------------------------------------------------------------------
# get_storage() — decisão de configuração (nunca SystemExit, sempre StorageError)
# ---------------------------------------------------------------------------


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


def test_no_credentials_without_ephemeral_flag_fails_loud_anywhere(monkeypatch):
    """Default invertido (D-03): sem R2 e sem ALLOW_EPHEMERAL_STORAGE=1,
    erra em QUALQUER ambiente — inclusive fora do Railway. Antes só errava
    dentro do Railway; dev local caía em LocalStorage sem opt-in nenhum."""
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )

    with pytest.raises(StorageError) as exc:
        get_storage("tenant-1")

    msg = str(exc.value)
    assert "R2_ENDPOINT" in msg
    assert "R2_KEY" in msg
    assert "R2_SECRET" in msg
    assert "ALLOW_EPHEMERAL_STORAGE" in msg


def test_no_credentials_with_ephemeral_flag_non_production_uses_local_with_warning(
    monkeypatch, caplog
):
    """ALLOW_EPHEMERAL_STORAGE=1 explícito fora de produção -> LocalStorage,
    mas com aviso estruturado (degraded_config=true) a cada boot/chamada."""
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "Desenvolvimento")

    with caplog.at_level("WARNING"):
        storage = get_storage("tenant-1")

    assert isinstance(storage, LocalStorage)
    assert any(
        "storage_ephemeral_allowed" in r.message and "degraded_config=true" in r.message
        for r in caplog.records
    )


def test_ephemeral_flag_in_production_fails_loud(monkeypatch):
    """ALLOW_EPHEMERAL_STORAGE=1 é PROIBIDO em produção — não importa o
    opt-in, produção nunca pode gravar em disco efêmero."""
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")

    with pytest.raises(StorageError) as exc:
        get_storage("tenant-1")

    msg = str(exc.value)
    assert "produção" in msg or "production" in msg


# ---------------------------------------------------------------------------
# ensure_storage_ready() — preflight de BOOT (converte StorageError em
# SystemExit(78); cenários (a)-(e) do mutirão 2.1)
# ---------------------------------------------------------------------------


def test_a_sem_r2_e_sem_ephemeral_exit_78_com_nomes_das_envs(monkeypatch, caplog):
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )

    with caplog.at_level("CRITICAL"), pytest.raises(SystemExit) as exc_info:
        ensure_storage_ready()

    assert exc_info.value.code == 78
    log_text = "\n".join(r.message for r in caplog.records)
    assert "R2_ENDPOINT" in log_text
    assert "R2_KEY" in log_text
    assert "R2_SECRET" in log_text


def test_b_sem_r2_ephemeral_1_nao_producao_retorna_local_com_warning(monkeypatch, caplog):
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "Desenvolvimento")

    with caplog.at_level("WARNING"):
        storage = ensure_storage_ready()

    assert isinstance(storage, LocalStorage)
    assert any("degraded_config=true" in r.message for r in caplog.records)


def test_c_ephemeral_1_em_producao_exit_78(monkeypatch):
    monkeypatch.setattr(
        _PATCH_CREDS,
        lambda *a, **k: _creds(endpoint="", access_key="", secret_key=""),
    )
    monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")

    with pytest.raises(SystemExit) as exc_info:
        ensure_storage_ready()

    assert exc_info.value.code == 78


def test_d_r2_configurado_retorna_r2storage_sem_warning(monkeypatch, caplog):
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds())
    monkeypatch.setattr(
        "app.infrastructure.storage.r2_storage.R2Storage.__init__",
        lambda self, **kw: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.storage.r2_storage.R2Storage.check_connectivity",
        lambda self, **kw: None,
    )
    from app.infrastructure.storage.r2_storage import R2Storage

    with caplog.at_level("WARNING"):
        storage = ensure_storage_ready()

    assert isinstance(storage, R2Storage)
    assert not any("degraded_config" in r.message for r in caplog.records)


def test_e_preflight_head_bucket_falhando_exit_78(monkeypatch):
    """head_bucket falhando (credencial expirada / bucket errado) nas N
    tentativas do preflight -> SystemExit(78), mesmo com R2 "configurado"."""
    monkeypatch.setattr(_PATCH_CREDS, lambda *a, **k: _creds())
    monkeypatch.setattr(
        "app.infrastructure.storage.r2_storage.R2Storage._configure_cors",
        lambda self: None,
    )
    mock_client = MagicMock()
    mock_client.head_bucket.side_effect = Exception("NoSuchBucket")
    monkeypatch.setattr(
        "app.infrastructure.storage.r2_storage.boto3.client",
        lambda *a, **k: mock_client,
    )
    monkeypatch.setattr(
        "app.infrastructure.storage.local_storage.time.sleep", lambda *_: None
    )

    with pytest.raises(SystemExit) as exc_info:
        ensure_storage_ready()

    assert exc_info.value.code == 78
    assert mock_client.head_bucket.call_count == 3  # _PREFLIGHT_ATTEMPTS
