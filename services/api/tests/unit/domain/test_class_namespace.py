"""Tests: class_namespace (namespacing module_classes ∪ yolo_classes)."""
from app.domain.services.class_namespace import (
    TENANT_CLASS_ID_OFFSET,
    namespace_tenant_class_id,
)


class TestNamespaceTenantClassId:
    def test_offsets_by_constant(self) -> None:
        assert namespace_tenant_class_id(1) == TENANT_CLASS_ID_OFFSET + 1

    def test_never_collides_with_module_catalog_range(self) -> None:
        """Maior catálogo real hoje é EPI (class_id 0-7) — o namespaced
        precisa ficar bem acima de qualquer índice plausível de módulo."""
        for yolo_id in (1, 2, 42, 9999):
            assert namespace_tenant_class_id(yolo_id) > 1000

    def test_distinct_yolo_ids_stay_distinct(self) -> None:
        assert namespace_tenant_class_id(5) != namespace_tenant_class_id(6)

    def test_accepts_str_castable_id(self) -> None:
        assert namespace_tenant_class_id("7") == TENANT_CLASS_ID_OFFSET + 7
