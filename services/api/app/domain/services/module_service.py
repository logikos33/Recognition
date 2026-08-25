"""
Recognition — Module Service.

Gerencia módulos por tenant: listing, stats e verificação de acesso.
"""
import json
import logging
from datetime import UTC, datetime, timedelta

from app.domain.services.class_namespace import namespace_tenant_class_id
from app.domain.services.platform_flags import platform_flag_enabled
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository
from app.infrastructure.database.repositories.training_repository import TrainingRepository
from app.infrastructure.database.repositories.tenant_policy_repository import (
    TenantPolicyRepository,
)

logger = logging.getLogger(__name__)

#: Sentinela para "a consulta falhou", distinta de qualquer valor legítimo.
#: `None` e `0` não servem: os dois são respostas possíveis do banco, e
#: confundi-los com falha foi exatamente o defeito da taxa de conformidade.
_FALHOU = object()

ENFORCE_PLAN_LIMITS_FLAG = "enforce_plan_limits"


def _get_module_repo() -> ModuleRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return ModuleRepository(pool)


def _get_policy_repo() -> TenantPolicyRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TenantPolicyRepository(pool)


def _plan_allowed_modules(tenant_id: str) -> list[str] | None:
    """Módulos permitidos pelo plano do tenant, ou None = sem restrição.

    Fail-open: tenant/plano inexistente, modules_allowed NULL/vazio ou erro de
    leitura → None (sem restrição), com log de warning quando aplicável.
    """
    try:
        entitlements = _get_policy_repo().get_plan_entitlements(tenant_id)
    except Exception as exc:
        logger.warning("plan_entitlements_read_error: tenant=%s err=%s", tenant_id, exc)
        return None
    if not entitlements:
        return None
    allowed = entitlements.get("modules_allowed")
    if isinstance(allowed, str):
        try:
            allowed = json.loads(allowed)
        except Exception:
            logger.warning("plan_modules_allowed_parse_error: tenant=%s", tenant_id)
            return None
    if not allowed or not isinstance(allowed, list):
        # NULL/[] = sem restrição (plano sem configuração de módulos)
        return None
    return [str(m) for m in allowed]


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_alert_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _get_training_repo() -> TrainingRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TrainingRepository(pool)


def _get_annotation_repo() -> AnnotationRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AnnotationRepository(pool)


class ModuleService:
    """Lógica de negócio para módulos multi-tenant."""

    def list_tenant_modules(self, tenant_id: str) -> list:
        """Lista módulos do tenant com stats básicas.

        Com a flag 'enforce_plan_limits' ON, filtra módulos fora de
        plans.modules_allowed (fail-open: sem plano/lista vazia = sem filtro).
        """
        modules = _get_module_repo().get_by_tenant(tenant_id)
        if platform_flag_enabled(ENFORCE_PLAN_LIMITS_FLAG):
            plan_modules = _plan_allowed_modules(tenant_id)
            if plan_modules is not None:
                filtered = [m for m in modules if m.get("module_code") in plan_modules]
                if len(filtered) != len(modules):
                    logger.info(
                        "plan_limits_modules_filtered: tenant=%s antes=%d depois=%d",
                        tenant_id, len(modules), len(filtered),
                    )
                modules = filtered
        result = []
        for mod in modules:
            try:
                stats = self.get_stats(tenant_id, mod["module_code"])
            except Exception as exc:
                logger.warning("module_stats_error: module=%s err=%s", mod["module_code"], exc)
                stats = {}
            result.append({
                **mod,
                "cameras_count": stats.get("cameras_active", 0),
                "alerts_today": stats.get("alerts_today", 0),
            })
        return result

    def get_module(self, tenant_id: str, module_code: str) -> dict | None:
        """Retorna módulo específico do tenant."""
        return _get_module_repo().get_tenant_module(tenant_id, module_code)

    def tenant_has_module(self, tenant_id: str, module_code: str) -> bool:
        """Verifica se tenant tem acesso ao módulo.

        Com a flag 'enforce_plan_limits' ON, o módulo também precisa estar em
        plans.modules_allowed (fail-open: sem plano/lista vazia = sem restrição).
        """
        module = _get_module_repo().get_tenant_module(tenant_id, module_code)
        enabled = module is not None and bool(module.get("enabled"))
        if not enabled:
            return False
        if platform_flag_enabled(ENFORCE_PLAN_LIMITS_FLAG):
            plan_modules = _plan_allowed_modules(tenant_id)
            if plan_modules is not None and module_code not in plan_modules:
                logger.info(
                    "plan_limits_module_denied: tenant=%s module=%s",
                    tenant_id, module_code,
                )
                return False
        return True

    def get_classes(
        self,
        module_code: str,
        tenant_id: "str | None" = None,
        include_archived: bool = False,
    ) -> list:
        """Lista classes YOLO do módulo: catálogo global ∪ custom do tenant.

        Bug corrigido: o anotador (AnnotationInterface.jsx) lê classes daqui
        (GET /modules/<code>/classes), mas uma classe criada pelo tenant
        (POST /classes → yolo_classes) nunca entrava nesta lista — só
        module_classes (catálogo global) era consultado. Resultado: a classe
        nova "sumia" no anotador, e mesmo que aparecesse, o save era
        rejeitado (AnnotationService._validate_class só validava contra
        module_classes).

        tenant_id omitido → comportamento anterior, inalterado (só catálogo
        global, sem usage_count/archived_at/display_order) — usado pelos
        callers que não são o anotador (scenarios, demo_event_service).

        Quando informado (migration 110 — curadoria):
          - classes custom do tenant entram com `class_id` namespaced
            (class_namespace.namespace_tenant_class_id) — o índice pequeno
            0-based do catálogo nunca é reaproveitado por uma classe custom;
          - classes ARQUIVADAS (archived_at) do tenant são excluídas por
            padrão — o anotador não oferece classe aposentada para escolha
            nova. `include_archived=True` (tela de gestão de classes, que
            precisa listar arquivadas para oferecer "restaurar") inclui-as
            de volta;
          - cada item ganha `usage_count` (amostras já anotadas com essa
            classe, escopado ao tenant — AnnotationRepository.
            get_usage_counts_by_tenant) e `archived_at`/`display_order`;
          - ordenação: classes do TENANT primeiro (por display_order NULLS
            LAST — a ordem que o tenant escolheu), catálogo global depois.
            Cada item carrega `source: "module"|"tenant"`.
        """
        module_classes = _get_module_repo().get_classes(module_code)

        if not tenant_id:
            return [{**c, "source": "module"} for c in module_classes]

        usage_counts = _get_annotation_repo().get_usage_counts_by_tenant(str(tenant_id))

        module_list = [
            {
                **c,
                "source": "module",
                "archived_at": None,
                "display_order": None,
                "usage_count": usage_counts.get(c["class_id"], 0),
            }
            for c in module_classes
        ]

        tenant_classes = _get_annotation_repo().get_classes_for_tenant(
            str(tenant_id),
            module_code=module_code,
            exclude_archived=not include_archived,
            order_by_curation=True,
        )
        tenant_list = [
            {
                "id": tc["id"],
                "class_id": namespace_tenant_class_id(tc["id"]),
                "class_name": tc["name"],
                "display_name": tc["name"],
                "color": tc.get("color"),
                # ADR-0063: a polaridade é DADO (yolo_classes.is_violation,
                # migration 125), não constante. O False hardcoded fazia
                # "Sem protetor de ouvido" chegar ao frontend como se fosse
                # presença — origem da inversão do shadow EPI da RVB.
                # NULL (ninguém decidiu ainda) NUNCA vira presença.
                "is_violation": tc.get("is_violation") is True,
                "is_active": True,
                "module_code": tc.get("module_code", module_code),
                "source": "tenant",
                "archived_at": tc.get("archived_at"),
                "display_order": tc.get("display_order"),
                "usage_count": usage_counts.get(namespace_tenant_class_id(tc["id"]), 0),
            }
            for tc in tenant_classes
        ]

        # Tenant primeiro (já vem ordenado por display_order NULLS LAST do
        # repo), catálogo depois — ordenação pedida para o painel de curadoria.
        return tenant_list + module_list

    def get_stats(self, tenant_id: str, module_code: str) -> dict:
        """Estatísticas do módulo para o tenant. Cada contagem é isolada — falha individual retorna 0/None.

        Além das 4 chaves originais (mantidas — aditivo), retorna os KPIs de BI (WS3):
          - alerts_last_hour / alerts_prev_hour: alertas na hora corrente vs hora anterior
          - active_model_name / active_model_map50: modelo is_active do tenant (None se ausente)
          - compliance_rate: proxy honesto — 100*(1 - horas-câmera-com-violação /
            (cameras_active*24)) nas últimas 24h. None quando não há câmera ativa.
            Não existe tabela de detecções positivas — o denominador real é aproximado
            por horas-câmera monitoradas (fórmula exposta em tooltip na UI).
          - compliance_by_class: mesmo cálculo por classe de violação.
        """
        now = datetime.now(tz=UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        hour_ago = now - timedelta(hours=1)
        two_hours_ago = now - timedelta(hours=2)
        day_ago = now - timedelta(hours=24)

        camera_repo = _get_camera_repo()
        alert_repo = _get_alert_repo()
        training_repo = _get_training_repo()

        def _safe(fn, *args, default=0):  # type: ignore[no-untyped-def]
            try:
                return fn(*args)
            except Exception as exc:
                logger.warning("stats_count_safe: fn=%s err=%s", fn.__name__, exc)
                return default

        stats = {
            "cameras_active": _safe(camera_repo.count_by_status, tenant_id, module_code, "active"),
            "cameras_total": _safe(camera_repo.count_by_module, tenant_id, module_code),
            "alerts_today": _safe(alert_repo.count_since, tenant_id, module_code, today_start),
            "alerts_week": _safe(alert_repo.count_since, tenant_id, module_code, week_start),
            "alerts_last_hour": _safe(
                alert_repo.count_in_window, tenant_id, hour_ago, now, module_code
            ),
            "alerts_prev_hour": _safe(
                alert_repo.count_in_window, tenant_id, two_hours_ago, hour_ago, module_code
            ),
        }

        model = _safe(training_repo.get_active_for_tenant, tenant_id, default=None)
        stats["active_model_name"] = model.get("name") if model else None
        stats["active_model_map50"] = model.get("map50") if model else None

        cameras_active = stats["cameras_active"] or 0
        if cameras_active > 0:
            total_camera_hours = cameras_active * 24
            # ⛔ `or 0` aqui era o pior default possível: falha de consulta
            # virava ZERO violações, e zero violações vira "Taxa de
            # Conformidade 100%" — pintada de VERDE no painel (KPIRow pinta
            # verde em >= 90). O banco cair mostrava o número perfeito.
            # `_FALHOU` distingue "consultei e deu zero" de "não consegui
            # consultar"; a segunda vira None, que a tela mostra como
            # indisponível em vez de inventar conformidade.
            violation_hours = _safe(
                alert_repo.camera_hours_with_violation, tenant_id, module_code, day_ago,
                default=_FALHOU,
            )
            if violation_hours is _FALHOU:
                stats["compliance_rate"] = None
            else:
                horas = violation_hours or 0
                rate = 100.0 * (1 - min(horas, total_camera_hours) / total_camera_hours)
                stats["compliance_rate"] = round(rate, 1)

            by_class_rows = _safe(
                alert_repo.violation_hours_by_class, tenant_id, module_code, day_ago,
                default=[],
            ) or []
            compliance_by_class: dict[str, float] = {}
            for row in by_class_rows:
                cls = row.get("class")
                hours = row.get("hours") or 0
                if not cls:
                    continue
                pct = 100.0 * (1 - min(hours, total_camera_hours) / total_camera_hours)
                compliance_by_class[cls] = round(pct, 1)
            stats["compliance_by_class"] = compliance_by_class
        else:
            stats["compliance_rate"] = None
            stats["compliance_by_class"] = {}

        return stats

    def toggle_class(
        self, tenant_id: str, module_code: str, class_id: str, is_active: bool
    ) -> dict:
        """Ativa ou desativa uma classe do módulo (task-073/achado #6).

        `module_classes` é um catálogo global (sem coluna tenant_id) — o
        isolamento multi-tenant possível aqui é: o tenant requisitante
        precisa ter o módulo habilitado (tenant_modules, C-01) E o
        class_id precisa realmente pertencer a module_code (checado no
        repository). Qualquer uma das duas falhas → NotFoundError (404),
        nunca 403 — não vaza a existência de classes de módulos que o
        tenant não tem acesso.
        """
        from app.core.exceptions import NotFoundError  # noqa: PLC0415

        if not self.tenant_has_module(tenant_id, module_code):
            raise NotFoundError("Classe", class_id)

        result = _get_module_repo().toggle_class_active(module_code, class_id, is_active)
        if not result:
            raise NotFoundError("Classe", class_id)
        return result


module_service = ModuleService()
