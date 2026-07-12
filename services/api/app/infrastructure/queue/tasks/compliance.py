"""
Compliance EPI — Task agendada (Celery Beat).

Fila: reports
Responsabilidade:
  - generate_daily_compliance_reports: gera e arquiva o PDF de compliance EPI
    (período "dia") por tenant no R2, uma vez por dia (task-043 lacuna 2 —
    a task se chamava "relatórios AGENDADOS" mas só existia o endpoint
    on-demand GET /api/reports/compliance).

Reaproveita ComplianceReportService.generate() — a mesma lógica usada pelo
endpoint on-demand (já corrigida do bug crítico do tenant_id ausente em
list_with_filters, PR #75/task-043). A chave R2 agora inclui a data
(tenant/{tenant_id}/reports/dia-{YYYY-MM-DD}.pdf), então cada execução
diária arquiva um PDF novo em vez de sobrescrever o de ontem.

Escopo: apenas tenants ativos com o módulo "epi" habilitado — compliance
report é EPI-específico (ComplianceReportService conta violações do módulo
"epi" internamente). Falha em um tenant não interrompe os demais.
"""
import logging

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_active_epi_tenants() -> list[str]:
    """Tenants ativos com módulo EPI habilitado (compliance é EPI-scoped)."""
    pool = _get_pool()
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT t.id FROM public.tenants t "
            "JOIN public.tenant_modules tm ON tm.tenant_id = t.id "
            "WHERE t.is_active = true AND tm.module_code = 'epi' AND tm.enabled = true"
        )
        return [str(row["id"]) for row in cur.fetchall()]


@celery.task(
    queue="reports",
    name="app.infrastructure.queue.tasks.compliance.generate_daily_compliance_reports",
)
def generate_daily_compliance_reports():  # type: ignore[no-untyped-def]
    """
    Gera e arquiva o relatório de compliance EPI (PDF, período "dia") de cada
    tenant ativo com o módulo EPI habilitado.

    Agendado: diário (via Celery Beat) — task-043 lacuna 2.
    Delega para ComplianceReportService.generate(tenant_id, period="dia"),
    a mesma lógica do endpoint on-demand GET /api/reports/compliance.
    """
    from app.domain.services.compliance_report_service import compliance_report_service

    logger.info("compliance_daily_report_start")

    try:
        tenant_ids = _get_active_epi_tenants()
    except Exception as exc:
        logger.error("compliance_daily_report_tenant_query_error: %s", exc)
        return

    ok, failed = 0, 0
    for tenant_id in tenant_ids:
        try:
            compliance_report_service.generate(tenant_id=tenant_id, period="dia")
            ok += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "compliance_daily_report_tenant_error: tenant=%s err=%s",
                tenant_id, exc, exc_info=True,
            )

    logger.info(
        "compliance_daily_report_done: tenants=%d ok=%d failed=%d",
        len(tenant_ids), ok, failed,
    )
