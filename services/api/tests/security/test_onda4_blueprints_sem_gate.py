"""
Segurança — ONDA 4: os três blueprints que rodavam SÓ com @jwt_required().

Medido no aceite de 05/09 contra a API do DEV em `2538d047`, com token de
operador REAL do tenant RVB (issues #782 e #785):

    grep -c "require_permission|require_training_role|has_permission" \
        app/api/v1/{videos,rules,operations}/routes.py  →  0, 0, 0

    >>>> 200 DELETE /api/v1/videos/<id>      :: {"deleted": true}   ← IRREVERSÍVEL
    >>>> 404 DELETE /api/rules/<id>          :: "Regra não encontrada"
    >>>> 404 DELETE /api/operations/<id>     :: "Operação não encontrada"

O 404 ali NÃO era gate: era o handler já no banco procurando a linha. A prova
do 200 é a mais dura — o operador apagou vídeo de treino E os frames dele.

Todo teste aqui CRUZA A FRONTEIRA HTTP (client.post/put/delete). Nas rotas
barradas exigimos 403 *e* que a porta de entrada do efeito colateral (service,
repo, pool, storage) NUNCA tenha sido chamada — status sozinho não prova que a
escrita não aconteceu.

⛔ Leitura (GET) fica de fora de propósito: quebrar tela de usuário legítimo na
véspera do go-live é pior que o risco que este PR fecha.

Chaves (registry canônico, app/core/permissions.py):
  videos      → training:write   (a MESMA de POST /api/training/videos, que o
                                  #679 já fechou — vídeo é a entrada do treino)
  rules       → rules:write      (chave NOVA: não havia nada para "regra de
                                  alerta"; superadmin+admin, igual ao resto da
                                  configuração de tenant)
  operations  → cameras:configure para criar/editar/apagar (é configuração da
                câmera, mesma chave que o #679 usou na config de qualidade) e
                cameras:control para pausar/retomar/testar (operação do dia a
                dia — o operador continua podendo pausar o que já existe).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"
SCHEMA = "tenant_test"
VIDEO = str(uuid4())
REGRA = str(uuid4())
CAM = str(uuid4())
OP = 4242


def _auth(app, role: str, perms: list[str] | None = None) -> dict[str, str]:
    claims: dict = {"tenant_id": TENANT, "tenant_schema": SCHEMA, "role": role}
    if perms is not None:
        claims["perms"] = perms
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. VIDEOS — 10 rotas mutantes, incluindo o DELETE que saiu 200 no DEV
# ═══════════════════════════════════════════════════════════════════════════

# (método, url) — training:write → superadmin, admin, trainer
ROTAS_VIDEOS = [
    ("post", "/api/v1/videos/upload"),
    ("post", "/api/v1/videos/upload-url"),
    ("post", f"/api/v1/videos/{VIDEO}/extract"),
    ("delete", f"/api/v1/videos/{VIDEO}"),
    ("post", f"/api/v1/videos/{VIDEO}/upload-complete"),
    ("post", f"/api/v1/videos/{VIDEO}/retry-extraction"),
    ("post", f"/api/v1/videos/{VIDEO}/frames/upload"),
    ("post", f"/api/v1/videos/{VIDEO}/finalize-extraction"),
    ("post", f"/api/v1/videos/{VIDEO}/server-extract"),
    ("post", "/api/v1/videos/images/upload"),
]


@pytest.fixture()
def portas_videos():
    """Toda porta de efeito colateral do blueprint, mockada e observável."""
    base = "app.api.v1.videos.routes."
    with patch(base + "_video_service") as svc, \
         patch(base + "_video_repo") as vrepo, \
         patch(base + "_frame_repo") as frepo, \
         patch(base + "get_storage") as storage, \
         patch(base + "DatabasePool") as pool:
        yield (svc, vrepo, frepo, storage, pool.get_instance)


class TestVideosRotasMutantes:
    """#782 — o único caminho irreversível da régua: DELETE apaga os frames."""

    @pytest.mark.parametrize("metodo,url", ROTAS_VIDEOS)
    @pytest.mark.parametrize("role", ["viewer", "operator", "analyst"])
    def test_papel_sem_treino_barrado(self, app, client, portas_videos, metodo, url, role):
        """FALHA-ANTES: 200/400/404 com o handler rodando (só @jwt_required)."""
        resp = getattr(client, metodo)(url, json={}, headers=_auth(app, role))
        assert resp.status_code == 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"
        for porta in portas_videos:
            porta.assert_not_called()

    @pytest.mark.parametrize("metodo,url", ROTAS_VIDEOS)
    @pytest.mark.parametrize("role", ["admin", "trainer", "superadmin"])
    def test_papel_de_treino_passa(self, app, client, portas_videos, metodo, url, role):
        """Passar do gate basta: o corpo depende de arquivo/banco reais."""
        resp = getattr(client, metodo)(url, json={}, headers=_auth(app, role))
        assert resp.status_code != 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"

    def test_grant_granular_passa(self, app, client, portas_videos):
        """O gate lê o registry, não uma lista de papéis embutida."""
        resp = client.delete(
            f"/api/v1/videos/{VIDEO}",
            headers=_auth(app, "viewer", perms=["training:write"]),
        )
        assert resp.status_code != 403, resp.get_json()

    def test_deny_granular_barra_admin(self, app, client, portas_videos):
        resp = client.delete(
            f"/api/v1/videos/{VIDEO}", headers=_auth(app, "admin", perms=[]),
        )
        assert resp.status_code == 403, resp.get_json()
        for porta in portas_videos:
            porta.assert_not_called()

    def test_leitura_continua_liberada(self, app, client, portas_videos):
        """Guarda de regressão do escopo: GET não entrou nesta onda."""
        portas_videos[0].return_value.get_video_status.return_value = {}
        resp = client.get(
            f"/api/v1/videos/{VIDEO}/status", headers=_auth(app, "viewer"),
        )
        assert resp.status_code != 403, resp.get_json()


# ═══════════════════════════════════════════════════════════════════════════
# 2. RULES — a regra é o que decide se a violação vira alerta
# ═══════════════════════════════════════════════════════════════════════════

# (método, url) — rules:write → superadmin, admin
ROTAS_RULES = [
    ("post", "/api/rules"),
    ("put", f"/api/rules/{REGRA}"),
    ("delete", f"/api/rules/{REGRA}"),
    ("post", f"/api/rules/{REGRA}/toggle"),
]

CORPO_REGRA = {"name": "r", "camera_id": CAM, "class_name": "capacete"}


@pytest.fixture()
def pool_rules():
    pool, conn, cur = MagicMock(), MagicMock(), MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    pool.get_connection.return_value.__enter__ = MagicMock(return_value=conn)
    pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = None
    cur.fetchall.return_value = []
    with patch("app.api.v1.rules.routes._get_pool", return_value=pool):
        yield cur


class TestRulesRotasMutantes:
    @pytest.mark.parametrize("metodo,url", ROTAS_RULES)
    @pytest.mark.parametrize("role", ["viewer", "operator", "analyst", "trainer"])
    def test_papel_sem_permissao_barrado(self, app, client, pool_rules, metodo, url, role):
        """FALHA-ANTES: 404 'Regra não encontrada' — o handler foi ao banco."""
        resp = getattr(client, metodo)(url, json=CORPO_REGRA, headers=_auth(app, role))
        assert resp.status_code == 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"
        pool_rules.execute.assert_not_called()

    @pytest.mark.parametrize("metodo,url", ROTAS_RULES)
    @pytest.mark.parametrize("role", ["admin", "superadmin"])
    def test_admin_passa_do_gate(self, app, client, pool_rules, metodo, url, role):
        resp = getattr(client, metodo)(url, json=CORPO_REGRA, headers=_auth(app, role))
        assert resp.status_code != 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"

    def test_listagem_continua_liberada(self, app, client, pool_rules):
        resp = client.get("/api/rules", headers=_auth(app, "viewer"))
        assert resp.status_code != 403, resp.get_json()


# ═══════════════════════════════════════════════════════════════════════════
# 3. OPERATIONS — o motor de operações (PR #203) roda em cima dessas linhas
# ═══════════════════════════════════════════════════════════════════════════

# (método, url, papéis barrados, papéis liberados)
ROTAS_OPERATIONS = [
    # cameras:configure → superadmin, admin
    ("post", f"/api/cameras/{CAM}/operations",
     ["viewer", "operator", "analyst", "trainer"], ["admin", "superadmin"]),
    ("put", f"/api/operations/{OP}",
     ["viewer", "operator", "analyst", "trainer"], ["admin", "superadmin"]),
    ("delete", f"/api/operations/{OP}",
     ["viewer", "operator", "analyst", "trainer"], ["admin", "superadmin"]),
    # cameras:control → superadmin, admin, operator
    ("post", f"/api/operations/{OP}/pause",
     ["viewer", "analyst", "trainer"], ["admin", "operator", "superadmin"]),
    ("post", f"/api/operations/{OP}/resume",
     ["viewer", "analyst", "trainer"], ["admin", "operator", "superadmin"]),
    ("post", f"/api/operations/{OP}/test",
     ["viewer", "analyst", "trainer"], ["admin", "operator", "superadmin"]),
]

CORPO_OP = {"type_id": "epi_zone", "name": "op", "config": {}}


@pytest.fixture()
def repo_operations():
    repo = MagicMock()
    repo.get_by_id.return_value = None  # operação inexistente → 404 do handler
    with patch("app.api.v1.operations.routes._get_repo", return_value=repo):
        yield repo


class TestOperationsRotasMutantes:
    @pytest.mark.parametrize("metodo,url,barrados,liberados", ROTAS_OPERATIONS)
    def test_papel_errado_barrado(
        self, app, client, repo_operations, metodo, url, barrados, liberados
    ):
        """FALHA-ANTES: 404 'Operação não encontrada' — repo.get_by_id rodou."""
        for role in barrados:
            resp = getattr(client, metodo)(url, json=CORPO_OP, headers=_auth(app, role))
            assert resp.status_code == 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"
        repo_operations.get_by_id.assert_not_called()
        repo_operations.create.assert_not_called()
        repo_operations.delete.assert_not_called()

    @pytest.mark.parametrize("metodo,url,barrados,liberados", ROTAS_OPERATIONS)
    def test_papel_certo_passa_do_gate(
        self, app, client, repo_operations, metodo, url, barrados, liberados
    ):
        for role in liberados:
            resp = getattr(client, metodo)(url, json=CORPO_OP, headers=_auth(app, role))
            assert resp.status_code != 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"

    def test_listagem_continua_liberada(self, app, client, repo_operations):
        repo_operations.list_by_camera.return_value = []
        resp = client.get(
            f"/api/cameras/{CAM}/operations", headers=_auth(app, "viewer"),
        )
        assert resp.status_code != 403, resp.get_json()


# ═══════════════════════════════════════════════════════════════════════════
# 4. A varredura vira teste: nenhum dos três volta a ficar sem gate
# ═══════════════════════════════════════════════════════════════════════════

class TestVarreduraNaoRegride:
    """O que a re-medição contou na mão (`grep -c` = 0) passa a falhar o CI.

    ponytail: contagem textual, igual à varredura da issue. Não é AST — um
    decorator citado só em comentário passaria. O que precisa pegar é a
    REGRESSÃO de arquivo inteiro sem gate, que foi o defeito real.
    """

    @pytest.mark.parametrize(
        "blueprint,minimo", [("videos", 10), ("rules", 4), ("operations", 6)]
    )
    def test_blueprint_tem_gate(self, blueprint, minimo):
        from pathlib import Path

        arquivo = (
            Path(__file__).resolve().parents[2]
            / "app" / "api" / "v1" / blueprint / "routes.py"
        )
        texto = arquivo.read_text(encoding="utf-8")
        n = texto.count("@require_permission(")
        assert n >= minimo, (
            f"{blueprint}/routes.py tem {n} gates, esperado >= {minimo} "
            "(issues #782/#785: os três já rodaram com ZERO)"
        )
