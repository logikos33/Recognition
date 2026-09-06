"""
Segurança/produto — o papel que o cliente vai receber FECHA o ciclo dele.

Por que este arquivo existe (issues #774 e #775)

Na segunda-feira três pessoas reais recebem uma conta. O que se sabia até
agora sobre papéis vinha de duas medições isoladas ("operator abre a fila",
"trainer anota") e de uma matriz de permissões — nenhuma das duas responde a
pergunta que importa: **um papel sozinho consegue ir do começo ao fim do
trabalho da pessoa?** A matriz pode estar inteira e o percurso ainda quebrar
no terceiro passo, que é exatamente o que acontecia com `trainer`: anotava,
classificava, e batia num 403 na hora de verificar a detecção — o papel cujo
nome diz "quem treina" era o único que não abria metade do próprio ciclo.

O teste percorre o trabalho INTEIRO, passo a passo, CRUZANDO A FRONTEIRA
HTTP (client.get/post/patch/put), e em cada passo cobra duas coisas:

  · a rota não devolveu 403 — o papel passou pelo gate;
  · o colaborador da rota FOI CHAMADO — passou do gate e de fato executou.
    Sem isto, uma rota que devolvesse 200 sem fazer nada passaria por
    "ciclo fechado".

E cobra o contrário também: um papel que não deveria escrever (`viewer`)
é barrado em cada passo de escrita — senão o teste estaria medindo "todo
mundo pode tudo", que passa igual.

FALHA-ANTES: o percurso do ANOTADOR morre no passo "verificar a detecção"
(403), porque `verification:write` não incluía `trainer` no registry.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"
SCHEMA = "tenant_rvb"
ALERTA = str(uuid4())
FRAME = str(uuid4())

# Papel decidido para cada persona do cliente (ver PR / issue #774).
PAPEL_TST = "operator"
PAPEL_ANOTADOR = "trainer"


def _auth(app, role: str) -> dict[str, str]:
    """Token do jeito que o /login emite para uma conta comum do tenant.

    Sem claim `perms`: é assim que o token sai quando o cálculo de permissões
    efetivas falha (best-effort em auth/routes.py) e é o caminho que cai no
    registry por papel — justamente o que este arquivo mede.
    """
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": SCHEMA,
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def colaboradores():
    """Mocka só o que cada rota do percurso chama — nada de banco."""
    alerts_repo = MagicMock()
    alerts_repo.list_with_filters.return_value = {
        "items": [], "total": 0, "total_situacoes": 0,
    }
    alerts_repo.corrigir_bboxes.return_value = {
        "violations": [], "violations_historico": [],
    }

    verif_svc = MagicMock()
    verif_svc.get_human_queue.return_value = []
    verif_svc.get_queue_count.return_value = 0
    verif_svc.human_review.return_value = 1

    anotacao_svc = MagicMock()
    anotacao_svc.save_annotations.return_value = 2

    classes_svc = MagicMock()
    classes_svc.list_classes.return_value = []

    gabarito_repo = MagicMock()
    gabarito_repo.list_fila.return_value = []
    gabarito_repo.is_holdout_frame.return_value = True
    gabarito_repo.upsert_verdicts.return_value = 1

    modulos = MagicMock()
    modulos.return_value.get_classes.return_value = []

    p = "app.api.v1."
    with ExitStack() as st:
        st.enter_context(patch(p + "alerts.routes._get_repo", return_value=alerts_repo))
        st.enter_context(patch(p + "alerts.routes._nome_usuario_atual", return_value="Fulana"))
        st.enter_context(patch(p + "verification.routes._svc", verif_svc))
        st.enter_context(patch(
            p + "training.annotation_handlers.get_annotation_service",
            return_value=anotacao_svc,
        ))
        st.enter_context(patch(
            p + "training.annotation_handlers.get_tenant_class_service",
            return_value=classes_svc,
        ))
        st.enter_context(patch(
            p + "training.gabarito_handlers._get_repo", return_value=gabarito_repo,
        ))
        st.enter_context(patch(p + "training.gabarito_handlers.ModuleService", modulos))
        yield {
            "alerts_repo": alerts_repo,
            "verif_svc": verif_svc,
            "anotacao_svc": anotacao_svc,
            "classes_svc": classes_svc,
            "gabarito_repo": gabarito_repo,
        }


# (passo, método, url, corpo, (apelido do mock, método esperado), escreve?)
PERCURSO_TST = [
    ("ver o evento", "get", "/api/alerts", None,
     ("alerts_repo", "list_with_filters"), False),
    ("tratar (corrigir a violação)", "patch", f"/api/alerts/{ALERTA}/violations",
     {"correcoes": [{"index": 0, "bbox": [1, 2, 3, 4]}]},
     ("alerts_repo", "corrigir_bboxes"), True),
    ("abrir a fila de verificação", "get", "/api/verification/queue", None,
     ("verif_svc", "get_human_queue"), False),
    ("verificar a detecção", "post", f"/api/verification/{ALERTA}/review",
     {"verdict": "approve"}, ("verif_svc", "human_review"), True),
]

PERCURSO_ANOTADOR = [
    ("abrir o estúdio (classes do tenant)", "get", "/api/classes", None,
     ("classes_svc", "list_classes"), False),
    ("anotar o frame", "post", f"/api/training/frames/{FRAME}/annotations",
     {"annotations": []}, ("anotacao_svc", "save_annotations"), True),
    ("abrir a triagem (F/V/X)", "get", "/api/training/gabarito/fila", None,
     ("gabarito_repo", "list_fila"), False),
    ("classificar o quadro (F/V/X)", "put", f"/api/training/gabarito/frames/{FRAME}",
     {"verdicts": {"5": "sim"}}, ("gabarito_repo", "upsert_verdicts"), True),
    ("abrir a fila de verificação", "get", "/api/verification/queue", None,
     ("verif_svc", "get_human_queue"), False),
    # ← o passo que faltava: sem ele o anotador não fecha o próprio ciclo.
    ("verificar a detecção", "post", f"/api/verification/{ALERTA}/review",
     {"verdict": "approve"}, ("verif_svc", "human_review"), True),
]

PERCURSOS = [
    ("TST", PAPEL_TST, PERCURSO_TST),
    ("anotador", PAPEL_ANOTADOR, PERCURSO_ANOTADOR),
]


def _chamar(client, metodo, url, corpo, headers):
    fn = getattr(client, metodo)
    return fn(url, json=corpo, headers=headers) if corpo is not None else fn(url, headers=headers)


class TestPapelFechaOCicloDaPessoa:

    @pytest.mark.parametrize(
        "persona,papel,percurso", PERCURSOS, ids=[p[0] for p in PERCURSOS],
    )
    def test_percurso_inteiro_sem_403(
        self, app, client, colaboradores, persona, papel, percurso
    ):
        headers = _auth(app, papel)
        for passo, metodo, url, corpo, (apelido, alvo), _escreve in percurso:
            efeito = getattr(colaboradores[apelido], alvo)
            efeito.reset_mock()
            resp = _chamar(client, metodo, url, corpo, headers)
            assert resp.status_code != 403, (
                f"{persona} ({papel}) travou em '{passo}': "
                f"{metodo.upper()} {url} → {resp.status_code} "
                f"{resp.get_data(as_text=True)[:200]}"
            )
            assert efeito.called, (
                f"{persona} ({papel}) passou do gate em '{passo}' mas "
                f"{apelido}.{alvo} não executou — 200 vazio não é ciclo fechado"
            )

    @pytest.mark.parametrize(
        "persona,papel,percurso", PERCURSOS, ids=[p[0] for p in PERCURSOS],
    )
    def test_viewer_e_barrado_em_todo_passo_que_escreve(
        self, app, client, colaboradores, persona, papel, percurso
    ):
        """Contraprova: se 'ninguém é barrado', o teste acima não mede nada."""
        headers = _auth(app, "viewer")
        escritas = [p for p in percurso if p[5]]
        assert escritas, f"percurso do {persona} sem nenhum passo de escrita"
        for passo, metodo, url, corpo, (apelido, alvo), _ in escritas:
            efeito = getattr(colaboradores[apelido], alvo)
            efeito.reset_mock()
            resp = _chamar(client, metodo, url, corpo, headers)
            assert resp.status_code == 403, (
                f"viewer escreveu em '{passo}': {metodo.upper()} {url} "
                f"→ {resp.status_code}"
            )
            efeito.assert_not_called()


class TestOsDoisPapeisEstaoNoRegistry:
    """Se alguém renomear/remover um papel, este arquivo tem de cair junto."""

    def test_papeis_escolhidos_existem(self):
        from app.core.permissions import ROLE_ORDER

        assert PAPEL_TST in ROLE_ORDER
        assert PAPEL_ANOTADOR in ROLE_ORDER

    def test_nenhum_dos_dois_ganhou_permissao_de_plataforma(self):
        """A decisão do papel não pode ter virado escada de privilégio."""
        from app.core.permissions import permissions_for_role

        for papel in (PAPEL_TST, PAPEL_ANOTADOR):
            perms = set(permissions_for_role(papel))
            vazadas = {p for p in perms if p.startswith("admin:")} | {
                p for p in perms
                if p in ("training:approve", "workers:manage", "plans:manage",
                         "announcements:manage", "audit:read", "modules:write")
            }
            assert vazadas == set(), f"{papel} recebeu permissão de plataforma: {vazadas}"
