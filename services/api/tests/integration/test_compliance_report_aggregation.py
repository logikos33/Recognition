"""
Integration tests: agregação real de compliance (task-043 — bugfix crítico).

Contexto do bug (PR #75, corrigido nesta task):
  ComplianceReportService._aggregate chamava
  alert_repo.list_with_filters(limit=500, offset=0, start_date=start, end_date=end)
  sem o parâmetro `tenant_id` — posicional e obrigatório (sem default) na
  assinatura real de AlertRepository.list_with_filters. Isso levantava
  TypeError toda vez que a agregação rodava de verdade contra o banco.
  O TypeError era engolido por um `except Exception` genérico dentro do
  próprio `_aggregate`, que sobrescrevia o summary com valores fixos
  (total_violations=0, top_cameras=[], compliance_rate=100.0) — o endpoint
  SEMPRE reportava "100% compliance / 0 violações", independente dos dados
  reais em produção.

Por que o teste unitário existente não pegou: test_compliance_reports.py
faz `patch("...ComplianceReportService._aggregate", return_value=summary)` —
mocka a função inteira, nunca exercitando a chamada real de
list_with_filters. Estes testes aqui rodam contra Postgres REAL e NUNCA
mockam _aggregate — teriam falhado (total_violations sempre 0, independente
do seed) antes do fix, e passam depois.

Estratégia idêntica à de test_edge_fleet_overview.py: Postgres REAL via
pg_pool/pg_raw/tenant_id fixtures (conftest.py), cross-tenant isolation via
um segundo tenant efêmero criado/limpo explicitamente no teste.

Pulados automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.services.compliance_report_service import compliance_report_service


# ---------------------------------------------------------------------------
# Helpers de seed
# ---------------------------------------------------------------------------

def _insert_user(cur, tenant_id: str) -> str:
    """public.cameras.user_id é NOT NULL + FK — precisa de um usuário real."""
    uid = str(uuid4())
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, f"compliance-{uid[:8]}@test.dev", "x", "IntTest Compliance", "operator", tenant_id),
    )
    return uid


def _insert_camera(cur, tenant_id: str, user_id: str, name: str) -> str:
    cid = str(uuid4())
    cur.execute(
        "INSERT INTO public.cameras (id, tenant_id, user_id, name, host, port) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (cid, tenant_id, user_id, name, "192.168.1.1", 554),
    )
    return cid


def _insert_alert(cur, tenant_id: str, camera_id: str, created_at: datetime) -> None:
    """module_code default 'epi' — o mesmo módulo que ComplianceReportService agrega."""
    cur.execute(
        "INSERT INTO public.alerts "
        "(id, camera_id, tenant_id, module_code, violations, confidence, evidence_key, created_at) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)",
        (str(uuid4()), camera_id, tenant_id, "epi", "[]", 0.9, "evidence.jpg", created_at),
    )


# ---------------------------------------------------------------------------
# Integration tests: Postgres REAL — NÃO mockar _aggregate (essa foi a lição)
# ---------------------------------------------------------------------------

class TestComplianceAggregationIntegration:
    """Prova que _aggregate roda de verdade contra o banco (sem TypeError) e
    isola corretamente por tenant — falha-antes/passa-depois do fix task-043."""

    def test_aggregate_matches_seed_and_isolates_cross_tenant(
        self, pg_pool, pg_raw, tenant_id
    ) -> None:
        """Seed 3 alertas p/ tenant A + 5 p/ tenant B; cada agregação só conta os
        próprios alertas e os números batem exatamente com o seed."""
        tenant_a = tenant_id
        tenant_b = str(uuid4())
        slug_b = f"inttest-compliance-b-{tenant_b[:8]}"

        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (tenant_b, f"IntTest Compliance B {slug_b}", slug_b),
            )

        user_a = user_b = None
        try:
            # Janela fixa de 2h (start..end) — hours=2.0 exato, sem drift de
            # ponto flutuante, permitindo assert exato de compliance_rate.
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            start = now - timedelta(hours=1)
            end = now + timedelta(hours=1)

            with pg_raw.cursor() as cur:
                user_a = _insert_user(cur, tenant_a)
                user_b = _insert_user(cur, tenant_b)
                cam_a = _insert_camera(cur, tenant_a, user_a, "cam-a")
                cam_b = _insert_camera(cur, tenant_b, user_b, "cam-b")

                for _ in range(3):
                    _insert_alert(cur, tenant_a, cam_a, now)
                for _ in range(5):
                    _insert_alert(cur, tenant_b, cam_b, now)

            # --- Tenant A: só vê seus 3 alertas ---
            summary_a = compliance_report_service._aggregate(tenant_a, "dia", start, end)
            assert summary_a["total_violations"] == 3, (
                f"esperado 3 violações seedadas p/ tenant A, veio "
                f"{summary_a['total_violations']} — TypeError silenciosamente "
                "engolido de novo? (bug PR #75 reintroduzido)"
            )
            assert summary_a["top_cameras"] == [{"camera_id": cam_a, "count": 3}]
            # hours=2.0 exato -> violations_proxy=1.5 -> 100-1.5*50=25.0
            assert summary_a["compliance_rate"] == 25.0

            # --- Tenant B: só vê seus 5 alertas ---
            summary_b = compliance_report_service._aggregate(tenant_b, "dia", start, end)
            assert summary_b["total_violations"] == 5, (
                f"esperado 5 violações seedadas p/ tenant B, veio "
                f"{summary_b['total_violations']}"
            )
            assert summary_b["top_cameras"] == [{"camera_id": cam_b, "count": 5}]
            # hours=2.0 exato -> violations_proxy=2.5 -> 100-2.5*50=-25 -> clamp 0.0
            assert summary_b["compliance_rate"] == 0.0

            # --- Isolamento cruzado explícito (C-01) ---
            cam_ids_a = {c["camera_id"] for c in summary_a["top_cameras"]}
            cam_ids_b = {c["camera_id"] for c in summary_b["top_cameras"]}
            assert cam_b not in cam_ids_a, "cross-tenant leak: câmera de B na agregação de A"
            assert cam_a not in cam_ids_b, "cross-tenant leak: câmera de A na agregação de B"
        finally:
            with pg_raw.cursor() as cur:
                # DELETE do usuário faz CASCADE em cameras -> alerts (FKs ON DELETE
                # CASCADE). Precisa rodar antes do teardown do fixture tenant_id
                # (que deleta o tenant e falharia com FK ainda pendurada).
                if user_a:
                    cur.execute("DELETE FROM public.users WHERE id = %s", (user_a,))
                if user_b:
                    cur.execute("DELETE FROM public.users WHERE id = %s", (user_b,))
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (tenant_b,))
