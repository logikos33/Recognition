"""
Recognition — BaseOperation.

Strategy pattern para tipos de operação configuráveis.
Cada operação recebe detecções de frame e retorna um resultado calculado.

Pattern: espelha TowerController em app/api/v1/quality/tower_controller.py.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseOperation(ABC):
    """Interface abstrata para operações de análise de vídeo configuráveis.

    Implementações concretas herdam esta classe e são registradas
    no OperationTypeRegistry via OperationTypeRegistry.register().

    Atributos de classe (definir em cada subclasse):
        type_id:           Identificador único da operação (ex: 'position').
        type_label:        Label legível (ex: 'Posição').
        available_modules: Lista de módulos onde aparece; ['*'] = todos.
        config_schema:     JSON schema para gerar formulário no frontend.
        metric_options:    Opções de métrica disponíveis.
        output_formats:    Formatos de saída suportados.
        description:       Descrição curta para o catálogo.
    """

    type_id: str = ""
    type_label: str = ""
    available_modules: list[str] = ["*"]
    config_schema: dict = {}
    metric_options: list[str] = []
    output_formats: list[str] = ["physical", "conditional", "both"]
    description: str = ""

    def __init__(self, config: dict) -> None:
        """Inicializa operação com config validada.

        Args:
            config: Configuração específica da instância (validada antes).
        """
        self.config = config

    @abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """Valida configuração e retorna lista de erros (vazia = OK).

        Args:
            config: Dicionário de configuração a validar.

        Returns:
            Lista de strings de erro. Vazia se válida.
        """

    @abstractmethod
    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        """Processa detecções de um frame e retorna resultado calculado.

        Args:
            detections: Lista de detecções YOLO do frame atual.
            frame_meta: Metadados do frame (camera_id, timestamp, etc.).
            state:      Estado persistente entre frames para esta operação.

        Returns:
            Dict com keys: result, metric_value, condition_satisfied, state_next.
        """

    def render_form_schema(self) -> dict:
        """Retorna JSON schema para geração de formulário no frontend."""
        return self.config_schema

    @classmethod
    def get_catalog_entry(cls) -> dict:
        """Retorna dicionário para exibição no catálogo de tipos."""
        return {
            "type_id": cls.type_id,
            "type_label": cls.type_label,
            "description": cls.description,
            "available_modules": cls.available_modules,
            "config_schema": cls.config_schema,
            "metric_options": cls.metric_options,
            "output_formats": cls.output_formats,
        }


def _point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray casting — verifica se ponto (x,y) está dentro do polígono normalizado."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside
