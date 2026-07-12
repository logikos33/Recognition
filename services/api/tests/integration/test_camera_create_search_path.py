"""Integração: criação de câmera imune a search_path de tenant vazado.

Reproduz o bug de staging (2026-07-01): uma conexão do pool voltava com
search_path apontando para o schema do tenant (ex: rvb), onde a tabela
`cameras` tem outro formato e NÃO tem tenant_id. O INSERT não qualificado
do CameraRepository resolvia para {schema}.cameras e falhava com
"column tenant_id of relation cameras does not exist".

Falha-antes/passa-depois: com o repository qualificando public.cameras,
o INSERT funciona mesmo com search_path envenenado, e o isolamento por
tenant é mantido.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.camera_repository import CameraRepository

TENANT_SCHEMA = "inttest_sp"


@pytest.fixture
def user_id(pg_raw, tenant_id: str) -> str:  # type: ignore[return]
    """Usuário efêmero do tenant (public.cameras.user_id é NOT NULL + FK)."""
    uid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, f"cam-sp-{uid[:8]}@test.dev", "x", "IntTest Cam", "operator", tenant_id),
        )
    yield uid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.cameras WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


@pytest.fixture
def tenant_schema_cameras(pg_raw):  # type: ignore[no-untyped-def]
    """Schema de tenant com a tabela cameras SEM tenant_id (formato real)."""
    with pg_raw.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TENANT_SCHEMA}")
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {TENANT_SCHEMA}.cameras ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
            "name VARCHAR(255) NOT NULL, "
            "rtsp_url TEXT, "
            "status VARCHAR(50) DEFAULT 'inactive', "
            "created_at TIMESTAMPTZ DEFAULT NOW())"
        )
    yield TENANT_SCHEMA
    with pg_raw.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {TENANT_SCHEMA} CASCADE")


def _poison_pool_search_path(pool, schema: str) -> None:
    """Simula conexão devolvida ao pool com search_path do tenant.

    Bypassa o reset do get_connection() (contexto do bug: código antigo em
    staging não resetava; qualquer handler que use putconn direto também).
    """
    raw = pool._pool.getconn()
    with raw.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public")
    raw.commit()
    pool._pool.putconn(raw)


class TestCameraCreateSearchPathLeak:
    def test_create_lands_in_public_cameras_despite_leaked_search_path(
        self, pg_pool, pg_raw, tenant_id: str, user_id: str, tenant_schema_cameras: str
    ) -> None:
        _poison_pool_search_path(pg_pool, tenant_schema_cameras)

        repo = CameraRepository(pg_pool)
        camera = repo.create({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "name": "Cam Regressão search_path",
            "host": "192.168.1.51",
            "channel": 1,
        })

        assert camera is not None
        assert str(camera["tenant_id"]) == tenant_id

        # A linha está em public.cameras, não no schema do tenant
        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT tenant_id FROM public.cameras WHERE id = %s",
                (str(camera["id"]),),
            )
            row = cur.fetchone()
            assert row is not None
            assert str(row["tenant_id"]) == tenant_id

            cur.execute(f"SELECT COUNT(*) AS c FROM {tenant_schema_cameras}.cameras")
            assert cur.fetchone()["c"] == 0

    def test_tenant_isolation_on_list(
        self, pg_pool, tenant_id: str, user_id: str
    ) -> None:
        """Câmera criada só aparece para o próprio tenant."""
        repo = CameraRepository(pg_pool)
        repo.create({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "name": "Cam Isolamento",
            "host": "192.168.1.51",
        })

        own = repo.get_by_user(tenant_id)  # type: ignore[arg-type]
        assert any(c["name"] == "Cam Isolamento" for c in own)

        other = repo.get_by_user(str(uuid4()))  # type: ignore[arg-type]
        assert all(c["name"] != "Cam Isolamento" for c in other)
