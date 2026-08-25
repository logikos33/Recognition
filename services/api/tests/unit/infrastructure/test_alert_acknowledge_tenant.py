"""Reconhecer alerta é escrita — e escrita sem tenant atravessa o isolamento.

`AlertRepository.acknowledge` fazia `UPDATE alerts SET acknowledged = TRUE
WHERE id = %s`, sem tenant. Qualquer sessão autenticada que soubesse (ou
adivinhasse) o UUID reconhecia alerta de OUTRO tenant. Agravante do caminho:
a lista disparava isso no `onMouseEnter`, sem clique nenhum.
"""
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.alert_repository import AlertRepository


def _repo() -> tuple[AlertRepository, MagicMock]:
    repo = AlertRepository.__new__(AlertRepository)
    mutation = MagicMock(return_value={"id": "a", "acknowledged": True})
    repo._execute_mutation = mutation  # type: ignore[method-assign]
    return repo, mutation


def test_o_update_filtra_por_tenant():
    repo, mutation = _repo()
    alert_id = uuid4()

    repo.acknowledge(alert_id, tenant_id="tenant-a")

    sql, params = mutation.call_args[0]
    assert "tenant_id = %s" in sql, "UPDATE sem tenant_id é escrita cross-tenant"
    assert params == (str(alert_id), "tenant-a")


def test_tenant_e_obrigatorio():
    """Sem valor padrão: um chamador novo não pode esquecer o tenant em silêncio."""
    repo, _ = _repo()
    try:
        repo.acknowledge(uuid4())  # type: ignore[call-arg]
    except TypeError:
        return
    raise AssertionError("acknowledge aceitou chamada sem tenant_id")
