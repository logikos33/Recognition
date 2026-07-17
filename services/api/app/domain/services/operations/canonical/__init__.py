"""Operações canônicas e de módulo — registradas no OperationTypeRegistry."""
from app.domain.services.operations.canonical.attention_points import AttentionPointsOperation
from app.domain.services.operations.canonical.count_static import CountStaticOperation
from app.domain.services.operations.canonical.counting_line import CountingLineOperation
from app.domain.services.operations.canonical.crowd_zone import CrowdZoneOperation
from app.domain.services.operations.canonical.defect_trigger import DefectTriggerOperation
from app.domain.services.operations.canonical.dwell_zone import DwellZoneOperation
from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
from app.domain.services.operations.canonical.overlap_dynamic import OverlapDynamicOperation
from app.domain.services.operations.canonical.overlap_fixed import OverlapFixedOperation
from app.domain.services.operations.canonical.position import PositionOperation
from app.domain.services.operations.canonical.stage_timer import StageTimerOperation
from app.domain.services.operations.registry import OperationTypeRegistry

OperationTypeRegistry.register(CountStaticOperation)
OperationTypeRegistry.register(CountingLineOperation)
OperationTypeRegistry.register(OverlapDynamicOperation)
OperationTypeRegistry.register(OverlapFixedOperation)
OperationTypeRegistry.register(PositionOperation)
OperationTypeRegistry.register(EpiZoneOperation)
OperationTypeRegistry.register(DefectTriggerOperation)
# Cenário RVB multi-módulo (ADR-0053)
OperationTypeRegistry.register(CrowdZoneOperation)        # task-110: aglomeração
OperationTypeRegistry.register(DwellZoneOperation)        # task-110: permanência (termo neutro)
OperationTypeRegistry.register(AttentionPointsOperation)  # task-109: multi-atributo por ROI
OperationTypeRegistry.register(StageTimerOperation)       # task-109: cronômetro de etapa
