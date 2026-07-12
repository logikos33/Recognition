"""
Recognition — Tests: TrainingRepository (dono/origem — migration 090, WS5).

Cobre:
  1. create_model grava created_by (default = user_id), origin e tenant_id
  2. create_model respeita created_by/origin explícitos
  3. get_models_by_user usa SELECT explícito com JOIN em users
     (owner_name/owner_email) — sem SELECT *

Isolamento: sem SQL real — o método _execute*/mutation é mockado.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)


def _make_repo() -> TrainingRepository:
    return TrainingRepository(MagicMock())


class TestCreateModelOwnership:
    """INSERT em trained_models inclui created_by/origin/tenant_id."""

    def test_defaults_created_by_to_user_id_and_origin_unknown(self):
        repo = _make_repo()
        user_id = str(uuid4())
        with patch.object(
            repo, "_execute_mutation", return_value={"id": uuid4()}
        ) as mock_mut:
            repo.create_model({
                "user_id": user_id,
                "job_id": None,
                "name": "m1",
                "model_path": "models/x/best.pt",
            })

        query, params = mock_mut.call_args[0]
        assert "created_by" in query
        assert "origin" in query
        assert "tenant_id" in query
        # created_by default = user_id; origin default = 'unknown'
        assert params[7] == user_id
        assert params[8] == "unknown"
        # tenant_id explícito ausente → slot do COALESCE é None e o
        # subselect de tenant usa o user_id (posição 10 desde a 098)
        assert params[9] is None
        assert params[10] == user_id
        assert "SELECT tenant_id FROM users WHERE id = %s" in query

    def test_explicit_created_by_and_origin_are_used(self):
        repo = _make_repo()
        user_id = str(uuid4())
        creator = str(uuid4())
        with patch.object(
            repo, "_execute_mutation", return_value={"id": uuid4()}
        ) as mock_mut:
            repo.create_model({
                "user_id": user_id,
                "name": "m2",
                "model_path": "models/y/best.pt",
                "created_by": creator,
                "origin": "vast_ai",
            })

        _, params = mock_mut.call_args[0]
        assert params[7] == creator
        assert params[8] == "vast_ai"


class TestGetModelsByUserOwnerJoin:
    """SELECT explícito com JOIN users — retorna owner_name/owner_email."""

    def test_query_selects_owner_fields_without_select_star(self):
        repo = _make_repo()
        user_id = uuid4()
        with patch.object(repo, "_execute", return_value=[]) as mock_exec:
            repo.get_models_by_user(user_id)

        query, params = mock_exec.call_args[0]
        assert "SELECT *" not in query
        assert "owner_name" in query
        assert "owner_email" in query
        assert "COALESCE(tm.created_by, tm.user_id)" in query
        # Colunas da 003 + 052 + 090 explícitas
        for col in (
            "tm.scenario_config", "tm.created_by", "tm.origin", "tm.tenant_id",
            "tm.map50", "tm.is_active",
        ):
            assert col in query, f"coluna {col} ausente no SELECT explícito"
        assert params == (str(user_id),)
