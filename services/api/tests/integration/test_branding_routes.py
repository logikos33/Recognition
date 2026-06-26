"""
Integration tests: branding endpoints (task-048).

Estratégia:
  - DatabasePool.get_instance() é mockado (TestingConfig não inicializa DB)
  - MockStorageStrategy (conftest) injetada via patch no upload de logo
  - JWT gerado com additional_claims (tenant_id, role) como o CI faz
  - success() retorna {"success": True, "data": ...} — não "status"
"""
import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Sentinela para distinguir "não passado" de "explicitamente None" em _mock_pool
_UNSET = object()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_ID = str(uuid4())


@pytest.fixture
def superadmin_headers(app):
    """JWT com role superadmin + tenant_id."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "superadmin",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(app):
    """JWT com role admin + tenant_id."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "admin",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    """JWT com role operator (sem permissão admin)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(branding=None, rows=None, fetchone_returns=_UNSET):
    """
    Cria mock do DatabasePool para injetar via patch.

    Usa MagicMock.return_value nos __enter__ (não lambda) para que
    os context managers encadeados funcionem corretamente.

    branding:          dict → fetchone retorna {'branding': ..., 'id': uuid, ...}
    rows:              lista → fetchall retorna essa lista
    fetchone_returns:  valor explícito para fetchone; passe None para simular "não encontrado"
                       (use sentinel _UNSET quando não passado, diferente de None explícito)
    """
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    # Configura fetchone — usa sentinela para aceitar None explícito
    if fetchone_returns is not _UNSET:
        cur.fetchone.return_value = fetchone_returns
    elif branding is not None:
        cur.fetchone.return_value = {
            "branding": branding,
            "id": uuid4(),
            "name": "Test Tenant",
            "slug": "test",
            "is_active": True,
        }
    else:
        # Default: UPDATE bem-sucedido (retorna linha com id)
        cur.fetchone.return_value = {"id": uuid4()}

    cur.fetchall.return_value = rows or []

    # Encadeia context managers via .return_value (não lambda)
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False

    return pool


# ---------------------------------------------------------------------------
# GET /api/v1/tenant/branding
# ---------------------------------------------------------------------------
class TestGetTenantBranding:

    def test_returns_empty_without_auth(self, client) -> None:
        """Sem JWT → retorna {} sem 401 (tema padrão silencioso)."""
        res = client.get("/api/v1/tenant/branding")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # data key pode não existir quando retornado {} (success omite data=None)
        # mas {} não é None então deve estar presente
        assert data.get("data") == {}

    def test_returns_branding_with_auth(self, client, superadmin_headers) -> None:
        """Com JWT válido → retorna branding do tenant."""
        sample = {"brand": {"productName": "AcmeCo"}, "colors": {"primary": "#ff0000"}}
        pool = _mock_pool(branding=sample)
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/branding", headers=superadmin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["brand"]["productName"] == "AcmeCo"
        assert data["data"]["colors"]["primary"] == "#ff0000"

    def test_returns_empty_when_no_branding_set(self, client, operator_headers) -> None:
        """Tenant sem branding configurado (JSONB vazio) → retorna {}."""
        pool = _mock_pool(branding={})
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/branding", headers=operator_headers)
        assert res.status_code == 200
        assert res.get_json()["data"] == {}

    def test_returns_empty_when_tenant_not_found(self, client, operator_headers) -> None:
        """Tenant não encontrado → retorna {} (não expõe 404)."""
        pool = _mock_pool(fetchone_returns=None)
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/branding", headers=operator_headers)
        assert res.status_code == 200
        assert res.get_json()["data"] == {}


# ---------------------------------------------------------------------------
# GET /api/v1/admin/branding/tenants
# ---------------------------------------------------------------------------
class TestListTenantsBranding:

    def test_requires_superadmin(self, client, admin_headers) -> None:
        """Admin (não superadmin) recebe 403."""
        res = client.get("/api/v1/admin/branding/tenants", headers=admin_headers)
        assert res.status_code == 403

    def test_requires_auth(self, client) -> None:
        """Sem JWT → 401 ou 422."""
        res = client.get("/api/v1/admin/branding/tenants")
        assert res.status_code in (401, 422)

    def test_returns_tenant_list(self, client, superadmin_headers) -> None:
        """Superadmin recebe lista de tenants com branding."""
        tenant_id = uuid4()
        rows = [
            {
                "id": tenant_id,
                "name": "Logikos",
                "slug": "logikos",
                "is_active": True,
                "branding": {"brand": {"productName": "Recognition"}},
            }
        ]
        pool = _mock_pool(rows=rows)
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/admin/branding/tenants", headers=superadmin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        tenants = data["data"]["tenants"]
        assert len(tenants) == 1
        assert tenants[0]["name"] == "Logikos"
        assert tenants[0]["branding"]["brand"]["productName"] == "Recognition"

    def test_returns_empty_list(self, client, superadmin_headers) -> None:
        """Nenhum tenant cadastrado → lista vazia."""
        pool = _mock_pool(rows=[])
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/admin/branding/tenants", headers=superadmin_headers)
        assert res.status_code == 200
        assert res.get_json()["data"]["tenants"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/admin/branding/tenant/<id>
# ---------------------------------------------------------------------------
class TestGetBrandingByTenant:

    def test_requires_superadmin(self, client, admin_headers) -> None:
        res = client.get(f"/api/v1/admin/branding/tenant/{TENANT_ID}", headers=admin_headers)
        assert res.status_code == 403

    def test_not_found(self, client, superadmin_headers) -> None:
        """Tenant inexistente → 404."""
        pool = _mock_pool(fetchone_returns=None)
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                f"/api/v1/admin/branding/tenant/{TENANT_ID}",
                headers=superadmin_headers,
            )
        assert res.status_code == 404

    def test_returns_branding(self, client, superadmin_headers) -> None:
        """Tenant encontrado → retorna branding + metadados."""
        pool = _mock_pool(branding={"brand": {"productName": "Foo"}})
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                f"/api/v1/admin/branding/tenant/{TENANT_ID}",
                headers=superadmin_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["branding"]["brand"]["productName"] == "Foo"
        assert "tenant_id" in data["data"]


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/branding
# ---------------------------------------------------------------------------
class TestUpdateBranding:

    def test_requires_admin(self, client, operator_headers) -> None:
        """Operador (sem role admin) recebe 403."""
        res = client.put(
            "/api/v1/admin/branding",
            json={"branding": {}},
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_requires_auth(self, client) -> None:
        res = client.put("/api/v1/admin/branding", json={"branding": {}})
        assert res.status_code in (401, 422)

    def test_invalid_branding_type(self, client, admin_headers) -> None:
        """branding que não é dict → 400."""
        pool = _mock_pool()
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": "invalid"},
                headers=admin_headers,
            )
        assert res.status_code == 400
        assert res.get_json()["success"] is False

    def test_invalid_branding_keys(self, client, admin_headers) -> None:
        """Chave não permitida em branding → 400."""
        pool = _mock_pool()
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {}, "malicious_key": "bad"}},
                headers=admin_headers,
            )
        assert res.status_code == 400

    def test_admin_updates_own_tenant(self, client, admin_headers) -> None:
        """Admin atualiza o branding do próprio tenant com sucesso."""
        pool = _mock_pool()  # fetchone retorna {"id": uuid} → UPDATE bem-sucedido
        branding = {"brand": {"productName": "AcmeCo"}, "colors": {"primary": "#ff0000"}}
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": branding},
                headers=admin_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["branding"]["brand"]["productName"] == "AcmeCo"

    def test_superadmin_can_target_other_tenant(self, client, superadmin_headers) -> None:
        """Superadmin pode passar tenant_id para editar outro tenant."""
        pool = _mock_pool()
        other_tenant = str(uuid4())
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {}}, "tenant_id": other_tenant},
                headers=superadmin_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["tenant_id"] == other_tenant

    def test_tenant_not_found(self, client, admin_headers) -> None:
        """UPDATE sem linhas afetadas → 404."""
        pool = _mock_pool(fetchone_returns=None)
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {}}},
                headers=admin_headers,
            )
        assert res.status_code == 404

    def test_reset_to_empty_branding(self, client, admin_headers) -> None:
        """Branding vazio {} é válido (reset ao padrão)."""
        pool = _mock_pool()
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": {}},
                headers=admin_headers,
            )
        assert res.status_code == 200

    def test_cross_tenant_isolation(self, client, admin_headers) -> None:
        """Admin (não superadmin) NÃO pode passar tenant_id para editar outro tenant."""
        pool = _mock_pool()
        other_tenant = str(uuid4())
        with patch("app.api.v1.branding.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {}}, "tenant_id": other_tenant},
                headers=admin_headers,
            )
        # Admin ignora o tenant_id passado (usa o próprio do JWT)
        assert res.status_code == 200
        data = res.get_json()
        # Deve usar o TENANT_ID do JWT, não o other_tenant
        assert data["data"]["tenant_id"] == TENANT_ID


# ---------------------------------------------------------------------------
# POST /api/v1/admin/branding/logo
# ---------------------------------------------------------------------------
class TestUploadLogo:

    def test_requires_admin(self, client, operator_headers) -> None:
        """Operador (sem admin) recebe 403 no upload."""
        data = {"file": (io.BytesIO(b"fake"), "logo.png", "image/png")}
        res = client.post(
            "/api/v1/admin/branding/logo",
            data=data,
            content_type="multipart/form-data",
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_no_file_sent(self, client, admin_headers) -> None:
        """Sem arquivo → 400."""
        res = client.post("/api/v1/admin/branding/logo", headers=admin_headers)
        assert res.status_code == 400

    def test_invalid_mime_rejected(self, client, admin_headers, mock_storage) -> None:
        """Tipo não permitido (PDF) → 415."""
        data = {
            "file": (io.BytesIO(b"%PDF-1.4"), "doc.pdf", "application/pdf"),
        }
        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            res = client.post(
                "/api/v1/admin/branding/logo",
                data=data,
                content_type="multipart/form-data",
                headers=admin_headers,
            )
        assert res.status_code == 415

    def test_file_too_large_rejected(self, client, admin_headers, mock_storage) -> None:
        """Arquivo > 2 MB → 413."""
        big = b"x" * (2 * 1024 * 1024 + 1)
        data = {
            "file": (io.BytesIO(big), "logo.png", "image/png"),
        }
        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            res = client.post(
                "/api/v1/admin/branding/logo",
                data=data,
                content_type="multipart/form-data",
                headers=admin_headers,
            )
        assert res.status_code == 413

    def test_valid_png_upload(self, client, admin_headers, mock_storage) -> None:
        """PNG válido dentro do limite → 200 com url e key."""
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        data = {
            "file": (io.BytesIO(png), "logo.png", "image/png"),
        }
        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            res = client.post(
                "/api/v1/admin/branding/logo",
                data=data,
                content_type="multipart/form-data",
                headers=admin_headers,
            )
        assert res.status_code == 200
        resp = res.get_json()
        assert resp["success"] is True
        assert "url" in resp["data"]
        assert "key" in resp["data"]
        assert f"branding/{TENANT_ID}" in resp["data"]["key"]

    def test_valid_svg_upload(self, client, admin_headers, mock_storage) -> None:
        """SVG válido → 200 e key com extensão svg."""
        svg = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>"
        data = {
            "file": (io.BytesIO(svg), "logo.svg", "image/svg+xml"),
        }
        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            res = client.post(
                "/api/v1/admin/branding/logo",
                data=data,
                content_type="multipart/form-data",
                headers=admin_headers,
            )
        assert res.status_code == 200
        key = res.get_json()["data"]["key"]
        assert key.endswith(".svg")
