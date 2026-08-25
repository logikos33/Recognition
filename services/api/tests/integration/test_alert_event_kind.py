"""
Integration: presença é CONFORMIDADE, ausência é VIOLAÇÃO (ADR-0063).

Postgres REAL — o defeito é de SQL (predicado + ordem de parâmetros) e de
schema (`yolo_classes.is_violation`, migration 125). Mock de repositório não
enxerga nenhum dos dois.

FALHA antes do fix: `list_with_filters` não conhecia `kind`, não devolvia
`event_kind`, e as classes do tenant não tinham polaridade — todo alerta era
violação, inclusive "Protetor auditivo" (EPI EM USO). PASSA depois.

O caso que mais importa aqui é o 4º: o alerta `camera_gap` do liveness grava
`[{"type": "camera_gap", ...}]` SEM chave `class`. Se a classificação errasse
para o lado "conformidade", o alerta de CÂMERA OFFLINE sumiria da tela padrão
e ninguém perceberia. Sumir é o erro caro; aparecer a mais é barato (ADR-0017).

Pulados automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.alert_repository import AlertRepository


NOW = datetime.now(tz=timezone.utc)

PRESENCA = "Protetor auditivo"
AUSENCIA = "Sem protetor de ouvido"
DESCONHECIDA = "Classe Que Ninguem Cadastrou"


# ---------------------------------------------------------------------------
# Helpers de seed
# ---------------------------------------------------------------------------

def _insert_user(cur, tenant_id: str) -> str:
    uid = str(uuid4())
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, f"kind-{uid[:8]}@test.dev", "x", "IntTest Kind", "operator", tenant_id),
    )
    return uid


def _insert_camera(cur, tenant_id: str, user_id: str, name: str, location: str | None) -> str:
    cid = str(uuid4())
    cur.execute(
        "INSERT INTO public.cameras (id, tenant_id, user_id, name, location, host, port) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (cid, tenant_id, user_id, name, location, "192.168.1.1", 554),
    )
    return cid


def _insert_class(cur, tenant_id: str, user_id: str, name: str, is_violation: bool | None) -> None:
    cur.execute(
        "INSERT INTO public.yolo_classes (user_id, name, tenant_id, module_code, is_violation) "
        "VALUES (%s, %s, %s, 'epi', %s)",
        (user_id, name, tenant_id, is_violation),
    )


def _insert_alert(cur, tenant_id: str, camera_id: str, violations: list[dict]) -> str:
    aid = str(uuid4())
    cur.execute(
        "INSERT INTO public.alerts "
        "  (id, camera_id, tenant_id, module_code, violations, confidence, "
        "   evidence_key, created_at) "
        "VALUES (%s, %s, %s, 'epi', %s::jsonb, %s, %s, %s)",
        (aid, camera_id, tenant_id, json.dumps(violations), 0.76,
         f"evidence/{aid}.jpg", NOW - timedelta(minutes=5)),
    )
    return aid


def _purge_tenant(pg_raw, tid: str) -> None:
    """Apaga o que este arquivo semeia, em ordem reversa de FK.

    `alerts`, `cameras`, `yolo_classes` e `users` referenciam `tenants` com
    NO ACTION (não CASCADE, conferido em pg_constraint) — sem isto o
    `DELETE FROM tenants` do fixture `tenant_id` (conftest) estoura
    ForeignKeyViolation no teardown. Mesmo padrão de limpeza explícita de
    test_compliance_report_aggregation.py.
    """
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.yolo_classes WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tid,))


@pytest.fixture
def cenario(pg_raw, tenant_id):
    """Taxonomia + 4 alertas: o campo virgem da RVB em miniatura."""
    with pg_raw.cursor() as cur:
        user_id = _insert_user(cur, tenant_id)
        cam = _insert_camera(cur, tenant_id, user_id, "Canal 8", "Expedição")
        _insert_class(cur, tenant_id, user_id, PRESENCA, False)
        _insert_class(cur, tenant_id, user_id, AUSENCIA, True)

        ids = {
            "so_presenca": _insert_alert(cur, tenant_id, cam, [
                {"class": PRESENCA, "confidence": 0.76, "modo": "shadow"},
            ]),
            "presenca_e_ausencia": _insert_alert(cur, tenant_id, cam, [
                {"class": PRESENCA, "confidence": 0.81},
                {"class": AUSENCIA, "confidence": 0.44},
            ]),
            "camera_gap": _insert_alert(cur, tenant_id, cam, [
                {"type": "camera_gap", "cameras_online": 27, "cameras_total": 28},
            ]),
            "desconhecida": _insert_alert(cur, tenant_id, cam, [
                {"class": DESCONHECIDA, "confidence": 0.5},
            ]),
        }
    yield {"camera_id": cam, "user_id": user_id, "ids": ids}
    _purge_tenant(pg_raw, tenant_id)


def _kind_by_id(repo: AlertRepository, tenant_id: str, kind: str | None = None) -> dict[str, str]:
    result = repo.list_with_filters(tenant_id=tenant_id, limit=100, offset=0, kind=kind)
    return {str(row["id"]): row["event_kind"] for row in result["items"]}


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

class TestEventKind:

    def test_so_presenca_e_conformidade(self, pg_pool, tenant_id, cenario):
        """EPI EM USO não é alerta — é telemetria."""
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
        assert kinds[cenario["ids"]["so_presenca"]] == "compliance"

    def test_uma_ausencia_basta_para_ser_violacao(self, pg_pool, tenant_id, cenario):
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
        assert kinds[cenario["ids"]["presenca_e_ausencia"]] == "violation"

    def test_camera_gap_sem_chave_class_nao_pode_sumir(self, pg_pool, tenant_id, cenario):
        """A regressão perigosa: câmera offline continua visível."""
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
        assert kinds[cenario["ids"]["camera_gap"]] == "violation"

    def test_classe_fora_do_catalogo_e_violacao(self, pg_pool, tenant_id, cenario):
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
        assert kinds[cenario["ids"]["desconhecida"]] == "violation"

    def test_is_violation_null_nunca_conta_como_presenca(self, pg_raw, pg_pool, tenant_id, cenario):
        """NULL = ninguém decidiu ainda ⇒ cai em VIOLAÇÃO, onde alguém percebe."""
        with pg_raw.cursor() as cur:
            _insert_class(cur, tenant_id, cenario["user_id"], "Classe Indecisa", None)
            aid = _insert_alert(cur, tenant_id, cenario["camera_id"], [
                {"class": "Classe Indecisa", "confidence": 0.9},
            ])
        assert _kind_by_id(AlertRepository(pg_pool), tenant_id)[aid] == "violation"


# ---------------------------------------------------------------------------
# Filtro ?kind= — o recorte paginado tem de bater com o event_kind mostrado
# ---------------------------------------------------------------------------

class TestKindFilter:

    def test_violation_esconde_a_conformidade(self, pg_pool, tenant_id, cenario):
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id, kind="violation")
        assert cenario["ids"]["so_presenca"] not in kinds
        assert set(kinds.values()) == {"violation"}
        assert len(kinds) == 3

    def test_compliance_mostra_so_o_epi_em_uso(self, pg_pool, tenant_id, cenario):
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id, kind="compliance")
        assert list(kinds) == [cenario["ids"]["so_presenca"]]

    def test_total_acompanha_o_filtro(self, pg_pool, tenant_id, cenario):
        """`total` alimenta a paginação — se ignorar o filtro, a tela mente."""
        repo = AlertRepository(pg_pool)
        assert repo.list_with_filters(tenant_id=tenant_id, kind="violation")["total"] == 3
        assert repo.list_with_filters(tenant_id=tenant_id, kind="compliance")["total"] == 1
        assert repo.list_with_filters(tenant_id=tenant_id)["total"] == 4

    def test_kind_none_devolve_tudo_com_event_kind(self, pg_pool, tenant_id, cenario):
        """Default do backend é 'todos' — nenhum consumidor existente muda."""
        kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
        assert len(kinds) == 4

    def test_filtro_convive_com_os_filtros_antigos(self, pg_pool, tenant_id, cenario):
        """Ordem dos parâmetros: `kind` entra DEPOIS de camera_id/datas/ack."""
        result = AlertRepository(pg_pool).list_with_filters(
            tenant_id=tenant_id,
            camera_id=cenario["camera_id"],
            start_date=NOW - timedelta(hours=1),
            end_date=NOW,
            acknowledged=False,
            kind="violation",
        )
        assert result["total"] == 3
        assert {r["event_kind"] for r in result["items"]} == {"violation"}


# ---------------------------------------------------------------------------
# C-01 — a polaridade de um tenant não classifica o alerta de outro
# ---------------------------------------------------------------------------

class TestCrossTenant:

    def test_presenca_de_outro_tenant_nao_vira_conformidade_aqui(
        self, pg_raw, pg_pool, tenant_id, cenario
    ):
        outro = str(uuid4())
        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (outro, "IntTest Outro", f"inttest-outro-{outro[:8]}"),
            )
            outro_user = _insert_user(cur, outro)
            # O OUTRO tenant declara a classe desconhecida como presença.
            _insert_class(cur, outro, outro_user, DESCONHECIDA, False)
        try:
            kinds = _kind_by_id(AlertRepository(pg_pool), tenant_id)
            assert kinds[cenario["ids"]["desconhecida"]] == "violation"
        finally:
            _purge_tenant(pg_raw, outro)
            with pg_raw.cursor() as cur:
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (outro,))


# ---------------------------------------------------------------------------
# KPIs que estavam invertidos + painel de taxa de uso
# ---------------------------------------------------------------------------

class TestAggregates:

    def test_hora_camera_so_de_presenca_nao_conta_como_violacao(
        self, pg_raw, pg_pool, tenant_id, cenario
    ):
        """`compliance_rate` se apoia neste número — com presença dentro, quanto
        mais gente usava EPI, MENOR ficava a 'conformidade'."""
        repo = AlertRepository(pg_pool)
        since = NOW - timedelta(hours=1)
        # Cenário completo: 1 hora-câmera (todos os alertas na mesma hora/câmera).
        assert repo.camera_hours_with_violation(tenant_id, "epi", since) == 1

        # Câmera 2 com APENAS conformidade não pode somar hora de violação.
        with pg_raw.cursor() as cur:
            cam2 = _insert_camera(cur, tenant_id, cenario["user_id"], "Canal 9", "Portaria")
            _insert_alert(cur, tenant_id, cam2, [{"class": PRESENCA, "confidence": 0.9}])
        assert repo.camera_hours_with_violation(tenant_id, "epi", since) == 1

    def test_classe_de_presenca_nao_vira_linha_de_violacao_por_classe(
        self, pg_pool, tenant_id, cenario
    ):
        rows = AlertRepository(pg_pool).violation_hours_by_class(
            tenant_id, "epi", NOW - timedelta(hours=1)
        )
        classes = {r["class"] for r in rows}
        assert PRESENCA not in classes
        assert AUSENCIA in classes

    def test_taxa_de_uso_por_area(self, pg_pool, tenant_id, cenario):
        rows = AlertRepository(pg_pool).usage_rate_by_area(
            tenant_id, NOW - timedelta(hours=1), NOW + timedelta(minutes=1), module_code="epi"
        )
        por_area = {r["area"]: r for r in rows}
        assert por_area["Expedição"]["compliance"] == 1
        assert por_area["Expedição"]["violation"] == 3

    def test_area_cai_no_nome_da_camera_sem_location(
        self, pg_raw, pg_pool, tenant_id, cenario
    ):
        with pg_raw.cursor() as cur:
            cam = _insert_camera(cur, tenant_id, cenario["user_id"], "Canal 12", None)
            _insert_alert(cur, tenant_id, cam, [{"class": AUSENCIA, "confidence": 0.3}])
        rows = AlertRepository(pg_pool).usage_rate_by_area(
            tenant_id, NOW - timedelta(hours=1), NOW + timedelta(minutes=1)
        )
        assert {r["area"] for r in rows} >= {"Expedição", "Canal 12"}


# ---------------------------------------------------------------------------
# A raiz: polaridade da classe do tenant chega ao frontend
# ---------------------------------------------------------------------------

class TestModuleServicePolarity:

    def test_get_classes_devolve_a_polaridade_real(self, pg_pool, tenant_id, cenario):
        """FALHA antes do fix: `is_violation: False` hardcoded para TODA classe
        de tenant — "Sem protetor de ouvido" chegava como se fosse presença."""
        from app.domain.services.module_service import module_service

        classes = module_service.get_classes("epi", tenant_id=tenant_id)
        por_nome = {c["class_name"]: c["is_violation"] for c in classes}
        assert por_nome[AUSENCIA] is True
        assert por_nome[PRESENCA] is False
