"""Tests: Middleware (error handlers, security headers, request logging)."""
import logging
import re

from flask import Flask

from app.core.exceptions import ValidationError, NotFoundError
from app.core.middleware import (
    register_error_handlers,
    register_security_headers,
    register_request_logging,
    register_request_id,
    register_rate_limit_handler,
)


class TestErrorHandlers:
    """Tests for error handler registration."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_error_handlers(self.app)
        self.client = self.app.test_client()

    def test_app_error_handled(self) -> None:
        @self.app.route("/test-validation")
        def raise_validation():  # type: ignore[no-untyped-def]
            raise ValidationError("bad input")

        res = self.client.get("/test-validation")
        assert res.status_code == 400
        data = res.get_json()
        assert data["error"] == "bad input"
        assert data["success"] is False

    def test_not_found_error(self) -> None:
        @self.app.route("/test-notfound")
        def raise_notfound():  # type: ignore[no-untyped-def]
            raise NotFoundError("Item", "xyz")

        res = self.client.get("/test-notfound")
        assert res.status_code == 404

    def test_404_handler(self) -> None:
        res = self.client.get("/nonexistent-route")
        assert res.status_code == 404
        data = res.get_json()
        assert not data["success"]

    def test_405_handler(self) -> None:
        @self.app.route("/only-get", methods=["GET"])
        def only_get():  # type: ignore[no-untyped-def]
            return "ok"

        res = self.client.post("/only-get")
        assert res.status_code == 405

    def test_generic_exception_handled(self) -> None:
        @self.app.route("/test-crash")
        def crash():  # type: ignore[no-untyped-def]
            raise RuntimeError("unexpected")

        res = self.client.get("/test-crash")
        assert res.status_code == 500
        data = res.get_json()
        assert data["error"] == "Erro interno"
        # Stack trace should NOT be in response
        assert "RuntimeError" not in str(data)


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_security_headers(self.app)

        @self.app.route("/test")
        def test_route():  # type: ignore[no-untyped-def]
            return "ok"

        self.client = self.app.test_client()

    def test_x_content_type_options(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_x_xss_protection(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self) -> None:
        res = self.client.get("/test")
        assert "strict-origin" in res.headers.get("Referrer-Policy", "")


class TestRequestLogging:
    """Tests for request logging middleware."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_request_logging(self.app)

        @self.app.route("/test")
        def test_route():  # type: ignore[no-untyped-def]
            return "ok"

        self.client = self.app.test_client()

    def test_request_completes(self) -> None:
        res = self.client.get("/test")
        assert res.status_code == 200


class TestRoutineStreamLogHygiene:
    """
    task-068 — routine HLS polling floods INFO at ~1 req/s per open camera.
    `.m3u8`/`.ts` requests that succeed (200/304) must log at DEBUG; everything
    else (start/stop/status, and any error on a stream path) must stay at INFO
    so operational events remain visible.
    """

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_request_logging(self.app)

        @self.app.route("/api/cameras/<camera_id>/stream/stream.m3u8")
        def playlist(camera_id):  # type: ignore[no-untyped-def]
            return "playlist", 200

        @self.app.route("/api/cameras/<camera_id>/stream/seg1.ts")
        def segment(camera_id):  # type: ignore[no-untyped-def]
            return "segment", 200

        @self.app.route("/api/cameras/<camera_id>/stream/broken.ts")
        def broken_segment(camera_id):  # type: ignore[no-untyped-def]
            return "err", 500

        @self.app.route("/api/cameras/<camera_id>/stream/start", methods=["POST"])
        def start(camera_id):  # type: ignore[no-untyped-def]
            return "starting", 200

        self.client = self.app.test_client()

    def _last_record(self, caplog):  # type: ignore[no-untyped-def]
        records = [r for r in caplog.records if r.name == "app.core.middleware"]
        assert records, "expected a request log record from app.core.middleware"
        return records[-1]

    def test_playlist_200_logs_at_debug(self, caplog) -> None:
        """FAILS BEFORE FIX: previously every non-/health request logged at INFO."""
        with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
            self.client.get("/api/cameras/abc/stream/stream.m3u8")
        assert self._last_record(caplog).levelname == "DEBUG"

    def test_segment_200_logs_at_debug(self, caplog) -> None:
        """FAILS BEFORE FIX: `.ts` segment fetches also used to log at INFO."""
        with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
            self.client.get("/api/cameras/abc/stream/seg1.ts")
        assert self._last_record(caplog).levelname == "DEBUG"

    def test_stream_error_response_stays_at_info(self, caplog) -> None:
        """An error on a stream path must remain visible at INFO, never DEBUG."""
        with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
            self.client.get("/api/cameras/abc/stream/broken.ts")
        assert self._last_record(caplog).levelname == "INFO"

    def test_stream_start_stays_at_info(self, caplog) -> None:
        """Non-attrition routes (start/stop/status) are unaffected by the regex — stay INFO."""
        with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
            self.client.post("/api/cameras/abc/stream/start")
        assert self._last_record(caplog).levelname == "INFO"


# Log de produção (04/08): duas linhas por requisição (app.core.middleware +
# geventwebsocket.handler), ~2M linhas/dia com 8 câmeras. A linha consolidada
# abaixo carrega os 7 campos que sustentavam as DUAS linhas antigas — nenhuma
# perde informação (bytes/IP vinham só da linha do gevent; rid/duração só da
# do middleware).
_LOG_LINE_RE = re.compile(
    r"^request: (?P<method>\S+) (?P<path>\S+) → (?P<status>\d+) "
    r"\((?P<duration>[\d.]+)s\) bytes=(?P<bytes>\S+) ip=(?P<ip>\S+) rid=(?P<rid>\S+)$"
)


class TestConsolidatedAccessLog:
    """Uma linha por requisição, com rid/método/rota/status/duração/bytes/IP."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_request_id(self.app)
        register_request_logging(self.app)

        @self.app.route("/test")
        def test_route():  # type: ignore[no-untyped-def]
            return "hello world", 200  # 11 bytes

        @self.app.route("/stream/live")
        def stream_route():  # type: ignore[no-untyped-def]
            from flask import Response

            def gen():
                yield b"chunk"

            return Response(gen(), mimetype="video/mp2t")  # sem Content-Length

        self.client = self.app.test_client()

    def _records(self, caplog):  # type: ignore[no-untyped-def]
        return [r for r in caplog.records if r.name == "app.core.middleware"]

    def test_single_line_with_seven_fields(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            self.client.get("/test")

        records = self._records(caplog)
        assert len(records) == 1, "esperado EXATAMENTE uma linha de access log por requisição"

        message = records[0].getMessage()
        match = _LOG_LINE_RE.match(message)
        assert match, f"linha não bate o formato esperado: {message!r}"
        fields = match.groupdict()
        assert fields["method"] == "GET"
        assert fields["path"] == "/test"
        assert fields["status"] == "200"
        assert fields["rid"] != "-"

    def test_bytes_reflects_response_content_length(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            self.client.get("/test")

        message = self._records(caplog)[0].getMessage()
        fields = _LOG_LINE_RE.match(message).groupdict()  # type: ignore[union-attr]
        assert fields["bytes"] == "11", "b'hello world' tem 11 bytes"

    def test_bytes_is_dash_when_streaming_without_content_length(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            self.client.get("/stream/live")

        message = self._records(caplog)[0].getMessage()
        fields = _LOG_LINE_RE.match(message).groupdict()  # type: ignore[union-attr]
        assert fields["bytes"] == "-"

    def test_x_forwarded_for_used_as_client_ip(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            self.client.get(
                "/test", headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
            )

        message = self._records(caplog)[0].getMessage()
        fields = _LOG_LINE_RE.match(message).groupdict()  # type: ignore[union-attr]
        assert fields["ip"] == "203.0.113.7", (
            "deve usar o primeiro hop do X-Forwarded-For — Railway tem proxy na "
            "frente e remote_addr sozinho é o IP interno do proxy"
        )

    def test_no_forwarded_for_falls_back_to_remote_addr(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            self.client.get("/test")

        message = self._records(caplog)[0].getMessage()
        fields = _LOG_LINE_RE.match(message).groupdict()  # type: ignore[union-attr]
        assert fields["ip"] == "127.0.0.1"  # remote_addr default do test client


class TestRateLimit429CoveredByAccessLog:
    """
    O caso mais crítico do consolidado: flask-limiter registra seu próprio
    before_request em limiter.init_app() — ANTES de register_request_id e
    register_request_logging, mesma ordem de app/__init__.py — então uma
    requisição barrada por 429 nunca passa pelos before_request deste módulo.
    Sem o backfill em register_rate_limit_handler, a linha consolidada sairia
    com rid="-" e duração inválida (bug real observado em produção 04/08). Os
    429 são exatamente o que sustenta a investigação de rate limit — não podem
    sumir do log.
    """

    def setup_method(self) -> None:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        self.app = Flask(__name__)

        # Limite baixo pra estourar na 2ª request — mesma ordem de
        # app/__init__.py: limiter.init_app() ANTES do resto do middleware.
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["1 per minute"],
            app=self.app,
        )
        register_rate_limit_handler(self.app)
        register_request_id(self.app)
        register_request_logging(self.app)

        @self.app.route("/limited")
        def limited_route():  # type: ignore[no-untyped-def]
            return "ok", 200

        self.limiter = limiter
        self.client = self.app.test_client()

    def _records(self, caplog):  # type: ignore[no-untyped-def]
        return [r for r in caplog.records if r.name == "app.core.middleware"]

    def test_429_appears_in_consolidated_log_with_valid_rid(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            first = self.client.get("/limited")
            second = self.client.get("/limited")

        assert first.status_code == 200
        assert second.status_code == 429

        records = self._records(caplog)
        assert len(records) == 2, "uma linha por requisição, inclusive a barrada pelo limiter"

        second_fields = _LOG_LINE_RE.match(records[1].getMessage()).groupdict()  # type: ignore[union-attr]
        assert second_fields["status"] == "429"
        assert second_fields["rid"] != "-", (
            "429 do flask-limiter não pode sair sem rid — é o antes/depois "
            "investigado no rate limit"
        )
        assert re.match(r"^[\d.]+$", second_fields["duration"]), "duração deve ser numérica, não '-'"
