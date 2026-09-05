"""
Recognition — Modules Routes.

Endpoints de módulos multi-tenant: listing, classes e stats.
"""
import logging
from datetime import UTC, datetime, timedelta

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import NotFoundError
from app.core.responses import error, success
from app.core.tenant_context import require_superadmin_or_404
from app.domain.services.module_service import module_service
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

modules_bp = Blueprint("modules", __name__, url_prefix="/api/modules")

#: Janela do `compliance_rate` — a MESMA de `module_service.get_stats`
#: (`day_ago = now - 24h`). O guard tem de olhar exatamente a mesma janela do
#: número que ele nega, senão vira uma segunda opinião sobre o mesmo período.
_JANELA_CONFORMIDADE_HORAS = 24

#: Por que o score não pôde ser calculado. Chave estável para a tela escolher
#: a frase — a tela nunca deve deduzir a razão do valor `null`.
RAZAO_SEM_CAMERA = "sem_cameras_ativas"
RAZAO_SEM_SINAL = "sem_sinal_no_periodo"
RAZAO_NAO_APURADA = "nao_foi_possivel_apurar"


def _houve_ingestao(tenant_id: str, module_code: str) -> bool | None:
    """Chegou ALGUM alerta do módulo nas últimas 24 h? `None` = não deu para saber.

    Fonte de propósito igual à do NUMERADOR do score (`alerts`, mesma janela,
    mesmo `module_code`): o guard não pode ter opinião própria sobre o que é
    "sinal", senão a tela ganha uma terceira contagem para não fechar.

    Qualquer alerta serve — inclusive conformidade (EPI em uso). A pergunta
    aqui não é "houve violação", é "o módulo estava OLHANDO"; um turno inteiro
    sem uma linha sequer é ausência de observação, não conformidade perfeita.
    """
    pool = DatabasePool.get_instance()
    if pool is None:
        return None
    agora = datetime.now(tz=UTC)
    try:
        vistos = AlertRepository(pool).count_in_window(
            tenant_id=tenant_id,
            from_ts=agora - timedelta(hours=_JANELA_CONFORMIDADE_HORAS),
            to_ts=agora,
            module_code=module_code,
        )
    except Exception as exc:
        logger.warning(
            "compliance_ingestao_check_error: tenant=%s module=%s err=%s",
            tenant_id, module_code, exc,
        )
        return None
    return vistos > 0


def _com_score_honesto(stats: dict, tenant_id: str, module_code: str) -> dict:
    """Anula `compliance_rate` quando ele afirmaria mais do que se sabe.

    O score é `100 × (1 − horas-câmera-com-violação ÷ (câmeras ativas × 24))`.
    O denominador SUPÕE que cada câmera ativa foi monitorada 24 h — ninguém
    mede horas monitoradas. Quando nada chegou na janela, o que o sistema
    observou foram ZERO horas, e zero violação em zero hora não é 100 % de
    conformidade: é ausência de medição.

    MEDIDO no DEV (2026-09-05, tenant RVB, `GET /api/modules/epi/stats`):
    `alerts_today=0`, `alerts_last_hour=0`, nenhum alerta nas últimas 24 h —
    e mesmo assim `compliance_rate=100.0`, que a tela pintava de VERDE com a
    palavra "Conforme". 100 sobre o vazio é o número mais caro que este painel
    pode imprimir: ele diz ao gestor que a fábrica está em ordem exatamente no
    caso em que o sistema não estava vendo nada.

    Falha ao apurar também anula — mesma doutrina do `_FALHOU` em
    `module_service.get_stats`: consulta que não respondeu não vira 100.
    """
    if stats.get("compliance_rate") is None:
        # `get_stats` já anulou (sem câmera ativa, ou a consulta de horas
        # falhou). Só nomeia a razão; não recalcula nada.
        stats.setdefault(
            "compliance_reason",
            RAZAO_SEM_CAMERA if not stats.get("cameras_active") else RAZAO_NAO_APURADA,
        )
        return stats

    houve = _houve_ingestao(tenant_id, module_code)
    if houve is True:
        stats["compliance_reason"] = None
        return stats

    stats["compliance_rate"] = None
    stats["compliance_by_class"] = {}
    stats["compliance_reason"] = RAZAO_SEM_SINAL if houve is False else RAZAO_NAO_APURADA
    return stats


@modules_bp.route("/", methods=["GET"])
@jwt_required()
def list_modules():  # type: ignore[no-untyped-def]
    """Lista módulos do tenant com stats básicas."""
    try:
        tenant_id = get_tenant_id()
        modules = module_service.list_tenant_modules(tenant_id)
        return success({"modules": modules})
    except Exception as exc:
        logger.error("list_modules_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>", methods=["GET"])
@jwt_required()
def get_module(module_code: str):  # type: ignore[no-untyped-def]
    """Retorna detalhes de um módulo do tenant."""
    try:
        tenant_id = get_tenant_id()
        module = module_service.get_module(tenant_id, module_code)
        if not module:
            return error("Módulo não encontrado", 404)
        return success({"module": module})
    except Exception as exc:
        logger.error("get_module_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/classes", methods=["GET"])
@jwt_required()
def get_module_classes(module_code: str):  # type: ignore[no-untyped-def]
    """Lista classes YOLO do módulo: catálogo global ∪ custom do tenant do
    contexto (get_tenant_id() — honra contexto assumido, C-01/ADR-0017).

    `?include_archived=1` inclui classes do tenant arquivadas (archived_at
    preenchido) — a tela de gestão de classes (estúdio de anotação) precisa
    delas para oferecer "restaurar"; o anotador em si nunca passa esse
    param, então continua sem ofertar classe aposentada para escolha nova.
    """
    from flask import request  # noqa: PLC0415

    try:
        tenant_id = get_tenant_id()
        include_archived = request.args.get("include_archived", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        classes = module_service.get_classes(
            module_code, tenant_id=tenant_id, include_archived=include_archived
        )
        return success({"classes": classes})
    except Exception as exc:
        logger.error("get_module_classes_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/stats", methods=["GET"])
@jwt_required()
def get_module_stats(module_code: str):  # type: ignore[no-untyped-def]
    """Estatísticas do módulo para o tenant.

    `compliance_rate` sai por `_com_score_honesto`: `null` (com
    `compliance_reason`) sempre que o número afirmaria mais do que se sabe —
    sem câmera ativa, sem sinal de ingestão na janela, ou consulta que não
    respondeu. Este é o ÚNICO endpoint que publica o score.
    """
    try:
        tenant_id = get_tenant_id()
        if not module_service.tenant_has_module(tenant_id, module_code):
            return error("Módulo não disponível", 403)
        stats = module_service.get_stats(tenant_id, module_code)
        return success({"stats": _com_score_honesto(stats, tenant_id, module_code)})
    except Exception as exc:
        logger.error("get_module_stats_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/classes/<class_id>", methods=["PATCH"])
@jwt_required()
@require_superadmin_or_404
def toggle_module_class(module_code: str, class_id: str):  # type: ignore[no-untyped-def]
    """Ativa ou desativa uma classe do módulo — SÓ superadmin.

    public.module_classes é catálogo GLOBAL de plataforma (sem tenant_id):
    antes, o gate `modules:write` (admin/superadmin) deixava um admin de um
    tenant desativar a classe para TODOS os tenants. Não-superadmin → 404
    (mesma convenção do blueprint para módulo não habilitado; nunca 403 —
    C-01). Classes custom por tenant vivem em /api/classes. Mantido o
    isolamento task-073: módulo não habilitado para o tenant do contexto ou
    class_id de outro module_code → 404.
    """
    from flask import request  # noqa: PLC0415

    try:
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        is_active = bool(data.get("is_active", True))
        cls = module_service.toggle_class(tenant_id, module_code, class_id, is_active)
        return success({"class": cls})
    except NotFoundError:
        raise
    except Exception as exc:
        logger.error("toggle_class_error: class=%s err=%s", class_id, exc, exc_info=True)
        return error("Erro interno", 500)
