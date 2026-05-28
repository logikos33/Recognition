"""Operações canônicas — disponíveis em todos os módulos."""
from app.domain.services.operations.canonical.count_static import CountStaticOperation
from app.domain.services.operations.canonical.overlap_dynamic import OverlapDynamicOperation
from app.domain.services.operations.canonical.overlap_fixed import OverlapFixedOperation
from app.domain.services.operations.canonical.position import PositionOperation
from app.domain.services.operations.registry import OperationTypeRegistry

OperationTypeRegistry.register(CountStaticOperation)
OperationTypeRegistry.register(OverlapDynamicOperation)
OperationTypeRegistry.register(OverlapFixedOperation)
OperationTypeRegistry.register(PositionOperation)
