"""
Admin Test Console — endpoints para operação de teste E2E via painel admin.

task-055a / PR C1.

Role-gate: admin ou superadmin. Tudo isolado no tenant de teste
(00000000-0000-0000-0000-0000000000AA).

Endpoints:
  POST /api/v1/admin/test-console/harness/start   {cameras:N, model_id?}
  POST /api/v1/admin/test-console/harness/stop
  GET  /api/v1/admin/test-console/status
  GET  /api/v1/admin/test-console/models
  GET  /api/v1/admin/test-console/evidence
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import redis as _redis
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.responses import error, success
from app.core.tenant import require_admin
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

test_console_bp = Blueprint("test_console", __name__, url_prefix="/api/v1/admin/test-console")

# ── Constantes ────────────────────────────────────────────────────────────────

TEST_TENANT_ID = "00000000-0000-0000-0000-0000000000AA"
REDIS_CONFIG_KEY = "epi:testconsole:config"
REDIS_STREAM_KEY = "epi:stream:{camera_id}:active"
REDIS_TTL_SECONDS = 7200  # 2h — limite de segurança para testes

# URL template do harness RTSP (MediaMTX local ou staging)
RTSP_TEMPLATE = os.environ.get(
    "HARNESS_RTSP_URL_TEMPLATE",
    "rtsp://localhost:8555/cam{index}",
)
MAX_TEST_CAMERAS = int(os.environ.get("MAX_TEST_CAMERAS", "28"))


# ── Redis helper ──────────────────────────────────────────────────────────────

def _get_redis() -> _redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return _redis.from_url(url, decode_responses=True)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_pool() -> DatabasePool:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _register_test_cameras(n: int, model_id: str | None) -> list[dict]:
    """Cria N câmeras no tenant de teste. Retorna lista de dicts."""
    pool = _get_pool()
    cameras = []
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            for i in range(n):
                cam_id = str(uuid.uuid4())
                rtsp_url = RTSP_TEMPLATE.format(index=i)
                cur.execute(
                    """
                    INSERT INTO cameras (id, tenant_id, name, rtsp_url, module_code, status, active_model_id)
                    VALUES (%s, %s, %s, %s, 'epi', 'active', %s)
                    RETURNING id, name, rtsp_url
                    """,
                    (cam_id, TEST_TENANT_ID, f"test-console-cam-{i}", rtsp_url, model_id),
                )
                row = cur.fetchone()
                if row:
                    cameras.append({
                        "id": str(row[0]),
                        "name": row[1],
                        "rtsp_url": row[2],
                        "index": i,
                    })
        conn.commit()
    return cameras


def _delete_test_cameras(camera_ids: list[str]) -> int:
    """Remove câmeras de teste pelo ID. Retorna nº de removidas."""
    if not camera_ids:
        return 0
    pool = _get_pool()
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cameras WHERE id = ANY(%s::uuid[]) AND tenant_id = %s",
                (camera_ids, TEST_TENANT_ID),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


def _list_models() -> list[dict]:
    """Lista modelos disponíveis para o tenant de teste."""
    pool = _get_pool()
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, model_key, metrics, is_default, created_at
                FROM models
                WHERE tenant_id = %s
                ORDER BY is_default DESC, created_at DESC
                """,
                (TEST_TENANT_ID,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "name": r[1],
            "model_key": r[2],
            "metrics": r[3] or {},
            "is_default": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]


def _list_recent_evidence(limit: int = 20) -> list[dict]:
    """Lista alertas recentes do tenant de teste com chaves de evidência."""
    pool = _get_pool()
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.camera_id, a.evidence_key, a.confidence,
                       a.created_at, c.name AS camera_name
                FROM alerts a
                LEFT JOIN cameras c ON c.id = a.camera_id
                WHERE a.tenant_id = %s
                ORDER BY a.created_at DESC
                LIMIT %s
                """,
                (TEST_TENANT_ID, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "camera_id": str(r[1]) if r[1] else None,
            "evidence_key": r[2],
            "confidence": float(r[3]) if r[3] else None,
            "created_at": r[4].isoformat() if r[4] else None,
            "camera_name": r[5],
        }
        for r in rows
    ]


def _dispatch_inference_tasks(cameras: list[dict], model_path: str) -> int:
    """Despacha inference_loop para cada câmera via Celery. Retorna nº despachadas."""
    dispatched = 0
    try:
        from app.infrastructure.queue.tasks.inference import inference_loop  # noqa: PLC0415
        for cam in cameras:
            inference_loop.apply_async(
                kwargs={
                    "camera_id": cam["id"],
                    "rtsp_url": cam["rtsp_url"],
                },
                queue="inference",
            )
            dispatched += 1
        logger.info("test_console_dispatched: %d tasks para inference queue", dispatched)
    except Exception as exc:
        logger.warning("test_console_dispatch_skip: %s — worker ausente?", exc)
    return dispatched


# ── Endpoints ─────────────────────────────────────────────────────────────────

@test_console_bp.post("/harness/start")
@jwt_required()
@require_admin
def harness_start():
    """
    Inicia o harness de teste: registra N câmeras, ativa streams, despacha inferência.

    Body JSON:
      {
        "cameras": 4,          // obrigatório, 1-28
        "model_id": "uuid"     // opcional — usa modelo padrão do tenant de teste
      }
    """
    body = request.get_json(silent=True) or {}
    n = int(body.get("cameras", 4))
    model_id = body.get("model_id")

    if not (1 <= n <= MAX_TEST_CAMERAS):
        return error(f"cameras deve ser entre 1 e {MAX_TEST_CAMERAS}", 400)

    # Verificar se já há harness ativo
    r = _get_redis()
    existing = r.get(REDIS_CONFIG_KEY)
    if existing:
        cfg = json.loads(existing)
        return error(
            f"Harness já ativo com {len(cfg.get('camera_ids', []))} câmeras. "
            "Chame /harness/stop antes de iniciar novo teste.",
            409,
        )

    # Resolver model_id se não fornecido (usa default do tenant)
    if not model_id:
        models = _list_models()
        default = next((m for m in models if m["is_default"]), None)
        if default:
            model_id = default["id"]

    # Registrar câmeras no banco
    cameras = _register_test_cameras(n, model_id)
    if not cameras:
        return error("Falha ao registrar câmeras de teste no banco", 500)

    camera_ids = [c["id"] for c in cameras]

    # Ativar streams no Redis (inference_loop checa essa chave)
    pipeline = r.pipeline()
    for cam_id in camera_ids:
        pipeline.setex(REDIS_STREAM_KEY.format(camera_id=cam_id), REDIS_TTL_SECONDS, "1")

    # Salvar config do harness
    config = {
        "camera_ids": camera_ids,
        "model_id": model_id,
        "n_cameras": n,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "rtsp_template": RTSP_TEMPLATE,
    }
    pipeline.setex(REDIS_CONFIG_KEY, REDIS_TTL_SECONDS, json.dumps(config))
    pipeline.execute()

    # Despachar tarefas Celery
    model_path = os.environ.get("DETECTOR_MODEL_PATH", "models/yolox_s.onnx")
    dispatched = _dispatch_inference_tasks(cameras, model_path)

    logger.info(
        "test_console_start: n=%d model_id=%s dispatched=%d tenant=%s",
        n, model_id, dispatched, TEST_TENANT_ID,
    )

    return success({
        "status": "started",
        "n_cameras": n,
        "model_id": model_id,
        "camera_ids": camera_ids,
        "tasks_dispatched": dispatched,
        "rtsp_template": RTSP_TEMPLATE,
        "violation_classes": os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves"),
        "tenant_id": TEST_TENANT_ID,
    })


@test_console_bp.post("/harness/stop")
@jwt_required()
@require_admin
def harness_stop():
    """Para o harness: desativa streams, remove câmeras de teste do banco."""
    r = _get_redis()
    raw = r.get(REDIS_CONFIG_KEY)
    if not raw:
        return error("Nenhum harness ativo no momento", 404)

    config = json.loads(raw)
    camera_ids = config.get("camera_ids", [])

    # Desativar streams (inference_loop para ao detectar ausência da chave)
    pipeline = r.pipeline()
    for cam_id in camera_ids:
        pipeline.delete(REDIS_STREAM_KEY.format(camera_id=cam_id))
    pipeline.delete(REDIS_CONFIG_KEY)
    pipeline.execute()

    # Limpar câmeras do banco
    deleted = _delete_test_cameras(camera_ids)

    logger.info(
        "test_console_stop: cameras=%d db_deleted=%d tenant=%s",
        len(camera_ids), deleted, TEST_TENANT_ID,
    )

    return success({
        "status": "stopped",
        "cameras_stopped": len(camera_ids),
        "cameras_deleted_from_db": deleted,
    })


@test_console_bp.get("/status")
@jwt_required()
@require_admin
def harness_status():
    """Retorna estado atual do harness: câmeras ativas, métricas, alertas recentes."""
    r = _get_redis()
    raw = r.get(REDIS_CONFIG_KEY)

    if not raw:
        return success({"active": False, "message": "Nenhum harness em execução"})

    config = json.loads(raw)
    camera_ids = config.get("camera_ids", [])

    # Checar quais streams ainda estão ativos no Redis
    active_streams = []
    for cam_id in camera_ids:
        if r.exists(REDIS_STREAM_KEY.format(camera_id=cam_id)):
            active_streams.append(cam_id)

    # Contar alertas gerados desde o início do teste
    alert_count = 0
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM alerts WHERE tenant_id = %s AND created_at >= %s",
                    (TEST_TENANT_ID, config.get("started_at", "1970-01-01")),
                )
                row = cur.fetchone()
                alert_count = row[0] if row else 0
    except Exception as exc:
        logger.warning("test_console_status_alert_count_failed: %s", exc)

    return success({
        "active": True,
        "n_cameras": config.get("n_cameras"),
        "started_at": config.get("started_at"),
        "model_id": config.get("model_id"),
        "active_streams": len(active_streams),
        "total_cameras": len(camera_ids),
        "alerts_generated": alert_count,
        "rtsp_template": config.get("rtsp_template"),
        "tenant_id": TEST_TENANT_ID,
        "violation_classes": os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves"),
    })


@test_console_bp.get("/models")
@jwt_required()
@require_admin
def list_models():
    """Lista modelos disponíveis no registry do tenant de teste."""
    try:
        models = _list_models()
    except Exception as exc:
        logger.error("test_console_models_error: %s", exc)
        return error("Erro ao consultar registry de modelos", 500)

    return success({"models": models, "count": len(models)})


@test_console_bp.get("/evidence")
@jwt_required()
@require_admin
def list_evidence():
    """Lista evidências (chaves R2) geradas durante o teste."""
    limit = min(int(request.args.get("limit", 20)), 100)
    try:
        items = _list_recent_evidence(limit=limit)
    except Exception as exc:
        logger.error("test_console_evidence_error: %s", exc)
        return error("Erro ao consultar evidências", 500)

    return success({"evidence": items, "count": len(items)})


# ── Seed do tenant de teste ───────────────────────────────────────────────────

_TEST_TENANT_NAME  = "Tenant de Teste CI (task-055a)"
_TEST_TENANT_SLUG  = "test-epi-ci"
_TEST_USER_EMAIL   = "test-admin@epi-ci.internal"
_TEST_USER_NAME    = "CI Test Admin"
_TEST_USER_ROLE    = "admin"
_DEFAULT_TEST_PASS = "ci-test-password-2026"


@test_console_bp.post("/seed")
@jwt_required()
@require_admin
def seed_test_tenant():
    """
    Semeia o tenant de teste isolado no banco de staging.

    Idempotente — seguro chamar múltiplas vezes (ON CONFLICT DO UPDATE/NOTHING).
    Requer role admin/superadmin. Nunca cria dados em tenants reais.
    """
    import bcrypt  # noqa: PLC0415

    body = request.get_json(silent=True) or {}
    test_password = body.get("password", _DEFAULT_TEST_PASS)

    try:
        pwd_hash = bcrypt.hashpw(
            test_password.encode(), bcrypt.gensalt(rounds=10)
        ).decode()
    except Exception as exc:
        logger.warning("seed_bcrypt_failed: %s — using sha256 fallback", exc)
        import hashlib  # noqa: PLC0415
        sha = hashlib.sha256(test_password.encode()).hexdigest()
        pwd_hash = f"sha256:{sha}"

    pool = _get_pool()
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Tenant
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (id) DO UPDATE
                    SET name = EXCLUDED.name, slug = EXCLUDED.slug
                RETURNING id, slug
                """,
                (TEST_TENANT_ID, _TEST_TENANT_NAME, _TEST_TENANT_SLUG),
            )
            tenant_row = cur.fetchone()

            # 2. tenant_module epi
            cur.execute(
                """
                INSERT INTO tenant_modules (tenant_id, module_code, enabled)
                VALUES (%s, 'epi', TRUE)
                ON CONFLICT (tenant_id, module_code) DO UPDATE SET enabled = TRUE
                """,
                (TEST_TENANT_ID,),
            )

            # 3. Usuário admin de teste
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash, name, role, tenant_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO UPDATE
                    SET name = EXCLUDED.name,
                        role = EXCLUDED.role,
                        tenant_id = EXCLUDED.tenant_id,
                        is_active = TRUE,
                        password_hash = EXCLUDED.password_hash
                RETURNING id, email, role
                """,
                (
                    str(uuid.uuid4()), _TEST_USER_EMAIL, pwd_hash,
                    _TEST_USER_NAME, _TEST_USER_ROLE, TEST_TENANT_ID,
                ),
            )
            user_row = cur.fetchone()

        conn.commit()

    logger.info(
        "seed_test_tenant: tenant_id=%s user=%s", TEST_TENANT_ID, _TEST_USER_EMAIL
    )
    return success({
        "seeded": True,
        "tenant_id":  TEST_TENANT_ID,
        "tenant_slug": tenant_row[1] if tenant_row else _TEST_TENANT_SLUG,
        "user_email": user_row[1] if user_row else _TEST_USER_EMAIL,
        "user_role":  user_row[2] if user_row else _TEST_USER_ROLE,
        "login_email": _TEST_USER_EMAIL,
        "login_password_hint": "(body.password ou 'ci-test-password-2026')",
    })
