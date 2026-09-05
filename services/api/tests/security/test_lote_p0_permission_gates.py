"""
Segurança — LOTE P0 de gates de permissão (Bloco 3: A REDE).

Todo teste aqui CRUZA A FRONTEIRA HTTP (client.get/post/put/delete), nunca
chama a função do handler direto: a lição da casa é que teste que não cruza a
rota já deixou bug passar por review e por CI verde.

Buracos fechados (falha-antes → passa-depois):

  1. GET /api/v1/quality/andon/<camera_id> rodava SEM JWT e ITERAVA TODOS os
     schemas de tenant atrás da câmera. O único portão era allowlist de IP
     privado — inútil atrás de proxy (o remote_addr é o do proxy) e desligável
     por ANDON_ALLOW_EXTERNAL=true. Vazava dado de produção entre clientes.

  2. DELETE /api/cameras/<id> (e POST/PUT/archive/restore) aceitava QUALQUER
     papel do tenant. O DELETE tem CASCADE em alerts/events/operations.

  3. 9 rotas mutantes de treino (6 em training/routes.py, 3 em quality/
     routes.py) sem gate nenhum, num arquivo onde require_training_role já era
     usado 14 vezes.

Chaves usadas são as do registry canônico (app/core/permissions.py) — fiação,
não design novo. Cada teste checa também que o efeito colateral NÃO acontece
(service/pool não chamado), não só o código de status.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"
SCHEMA = "tenant_test"
CAM = str(uuid4())


def _auth(app, role: str, perms: list[str] | None = None) -> dict[str, str]:
    claims: dict = {"tenant_id": TENANT, "tenant_schema": SCHEMA, "role": role}
    if perms is not None:
        claims["perms"] = perms
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _mock_pool():
    """(pool, cur) — pool cujo get_connection() é context manager."""
    pool, conn, cur = MagicMock(), MagicMock(), MagicMock()
    conn.cursor.return_value = cur
    pool.get_connection.return_value.__enter__ = MagicMock(return_value=conn)
    pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool, cur


# ═══════════════════════════════════════════════════════════════════════════
# 1. ANDON — exigia só IP privado, varria todos os schemas de tenant
# ═══════════════════════════════════════════════════════════════════════════

class TestAndonExigeJWTEEscopoDeTenant:
    URL = f"/api/v1/quality/andon/{CAM}"

    def test_sem_token_nao_entra(self, client):
        """FALHA-ANTES: sem Authorization a rota executava a consulta.
        PASSA-DEPOIS: 401 antes de tocar no banco."""
        pool, cur = _mock_pool()
        with patch("app.api.v1.quality.routes._get_pool", return_value=pool):
            resp = client.get(self.URL)
        assert resp.status_code == 401, resp.get_data(as_text=True)
        cur.execute.assert_not_called()

    def test_nao_varre_schemas_e_usa_o_do_jwt(self, app, client):
        """FALHA-ANTES: SELECT schema_name FROM public.tenants + loop por todos
        os schemas (psycopg2.connect cru, fora do pool).
        PASSA-DEPOIS: uma única consulta, no schema do JWT."""
        pool, cur = _mock_pool()
        cur.fetchone.return_value = None  # câmera não existe neste tenant
        with patch("app.api.v1.quality.routes._get_pool", return_value=pool):
            resp = client.get(self.URL, headers=_auth(app, "operator"))

        assert resp.status_code == 404, resp.get_json()
        sqls = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        assert "public.tenants" not in sqls, f"ainda varre schemas: {sqls}"
        assert cur.execute.call_args_list[0].args == (
            "SET search_path TO %s, public", (SCHEMA,),
        )

    def test_papel_sem_quality_read_barrado(self, app, client):
        """Chave inexistente/negada no token granular → 403 sem tocar no banco."""
        pool, cur = _mock_pool()
        with patch("app.api.v1.quality.routes._get_pool", return_value=pool):
            resp = client.get(self.URL, headers=_auth(app, "viewer", perms=[]))
        assert resp.status_code == 403, resp.get_json()
        cur.execute.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# 2. CÂMERAS — CRUD mutante aceitava qualquer papel do tenant
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def camera_service():
    svc = MagicMock()
    svc.create_camera.return_value = {"id": CAM}
    svc.update_camera.return_value = {"id": CAM}
    svc.delete_camera.return_value = None
    svc.archive_camera.return_value = {"id": CAM}
    svc.restore_camera.return_value = {"id": CAM}
    base = "app.api.v1.cameras.crud_handlers."
    with patch(base + "_get_camera_service", return_value=svc), \
         patch(base + "_is_admin", return_value=False), \
         patch(base + "platform_flag_enabled", return_value=False):
        yield svc


SEM_PODER = ["viewer", "operator", "trainer", "analyst"]


class TestCameraDeleteGate:
    """DELETE tem CASCADE em alerts/events/operations — chave cameras:delete."""

    @pytest.mark.parametrize("role", SEM_PODER)
    def test_papel_sem_permissao_nao_apaga(self, app, client, camera_service, role):
        """FALHA-ANTES: HTTP 200 e camera_repo.delete() executado."""
        resp = client.delete(f"/api/cameras/{CAM}", headers=_auth(app, role))
        assert resp.status_code == 403, resp.get_json()
        camera_service.delete_camera.assert_not_called()

    @pytest.mark.parametrize("role", ["admin", "superadmin"])
    def test_admin_apaga(self, app, client, camera_service, role):
        resp = client.delete(f"/api/cameras/{CAM}", headers=_auth(app, role))
        assert resp.status_code == 200, resp.get_json()
        camera_service.delete_camera.assert_called_once()

    def test_grant_granular_passa(self, app, client, camera_service):
        """O gate lê o registry, não uma lista de papéis embutida."""
        resp = client.delete(
            f"/api/cameras/{CAM}",
            headers=_auth(app, "viewer", perms=["cameras:delete"]),
        )
        assert resp.status_code == 200, resp.get_json()
        camera_service.delete_camera.assert_called_once()

    def test_deny_granular_barra_admin(self, app, client, camera_service):
        resp = client.delete(
            f"/api/cameras/{CAM}", headers=_auth(app, "admin", perms=[]),
        )
        assert resp.status_code == 403, resp.get_json()
        camera_service.delete_camera.assert_not_called()


class TestCameraEscritaGate:
    """create/update/archive/restore — chave cameras:write (a MESMA que o
    front já usa para mostrar os botões, ver app/epi/Cameras.tsx)."""

    CASOS = [
        ("post", "/api/cameras", "create_camera"),
        ("put", f"/api/cameras/{CAM}", "update_camera"),
        ("post", f"/api/cameras/{CAM}/archive", "archive_camera"),
        ("post", f"/api/cameras/{CAM}/restore", "restore_camera"),
    ]

    @pytest.mark.parametrize("metodo,url,metodo_service", CASOS)
    @pytest.mark.parametrize("role", SEM_PODER)
    def test_papel_sem_permissao_barrado(
        self, app, client, camera_service, metodo, url, metodo_service, role
    ):
        resp = getattr(client, metodo)(
            url, json={"name": "cam", "host": "10.0.0.9"}, headers=_auth(app, role)
        )
        assert resp.status_code == 403, resp.get_json()
        getattr(camera_service, metodo_service).assert_not_called()

    @pytest.mark.parametrize("metodo,url,metodo_service", CASOS)
    def test_admin_passa(self, app, client, camera_service, metodo, url, metodo_service):
        resp = getattr(client, metodo)(
            url, json={"name": "cam", "host": "10.0.0.9"}, headers=_auth(app, "admin")
        )
        assert resp.status_code != 403, resp.get_json()
        getattr(camera_service, metodo_service).assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# 3. TREINO — 6 rotas mutantes em training/ + 3 em quality/
# ═══════════════════════════════════════════════════════════════════════════

_TRAINING_HANDLERS = (
    "create_video_handler",
    "save_annotations_handler",
    "create_job_handler",
    "validate_frame_handler",
    "stop_job_handler",
    "upsert_scenario_config_handler",
)


@pytest.fixture()
def training_handlers():
    with ExitStack() as stack:
        yield {
            nome: stack.enter_context(
                patch(
                    f"app.api.v1.training.routes.{nome}",
                    return_value=({"success": True}, 200),
                )
            )
            for nome in _TRAINING_HANDLERS
        }


FRAME = str(uuid4())
JOB = str(uuid4())
MODELO = str(uuid4())

# (método, url, handler, papéis barrados, papéis que passam)
ROTAS_TREINO = [
    # training:write → superadmin, admin, trainer
    ("post", "/api/training/videos", "create_video_handler",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    ("post", "/api/training/jobs", "create_job_handler",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    ("post", f"/api/training/jobs/{JOB}/stop", "stop_job_handler",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    ("put", f"/api/training/scenarios/{MODELO}/config", "upsert_scenario_config_handler",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    # frames:annotate → superadmin, admin, operator, trainer (inclui operator:
    # é quem anota no chão de fábrica, e o front libera o Estúdio por essa
    # mesma chave — usar training:write aqui tiraria o anotador da fila)
    ("post", f"/api/training/frames/{FRAME}/annotations", "save_annotations_handler",
     ["viewer", "analyst"], ["admin", "operator", "trainer"]),
    ("post", f"/api/training/frames/{FRAME}/validate", "validate_frame_handler",
     ["viewer", "analyst"], ["admin", "operator", "trainer"]),
]


class TestTrainingRotasMutantes:
    @pytest.mark.parametrize("metodo,url,handler,barrados,liberados", ROTAS_TREINO)
    def test_papel_errado_barrado(
        self, app, client, training_handlers, metodo, url, handler, barrados, liberados
    ):
        """FALHA-ANTES: 200, handler executado (só @jwt_required, sem gate)."""
        for role in barrados:
            resp = getattr(client, metodo)(url, json={}, headers=_auth(app, role))
            assert resp.status_code == 403, f"{role} em {url}: {resp.get_json()}"
        training_handlers[handler].assert_not_called()

    @pytest.mark.parametrize("metodo,url,handler,barrados,liberados", ROTAS_TREINO)
    def test_papel_certo_passa(
        self, app, client, training_handlers, metodo, url, handler, barrados, liberados
    ):
        for role in liberados:
            resp = getattr(client, metodo)(url, json={}, headers=_auth(app, role))
            assert resp.status_code == 200, f"{role} em {url}: {resp.get_json()}"
        assert training_handlers[handler].call_count == len(liberados)


INSPECAO = str(uuid4())

# (url, papéis barrados, papéis liberados)
ROTAS_QUALIDADE = [
    (f"/api/v1/quality/inspections/{INSPECAO}/create-training-job",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    ("/api/v1/quality/training/jobs",
     ["viewer", "operator", "analyst"], ["admin", "trainer"]),
    # ativar modelo = models:approve (superadmin, admin) — a chave do registry
    # cuja descrição É esta ação ("aprovar a publicação de um modelo treinado
    # para uso em produção"). Não é training:approve (só-superadmin): isso
    # tiraria o admin do tenant, que hoje ativa e é quem conhece a linha
    # (ver tests/unit/api/test_quality_activate_model_guard.py, que já exigia
    # 200 para admin antes deste PR).
    (f"/api/v1/quality/training/models/{MODELO}/activate",
     ["viewer", "operator", "analyst", "trainer"], ["admin", "superadmin"]),
]


class TestQualityRotasDeTreino:
    @pytest.mark.parametrize("url,barrados,liberados", ROTAS_QUALIDADE)
    def test_papel_errado_barrado(self, app, client, url, barrados, liberados):
        pool, cur = _mock_pool()
        with patch("app.api.v1.quality.routes._get_pool", return_value=pool):
            for role in barrados:
                resp = client.post(
                    url,
                    json={"name": "x", "source_video_r2_key": "k", "camera_ids": [CAM]},
                    headers=_auth(app, role),
                )
                assert resp.status_code == 403, f"{role} em {url}: {resp.get_json()}"
        cur.execute.assert_not_called()

    @pytest.mark.parametrize("url,barrados,liberados", ROTAS_QUALIDADE)
    def test_papel_certo_passa_do_gate(self, app, client, url, barrados, liberados):
        """Passar do gate basta: o corpo depende de banco real, então só
        exigimos que NÃO seja 403 e que a consulta tenha começado."""
        pool, cur = _mock_pool()
        cur.fetchone.return_value = None
        with patch("app.api.v1.quality.routes._get_pool", return_value=pool):
            for role in liberados:
                resp = client.post(
                    url,
                    json={"name": "x", "source_video_r2_key": "k", "camera_ids": [CAM]},
                    headers=_auth(app, role),
                )
                assert resp.status_code != 403, f"{role} em {url}: {resp.get_json()}"
        assert cur.execute.called


# ═══════════════════════════════════════════════════════════════════════════
# 4. O registry não pode mentir sobre quem ele barra
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryEnforcedHonesto:
    """`enforced=True` no registry vira afirmação verificada, não enfeite.

    O flag existia desde WS7 e ninguém conferia: `training:write` estava
    marcado False mesmo com 14 rotas usando require_training_role('write'),
    e chave nenhuma marcada True era checada de volta. Um flag que ninguém
    verifica é exatamente o tipo de confiança ornamental que já mordeu a casa.
    """

    # ponytail: varredura textual, não AST. Um módulo que só CITA a chave num
    # comentário e gate outra passaria — troca aceita de propósito, porque
    # metade dos gates da casa passa a chave por constante
    # (_MANAGE_PERMISSION = "edge:manage" → require_permission(_MANAGE_PERMISSION))
    # e casar só a chamada literal daria falso-positivo em 4 gates reais. O que
    # este teste precisa pegar é chave marcada enforced que não existe em
    # arquivo de gate nenhum. Se um dia precisar de precisão, trocar por ast.walk.
    def _chaves_amarradas_a_rota(self) -> set[str]:
        import re
        from pathlib import Path

        from app.core.auth import _TRAINING_PERMISSION_KEYS

        raiz = Path(__file__).resolve().parents[2] / "app"
        gates = ("require_permission", "has_permission", "require_training_role")
        chaves: set[str] = set()
        for arquivo in raiz.rglob("*.py"):
            if arquivo.name == "permissions.py":
                continue  # o registry se cita; não conta como uso
            texto = arquivo.read_text(encoding="utf-8")
            if not any(g in texto for g in gates):
                continue
            chaves.update(re.findall(r'"([a-z_]+:[a-z_]+)"', texto))
            for nivel in re.findall(r'require_training_role\(\s*"([^"]+)"', texto):
                chave = _TRAINING_PERMISSION_KEYS.get(nivel)
                if chave:
                    chaves.add(chave)
        return chaves

    def test_toda_chave_marcada_enforced_tem_gate_real(self):
        from app.core.permissions import PERMISSION_REGISTRY

        declaradas = {
            k for k, meta in PERMISSION_REGISTRY.items() if meta["enforced"]
        }
        amarradas = self._chaves_amarradas_a_rota()
        mentirosas = sorted(declaradas - amarradas)
        assert not mentirosas, (
            "chaves marcadas enforced=True sem nenhum gate no código: "
            f"{mentirosas}"
        )

    def test_lote_p0_ficou_marcado(self):
        """As chaves fiadas neste PR precisam estar declaradas enforced."""
        from app.core.permissions import PERMISSION_REGISTRY

        for chave in (
            "cameras:write", "cameras:delete", "frames:annotate",
            "training:write", "training:approve", "models:approve",
            "quality:read",
        ):
            assert PERMISSION_REGISTRY[chave]["enforced"] is True, chave
