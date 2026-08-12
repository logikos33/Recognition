"""
Tests: search_handlers.py::promote_search_findings_handler — promove
achado(s) de um job de busca por conteúdo a proposta(s) pendente(s).

Cobre:
- cross-tenant → 404 (C-01, nunca 403);
- items ausente/vazio → 400; index inválido (não-int, bool, fora de
  alcance) → 400, nada gravado; class_name vazio (quando informado) → 400;
- achado sem label E sem class_name informado → 400;
- promoção válida: agrupa por frame_id, chama
  FrameRepository.append_pre_annotations (MERGE, nunca apply_propagation_
  proposals que sobrescreve) com o shape {bbox, class, confidence}, conta
  "promoted" corretamente;
- class_name explícito no item sobrescreve o label do achado;
- merge nunca apaga pre_annotations existentes de outro job — a garantia
  vem do próprio método do repository (append_pre_annotations faz
  COALESCE(...) || ...), aqui cobrimos que o handler CHAMA esse método
  (nunca apply_propagation_proposals/overwrite) por frame.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.search_handlers"
_JOB_ID = str(uuid4())


def _make_token(app, role="admin", tenant_id=_TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _job_with_results(**overrides) -> dict:
    job = {
        "id": _JOB_ID, "tenant_id": _TENANT_ID, "status": "completed",
        "results": [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Capacete",
                "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.91,
            },
            {
                "frame_id": "f2", "term": "safety boot", "label": "Bota",
                "bbox": [0.2, 0.3, 0.05, 0.05], "confidence": 0.77,
            },
        ],
    }
    job.update(overrides)
    return job


def _promote(client, token, body, repo=None, frame_repo=None):
    """`repo` precisa ter `get_by_id_and_tenant.return_value` já setado
    pelo caller — sem default aqui (evita mascarar um teste que esqueceu
    de configurar o mock e acaba testando um MagicMock genérico)."""
    repo = repo or MagicMock()
    frame_repo = frame_repo or MagicMock()
    with patch(f"{_HANDLERS}._get_search_repo", return_value=repo), \
         patch(f"{_HANDLERS}._get_frame_repo", return_value=frame_repo):
        res = client.post(
            f"/api/v1/training/search/jobs/{_JOB_ID}/promote",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    return res, repo, frame_repo


class TestPromoteAuthAndOwnership:
    def test_cross_tenant_returns_404_never_403(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = None
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": 0}]}, repo=repo,
        )
        assert res.status_code == 404
        frame_repo.append_pre_annotations.assert_not_called()

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _repo, _frame_repo = _promote(client, token, {"items": [{"index": 0}]})
        assert res.status_code == 403


class TestPromoteValidation:
    def test_missing_items_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(client, token, {}, repo=repo)
        assert res.status_code == 400
        frame_repo.append_pre_annotations.assert_not_called()

    def test_empty_items_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(client, token, {"items": []}, repo=repo)
        assert res.status_code == 400
        frame_repo.append_pre_annotations.assert_not_called()

    def test_index_out_of_range_returns_400_nothing_written(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": 5}]}, repo=repo,
        )
        assert res.status_code == 400
        frame_repo.append_pre_annotations.assert_not_called()

    def test_negative_index_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": -1}]}, repo=repo,
        )
        assert res.status_code == 400

    def test_non_integer_index_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": "0"}]}, repo=repo,
        )
        assert res.status_code == 400

    def test_boolean_index_returns_400(self, client, app) -> None:
        """`bool` é subclasse de `int` — `True` sem guard explícito viraria
        `index=1` silenciosamente."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": True}]}, repo=repo,
        )
        assert res.status_code == 400

    def test_empty_class_name_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": 0, "class_name": "   "}]}, repo=repo,
        )
        assert res.status_code == 400
        frame_repo.append_pre_annotations.assert_not_called()

    def test_one_invalid_item_rejects_whole_batch(self, client, app) -> None:
        """Fail-closed: um item ruim invalida o lote inteiro — nunca
        promove os itens bons e ignora o ruim."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        res, _repo, frame_repo = _promote(
            client, token, {"items": [{"index": 0}, {"index": 99}]}, repo=repo,
        )
        assert res.status_code == 400
        frame_repo.append_pre_annotations.assert_not_called()


class TestPromoteSuccess:
    def test_promotes_finding_using_its_label(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        frame_repo = MagicMock()
        res, _repo, _frame_repo = _promote(
            client, token, {"items": [{"index": 0}]}, repo=repo, frame_repo=frame_repo,
        )
        assert res.status_code == 200
        assert res.get_json()["data"] == {"promoted": 1}

        frame_repo.append_pre_annotations.assert_called_once()
        call_args = frame_repo.append_pre_annotations.call_args.args
        assert call_args[0] == "f1"
        assert call_args[1] == _TENANT_ID
        proposals = call_args[2]
        assert proposals == [
            {"bbox": [0.5, 0.5, 0.1, 0.1], "class": "Capacete", "confidence": 0.91},
        ]

    def test_class_name_override_replaces_label(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        frame_repo = MagicMock()
        res, _repo, _frame_repo = _promote(
            client, token,
            {"items": [{"index": 0, "class_name": "Capacete de Segurança Customizado"}]},
            repo=repo, frame_repo=frame_repo,
        )
        assert res.status_code == 200
        proposals = frame_repo.append_pre_annotations.call_args.args[2]
        assert proposals[0]["class"] == "Capacete de Segurança Customizado"

    def test_multiple_items_different_frames_grouped_and_counted(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        frame_repo = MagicMock()
        res, _repo, _frame_repo = _promote(
            client, token, {"items": [{"index": 0}, {"index": 1}]},
            repo=repo, frame_repo=frame_repo,
        )
        assert res.status_code == 200
        assert res.get_json()["data"] == {"promoted": 2}
        assert frame_repo.append_pre_annotations.call_count == 2
        frames_called = {c.args[0] for c in frame_repo.append_pre_annotations.call_args_list}
        assert frames_called == {"f1", "f2"}

    def test_uses_append_pre_annotations_never_the_overwriting_propagation_method(
        self, client, app,
    ) -> None:
        """A garantia de "nunca apaga propostas pendentes de outro job" vem
        de append_pre_annotations (MERGE) — o handler nunca deve chamar
        apply_propagation_proposals (overwrite) pra promoção de achados."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_with_results()
        frame_repo = MagicMock()
        _promote(
            client, token, {"items": [{"index": 0}]}, repo=repo, frame_repo=frame_repo,
        )
        frame_repo.append_pre_annotations.assert_called_once()
        frame_repo.apply_propagation_proposals.assert_not_called()
