"""
Photo Service — gera 3 tipos de foto para o quality gate.

Tipos de foto:
  1. photo_analysis : frame com bounding boxes YOLO sobrepostos (evidência NOK, para tablet)
  2. photo_raw      : frame original sem overlay (evidência interna)
  3. photo_quality  : foto HD padronizada para o cliente (via Wiser):
                        - Sem bounding boxes
                        - Watermark sutil no rodapé: {peça} | OP {ordem} | {timestamp}
                        - JPEG qualidade 95%

Armazenamento:
  - Salva localmente em QUALITY_PHOTOS_DIR/{type}/ (default: /tmp/quality_photos)
  - Backup no R2 se disponível (não falha se R2 indisponível)

Retorno de cada método: (local_path: str, r2_key: str)
  - Se cv2 indisponível: ("", "")
"""
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Diretório base para fotos de qualidade — configurável por variável de ambiente
PHOTOS_DIR = Path(os.environ.get("QUALITY_PHOTOS_DIR", "/tmp/quality_photos"))  # noqa: S108


class PhotoService:
    """Gera e armazena fotos de inspeção de qualidade."""

    def save_analysis_photo(
        self,
        frame_bytes: bytes,
        detections: list,
        camera_id: str,
    ) -> tuple[str, str]:
        """Salva frame com bounding boxes YOLO sobrepostos.

        Cor dos boxes: vermelho para defeitos, verde para OK.

        Args:
            frame_bytes: Bytes brutos do frame (JPEG/PNG).
            detections: Lista de dicts de detecção com campos:
                          bbox (x1,y1,x2,y2), class, confidence, is_defect.
            camera_id: UUID da câmera (usado no nome do arquivo).

        Returns:
            Tupla (local_path, r2_key). Ambos vazios em caso de erro.
        """
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Desenha bounding boxes com cor por tipo (vermelho=defeito, verde=ok)
            for det in detections:
                x1, y1, x2, y2 = det.get("bbox", [0, 0, 0, 0])
                label = det.get("class", "")
                conf = det.get("confidence", 0)
                color = (0, 0, 255) if det.get("is_defect") else (0, 255, 0)
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(
                    img,
                    f"{label} {conf:.2f}",
                    (int(x1), int(y1) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

            return self._save_and_upload(img, camera_id, "analysis")
        except Exception as exc:
            logger.error("photo_analysis_error: %s", exc)
            return "", ""

    def save_raw_photo(self, frame_bytes: bytes, camera_id: str) -> tuple[str, str]:
        """Salva frame original sem modificações (evidência interna).

        Args:
            frame_bytes: Bytes brutos do frame (JPEG/PNG).
            camera_id: UUID da câmera.

        Returns:
            Tupla (local_path, r2_key). Ambos vazios em caso de erro.
        """
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return self._save_and_upload(img, camera_id, "raw")
        except Exception as exc:
            logger.error("photo_raw_error: %s", exc)
            return "", ""

    def save_quality_photo(
        self,
        frame_bytes: bytes,
        camera_id: str,
        piece_number: str,
        work_order: str = "",
    ) -> tuple[str, str]:
        """Salva foto de qualidade HD para exportação ao cliente (Wiser).

        Características:
          - JPEG qualidade 95%
          - Watermark no rodapé: "Peça {num} | OP {ordem} | {timestamp}"
          - Sem bounding boxes

        Args:
            frame_bytes: Bytes brutos do frame (JPEG/PNG).
            camera_id: UUID da câmera.
            piece_number: Número da peça para o watermark.
            work_order: Ordem de produção para o watermark (opcional).

        Returns:
            Tupla (local_path, r2_key). Ambos vazios em caso de erro.
        """
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Aplica watermark sutil no rodapé com fundo preto semitransparente
            ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            watermark = f"Peça {piece_number} | OP {work_order} | {ts}"
            h, w = img.shape[:2]
            cv2.rectangle(img, (0, h - 30), (w, h), (0, 0, 0), -1)
            cv2.putText(
                img,
                watermark,
                (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            return self._save_and_upload(img, camera_id, "quality", jpeg_quality=95)
        except Exception as exc:
            logger.error("photo_quality_error: %s", exc)
            return "", ""

    def _save_and_upload(
        self,
        img,
        camera_id: str,
        photo_type: str,
        jpeg_quality: int = 85,
    ) -> tuple[str, str]:
        """Salva imagem JPEG localmente e faz upload para R2.

        Estrutura de diretórios: PHOTOS_DIR/{photo_type}/{filename}.jpg
        Estrutura R2: quality-photos/{photo_type}/{camera_id}/{filename}.jpg

        Args:
            img: Array numpy da imagem (cv2 format).
            camera_id: UUID da câmera (primeiros 8 chars usados no filename).
            photo_type: Tipo de foto ("analysis", "raw" ou "quality").
            jpeg_quality: Qualidade JPEG de 0 a 100 (default: 85).

        Returns:
            Tupla (local_path, r2_key). r2_key será "" se upload falhar.
        """
        import cv2

        ts = int(time.time())
        filename = f"{photo_type}_{camera_id[:8]}_{ts}.jpg"
        local_dir = PHOTOS_DIR / photo_type
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = str(local_dir / filename)

        # Salva localmente com qualidade configurável
        cv2.imwrite(local_path, img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

        # Upload para R2 (opcional — não falha se R2 indisponível)
        r2_key = f"quality-photos/{photo_type}/{camera_id}/{filename}"
        try:
            from app.infrastructure.storage.r2_storage import R2Storage
            storage = R2Storage.get_instance()
            if storage:
                with open(local_path, "rb") as f:
                    storage.upload_file(r2_key, f.read(), content_type="image/jpeg")
        except Exception as exc:
            logger.warning("photo_r2_upload_skipped: %s", exc)
            r2_key = ""

        return local_path, r2_key


# Instância singleton — criada na primeira chamada a get_photo_service()
_photo_service: PhotoService | None = None


def get_photo_service() -> PhotoService:
    """Retorna instância singleton do PhotoService.

    Returns:
        PhotoService: instância compartilhada do serviço.
    """
    global _photo_service
    if _photo_service is None:
        _photo_service = PhotoService()
    return _photo_service
