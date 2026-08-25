"""
Detector — interface abstrata.

Todos os backends (YOLOX ONNX, RF-DETR ONNX, …) implementam esta classe.
O contrato de saída é idêntico ao que `inference_loop` publicava com ultralytics:
  [{"class": str, "confidence": float, "bbox": [x, y, w, h], "track_id": None}]
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class Detector(ABC):
    """Interface de inferência para detecção de objetos."""

    @abstractmethod
    def predict(self, frame: "np.ndarray") -> list[dict]:
        """
        Roda inferência num frame BGR (HxWxC uint8).

        Retorna lista de detecções:
          [{"class": str, "confidence": float, "bbox": [x, y, w, h], "track_id": None}]

        "bbox" está em pixels do frame original (antes de qualquer resize).
        "track_id" sempre None aqui; DeepSORT atribui o id depois.
        """

    @property
    def is_ready(self) -> bool:
        """True quando o modelo está carregado e pronto para inferência."""
        return True

    #: Erro da ÚLTIMA chamada a `predict`, ou None se ela correu bem.
    #:
    #: Existe porque `predict` devolve `[]` tanto quando não viu nada quanto
    #: quando a inferência explodiu — e num produto de segurança essas duas
    #: coisas não podem ser a mesma. O laço de inferência publicava
    #: `has_violation: false` nos dois casos, e a grade ao vivo lia isso como
    #: "tudo certo nesta câmera".
    #:
    #: Quem chama `predict` deve consultar isto DEPOIS e tratar
    #: `ultimo_erro is not None` como "não sei", nunca como "nada encontrado".
    ultimo_erro: str | None = None

    #: Já avisamos sobre dicionário incompatível? (avisa uma vez, não por frame)
    _dicionario_conferido: bool = False

    def _confere_dicionario(self, classes_do_modelo: int) -> None:
        """Denuncia dicionário de classe incompatível com o modelo carregado.

        O ONNX devolve um ÍNDICE; `class_names` é quem o traduz. Quando as duas
        coisas vêm de lugares diferentes, elas divergem em silêncio: a
        geometria continua certa e o rótulo passa a ser de outro domínio.

        Foi o que aconteceu no #542 — o caminho servido não passava
        `class_names`, o detector caía em COCO, e um modelo de EPI chamava
        "Sem protetor de ouvido" de "truck" em 61 de 61 detecções. Nada
        reclamou porque um dicionário maior "cabe": o índice 8 existe nos dois,
        só significa outra coisa.

        A contagem de saídas do modelo é a única testemunha disponível aqui, e
        ela basta para o caso que importa. Aviso, não exceção: derrubar a
        inferência de 28 câmeras por um dicionário suspeito seria pior que o
        defeito. Uma vez por detector — isto roda a cada frame.
        """
        if self._dicionario_conferido:
            return
        self._dicionario_conferido = True

        n = len(getattr(self, "_class_names", ()) or ())
        if n and classes_do_modelo and classes_do_modelo != n:
            logger.warning(
                "detector_dicionario_incompativel: modelo emite %d classes mas o "
                "dicionário tem %d — os rótulos vão sair de outro domínio "
                "(primeiros: %s). Ver #542.",
                classes_do_modelo, n,
                list(getattr(self, "_class_names", ()))[:4],
            )
