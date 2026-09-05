"""
Integration: DOIS operadores, o MESMO alerta — Postgres REAL.

O que este arquivo prova (e nenhum teste com mock provava, porque a corrida
mora no `WHERE` do UPDATE e no que o Postgres faz com duas transações
concorrentes na mesma linha):

  1. O SEGUNDO veredito NÃO sobrescreve o primeiro — recebe `ConflictError`
     (409) dizendo quem julgou e quando; o valor final é o do PRIMEIRO,
     `verified_by` incluído.
  2. Sob concorrência de verdade (duas threads, duas conexões, largada
     simultânea por `Barrier`), EXATAMENTE UM grava. Não "os dois com sorte":
     um.
  3. Mudar de ideia sobre o PRÓPRIO veredito continua permitido — a docstring
     de `human_review` promete isso desde sempre e a guarda não pode ter
     quebrado a promessa.
  4. Alerta de outro tenant continua 404 (`False`), nunca 409: o conflito não
     pode virar um oráculo de existência cross-tenant (C-01).
  5. O rodízio (`get_human_queue(user_id=...)`) entrega o MESMO conjunto a
     todo mundo, mas com PRIMEIRO ITEM diferente por operador — é o que
     reduz a colisão na origem, antes de precisar do 409.

Mata (sem esta suíte, os dois sobrevivem a lint, tipo e testes unitários):
  · tirar `AND (verification_verdict IS NULL OR verified_by = %s)` do UPDATE
    → o caso 1 volta a devolver `True` e o veredito do primeiro some;
  · trocar a guarda por `AND verification_verdict IS NULL` puro → o caso 3
    passa a 409 e o operador não consegue mais corrigir o próprio veredito.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError
from app.domain.services.verification_service import VerificationService

BASE = datetime(2026, 9, 5, 9, 0, 0, tzinfo=timezone.utc)
CLASSE = "Sem Luvas"


def _insert_user(cur, tenant_id: str, nome: str) -> str:
    uid = str(uuid4())
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, f"conc-{uid[:8]}@test.dev", "x", nome, "operator", tenant_id),
    )
    return uid


def _insert_camera(cur, tenant_id: str, user_id: str) -> str:
    cid = str(uuid4())
    cur.execute(
        "INSERT INTO public.cameras (id, tenant_id, user_id, name, location, host, port) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (cid, tenant_id, user_id, "Canal 8", "Expedição", "192.168.1.1", 554),
    )
    return cid


def _insert_alert(cur, tenant_id: str, camera_id: str, created_at: datetime) -> str:
    aid = str(uuid4())
    cur.execute(
        "INSERT INTO public.alerts "
        "  (id, camera_id, tenant_id, module_code, violations, confidence, "
        "   evidence_key, created_at) "
        "VALUES (%s, %s, %s, 'epi', %s::jsonb, %s, %s, %s)",
        (
            aid, camera_id, tenant_id,
            json.dumps([{"class": CLASSE, "confidence": 0.55}]),
            0.55, f"evidence/{aid}.jpg", created_at,
        ),
    )
    return aid


def _veredito_final(pg_raw, alert_id: str) -> dict:
    with pg_raw.cursor() as cur:
        cur.execute(
            "SELECT verification_verdict, verification_status, verified_by "
            "FROM public.alerts WHERE id = %s",
            (alert_id,),
        )
        return dict(cur.fetchone())


@pytest.fixture
def cenario(pg_raw, pg_pool, tenant_id):
    """Um alerta sem veredito + dois operadores do MESMO tenant."""
    with pg_raw.cursor() as cur:
        maria = _insert_user(cur, tenant_id, "Maria Silva")
        joao = _insert_user(cur, tenant_id, "João Souza")
        cam = _insert_camera(cur, tenant_id, maria)
        alerta = _insert_alert(cur, tenant_id, cam, BASE)
    yield {"tenant": tenant_id, "maria": maria, "joao": joao, "cam": cam, "alerta": alerta}
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tenant_id,))


# ---------------------------------------------------------------------------
# 1. O segundo veredito não sobrescreve o primeiro
# ---------------------------------------------------------------------------

def test_segundo_veredito_recebe_conflito_e_nao_sobrescreve(pg_raw, cenario):
    """Maria confirma, João rejeita o MESMO alerta.

    ANTES da guarda: os dois recebiam `True`, e o banco terminava com
    `human_rejected`/`user:joao` — o trabalho da Maria evaporava em silêncio.
    """
    svc = VerificationService()

    assert svc.human_review(
        alert_id=cenario["alerta"], verdict="approve",
        user_id=cenario["maria"], tenant_id=cenario["tenant"],
    ) is True

    with pytest.raises(ConflictError) as excinfo:
        svc.human_review(
            alert_id=cenario["alerta"], verdict="reject",
            user_id=cenario["joao"], tenant_id=cenario["tenant"],
        )

    # A mensagem tem de servir pra tela: NOME de quem julgou (nunca o UUID) e
    # quando — é literalmente o que o operador lê no toast.
    assert excinfo.value.status_code == 409
    assert "Maria Silva" in excinfo.value.message
    assert cenario["maria"] not in excinfo.value.message
    assert "agora há pouco" in excinfo.value.message

    final = _veredito_final(pg_raw, cenario["alerta"])
    assert final["verification_verdict"] == "approve"
    assert final["verification_status"] == "human_approved"
    assert final["verified_by"] == f"user:{cenario['maria']}"


# ---------------------------------------------------------------------------
# 2. Concorrência real: duas threads, duas conexões, largada simultânea
# ---------------------------------------------------------------------------

def test_duas_threads_no_mesmo_alerta_apenas_uma_grava(pg_raw, cenario):
    """A corrida de verdade — `Barrier` solta as duas no mesmo instante.

    READ COMMITTED: o segundo UPDATE espera o primeiro commitar e reavalia o
    WHERE contra a linha NOVA; sem a guarda, o WHERE (só id+tenant) continua
    batendo e o segundo grava por cima.
    """
    svc = VerificationService()
    largada = threading.Barrier(2)
    resultado: dict[str, object] = {}

    def julgar(nome: str, user_id: str, verdict: str) -> None:
        largada.wait(timeout=10)
        try:
            resultado[nome] = svc.human_review(
                alert_id=cenario["alerta"], verdict=verdict,
                user_id=user_id, tenant_id=cenario["tenant"],
            )
        except ConflictError as exc:
            resultado[nome] = exc

    threads = [
        threading.Thread(target=julgar, args=("maria", cenario["maria"], "approve")),
        threading.Thread(target=julgar, args=("joao", cenario["joao"], "reject")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive(), "thread travou — deadlock no UPDATE"

    vencedores = [k for k, v in resultado.items() if v is True]
    perdedores = [k for k, v in resultado.items() if isinstance(v, ConflictError)]
    assert len(vencedores) == 1, f"esperado exatamente 1 vencedor, veio {resultado}"
    assert len(perdedores) == 1, f"esperado exatamente 1 conflito, veio {resultado}"

    # O banco tem o veredito de QUEM VENCEU — não uma mistura dos dois.
    final = _veredito_final(pg_raw, cenario["alerta"])
    vencedor = vencedores[0]
    assert final["verified_by"] == f"user:{cenario[vencedor]}"
    assert final["verification_verdict"] == ("approve" if vencedor == "maria" else "reject")


# ---------------------------------------------------------------------------
# 3. Mudar de ideia sobre o PRÓPRIO veredito continua valendo
# ---------------------------------------------------------------------------

def test_mesmo_operador_pode_mudar_de_ideia(pg_raw, cenario):
    svc = VerificationService()
    assert svc.human_review(
        alert_id=cenario["alerta"], verdict="approve",
        user_id=cenario["maria"], tenant_id=cenario["tenant"],
    ) is True
    assert svc.human_review(
        alert_id=cenario["alerta"], verdict="reject",
        user_id=cenario["maria"], tenant_id=cenario["tenant"],
    ) is True

    final = _veredito_final(pg_raw, cenario["alerta"])
    assert final["verification_verdict"] == "reject"
    assert final["verified_by"] == f"user:{cenario['maria']}"


# ---------------------------------------------------------------------------
# 4. Cross-tenant continua 404, nunca 409
# ---------------------------------------------------------------------------

def test_alerta_de_outro_tenant_e_404_nao_409(cenario):
    """O 409 não pode virar oráculo de existência (C-01): pra quem está fora
    do tenant, o alerta simplesmente não existe."""
    svc = VerificationService()
    svc.human_review(
        alert_id=cenario["alerta"], verdict="approve",
        user_id=cenario["maria"], tenant_id=cenario["tenant"],
    )
    assert svc.human_review(
        alert_id=cenario["alerta"], verdict="reject",
        user_id=cenario["joao"], tenant_id=str(uuid4()),
    ) is False


# ---------------------------------------------------------------------------
# 5. Rodízio: mesmo conjunto, primeiro item diferente por operador
# ---------------------------------------------------------------------------

def test_rodizio_da_fila_muda_o_primeiro_item_por_operador(pg_raw, pg_pool, tenant_id):
    """Colisão reduzida na ORIGEM: os operadores não abrem o mesmo alerta.

    9 alertas em câmeras distintas (uma rajada de 1 item cada → todos rank 1),
    confiança escalonada pra ordem canônica ser determinística. Cada trilha
    (`_TRILHAS = 3`) começa por uma posição diferente e mesmo assim vê os 9.
    """
    svc = VerificationService()
    with pg_raw.cursor() as cur:
        dono = _insert_user(cur, tenant_id, "Dono")
        for i in range(9):
            cam = _insert_camera(cur, tenant_id, dono)
            cur.execute(
                "INSERT INTO public.alerts "
                "  (id, camera_id, tenant_id, module_code, violations, confidence, "
                "   evidence_key, created_at) "
                "VALUES (%s, %s, %s, 'epi', %s::jsonb, %s, %s, %s)",
                (
                    str(uuid4()), cam, tenant_id,
                    json.dumps([{"class": CLASSE, "confidence": 0.50 + i * 0.01}]),
                    0.50 + i * 0.01, f"evidence/{uuid4()}.jpg",
                    BASE + timedelta(minutes=i),
                ),
            )
    try:
        # Um user_id sintético por trilha — o que importa é a trilha, não quem.
        por_trilha: dict[int, list[str]] = {}
        tentativas = 0
        while len(por_trilha) < VerificationService._TRILHAS and tentativas < 200:
            uid = str(uuid4())
            t = VerificationService._trilha(uid)
            tentativas += 1
            if t in por_trilha:
                continue
            itens = svc.get_human_queue(tenant_id=tenant_id, limit=50, user_id=uid)
            por_trilha[t] = [str(i["id"]) for i in itens]

        assert len(por_trilha) == VerificationService._TRILHAS, "trilhas não cobertas"

        # Mesmo CONJUNTO pra todo mundo — o rodízio não esconde ninguém.
        conjuntos = [frozenset(v) for v in por_trilha.values()]
        assert len(set(conjuntos)) == 1
        assert len(conjuntos[0]) == 9

        # Primeiros itens DIFERENTES — é isso que impede os três de abrirem o
        # mesmo alerta na segunda.
        primeiros = [v[0] for v in por_trilha.values()]
        assert len(set(primeiros)) == VerificationService._TRILHAS, primeiros

        # Estável entre chamadas: a tela reabastece por dedup de id e não
        # reordena; ordem que dança a cada poll de 15s quebraria isso.
        alguma = next(iter(por_trilha))
        uid_estavel = next(
            u for u in (str(uuid4()) for _ in range(200))
            if VerificationService._trilha(u) == alguma
        )
        assert [str(i["id"]) for i in svc.get_human_queue(
            tenant_id=tenant_id, limit=50, user_id=uid_estavel
        )] == por_trilha[alguma]
    finally:
        with pg_raw.cursor() as cur:
            cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tenant_id,))


# ---------------------------------------------------------------------------
# 6. Veredito da IA NÃO bloqueia o humano (achado do segundo cético)
# ---------------------------------------------------------------------------

def test_veredito_da_ia_nao_bloqueia_o_humano(pg_raw, cenario):
    """Corrigir a máquina é o produto — a guarda não pode proibir isso.

    `tasks/verification.py` grava o MESMO 'approve'/'reject' com
    `verified_by='claude-haiku'`. As telas de evento (Acoes/Eventos/
    EventoDetalhe/AlertsHistory) mostram "Não revisado" para esses alertas —
    `VereditoHumano.tsx` só aceita o prefixo 'user:' como prova de humanidade
    — e oferecem os botões de veredito. Com a guarda em
    `verification_verdict IS NULL` pura, o PRIMEIRO clique humano nesses
    botões virava 409 "A verificação automática já avaliou este alerta" e a
    revisão humana da decisão da IA ficava impossível pela rota.

    FALHA (ConflictError) sem `OR verified_by NOT LIKE 'user:%'` no WHERE.
    """
    with pg_raw.cursor() as cur:
        cur.execute(
            "UPDATE public.alerts SET verification_status = 'auto_approved', "
            "verification_verdict = 'approve', verified_at = NOW(), "
            "verified_by = 'claude-haiku' WHERE id = %s",
            (cenario["alerta"],),
        )

    assert VerificationService().human_review(
        alert_id=cenario["alerta"], verdict="reject",
        user_id=cenario["joao"], tenant_id=cenario["tenant"],
    ) is True

    final = _veredito_final(pg_raw, cenario["alerta"])
    assert final["verification_verdict"] == "reject"
    assert final["verification_status"] == "human_rejected"
    assert final["verified_by"] == f"user:{cenario['joao']}"


def test_veredito_humano_sobre_o_da_ia_volta_a_bloquear_terceiros(pg_raw, cenario):
    """A porta aberta pra IA não abre pra pessoa: depois que o humano corrige
    a máquina, o veredito dele é do MESMO tipo dos outros — o próximo operador
    leva 409. Sem este par, `NOT LIKE` viraria "qualquer um sobrescreve"."""
    svc = VerificationService()
    with pg_raw.cursor() as cur:
        cur.execute(
            "UPDATE public.alerts SET verification_verdict = 'approve', "
            "verified_at = NOW(), verified_by = 'claude-haiku' WHERE id = %s",
            (cenario["alerta"],),
        )

    assert svc.human_review(
        alert_id=cenario["alerta"], verdict="reject",
        user_id=cenario["joao"], tenant_id=cenario["tenant"],
    ) is True

    with pytest.raises(ConflictError) as excinfo:
        svc.human_review(
            alert_id=cenario["alerta"], verdict="approve",
            user_id=cenario["maria"], tenant_id=cenario["tenant"],
        )
    assert "João Souza" in excinfo.value.message
    assert _veredito_final(pg_raw, cenario["alerta"])["verified_by"] == (
        f"user:{cenario['joao']}"
    )
