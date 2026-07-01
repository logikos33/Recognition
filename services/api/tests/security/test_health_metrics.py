"""
Regression tests — _count_active_cameras é escopado por tenant (sem leak cross-tenant).

Auditoria de segurança 2026-07 (Multi-tenant / CWE-200): a versão anterior fazia
`SET search_path TO <schema>` e `SELECT COUNT(*) FROM cameras WHERE status='active'`
sem filtro de tenant — como a tabela `cameras` vive em `public`, o search_path caía
em `public.cameras` e contava as câmeras de TODOS os tenants (vazamento de métrica
de negócio para qualquer usuário autenticado).

Correção: contar direto em `public.cameras` filtrando por tenant, alinhado ao padrão
já provado em `camera_repository.count_active_all` (`WHERE tenant_id=%s AND is_active=true`).
A função agora recebe `tenant_id` (não mais um schema interpolado no SQL).
"""
from unittest.mock import MagicMock, patch


class TestCountActiveCamerasQuery:
    """_count_active_cameras deve escopar a contagem por tenant."""

    def test_query_is_scoped_by_tenant(self):
        from app.api.v1.health.routes import _count_active_cameras

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"count": 3}
        mock_conn.cursor.return_value = mock_cur
        mock_pool.get_connection.return_value.__enter__.return_value = mock_conn
        mock_pool.get_connection.return_value.__exit__.return_value = False

        tenant_id = "11111111-1111-1111-1111-111111111111"
        with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp:
            mock_dp.get_instance.return_value = mock_pool
            result = _count_active_cameras(tenant_id)

        assert result == 3

        camera_calls = [
            call
            for call in mock_cur.execute.call_args_list
            if "cameras" in call[0][0].lower()
        ]
        assert camera_calls, "Expected at least one query on cameras table"
        for call in camera_calls:
            sql = call[0][0].lower()
            # A contagem NUNCA pode ser global: tem que filtrar por tenant_id.
            assert "tenant_id" in sql, f"Camera count must be tenant-scoped. Got: {sql}"
            # E o tenant vem parametrizado (%s), nunca interpolado.
            params = call[0][1] if len(call[0]) > 1 else None
            assert params and tenant_id in tuple(params), (
                "tenant_id deve ser passado como parâmetro vinculado"
            )
        # Nenhuma query pode setar search_path para um schema (fonte do leak antigo).
        all_sqls = [c[0][0].lower() for c in mock_cur.execute.call_args_list]
        assert not any("set search_path" in s for s in all_sqls), (
            "Não deve mais depender de SET search_path para contar câmeras"
        )

    def test_returns_zero_when_pool_is_none(self):
        from app.api.v1.health.routes import _count_active_cameras

        with patch("app.infrastructure.database.connection.DatabasePool") as mock_dp:
            mock_dp.get_instance.return_value = None
            result = _count_active_cameras("11111111-1111-1111-1111-111111111111")

        assert result == 0
