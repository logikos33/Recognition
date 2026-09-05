"""
Integração — ISOLAMENTO POR TENANT do vínculo câmera↔módulo (migration 134).

Complementa test_escopo_modulo_camera.py, que prova o EFEITO do vínculo nos
consumidores (pool, fila, dashboard, eventos) dentro de UM tenant. Aqui há
DOIS tenants vizinhos, porque o eixo que o outro arquivo não pode cobrir com um
`tenant_id` só é justamente o que a casa mais sangra: vazamento cross-tenant.

Três perguntas, todas com dois tenants no banco ao mesmo tempo:
  1. A leitura do vínculo do tenant A enxerga vínculo do tenant B?
  2. O PREDICADO (escopo_sql/escopo_camera_sql) considera o escopo do A como
     "declarado" porque o B declarou? Se sim, o deploy da 134 restringiria a
     galeria de um tenant por causa da decisão de outro.
  3. Se a aplicação errasse e gravasse a linha cruzada, o BANCO recusa?
     (FK composta camera_id+tenant_id → cameras(id, tenant_id).)

Nada aqui depende de COMO se desvincula (apagar a linha ou desligá-la): os
testes falam só de quem enxerga o quê, então continuam valendo se o desenho
do desvincular mudar.

MUTAÇÕES EXECUTADAS (cada uma reprovou exatamente um teste daqui):
  - tirar `tenant_id = %s` do WHERE de `camera_ids_for_module`
  - trocar o termo de escopo-não-declarado do predicado por FALSE
"""
from __future__ import annotations

from uuid import uuid4

import psycopg2
import pytest

from app.infrastructure.database.repositories.camera_module_repository import (
    CameraModuleRepository,
    escopo_camera_params,
    escopo_camera_sql,
)


# ---------------------------------------------------------------------------
# Seed — dois tenants, câmeras dos dois lados
# ---------------------------------------------------------------------------

def _insert_tenant(cur) -> str:
    tid = str(uuid4())
    cur.execute(
        "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
        (tid, f"CamMod {tid[:8]}", f"cammod-{tid[:8]}"),
    )
    return tid


def _insert_user(cur, tenant_id: str) -> str:
    uid = str(uuid4())
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, f"cammod-{uid[:8]}@test.dev", "x", "CamMod", "operator", tenant_id),
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


@pytest.fixture
def vizinhos(pg_raw):
    """Dois tenants com câmeras. Nomes são os do estrago medido na RVB.

    "Qualidade 01 EPI" está aqui de propósito: é a câmera que serve DOIS
    módulos legitimamente, e é por causa dela que o vínculo é N:N — nenhum
    teste deste arquivo trata câmera de Qualidade no EPI como erro.
    """
    with pg_raw.cursor() as cur:
        t_a, t_b = _insert_tenant(cur), _insert_tenant(cur)
        u_a, u_b = _insert_user(cur, t_a), _insert_user(cur, t_b)
        dados = {
            "tenant_a": t_a,
            "tenant_b": t_b,
            "user_a": u_a,
            "cam_qualidade": _insert_camera(cur, t_a, u_a, "Qualidade 01 EPI"),
            "cam_guarita": _insert_camera(cur, t_a, u_a, "Guarita"),
            "cam_vizinha": _insert_camera(cur, t_b, u_b, "Camera do vizinho"),
        }
    yield dados
    tenants = [dados["tenant_a"], dados["tenant_b"]]
    with pg_raw.cursor() as cur:
        # users → cameras → camera_modules cascateiam nessa ordem; tenants não
        # tem CASCADE a partir de users, por isso os dois passos.
        cur.execute(
            "DELETE FROM public.users WHERE tenant_id = ANY(%s::uuid[])", (tenants,)
        )
        cur.execute(
            "DELETE FROM public.tenants WHERE id = ANY(%s::uuid[])", (tenants,)
        )


@pytest.fixture
def repo(pg_pool) -> CameraModuleRepository:
    return CameraModuleRepository(pg_pool)


def _conta_cameras_do_modulo(pg_raw, tenant_id: str, module_code: str) -> int:
    """Quantas câmeras o predicado considera do módulo, para ESTE tenant."""
    sql = (
        "SELECT count(*) AS n FROM public.cameras c "
        f"WHERE c.tenant_id = %s AND {escopo_camera_sql('c.id', 'c.module_code')}"
    )
    with pg_raw.cursor() as cur:
        cur.execute(sql, tuple([tenant_id] + escopo_camera_params(tenant_id, module_code)))
        return cur.fetchone()["n"]


# ---------------------------------------------------------------------------
# 1. Leitura do vínculo não atravessa tenant
# ---------------------------------------------------------------------------

def test_vinculo_do_vizinho_nao_vaza_nas_leituras_do_tenant(repo, vizinhos):
    repo.replace_for_cameras(vizinhos["tenant_b"], [vizinhos["cam_vizinha"]], ["epi"], None)

    assert repo.camera_ids_for_module(vizinhos["tenant_a"], "epi") == []
    assert repo.list_by_tenant(vizinhos["tenant_a"]) == []
    # e o vizinho continua enxergando o que é dele
    assert repo.camera_ids_for_module(vizinhos["tenant_b"], "epi") == [
        vizinhos["cam_vizinha"]
    ]


def test_camera_do_vizinho_nao_serve_modulo_do_tenant(repo, vizinhos):
    """Escopo declarado no tenant A não pode adotar câmera do tenant B."""
    repo.replace_for_cameras(vizinhos["tenant_a"], [vizinhos["cam_qualidade"]], ["epi"], None)

    assert repo.camera_serves_module(
        vizinhos["tenant_a"], vizinhos["cam_vizinha"], "epi"
    ) is False


# ---------------------------------------------------------------------------
# 2. O predicado: a decisão de um tenant não pode declarar escopo do outro
# ---------------------------------------------------------------------------

def test_escopo_do_vizinho_nao_declara_escopo_do_tenant(repo, pg_raw, vizinhos):
    """O caso perigoso do multi-tenant + escopo-não-declarado.

    O tenant B declara EPI; o tenant A não declarou nada. Para o A o escopo
    continua NÃO declarado, então o predicado tem de deixar passar as duas
    câmeras dele. Se o EXISTS de "escopo declarado" não filtrasse por tenant,
    a galeria do A seria zerada por uma decisão que ele nunca tomou.
    """
    repo.replace_for_cameras(vizinhos["tenant_b"], [vizinhos["cam_vizinha"]], ["epi"], None)

    assert _conta_cameras_do_modulo(pg_raw, vizinhos["tenant_a"], "epi") == 2, (
        "a decisão do tenant vizinho restringiu o escopo deste tenant"
    )


def test_escopo_declarado_restringe_dentro_do_proprio_tenant(repo, pg_raw, vizinhos):
    """Contraprova do teste acima: declarado no PRÓPRIO tenant, restringe mesmo."""
    repo.replace_for_cameras(vizinhos["tenant_a"], [vizinhos["cam_qualidade"]], ["epi"], None)

    assert _conta_cameras_do_modulo(pg_raw, vizinhos["tenant_a"], "epi") == 1
    # e o vizinho, que não declarou nada, continua com escopo aberto
    assert _conta_cameras_do_modulo(pg_raw, vizinhos["tenant_b"], "epi") == 1


# ---------------------------------------------------------------------------
# 3. A tranca no banco, abaixo da aplicação
# ---------------------------------------------------------------------------

def test_banco_recusa_linha_com_tenant_de_outra_camera(pg_raw, vizinhos):
    """FK composta (camera_id, tenant_id) → cameras(id, tenant_id).

    Mesmo que a API errasse, o banco recusa registrar que a câmera do tenant B
    pertence ao tenant A. Sem essa FK o isolamento dependeria só de a
    aplicação nunca errar.
    """
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.camera_modules "
                "(tenant_id, camera_id, module_code) VALUES (%s, %s, 'epi')",
                (vizinhos["tenant_a"], vizinhos["cam_vizinha"]),
            )


# ---------------------------------------------------------------------------
# Ação em massa
# ---------------------------------------------------------------------------

def test_declarar_varias_cameras_numa_transacao(repo, vizinhos):
    """Ação em massa: uma chamada, N câmeras — e nenhuma do tenant vizinho."""
    tenant = vizinhos["tenant_a"]
    cams = [vizinhos["cam_qualidade"], vizinhos["cam_guarita"]]

    assert repo.replace_for_cameras(tenant, cams, ["epi"], None) == 2
    assert sorted(repo.camera_ids_for_module(tenant, "epi")) == sorted(cams)
    assert repo.camera_ids_for_module(vizinhos["tenant_b"], "epi") == []
