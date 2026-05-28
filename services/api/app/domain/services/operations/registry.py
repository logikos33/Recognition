"""
Recognition — OperationTypeRegistry.

Singleton que mantém o mapeamento type_id → classe de operação.
Operações são registradas via OperationTypeRegistry.register() no import do módulo.
"""
import logging

from app.domain.services.operations.base import BaseOperation

logger = logging.getLogger(__name__)


class OperationTypeRegistry:
    """Registro singleton de tipos de operação disponíveis.

    Uso:
        OperationTypeRegistry.register(PositionOperation)
        types = OperationTypeRegistry.get_for_module('ppe')
    """

    _types: dict[str, type[BaseOperation]] = {}

    @classmethod
    def register(cls, operation_class: type[BaseOperation]) -> None:
        """Registra um tipo de operação pelo seu type_id.

        Args:
            operation_class: Subclasse concreta de BaseOperation.
        """
        cls._types[operation_class.type_id] = operation_class
        logger.debug("operation_type_registered: %s", operation_class.type_id)

    @classmethod
    def get(cls, type_id: str) -> type[BaseOperation] | None:
        """Retorna classe de operação pelo type_id ou None se não encontrada."""
        return cls._types.get(type_id)

    @classmethod
    def get_for_module(cls, module_id: str) -> list[type[BaseOperation]]:
        """Retorna todos os tipos disponíveis para o módulo informado.

        Inclui tipos com available_modules == ['*'] (canônicos/universais).

        Args:
            module_id: Código do módulo (ex: 'ppe', 'quality').
        """
        return [
            op for op in cls._types.values()
            if "*" in op.available_modules or module_id in op.available_modules
        ]

    @classmethod
    def list_all(cls) -> list[type[BaseOperation]]:
        """Retorna todos os tipos registrados."""
        return list(cls._types.values())

    @classmethod
    def to_catalog(cls, module_id: str) -> list[dict]:
        """Retorna lista de dicts do catálogo para um módulo.

        Args:
            module_id: Código do módulo.
        """
        return [op.get_catalog_entry() for op in cls.get_for_module(module_id)]
