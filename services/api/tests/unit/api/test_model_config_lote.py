"""A tela de escopo por câmera não pode quebrar no tenant de tamanho real.

A versão por câmera disparava um GET por câmera em `Promise.all`. Com as 28 da
RVB, o pool de conexões da API estourava e a aba ficava inacessível — medido no
DEV em 2026-08-25: "connection pool exhausted" na resposta, com o banco folgado
(5 conexões de 500). O gargalo era a concorrência da própria tela.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.infrastructure.database.repositories.model_deployment_repository import (
    ModelDeploymentRepository,
)


def _repo() -> tuple[ModelDeploymentRepository, MagicMock]:
    repo = ModelDeploymentRepository.__new__(ModelDeploymentRepository)
    executar = MagicMock(return_value=[])
    repo._execute = executar  # type: ignore[method-assign]
    return repo, executar


def test_uma_consulta_para_todas_as_cameras():
    repo, executar = _repo()

    repo.list_active_for_tenant("tenant-a", "epi")

    assert executar.call_count == 1, "uma ida ao banco, não uma por câmera"
    sql, params = executar.call_args[0]
    assert "DISTINCT ON (camera_id)" in sql, (
        "sem DISTINCT ON o lote devolve todo o histórico, não o ativo por câmera"
    )
    assert "ORDER BY camera_id, created_at DESC" in sql, (
        "o mais recente por câmera é o que get_active_for_camera devolve"
    )
    assert params == ("tenant-a", "epi")


def test_o_tenant_esta_no_where():
    """C-01: não existe caminho para ler deployment de outro tenant."""
    repo, executar = _repo()

    repo.list_active_for_tenant("tenant-a")

    sql, params = executar.call_args[0]
    assert "tenant_id = %s" in sql
    assert params[0] == "tenant-a"


def test_so_deployment_ativo():
    repo, executar = _repo()
    repo.list_active_for_tenant("tenant-a")
    sql, _ = executar.call_args[0]
    assert "status = 'active'" in sql


def test_a_rota_em_lote_existe_antes_da_rota_por_id():
    """Ordem importa: '/model-config' casaria como <camera_id> se viesse depois."""
    from app.api.v1.cameras import routes

    fonte = open(routes.__file__).read()
    lote = fonte.index('"/model-config"')
    por_id = fonte.index('"/<camera_id>/model-config"')
    assert lote < por_id, (
        "a rota em lote precisa ser registrada antes da rota com <camera_id>"
    )


def test_handler_agrupa_por_camera_id():
    from app.api.v1.cameras import model_config_handlers as h

    cam = uuid4()
    dep = {"camera_id": cam, "model_id": uuid4(), "config": {"classes": ["Luvas"]},
           "status": "active", "module_code": "epi"}
    repo = MagicMock()
    repo.list_active_for_tenant.return_value = [dep]

    with patch.object(h, "_get_deployment_repo", return_value=repo), \
         patch.object(h, "get_tenant_id", return_value="tenant-a"), \
         patch.object(h, "request", MagicMock(args={})), \
         patch.object(h, "success", lambda payload: payload):
        resposta = h.list_camera_model_configs.__wrapped__()

    assert str(cam) in resposta["deployments"]
