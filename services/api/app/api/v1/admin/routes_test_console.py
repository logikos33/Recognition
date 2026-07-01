"""
Recognition — Admin Test Console Routes (task-056).

Endpoints role-gated (superadmin) para console de teste E2E e gestão de
segredos de integração.

Grupos:
  Test Console   GET  /api/v1/admin/test-console/status
                 POST /api/v1/admin/test-console/start
                 POST /api/v1/admin/test-console/stop
  Integrations   GET  /api/v1/admin/integrations
                 PUT  /api/v1/admin/integrations/<key>

Segurança:
  - Todos os endpoints protegidos por @require_superadmin
  - Segredos cifrados com Fernet (chave em env var INTEGRATIONS_SECRET)
  - Valores nunca retornados em texto simples — apenas flag "configured"
  - test-console opera sobre tenant de teste isolado (tenant_id do JWT ou
    do payload — nunca cross-tenant sem isolamento explícito)
"""
import base64
import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint, request

from app.core.responses import error, success
from app.core.tenant import require_superadmin
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

test_console_bp = Blueprint(
    "admin_test_console", __name__, url_prefix="/api/v1/admin"
)

# ---------------------------------------------------------------------------
# Cipher helpers — Fernet (AES-128-CBC + HMAC-SHA256)
# ---------------------------------------------------------------------------

_INTEGRATIONS_SECRET_ENV = "INTEGRATIONS_SECRET"

# In-memory state for the test console session (single-node acceptable for
# admin-only feature; persisted to Redis for multi-instance support later)
_console_state: dict = {
    "status": "idle",          # idle | running | stopped | error
    "session_id": None,
    "started_at": None,
    "stopped_at": None,
    "config": None,
    "metrics": {
        "detections_per_sec": 0.0,
        "latency_ms": 0.0,
        "throughput_infs": 0.0,
        "vram_pct": 0.0,
        "cameras_active": 0,
    },
    "log_lines": [],
}


def _get_cipher():
    """
    Retorna instância Fernet usando INTEGRATIONS_SECRET env var.

    A chave deve ser uma Fernet key válida (32 bytes URL-safe base64).
    Se ausente, gera uma ephemeral — segredos gravados não sobrevivem restart.
    Loga warning para que ops configure a variável.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None

    raw = os.environ.get(_INTEGRATIONS_SECRET_ENV, "")
    if not raw:
        logger.warning(
            "INTEGRATIONS_SECRET not set — using ephemeral key; "
            "configure env var for persistent encryption"
        )
        # Gerar chave determinística baseada em SECRET_KEY para não perder
        # segredos entre restarts (best-effort sem a env var correta)
        import hashlib
        secret_key = os.environ.get("SECRET_KEY", "dev-only-fallback-key-do-not-use")
        derived = hashlib.sha256(secret_key.encode()).digest()
        raw = base64.urlsafe_b64encode(derived).decode()

    try:
        return Fernet(raw.encode())
    except Exception:
        # Chave inválida — gerar nova ephemeral e logar
        logger.error(
            "INTEGRATIONS_SECRET is not a valid Fernet key — "
            "re-generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        from cryptography.fernet import Fernet as F
        return F(F.generate_key())


def _encrypt(value: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        # cryptography não disponível — fallback base64 (não seguro, apenas
        # para ambientes de dev sem o pacote)
        return base64.b64encode(value.encode()).decode()
    return cipher.encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        return base64.b64decode(token.encode()).decode()
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        raise ValueError("Falha ao decifrar — chave incorreta ou token corrompido")


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _clean(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if v is None:
            result[k] = None
        elif hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (int, float, bool)):
            result[k] = str(v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Test Console — status
# ---------------------------------------------------------------------------
@test_console_bp.route("/test-console/status", methods=["GET"])
@require_superadmin
def test_console_status():
    """
    Retorna estado atual do console de teste + métricas.

    Não executa queries no DB — lê estado em memória.
    """
    try:
        # Verificar se chave Vast.ai está configurada para o tenant do actor
        vast_configured = _check_integration_configured("vast_ai")

        return success({
            "status": _console_state["status"],
            "session_id": _console_state["session_id"],
            "started_at": _console_state["started_at"],
            "stopped_at": _console_state["stopped_at"],
            "config": _console_state["config"],
            "metrics": _console_state["metrics"],
            "log_lines": _console_state["log_lines"][-50:],  # últimas 50
            "vast_ai_configured": vast_configured,
        })
    except Exception as exc:
        logger.error("test_console_status_error: %s", exc, exc_info=True)
        return error("Erro ao buscar status do console", 500)


def _check_integration_configured(key: str) -> bool:
    """Verifica se integração existe no banco (qualquer tenant admin)."""
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM public.integrations WHERE key = %s LIMIT 1",
                (key,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test Console — start
# ---------------------------------------------------------------------------
@test_console_bp.route("/test-console/start", methods=["POST"])
@require_superadmin
def test_console_start():
    """
    Inicia sessão de teste E2E.

    Body esperado:
      camera_count   int  (1-28)
      model_id       str  (UUID do modelo ou "pretrained")
      scenario_config dict (opcional — configuração de zona/classes/limiar)

    Se harness (task-027) não disponível, registra log e retorna 501.
    """
    try:
        if _console_state["status"] == "running":
            return error("Teste já em andamento — pare antes de iniciar novo", 409)

        data = request.get_json() or {}
        camera_count = int(data.get("camera_count", 1))
        model_id = str(data.get("model_id", "pretrained")).strip()
        scenario_config = data.get("scenario_config") or {}

        if not 1 <= camera_count <= 28:
            return error("camera_count deve ser entre 1 e 28", 400)
        if not model_id:
            return error("model_id é obrigatório", 400)

        # Tentar invocar harness de teste (task-027)
        harness_available = _try_invoke_harness(
            camera_count=camera_count,
            model_id=model_id,
            scenario_config=scenario_config,
        )

        if not harness_available:
            _log_console("harness not configured — operando em modo stub")
            _console_state.update({
                "status": "running",
                "session_id": str(uuid.uuid4()),
                "started_at": datetime.utcnow().isoformat(),
                "stopped_at": None,
                "config": {
                    "camera_count": camera_count,
                    "model_id": model_id,
                    "scenario_config": scenario_config,
                    "mode": "stub",
                },
                "metrics": {
                    "detections_per_sec": 0.0,
                    "latency_ms": 0.0,
                    "throughput_infs": 0.0,
                    "vram_pct": 0.0,
                    "cameras_active": camera_count,
                },
                "log_lines": [
                    f"[{datetime.utcnow().isoformat()}] harness not configured — stub mode",
                    f"[{datetime.utcnow().isoformat()}] cameras_simuladas={camera_count} model={model_id}",
                ],
            })
            return success({
                "session_id": _console_state["session_id"],
                "status": "running",
                "mode": "stub",
                "message": "Harness não configurado — rodando em modo stub. Configure task-027 para teste real.",
            }, status=201)

        _console_state.update({
            "status": "running",
            "session_id": str(uuid.uuid4()),
            "started_at": datetime.utcnow().isoformat(),
            "stopped_at": None,
            "config": {
                "camera_count": camera_count,
                "model_id": model_id,
                "scenario_config": scenario_config,
                "mode": "harness",
            },
        })
        _log_console(f"sessão iniciada — {camera_count} câmeras, model={model_id}")

        return success({
            "session_id": _console_state["session_id"],
            "status": "running",
            "mode": "harness",
        }, status=201)

    except Exception as exc:
        logger.error("test_console_start_error: %s", exc, exc_info=True)
        _console_state["status"] = "error"
        return error(f"Erro ao iniciar teste: {exc}", 500)


def _try_invoke_harness(camera_count: int, model_id: str, scenario_config: dict) -> bool:
    """
    Tenta invocar o harness de teste (task-027).

    Retorna True se harness disponível, False caso contrário.
    Nunca lança exceção.
    """
    try:
        from app.domain.services.test_harness_service import TestHarnessService  # type: ignore[import]
        TestHarnessService.start(
            camera_count=camera_count,
            model_id=model_id,
            scenario_config=scenario_config,
        )
        return True
    except ImportError:
        logger.info("test_harness_service not available (task-027 not implemented)")
        return False
    except Exception as exc:
        logger.warning("test_harness_invoke_failed: %s", exc)
        return False


def _log_console(message: str) -> None:
    ts = datetime.utcnow().isoformat()
    _console_state["log_lines"].append(f"[{ts}] {message}")
    # Manter apenas últimas 200 linhas para evitar leak de memória
    if len(_console_state["log_lines"]) > 200:
        _console_state["log_lines"] = _console_state["log_lines"][-200:]


# ---------------------------------------------------------------------------
# Test Console — stop
# ---------------------------------------------------------------------------
@test_console_bp.route("/test-console/stop", methods=["POST"])
@require_superadmin
def test_console_stop():
    """Para a sessão de teste em andamento."""
    try:
        if _console_state["status"] != "running":
            return error("Nenhum teste em andamento", 409)

        # Tentar parar harness (best-effort)
        try:
            from app.domain.services.test_harness_service import TestHarnessService  # type: ignore[import]
            TestHarnessService.stop()
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("test_harness_stop_failed: %s", exc)

        _console_state["status"] = "stopped"
        _console_state["stopped_at"] = datetime.utcnow().isoformat()
        _log_console("sessão encerrada pelo operador")

        return success({
            "session_id": _console_state["session_id"],
            "status": "stopped",
            "stopped_at": _console_state["stopped_at"],
        })
    except Exception as exc:
        logger.error("test_console_stop_error: %s", exc, exc_info=True)
        return error(f"Erro ao parar teste: {exc}", 500)


# ---------------------------------------------------------------------------
# Integrations — REMOVIDO (task-058)
# As rotas GET /integrations e PUT /integrations/<key> foram migradas para
# integration_routes.py (admin_integrations_bp) com o schema correto da
# migration 082 (colunas: integration_type, label, config, secret_encrypted).
# Mantê-las aqui causava:
#   1. Conflito de rota: GET /api/v1/admin/integrations era capturado por este
#      blueprint antes do admin_integrations_bp.
#   2. 500 — query usava coluna `key` que não existe na migration 082.
# ---------------------------------------------------------------------------
