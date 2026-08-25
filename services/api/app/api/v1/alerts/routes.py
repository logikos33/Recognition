"""
Recognition — Alerts Routes.

Lista, filtra, exporta e reconhece alertas de violações de EPI.
"""
import csv
import io
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


def _get_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _parse_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    return s.lower() in ("true", "1", "yes")


def _parse_kind(s: str | None) -> str | None:
    """?kind= (ADR-0063). Valor inválido → None (= todos). Nunca 500 por querystring."""
    return s if s in ("violation", "compliance") else None


def _iso_utc(value):  # type: ignore[no-untyped-def]
    """Data de alerta → ISO 8601 UTC com sufixo Z. Não-datetime passa intacto.

    O ÚNICO formato de data que este blueprint emite. Antes cada rota escolhia
    o seu: a lista caía no jsonify do Flask (RFC 822, "…GMT") e o detalhe usava
    `isoformat()` de um TIMESTAMP naive (SEM offset) — o browser lê o segundo
    como hora LOCAL e o MESMO alerta aparecia com 3h de diferença entre lista e
    detalhe. Naive é tratado como UTC: é o que o NOW() do banco grava, e é o
    mesmo pressuposto do http_date do Flask (que carimbava "GMT" na lista).
    """
    if not isinstance(value, datetime):
        return value
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def _serialize_dates(row: dict) -> dict:
    """Aplica `_iso_utc` em todo valor datetime da linha (created_at, timestamp, …)."""
    return {k: _iso_utc(v) for k, v in row.items()}


@alerts_bp.route("", methods=["GET"])
@jwt_required()
def list_alerts():  # type: ignore[no-untyped-def]
    """Lista alertas com filtros e paginação."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        offset = (page - 1) * per_page

        result = _get_repo().list_with_filters(
            tenant_id=get_tenant_id(),
            limit=per_page,
            offset=offset,
            camera_id=request.args.get("camera_id"),
            start_date=_parse_date(request.args.get("start_date")),
            end_date=_parse_date(request.args.get("end_date")),
            violation_type=request.args.get("violation_type"),
            acknowledged=_parse_bool(request.args.get("acknowledged")),
            kind=_parse_kind(request.args.get("kind")),
        )

        total = result["total"]
        return success({
            # Datas em ISO 8601 UTC (Z) — o MESMO formato do detalhe. Sem isto o
            # jsonify emitiria RFC 822 aqui e a mesma linha teria dois formatos.
            "alerts": [_serialize_dates(a) for a in result["items"]],
            "count": len(result["items"]),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/export", methods=["GET"])
@jwt_required()
def export_alerts():  # type: ignore[no-untyped-def]
    """Exporta alertas para CSV."""
    try:
        result = _get_repo().list_with_filters(
            tenant_id=get_tenant_id(),
            limit=10000,
            offset=0,
            camera_id=request.args.get("camera_id"),
            start_date=_parse_date(request.args.get("start_date")),
            end_date=_parse_date(request.args.get("end_date")),
            violation_type=request.args.get("violation_type"),
            acknowledged=_parse_bool(request.args.get("acknowledged")),
            # O CSV exporta o MESMO recorte que a tela mostra (ADR-0063).
            kind=_parse_kind(request.args.get("kind")),
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Data", "Câmera", "Tipo de Violação", "Confiança", "Reconhecido"])

        for alert in result["items"]:
            violations = alert.get("violations") or []
            if not violations:
                violations = [{}]
            # Coluna "Data" = a MESMA que a tela mostra: hora de CAPTURA
            # (`timestamp`), com fallback para `created_at`. Exportar created_at
            # enquanto a tela exibe timestamp faz CSV e tela discordarem da
            # mesma linha. Formato idêntico ao da API (ISO 8601 UTC, Z).
            data = _iso_utc(alert.get("timestamp") or alert.get("created_at") or "")
            for v in violations:
                writer.writerow([
                    data,
                    alert.get("camera_name", ""),
                    v.get("class", ""),
                    f"{v.get('confidence', 0):.0%}" if v.get("confidence") else "",
                    "Sim" if alert.get("acknowledged") else "Não",
                ])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=alertas.csv"},
        )
    except Exception as exc:
        logger.error("export_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/usage-rate", methods=["GET"])
@jwt_required()
def usage_rate():  # type: ignore[no-untyped-def]
    """Taxa de uso de EPI por área (ADR-0063): conformidades × violações.

    EPI PRESENTE é telemetria, não evento alertável — este é o painel que a
    consome. A divisão fica na tela; aqui só saem contagens.

    Rota estática declarada ANTES de `/<alert_id>` de propósito: leitura
    humana. (Werkzeug já prioriza regra sem argumento, mas a ordem no arquivo
    evita a dúvida na próxima leitura.)
    """
    try:
        # tz-aware, igual ao que `_parse_date` devolve — não misturar naive
        # com aware nos dois lados da janela.
        to_ts = _parse_date(request.args.get("end_date")) or datetime.now(UTC)
        from_ts = _parse_date(request.args.get("start_date")) or (to_ts - timedelta(days=7))
        rows = _get_repo().usage_rate_by_area(
            tenant_id=str(get_tenant_id()),
            from_ts=from_ts,
            to_ts=to_ts,
            module_code=request.args.get("module_code"),
        )
        return success({"areas": rows})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("usage_rate_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>", methods=["GET"])
@jwt_required()
def get_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Detalhe de UM alerta — o que a tela de evidência precisa.

    Devolve `captured_at` (coluna `timestamp` = hora REAL do evento no edge,
    com fallback para `created_at`), o nome da câmera e a URL assinada do
    FRAME INTEIRO. `violations` sai cru, com o `bbox` e o `bbox_unidade` que o
    edge gravou — a tela projeta; o backend não reinterpreta coordenada.

    Cross-tenant, id inexistente e id malformado respondem o MESMO 404 (C-01).
    Projeção explícita (não `dict(row)`): não vaza `tenant_id`/`verified_by`/
    `site_id` e datetime sai em ISO, não no RFC 822 do jsonify do Flask.
    """
    try:
        from app.infrastructure.storage.local_storage import get_storage

        try:
            parsed_id = UUID(alert_id)
        except ValueError:
            return error("Alerta não encontrado", 404)

        alert = _get_repo().get_by_id(parsed_id, tenant_id=get_tenant_id())
        if alert is None:
            return error("Alerta não encontrado", 404)

        captured = alert.get("timestamp") or alert.get("created_at")
        created = alert.get("created_at")
        evidence_url = None
        if alert.get("evidence_key"):
            try:
                evidence_url = get_storage().generate_presigned_download_url(
                    alert["evidence_key"], ttl=3600, response_content_type="image/jpeg"
                )
            except Exception:
                # Evidência indisponível não derruba a tela — câmera, hora,
                # classe e confiança ainda contam o acontecido.
                logger.warning("alert_evidence_url_failed: alert_id=%s", alert_id)

        return success({"alert": {
            "id": str(alert["id"]),
            "camera_id": str(alert["camera_id"]) if alert.get("camera_id") else None,
            "camera_name": alert.get("camera_name"),
            "violations": alert.get("violations") or [],
            "confidence": alert.get("confidence"),
            "acknowledged": bool(alert.get("acknowledged")),
            "class_name": alert.get("class_name"),
            "evidence_key": alert.get("evidence_key"),
            "evidence_url": evidence_url,
            # `_iso_utc`, não `isoformat()` cru: o TIMESTAMP do banco é naive e
            # sairia SEM offset — o browser leria como hora LOCAL (−3h em BRT).
            "captured_at": _iso_utc(captured) if captured else None,
            "created_at": _iso_utc(created) if created else None,
        }})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Marca alerta como reconhecido."""
    try:
        alert = _get_repo().acknowledge(UUID(alert_id))
        if alert is None:
            return error("Alerta não encontrado", 404)
        # Mesmo formato de data das outras rotas do blueprint.
        return success({"alert": _serialize_dates(alert)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("acknowledge_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>/snapshot", methods=["GET"])
@jwt_required()
def alert_snapshot(alert_id: str):  # type: ignore[no-untyped-def]
    """Retorna presigned URL da imagem de evidência do alerta (tenant-scoped — task-074)."""
    try:
        from app.infrastructure.storage.local_storage import get_storage
        from app.infrastructure.storage.r2_storage import R2Storage

        repo = _get_repo()
        # Busca escopada por tenant (C-01) — alerta de outro tenant nunca é
        # encontrado aqui, então cai no mesmo 404 de "alerta inexistente"
        # (evita enumeração cross-tenant via diferença de status/mensagem).
        alert = repo.get_evidence_key(UUID(alert_id), tenant_id=get_tenant_id())
        if not alert or not alert.get("evidence_key"):
            return error("Snapshot não disponível", 404)

        storage = get_storage()
        if isinstance(storage, R2Storage):
            url = storage.generate_presigned_download_url(
                alert["evidence_key"], ttl=3600, response_content_type="image/jpeg"
            )
            return success({"snapshot_url": url})

        return error("Storage local não suporta presigned URLs", 400)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("alert_snapshot_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/stats", methods=["GET"])
@jwt_required()
def alert_stats():  # type: ignore[no-untyped-def]
    """Estatísticas de alertas (tenant-scoped — BUG-6 fix)."""
    try:
        tenant_id = str(get_tenant_id())
        camera_id = request.args.get("camera_id")
        repo = _get_repo()
        count = repo.count_by_camera(UUID(camera_id), tenant_id=tenant_id) if camera_id else 0
        unack = len(repo.get_unacknowledged(
            camera_id=UUID(camera_id) if camera_id else None,
            limit=1000,
            tenant_id=tenant_id,
        ))
        return success({"total": count, "unacknowledged": unack})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("alert_stats_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
