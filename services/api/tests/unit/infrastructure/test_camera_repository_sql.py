"""Tests: CameraRepository SQL must target public.cameras explicitly.

Regressão do bug de cadastro em staging (2026-07-01): o INSERT usava
`cameras` sem qualificar o schema. Quando uma conexão do pool voltava com
search_path apontando para um schema de tenant ({schema}.cameras não tem
tenant_id), o INSERT falhava com "column tenant_id of relation cameras
does not exist". Toda query do CRUD principal deve mirar public.cameras.

Também cobre a coluna user_id (NOT NULL em public.cameras): o INSERT
precisa incluí-la ou a criação falha com violação de NOT NULL.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.camera_repository import CameraRepository


class MockPool:
    """Mock leve de DatabasePool com suporte a context manager."""

    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn
        self.mock_conn.commit()


def _make_repo() -> tuple[CameraRepository, MockPool]:
    pool = MockPool()
    return CameraRepository(pool), pool  # type: ignore[arg-type]


class TestCameraRepositorySchemaQualification:
    """Toda query do CameraRepository qualifica public.cameras."""

    def test_create_inserts_into_public_cameras(self) -> None:
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}

        repo.create({
            "tenant_id": uuid4(),
            "user_id": uuid4(),
            "name": "Cam",
            "host": "192.168.1.51",
        })

        sql = pool.mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO public.cameras" in sql, (
            "INSERT sem qualificar public.cameras — vulnerável a search_path "
            "de tenant vazado ({schema}.cameras não tem tenant_id)"
        )

    def test_create_includes_user_id_column(self) -> None:
        """public.cameras.user_id é NOT NULL — o INSERT precisa preenchê-la."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}
        user_id = uuid4()

        repo.create({
            "tenant_id": uuid4(),
            "user_id": user_id,
            "name": "Cam",
            "host": "192.168.1.51",
        })

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "user_id" in sql
        assert str(user_id) in params

    def test_all_queries_qualify_public_cameras(self) -> None:
        """Nenhum método do repository usa `cameras` sem schema."""
        import inspect

        import app.infrastructure.database.repositories.camera_repository as mod

        source = inspect.getsource(mod)
        for token in ("INTO cameras", "FROM cameras", "UPDATE cameras"):
            assert token not in source, (
                f"Query com '{token}' sem qualificar public. — "
                "sujeita a search_path de tenant vazado"
            )


class TestCameraRepositorySiteId:
    """site_id precisa CHEGAR no SQL — não basta o service aceitar o campo.

    Bug real (encontrado ligando o live view na RVB): `site_id` foi adicionado
    à lista de campos de camera_service.update_camera, mas o repository tem uma
    SEGUNDA lista de colunas permitidas. O campo era descartado em silêncio: o
    PUT devolvia 200, o UPDATE nunca incluía a coluna, e a câmera seguia órfã
    de site — invisível pro edge (config_poll, live-view/wanted, fps demand
    filtram todos por site_id).

    Teste de service com repository mockado NÃO pega isso — precisa olhar o SQL.
    """

    def test_create_includes_site_id_in_insert(self) -> None:
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}
        site_id = uuid4()

        repo.create({
            "tenant_id": uuid4(), "user_id": uuid4(),
            "name": "Cam", "host": "10.0.0.1", "site_id": str(site_id),
        })

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "site_id" in sql
        assert str(site_id) in params

    def test_create_without_site_id_passes_none(self) -> None:
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"id": uuid4(), "name": "Cam"}

        repo.create({
            "tenant_id": uuid4(), "user_id": uuid4(),
            "name": "Cam", "host": "10.0.0.1",
        })

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "site_id" in sql
        assert None in params

    def test_update_includes_site_id_in_set_clause(self) -> None:
        repo, pool = _make_repo()
        cam_id = uuid4()
        site_id = uuid4()
        pool.mock_cursor.fetchone.return_value = {"id": cam_id, "name": "Cam"}

        repo.update(cam_id, {"site_id": str(site_id)})

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "site_id = %s" in sql, (
            "site_id não chegou ao UPDATE — o repository tem lista própria de "
            "colunas permitidas, separada da do service"
        )
        assert str(site_id) in params

    def test_service_and_repository_update_field_lists_agree(self) -> None:
        """As duas listas de campos permitidos precisam concordar, senão um
        campo aceito pelo service some em silêncio no repository."""
        import inspect

        from app.domain.services.camera_service import CameraService

        service_src = inspect.getsource(CameraService.update_camera)
        repo_src = inspect.getsource(CameraRepository.update)

        for field in ("site_id", "channel", "live_view_subtype", "host", "port"):
            assert f'"{field}"' in service_src, f"{field} ausente no service"
            assert f'"{field}"' in repo_src, (
                f"{field} aceito pelo service mas AUSENTE no repository — "
                "seria descartado em silêncio"
            )
