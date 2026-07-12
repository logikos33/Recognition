"""Tests: TenantClassService (WS-A1 — classes tenant-scoped)."""
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg2.errors
import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.services.tenant_class_service import TenantClassService


class TestListClasses:
    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = TenantClassService(self.repo)

    def test_list_default_module_epi(self) -> None:
        tenant = str(uuid4())
        uid = uuid4()
        self.repo.get_classes_for_tenant.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e"},
        ]
        result = self.service.list_classes(tenant, user_id=uid)
        assert len(result) == 1
        self.repo.get_classes_for_tenant.assert_called_once_with(
            tenant, user_id=uid, module_code="epi"
        )
        self.repo.get_classes_with_counts.assert_not_called()

    def test_list_with_counts_uses_count_query(self) -> None:
        tenant = str(uuid4())
        self.repo.get_classes_with_counts.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e", "annotation_count": 7},
        ]
        result = self.service.list_classes(tenant, include_counts=True)
        assert result[0]["annotation_count"] == 7
        self.repo.get_classes_with_counts.assert_called_once_with(
            tenant, user_id=None, module_code="epi"
        )
        self.repo.get_classes_for_tenant.assert_not_called()

    def test_list_module_normalized(self) -> None:
        tenant = str(uuid4())
        self.repo.get_classes_for_tenant.return_value = []
        self.service.list_classes(tenant, module_code="  FUELING ")
        self.repo.get_classes_for_tenant.assert_called_once_with(
            tenant, user_id=None, module_code="fueling"
        )

    def test_list_empty_module_falls_back_to_epi(self) -> None:
        tenant = str(uuid4())
        self.repo.get_classes_for_tenant.return_value = []
        self.service.list_classes(tenant, module_code="")
        assert (
            self.repo.get_classes_for_tenant.call_args.kwargs["module_code"]
            == "epi"
        )

    def test_list_invalid_module_raises(self) -> None:
        with pytest.raises(ValidationError, match="module"):
            self.service.list_classes(str(uuid4()), module_code="drop table;")


class TestCreateClass:
    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = TenantClassService(self.repo)

    def test_create_passes_tenant_and_module(self) -> None:
        uid = uuid4()
        tenant = str(uuid4())
        self.repo.create_class.return_value = {
            "id": 1, "name": "Capacete", "color": "#22c55e",
        }
        result = self.service.create_class(
            uid, tenant, "  Capacete ", "#22c55e", module_code="fueling"
        )
        assert result["name"] == "Capacete"
        self.repo.create_class.assert_called_once_with(
            uid, "Capacete", "#22c55e", tenant_id=tenant, module_code="fueling"
        )

    def test_create_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="obrigatório"):
            self.service.create_class(uuid4(), str(uuid4()), "   ")

    def test_create_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError, match="100"):
            self.service.create_class(uuid4(), str(uuid4()), "x" * 101)

    def test_create_invalid_color_raises(self) -> None:
        # color VARCHAR(7) no schema — só #RRGGBB
        with pytest.raises(ValidationError, match="RRGGBB"):
            self.service.create_class(uuid4(), str(uuid4()), "Capacete", "azul")

    def test_create_short_hex_color_raises(self) -> None:
        with pytest.raises(ValidationError, match="RRGGBB"):
            self.service.create_class(uuid4(), str(uuid4()), "Capacete", "#fff")

    def test_create_duplicate_name_maps_to_conflict(self) -> None:
        self.repo.create_class.side_effect = psycopg2.errors.UniqueViolation()
        with pytest.raises(ConflictError, match="já existe") as exc_info:
            self.service.create_class(uuid4(), str(uuid4()), "Capacete")
        assert exc_info.value.status_code == 409


class TestUpdateClass:
    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = TenantClassService(self.repo)

    def test_update_rename_success(self) -> None:
        tenant = str(uuid4())
        uid = uuid4()
        self.repo.update_class.return_value = {
            "id": 5, "name": "Colete", "color": "#f59e0b",
        }
        result = self.service.update_class(
            5, tenant, user_id=uid, name=" Colete "
        )
        assert result["name"] == "Colete"
        self.repo.update_class.assert_called_once_with(
            5, tenant, name="Colete", color=None, user_id=uid
        )

    def test_update_color_only(self) -> None:
        tenant = str(uuid4())
        self.repo.update_class.return_value = {"id": 5, "color": "#ff0000"}
        self.service.update_class(5, tenant, color="#ff0000")
        self.repo.update_class.assert_called_once_with(
            5, tenant, name=None, color="#ff0000", user_id=None
        )

    def test_update_no_fields_raises(self) -> None:
        with pytest.raises(ValidationError, match="name e/ou color"):
            self.service.update_class(5, str(uuid4()))
        self.repo.update_class.assert_not_called()

    def test_update_invalid_color_raises(self) -> None:
        with pytest.raises(ValidationError, match="RRGGBB"):
            self.service.update_class(5, str(uuid4()), color="red")

    def test_update_other_tenant_raises_404(self) -> None:
        self.repo.update_class.return_value = None
        with pytest.raises(NotFoundError) as exc_info:
            self.service.update_class(99, str(uuid4()), name="X")
        assert exc_info.value.status_code == 404

    def test_update_duplicate_name_maps_to_conflict(self) -> None:
        self.repo.update_class.side_effect = psycopg2.errors.UniqueViolation()
        with pytest.raises(ConflictError):
            self.service.update_class(5, str(uuid4()), name="Capacete")


class TestDeleteClass:
    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = TenantClassService(self.repo)

    def test_delete_success(self) -> None:
        tenant = str(uuid4())
        uid = uuid4()
        self.repo.get_class_for_tenant.return_value = {"id": 5, "name": "Colete"}
        self.repo.count_annotations_for_class.return_value = 0
        self.repo.delete_class.return_value = 1
        result = self.service.delete_class(5, tenant, user_id=uid)
        assert result["id"] == 5
        self.repo.delete_class.assert_called_once_with(5, tenant, user_id=uid)

    def test_delete_other_tenant_raises_404(self) -> None:
        self.repo.get_class_for_tenant.return_value = None
        with pytest.raises(NotFoundError) as exc_info:
            self.service.delete_class(99, str(uuid4()))
        assert exc_info.value.status_code == 404
        self.repo.delete_class.assert_not_called()

    def test_delete_referenced_raises_409_with_count(self) -> None:
        self.repo.get_class_for_tenant.return_value = {"id": 5, "name": "Colete"}
        self.repo.count_annotations_for_class.return_value = 12
        with pytest.raises(ConflictError, match="12 anotações") as exc_info:
            self.service.delete_class(5, str(uuid4()))
        assert exc_info.value.status_code == 409
        self.repo.delete_class.assert_not_called()

    def test_delete_race_guard_raises_409(self) -> None:
        # count=0 mas guarda NOT EXISTS do SQL não deletou (anotação criada
        # entre a checagem e o DELETE)
        self.repo.get_class_for_tenant.return_value = {"id": 5, "name": "Colete"}
        self.repo.count_annotations_for_class.return_value = 0
        self.repo.delete_class.return_value = 0
        with pytest.raises(ConflictError, match="abortada"):
            self.service.delete_class(5, str(uuid4()))
