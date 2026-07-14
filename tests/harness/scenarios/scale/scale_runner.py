"""
Harness de escala — runner de N câmeras sintéticas (task-027 / PR A3).

Sobe N publishers ffmpeg no MediaMTX, registra N câmeras no tenant de teste,
roda N threads de inferência ONNX (ou stub quando modelo não existe) e coleta
métricas: latência frame→detecção, inf/s, erros, conexões PG.

Uso:
  python3 tests/harness/scenarios/scale/scale_runner.py --cameras 4
  python3 tests/harness/scenarios/scale/scale_runner.py --cameras 28 --duration 60
  python3 tests/harness/scenarios/scale/scale_runner.py --cameras 28 --report docs/evidence/e2e-scale/REPORT.md

Pré-requisitos:
  docker-compose -f tests/harness/scenarios/scale/docker-compose.scale.yml up -d
  (ou RTSP_HOST/RTSP_PORT/DB_URL/REDIS_URL apontando para infra existente)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import psycopg2
import psycopg2.extras
import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCALE] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scale_runner")

# ── Defaults (sobrescritos por env / args) ────────────────────────────────────
RTSP_HOST = os.environ.get("RTSP_HOST", "localhost")
RTSP_PORT = int(os.environ.get("RTSP_PORT", "8555"))
DB_URL = os.environ.get(
    "SCALE_DB_URL",
    "postgresql://harness:harness@localhost:55434/recognition_scale",
)
REDIS_URL = os.environ.get("SCALE_REDIS_URL", "redis://localhost:6381")
TEST_TENANT_ID = "00000000-0000-0000-0000-0000000000AA"

# Vídeo sintético — 5fps de frames pretos com texto
SYNTHETIC_VIDEO_SRC = (
    "testsrc=size=640x480:rate=5,drawtext=text='CAM%i':fontsize=60:"
    "fontcolor=white:x=10:y=10"
)


# ── Dados ─────────────────────────────────────────────────────────────────────

@dataclass
class CameraMetrics:
    camera_id: str
    camera_index: int
    frames_read: int = 0
    frames_inferred: int = 0
    detections_total: int = 0
    redis_publishes: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    stopped_at: float | None = None

    @property
    def elapsed(self) -> float:
        end = self.stopped_at or time.time()
        return max(end - self.started_at, 0.001)

    @property
    def inf_per_sec(self) -> float:
        return self.frames_inferred / self.elapsed

    @property
    def p50_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        s = sorted(self.latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.95)]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _ensure_test_tenant(conn) -> None:
    """Cria o tenant de teste se não existir (idempotente)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active)
            VALUES (%s, 'Scale Test Tenant', 'scale-test', TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            (TEST_TENANT_ID,),
        )
        cur.execute(
            """
            INSERT INTO tenant_modules (tenant_id, module_code, enabled)
            VALUES (%s, 'epi', TRUE)
            ON CONFLICT (tenant_id, module_code) DO NOTHING
            """,
            (TEST_TENANT_ID,),
        )
    conn.commit()
    log.info("tenant de teste garantido: %s", TEST_TENANT_ID)


def _register_cameras(conn, n: int) -> list[dict]:
    """Registra N câmeras no tenant de teste. Retorna lista de dicts."""
    cameras = []
    with conn.cursor() as cur:
        for i in range(n):
            cam_id = str(uuid.uuid4())
            rtsp_url = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/cam{i}"
            cur.execute(
                """
                INSERT INTO cameras (id, tenant_id, name, rtsp_url, module_code, status)
                VALUES (%s, %s, %s, %s, 'epi', 'active')
                ON CONFLICT DO NOTHING
                RETURNING id, name, rtsp_url
                """,
                (cam_id, TEST_TENANT_ID, f"scale-cam-{i}", rtsp_url),
            )
            row = cur.fetchone()
            if row:
                cameras.append({"id": row["id"], "name": row["name"], "rtsp_url": row["rtsp_url"], "index": i})
            else:
                # Câmera já existia — busca
                cur.execute(
                    "SELECT id, name, rtsp_url FROM cameras WHERE tenant_id = %s AND name = %s",
                    (TEST_TENANT_ID, f"scale-cam-{i}"),
                )
                row = cur.fetchone()
                if row:
                    cameras.append({"id": row["id"], "name": row["name"], "rtsp_url": row["rtsp_url"], "index": i})
    conn.commit()
    log.info("câmeras registradas: %d", len(cameras))
    return cameras


def _cleanup_cameras(conn, camera_ids: list[str]) -> None:
    if not camera_ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM cameras WHERE id = ANY(%s::uuid[])",
            (camera_ids,),
        )
    conn.commit()
    log.info("câmeras de teste removidas: %d", len(camera_ids))


# ── ffmpeg publishers ─────────────────────────────────────────────────────────

def _start_ffmpeg_publisher(cam_index: int, duration: int) -> subprocess.Popen:
    """Publica vídeo sintético para MediaMTX via RTSP."""
    rtsp_target = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/cam{cam_index}"
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=black:size=640x480:rate=5",
        "-vf", f"drawtext=text='CAM{cam_index}':fontsize=40:fontcolor=white:x=10:y=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-b:v", "128k", "-g", "5",
        "-f", "rtsp", "-rtsp_transport", "tcp",
        "-t", str(duration + 5),
        rtsp_target,
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── Inference thread ──────────────────────────────────────────────────────────

def _run_inference_thread(
    camera: dict,
    metrics: CameraMetrics,
    stop_event: threading.Event,
    redis_client: redis.Redis,
    detector,
    every_n: int = 5,
) -> None:
    """Loop de inferência para uma câmera. Publica det:{camera_id} no Redis."""
    rtsp_url = camera["rtsp_url"]
    camera_id = camera["id"]

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame_count += 1
            metrics.frames_read += 1

            if frame_count % every_n != 0:
                continue

            t0 = time.time()
            try:
                if detector is not None:
                    detections = detector.predict(frame)
                else:
                    detections = []
                metrics.frames_inferred += 1
                metrics.detections_total += len(detections)

                latency_ms = (time.time() - t0) * 1000
                metrics.latencies_ms.append(latency_ms)

                payload = json.dumps({
                    "camera_id": camera_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "detections": detections,
                    "has_violation": False,
                })
                redis_client.publish(f"det:{camera_id}", payload)
                metrics.redis_publishes += 1
            except Exception as exc:
                metrics.errors += 1
                log.warning("inference_error: cam=%s err=%s", camera_id, exc)

    except Exception as exc:
        metrics.errors += 1
        log.error("thread_fatal: cam=%s err=%s", camera_id, exc)
    finally:
        cap.release()
        metrics.stopped_at = time.time()


# ── Métricas PG ──────────────────────────────────────────────────────────────

def _get_pg_connections() -> int | None:
    try:
        conn = _db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            return cur.fetchone()["count"]
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Report ────────────────────────────────────────────────────────────────────

def _build_report(
    n_cameras: int,
    duration: int,
    all_metrics: list[CameraMetrics],
    pg_conn_samples: list[int],
) -> str:
    total_inf = sum(m.frames_inferred for m in all_metrics)
    total_errors = sum(m.errors for m in all_metrics)
    total_publishes = sum(m.redis_publishes for m in all_metrics)
    all_latencies = sorted(lat for m in all_metrics for lat in m.latencies_ms)

    def pct(lst, p):
        if not lst:
            return "N/A"
        return f"{lst[int(len(lst) * p / 100)]:.1f}ms"

    pg_avg = (sum(pg_conn_samples) / len(pg_conn_samples)) if pg_conn_samples else 0

    lines = [
        "# Scale Harness Report — Recognition E2E",
        "",
        f"**Câmeras**: {n_cameras}  **Duração**: {duration}s  **Every N frames**: 5",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---------|-------|",
        f"| Frames inferidos (total) | {total_inf} |",
        f"| Inf/s (total) | {total_inf / duration:.1f} |",
        f"| Detecções totais | {sum(m.detections_total for m in all_metrics)} |",
        f"| Publishes Redis | {total_publishes} |",
        f"| Erros | {total_errors} |",
        f"| Latência p50 | {pct(all_latencies, 50)} |",
        f"| Latência p95 | {pct(all_latencies, 95)} |",
        f"| Latência p99 | {pct(all_latencies, 99)} |",
        f"| Conexões PG (média) | {pg_avg:.1f} |",
        "",
        "## Por câmera",
        "",
        "| Câmera | Frames | Inf/s | Erros | p50 | p95 |",
        "|--------|--------|-------|-------|-----|-----|",
    ]

    for m in all_metrics:
        p50 = f"{m.p50_latency_ms:.1f}ms" if m.p50_latency_ms else "N/A"
        p95 = f"{m.p95_latency_ms:.1f}ms" if m.p95_latency_ms else "N/A"
        lines.append(
            f"| cam{m.camera_index} | {m.frames_inferred} | {m.inf_per_sec:.1f} | {m.errors} | {p50} | {p95} |"
        )

    lines += [
        "",
        "## Degradação",
        "",
        f"- Erros totais: {total_errors}",
        (
            f"- **PONTO DE DEGRADAÇÃO DETECTADO**: {total_errors} erros em {n_cameras} câmeras."
            if total_errors > n_cameras
            else f"- Sistema estável com {n_cameras} câmeras (erros={total_errors})."
        ),
        "",
        "_Gerado pelo harness scale_runner.py (task-055a / PR A3)_",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Scale harness — N câmeras sintéticas")
    parser.add_argument("--cameras", type=int, default=4, help="Número de câmeras (padrão: 4)")
    parser.add_argument("--duration", type=int, default=30, help="Duração do teste em segundos (padrão: 30)")
    parser.add_argument("--every-n", type=int, default=5, help="Inferir a cada N frames (padrão: 5)")
    parser.add_argument("--report", type=str, default="", help="Caminho para salvar o relatório Markdown")
    parser.add_argument("--no-cleanup", action="store_true", help="Manter câmeras no banco após o teste")
    parser.add_argument("--model-path", type=str, default="", help="Caminho do modelo ONNX (omitir = stub)")
    args = parser.parse_args()

    n = args.cameras
    duration = args.duration
    log.info("Iniciando harness scale: %d câmeras por %ds", n, duration)

    # Detector (stub se modelo não existir)
    detector = None
    if args.model_path and Path(args.model_path).exists():
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "services" / "api"))
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            detector = get_detector(backend="yolox_onnx", model_path=args.model_path)
            log.info("Detector ONNX carregado: %s", args.model_path)
        except Exception as exc:
            log.warning("Não foi possível carregar detector: %s — usando stub", exc)
    else:
        log.info("Modelo não especificado — usando stub (sem inferência real)")

    # DB + Redis
    conn = _db_conn()
    r = redis.from_url(REDIS_URL, decode_responses=True)

    # Preparar banco
    _ensure_test_tenant(conn)
    cameras = _register_cameras(conn, n)
    camera_ids = [c["id"] for c in cameras]

    # Iniciar publishers ffmpeg
    publishers = [_start_ffmpeg_publisher(i, duration) for i in range(n)]
    log.info("publishers ffmpeg iniciados: %d", n)
    time.sleep(2)  # deixar MediaMTX registrar as streams

    # Iniciar threads de inferência
    stop_event = threading.Event()
    all_metrics = [CameraMetrics(camera_id=c["id"], camera_index=c["index"]) for c in cameras]
    threads = []
    for cam, metrics in zip(cameras, all_metrics):
        t = threading.Thread(
            target=_run_inference_thread,
            args=(cam, metrics, stop_event, r, detector, args.every_n),
            daemon=True,
        )
        t.start()
        threads.append(t)

    log.info("threads de inferência iniciadas: %d", n)

    # Coletar métricas PG durante o teste
    pg_conn_samples: list[int] = []
    deadline = time.time() + duration
    while time.time() < deadline:
        pg = _get_pg_connections()
        if pg is not None:
            pg_conn_samples.append(pg)
        elapsed = duration - (deadline - time.time())
        total_inf = sum(m.frames_inferred for m in all_metrics)
        log.info(
            "[%ds/%ds] inferences=%d errors=%d",
            int(elapsed), duration, total_inf, sum(m.errors for m in all_metrics),
        )
        time.sleep(5)

    # Parar
    stop_event.set()
    for t in threads:
        t.join(timeout=5)
    for p in publishers:
        p.terminate()

    # Relatório
    report = _build_report(n, duration, all_metrics, pg_conn_samples)
    print("\n" + report)

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        log.info("Relatório salvo em: %s", out)

    # Cleanup
    if not args.no_cleanup:
        _cleanup_cameras(conn, camera_ids)
    conn.close()

    # Exit code 1 se erros altos (> câmeras)
    total_errors = sum(m.errors for m in all_metrics)
    if total_errors > n:
        log.error("DEGRADAÇÃO: %d erros para %d câmeras", total_errors, n)
        sys.exit(1)

    log.info("Harness scale concluído com sucesso.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    main()
