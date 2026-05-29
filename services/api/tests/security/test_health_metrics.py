"""
Regression tests — _count_active_cameras uses correct column.

The tenant schema cameras table (created by create_tenant_schema in
migrations 024/028/033) has 'status VARCHAR(50)', not 'is_active BOOLEAN'.
The endpoint runs after SET search_path to the tenant schema, so the query
must reference 'status'.

Regression for Sprint 0.5 BLOCO 5 (ec44e55) which incorrectly changed
the query to use is_active, causing 'column is_active does not exist' in
production logs.
"""
from unittest.mock import MagicMock, patch


class TestCountActiveCamerasQuery:
    """_count_active_cameras must use status column from tenant schema cameras."""

    def test_uses_status_column_not_is_active(self):
        from app.api.v1.health.routes import _count_active_cameras

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"count": 3}
        mock_conn.cursor.return_value = mock_cur
        mock_pool.get_connection.return_value.__enter__.return_value = mock_conn
        mock_pool.get_connection.return_value.__exit__.return_value = False

        with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp:
            mock_dp.get_instance.return_value = mock_pool
            result = _count_active_cameras("test_schema")

        assert result == 3
        executed_sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
        camera_queries = [s for s in executed_sqls if "cameras" in s.lower()]
        assert camera_queries, "Expected at least one query on cameras table"
        for sql in camera_queries:
            assert "status" in sql.lower(), f"Must use 'status' column. Got: {sql}"
            assert "is_active" not in sql.lower(), f"Must NOT use 'is_active'. Got: {sql}"

    def test_returns_zero_on_invalid_schema(self):
        from app.api.v1.health.routes import _count_active_cameras

        assert _count_active_cameras("") == 0
        assert _count_active_cameras("public; DROP TABLE users--") == 0
        assert _count_active_cameras("123invalid") == 0

    def test_returns_zero_when_pool_is_none(self):
        from app.api.v1.health.routes import _count_active_cameras

        with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp:
            mock_dp.get_instance.return_value = None
            result = _count_active_cameras("test_schema")

        assert result == 0
