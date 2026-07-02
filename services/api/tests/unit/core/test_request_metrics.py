"""Tests: app/core/request_metrics.py — instrumentação RED da API (WS11/E2-4).

Contadores horários em Redis via before/after_request:
  - count/err_4xx/err_5xx/dur_ms_sum incrementados por request
  - /health e /streams excluídos
  - falha de Redis é silenciosa (nunca derruba a request)
  - aggregate_last_hours soma as chaves horárias
"""
from unittest.mock import MagicMock, patch

from flask import Flask

from app.core.request_metrics import (
    _hour_key,
    _is_excluded,
    aggregate_last_hours,
    current_hour_snapshot,
    register_request_metrics,
)

_GET_REDIS = "app.core.request_metrics._get_redis"


def _make_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/api/v1/ok")
    def ok():  # type: ignore[no-untyped-def]
        return {"ok": True}, 200

    @app.route("/api/v1/notfound")
    def notfound():  # type: ignore[no-untyped-def]
        return {"err": True}, 404

    @app.route("/api/v1/boom")
    def boom():  # type: ignore[no-untyped-def]
        return {"err": True}, 500

    @app.route("/health")
    def health():  # type: ignore[no-untyped-def]
        return {"ok": True}, 200

    register_request_metrics(app)
    return app


def _mock_redis() -> tuple[MagicMock, MagicMock]:
    r = MagicMock()
    pipe = MagicMock()
    r.pipeline.return_value = pipe
    pipe.execute.return_value = []
    return r, pipe


def _hincrby_fields(pipe: MagicMock) -> list[str]:
    return [c.args[1] for c in pipe.hincrby.call_args_list]


class TestRecordHooks:
    def test_200_increments_count_and_duration(self):
        app = _make_app()
        r, pipe = _mock_redis()
        with patch(_GET_REDIS, return_value=r):
            resp = app.test_client().get("/api/v1/ok")
        assert resp.status_code == 200
        fields = _hincrby_fields(pipe)
        assert "count" in fields
        assert "dur_ms_sum" in fields
        assert "err_4xx" not in fields
        assert "err_5xx" not in fields
        pipe.expire.assert_called_once()

    def test_404_increments_err_4xx(self):
        app = _make_app()
        r, pipe = _mock_redis()
        with patch(_GET_REDIS, return_value=r):
            app.test_client().get("/api/v1/notfound")
        assert "err_4xx" in _hincrby_fields(pipe)

    def test_500_increments_err_5xx(self):
        app = _make_app()
        r, pipe = _mock_redis()
        with patch(_GET_REDIS, return_value=r):
            app.test_client().get("/api/v1/boom")
        assert "err_5xx" in _hincrby_fields(pipe)

    def test_health_path_excluded(self):
        app = _make_app()
        r, pipe = _mock_redis()
        with patch(_GET_REDIS, return_value=r):
            app.test_client().get("/health")
        pipe.hincrby.assert_not_called()

    def test_redis_failure_never_breaks_request(self):
        app = _make_app()
        with patch(_GET_REDIS, side_effect=Exception("redis down")):
            resp = app.test_client().get("/api/v1/ok")
        assert resp.status_code == 200


class TestExclusions:
    def test_excluded_prefixes(self):
        assert _is_excluded("/health")
        assert _is_excluded("/api/v1/health/metrics")
        assert _is_excluded("/api/streams/status")
        assert _is_excluded("/streams/1/stream.m3u8")
        assert not _is_excluded("/api/v1/cameras")


class TestAggregation:
    def test_sums_hourly_hashes(self):
        r, pipe = _mock_redis()
        pipe.execute.return_value = [
            {"count": "10", "err_4xx": "2", "err_5xx": "1", "dur_ms_sum": "500"},
            {"count": "5", "dur_ms_sum": "250"},
            {},
        ]
        with patch(_GET_REDIS, return_value=r):
            agg = aggregate_last_hours(3)
        assert agg["count"] == 15
        assert agg["err_4xx"] == 2
        assert agg["err_5xx"] == 1
        assert agg["dur_ms_sum"] == 750
        assert agg["avg_ms"] == 50.0

    def test_redis_down_returns_zeros(self):
        with patch(_GET_REDIS, side_effect=Exception("down")):
            agg = aggregate_last_hours(24)
        assert agg["count"] == 0
        assert agg["avg_ms"] == 0.0

    def test_current_hour_snapshot_parses_hash(self):
        r = MagicMock()
        r.hgetall.return_value = {"count": "7", "err_5xx": "1", "dur_ms_sum": "70"}
        with patch(_GET_REDIS, return_value=r):
            snap = current_hour_snapshot()
        assert snap == {"count": 7, "err_4xx": 0, "err_5xx": 1, "dur_ms_sum": 70}

    def test_current_hour_snapshot_redis_down(self):
        with patch(_GET_REDIS, side_effect=Exception("down")):
            snap = current_hour_snapshot()
        assert snap["count"] == 0


class TestHourKey:
    def test_key_format(self):
        from datetime import datetime, timezone
        dt = datetime(2026, 7, 1, 13, 45, tzinfo=timezone.utc)
        assert _hour_key(dt) == "apimetrics:2026070113"
