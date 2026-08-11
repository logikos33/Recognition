"""
Tests: AnnotationService — get_frame_annotations (pre-annotation fallback),
save_annotations paths e _validate_annotation (item-24).

Complementa test_annotation_service.py com os caminhos não cobertos.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.annotation_service import AnnotationService


class TestAnnotationServiceExtended:

    def setup_method(self):
        self.annotation_repo = MagicMock()
        self.frame_repo = MagicMock()
        self.module_repo = MagicMock()
        self.module_repo.get_classes.return_value = [
            {"module_code": "epi", "class_id": 0, "class_name": "helmet"},
            {"module_code": "epi", "class_id": 1, "class_name": "no_helmet"},
            {"module_code": "epi", "class_id": 2, "class_name": "vest"},
        ]
        self.service = AnnotationService(self.annotation_repo, self.frame_repo, self.module_repo)

    def _frame(self, frame_id=None, filename="frames/u/v/frame_0001.jpg"):
        return {"id": frame_id or uuid4(), "filename": filename, "is_annotated": False}

    # ------------------------------------------------------------------
    # get_frame_annotations — with user_id IDOR check
    # ------------------------------------------------------------------

    def test_get_frame_annotations_user_owns_frame(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = [
            {"id": uuid4(), "class_id": 1, "x_center": 0.5, "y_center": 0.5}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert isinstance(result[0]["id"], str)

    def test_get_frame_annotations_user_not_owner_raises(self):
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_frame_annotations(uuid4(), uuid4())

    def test_get_frame_annotations_no_user_skips_idor_check(self):
        frame_id = uuid4()
        self.annotation_repo.get_by_frame.return_value = [{"id": uuid4(), "class_id": 1}]
        result = self.service.get_frame_annotations(frame_id, user_id=None)
        self.frame_repo.get_by_id_and_user.assert_not_called()
        assert len(result) == 1

    # ------------------------------------------------------------------
    # Contexto de tenant propagado ao ownership check (fix #302 — anotador
    # 404 sob contexto assumido de superadmin). fail-before/pass-after: antes
    # do fix o service chamava get_by_id_and_user com 2 args (sem tenant), e
    # o repo derivava o tenant "de casa" do user — errado sob contexto assumido.
    # ------------------------------------------------------------------

    def test_get_frame_annotations_threads_request_tenant_to_ownership_check(self):
        frame_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.frame_repo.get_pre_annotations.return_value = []

        self.service.get_frame_annotations(frame_id, user_id, tenant_id)

        self.frame_repo.get_by_id_and_user.assert_called_once_with(
            frame_id, user_id, tenant_id
        )

    def test_save_annotations_threads_request_tenant_to_ownership_check(self):
        frame_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.save_batch.return_value = 0

        self.service.save_annotations(frame_id, [], user_id, tenant_id)

        self.frame_repo.get_by_id_and_user.assert_called_once_with(
            frame_id, user_id, tenant_id
        )

    def test_pre_annotate_frame_threads_tenant_to_ownership_check(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.pre_annotate_frame(frame_id, "tenant-abc", user_id, "epi")
        self.frame_repo.get_by_id_and_user.assert_called_once_with(
            frame_id, user_id, "tenant-abc"
        )

    # ------------------------------------------------------------------
    # get_frame_annotations — pre-annotation fallback (AI)
    # ------------------------------------------------------------------

    def test_get_frame_annotations_returns_pre_annotations_when_no_human(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []  # no human annotations
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "helmet", "color": "#0f0"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "helmet", "bbox": [0.5, 0.5, 0.2, 0.2], "confidence": 0.9}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["source"] == "ai"
        assert result[0]["class_name"] == "helmet"
        assert result[0]["class_id"] == 1

    def test_get_frame_annotations_pre_annotation_dict_bbox(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 7, "name": "vest", "color": "#fff"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "vest", "bbox": {"cx": 0.5, "cy": 0.5, "w": 0.1, "h": 0.1}, "confidence": 0.8}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["x_center"] == 0.5
        assert result[0]["class_id"] == 7

    def test_get_frame_annotations_invalid_bbox_is_skipped(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "helmet", "color": "#fff"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "helmet", "bbox": "not-a-bbox", "confidence": 0.9}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert result == []

    def test_get_frame_annotations_no_pre_annotations_returns_empty(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.frame_repo.get_pre_annotations.return_value = []

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert result == []

    def test_get_frame_annotations_class_not_in_map_raises(self):
        """task-077 (ADR-0017): label desconhecido falha alto, NUNCA usa a
        primeira classe disponível nem um id hardcoded — essa era exatamente
        a classe de bug (rótulo errado sem erro visível) que a task corrige."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 99, "name": "known_class", "color": "#fff"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "unknown_label", "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.7}
        ]

        with pytest.raises(ValidationError, match="label desconhecido"):
            self.service.get_frame_annotations(frame_id, user_id)

    # ------------------------------------------------------------------
    # save_annotations
    # ------------------------------------------------------------------

    # _export_yolo_labels does `from app.infrastructure.storage.local_storage import get_storage`
    # inside the function body. Patch at source module to intercept it.
    _STORAGE_PATH = "app.infrastructure.storage.local_storage.get_storage"

    def test_save_annotations_with_user_id(self):
        frame_id = uuid4()
        user_id = uuid4()
        frame = self._frame(frame_id)
        self.frame_repo.get_by_id_and_user.return_value = frame
        self.annotation_repo.save_batch.return_value = 2

        ann = [
            {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
            {"class_id": 2, "class_name": "vest", "module_code": "epi",
             "x_center": 0.3, "y_center": 0.3, "width": 0.1, "height": 0.1},
        ]
        with patch(self._STORAGE_PATH):
            count = self.service.save_annotations(frame_id, ann, user_id)

        assert count == 2
        self.frame_repo.mark_annotated.assert_called_once_with(frame_id)

    def test_save_annotations_without_user_id_uses_get_by_id(self):
        frame_id = uuid4()
        frame = self._frame(frame_id)
        self.frame_repo.get_by_id.return_value = frame
        self.annotation_repo.save_batch.return_value = 1

        ann = [{"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
                "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}]
        with patch(self._STORAGE_PATH):
            self.service.save_annotations(frame_id, ann, user_id=None)

        self.frame_repo.get_by_id.assert_called_once_with(frame_id)

    def test_save_annotations_frame_not_found_raises(self):
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.save_annotations(uuid4(), [], uuid4())

    def test_save_annotations_zero_count_does_not_mark_annotated(self):
        frame_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.save_batch.return_value = 0

        self.service.save_annotations(frame_id, [], uuid4())
        self.frame_repo.mark_annotated.assert_not_called()

    # ------------------------------------------------------------------
    # _validate_annotation
    # ------------------------------------------------------------------

    def test_validate_annotation_missing_class_id_raises(self):
        with pytest.raises(ValidationError, match="class_id"):
            self.service._validate_annotation(
                {"x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
            )

    def test_validate_annotation_coord_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="entre 0 e 1"):
            self.service._validate_annotation(
                {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
                 "x_center": 1.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
            )

    def test_validate_annotation_valid_passes(self):
        self.service._validate_annotation(
            {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
        )  # no exception

    # ------------------------------------------------------------------
    # _export_yolo_labels — best-effort, storage error silenced
    # ------------------------------------------------------------------

    def test_export_yolo_labels_storage_error_is_silenced(self):
        frame = self._frame(filename="frames/u/v/frame_001.jpg")
        ann = [{"class_id": 1, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}]

        with patch(self._STORAGE_PATH) as mock_gs:
            mock_gs.return_value.upload_bytes.side_effect = Exception("R2 error")
            # Should not raise — _export_yolo_labels is best-effort
            self.service._export_yolo_labels(frame, ann)

    # ------------------------------------------------------------------
    # pre_annotate_frame (WS-B4) — backend plugável OFF por padrão
    # ------------------------------------------------------------------

    def test_pre_annotate_frame_raises_not_found_when_not_owned(self):
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.pre_annotate_frame(uuid4(), "tenant-1", uuid4(), "epi")

    def test_pre_annotate_frame_raises_authorization_when_backend_disabled(self):
        from app.core.exceptions import AuthorizationError

        self.frame_repo.get_by_id_and_user.return_value = self._frame()
        with patch(
            "app.domain.services.pre_annotation.factory.get_pre_annotation_backend",
            return_value=None,
        ):
            with pytest.raises(AuthorizationError):
                self.service.pre_annotate_frame(uuid4(), "tenant-1", uuid4(), "epi")

    def test_pre_annotate_frame_delegates_to_backend_when_enabled(self):
        frame_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        mock_backend = MagicMock()
        mock_backend.predict_and_store.return_value = 3
        with patch(
            "app.domain.services.pre_annotation.factory.get_pre_annotation_backend",
            return_value=mock_backend,
        ):
            count = self.service.pre_annotate_frame(frame_id, "tenant-1", uuid4(), "epi")
        assert count == 3
        mock_backend.predict_and_store.assert_called_once_with(str(frame_id), "epi")

    # ------------------------------------------------------------------
    # accept_suggestions (WS-B4)
    # ------------------------------------------------------------------

    def test_accept_suggestions_accepts_all_by_default(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []  # sem anotação humana
        self.frame_repo.get_pre_annotations.return_value = [
            {"bbox": [0.5, 0.5, 0.1, 0.1], "class": "hardhat", "confidence": 0.9},
            {"bbox": [0.3, 0.3, 0.1, 0.1], "class": "no-hardhat", "confidence": 0.8},
        ]
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "hardhat"}, {"id": 2, "name": "no-hardhat"},
        ]
        self.annotation_repo.accept_pre_annotations.return_value = 2

        count = self.service.accept_suggestions(frame_id, user_id)

        assert count == 2
        accepted_arg = self.annotation_repo.accept_pre_annotations.call_args.args[1]
        assert len(accepted_arg) == 2
        self.frame_repo.mark_annotated.assert_called_once_with(frame_id)

    def test_accept_suggestions_filters_by_indices(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.frame_repo.get_pre_annotations.return_value = [
            {"bbox": [0.5, 0.5, 0.1, 0.1], "class": "hardhat", "confidence": 0.9},
            {"bbox": [0.3, 0.3, 0.1, 0.1], "class": "no-hardhat", "confidence": 0.8},
        ]
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "hardhat"}, {"id": 2, "name": "no-hardhat"},
        ]
        self.annotation_repo.accept_pre_annotations.return_value = 1

        self.service.accept_suggestions(frame_id, user_id, indices=[1])

        accepted_arg = self.annotation_repo.accept_pre_annotations.call_args.args[1]
        assert len(accepted_arg) == 1
        assert accepted_arg[0]["class_id"] == 2

    def test_accept_suggestions_no_pending_returns_zero_without_db_call(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.frame_repo.get_pre_annotations.return_value = None

        count = self.service.accept_suggestions(frame_id, user_id)

        assert count == 0
        self.annotation_repo.accept_pre_annotations.assert_not_called()
        self.frame_repo.mark_annotated.assert_not_called()

    def test_accept_suggestions_skips_when_human_already_annotated(self):
        """Se ja tem anotacao humana, get_frame_annotations retorna ela (nao
        as pre_annotations) -- nao ha sugestao 'ai' pendente pra aceitar."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = [
            {"id": uuid4(), "class_id": 1, "x_center": 0.5, "y_center": 0.5}
        ]

        count = self.service.accept_suggestions(frame_id, user_id)

        assert count == 0
        self.annotation_repo.accept_pre_annotations.assert_not_called()

    # ------------------------------------------------------------------
    # review_pre_annotation (migration 111 — fila de aprovação de propostas)
    # ------------------------------------------------------------------

    def test_review_pre_annotation_cross_tenant_raises_not_found(self):
        """FALHA-ANTES/PASSA-DEPOIS (C-01): frame de outro tenant/inexistente
        → get_by_id_and_user retorna None → 404, nunca vazamento de
        existência (nunca 403)."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = None

        with pytest.raises(NotFoundError):
            self.service.review_pre_annotation(
                frame_id, user_id, "rejected", tenant_id="tenant-a"
            )
        self.frame_repo.mark_pre_annotation_review.assert_not_called()

    def test_review_pre_annotation_invalid_status_raises_validation_error(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)

        with pytest.raises(ValidationError):
            self.service.review_pre_annotation(
                frame_id, user_id, "maybe", tenant_id="tenant-a"
            )
        self.frame_repo.mark_pre_annotation_review.assert_not_called()

    def test_review_pre_annotation_rejected_stamps_status(self):
        """Rejeitar: nunca chama accept_pre_annotations/mark_annotated —
        só estampa o status, a proposta some da fila de pendentes sem
        virar caixa."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.frame_repo.mark_pre_annotation_review.return_value = {
            "id": frame_id,
            "pre_annotation_review_status": "rejected",
            "pre_annotation_reviewed_at": None,
        }

        result = self.service.review_pre_annotation(
            frame_id, user_id, "rejected", tenant_id="tenant-a"
        )

        assert result["status"] == "rejected"
        assert result["frame_id"] == str(frame_id)
        self.frame_repo.mark_pre_annotation_review.assert_called_once_with(
            frame_id, "rejected", user_id, "tenant-a"
        )
        self.annotation_repo.accept_pre_annotations.assert_not_called()
        self.frame_repo.mark_annotated.assert_not_called()

    def test_review_pre_annotation_accepted_stamps_status(self):
        """Aceitar-com-edição: o estúdio já salvou as caixas via
        /annotations antes de chamar isto — aqui só fecha o registro de
        revisão (não grava caixa nenhuma, ao contrário de accept-suggestions)."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.frame_repo.mark_pre_annotation_review.return_value = {
            "id": frame_id,
            "pre_annotation_review_status": "accepted",
            "pre_annotation_reviewed_at": None,
        }

        result = self.service.review_pre_annotation(
            frame_id, user_id, "accepted", tenant_id="tenant-a"
        )

        assert result["status"] == "accepted"
        self.frame_repo.mark_pre_annotation_review.assert_called_once_with(
            frame_id, "accepted", user_id, "tenant-a"
        )

    def test_review_pre_annotation_is_idempotent(self):
        """Chamar de novo (usuário aperta a tecla duas vezes) só reescreve
        os campos — não levanta erro, não muda o resultado."""
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.frame_repo.mark_pre_annotation_review.return_value = {
            "id": frame_id,
            "pre_annotation_review_status": "rejected",
            "pre_annotation_reviewed_at": None,
        }

        first = self.service.review_pre_annotation(
            frame_id, user_id, "rejected", tenant_id="tenant-a"
        )
        second = self.service.review_pre_annotation(
            frame_id, user_id, "rejected", tenant_id="tenant-a"
        )

        assert first == second
        assert self.frame_repo.mark_pre_annotation_review.call_count == 2
