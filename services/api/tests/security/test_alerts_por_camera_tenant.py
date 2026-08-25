"""`GET /api/cameras/<id>/alerts` lia alerta de qualquer tenant.

A rota tem apenas `@jwt_required()`, e a cadeia inteira não checava posse:

    rota → get_alerts_handler → InferenceService.get_alerts
         → AlertRepository.get_by_camera
         → SELECT * FROM alerts WHERE camera_id = %s

Escopo puro de câmera. Qualquer usuário autenticado de QUALQUER tenant lia os
alertas de qualquer câmera bastando o id. É a mesma forma do achado #14 (fila
de verificação), que foi corrigido lá e ficou aqui — o irmão
`get_unacknowledged` já filtrava por tenant desde sempre.

Agravante encontrado junto: a migration 022 insere 13 alertas de demonstração
com `tenant_id` fixo no tenant "Default" e `camera_id` de
`SELECT id FROM cameras LIMIT 1` — qualquer câmera, de qualquer tenant. Com o
escopo puro de câmera, esses alertas falsos apareceriam dentro da visão do
tenant dono daquela câmera.

C-01: câmera de outro tenant sai VAZIA, não 403 — não vazar existência.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.domain.services.inference_service import InferenceService
from app.infrastructure.database.repositories.alert_repository import AlertRepository

_CAMERA = uuid4()
_TENANT_A = str(uuid4())
_TENANT_B = str(uuid4())


class TestSqlEscopadoPorTenant:
    def _sql_de(self, **kwargs) -> tuple[str, tuple]:
        repo = AlertRepository.__new__(AlertRepository)
        chamada = MagicMock(return_value=[])
        repo._execute = chamada  # type: ignore[method-assign]
        repo.get_by_camera(**kwargs)
        return chamada.call_args[0]

    def test_query_filtra_por_tenant(self):
        sql, params = self._sql_de(camera_id=_CAMERA, tenant_id=_TENANT_A)
        assert "tenant_id = %s" in sql, (
            "sem isto a rota devolve alerta de qualquer tenant pelo camera_id"
        )
        assert _TENANT_A in params

    def test_tenant_e_obrigatorio(self):
        """Sem default: esquecer o tenant tem de quebrar em tempo de chamada,
        não devolver dados de todo mundo em silêncio."""
        repo = AlertRepository.__new__(AlertRepository)
        repo._execute = MagicMock(return_value=[])  # type: ignore[method-assign]
        with pytest.raises(TypeError):
            repo.get_by_camera(_CAMERA)  # type: ignore[call-arg]

    def test_tenant_de_outro_nao_entra_nos_params(self):
        _sql, params = self._sql_de(camera_id=_CAMERA, tenant_id=_TENANT_B)
        assert _TENANT_B in params
        assert _TENANT_A not in params


class TestServicoRepassaOTenant:
    def test_get_alerts_repassa(self):
        repo = MagicMock()
        repo.get_by_camera.return_value = []
        InferenceService(repo).get_alerts(_CAMERA, _TENANT_A, 10, 0)
        repo.get_by_camera.assert_called_once_with(_CAMERA, _TENANT_A, 10, 0)

    def test_get_alerts_exige_o_tenant(self):
        repo = MagicMock()
        with pytest.raises(TypeError):
            InferenceService(repo).get_alerts(_CAMERA)  # type: ignore[call-arg]

    def test_get_unacknowledged_repassa_o_tenant(self):
        """Antes passava (camera_id, limit) e deixava tenant_id=None, que
        virava a string "None" contra uma coluna uuid."""
        repo = MagicMock()
        repo.get_unacknowledged.return_value = []
        InferenceService(repo).get_unacknowledged(_TENANT_A, _CAMERA, 25)
        repo.get_unacknowledged.assert_called_once_with(_CAMERA, 25, _TENANT_A)


class TestOHandlerPegaOTenantDoToken:
    def test_handler_chama_get_tenant_id(self):
        """Guard de fonte: o tenant tem de vir do token, nunca da query string
        (onde o cliente escolheria de quem ler)."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        fonte = (
            raiz / "app" / "api" / "v1" / "training" / "job_handlers.py"
        ).read_text(encoding="utf-8")
        trecho = fonte.split("def get_alerts_handler", 1)[1].split("\ndef ", 1)[0]
        assert "get_tenant_id()" in trecho
        assert 'args.get("tenant' not in trecho
