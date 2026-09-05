"""O número que o usuário CLICA é o número que ele ENCONTRA (issues #674/#676).

Postgres REAL + fronteira HTTP: o cartão sai de `GET /api/v1/events/profile`
(o que o Dashboard lê) e a lista sai de `GET /api/alerts` (o destino do
clique). Os dois têm de devolver o MESMO total para a MESMA janela — mesmo
eixo de tempo, mesmo escopo de módulo. Mock nenhum prova isto: o defeito era
justamente cada rota montar o seu próprio WHERE.

CENÁRIO (o do DEV, encolhido): carga em LOTE. Seis alertas GRAVADOS no mesmo
segundo (03:00 de 01/09, quando o processo de ingestão rodou) mas CAPTURADOS
ao longo do turno de 25/08 — mais um alerta de câmera FORA do escopo do EPI.

FALHA ANTES / PASSA DEPOIS (rodado no worktree, ver corpo do PR):

  · `list_with_filters` filtrava `start_date`/`end_date` em `a.created_at`:
    a janela de captura do turno devolvia 0 linhas enquanto o cartão dizia 6
    → `test_lista_conta_o_mesmo_que_o_cartao_na_janela_de_captura` VERMELHO.
  · `/api/alerts` não aceitava `module_code`: a câmera da Guarita entrava na
    lista e não no cartão → `test_escopo_de_modulo_recorta_a_lista_como_o_cartao`
    VERMELHO.
  · A CTE de `total_situacoes` particionava por `created_at`: as 6 capturas
    distintas, gravadas no MESMO segundo, viravam UMA rajada
    → `test_rajada_conta_capturas_distintas_gravadas_no_mesmo_segundo` VERMELHO
    (dava 1, o esperado é 6).

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

# Captura: o turno real da fábrica, 25/08, uma por hora das 10h às 15h.
CAPTURA_INICIO = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
# Gravação: a carga em lote rodou de madrugada, dias depois, num segundo só.
GRAVACAO_LOTE = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)
CAPTURAS = [CAPTURA_INICIO + timedelta(hours=i) for i in range(6)]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _jwt(app, tenant_id: str) -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": str(tenant_id), "role": "admin"},
        )


def _insere_alerta(cur, tenant_id, camera_id, capturado_em, gravado_em, classe):
    cur.execute(
        "INSERT INTO public.alerts "
        "  (id, camera_id, tenant_id, module_code, timestamp, violations, "
        "   confidence, evidence_key, created_at) "
        "VALUES (%s, %s, %s, 'epi', %s, %s::jsonb, 0.9, %s, %s)",
        (
            str(uuid4()), camera_id, tenant_id, capturado_em,
            json.dumps([{"class": classe, "confidence": 0.9}]),
            f"evidence/{uuid4()}.jpg", gravado_em,
        ),
    )


@pytest.fixture
def cenario(pg_raw, tenant_id):
    """Duas câmeras; o dono declarou SÓ a primeira como EPI (migration 134).

    Câmera EPI: 6 alertas do turno, todos gravados no mesmo segundo do lote.
    Guarita: 1 alerta, capturado DENTRO da mesma janela — é a linha que a
    lista mostrava e o cartão não contava (82 linhas no DEV).
    """
    user = str(uuid4())
    cam_epi, cam_fora = str(uuid4()), str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, 'x', 'IntTest Eixo', 'admin', %s)",
            (user, f"eixo-{user[:8]}@test.dev", tenant_id),
        )
        for cid, nome in ((cam_epi, "Corredor Expedição"), (cam_fora, "Guarita")):
            cur.execute(
                "INSERT INTO public.cameras "
                "(id, tenant_id, user_id, name, host, module_code, active_module, is_active) "
                "VALUES (%s, %s, %s, %s, '10.0.0.1', 'epi', 'epi', true)",
                (cid, tenant_id, user, nome),
            )
        # O vínculo declarado — sem ele o escopo de módulo é inerte por design
        # (tabela vazia = nada muda, ver test_escopo_modulo_camera.py).
        cur.execute(
            "INSERT INTO public.camera_modules (tenant_id, camera_id, module_code, enabled) "
            "VALUES (%s, %s, 'epi', true)",
            (tenant_id, cam_epi),
        )
        for t in CAPTURAS:
            _insere_alerta(cur, tenant_id, cam_epi, t, GRAVACAO_LOTE, "Sem capacete")
        _insere_alerta(
            cur, tenant_id, cam_fora, CAPTURAS[0], GRAVACAO_LOTE, "Sem capacete"
        )

    yield {"cam_epi": cam_epi, "cam_fora": cam_fora}

    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.camera_modules WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tenant_id,))


@pytest.fixture
def janela() -> dict[str, str]:
    """A janela do turno, em hora de CAPTURA — é o que a barra do Dashboard
    manda no deep-link (`start_date`/`end_date` = bucket da barra)."""
    return {"de": _iso(CAPTURAS[0]), "ate": _iso(CAPTURAS[-1] + timedelta(minutes=1))}


def _cartao(client, token, janela) -> int:
    """O número do CARTÃO: `situacao.total` de `/v1/events/profile` (eixo de
    captura + escopo de módulo por dentro) — o que o Dashboard imprime."""
    r = client.get(
        f"/api/v1/events/profile?from={janela['de']}&to={janela['ate']}&module_code=epi",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]["situacao"]["total"]


def _lista(client, token, janela, extra: str = "") -> dict:
    """O número da LISTA: `GET /api/alerts` com o MESMO recorte do link."""
    r = client.get(
        f"/api/alerts?start_date={janela['de']}&end_date={janela['ate']}"
        f"&kind=&module_code=epi&per_page=100{extra}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


def test_lista_conta_o_mesmo_que_o_cartao_na_janela_de_captura(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """O critério inteiro numa linha: cartão == lista, mesmo eixo, mesmo escopo."""
    token = _jwt(app, tenant_id)

    cartao = _cartao(client, token, janela)
    lista = _lista(client, token, janela)

    assert cartao == 6, "fixture: 6 capturas no turno da câmera de EPI"
    assert lista["total"] == cartao, (
        f"cartão diz {cartao} e a lista devolve {lista['total']} — "
        "o eixo do tempo ou o escopo de módulo mudou no caminho do clique"
    )
    assert len(lista["alerts"]) == cartao


def test_escopo_de_modulo_recorta_a_lista_como_o_cartao(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """A Guarita não é EPI: aparece SEM `module_code`, some COM ele.

    Nada é apagado — a linha continua no banco e na lista sem escopo. O que
    o escopo faz é a lista parar de contar o que o cartão nunca contou.
    """
    token = _jwt(app, tenant_id)

    com_escopo = _lista(client, token, janela)
    r = client.get(
        f"/api/alerts?start_date={janela['de']}&end_date={janela['ate']}&kind=&per_page=100",
        headers={"Authorization": f"Bearer {token}"},
    )
    sem_escopo = r.get_json()["data"]

    assert sem_escopo["total"] == 7
    assert com_escopo["total"] == 6
    assert cenario["cam_fora"] not in {a["camera_id"] for a in com_escopo["alerts"]}


def test_time_field_created_continua_devolvendo_o_eixo_da_gravacao(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """A saída de emergência existe e é a que o nome diz.

    `?time_field=created` volta ao eixo da ingestão: a janela do TURNO (25/08)
    não alcança nenhuma das linhas, porque todas foram GRAVADAS em 01/09.
    """
    token = _jwt(app, tenant_id)
    legado = _lista(client, token, janela, extra="&time_field=created")
    assert legado["total"] == 0

    gravacao = {
        "de": _iso(GRAVACAO_LOTE - timedelta(minutes=1)),
        "ate": _iso(GRAVACAO_LOTE + timedelta(minutes=1)),
    }
    assert _lista(client, token, gravacao, extra="&time_field=created")["total"] == 6


def test_rajada_conta_capturas_distintas_gravadas_no_mesmo_segundo(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """Issue #674: 6 capturas de 1 em 1 hora não são UMA rajada.

    Isolado de propósito na janela da GRAVAÇÃO (`time_field=created`): as
    MESMAS 6 linhas que o código anterior já devolvia aqui — o recorte não
    muda, só a contagem de situações. Pelo eixo da gravação elas nasceram no
    mesmo segundo (gap 0s, abaixo de qualquer janela de dedup) e
    `total_situacoes` dizia 1, escondendo 5 acontecimentos atrás de
    "+5 repetições". O eixo da rajada é a CAPTURA, sempre.
    """
    token = _jwt(app, tenant_id)
    gravacao = {
        "de": _iso(GRAVACAO_LOTE - timedelta(minutes=1)),
        "ate": _iso(GRAVACAO_LOTE + timedelta(minutes=1)),
    }
    # `camera_id` em vez de `module_code`: isola a rajada do escopo de módulo
    # — o recorte é o MESMO que o código anterior já devolvia aqui.
    so_epi = f"&time_field=created&camera_id={cenario['cam_epi']}"
    lista = _lista(client, token, gravacao, extra=so_epi)
    assert lista["total"] == 6, "o RECORTE é o mesmo de antes — 6 linhas"
    assert lista["total_situacoes"] == 6, (
        "capturas a 1 hora de distância são 6 situações; agrupá-las pela "
        "hora da GRAVAÇÃO funde acontecimentos distintos do chão de fábrica"
    )

    # E na janela de CAPTURA (o caminho do clique) o par bate igual.
    assert _lista(client, token, janela)["total_situacoes"] == 6


def _cartao_resumo(client, token, janela, extra: str = "&time_field=captured") -> dict:
    """O outro cartão: `/v1/events/summary` — a fonte de "Violações por classe"
    e "Câmeras com mais eventos", os dois painéis com deep-link do Dashboard.

    `time_field=captured` é o que o cliente manda em TODO pedido do
    `eventsService` (`buildQuery`); a rota mantém o default histórico
    'created' porque tem outros leitores (issue #702).
    """
    r = client.get(
        f"/api/v1/events/summary?from={janela['de']}&to={janela['ate']}"
        f"&module_code=epi{extra}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


def test_resumo_conta_no_mesmo_eixo_que_a_lista_que_ele_abre(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """ACHADO DO CÉTICO (#732): `/v1/events/summary` ignorava `time_field`.

    O parâmetro existia na rota (`_time_column`) e só chegava ao
    `/events/timeline`: o resumo contava SEMPRE por `created_at`, enquanto
    `/api/alerts` passou a recortar pela captura. Os painéis "Violações por
    classe" e "Câmeras com mais eventos" diriam um número e o clique abriria a
    lista com outro — o defeito que a issue #676 existe para matar, na tela
    irmã.

    FALHA ANTES: com `time_field=captured` no pedido, esta janela (o turno de
    25/08) devolvia `total=0` e `by_camera=[]` mesmo assim, porque as 6 linhas
    foram GRAVADAS em 01/09 e o parâmetro era ignorado.
    """
    token = _jwt(app, tenant_id)

    resumo = _cartao_resumo(client, token, janela)
    lista = _lista(client, token, janela)

    assert resumo["total"] == 6, "o resumo conta a janela pela CAPTURA, como a lista"
    assert lista["total"] == resumo["total"], (
        f"cartão do resumo diz {resumo['total']} e a lista devolve {lista['total']} "
        "— o eixo mudou entre o painel e o destino do clique"
    )
    por_camera = {c["camera_id"]: c["count"] for c in resumo["by_camera"]}
    assert por_camera.get(cenario["cam_epi"]) == 6
    assert cenario["cam_fora"] not in por_camera, "escopo de módulo, igual à lista"


def test_resumo_aceita_a_saida_de_emergencia_do_eixo_da_gravacao(
    app, client, pg_pool, pg_raw, tenant_id, cenario, janela
):
    """`time_field=created` (e a AUSÊNCIA, que é o default histórico da rota)
    continuam no eixo da ingestão — nenhum consumidor antigo muda por baixo."""
    token = _jwt(app, tenant_id)
    assert _cartao_resumo(client, token, janela, extra="&time_field=created")["total"] == 0
    assert _cartao_resumo(client, token, janela, extra="")["total"] == 0

    gravacao = {
        "de": _iso(GRAVACAO_LOTE - timedelta(minutes=1)),
        "ate": _iso(GRAVACAO_LOTE + timedelta(minutes=1)),
    }
    assert _cartao_resumo(client, token, gravacao, extra="&time_field=created")["total"] == 6
