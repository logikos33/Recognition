"""Operações canônicas e de módulo — registradas no OperationTypeRegistry."""
from app.domain.services.operations.canonical.count_static import CountStaticOperation
from app.domain.services.operations.canonical.counting_line import CountingLineOperation
from app.domain.services.operations.canonical.defect_trigger import DefectTriggerOperation
from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
from app.domain.services.operations.canonical.overlap_dynamic import OverlapDynamicOperation
from app.domain.services.operations.canonical.overlap_fixed import OverlapFixedOperation
from app.domain.services.operations.canonical.position import PositionOperation
from app.domain.services.operations.registry import OperationTypeRegistry

OperationTypeRegistry.register(CountStaticOperation)
OperationTypeRegistry.register(OverlapDynamicOperation)
OperationTypeRegistry.register(OverlapFixedOperation)
OperationTypeRegistry.register(PositionOperation)
OperationTypeRegistry.register(EpiZoneOperation)
OperationTypeRegistry.register(DefectTriggerOperation)
OperationTypeRegistry.register(CountingLineOperation)
