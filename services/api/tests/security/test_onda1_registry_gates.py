"""
Segurança — ONDA 1 da issue #678: as chaves do registry que MUTAM dado.

O lote P0 (tests/security/test_lote_p0_permission_gates.py) fechou andon,
CRUD de câmera e treino. Sobraram 24 chaves do registry canônico que existiam
na tela de roles, o admin marcava e desmarcava, e o backend ignorava. Esta
onda amarra as 8 que MUDAM dado do cliente:

  counting:write      sessões de contagem (iniciar/atualizar/encerrar/placa)
  verification:write  veredito humano em alerta e em inspeção de qualidade
  alerts:feedback     correção de bbox e registro de feedback de detecção
  quality:write       concluir retrabalho
  cameras:control     parar stream e mudar FPS/qualidade/coleta da câmera
  branding:write      logo, cores e nome do produto do tenant
  admin:roles         criar/editar/apagar role customizada
  admin:users         atribuir role a um usuário

Duas naturezas de conserto, e a diferença importa na hora de ler o resultado:

  A) SEM GATE NENHUM (só @jwt_required) — counting, verification, alerts,
     feedback, quality, cameras. Aqui o teste falha-antes com 200/201: viewer
     encerrava sessão de contagem, julgava alerta e mudava o FPS por curl.

  B) GATE POR ROLE (@require_admin) — branding e roles. Não era buraco aberto,
     mas ignorava custom_role e overrides: o tenant criava role com
     `branding:write`, o usuário marcava na UI, e a rota continuava decidindo
     por `role == 'admin'`. O role-set é IDÊNTICO ao do decorator anterior
     (superadmin, admin) — paridade — e o que muda é a permissão granular
     passar a valer. O teste do grant/deny granular é o que falha-antes aqui.

Todo teste CRUZA A FRONTEIRA HTTP (client.post/patch/delete), nunca chama o
handler direto, e checa também que o efeito colateral NÃO aconteceu — não só
o código de status. Cross-tenant continua 404 (C-01) e não é assunto aqui.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"
SCHEMA = "tenant_test"
CAM = str(uuid4())
SESSAO = str(uuid4())
ALERTA = str(uuid4())
INSPECAO = str(uuid4())
RETRABALHO = str(uuid4())
ROLE_ID = str(uuid4())
USUARIO = str(uuid4())


def _auth(app, role: str, perms: list[str] | None = None) -> dict[str, str]:
    claims: dict = {
        "tenant_id": TENANT,
        "tenant_schema": SCHEMA,
        "role": role,
        # módulos completos: o 403 que o teste observa é sempre o gate de
        # PERMISSÃO, nunca o gate de módulo do tenant.
        "modules": ["epi", "quality", "counting"],
    }
    if perms is not None:
        claims["perms"] = perms
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _pool_mock():
    """pool cujo get_connection() é context manager; cursor com fetchone dict."""
    pool, conn, cur = MagicMock(), MagicMock(), MagicMock()
    conn.cursor.return_value = cur
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    pool.get_connection.return_value.__enter__ = MagicMock(return_value=conn)
    pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool, cur


@pytest.fixture()
def alvos():
    """Todos os colaboradores das rotas desta onda, mockados de uma vez.

    Devolve um dict {apelido: mock} — a tabela de rotas aponta para
    (apelido, método) como EFEITO COLATERAL observável.
    """
    counting_svc = MagicMock()
    counting_svc.start_session.return_value = {"id": SESSAO}
    counting_svc.update_session.return_value = {"id": SESSAO}
    counting_svc.stop_session.return_value = {"id": SESSAO}

    counting_repo = MagicMock()
    counting_repo.update_plate.return_value = {"id": SESSAO}

    verif_svc = MagicMock()
    verif_svc.human_review.return_value = 1

    alerts_repo = MagicMock()
    alerts_repo.corrigir_bboxes.return_value = {
        "violations": [], "violations_historico": [],
    }

    feedback_repo = MagicMock()
    feedback_repo.create.return_value = {"id": str(uuid4())}

    gate_svc = MagicMock()
    gate_svc.complete_rework.return_value = {"id": RETRABALHO}

    quality_pool, quality_cur = _pool_mock()
    quality_cur.fetchone.return_value = {
        "id": INSPECAO, "camera_id": None, "clip_r2_key": None,
        "feedback_status": "confirmed",
    }

    branding_pool, branding_cur = _pool_mock()
    branding_cur.fetchone.return_value = {"id": TENANT}

    roles_repo = MagicMock()
    roles_repo.create.return_value = {"id": ROLE_ID}
    roles_repo.update.return_value = {"id": ROLE_ID}
    roles_repo.get_by_id.return_value = {"id": ROLE_ID}
    roles_repo.count_users_with_role.return_value = 0
    roles_repo.delete.return_value = True
    roles_repo.set_user_custom_role.return_value = True

    segments_redis = MagicMock()
    camera_svc = MagicMock()
    camera_svc.patch_config.return_value = {
        "id": CAM, "tenant_id": TENANT, "site_id": None, "fps_target": 5,
    }

    p = "app.api.v1."
    with ExitStack() as st:
        st.enter_context(patch(p + "counting.routes._get_service", return_value=counting_svc))
        st.enter_context(patch(p + "counting.routes._get_repo", return_value=counting_repo))
        st.enter_context(patch(p + "verification.routes._svc", verif_svc))
        st.enter_context(patch(p + "alerts.routes._get_repo", return_value=alerts_repo))
        st.enter_context(patch(p + "alerts.routes._nome_usuario_atual", return_value="Fulana"))
        st.enter_context(patch(p + "feedback.routes._get_repo", return_value=feedback_repo))
        st.enter_context(patch(p + "quality.routes._get_pool", return_value=quality_pool))
        st.enter_context(patch(p + "quality.routes._get_gate_service", return_value=gate_svc))
        st.enter_context(patch(p + "branding.routes._pool", return_value=branding_pool))
        st.enter_context(patch(p + "roles.routes._repo", return_value=roles_repo))
        st.enter_context(patch(p + "cameras.stream_handlers.get_segments_redis", return_value=segments_redis))
        st.enter_context(patch(p + "cameras.stream_handlers._get_redis", return_value=MagicMock()))
        st.enter_context(patch(p + "cameras.config_handler._get_camera_service", return_value=camera_svc))
        yield {
            "counting_svc": counting_svc,
            "counting_repo": counting_repo,
            "verif_svc": verif_svc,
            "alerts_repo": alerts_repo,
            "feedback_repo": feedback_repo,
            "gate_svc": gate_svc,
            "quality_cur": quality_cur,
            "branding_cur": branding_cur,
            "roles_repo": roles_repo,
            "segments_redis": segments_redis,
            "camera_svc": camera_svc,
        }


TODOS = ("superadmin", "admin", "operator", "analyst", "trainer", "viewer")


def _sem(*roles: str) -> list[str]:
    """Papéis que NÃO estão no role-set — os que o gate tem de barrar."""
    return [r for r in TODOS if r not in roles]


_OPERACAO = ("superadmin", "admin", "operator")
_FEEDBACK = ("superadmin", "admin", "operator", "analyst")
_ADMIN = ("superadmin", "admin")

# (id, método, url, chave, corpo, role-set, (apelido do mock, método))
ROTAS = [
    # ── counting:write ──────────────────────────────────────────────────────
    ("counting_start", "post", "/api/counting/sessions", "counting:write",
     {"camera_id": CAM}, _OPERACAO, ("counting_svc", "start_session")),
    ("counting_update", "patch", f"/api/counting/sessions/{SESSAO}", "counting:write",
     {"manual_count": 3}, _OPERACAO, ("counting_svc", "update_session")),
    ("counting_stop", "delete", f"/api/counting/sessions/{SESSAO}", "counting:write",
     None, _OPERACAO, ("counting_svc", "stop_session")),
    ("counting_plate", "patch", f"/api/counting/sessions/{SESSAO}/plate", "counting:write",
     {"plate_text": "ABC1D23"}, _OPERACAO, ("counting_repo", "update_plate")),
    # ── verification:write ──────────────────────────────────────────────────
    ("verificacao_review", "post", f"/api/verification/{ALERTA}/review", "verification:write",
     {"verdict": "approve"}, _OPERACAO, ("verif_svc", "human_review")),
    ("qualidade_feedback", "patch", f"/api/v1/quality/inspections/{INSPECAO}/feedback",
     "verification:write", {"status": "confirmed"}, _OPERACAO, ("quality_cur", "execute")),
    # ── alerts:feedback ─────────────────────────────────────────────────────
    ("alerta_corrigir_bbox", "patch", f"/api/alerts/{ALERTA}/violations", "alerts:feedback",
     {"correcoes": [{"index": 0, "bbox": [1, 2, 3, 4]}]}, _FEEDBACK,
     ("alerts_repo", "corrigir_bboxes")),
    ("feedback_deteccao", "post", "/api/v1/feedback", "alerts:feedback",
     {"verdict": "correct", "module": "epi"}, _FEEDBACK, ("feedback_repo", "create")),
    # ── quality:write ───────────────────────────────────────────────────────
    ("retrabalho_concluir", "patch", f"/api/v1/quality/gate/reworks/{RETRABALHO}/complete",
     "quality:write", None, _OPERACAO, ("gate_svc", "complete_rework")),
    # ── cameras:control ─────────────────────────────────────────────────────
    ("stream_parar", "post", f"/api/cameras/{CAM}/stream/stop", "cameras:control",
     None, _OPERACAO, ("segments_redis", "delete")),
    ("camera_config", "patch", f"/api/cameras/{CAM}/config", "cameras:control",
     {"fps_target": 15}, _OPERACAO, ("camera_svc", "patch_config")),
    # ── branding:write (era @require_admin — mesmo role-set) ────────────────
    ("branding_atualizar", "put", "/api/v1/admin/branding", "branding:write",
     {"branding": {"colors": {"primary": "#000"}}}, _ADMIN, ("branding_cur", "execute")),
    # ── admin:roles / admin:users (eram @require_admin — mesmo role-set) ────
    ("role_criar", "post", "/api/admin/roles", "admin:roles",
     {"name": "Turno B", "permissions": {}}, _ADMIN, ("roles_repo", "create")),
    ("role_editar", "put", f"/api/admin/roles/{ROLE_ID}", "admin:roles",
     {"name": "Turno C"}, _ADMIN, ("roles_repo", "update")),
    ("role_apagar", "delete", f"/api/admin/roles/{ROLE_ID}", "admin:roles",
     None, _ADMIN, ("roles_repo", "delete")),
    ("usuario_atribuir_role", "put", f"/api/admin/users/{USUARIO}/role", "admin:users",
     {"custom_role_id": ROLE_ID}, _ADMIN, ("roles_repo", "set_user_custom_role")),
    # ── os aliases /api/v1/** NÃO são porta dos fundos ──────────────────────
    # Mesmas view functions por add_url_rule (ADR-0041) — o gate viaja junto.
    # Sem esta linha, uma futura cópia do handler para o alias passaria batido.
    ("counting_stop_alias_v1", "delete", f"/api/v1/counting/sessions/{SESSAO}",
     "counting:write", None, _OPERACAO, ("counting_svc", "stop_session")),
    ("camera_config_alias_v1", "patch", f"/api/v1/cameras/{CAM}/config",
     "cameras:control", {"fps_target": 15}, _OPERACAO, ("camera_svc", "patch_config")),
]

IDS = [r[0] for r in ROTAS]


def _chamar(client, metodo, url, corpo, headers):
    kwargs = {"headers": headers}
    if corpo is not None:
        kwargs["json"] = corpo
    return getattr(client, metodo)(url, **kwargs)


def _efeito(alvos, alvo):
    apelido, metodo = alvo
    return getattr(alvos[apelido], metodo)


class TestOnda1RotasMutantes:
    """Papel errado é barrado E não deixa rastro; papel certo passa."""

    @pytest.mark.parametrize(
        "_id,metodo,url,chave,corpo,roles,alvo", ROTAS, ids=IDS,
    )
    def test_papel_errado_barrado_sem_efeito(
        self, app, client, alvos, _id, metodo, url, chave, corpo, roles, alvo
    ):
        """FALHA-ANTES: 200/201 e o serviço executado (ou, em branding/roles,
        403 pelo papel — mas sem consultar a permissão do registry)."""
        efeito = _efeito(alvos, alvo)
        for role in _sem(*roles):
            resp = _chamar(client, metodo, url, corpo, _auth(app, role))
            assert resp.status_code == 403, (
                f"{role} em {metodo.upper()} {url}: {resp.status_code} "
                f"{resp.get_data(as_text=True)[:200]}"
            )
        efeito.assert_not_called()

    @pytest.mark.parametrize(
        "_id,metodo,url,chave,corpo,roles,alvo", ROTAS, ids=IDS,
    )
    def test_papel_certo_passa(
        self, app, client, alvos, _id, metodo, url, chave, corpo, roles, alvo
    ):
        """O gate barra quem não tem a chave — não fecha a porta de quem tem.

        Sem claim `perms` no token (sessão antiga): o fallback do registry
        decide por role, exatamente o comportamento anterior nas rotas que já
        tinham gate — é isto que garante a paridade de branding/roles.
        """
        efeito = _efeito(alvos, alvo)
        for role in roles:
            resp = _chamar(client, metodo, url, corpo, _auth(app, role))
            assert resp.status_code != 403, (
                f"{role} em {metodo.upper()} {url}: {resp.get_data(as_text=True)[:200]}"
            )
        assert efeito.called, f"{metodo.upper()} {url} passou do gate mas não executou"

    @pytest.mark.parametrize(
        "_id,metodo,url,chave,corpo,roles,alvo", ROTAS, ids=IDS,
    )
    def test_grant_granular_vale_mais_que_o_papel(
        self, app, client, alvos, _id, metodo, url, chave, corpo, roles, alvo
    ):
        """viewer COM a chave passa; admin SEM a chave é barrado.

        Prova que o gate lê a claim `perms` (role customizada + overrides do
        tenant) e não um tuple de papéis embutido — o buraco que a issue #678
        chama de "permissão granular vira enfeite".
        """
        efeito = _efeito(alvos, alvo)
        liberado = _chamar(client, metodo, url, corpo, _auth(app, "viewer", perms=[chave]))
        assert liberado.status_code != 403, liberado.get_data(as_text=True)[:200]
        assert efeito.called

        efeito.reset_mock()
        negado = _chamar(
            client, metodo, url, corpo, _auth(app, "admin", perms=["cameras:read"]),
        )
        assert negado.status_code == 403, negado.get_data(as_text=True)[:200]
        efeito.assert_not_called()

    def test_sem_token_nao_entra(self, app, client, alvos):
        """Nenhuma destas rotas responde sem Authorization."""
        for _id, metodo, url, _chave, corpo, _roles, _alvo in ROTAS:
            resp = _chamar(client, metodo, url, corpo, {})
            assert resp.status_code == 401, f"{metodo.upper()} {url}: {resp.status_code}"


class TestRegistryDeclaraOQueFoiAmarrado:
    """`enforced=True` é afirmação verificada (TestRegistryEnforcedHonesto no
    lote P0 varre app/ e derruba quem mentir). Aqui só fixamos as 8 desta onda
    para que ninguém desmarque sem remover o gate."""

    CHAVES_DA_ONDA = (
        "counting:write", "verification:write", "alerts:feedback", "quality:write",
        "cameras:control", "branding:write", "admin:roles", "admin:users",
    )

    def test_chaves_da_onda_marcadas(self):
        from app.core.permissions import PERMISSION_REGISTRY

        for chave in self.CHAVES_DA_ONDA:
            assert PERMISSION_REGISTRY[chave]["enforced"] is True, chave

    def test_role_set_do_registry_e_o_do_gate_anterior(self):
        """Paridade das duas rotas que TROCARAM @require_admin por permissão:
        require_admin aceitava (superadmin, admin) — igual ao default_roles."""
        from app.core.permissions import default_roles_for

        for chave in ("branding:write", "admin:roles", "admin:users"):
            assert set(default_roles_for(chave)) == {"superadmin", "admin"}, chave


class TestLiveViewSegueAbertoAPapelSemControle:
    """A EXCEÇÃO desta onda, fixada como teste — não como comentário.

    `POST /cameras/<id>/stream/start` ficou DE PROPÓSITO sem
    `cameras:control`: é o caminho do live view (`hooks/useLiveView.ts` pede a
    URL tokenizada por ele) e `cameras:read` promete vídeo ao vivo a TODO
    papel. Gatear o start pela chave de controle apagaria a imagem de viewer,
    analyst e trainer — e é o "conserto" óbvio que a próxima onda tentaria
    fazer lendo só o `enforced=True` de cameras:control.

    Este teste é o que segura essa mão: se alguém amarrar o start na chave de
    controle, ele fica vermelho ANTES de a fábrica ficar sem imagem. O dia em
    que o start for partido em duas rotas (issue #714), o gate entra na
    metade que inicia o pipeline e este teste passa a olhar a outra.
    """

    def _mocks(self):
        svc = MagicMock()
        svc.build_stream_url.return_value = "rtsp://x/y"
        p = "app.api.v1.cameras.stream_handlers."
        st = ExitStack()
        st.enter_context(patch(p + "_get_camera_service", return_value=svc))
        st.enter_context(patch(p + "_get_redis", return_value=MagicMock()))
        st.enter_context(patch(p + "get_segments_redis", return_value=MagicMock()))
        st.enter_context(patch(p + "_is_gateway_online", return_value=True))
        return st

    def test_todo_papel_ainda_obtem_a_url_do_ao_vivo(self, app, client):
        with self._mocks():
            for role in TODOS:
                resp = client.post(
                    f"/api/cameras/{CAM}/stream/start", headers=_auth(app, role)
                )
                assert resp.status_code != 403, (
                    f"{role} perdeu o live view: {resp.get_data(as_text=True)[:200]}"
                )

    def test_viewer_sem_cameras_control_ainda_ve(self, app, client):
        """Papel com a chave de controle NEGADA continua enxergando."""
        with self._mocks():
            resp = client.post(
                f"/api/cameras/{CAM}/stream/start",
                headers=_auth(app, "viewer", perms=["cameras:read"]),
            )
            assert resp.status_code != 403, resp.get_data(as_text=True)[:200]

    def test_sem_token_nao_entra(self, app, client):
        resp = client.post(f"/api/cameras/{CAM}/stream/start")
        assert resp.status_code == 401
