"""
OCR Service — leitura de números de peça via OCR ou código de barras.

Dois métodos com fallback automático:
  1. PaddleOCR (texto impresso)
  2. pyzbar (código de barras / QR code)

Ambas as dependências são lazy-importadas para não quebrar o API server
que não as tem instaladas (requerem torch e libzbar).

Configuração via variáveis de ambiente:
  QUALITY_OCR_PATTERN        : regex para extrair número da peça (default: 4-6 dígitos)
  QUALITY_OCR_MIN_CONFIDENCE : confiança mínima do OCR (default: 0.85)
"""
import logging
import os
import re

logger = logging.getLogger(__name__)

# Padrão regex configurável para extrair o número da peça do texto reconhecido
OCR_PATTERN = re.compile(os.environ.get("QUALITY_OCR_PATTERN", r"\d{4,6}"))

# Confiança mínima aceita do PaddleOCR (0.0 a 1.0)
OCR_MIN_CONFIDENCE = float(os.environ.get("QUALITY_OCR_MIN_CONFIDENCE", "0.85"))


class OcrService:
    """Lê número de peça via OCR (PaddleOCR) com fallback para código de barras (pyzbar).

    Lazy-importa dependências pesadas para não quebrar o API server que não as tem instaladas.
    """

    def read_piece_number(self, frame_bytes: bytes) -> dict:
        """Tenta ler número da peça no frame fornecido.

        Tenta PaddleOCR primeiro; se falhar ou confiança insuficiente,
        tenta leitura de código de barras via pyzbar.

        Args:
            frame_bytes: Frame JPEG/PNG como bytes brutos.

        Returns:
            Dict com:
              - piece_number (str | None): número extraído ou None
              - confidence (float): confiança da leitura (0.0 a 1.0)
              - method (str | None): "ocr", "barcode" ou None
        """
        # Tenta PaddleOCR primeiro
        result = self._try_paddle_ocr(frame_bytes)
        if result and result["confidence"] >= OCR_MIN_CONFIDENCE:
            return result

        # Fallback: código de barras via pyzbar
        result = self._try_pyzbar(frame_bytes)
        if result:
            return result

        return {"piece_number": None, "confidence": 0.0, "method": None}

    def _try_paddle_ocr(self, frame_bytes: bytes) -> dict | None:
        """Tenta leitura via PaddleOCR.

        Args:
            frame_bytes: Bytes brutos do frame.

        Returns:
            Dict com piece_number/confidence/method se encontrado,
            ou None se PaddleOCR não disponível ou nada detectado.
        """
        try:
            import cv2
            import numpy as np
            from paddleocr import PaddleOCR  # lazy — não instalado na API
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            result = ocr.ocr(img, cls=True)
            if not result or not result[0]:
                return None
            # Filtra por padrão configurável
            for line in result[0]:
                text, confidence = line[1]
                match = OCR_PATTERN.search(text)
                if match:
                    return {
                        "piece_number": match.group(),
                        "confidence": float(confidence),
                        "method": "ocr",
                    }
            return None
        except ImportError:
            logger.debug("paddleocr_not_available")
            return None
        except Exception as exc:
            logger.error("paddle_ocr_error: %s", exc)
            return None

    def _try_pyzbar(self, frame_bytes: bytes) -> dict | None:
        """Tenta leitura de código de barras / QR code via pyzbar.

        Args:
            frame_bytes: Bytes brutos do frame.

        Returns:
            Dict com piece_number/confidence/method se encontrado,
            ou None se pyzbar não disponível ou nenhum código detectado.
        """
        try:
            import cv2
            import numpy as np
            from pyzbar import pyzbar  # lazy
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            barcodes = pyzbar.decode(img)
            for bc in barcodes:
                text = bc.data.decode("utf-8")
                match = OCR_PATTERN.search(text)
                if match:
                    return {
                        "piece_number": match.group(),
                        "confidence": 1.0,  # código de barras tem confiança total
                        "method": "barcode",
                    }
            return None
        except ImportError:
            logger.debug("pyzbar_not_available")
            return None
        except Exception as exc:
            logger.error("pyzbar_error: %s", exc)
            return None


# Instância singleton — criada na primeira chamada a get_ocr_service()
_ocr_service: OcrService | None = None


def get_ocr_service() -> OcrService:
    """Retorna instância singleton do OcrService.

    Returns:
        OcrService: instância compartilhada do serviço.
    """
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OcrService()
    return _ocr_service
