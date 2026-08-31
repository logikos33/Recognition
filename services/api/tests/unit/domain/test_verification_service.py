"""
Tests: VerificationService — submit_for_verification, get_human_queue,
human_review, get_queue_count.

All DB calls go through a mocked DatabasePool; verify_alert task is stubbed
via patch.dict(sys.modules) to avoid needing celery installed.
"""
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.domain.services.verification_service import VerificationService

_POOL_PATH = "app.domain.services.verification_service.DatabasePool"
_VERIFICATION_MODULE = "app.infrastructure.queue.tasks.verification"


def _make_service() -> VerificationService:
    return VerificationService()


def _pool_with_cursor(mock_cursor):
    """Build a pool mock whose get_connection() yields a conn with mock_cursor."""
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# submit_for_verification
# ---------------------------------------------------------------------------

class TestSubmitForVerification:

    def _call(self, mock_task, **kwargs):
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id=kwargs.get("alert_id", "alert-1"),
                camera_id=kwargs.get("camera_id", "cam-1"),
                class_name=kwargs.get("class_name", "no_helmet"),
                confidence=kwargs.get("confidence", 0.7),
                tenant_id=kwargs.get("tenant_id", "tenant-1"),
                module_code=kwargs.get("module_code", "epi"),
            )
        return mock_task

    def test_calls_verify_alert_delay(self):
        mock_task = MagicMock()
        self._call(mock_task)
        mock_task.delay.assert_called_once()

    def test_passes_correct_kwargs(self):
        mock_task = MagicMock()
        self._call(mock_task, alert_id="a-1", camera_id="c-1",
                   class_name="no_vest", confidence=0.65, tenant_id="tenant-9",
                   module_code="epi")
        kw = mock_task.delay.call_args[1]
        assert kw["alert_id"] == "a-1"
        assert kw["camera_id"] == "c-1"
        assert kw["class_name"] == "no_vest"
        assert kw["confidence"] == 0.65
        assert kw["tenant_id"] == "tenant-9"
        assert kw["module_code"] == "epi"

    def test_exception_in_delay_is_swallowed(self):
        mock_task = MagicMock()
        mock_task.delay.side_effect = Exception("broker unreachable")
        # Should not raise — fire-and-forget with error logging
        self._call(mock_task)

    def test_default_module_code_is_epi(self):
        mock_task = MagicMock()
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id="a", camera_id="c", class_name="no_helmet", confidence=0.5,
                tenant_id="tenant-1",
            )
        kw = mock_task.delay.call_args[1]
        assert kw["module_code"] == "epi"

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório (C-01) — `verify_alert` grava o
        veredito de volta no alerta e o UPDATE precisa do tenant no WHERE."""
        with pytest.raises(TypeError):
            _make_service().submit_for_verification(  # type: ignore[call-arg]
                alert_id="a", camera_id="c", class_name="no_helmet", confidence=0.5,
            )


# ---------------------------------------------------------------------------
# get_human_queue
# ---------------------------------------------------------------------------

class TestGetHumanQueue:

    def test_pool_none_returns_empty(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert result == []

    def test_returns_list_of_dicts(self):
        mock_cursor = MagicMock()
        # 2 chamadas de verdade agora: (1) AlertRepository.presence_class_names
        # (via `_execute` -> `fetchall`), (2) a query principal de dedup. A
        # MESMA `mock_cursor` serve as duas — `side_effect` consome uma por vez.
        mock_cursor.fetchall.side_effect = [
            [],  # presence_class_names: sem classes de presença cadastradas
            [{"id": "a1", "camera_name": "Cam A", "verification_status": "needs_human"}],
        ]
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert len(result) == 1
        assert result[0]["id"] == "a1"

    def test_empty_fetchall_returns_empty_list(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert result == []

    def test_camera_id_filter_adds_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1", camera_id="cam-42")
        call_args = mock_cursor.execute.call_args
        query, params = call_args[0]
        assert "camera_id" in query
        assert "cam-42" in params

    def test_db_exception_sobe_em_vez_de_virar_fila_vazia(self):
        """`[]` é "fila vazia", e a tela escreve exatamente isso.

        Com a exceção engolida aqui, a rota respondia 200 e o `catch` da
        página nunca disparava: o operador lia "Nenhum alerta aguardando
        revisão humana", ia embora, e os alertas de baixa confiança ficavam
        invisíveis — com o badge repetindo 0 a cada 15s.

        O caminho honesto já existia nas duas pontas (rota com
        `except -> 500`, página com `catch`); só este `return []` impedia que
        fossem alcançados.
        """
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB down")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            with pytest.raises(Exception, match="DB down"):
                _make_service().get_human_queue(tenant_id="tenant-1")

    def test_limit_passed_as_last_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1", limit=10)
        _, params = mock_cursor.execute.call_args[0]
        assert 10 in params

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().get_human_queue()  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        query, params = mock_cursor.execute.call_args[0]
        assert "a.tenant_id = %s" in query
        assert "tenant-1" in params

    def test_camera_join_usa_public_cameras_qualificado(self):
        """Duas regressões na mesma asserção:

        1. Join stale em `ip_cameras` (renomeada na migration 013) quebrava a
           query inteira contra o schema real — ver anti-padrões no CLAUDE.md.
        2. `cameras` sem qualificar schema (achado do cético, rodada 2): o
           pool é COMPARTILHADO entre `public` e os schemas por tenant
           (`rvb.cameras`, `dev.cameras`... — ADR-0004), cada um com sua
           própria tabela `cameras` SEM `tenant_id`. Sem `public.` explícito,
           um `search_path` de outra query na mesma conexão bastaria pra
           casar com a tabela errada.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        query, _ = mock_cursor.execute.call_args[0]
        assert "JOIN public.cameras " in query
        assert "ip_cameras" not in query


# ---------------------------------------------------------------------------
# Teste de mutação: critério fantasma `needs_human` + conformidade + rajada
#
# get_human_queue e get_queue_count filtravam por `verification_status =
# 'needs_human'`, mas essa coluna é escrita SÓ pela task Celery `verify_alert`
# (triagem por IA), que nunca conclui no worker atual. Medido no DEV, tenant
# RVB: 423 alerts, 416 `pending` (verdict NULL), 6 `human_rejected`,
# 1 `human_approved`, 0 `needs_human`. A fila filtrava por um conjunto vazio
# por construção.
#
# Rodada 2 foi além do WHERE: a fila também precisa excluir CONFORMIDADE
# (302/416 = 72,6% no DEV) e lidar com rajada de câmera+classe (347/416
# repetem em <10s).
#
# Rodada 3 (o cético reprovou a rodada 2): dedup como FILTRO fazia "N
# RESTANTES" cair pra 0 ao julgar só os 15 representantes, enquanto 99
# irmãos de rajada continuavam pendentes no banco — "Fila zerada" mentindo de
# novo, a MESMA classe de bug que abriu esta rodada. Decisão (orquestrador):
# `total`/`get_queue_count` conta TODO O TRABALHO REAL (114 no DEV, sem
# dedup); `get_human_queue` só REORDENA — o representante mais incerto de
# cada rajada (`rank_na_rajada = 1`) aparece antes de qualquer irmão, mas
# NINGUÉM é filtrado. Também corrigido: `presence_class_names` sem
# `module_code` vazava classes de outro módulo (medido: 24 nomes sem módulo
# vs. 13 com 'epi') — agora escopado.
#
# `_FakeDbCursor` interpreta de verdade a query que o código EMITIU — não um
# retorno fixo de MagicMock, e não mais uma reimplementação hardcoded do
# "resultado correto" desconectada do texto (foi assim que as mutações M3 —
# reverter `ORDER BY` pra `created_at DESC` — e M4 — neutralizar o rank de
# rajada — passaram no fake da rodada 2: 102 passed, 0 failed). Este:
#   · lê `tenant_id`/`camera_id`/`presence_names`/`window`/`limit` NA POSIÇÃO
#     em que o código realmente os coloca — não hardcoda o resultado;
#   · decide o critério de veredito/conformidade LENDO O TEXTO da query;
#   · decide a ORDENAÇÃO lendo qual `ORDER BY` está de fato no texto — o
#     oráculo de "rank de rajada" só roda quando o `ORDER BY` real está
#     presente; um `ORDER BY` diferente (mutado) produz uma ordem DIFERENTE
#     e OBSERVÁVEL, não a mesma resposta disfarçada.
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 8, 24, 23, 58, 0)


def _alerta(
    id_: str, *, tenant_id: str, camera_id: str = "cam-1", classe: str | None = "Sem Luvas",
    confidence: float | None = 0.5, verdict: str | None = None, status: str = "pending",
    offset_s: float = 0,
) -> dict:
    return {
        "id": id_,
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "verification_verdict": verdict,
        "verification_status": status,
        "violations": [{"class": classe}] if classe else [],
        "confidence": confidence,
        "created_at": _T0 + timedelta(seconds=offset_s),
    }


def _incerteza(a: dict) -> float:
    conf = a.get("confidence")
    return abs((conf if conf is not None else 1.0) - 0.5)


def _classe_de(a: dict) -> str:
    viols = a.get("violations") or []
    return viols[0].get("class", "") if viols else ""


def _ordem_real_por_rajada(candidatos: list[dict], window_seconds: float) -> list[dict]:
    """Oráculo: reproduz a ordenação de 2 camadas real (rank_na_rajada, depois
    incerteza) — sessioniza por (câmera, classe) com gap > window_seconds
    (gaps-and-islands), rank 1 = o mais incerto de cada sessão."""
    grupos: dict[tuple, list[dict]] = {}
    for a in candidatos:
        grupos.setdefault((a.get("camera_id"), _classe_de(a)), []).append(a)

    ranqueados: list[tuple[int, dict]] = []
    for grupo in grupos.values():
        por_tempo = sorted(grupo, key=lambda a: a["created_at"])
        sessoes: list[list[dict]] = []
        anterior = None
        for a in por_tempo:
            nova_sessao = anterior is None or (a["created_at"] - anterior).total_seconds() > window_seconds
            if nova_sessao:
                sessoes.append([])
            sessoes[-1].append(a)
            anterior = a["created_at"]
        for sessao in sessoes:
            for rank, a in enumerate(sorted(sessao, key=lambda a: (_incerteza(a), a["created_at"])), start=1):
                ranqueados.append((rank, a))

    ranqueados.sort(key=lambda t: (t[0], _incerteza(t[1])))
    return [a for _, a in ranqueados]


_ORDER_BY_REAL = "ORDER BY r.rank_na_rajada ASC, ABS(COALESCE(a.confidence, 1.0) - 0.5) ASC"


class _FakeDbCursor:
    """Interpreta de verdade as DUAS queries que `get_human_queue` e
    `get_queue_count` emitem: (1) `AlertRepository.presence_class_names`
    (delegada de verdade — não mockada — para exercitar o código real de
    conformidade, e ESCOPADA por `module_code`) e (2) a CTE de candidatos
    (conformidade + rank de rajada). Um WHERE/ORDER BY fora do esperado
    FALHA alto — não filtra/ordena errado em silêncio.
    """

    def __init__(self, alerts: list[dict], presence_names: tuple[str, ...] = ()):
        self._alerts = alerts
        self._presence_names = presence_names
        self.calls: list[tuple[str, tuple]] = []
        self._result: list[dict] = []

    @property
    def last_query(self) -> str:
        return self.calls[-1][0] if self.calls else ""

    @property
    def last_params(self) -> tuple:
        return self.calls[-1][1] if self.calls else ()

    def execute(self, query: str, params=()) -> None:
        params = tuple(params)
        self.calls.append((query, params))

        if "module_classes" in query and "yolo_classes" in query:
            # AlertRepository.presence_class_names — devolve o fixture de
            # nomes de presença configurado no cursor (shape real: {"n": ...}).
            self._result = [{"n": n} for n in self._presence_names]
            return

        if "candidatos AS" not in query:
            raise AssertionError(f"WHERE inesperado no fixture do teste: {query!r}")

        # 1) Critério de veredito — LIDO DO TEXTO, não assumido.
        if "a.verification_verdict IS NULL" in query:
            veredito_ok = lambda a: a.get("verification_verdict") is None  # noqa: E731
        elif "verification_status = 'needs_human'" in query:
            veredito_ok = lambda a: a.get("verification_status") == "needs_human"  # noqa: E731
        else:
            raise AssertionError(f"critério de veredito não reconhecido: {query!r}")

        # 2) Params NA POSIÇÃO em que o código os monta — tenant primeiro,
        #    depois camera_id SE o texto tiver o filtro, depois presença,
        #    depois (só na lista) janela de rajada e limit.
        idx = 0
        tenant_id = params[idx]; idx += 1
        camera_filtro = "AND a.camera_id = %s" in query
        camera_id = None
        if camera_filtro:
            camera_id = params[idx]; idx += 1
        exclui_conformidade = "jsonb_array_length(a.violations)" in query
        presence_lower: set[str] = set()
        if exclui_conformidade:
            presence_lower = {str(p).lower() for p in params[idx]}
            idx += 1
        is_list = "cam.name AS camera_name" in query
        is_count = "COUNT(*) AS total" in query
        if not is_list and not is_count:
            raise AssertionError(f"nem lista nem contagem reconhecidas: {query!r}")
        window = limit = None
        if is_list:
            window = params[idx]; idx += 1
            limit = params[idx]; idx += 1

        def _e_conformidade(a: dict) -> bool:
            viols = a.get("violations") or []
            if not viols:
                return False
            return all(str(v.get("class", "")).lower() in presence_lower for v in viols)

        # 3) Filtro — tenant, câmera (se pedido), veredito, conformidade.
        #    NENHUM alerta de outro tenant passa daqui, mesmo que o dataset
        #    do fixture misture tenants (prova contra vazamento cross-tenant).
        #    NENHUM dedup de rajada aqui — rajada NUNCA filtra (rodada 3).
        candidatos = [
            a for a in self._alerts
            if a.get("tenant_id") == tenant_id
            and (camera_id is None or a.get("camera_id") == camera_id)
            and veredito_ok(a)
            and (not exclui_conformidade or not _e_conformidade(a))
        ]

        # 4) Ordenação — só na lista, e só lendo o ORDER BY de verdade do
        #    texto. Um ORDER BY diferente do real produz uma ordem DIFERENTE
        #    (efeito observável), não a mesma resposta disfarçada — é o que
        #    faz este fake pegar M3/M4 (ver testes de mutação abaixo).
        if is_list:
            if _ORDER_BY_REAL in query:
                candidatos = _ordem_real_por_rajada(candidatos, window)
            elif "ORDER BY a.created_at DESC" in query:
                candidatos = sorted(candidatos, key=lambda a: a["created_at"], reverse=True)
            elif "ORDER BY ABS(COALESCE(a.confidence, 1.0) - 0.5) ASC" in query:
                candidatos = sorted(candidatos, key=_incerteza)
            else:
                raise AssertionError(f"ORDER BY não reconhecido: {query!r}")
            if limit is not None:
                candidatos = candidatos[:limit]

        self._result = candidatos

    def fetchall(self):
        return [dict(a) for a in self._result]

    def fetchone(self):
        return {"total": len(self._result)}


def _rvb_like_alerts(tenant_id: str, outro_tenant: str = "tenant-outro") -> list[dict]:
    """Amostra reduzida, mas com a MESMA composição medida no DEV: pending
    (verdict NULL) que são violação de verdade, pending que são conformidade
    (excluídos), já julgados (excluídos), 0 needs_human, uma rajada
    câmera+classe (reordenada, NUNCA filtrada) e um alerta de OUTRO tenant
    (prova de isolamento).
    """
    alerts = [
        # 5 eventos DISTINTOS — câmeras/classes diferentes, bem espaçados.
        _alerta("pending-0", tenant_id=tenant_id, camera_id="cam-1", classe="Sem Luvas", confidence=0.4, offset_s=0),
        _alerta("pending-1", tenant_id=tenant_id, camera_id="cam-2", classe="Sem Óculos", confidence=0.45, offset_s=1000),
        _alerta("pending-2", tenant_id=tenant_id, camera_id="cam-3", classe="Sem mascara", confidence=0.6, offset_s=2000),
        _alerta("pending-3", tenant_id=tenant_id, camera_id="cam-4", classe="Sem Luvas", confidence=0.35, offset_s=3000),
        _alerta("pending-4", tenant_id=tenant_id, camera_id="cam-5", classe="Sem Óculos", confidence=0.55, offset_s=4000),
        # Rajada: MESMA câmera+classe de pending-0, 5s e 8s depois. Rodada 3:
        # NÃO somem mais — continuam contados e aparecem DEPOIS de todos os
        # representantes (rank 1) de outras rajadas.
        _alerta("rajada-0a", tenant_id=tenant_id, camera_id="cam-1", classe="Sem Luvas", confidence=0.4, offset_s=5),
        _alerta("rajada-0b", tenant_id=tenant_id, camera_id="cam-1", classe="Sem Luvas", confidence=0.4, offset_s=8),
        # Conformidade — classe no catálogo de presença, verdict NULL. Some
        # da fila mesmo sem nunca ter sido julgada.
        _alerta("conforme-0", tenant_id=tenant_id, camera_id="cam-6", classe="Protetor Auditivo", confidence=0.9, offset_s=10),
        # Já julgados — somem por verdict, não por conformidade.
        _alerta("rejected-1", tenant_id=tenant_id, camera_id="cam-7", verdict="reject", status="human_rejected", offset_s=20),
        _alerta("approved-1", tenant_id=tenant_id, camera_id="cam-8", verdict="approve", status="human_approved", offset_s=30),
        # Outro tenant — nunca pode aparecer na fila de `tenant_id`.
        _alerta("cross-tenant", tenant_id=outro_tenant, camera_id="cam-1", classe="Sem Luvas", confidence=0.4, offset_s=40),
    ]
    return alerts


# Presença = conjunto EXCLUI da fila (mesma semântica de
# AlertRepository.presence_class_names — lowercase, ADR-0065).
_PRESENCA = ("protetor auditivo",)

# 7 = trabalho real do fixture pro tenant "tenant-1": 5 eventos distintos +
# 2 irmãos de rajada (rajada-0a/0b). Exclui conforme-0 (conformidade),
# rejected-1/approved-1 (já julgados) e cross-tenant (outro tenant).
_TRABALHO_REAL_TENANT1 = 7


class TestFilaCriterioHonestoNaoENeedsHumanFantasma:

    def test_fila_devolve_todo_o_trabalho_real_pending_com_veredito_nulo(self):
        """A régua desta rodada: TODO alerta `pending`/verdict NULL que é
        violação de verdade aparece na fila — inclusive os irmãos de rajada
        (rodada 3: dedup não filtra mais ninguém). Com o critério
        `needs_human` antigo, 0 resultados."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        esperado = {f"pending-{i}" for i in range(5)} | {"rajada-0a", "rajada-0b"}
        assert {a["id"] for a in result} == esperado
        assert len(result) == _TRABALHO_REAL_TENANT1

    def test_fila_nao_devolve_alertas_ja_julgados(self):
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        ids = {a["id"] for a in result}
        assert "rejected-1" not in ids
        assert "approved-1" not in ids

    def test_fila_exclui_conformidade_mesmo_com_veredito_nulo(self):
        """Achado do cético: 302/416 (72,6%) dos `verdict IS NULL` do DEV são
        CONFORMIDADE — a fila de revisão HUMANA não é lugar pra confirmar o
        que o sistema já considera OK."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert "conforme-0" not in {a["id"] for a in result}

    def test_representante_da_rajada_aparece_antes_dos_irmaos(self):
        """Achado do cético (rodada 3): dedup não pode mais EXCLUIR — só
        reordenar. `rajada-0a`/`rajada-0b` (irmãos de `pending-0`, mesma
        câmera+classe, <10s de diferença) continuam na fila inteira, mas
        depois de TODOS os representantes (rank 1) das outras rajadas —
        maximiza eventos distintos vistos cedo sem esconder ninguém. Julgar
        o representante NÃO decide os irmãos — nenhuma propagação aqui (ver
        docstring do módulo: decisão de produto pendente)."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        ids = [a["id"] for a in result]
        assert "rajada-0a" in ids
        assert "rajada-0b" in ids
        posicao_irmaos = min(ids.index("rajada-0a"), ids.index("rajada-0b"))
        posicao_ultimo_representante = max(ids.index(f"pending-{i}") for i in range(5))
        assert posicao_irmaos > posicao_ultimo_representante, (
            "os 2 irmãos de rajada têm de vir DEPOIS de todos os 5 "
            "representantes de outras rajadas"
        )

    def test_fila_nunca_vaza_alerta_de_outro_tenant(self):
        """Prova direta contra o achado do cético (fake anterior vazava
        tenant-2 pra tenant-1): o fixture MISTURA tenants de propósito."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1", outro_tenant="tenant-2"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert "cross-tenant" not in {a["id"] for a in result}

        cursor2 = _FakeDbCursor(_rvb_like_alerts("tenant-1", outro_tenant="tenant-2"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor2)
            result2 = _make_service().get_human_queue(tenant_id="tenant-2")
        assert {a["id"] for a in result2} == {"cross-tenant"}

    def test_fila_respeita_limit_de_verdade(self):
        """Achado do cético: o fake anterior ignorava `limit`. Este devolve
        só os N primeiros na ordem real quando o `limit` corta o conjunto."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1", limit=2)
        assert len(result) == 2

    def test_fila_respeita_camera_id_de_verdade(self):
        """Achado do cético: o fake anterior ignorava `camera_id`."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1", camera_id="cam-3")
        assert {a["id"] for a in result} == {"pending-2"}

    def test_fila_ordena_por_incerteza_nao_por_recencia(self):
        """Achado do cético: os 50 mais recentes tinham confiança 0,90-1,00 —
        o modelo já tinha certeza. Dentro do tier de representantes (rank 1),
        a ordem é por incerteza — nunca por `created_at`, que poria
        `pending-4` (o mais recente) primeiro."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        # pending-4 (offset mais recente, confiança 0,55) NÃO pode ser o
        # primeiro — seria ORDER BY created_at, não por incerteza.
        assert result[0]["id"] != "pending-4"
        # Dentro do tier de representantes (as 5 primeiras posições, um por
        # rajada), a incerteza é crescente.
        tier_representantes = result[:5]
        incertezas = [_incerteza(a) for a in tier_representantes]
        assert incertezas == sorted(incertezas)

    def test_contagem_conta_trabalho_real_sem_dedup_de_rajada(self):
        """Achado do cético (rodada 3, o bloqueio principal): contar só os
        representantes (5 no fixture, 15 no DEV) faz `total` cair pra 0 ao
        julgar só eles, enquanto os irmãos de rajada (2 no fixture, 99 no
        DEV) continuam pendentes — "Fila zerada" mentindo de novo. Contagem
        honesta = TODO candidato, sem dedup nenhum."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            count = _make_service().get_queue_count(tenant_id="tenant-1")
        assert count == _TRABALHO_REAL_TENANT1

    def test_contagem_bate_com_o_tamanho_da_fila_sem_limit(self):
        """`total` e `len(get_human_queue(limit=200))` têm de bater — mesma
        régua que motivou o achado do cético (contagem e lista com WHERE
        divergente)."""
        cursor_count = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor_count)
            count = _make_service().get_queue_count(tenant_id="tenant-1")

        cursor_list = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor_list)
            items = _make_service().get_human_queue(tenant_id="tenant-1", limit=200)

        assert count == len(items)

    def test_query_nao_usa_mais_verification_status_needs_human(self):
        """Assinatura textual do gate: se alguém reintroduzir
        `verification_status = 'needs_human'` no WHERE, este teste falha —
        checa a query de CADA chamada, não só a última."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
            _make_service().get_queue_count(tenant_id="tenant-1")
        queries_principais = [q for q, _ in cursor.calls if "candidatos AS" in q]
        assert len(queries_principais) == 2, "get_human_queue + get_queue_count"
        for query in queries_principais:
            assert "needs_human" not in query
            assert "a.verification_verdict IS NULL" in query

    def test_presence_names_escopado_por_epi_nao_todos_os_modulos(self):
        """Achado do cético (rodada 3): `presence_class_names` sem
        `module_code` vazava classes de OUTRO módulo (medido no DEV: 24
        nomes sem módulo vs. 13 com 'epi' — `truck`/`pallet`/`forklift` de
        fueling seriam lidos como conformidade de EPI). Hoje o impacto é 0
        (RVB é EPI-only), mas no primeiro tenant de fueling/contagem isso
        some alerta real da fila em silêncio."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"), presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        presence_query, presence_params = cursor.calls[0]  # 1ª chamada = presence_class_names
        assert "module_classes" in presence_query and "yolo_classes" in presence_query
        assert "module_code = %s" in presence_query
        assert "epi" in presence_params


class TestFakeDetectaMutacoesDeOrdenacao:
    """As duas mutações que o cético provou que passavam no fake da rodada 2
    (102 passed, 0 failed): M3 reverte o `ORDER BY` pra `created_at DESC`;
    M4 neutraliza o rank de rajada (sobra só incerteza, sem tier). Aqui a
    query REAL capturada (não uma reconstrução manual, que pode divergir do
    texto de verdade) é mutada em UM ponto (o `ORDER BY`) e reexecutada no
    fake — a ordem observável muda, provando que o fake DEPENDE do texto."""

    def _query_real_capturada(self) -> tuple[list[dict], str, tuple]:
        alerts = _rvb_like_alerts("tenant-1")
        cursor = _FakeDbCursor(alerts, presence_names=_PRESENCA)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        query, params = cursor.calls[-1]
        assert _ORDER_BY_REAL in query, "sanity: a query real tem de conter o ORDER BY esperado"
        return alerts, query, params

    def test_M3_reverter_para_created_at_desc_muda_a_ordem(self):
        alerts, query_real, params = self._query_real_capturada()
        query_m3 = query_real.replace(_ORDER_BY_REAL, "ORDER BY a.created_at DESC")
        assert query_m3 != query_real

        cursor_m3 = _FakeDbCursor(alerts, presence_names=_PRESENCA)
        cursor_m3.execute(query_m3, params)
        ordem_m3 = [a["id"] for a in cursor_m3.fetchall()]

        # created_at DESC bota o mais RECENTE primeiro — pending-4 (offset
        # 4000, o maior). Com o rank de rajada (comportamento real), isso
        # NUNCA acontece (pending-4 tem incerteza mediana, não é o 1º).
        assert ordem_m3[0] == "pending-4"

    def test_M4_neutralizar_rank_de_rajada_intercala_irmao_com_representantes(self):
        alerts, query_real, params = self._query_real_capturada()
        query_m4 = query_real.replace(
            _ORDER_BY_REAL, "ORDER BY ABS(COALESCE(a.confidence, 1.0) - 0.5) ASC",
        )
        assert query_m4 != query_real

        cursor_m4 = _FakeDbCursor(alerts, presence_names=_PRESENCA)
        cursor_m4.execute(query_m4, params)
        ordem_m4 = [a["id"] for a in cursor_m4.fetchall()]

        # Sem o rank de rajada, `rajada-0a` (incerteza 0,1 — empatada com
        # pending-0/pending-2) intercala com representantes de OUTRAS
        # rajadas, ao invés de ficar atrás de TODOS eles (comportamento
        # real, provado em test_representante_da_rajada_aparece_antes_dos_irmaos).
        posicao_irmao = ordem_m4.index("rajada-0a")
        posicao_ultimo_representante = max(ordem_m4.index(f"pending-{i}") for i in range(5))
        assert posicao_irmao < posicao_ultimo_representante, (
            "sem o rank de rajada, o irmão vem ANTES de algum representante "
            "— prova que é o rank (não a incerteza sozinha) que garante "
            "'representante primeiro'"
        )


# ---------------------------------------------------------------------------
# human_review
# ---------------------------------------------------------------------------

class TestHumanReview:

    def test_invalid_verdict_raises_value_error(self):
        with pytest.raises(ValueError, match="verdict"):
            _make_service().human_review("alert-1", "maybe", "user-1", "tenant-1")

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="Database"):
                _make_service().human_review("a-1", "approve", "u-1", "tenant-1")

    def test_approve_sets_human_approved_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1", "tenant-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_approved" in params

    def test_reject_sets_human_rejected_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "reject", "u-1", "tenant-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_rejected" in params

    def test_no_rows_affected_returns_false(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1", "tenant-1")
        assert result is False

    def test_user_id_included_in_query_params(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("alert-xyz", "approve", "user-99", "tenant-1")
        params = mock_cursor.execute.call_args[0][1]
        assert any("user-99" in str(p) for p in params)

    def test_gate_nao_volta_a_exigir_needs_human(self):
        """FALHA se o gate voltar a `verification_status = 'needs_human'`.

        Nenhum alerta alcança esse estado: a coluna nasce `DEFAULT 'pending'`
        (migration 016) e `submit_for_verification` não tem NENHUM chamador no
        repositório. Com o gate, o veredito humano é INGRAVÁVEL e a coluna fica
        NULL em 100% das linhas — que é exatamente o estado medido no DEV
        (334/334 com `verification_verdict` NULL). C-01 continua no WHERE.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().human_review(
                "a1", "reject", "u1", tenant_id="t1"
            ) is True
        query, _ = mock_cursor.execute.call_args[0]
        assert "needs_human" not in query
        assert "tenant_id = %s" in query

    def test_veredito_humano_carimba_prefixo_user_em_verified_by(self):
        """FALHA se o prefixo 'user:' sumir de `verified_by`.

        É a ÚNICA prova de que quem julgou foi gente: a task Celery grava o
        MESMO 'approve'/'reject' com verified_by='claude-haiku'
        (infrastructure/queue/tasks/verification.py). Sem o prefixo, a tela
        apresenta decisão de máquina como julgamento humano.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("a1", "approve", "u-42", tenant_id="t1")
        _, params = mock_cursor.execute.call_args[0]
        assert "user:u-42" in params

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().human_review("a-1", "approve", "u-1")  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        """UPDATE deve incluir `tenant_id = %s` no WHERE — sem isso, um
        operador de um tenant podia revisar alerta de outro (achado #14)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("a-1", "approve", "u-1", "tenant-b")
        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert "tenant-b" in params

    def test_update_does_not_require_needs_human(self):
        """O veredito humano vale para QUALQUER alerta do tenant.

        FALHAVA antes: o WHERE terminava em
        `AND verification_status = 'needs_human'`, e como nada chama
        `submit_for_verification` nenhum alerta chega a esse status — a rota
        devolvia 404 para 100% dos alertas reais e `verification_verdict`
        ficava NULL nos 334 do shadow. O `tenant_id` NÃO pode ser afrouxado
        junto (C-01): é o que continua barrando IDOR cross-tenant.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().human_review("a-1", "approve", "u-1", "tenant-b") is True
        query, params = mock_cursor.execute.call_args[0]
        assert "needs_human" not in query
        assert "tenant_id = %s" in query
        assert "tenant-b" in params

    def test_cross_tenant_alert_id_does_not_match_other_tenant(self):
        """tenant_a_id nunca aparece nos params quando o request é do tenant_b."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # simula: WHERE não bate pois alerta é do tenant_a
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("alert-of-tenant-a", "approve", "u-1", "tenant-b")
        _, params = mock_cursor.execute.call_args[0]
        assert "tenant-b" in params
        assert result is False


# ---------------------------------------------------------------------------
# get_queue_count
# ---------------------------------------------------------------------------

class TestGetQueueCount:

    def test_pool_none_returns_zero(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_returns_count_from_db(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 7}
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 7

    def test_fetchone_none_returns_zero(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_db_exception_sobe_em_vez_de_virar_zero(self):
        """0 é uma contagem legítima do badge — não serve de "não sei"."""
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            with pytest.raises(Exception, match="DB crash"):
                _make_service().get_queue_count(tenant_id="tenant-1")

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().get_queue_count()  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_queue_count(tenant_id="tenant-b")
        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert "tenant-b" in params


class TestRazaoDoVeredito:
    """A justificativa do operador é o que alimenta a recalibração de limiar.

    A rota já aceitava `reason` no corpo e o descartava em silêncio: o UPDATE
    não tinha a coluna. Provado no DEV: veredito gravado, `verification_reason`
    vazio.
    """

    def test_a_razao_vai_para_o_update(self):
        from unittest.mock import MagicMock, patch

        from app.domain.services.verification_service import VerificationService

        cur = MagicMock()
        cur.rowcount = 1
        pool = MagicMock()
        pool.get_connection.return_value.__enter__.return_value.cursor.return_value = cur

        with patch("app.domain.services.verification_service._get_pool", return_value=pool):
            VerificationService().human_review(
                alert_id="a1", verdict="reject", user_id="u1", tenant_id="t1",
                reason="a caixa pegou a luva do colega ao lado",
            )

        sql, params = cur.execute.call_args[0]
        assert "verification_reason = %s" in sql
        assert "a caixa pegou a luva do colega ao lado" in params

    def test_sem_razao_grava_nulo_nao_string_vazia(self):
        from unittest.mock import MagicMock, patch

        from app.domain.services.verification_service import VerificationService

        cur = MagicMock()
        cur.rowcount = 1
        pool = MagicMock()
        pool.get_connection.return_value.__enter__.return_value.cursor.return_value = cur

        with patch("app.domain.services.verification_service._get_pool", return_value=pool):
            VerificationService().human_review(
                alert_id="a1", verdict="approve", user_id="u1", tenant_id="t1", reason="",
            )

        _, params = cur.execute.call_args[0]
        assert None in params
