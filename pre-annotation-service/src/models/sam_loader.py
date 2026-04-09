"""SAM (Segment Anything Model) — singleton com lazy loading."""
import logging

import numpy as np

logger = logging.getLogger(__name__)


class SamModel:
    """Singleton para SAM ViT-B."""

    _instance = None
    predictor = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> bool:
        """Carrega modelo. Retorna True se OK, False se não disponível."""
        if self.predictor is not None:
            return True
        try:
            import torch
            from segment_anything import SamPredictor, sam_model_registry
            from src.config import config

            device = "cuda" if torch.cuda.is_available() else "cpu"
            sam = sam_model_registry["vit_b"](checkpoint=config.SAM_CHECKPOINT)
            sam.to(device)
            self.predictor = SamPredictor(sam)
            logger.info("sam_loaded: device=%s", device)
            return True
        except Exception as exc:
            logger.warning("sam_load_failed: %s", exc)
            return False

    def refine_box(self, image_array: np.ndarray, bbox: dict) -> dict:
        """
        Refina bbox com máscara SAM.
        Retorna bbox original se SAM não disponível ou falhar.
        """
        if self.predictor is None:
            return bbox
        try:
            self.predictor.set_image(image_array)

            h, w = image_array.shape[:2]
            cx, cy, bw, bh = bbox["cx"], bbox["cy"], bbox["w"], bbox["h"]
            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)

            input_box = np.array([x1, y1, x2, y2])
            masks, _, _ = self.predictor.predict(box=input_box, multimask_output=False)

            if not len(masks):
                return bbox

            mask = masks[0]
            y_idx, x_idx = np.where(mask)
            if not len(x_idx):
                return bbox

            new_x1, new_x2 = x_idx.min(), x_idx.max()
            new_y1, new_y2 = y_idx.min(), y_idx.max()

            return {
                "cx": float((new_x1 + new_x2) / 2 / w),
                "cy": float((new_y1 + new_y2) / 2 / h),
                "w": float((new_x2 - new_x1) / w),
                "h": float((new_y2 - new_y1) / h),
            }
        except Exception as exc:
            logger.error("sam_refine_failed: %s", exc)
            return bbox


sam_model = SamModel()
