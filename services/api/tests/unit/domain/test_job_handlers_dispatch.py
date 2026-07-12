"""
Tests: _dispatch_to_training_service, _dispatch_celery_fallback, _publish_model_reload (item-20).

Cobre o fluxo de dispatch de jobs de treinamento:
- HTTP para training-service → fallback Celery quando HTTP falha
- Redis publish para hot-reload de modelo
"""
from unittest.mock import MagicMock, patch


class TestDispatchToTrainingService:

    def test_dispatch_calls_training_service_http(self):
        """_dispatch_to_training_service deve fazer POST para training-service."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201

        with patch("app.api.v1.training.job_handlers.http_requests") as mock_http:
            mock_http.post.return_value = mock_resp
            from app.api.v1.training.job_handlers import _dispatch_to_training_service
            _dispatch_to_training_service("job-abc", "user-xyz")

        mock_http.post.assert_called_once()
        call_kwargs = mock_http.post.call_args
        assert "job-abc" in str(call_kwargs)

    def test_dispatch_non_2xx_triggers_celery_fallback(self):
        """Status não-2xx do training-service deve acionar fallback Celery."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "service unavailable"

        with patch("app.api.v1.training.job_handlers.http_requests") as mock_http, \
             patch("app.api.v1.training.job_handlers._dispatch_celery_fallback") as mock_fallback:
            mock_http.post.return_value = mock_resp
            from app.api.v1.training.job_handlers import _dispatch_to_training_service
            _dispatch_to_training_service("job-503", "user-xyz")

        mock_fallback.assert_called_once_with("job-503")

    def test_dispatch_http_exception_triggers_celery_fallback(self):
        """Exceção HTTP deve acionar fallback Celery."""
        with patch("app.api.v1.training.job_handlers.http_requests") as mock_http, \
             patch("app.api.v1.training.job_handlers._dispatch_celery_fallback") as mock_fallback:
            mock_http.post.side_effect = ConnectionError("timeout")
            from app.api.v1.training.job_handlers import _dispatch_to_training_service
            _dispatch_to_training_service("job-err", "user-xyz")

        mock_fallback.assert_called_once_with("job-err")

    def test_dispatch_2xx_does_not_trigger_fallback(self):
        """Resposta 2xx não deve acionar fallback Celery."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("app.api.v1.training.job_handlers.http_requests") as mock_http, \
             patch("app.api.v1.training.job_handlers._dispatch_celery_fallback") as mock_fallback:
            mock_http.post.return_value = mock_resp
            from app.api.v1.training.job_handlers import _dispatch_to_training_service
            _dispatch_to_training_service("job-ok", "user-xyz")

        mock_fallback.assert_not_called()


class TestDispatchCeleryFallback:

    def test_fallback_calls_dispatch_training_delay(self):
        """_dispatch_celery_fallback deve chamar dispatch_training.delay."""
        mock_task = MagicMock()
        mock_module = MagicMock()
        mock_module.dispatch_training = mock_task
        with patch.dict("sys.modules", {
            "app.infrastructure.queue.tasks.training": mock_module
        }):
            from app.api.v1.training.job_handlers import _dispatch_celery_fallback
            _dispatch_celery_fallback("job-fb")

        mock_task.delay.assert_called_once()

    def test_fallback_silently_handles_import_error(self):
        """_dispatch_celery_fallback não deve propagar exceção quando Celery indisponível.

        Setting sys.modules[name] = None makes Python raise ImportError on
        `from <name> import ...` — the standard way to simulate a missing package.
        """
        with patch.dict("sys.modules", {"app.infrastructure.queue.tasks.training": None}):
            from app.api.v1.training.job_handlers import _dispatch_celery_fallback
            try:
                _dispatch_celery_fallback("job-no-celery")
            except Exception as exc:
                raise AssertionError(f"Não deveria propagar: {exc}")


class TestPublishModelReload:

    def test_publish_calls_redis_publish(self):
        """_publish_model_reload deve publicar canal model:reload no Redis."""
        mock_redis_instance = MagicMock()
        mock_redis_module = MagicMock(from_url=MagicMock(return_value=mock_redis_instance))

        with patch.dict("sys.modules", {"redis": mock_redis_module}), \
             patch("app.api.v1.training.job_handlers._REDIS_URL", "redis://localhost:6379"):
            from app.api.v1.training.job_handlers import _publish_model_reload
            _publish_model_reload("models/yolo26n.pt")

        mock_redis_instance.publish.assert_called_once()
        call_args = mock_redis_instance.publish.call_args[0]
        assert call_args[0] == "model:reload"
        assert "yolo26n.pt" in call_args[1]

    def test_publish_skips_when_no_redis_url(self):
        """_publish_model_reload não deve falhar quando REDIS_URL está vazio."""
        with patch("app.api.v1.training.job_handlers._REDIS_URL", ""):
            from app.api.v1.training.job_handlers import _publish_model_reload
            _publish_model_reload("models/yolo26n.pt")  # deve retornar sem erro

    def test_publish_skips_when_no_model_path(self):
        """_publish_model_reload não deve falhar quando model_path é vazio."""
        with patch("app.api.v1.training.job_handlers._REDIS_URL", "redis://localhost:6379"):
            from app.api.v1.training.job_handlers import _publish_model_reload
            _publish_model_reload("")  # deve retornar sem erro

    def test_publish_silently_handles_redis_error(self):
        """_publish_model_reload não deve propagar exceção de Redis."""
        mock_redis_module = MagicMock(from_url=MagicMock(side_effect=Exception("conn refused")))

        with patch.dict("sys.modules", {"redis": mock_redis_module}), \
             patch("app.api.v1.training.job_handlers._REDIS_URL", "redis://localhost:6379"):
            from app.api.v1.training.job_handlers import _publish_model_reload
            try:
                _publish_model_reload("models/yolo26n.pt")
            except Exception as exc:
                raise AssertionError(f"Não deveria propagar: {exc}")
