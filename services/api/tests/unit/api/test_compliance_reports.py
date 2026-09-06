"""
Unit tests — GET /api/reports/compliance

Cobre os 5 casos obrigatórios definidos na task-043:
  1. test_compliance_get_no_auth          → 401
  2. test_compliance_wrong_tenant_no_data → 200, dados zerados (tenant isolation)
  3. test_compliance_aggregates_correctly → conta violações corretamente
  4. test_compliance_pdf_uploaded         → upload_bytes chamado no storage
  5. test_compliance_invalid_period       → 400

Mocks:
  - Storage: MockStorageStrategy do conftest (nunca chama R2 real)
  - compliance_report_service._aggregate: patchado para evitar I/O de DB
  - _generate_pdf: patchado onde necessário para retornar bytes determinístico
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())


@pytest.fixture
def auth_headers_tenant_a(app):
    """JWT para tenant A com additional_claims."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": TENANT_A, "role": "operator"},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_tenant_b(app):
    """JWT para tenant B."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": TENANT_B, "role": "operator"},
        )
    return {"Authorization": f"Bearer {token}"}


# Resposta agregada padrão usada em vários testes
_EMPTY_SUMMARY = {
    "compliance_rate": 100.0,
    "total_violations": 0,
    "top_cameras": [],
    "trend_by_hour": [],
}

_ALERT_SUMMARY = {
    "compliance_rate": 80.0,
    "total_violations": 2,
    "top_cameras": [{"camera_id": "cam-1", "count": 2}],
    "trend_by_hour": [],
}

_FAKE_PDF_BYTES = b"%PDF-1.4 fake"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_storage_and_service(summary: dict, pdf_bytes: bytes = _FAKE_PDF_BYTES):
    """Retorna context managers que patcham storage e _aggregate."""
    mock_storage = MagicMock()
    mock_storage.upload_bytes.return_value = None
    mock_storage.generate_presigned_download_url.return_value = "https://mock-r2.test/report.pdf"

    patch_storage = patch(
        "app.domain.services.compliance_report_service._get_storage",
        return_value=mock_storage,
    )
    patch_aggregate = patch(
        "app.domain.services.compliance_report_service.ComplianceReportService._aggregate",
        return_value=summary,
    )
    patch_pdf = patch(
        "app.domain.services.compliance_report_service._generate_pdf",
        return_value=pdf_bytes,
    )
    return patch_storage, patch_aggregate, patch_pdf, mock_storage


# ---------------------------------------------------------------------------
# 1. Sem autenticação → 401
# ---------------------------------------------------------------------------

class TestComplianceNoAuth:
    def test_compliance_get_no_auth(self, client) -> None:
        res = client.get("/api/reports/compliance?period=dia")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.data}"


# ---------------------------------------------------------------------------
# 2. Period inválido → 400
# ---------------------------------------------------------------------------

class TestComplianceInvalidPeriod:
    def test_compliance_invalid_period(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=ano",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False

    def test_compliance_missing_period(self, client, auth_headers_tenant_a) -> None:
        res = client.get("/api/reports/compliance", headers=auth_headers_tenant_a)
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False

    def test_compliance_invalid_from_date(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=dia&from=not-a-date",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# 3. Tenant B não vê dados do tenant A (isolamento)
# ---------------------------------------------------------------------------

class TestComplianceTenantIsolation:
    def test_compliance_wrong_tenant_no_data(self, client, auth_headers_tenant_b) -> None:
        """Tenant B faz request — _aggregate é chamado com TENANT_B, não TENANT_A."""
        called_with: list = []

        def fake_aggregate(self_svc, tenant_id, period, start, end):  # noqa: ANN001
            called_with.append(tenant_id)
            return _EMPTY_SUMMARY

        ps, _, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pp, patch(
            "app.domain.services.compliance_report_service.ComplianceReportService._aggregate",
            fake_aggregate,
        ):
            res = client.get(
                "/api/reports/compliance?period=semana",
                headers=auth_headers_tenant_b,
            )

        assert res.status_code == 200
        # Garante que _aggregate foi chamado com o tenant correto (B, não A)
        assert called_with, "_aggregate não foi chamado"
        assert called_with[0] == TENANT_B, (
            f"Esperado TENANT_B={TENANT_B}, chamado com {called_with[0]}"
        )
        assert called_with[0] != TENANT_A, "cross-tenant leak detectado!"


# ---------------------------------------------------------------------------
# 4. Agrega corretamente (2 violações, verifica summary)
# ---------------------------------------------------------------------------

class TestComplianceAggregates:
    def test_compliance_aggregates_correctly(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_ALERT_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=dia",
                headers=auth_headers_tenant_a,
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        data = body["data"]
        assert "summary" in data
        summary = data["summary"]
        assert summary["total_violations"] == 2
        assert summary["compliance_rate"] == 80.0
        assert len(summary["top_cameras"]) == 1
        assert summary["top_cameras"][0]["camera_id"] == "cam-1"

    def test_compliance_period_dia_ok(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=dia",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["period"]["period"] == "dia"

    def test_compliance_period_semana_ok(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=semana",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["period"]["period"] == "semana"

    def test_compliance_custom_dates(self, client, auth_headers_tenant_a) -> None:
        ps, pa, pp, _ = _patch_storage_and_service(_ALERT_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=dia"
                "&from=2024-01-01T00:00:00Z&to=2024-01-02T00:00:00Z",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert "2024-01-01" in data["period"]["from"]


# ---------------------------------------------------------------------------
# 5. PDF é gerado e upload_bytes é chamado no storage
# ---------------------------------------------------------------------------

class TestCompliancePdfUpload:
    def test_compliance_pdf_uploaded(self, client, auth_headers_tenant_a) -> None:
        """Verifica que upload_bytes é chamado com a chave correta e content-type PDF."""
        ps, pa, pp, mock_storage = _patch_storage_and_service(
            _ALERT_SUMMARY, pdf_bytes=b"%PDF-1.4 test"
        )
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=dia",
                headers=auth_headers_tenant_a,
            )

        assert res.status_code == 200
        mock_storage.upload_bytes.assert_called_once()
        call_args = mock_storage.upload_bytes.call_args
        key_arg = call_args[0][0]
        content_type_arg = call_args[0][2]
        # Chave inclui a data de início do período (task-043 lacuna 2 — permite
        # arquivar histórico diário em vez de sobrescrever o mesmo arquivo).
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert f"tenant/{TENANT_A}/reports/dia-{today}.pdf" == key_arg
        assert content_type_arg == "application/pdf"

    def test_compliance_returns_pdf_url(self, client, auth_headers_tenant_a) -> None:
        """pdf_url deve estar presente na resposta."""
        ps, pa, pp, _ = _patch_storage_and_service(_EMPTY_SUMMARY)
        with ps, pa, pp:
            res = client.get(
                "/api/reports/compliance?period=semana",
                headers=auth_headers_tenant_a,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert "pdf_url" in data
        assert data["pdf_url"].startswith("https://")


# ---------------------------------------------------------------------------
# 6. ISSUE #797 — a Taxa de Conformidade PELA ROTA, com `_aggregate` de verdade
# ---------------------------------------------------------------------------

class TestTaxaDeConformidadePelaRota:
    """O número que o cliente lê sai por `GET /api/reports/compliance` e vira
    PDF arquivado no R2. Todo teste acima patcha `_aggregate` inteiro — nenhum
    deles tocava a fórmula, e por isso a inversão da #797 (conformidade
    derrubando a Taxa de Conformidade) atravessou review e CI.

    Aqui só o I/O é dublado (repositórios, R2, reportlab): a conta é a de
    produção e o valor é lido do JSON da resposta.

    Semana REAL da RVB medida no DEV (04/08 → 11/08, 168 h): 3.801 alertas EPI,
    dos quais a grande maioria é EPI EM USO. A fórmula antiga imprimia
    **0,0 %** — a pior nota possível na semana em que o EPI foi mais usado —
    enquanto o Dashboard, sobre os mesmos dados, dizia 92 · Conforme.
    """

    HORAS_VIOLACAO = 31
    CAMERAS_ATIVAS = 17

    class _AlertRepoFake:
        def __init__(self, total, horas_violacao):
            self.total, self.horas_violacao = total, horas_violacao

        def count_in_window(self, *a, **k):
            return self.total

        def camera_hours_with_violation(self, tenant_id, module_code, since, until=None):
            return self.horas_violacao

        def count_by_hour(self, *a, **k):
            return []

        def list_with_filters(self, **k):
            return {"items": []}

    class _CameraRepoFake:
        def __init__(self, ativas):
            self.ativas = ativas

        def count_by_status(self, tenant_id, module_code, status):
            return self.ativas

    def _pedir(self, client, headers, total_alertas):
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.generate_presigned_download_url.return_value = "https://mock-r2.test/r.pdf"
        with patch(
            "app.domain.services.compliance_report_service._get_alert_repo",
            return_value=self._AlertRepoFake(total_alertas, self.HORAS_VIOLACAO),
        ), patch(
            "app.domain.services.compliance_report_service._get_camera_repo",
            return_value=self._CameraRepoFake(self.CAMERAS_ATIVAS),
        ), patch(
            "app.domain.services.compliance_report_service._get_storage",
            return_value=mock_storage,
        ), patch(
            "app.domain.services.compliance_report_service._generate_pdf",
            return_value=_FAKE_PDF_BYTES,
        ):
            return client.get(
                "/api/reports/compliance?period=semana"
                "&from=2026-08-04T00:00:00Z&to=2026-08-11T00:00:00Z",
                headers=headers,
            )

    def test_semana_de_epi_usado_nao_sai_com_zero_por_cento(
        self, client, auth_headers_tenant_a
    ) -> None:
        res = self._pedir(client, auth_headers_tenant_a, total_alertas=3801)
        assert res.status_code == 200
        taxa = res.get_json()["data"]["summary"]["compliance_rate"]
        assert taxa is not None
        assert taxa > 90.0, (
            f"o PDF de auditoria da semana de maior USO de EPI saiu com {taxa}% — "
            "é a inversão da #797, agora atravessando a rota"
        )

    def test_a_taxa_da_rota_e_a_MESMA_conta_do_cartao_do_dashboard(
        self, client, auth_headers_tenant_a
    ) -> None:
        """100 × (1 − horas-câmera com violação ÷ (câmeras ativas × horas)).

        Escrita à mão: se as duas telas divergirem de novo, é aqui que fica
        vermelho.
        """
        res = self._pedir(client, auth_headers_tenant_a, total_alertas=3801)
        horas_camera = self.CAMERAS_ATIVAS * 168.0
        esperado = round(100.0 * (1 - self.HORAS_VIOLACAO / horas_camera), 2)
        assert res.get_json()["data"]["summary"]["compliance_rate"] == esperado

    def test_o_acervo_de_conformidade_nao_move_a_taxa(
        self, client, auth_headers_tenant_a
    ) -> None:
        """MESMA violação, 40× mais evento de EPI EM USO: mesma nota."""
        pouco = self._pedir(client, auth_headers_tenant_a, total_alertas=95)
        muito = self._pedir(client, auth_headers_tenant_a, total_alertas=3801)
        assert (
            pouco.get_json()["data"]["summary"]["compliance_rate"]
            == muito.get_json()["data"]["summary"]["compliance_rate"]
        )
