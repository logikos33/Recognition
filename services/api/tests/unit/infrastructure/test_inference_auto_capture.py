"""
Tests: tasks/inference.py — auto-captura de frames de treino (WS-B3).

Cobre:
- _save_alert chama _auto_capture_frame DEPOIS de salvar o alerta (hook
  único — nunca duplicar em socket_bridge.py::_create_alert_and_verify)
- _auto_capture_enabled / _auto_capture_daily_cap: feature_flags do tenant
  > env de plataforma
- _try_reserve_auto_capture_slot: reserva atômica (INCR+EXPIRE) — dentro do
  teto reserva, acima do teto nega, cap<=0 nunca toca Redis
- _try_acquire_auto_capture_dedup_lock: debounce atômico (SET NX EX) por
  câmera — idempotência POR DETECÇÃO (não só rate-limit por tenant/dia)
- _auto_capture_frame: upload + FrameRepository.create com source=AUTO só
  quando habilitado, dedup adquirido E dentro do teto; nunca propaga exceção
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Mesmo guard de test_inference_model_resolution.py — evita stub de celery_app
# poluído por outro arquivo de teste.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.constants import FrameSource  # noqa: E402
from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_CAMERA_ID = str(uuid4())
_TENANT_ID = "99999999-8888-7777-6666-555555555555"


class TestAutoCaptureFlags:
    def test_enabled_defaults_true_without_tenant_or_flag(self, monkeypatch):
        monkeypatch.delenv("AUTO_CAPTURE_ENABLED", raising=False)
        assert inference_mod._auto_capture_enabled(pool=None, tenant_id=None) is True

    def test_env_can_disable_default(self, monkeypatch):
        monkeypatch.setenv("AUTO_CAPTURE_ENABLED", "false")
        assert inference_mod._auto_capture_enabled(pool=None, tenant_id=None) is False

    def test_tenant_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AUTO_CAPTURE_ENABLED", "true")
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository.TenantSettingsRepository"
        ) as mock_repo_cls:
            mock_repo_cls.return_value.get_feature_flags.return_value = {
                "auto_capture_enabled": False
            }
            result = inference_mod._auto_capture_enabled(pool=MagicMock(), tenant_id=_TENANT_ID)
        assert result is False

    def test_daily_cap_defaults_to_20(self, monkeypatch):
        monkeypatch.delenv("AUTO_CAPTURE_DAILY_CAP", raising=False)
        assert inference_mod._auto_capture_daily_cap(pool=None, tenant_id=None) == 20

    def test_daily_cap_tenant_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AUTO_CAPTURE_DAILY_CAP", "20")
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository.TenantSettingsRepository"
        ) as mock_repo_cls:
            mock_repo_cls.return_value.get_feature_flags.return_value = {
                "auto_capture_daily_cap": 5
            }
            result = inference_mod._auto_capture_daily_cap(pool=MagicMock(), tenant_id=_TENANT_ID)
        assert result == 5

    def test_flag_read_failure_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("AUTO_CAPTURE_ENABLED", "true")
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository.TenantSettingsRepository",
            side_effect=RuntimeError("db down"),
        ):
            result = inference_mod._auto_capture_enabled(pool=MagicMock(), tenant_id=_TENANT_ID)
        assert result is True


class TestReserveAutoCaptureSlot:
    def test_cap_zero_never_touches_redis(self):
        with patch.object(inference_mod, "_get_redis_client") as mock_get_redis:
            result = inference_mod._try_reserve_auto_capture_slot(_CAMERA_ID, cap=0)
        assert result is False
        mock_get_redis.assert_not_called()

    def test_first_reservation_within_cap_succeeds(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            result = inference_mod._try_reserve_auto_capture_slot(_CAMERA_ID, cap=20)
        assert result is True
        mock_redis.expire.assert_called_once()  # TTL setado só na 1a reserva do dia

    def test_expire_not_called_again_after_first_increment(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 5
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            inference_mod._try_reserve_auto_capture_slot(_CAMERA_ID, cap=20)
        mock_redis.expire.assert_not_called()

    def test_exceeding_cap_denies(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 21
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            result = inference_mod._try_reserve_auto_capture_slot(_CAMERA_ID, cap=20)
        assert result is False

    def test_redis_failure_denies_without_raising(self):
        with patch.object(
            inference_mod, "_get_redis_client", side_effect=RuntimeError("redis down")
        ):
            result = inference_mod._try_reserve_auto_capture_slot(_CAMERA_ID, cap=20)
        assert result is False


class TestAutoCaptureDedupLock:
    """Debounce por detecção (SET NX EX) — achado pós-PR-3: o teto diário
    sozinho não impede que UMA violação contínua, amostrada em frames
    consecutivos, gere N capturas até esgotar o teto."""

    def test_first_call_acquires_lock(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            result = inference_mod._try_acquire_auto_capture_dedup_lock(_CAMERA_ID)
        assert result is True

    def test_second_call_while_lock_held_denies(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = None  # NX falha — chave já existe
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            result = inference_mod._try_acquire_auto_capture_dedup_lock(_CAMERA_ID)
        assert result is False

    def test_redis_failure_denies_without_raising(self):
        with patch.object(
            inference_mod, "_get_redis_client", side_effect=RuntimeError("redis down")
        ):
            result = inference_mod._try_acquire_auto_capture_dedup_lock(_CAMERA_ID)
        assert result is False

    def test_lock_key_and_ttl_format(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        with patch.object(inference_mod, "_get_redis_client", return_value=mock_redis):
            inference_mod._try_acquire_auto_capture_dedup_lock(_CAMERA_ID)
        args, kwargs = mock_redis.set.call_args
        assert args[0] == f"epi:autocapture:dedup:{_CAMERA_ID}"
        assert kwargs["nx"] is True
        assert kwargs["ex"] == inference_mod._AUTO_CAPTURE_DEDUP_TTL_SECONDS


class TestAutoCaptureFrame:
    def _run(self, monkeypatch, enabled=True, cap=20, reserved=True, dedup_ok=True):
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: enabled)
        monkeypatch.setattr(
            inference_mod, "_try_acquire_auto_capture_dedup_lock", lambda cam: dedup_ok
        )
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: cap)
        monkeypatch.setattr(
            inference_mod, "_try_reserve_auto_capture_slot", lambda cam, cap: reserved
        )
        mock_storage = MagicMock()
        mock_frame_repo = MagicMock()
        frame = MagicMock()
        frame.shape = (480, 640, 3)

        with patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
        ), patch(
            "app.infrastructure.database.repositories.frame_repository.FrameRepository",
            return_value=mock_frame_repo,
        ):
            inference_mod._auto_capture_frame(
                _CAMERA_ID, _TENANT_ID, "epi", b"jpeg-bytes", frame, 0.42, MagicMock()
            )
        return mock_storage, mock_frame_repo

    def test_disabled_skips_upload_and_db(self, monkeypatch):
        storage, frame_repo = self._run(monkeypatch, enabled=False)
        storage.upload_bytes.assert_not_called()
        frame_repo.create.assert_not_called()

    def test_rate_limited_skips_upload_and_db(self, monkeypatch):
        storage, frame_repo = self._run(monkeypatch, reserved=False)
        storage.upload_bytes.assert_not_called()
        frame_repo.create.assert_not_called()

    def test_dedup_denied_skips_upload_and_db_without_touching_cap(self, monkeypatch):
        """Prova a ordem: dedup roda ANTES do teto diário — uma recaptura da
        mesma violação em andamento não deve nem consultar o teto."""
        cap_check = MagicMock(return_value=True)
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: True)
        monkeypatch.setattr(
            inference_mod, "_try_acquire_auto_capture_dedup_lock", lambda cam: False
        )
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: 20)
        monkeypatch.setattr(inference_mod, "_try_reserve_auto_capture_slot", cap_check)
        mock_storage = MagicMock()
        mock_frame_repo = MagicMock()
        frame = MagicMock()
        frame.shape = (480, 640, 3)

        with patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
        ), patch(
            "app.infrastructure.database.repositories.frame_repository.FrameRepository",
            return_value=mock_frame_repo,
        ):
            inference_mod._auto_capture_frame(
                _CAMERA_ID, _TENANT_ID, "epi", b"jpeg-bytes", frame, 0.42, MagicMock()
            )

        mock_storage.upload_bytes.assert_not_called()
        mock_frame_repo.create.assert_not_called()
        cap_check.assert_not_called()

    def test_enabled_and_reserved_uploads_and_creates_frame(self, monkeypatch):
        storage, frame_repo = self._run(monkeypatch)
        storage.upload_bytes.assert_called_once()
        key, data, content_type = storage.upload_bytes.call_args.args
        assert key.startswith("training-images/")
        assert "/auto/" in key
        assert data == b"jpeg-bytes"
        assert content_type == "image/jpeg"

        frame_repo.create.assert_called_once()
        kwargs = frame_repo.create.call_args.kwargs
        assert kwargs["source"] == FrameSource.AUTO
        assert kwargs["tenant_id"] == _TENANT_ID
        assert kwargs["module_code"] == "epi"
        assert kwargs["model_confidence"] == 0.42
        assert kwargs["width"] == 640
        assert kwargs["height"] == 480
        assert kwargs["video_id"] is None

    def test_never_raises_on_internal_failure(self, monkeypatch):
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: True)
        monkeypatch.setattr(
            inference_mod, "_try_acquire_auto_capture_dedup_lock", lambda cam: True
        )
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: 20)
        monkeypatch.setattr(
            inference_mod,
            "_try_reserve_auto_capture_slot",
            lambda cam, cap: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # não deve levantar
        inference_mod._auto_capture_frame(
            _CAMERA_ID, _TENANT_ID, "epi", b"x", MagicMock(shape=(1, 1, 3)), 0.1, MagicMock()
        )


class _FakeRedisDedup:
    """Double mínimo pra SET NX EX + INCR/EXPIRE — sem servidor real, sem
    mocks parciais. `_auto_capture_frame` usa o mesmo client tanto pro
    dedup lock (SET NX EX) quanto pro teto diário (INCR+EXPIRE), então este
    double cobre os dois. `expire_key_now` simula a expiração do TTL do
    dedup manualmente (sem sleep real no teste)."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def incr(self, key):
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    def expire(self, key, ttl):
        return True

    def expire_key_now(self, key):
        self._store.pop(key, None)


class TestAutoCaptureDedupIntegration:
    """Falha-antes/passa-depois: prova que uma violação contínua (mesma
    câmera, chamadas consecutivas) não recaptura mais de uma vez por janela
    — sem este guard, frame_repo.create.call_count seria 2 na primeira
    asserção abaixo."""

    def _call(self, camera_id, fake_redis, storage, frame_repo):
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        with patch.object(inference_mod, "_get_redis_client", return_value=fake_redis), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=storage
        ), patch(
            "app.infrastructure.database.repositories.frame_repository.FrameRepository",
            return_value=frame_repo,
        ):
            inference_mod._auto_capture_frame(
                camera_id, _TENANT_ID, "epi", b"jpeg-bytes", frame, 0.42, MagicMock()
            )

    def test_second_consecutive_call_same_camera_does_not_recapture(self, monkeypatch):
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: True)
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: 20)
        fake_redis = _FakeRedisDedup()
        storage = MagicMock()
        frame_repo = MagicMock()

        self._call(_CAMERA_ID, fake_redis, storage, frame_repo)
        self._call(_CAMERA_ID, fake_redis, storage, frame_repo)

        assert frame_repo.create.call_count == 1
        assert storage.upload_bytes.call_count == 1

    def test_different_camera_not_blocked_by_other_cameras_lock(self, monkeypatch):
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: True)
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: 20)
        fake_redis = _FakeRedisDedup()
        storage = MagicMock()
        frame_repo = MagicMock()
        other_camera_id = str(uuid4())

        self._call(_CAMERA_ID, fake_redis, storage, frame_repo)
        self._call(other_camera_id, fake_redis, storage, frame_repo)

        assert frame_repo.create.call_count == 2

    def test_capture_allowed_again_after_dedup_window_expires(self, monkeypatch):
        monkeypatch.setattr(inference_mod, "_auto_capture_enabled", lambda pool, tid: True)
        monkeypatch.setattr(inference_mod, "_auto_capture_daily_cap", lambda pool, tid: 20)
        fake_redis = _FakeRedisDedup()
        storage = MagicMock()
        frame_repo = MagicMock()

        self._call(_CAMERA_ID, fake_redis, storage, frame_repo)
        fake_redis.expire_key_now(f"epi:autocapture:dedup:{_CAMERA_ID}")
        self._call(_CAMERA_ID, fake_redis, storage, frame_repo)

        assert frame_repo.create.call_count == 2


class TestSaveAlertCallsAutoCapture:
    def test_save_alert_calls_auto_capture_after_alert_saved(self, monkeypatch):
        """O hook roda DEPOIS do alerta salvo — nunca antes, nunca em
        outro lugar (ver docstring de _save_alert)."""
        call_order = []

        mock_cv2 = MagicMock()
        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"jpeg"))

        mock_pool = MagicMock()
        mock_storage = MagicMock()
        mock_alert_repo = MagicMock()

        def _record_alert_create(*a, **kw):
            call_order.append("alert_saved")

        mock_alert_repo.create.side_effect = _record_alert_create
        mock_alert_repo_cls = MagicMock(return_value=mock_alert_repo)

        def _record_auto_capture(*a, **kw):
            call_order.append("auto_capture")

        monkeypatch.setattr(inference_mod, "_auto_capture_frame", _record_auto_capture)
        monkeypatch.setattr(
            inference_mod, "_camera_tenant_module", lambda pool, cam: (_TENANT_ID, "epi")
        )

        with patch.dict(sys.modules, {"cv2": mock_cv2}), patch(
            "app.infrastructure.database.connection.DatabasePool"
        ) as mock_dbpool_cls, patch(
            "app.infrastructure.database.repositories.alert_repository.AlertRepository",
            mock_alert_repo_cls,
        ), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
        ):
            mock_dbpool_cls.get_instance.return_value = mock_pool
            inference_mod._save_alert(
                _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.9}], MagicMock()
            )

        assert call_order == ["alert_saved", "auto_capture"]

    def test_save_alert_still_saves_alert_when_auto_capture_raises(self, monkeypatch):
        """Falha na auto-captura nunca deve impedir o alerta de já ter sido
        salvo (auto-captura roda depois, best-effort)."""
        mock_cv2 = MagicMock()
        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"jpeg"))
        mock_pool = MagicMock()
        mock_storage = MagicMock()
        mock_alert_repo = MagicMock()

        monkeypatch.setattr(
            inference_mod, "_camera_tenant_module", lambda pool, cam: (_TENANT_ID, "epi")
        )

        with patch.dict(sys.modules, {"cv2": mock_cv2}), patch(
            "app.infrastructure.database.connection.DatabasePool"
        ) as mock_dbpool_cls, patch(
            "app.infrastructure.database.repositories.alert_repository.AlertRepository",
            return_value=mock_alert_repo,
        ), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
        ), patch.object(
            inference_mod, "_auto_capture_frame", side_effect=RuntimeError("boom")
        ):
            mock_dbpool_cls.get_instance.return_value = mock_pool
            # _save_alert engole TODA exceção (try/except no nível mais externo) —
            # confirma que não propaga mesmo com auto-captura quebrando.
            inference_mod._save_alert(
                _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.9}], MagicMock()
            )

        mock_alert_repo.create.assert_called_once()
