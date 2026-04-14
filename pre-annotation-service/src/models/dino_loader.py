"""Grounding DINO model — singleton com lazy loading."""
import logging

logger = logging.getLogger(__name__)

# AI_NOTE: Prompts específicos e descritivos melhoram a detecção DINO.
# Usar frases curtas separadas por " . " (sintaxe GroundingDINO).
_PROMPTS = {
    "epi": "person . yellow safety hard hat . high visibility reflective vest . safety gloves . protective safety glasses . person without helmet . person without vest",
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
            import os
            import torch
            from groundingdino.util.inference import load_model
            from src.config import config

            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            # AI_NOTE: Resolver paths — config vem do pacote, checkpoint pode estar em /tmp/epi-models/
            cfg_path = config.DINO_CONFIG
            ckpt_path = config.DINO_CHECKPOINT

            # Tentar resolver config do pacote groundingdino se bare filename
            if not os.path.isfile(cfg_path):
                try:
                    import groundingdino
                    pkg_dir = os.path.dirname(groundingdino.__file__)
                    candidate = os.path.join(pkg_dir, "config", cfg_path)
                    if os.path.isfile(candidate):
                        cfg_path = candidate
                        logger.info("dino_config_resolved: %s", cfg_path)
                except Exception:
                    pass

            # Tentar resolver checkpoint em /tmp/epi-models/
            if not os.path.isfile(ckpt_path):
                candidate = os.path.join("/tmp/epi-models", os.path.basename(ckpt_path))
                if os.path.isfile(candidate):
                    ckpt_path = candidate
                    logger.info("dino_checkpoint_resolved: %s", ckpt_path)

            if not os.path.isfile(ckpt_path):
                logger.warning("dino_checkpoint_not_found: tried %s and /tmp/epi-models/%s",
                               config.DINO_CHECKPOINT, os.path.basename(config.DINO_CHECKPOINT))
                return False

            self.model = load_model(cfg_path, ckpt_path)
            self.model.to(self.device)
            logger.info("dino_loaded: device=%s config=%s checkpoint=%s", self.device, cfg_path, ckpt_path)
            return True
        except Exception as exc:
            logger.warning("dino_load_failed: %s", exc)
            return False

    def predict(self, image, text_prompt: str) -> list:
        """
        Detecta objetos. Retorna [{class, bbox:{cx,cy,w,h}, confidence, source}].
        Retorna lista vazia se modelo não disponível.
        """
        # AI_NOTE: Lazy-reload — retenta load se checkpoint chegou ao disco após prefetch
        if self.model is None:
            if not self.load():
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
