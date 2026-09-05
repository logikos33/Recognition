"""
DOMAIN compliance_report_service.py — Relatório de compliance EPI on-demand.

Layer: domain
Pattern: Service (singleton at module level)

Responsabilidades:
  - Agregar dados de violação/conformidade EPI de alert_repository para um tenant
  - Calcular métricas: compliance_rate, top_cameras, tendência por hora
  - Gerar PDF (reportlab) com sumário de conformidade
  - Fazer upload do PDF no R2 sob chave
    tenant/{tenant_id}/reports/{period}-{YYYY-MM-DD}.pdf (data = início do período,
    permite histórico diário em vez de sobrescrever — task-043 lacuna 2)
  - Retornar summary dict + presigned download URL

Constraints:
  - TODAS as queries filtram por tenant_id (C-01 multi-tenant)
  - Nunca retorna dados de outro tenant
  - period válido: "dia" | "semana"
  - PDF gerado em memória (io.BytesIO) — zero I/O em disco

Related: app/infrastructure/database/repositories/alert_repository.py,
         app/infrastructure/storage/local_storage.py,
         app/api/v1/reports/routes.py
"""
import io
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

VALID_PERIODS = {"dia", "semana"}

#: Por que o `compliance_rate` não pôde ser calculado. MESMAS chaves que
#: `app/api/v1/modules/routes.py` publica no Dashboard — a tela de Relatórios
#: e o cartão do painel falam do mesmo score e têm de falar a mesma língua.
#: (String literal de propósito: `domain` não importa de `api`.)
RAZAO_SEM_CAMERA = "sem_cameras_ativas"
RAZAO_SEM_SINAL = "sem_sinal_no_periodo"
RAZAO_NAO_APURADA = "nao_foi_possivel_apurar"


def _get_alert_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.alert_repository import AlertRepository

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _get_camera_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.camera_repository import CameraRepository

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_storage():  # type: ignore[no-untyped-def]
    from app.infrastructure.storage.local_storage import get_storage

    return get_storage()


def _period_range(period: str, from_dt: datetime | None, to_dt: datetime | None) -> tuple[datetime, datetime]:
    """Calcula intervalo de datas. from_dt/to_dt têm precedência sobre period."""
    now = datetime.now(tz=timezone.utc)

    if from_dt and to_dt:
        return from_dt, to_dt

    if period == "dia":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # semana
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    return start, now


def valor_conformidade(summary: dict[str, Any]) -> str:
    """A Taxa de Conformidade como TEXTO, para o PDF.

    O PDF vai para o cliente e fica ARQUIVADO no R2 (o job diário gera um por
    dia). Score ausente tem de sair "—" com a razão: um relatório de auditoria
    que imprime "100,0%" porque a consulta caiu é a mentira mais cara deste
    serviço — e era o que acontecia, porque o `except` de `_aggregate` devolvia
    `compliance_rate = 100.0`.

    Função de módulo (e não inline no `_generate_pdf`) porque é a asserção que
    o teste precisa alcançar sem reportlab — que outros testes da suíte
    substituem em `sys.modules`.
    """
    pct = summary.get("compliance_rate")
    if pct is not None:
        return f"{pct:.1f}%"
    razao = summary.get("compliance_reason")
    motivo = (
        "sem evento no período — nada a apurar"
        if razao == RAZAO_SEM_SINAL
        else "não foi possível apurar"
    )
    return f"— ({motivo})"


def _generate_pdf(tenant_id: str, period: str, summary: dict[str, Any], from_dt: datetime, to_dt: datetime) -> bytes:
    """Gera PDF de compliance em memória. Requer reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    period_label = "Diário" if period == "dia" else "Semanal"
    fmt = "%d/%m/%Y %H:%M UTC"
    story.append(Paragraph(f"Relatório de Compliance EPI — {period_label}", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Tenant: {tenant_id}", styles["Normal"]))
    story.append(Paragraph(f"Período: {from_dt.strftime(fmt)} → {to_dt.strftime(fmt)}", styles["Normal"]))
    story.append(Spacer(1, 18))

    # Sumário
    total_violations = summary.get("total_violations", 0)
    top_cameras = summary.get("top_cameras", [])
    valor_pct = valor_conformidade(summary)

    story.append(Paragraph("Sumário de Conformidade", styles["Heading2"]))
    story.append(Spacer(1, 6))

    data = [
        ["Métrica", "Valor"],
        ["Taxa de Conformidade", valor_pct],
        ["Total de Violações", str(total_violations)],
        ["Câmeras com Violações", str(len(top_cameras))],
    ]
    tbl = Table(data, colWidths=[8 * cm, 6 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 18))

    # Top câmeras
    if top_cameras:
        story.append(Paragraph("Top Câmeras por Violações", styles["Heading2"]))
        story.append(Spacer(1, 6))
        cam_data = [["Câmera ID", "Violações"]] + [
            [str(c.get("camera_id", "—")), str(c.get("count", 0))]
            for c in top_cameras[:10]
        ]
        cam_tbl = Table(cam_data, colWidths=[10 * cm, 4 * cm])
        cam_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cam_tbl)
        story.append(Spacer(1, 18))

    # Rodapé
    generated_at = datetime.now(tz=timezone.utc).strftime(fmt)
    story.append(Paragraph(f"Gerado em: {generated_at}", styles["Normal"]))
    story.append(Paragraph("Recognition EPI Monitor V2 — Logikos", styles["Italic"]))

    doc.build(story)
    return buf.getvalue()


class ComplianceReportService:
    """Gera relatório de compliance EPI on-demand para um tenant."""

    def generate(
        self,
        tenant_id: str,
        period: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Agrega dados, gera PDF e faz upload no R2.

        Args:
            tenant_id: UUID do tenant (obrigatório, nunca None).
            period: "dia" | "semana" — determina janela padrão se from/to ausentes.
            from_dt: Início do período (UTC). Opcional.
            to_dt: Fim do período (UTC). Opcional.

        Returns:
            {
              "summary": {compliance_rate, total_violations, top_cameras, trend_by_hour},
              "pdf_url": "<presigned URL>",
              "period": {"period", "from", "to"},
            }

        Raises:
            ValueError: period inválido.
        """
        if period not in VALID_PERIODS:
            raise ValueError(f"period deve ser um de {sorted(VALID_PERIODS)!r}, recebido: {period!r}")

        start, end = _period_range(period, from_dt, to_dt)

        # --- Agregação ---
        summary = self._aggregate(tenant_id, period, start, end)

        # --- Gerar PDF ---
        pdf_bytes = _generate_pdf(tenant_id, period, summary, start, end)

        # --- Upload R2 ---
        # Chave inclui a data de início do período (task-043 lacuna 2): sem ela,
        # cada execução do job diário sobrescrevia o mesmo arquivo, sem histórico.
        pdf_key = f"tenant/{tenant_id}/reports/{period}-{start.strftime('%Y-%m-%d')}.pdf"
        storage = _get_storage()
        storage.upload_bytes(pdf_key, pdf_bytes, "application/pdf")
        pdf_url = storage.generate_presigned_download_url(
            pdf_key, ttl=3600, response_content_type="application/pdf"
        )

        return {
            "summary": summary,
            "pdf_url": pdf_url,
            "period": {
                "period": period,
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
        }

    def _aggregate(
        self, tenant_id: str, period: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        """Agrega métricas de compliance do alert_repository.

        **Taxa de Conformidade — issue #797.** A fórmula é a MESMA do cartão do
        Dashboard (`module_service.get_stats`, ADR-0065):

            100 × (1 − horas-câmera com violação ÷ (câmeras ativas × horas))

        Antes era `100 − (TODOS os alertas ÷ horas) × 50`, e `count_in_window`
        não filtra tipo: cada evento de **EPI EM USO** — o resultado bom, 3.881
        dos 5.092 do acervo da RVB — DERRUBAVA a Taxa de Conformidade. Quanto
        mais gente usando EPI, pior a nota. Medido no DEV: na semana de 04/08 o
        PDF imprimia **0,0 %** enquanto o Dashboard, sobre os mesmos dados,
        mostrava **92 · Conforme**. Cerca de 90 pontos de diferença, em
        direções opostas, com o MESMO rótulo, no mesmo produto — e o do PDF é o
        que fica arquivado no R2 como prova de auditoria.

        É a inversão que a ADR-0065 já tinha corrigido no Dashboard
        (`camera_hours_with_violation` conta violação DE VERDADE:
        `_IS_VIOLATION_SQL AND NOT _IS_COMPLIANCE_SQL`) e que nunca chegou aqui.
        Agora as duas telas leem o mesmo numerador e o mesmo denominador; o que
        as separa é só a JANELA que cada uma cobre, e cada uma diz a sua.

        `compliance_rate` é `None` (com `compliance_reason`) sempre que o número
        afirmaria mais do que se sabe: nenhum alerta na janela (nada foi
        observado), nenhuma câmera ativa (denominador zero) ou agregação que
        falhou. Nunca 100 sobre o vazio.
        """
        razao: str | None = None
        try:
            alert_repo = _get_alert_repo()
            # `count_since` ignorava `end`: para um período FECHADO (o "mês
            # anterior" da tela de Relatórios manda from/to) ele contava do
            # início do período até AGORA, somando eventos de fora da janela ao
            # número que a tela chama de "eventos no período". Mesmos filtros e
            # mesmo escopo de câmera; o que muda é o limite superior existir.
            total_violations = alert_repo.count_in_window(tenant_id, start, end, "epi")

            # Tendência por hora
            trend_rows = alert_repo.count_by_hour(tenant_id, start, end)
            trend = [
                {
                    "hour": row["hour"].isoformat() if hasattr(row.get("hour"), "isoformat") else str(row.get("hour")),
                    "count": int(row.get("count", 0)),
                }
                for row in (trend_rows or [])
            ]

            # Top câmeras (agrega das linhas detalhadas)
            # tenant_id é posicional/obrigatório em list_with_filters (C-01) — bug
            # crítico task-043/PR #75: omiti-lo levantava TypeError, engolido pelo
            # except abaixo, fazendo o endpoint sempre retornar 100%/0 violações.
            alerts = alert_repo.list_with_filters(
                tenant_id=tenant_id,
                limit=500,
                offset=0,
                start_date=start,
                end_date=end,
            )
            items = alerts.get("items", []) if isinstance(alerts, dict) else []
            cam_counter: Counter = Counter()
            for item in items:
                cam_id = item.get("camera_id") or item.get("camera_name") or "unknown"
                cam_counter[str(cam_id)] += 1

            top_cameras = [
                {"camera_id": cam_id, "count": cnt}
                for cam_id, cnt in cam_counter.most_common(10)
            ]

            # ── Taxa de Conformidade (issue #797) ────────────────────────
            # MESMO numerador e MESMO denominador do cartão do Dashboard.
            #
            # numerador: HORAS-CÂMERA COM VIOLAÇÃO — violação de verdade
            #   (ADR-0065 + contrato A1), pela janela FECHADA do relatório.
            #   Conformidade (EPI em uso) não entra: era ela que derrubava a
            #   nota quando o EPI estava sendo USADO.
            # denominador: câmeras ativas × horas do período — as horas-câmera
            #   que o módulo SUPÕE ter monitorado. É suposição, e é por isso
            #   que a legenda da tela tem de dizer o eixo (issue #789).
            hours = max(1.0, (end - start).total_seconds() / 3600)
            violation_hours = 0

            if total_violations == 0:
                # ZERO alerta na janela não é 100 % de conformidade: `count_in_window`
                # conta TODO alerta EPI do período (violação E conformidade), então
                # zero significa que nada chegou — o módulo não estava OLHANDO.
                # Mesma doutrina do score do Dashboard (`_com_score_honesto` em
                # `app/api/v1/modules/routes.py`): ausência de medição não vira
                # nota máxima. O PDF arquivado no R2 é prova para auditoria.
                compliance_rate = None
                razao = RAZAO_SEM_SINAL
            else:
                cameras_ativas = _get_camera_repo().count_by_status(tenant_id, "epi", "active")
                if cameras_ativas <= 0:
                    # Denominador zero. Mesma razão que `get_stats` publica
                    # quando não há câmera ativa — a tela já traduz a chave.
                    compliance_rate = None
                    razao = RAZAO_SEM_CAMERA
                else:
                    violation_hours = alert_repo.camera_hours_with_violation(
                        tenant_id, "epi", start, end
                    )
                    camera_hours = cameras_ativas * hours
                    compliance_rate = 100.0 * (
                        1 - min(violation_hours, camera_hours) / camera_hours
                    )

        except Exception as exc:
            logger.warning("compliance_aggregate_failed: %s", exc, exc_info=True)
            total_violations = 0
            violation_hours = 0
            trend = []
            top_cameras = []
            # ⛔ Era `100.0`. A consulta cair devolvia o relatório PERFEITO —
            # e o `except` cobre tudo, inclusive o TypeError do PR #75. O
            # endpoint mentia exatamente quando menos sabia. `None` + razão:
            # a tela mostra "não foi possível apurar", nunca um número.
            compliance_rate = None
            razao = RAZAO_NAO_APURADA

        return {
            "compliance_rate": None if compliance_rate is None else round(compliance_rate, 2),
            "compliance_reason": razao,
            # ⚠️ `total_violations` é, e sempre foi, TODO alerta EPI do período
            # (violação E conformidade) — o nome mente, e a tela o imprime como
            # "N eventos no período", que é o que ele de fato é. A chave fica
            # como está de propósito: `Relatorios.tsx` também a usa para decidir
            # se o período está VAZIO, e trocar o significado sem trocar a tela
            # faria uma semana de 3.881 eventos de conformidade e zero violação
            # aparecer como "sem dado". Renomear é tarefa da tela, com a tela
            # junto — issue própria.
            "total_violations": total_violations,
            # Estes dois são novos e são o que a taxa REALMENTE usa. Existem
            # para a tela poder mostrar de onde o número veio em vez de pedir
            # confiança (e para o próximo a mexer não precisar reconstituir a
            # fórmula a partir do resultado).
            "violation_hours": violation_hours,
            "period_hours": round(max(1.0, (end - start).total_seconds() / 3600), 2),
            "top_cameras": top_cameras,
            "trend_by_hour": trend,
        }


# Singleton — importar e chamar diretamente
compliance_report_service = ComplianceReportService()
