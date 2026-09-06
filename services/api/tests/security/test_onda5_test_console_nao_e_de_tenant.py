"""
Segurança — ONDA 5 / issue #787: ferramenta de PLATAFORMA não é de tenant.

Medido no aceite de 05/09 contra a API do DEV em `2538d047`, varrendo as 110
rotas sob `/admin` com token de admin REAL do tenant RVB
(`claude-ops@recognition.dev`): 93 barradas, e estas ALCANÇADAS:

    >>>> 503 POST /api/v1/admin/test-console/harness/start
         :: column "rtsp_url" of relation "cameras" does not exist
    >>>> 200 GET  /api/v1/admin/test-console/harness/status
    >>>> 200 GET  /api/v1/admin/test-console/models
    >>>> 200 GET  /api/v1/admin/test-console/evidence
    >>>> 200 GET  /api/v1/admin/introspection

O `503` é a prova mais dura: o gate não parou NADA — o handler rodou e só
quebrou num INSERT com coluna obsoleta. O que ele estava fazendo:
`_register_test_cameras()` gravando no tenant de teste da PLATAFORMA
(00000000-…-AA), que não é o tenant de quem chamou; na sequência setaria
chaves em Redis e despacharia tarefas Celery de inferência (GPU).

Causa: há DOIS blueprints de test-console registrados (app/__init__.py) e só
um estava fechado.

  app/api/v1/admin/routes_test_console.py  → /status /start /stop
      @require_superadmin  ✅ (já era, tests/admin/test_test_console.py)
  app/api/v1/admin/test_console_routes.py  → /harness/* /models /evidence
      @require_admin       ❌ ← esta frente
  app/api/v1/admin/introspection_routes.py → /introspection
      @require_admin       ❌ ← esta frente

403 e NÃO 404 (decisão registrada no PR): o 404 da casa (C-01,
`require_superadmin_or_404`) esconde a EXISTÊNCIA de recurso pertencente a
outro tenant. Aqui não há recurso de tenant nenhum — é rota de plataforma
cuja existência já é pública (o bundle do frontend que todo usuário baixa
tem o item "Console de Teste" em AdminLayout.tsx) e cuja metade irmã
(/test-console/status, /test-console/seed) JÁ responde 403 a admin de
tenant, com teste travando isso. Responder 404 em metade da mesma família
não esconderia nada e deixaria a API incoerente consigo mesma.

Todo teste aqui CRUZA A FRONTEIRA HTTP (client.get/post). Nas rotas barradas
exigimos 403 *e* que a porta do efeito colateral (Redis, banco, Celery) nunca
tenha sido tocada — status sozinho não prova que a escrita não aconteceu.
"""
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

# Tenant do CLIENTE (RVB no aceite) — o de teste da plataforma é o …AA
TENANT_CLIENTE = "11111111-1111-1111-1111-111111111111"
SCHEMA_CLIENTE = "tenant_rvb"

TC = "app.api.v1.admin.test_console_routes."
INTRO = "app.api.v1.admin.introspection_routes."

# (método, url) — as 5 rotas que o admin de tenant alcançava
ROTAS_HARNESS = [
    ("post", "/api/v1/admin/test-console/harness/start"),
    ("post", "/api/v1/admin/test-console/harness/stop"),
    ("get", "/api/v1/admin/test-console/harness/status"),
    ("get", "/api/v1/admin/test-console/models"),
    ("get", "/api/v1/admin/test-console/evidence"),
]

# Papéis de TENANT: nenhum deles é plataforma. `admin` é o que passava.
PAPEIS_DE_TENANT = ["viewer", "operator", "analyst", "trainer", "admin"]


def _auth(app, role: str) -> dict[str, str]:
    claims = {
        "tenant_id": TENANT_CLIENTE,
        "tenant_schema": SCHEMA_CLIENTE,
        "role": role,
    }
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def portas_harness():
    """Toda porta de efeito colateral do harness, mockada e observável.

    Ordem do yield = ordem dos `patch` (Redis config, Redis de segmentos,
    INSERT de câmeras, DELETE de câmeras, despacho Celery, pool cru).
    """
    with patch(TC + "_get_redis") as redis_cfg, \
         patch(TC + "_get_segments_redis") as redis_seg, \
         patch(TC + "_register_test_cameras") as reg_cams, \
         patch(TC + "_delete_test_cameras") as del_cams, \
         patch(TC + "_dispatch_inference_tasks") as dispatch, \
         patch(TC + "_get_pool") as pool:
        redis_cfg.return_value.get.return_value = None
        reg_cams.return_value = [
            {"id": str(uuid4()), "name": "c", "rtsp_url": "rtsp://x", "index": 0}
        ]
        dispatch.return_value = 0
        yield (redis_cfg, redis_seg, reg_cams, del_cams, dispatch, pool)


@pytest.fixture()
def portas_leitura():
    """Consultas do console ao banco do tenant de teste da plataforma."""
    with patch(TC + "_list_models", return_value=[]) as models, \
         patch(TC + "_list_recent_evidence", return_value=[]) as evid:
        yield (models, evid)


class TestHarnessDaPlataformaNaoEDeTenant:
    """#787 — o admin da RVB disparava escrita e trabalho de GPU num tenant
    que não é o dele."""

    @pytest.mark.parametrize("metodo,url", ROTAS_HARNESS)
    @pytest.mark.parametrize("role", PAPEIS_DE_TENANT)
    def test_papel_de_tenant_barrado(
        self, app, client, portas_harness, portas_leitura, metodo, url, role
    ):
        """FALHA-ANTES com role='admin': 200/503 e o handler já no Redis/INSERT."""
        resp = getattr(client, metodo)(url, json={"cameras": 2}, headers=_auth(app, role))
        assert resp.status_code == 403, f"{role} {metodo.upper()} {url}: {resp.get_json()}"
        for porta in (*portas_harness, *portas_leitura):
            porta.assert_not_called()

    @pytest.mark.parametrize("metodo,url", ROTAS_HARNESS)
    def test_superadmin_passa_do_gate(
        self, app, client, portas_harness, portas_leitura, metodo, url
    ):
        """Passar do gate basta: o corpo depende de Redis/banco reais."""
        resp = getattr(client, metodo)(
            url, json={"cameras": 2}, headers=_auth(app, "superadmin")
        )
        assert resp.status_code != 403, f"superadmin {metodo.upper()} {url}: {resp.get_json()}"

    def test_sem_token_continua_401(self, app, client, portas_harness, portas_leitura):
        resp = client.get("/api/v1/admin/test-console/harness/status")
        assert resp.status_code == 401

    def test_seed_continua_superadmin(self, app, client, portas_harness):
        """Guarda de não-regressão: /seed já era superadmin (#787 não afrouxa)."""
        resp = client.post(
            "/api/v1/admin/test-console/seed",
            json={"password": "x"},
            headers=_auth(app, "admin"),
        )
        assert resp.status_code == 403, resp.get_json()


class TestIntrospeccaoDoProcessoNaoEDeTenant:
    """#787 — telemetria do processo que serve TODOS os clientes."""

    @pytest.mark.parametrize("role", PAPEIS_DE_TENANT)
    def test_papel_de_tenant_barrado(self, app, client, role):
        """FALHA-ANTES com role='admin': 200 com rss/uptime/requests_served."""
        with patch(INTRO + "_live_view_snapshot", return_value={"degraded": False}) as snap:
            resp = client.get("/api/v1/admin/introspection", headers=_auth(app, role))
        assert resp.status_code == 403, f"{role}: {resp.get_json()}"
        snap.assert_not_called()

    def test_superadmin_passa(self, app, client):
        with patch(INTRO + "_live_view_snapshot", return_value={"degraded": False}):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth(app, "superadmin")
            )
        assert resp.status_code == 200, resp.get_json()

    def test_sem_token_continua_401(self, client):
        assert client.get("/api/v1/admin/introspection").status_code == 401


class TestVarreduraNaoRegride:
    """A varredura da issue vira teste: nenhum dos dois volta a `require_admin`.

    ponytail: contagem textual, igual à varredura da issue — não é AST. O que
    precisa pegar é a REGRESSÃO do gate no arquivo, que foi o defeito real.
    Comentário/docstring citando `@require_admin` não conta (só decorator em
    início de linha).
    """

    @pytest.mark.parametrize(
        "arquivo,minimo",
        [("test_console_routes.py", 6), ("introspection_routes.py", 1)],
    )
    def test_arquivo_so_tem_gate_de_superadmin(self, arquivo, minimo):
        caminho = (
            Path(__file__).resolve().parents[2]
            / "app" / "api" / "v1" / "admin" / arquivo
        )
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        gates_admin = [ln for ln in linhas if ln.strip() == "@require_admin"]
        gates_super = [ln for ln in linhas if ln.strip() == "@require_superadmin"]
        assert not gates_admin, (
            f"{arquivo}: @require_admin de volta em ferramenta de plataforma (#787)"
        )
        assert len(gates_super) >= minimo, (
            f"{arquivo}: {len(gates_super)} gates de superadmin, esperado >= {minimo}"
        )

    def test_irmao_ja_fechado_continua_fechado(self):
        """`routes_test_console.py` (/status /start /stop) nunca foi o furo —
        o teste existe para o par não divergir de novo."""
        caminho = (
            Path(__file__).resolve().parents[2]
            / "app" / "api" / "v1" / "admin" / "routes_test_console.py"
        )
        texto = caminho.read_text(encoding="utf-8")
        assert "@require_admin\n" not in texto
        assert texto.count("@require_superadmin") >= 3
