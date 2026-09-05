"""
Tests: `GET /api/modules/<code>/stats` não pode devolver 100 sobre o vazio.

MEDIDO no DEV em 2026-09-05 (tenant RVB, 17 câmeras ativas, 5.174 alertas no
acervo, ZERO nas últimas 24 h):

    GET /api/modules/epi/stats  →  200
    {"compliance_rate": 100.0, "alerts_today": 0, "alerts_last_hour": 0,
     "alerts_week": 127, "cameras_active": 17}

O `compliance_rate` é `100 × (1 − horas-câmera-com-violação ÷ (ativas × 24))`.
O denominador SUPÕE 24 h monitoradas por câmera — ninguém mede isso. Com nada
chegando, o numerador é 0 por ausência de observação, não por conformidade, e
o painel pintava "100 · Conforme" em VERDE sobre um dia em que o sistema não
viu nada. Um número que afirma mais do que sabe é o defeito; `null` é o
conserto.

O guard vive na ROTA (`app/api/v1/modules/routes.py`) porque é o único lugar
por onde `compliance_rate` sai para o cliente — `list_tenant_modules` só
publica `cameras_count`/`alerts_today`.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from app.infrastructure.database.repositories.alert_repository import AlertRepository

_HAS_MODULE = "app.domain.services.module_service.module_service.tenant_has_module"
_GET_STATS = "app.domain.services.module_service.module_service.get_stats"
# Alvos que JÁ existem na develop — o vermelho tem de vir da asserção
# ("devolveu 100 sobre o vazio"), nunca de um patch que não encontra o alvo.
_POOL = "app.infrastructure.database.connection.DatabasePool.get_instance"

#: A resposta REAL medida no DEV — copiada byte a byte do curl acima.
STATS_DEV_RVB = {
    "active_model_map50": 0.4304,
    "active_model_name": "RF-DETR - Job 0307e2b1",
    "alerts_last_hour": 0,
    "alerts_prev_hour": 0,
    "alerts_today": 0,
    "alerts_week": 127,
    "cameras_active": 17,
    "cameras_total": 17,
    "compliance_by_class": {},
    "compliance_rate": 100.0,
}


def _token(app, tenant_id=None):
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": "admin",
                "tenant_id": tenant_id or str(uuid4()),
                "tenant_schema": "public",
            },
        )


def _chamar(client, app, stats, alertas_na_janela):
    """Chama a rota com `get_stats` fixado e o contador de ingestão mockado.

    `alertas_na_janela` = o que `AlertRepository.count_in_window` devolve;
    passe uma Exception para simular consulta que não respondeu.
    """
    contador = MagicMock()
    if isinstance(alertas_na_janela, Exception):
        contador.side_effect = alertas_na_janela
    else:
        contador.return_value = alertas_na_janela
    with (
        patch(_HAS_MODULE, return_value=True),
        patch(_GET_STATS, return_value=dict(stats)),
        patch(_POOL, return_value=MagicMock()),
        patch.object(AlertRepository, "count_in_window", contador),
    ):
        res = client.get(
            "/api/modules/epi/stats",
            headers={"Authorization": f"Bearer {_token(app)}"},
        )
    return res, contador


class TestScoreSobreOVazio:
    def test_sem_alerta_nenhum_em_24h_o_score_vira_null(self, client, app):
        """O caso do DEV: 17 câmeras ativas, zero ingestão, score 100."""
        res, _contador = _chamar(client, app, STATS_DEV_RVB, alertas_na_janela=0)
        assert res.status_code == 200
        stats = res.get_json()["data"]["stats"]
        assert stats["compliance_rate"] is None
        assert stats["compliance_reason"] == "sem_sinal_no_periodo"
        # O por-classe se apoia no MESMO denominador — não pode sobreviver
        # ao número que o sustentava.
        assert stats["compliance_by_class"] == {}

    def test_com_alerta_na_janela_o_score_passa_intacto(self, client, app):
        """Houve ingestão ⇒ o número é apurável e sai como veio. O guard não
        pode virar um "sempre null" que apaga o painel no dia bom."""
        res, contador = _chamar(client, app, STATS_DEV_RVB, alertas_na_janela=3)
        stats = res.get_json()["data"]["stats"]
        assert stats["compliance_rate"] == 100.0
        assert stats["compliance_reason"] is None
        # Janela de 24 h e escopo do módulo — os mesmos do número que ele nega.
        _args, kwargs = contador.call_args
        assert kwargs["module_code"] == "epi"
        janela = kwargs["to_ts"] - kwargs["from_ts"]
        assert janela == timedelta(hours=24)
        assert kwargs["to_ts"] <= datetime.now(tz=UTC) + timedelta(seconds=5)

    def test_consulta_de_ingestao_que_falha_tambem_anula(self, client, app):
        """Mesma doutrina do `_FALHOU` em `get_stats`: consulta que não
        respondeu não vira 100 — o banco cair não pode mostrar o número
        perfeito."""
        res, _contador = _chamar(
            client, app, STATS_DEV_RVB, alertas_na_janela=RuntimeError("pool morto")
        )
        stats = res.get_json()["data"]["stats"]
        assert stats["compliance_rate"] is None
        assert stats["compliance_reason"] == "nao_foi_possivel_apurar"

    def test_score_ja_nulo_ganha_a_razao_sem_recalcular(self, client, app):
        """`get_stats` já anula sem câmera ativa. A rota só nomeia a razão —
        e não gasta uma consulta para redescobrir o que já sabe."""
        sem_camera = {**STATS_DEV_RVB, "cameras_active": 0, "compliance_rate": None}
        res, contador = _chamar(client, app, sem_camera, alertas_na_janela=99)
        stats = res.get_json()["data"]["stats"]
        assert stats["compliance_rate"] is None
        assert stats["compliance_reason"] == "sem_cameras_ativas"
        contador.assert_not_called()
