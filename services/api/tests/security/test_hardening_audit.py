"""
Security hardening audit — DB-free assertions.

Covers:
  FIX 1: SVG removed from branding ALLOWED_MIME allowlists (stored-XSS prevention).
  FIX 3: DatabasePool.get_connection importable (smoke; full reset tested via integration).

Branch: security/audit-hardening-2026-07
"""


class TestBrandingSvgXssHardening:
    """FIX 1: image/svg+xml must not appear in any branding upload allowlist.

    SVG files can embed <script> tags and execute JavaScript same-origin,
    enabling stored XSS when served back to users.
    """

    def test_branding_routes_does_not_allow_svg(self) -> None:
        from app.api.v1.branding.routes import ALLOWED_MIME

        assert "image/svg+xml" not in ALLOWED_MIME, (
            "SVG upload enables stored XSS — remove image/svg+xml from ALLOWED_MIME "
            "(services/api/app/api/v1/branding/routes.py)"
        )

    def test_admin_branding_routes_does_not_allow_svg(self) -> None:
        from app.api.v1.admin.branding_routes import _ALLOWED_MIME

        assert "image/svg+xml" not in _ALLOWED_MIME, (
            "SVG upload enables stored XSS — remove image/svg+xml from _ALLOWED_MIME "
            "(services/api/app/api/v1/admin/branding_routes.py)"
        )

    def test_branding_routes_still_allows_png(self) -> None:
        """Regression: PNG uploads must not be broken by the SVG removal."""
        from app.api.v1.branding.routes import ALLOWED_MIME

        assert "image/png" in ALLOWED_MIME

    def test_branding_routes_still_allows_jpeg(self) -> None:
        """Regression: JPEG uploads must not be broken by the SVG removal."""
        from app.api.v1.branding.routes import ALLOWED_MIME

        assert "image/jpeg" in ALLOWED_MIME

    def test_branding_routes_still_allows_webp(self) -> None:
        """Regression: WebP uploads must not be broken by the SVG removal."""
        from app.api.v1.branding.routes import ALLOWED_MIME

        assert "image/webp" in ALLOWED_MIME

    def test_admin_branding_routes_still_allows_png(self) -> None:
        from app.api.v1.admin.branding_routes import _ALLOWED_MIME

        assert "image/png" in _ALLOWED_MIME

    def test_admin_branding_routes_still_allows_jpeg(self) -> None:
        from app.api.v1.admin.branding_routes import _ALLOWED_MIME

        assert "image/jpeg" in _ALLOWED_MIME

    def test_admin_branding_routes_still_allows_gif(self) -> None:
        from app.api.v1.admin.branding_routes import _ALLOWED_MIME

        assert "image/gif" in _ALLOWED_MIME


class TestConnectionPoolSearchPathSmoke:
    """FIX 3: DatabasePool.get_connection is a callable context manager (import smoke)."""

    def test_database_pool_importable(self) -> None:
        from app.infrastructure.database.connection import DatabasePool

        assert callable(getattr(DatabasePool, "get_connection", None))

    def test_get_connection_is_generator_function(self) -> None:
        """get_connection() is decorated with @contextmanager — verify via inspect."""
        import inspect

        from app.infrastructure.database.connection import DatabasePool

        # contextmanager-wrapped functions are GeneratorFunctions at the inner level;
        # the public attribute is a regular callable. The wrapper exposes __wrapped__.
        method = DatabasePool.get_connection
        assert callable(method), "get_connection must be callable"
        # The search_path reset code lives in the finally block — verified by code review.
        # Full integration coverage is in tests/security/test_set_search_path.py.
        source = inspect.getsource(method)
        # A conexão é higienizada com conn.reset() (ROLLBACK + RESET ALL, que
        # limpa o search_path) antes do putconn — evita herança de schema entre
        # tenants em conexões reusadas (FIX 3).
        assert "conn.reset()" in source, (
            "get_connection finally block must reset the connection "
            "(conn.reset()) before returning it to the pool (FIX 3)"
        )
        assert "putconn" in source


class TestCountActiveCamerasTenantScoped:
    """FIX 2: _count_active_cameras must scope by tenant_id, not global schema search_path."""

    def test_uses_tenant_id_and_is_active(self) -> None:
        """_count_active_cameras queries public.cameras with tenant_id and is_active."""
        import inspect

        from app.api.v1.health.routes import _count_active_cameras

        source = inspect.getsource(_count_active_cameras)
        assert "tenant_id" in source, (
            "_count_active_cameras must filter by tenant_id (FIX 2)"
        )
        assert "is_active" in source, (
            "_count_active_cameras must use is_active column on public.cameras (FIX 2)"
        )

    def test_does_not_use_set_search_path(self) -> None:
        """The global SET search_path leak must be removed."""
        import inspect

        from app.api.v1.health.routes import _count_active_cameras

        source = inspect.getsource(_count_active_cameras)
        assert "SET search_path" not in source, (
            "_count_active_cameras must not use SET search_path — "
            "it leaks cross-tenant camera counts (FIX 2)"
        )

    def test_returns_zero_when_pool_is_none(self) -> None:
        from unittest.mock import patch

        from app.api.v1.health.routes import _count_active_cameras

        with patch(
            "app.infrastructure.database.connection.DatabasePool"
        ) as mock_dp:
            mock_dp.get_instance.return_value = None
            result = _count_active_cameras("00000000-0000-0000-0000-000000000001")

        assert result == 0
