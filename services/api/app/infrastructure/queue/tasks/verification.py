"""
Recognition — AI Verification Task.

Pré-filtra alertas de baixa confiança usando Claude claude-haiku-4-5-20251001.
Reduz a fila humana ao essencial — somente casos genuinamente ambíguos chegam ao operador.

Fluxo:
  1. socket_bridge detecta violação com confidence < VERIFICATION_THRESHOLD
  2. Cria alerta no DB com verification_status='pending'
  3. Dispara esta task via Celery
  4. Claude analisa: approve / reject / needs_human
  5. Atualiza alerts.verification_status no DB

Env vars:
  ANTHROPIC_API_KEY           — obrigatório para chamada Claude
  VERIFICATION_THRESHOLD      — float (default 0.85)
"""
import json
import logging
import os
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

VERIFICATION_THRESHOLD = float(os.environ.get("VERIFICATION_THRESHOLD", "0.85"))
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

_VERDICT_PROMPT = """\
Você é um agente de verificação de segurança que analisa detecções automáticas de EPIs (Equipamentos de Proteção Individual) em câmeras industriais.

Detecção recebida:
- Câmera ID: {camera_id}
- Classe detectada: {class_name}
- Confiança do modelo: {confidence_pct}%
- Módulo de segurança: {module_code}

Regra: classes que começam com "no_" indicam violação (ex: no_helmet = sem capacete).

Analise se esta detecção provavelmente representa uma violação real ou é um falso positivo do modelo.

Responda SOMENTE com JSON válido, sem markdown, sem texto adicional:
{{
  "verdict": "approve" | "reject" | "needs_human",
  "reason": "explicação breve em português",
  "adjusted_confidence": 0.0
}}

Diretrizes:
- "approve": detecção é provavelmente correta (salvar como alerta real)
- "reject": provavelmente falso positivo (descartar)
- "needs_human": caso ambíguo que exige revisão humana
- Se confiança < 40%: tenda para "reject"
- Se confiança 40-65%: tenda para "needs_human"
- Se confiança 65-85%: tenda para "approve" ou "needs_human" conforme contexto
"""


def _call_claude(camera_id: str, class_name: str, confidence: float, module_code: str) -> dict:
    """Chama Claude claude-haiku-4-5-20251001 para análise de detecção."""
    if not _ANTHROPIC_KEY:
        logger.warning("anthropic_key_missing: defaulting to needs_human")
        return {"verdict": "needs_human", "reason": "API key não configurada", "adjusted_confidence": confidence}

    try:
        import anthropic  # noqa: PLC0415
        client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)

        prompt = _VERDICT_PROMPT.format(
            camera_id=camera_id,
            class_name=class_name,
            confidence_pct=round(confidence * 100, 1),
            module_code=module_code,
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        result = json.loads(raw)
        result.setdefault("verdict", "needs_human")
        result.setdefault("reason", "")
        result.setdefault("adjusted_confidence", confidence)
        return result

    except json.JSONDecodeError as exc:
        logger.error("claude_json_parse_error: %s", exc)
        return {"verdict": "needs_human", "reason": "Erro ao parsear resposta IA", "adjusted_confidence": confidence}
    except Exception as exc:
        logger.error("claude_call_error: %s", exc)
        return {"verdict": "needs_human", "reason": f"Erro IA: {exc}", "adjusted_confidence": confidence}


def _update_alert_verification(alert_id: str, verdict: str, reason: str, confidence: float) -> None:
    """Atualiza verification_status da alerta no DB."""
    status_map = {
        "approve": "auto_approved",
        "reject": "auto_rejected",
        "needs_human": "needs_human",
    }
    verification_status = status_map.get(verdict, "needs_human")

    try:
        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("verification_update_skipped: pool not ready")
            return

        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE alerts SET "
                "verification_status = %s, verification_verdict = %s, "
                "verification_reason = %s, verified_at = NOW(), verified_by = 'claude-haiku' "
                "WHERE id = %s",
                (verification_status, verdict, reason, alert_id),
            )
        logger.info("alert_verified: id=%s status=%s", alert_id, verification_status)
    except Exception as exc:
        logger.error("alert_verification_update_error: alert=%s err=%s", alert_id, exc)


@celery.task(
    bind=True,
    max_retries=2,
    queue="inference",
    name="tasks.verification.verify_alert",
    acks_late=True,
)
def verify_alert(
    self,
    alert_id: str,
    camera_id: str,
    class_name: str,
    confidence: float,
    module_code: str = "epi",
) -> dict:
    """Verifica alerta de baixa confiança com Claude claude-haiku-4-5-20251001.

    Returns dict com verdict e reason.
    """
    logger.info(
        "verify_alert_start: alert=%s class=%s confidence=%.2f",
        alert_id, class_name, confidence,
    )

    try:
        result = _call_claude(camera_id, class_name, confidence, module_code)
        _update_alert_verification(
            alert_id,
            verdict=result["verdict"],
            reason=result["reason"],
            confidence=result["adjusted_confidence"],
        )
        logger.info(
            "verify_alert_done: alert=%s verdict=%s",
            alert_id, result["verdict"],
        )
        return result

    except Exception as exc:
        logger.error("verify_alert_error: alert=%s err=%s", alert_id, exc)
        try:
            _update_alert_verification(alert_id, "needs_human", f"Erro: {exc}", confidence)
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
