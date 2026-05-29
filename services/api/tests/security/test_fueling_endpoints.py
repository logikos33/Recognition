"""
Regression tests — Sprint 0.6 BLOCO 3: fueling endpoints DB pool API.

fueling/routes.py was written assuming raw psycopg2 ThreadedConnectionPool
API (pool.getconn() / pool.putconn()), which doesn't exist on
DatabasePool. All /api/fueling/* endpoints returned 500.

Also: row[0]/row[1] fails on RealDictCursor — must use dict access
with SQL aliases.
"""
import inspect


class TestFuelingUsesCorrectPoolApi:
    """fueling/routes.py must use get_connection() context manager, not getconn/putconn."""

    def test_no_getconn_in_source(self):
        import app.api.v1.fueling.routes as fueling

        source = inspect.getsource(fueling)
        assert "pool.getconn(" not in source, (
            "fueling routes must use pool.get_connection() context manager, "
            "not the raw psycopg2 pool.getconn() API"
        )
        assert "pool.putconn(" not in source, (
            "fueling routes must use pool.get_connection() context manager, "
            "not pool.putconn() — context manager handles cleanup"
        )

    def test_uses_get_connection_context_manager(self):
        import app.api.v1.fueling.routes as fueling

        source = inspect.getsource(fueling)
        assert "pool.get_connection()" in source


class TestFuelingUsesDictRowAccess:
    """fueling/routes.py must use row['col'] dict access (RealDictCursor)."""

    def test_no_tuple_row_access(self):
        import app.api.v1.fueling.routes as fueling

        source = inspect.getsource(fueling)
        # Reject tuple-style access like row[0], r[1], total_row[0]
        forbidden_patterns = ["row[0]", "row[1]", "r[0]", "r[1]", "total_row[0]"]
        for pat in forbidden_patterns:
            assert pat not in source, (
                f"Found tuple-style row access {pat!r}. "
                f"DatabasePool uses RealDictCursor — use row['col_name']"
            )

    def test_count_queries_have_alias(self):
        """SELECT COUNT(*) needs AS <alias> to be accessible via row['alias']."""
        import app.api.v1.fueling.routes as fueling

        source = inspect.getsource(fueling)
        # The total query in fueling_events
        assert "COUNT(*) AS total" in source
