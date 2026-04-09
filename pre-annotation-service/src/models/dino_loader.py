"""Grounding DINO model — singleton com lazy loading."""
import logging

logger = logging.getLogger(__name__)

_PROMPTS = {
    "epi": "person . helmet . safety vest . gloves . safety glasses . hard hat",
    "fueling": "truck . license plate . fuel nozzle . box . pallet",
}


class DinoModel:
    """Singleton para Grounding DINO."""

    _instance = None
    model = None
    device = "cpu"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> bool:
        """Carrega modelo. Retorna True se OK, False se não disponível."""
        if self.model is not None:
            return True
        try:
            import torch
            from groundingdino.util.inference import load_model
            from src.config import config

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = load_model(config.DINO_CONFIG, config.DINO_CHECKPOINT)
            self.model.to(self.device)
            logger.info("dino_loaded: device=%s", self.device)
            return True
        except Exception as exc:
            logger.warning("dino_load_failed: %s", exc)
            return False

    def predict(self, image, text_prompt: str) -> list:
        """
        Detecta objetos. Retorna [{class, bbox:{cx,cy,w,h}, confidence, source}].
        Retorna lista vazia se modelo não disponível.
        """
        if self.model is None:
            return []
        try:
            from groundingdino.util.inference import predict
            from src.config import config

            boxes, logits, phrases = predict(
                model=self.model,
                image=image,
                caption=text_prompt,
                box_threshold=config.DINO_BOX_THRESHOLD,
                text_threshold=config.DINO_TEXT_THRESHOLD,
                device=self.device,
            )

            results = []
            for box, logit, phrase in zip(boxes, logits, phrases):
                cx, cy, w, h = box.tolist()
                results.append({
                    "class": phrase.strip(),
                    "bbox": {"cx": cx, "cy": cy, "w": w, "h": h},
                    "confidence": float(logit),
                    "source": "dino",
                })
            return results
        except Exception as exc:
            logger.error("dino_predict_failed: %s", exc)
            return []

    @staticmethod
    def get_prompt(module_code: str) -> str:
        return _PROMPTS.get(module_code, _PROMPTS["epi"])


dino_model = DinoModel()
