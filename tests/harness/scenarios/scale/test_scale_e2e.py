"""
Testes E2E de escala — harness sintético (task-027 / PR A3).

Valida que o runner de escala funciona corretamente com N=4 câmeras.
Não requer model ONNX real — usa stub.

Pré-requisitos:
  docker-compose -f tests/harness/scenarios/scale/docker-compose.scale.yml up -d
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# ── Fixtures ──────────────────────────────────────────────────────────────────

DB_URL = os.environ.get(
    "SCALE_DB_URL",
    "postgresql://harness:harness@localhost:55434/recognition_scale",
)
REDIS_URL = os.environ.get("SCALE_REDIS_URL", "redis://localhost:6381")
RTSP_HOST = os.environ.get("RTSP_HOST", "localhost")
RTSP_PORT = int(os.environ.get("RTSP_PORT", "8555"))


@pytest.fixture(scope="module")
def db_conn():
    """Conexão ao banco do harness de escala."""
    pytest.importorskip("psycopg2", reason="psycopg2 não instalado")
    import psycopg2
    import psycopg2.extras
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = True
    except Exception:
        pytest.skip("Banco do harness de escala não disponível — rode docker-compose.scale.yml")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def redis_client():
    """Cliente Redis do harness de escala."""
    pytest.importorskip("redis", reason="redis-py não instalado")
    import redis as _redis
    try:
        r = _redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        r.ping()
    except Exception:
        pytest.skip("Redis do harness de escala não disponível — rode docker-compose.scale.yml")
    yield r


# ── Testes de infra ───────────────────────────────────────────────────────────

class TestScaleInfra:
    def test_db_reachable(self, db_conn) -> None:
        with db_conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone()["ok"] == 1

    def test_redis_reachable(self, redis_client) -> None:
        assert redis_client.ping() is True

    def test_cameras_table_exists(self, db_conn) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.cameras') IS NOT NULL AS exists"
            )
            assert cur.fetchone()["exists"] is True

    def test_tenants_table_exists(self, db_conn) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.tenants') IS NOT NULL AS exists"
            )
            assert cur.fetchone()["exists"] is True


# ── Testes do scale_runner ────────────────────────────────────────────────────

class TestScaleRunner:
    """Testa a lógica do scale_runner sem docker nem ffmpeg reais."""

    def test_camera_metrics_dataclass(self) -> None:
        from scale_runner import CameraMetrics  # noqa: PLC0415
        m = CameraMetrics(camera_id="abc", camera_index=0)
        assert m.inf_per_sec >= 0
        assert m.p50_latency_ms is None
        assert m.p95_latency_ms is None

    def test_camera_metrics_with_data(self) -> None:
        from scale_runner import CameraMetrics  # noqa: PLC0415
        m = CameraMetrics(camera_id="abc", camera_index=0)
        m.latencies_ms = [10.0, 20.0, 30.0, 40.0, 50.0]
        m.frames_inferred = 5
        assert m.p50_latency_ms == 30.0
        assert m.p95_latency_ms == 50.0
        assert m.inf_per_sec > 0

    def test_build_report_format(self) -> None:
        from scale_runner import CameraMetrics, _build_report  # noqa: PLC0415
        metrics = [
            CameraMetrics(camera_id=str(uuid.uuid4()), camera_index=i)
            for i in range(4)
        ]
        for m in metrics:
            m.frames_inferred = 100
            m.redis_publishes = 100
            m.latencies_ms = [5.0 + i * 0.5 for i in range(100)]

        report = _build_report(4, 30, metrics, [10, 12, 11])
        assert "Câmeras" in report
        assert "Duração" in report
        assert "Latência p95" in report
        assert "cam0" in report
        assert "cam3" in report

    def test_build_report_marks_degradation(self) -> None:
        from scale_runner import CameraMetrics, _build_report  # noqa: PLC0415
        metrics = [
            CameraMetrics(camera_id=str(uuid.uuid4()), camera_index=i)
            for i in range(4)
        ]
        for m in metrics:
            m.errors = 10  # 4 câmeras × 10 erros = 40 > 4
        report = _build_report(4, 30, metrics, [])
        assert "DEGRADAÇÃO" in report

    def test_inference_thread_stub_detector(self) -> None:
        """Thread de inferência com detector stub — publica no Redis mock."""
        from scale_runner import CameraMetrics, _run_inference_thread  # noqa: PLC0415

        # Mock CV2 para não precisar de stream RTSP real
        import numpy as np  # noqa: PLC0415

        stop_event = threading.Event()
        metrics = CameraMetrics(camera_id="cam-test", camera_index=0)
        redis_mock = MagicMock()

        frame_count = [0]

        def fake_read():
            if frame_count[0] >= 10:
                stop_event.set()
                return False, None
            frame_count[0] += 1
            return True, np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        mock_cap.read.side_effect = fake_read

        with patch("cv2.VideoCapture", return_value=mock_cap):
            camera = {"id": "cam-test", "rtsp_url": "rtsp://fake/cam0", "index": 0}
            _run_inference_thread(camera, metrics, stop_event, redis_mock, None, every_n=1)

        assert metrics.frames_read >= 10
        assert metrics.frames_inferred >= 10
        assert redis_mock.publish.call_count >= 10

    def test_redis_payload_format(self) -> None:
        """Valida que o payload publicado tem o formato correto."""
        from scale_runner import CameraMetrics, _run_inference_thread  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        stop_event = threading.Event()
        metrics = CameraMetrics(camera_id="cam-payload-test", camera_index=0)
        published_payloads = []

        class MockRedis:
            def publish(self, channel, payload):
                published_payloads.append((channel, json.loads(payload)))

        frame_count = [0]

        def fake_read():
            if frame_count[0] >= 3:
                stop_event.set()
                return False, None
            frame_count[0] += 1
            return True, np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        mock_cap.read.side_effect = fake_read

        with patch("cv2.VideoCapture", return_value=mock_cap):
            camera = {"id": "cam-payload-test", "rtsp_url": "rtsp://fake/cam0", "index": 0}
            _run_inference_thread(camera, metrics, stop_event, MockRedis(), None, every_n=1)

        assert len(published_payloads) > 0
        channel, payload = published_payloads[0]
        assert channel == "det:cam-payload-test"
        assert "camera_id" in payload
        assert "timestamp" in payload
        assert "detections" in payload
        assert "has_violation" in payload


# ── Testes E2E com DB real ────────────────────────────────────────────────────

class TestScaleE2EWithDb:
    """Testes que requerem banco do harness ativo."""

    def test_ensure_test_tenant_idempotent(self, db_conn) -> None:
        from scale_runner import _ensure_test_tenant  # noqa: PLC0415
        # Deve poder rodar 2x sem erro
        _ensure_test_tenant(db_conn)
        _ensure_test_tenant(db_conn)
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tenants WHERE id = '00000000-0000-0000-0000-0000000000AA'"
            )
            assert cur.fetchone() is not None

    def test_register_and_cleanup_cameras(self, db_conn) -> None:
        from scale_runner import _cleanup_cameras, _ensure_test_tenant, _register_cameras  # noqa: PLC0415
        _ensure_test_tenant(db_conn)

        n = 4
        cameras = _register_cameras(db_conn, n)
        assert len(cameras) == n

        # Todas têm IDs e rtsp_url correto
        for i, cam in enumerate(cameras):
            assert cam["id"]
            assert f"cam{i}" in cam["rtsp_url"]

        # Cleanup
        _cleanup_cameras(db_conn, [c["id"] for c in cameras])
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM cameras WHERE tenant_id = '00000000-0000-0000-0000-0000000000AA' AND name LIKE 'scale-cam-%'"
            )
            assert cur.fetchone()["count"] == 0
