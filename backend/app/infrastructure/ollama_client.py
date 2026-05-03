"""Cliente HTTP para Ollama — geração e embeddings."""
import json
import logging
from collections.abc import Generator
from typing import Any

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str, model: str, embed_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def embed(self, text: str) -> list[float]:
        r = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.embed_model, "prompt": text},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["embedding"]

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        """Gera tokens em streaming. Yield: cada token de texto."""
        with requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": True},
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data: dict[str, Any] = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    def generate(self, prompt: str) -> str:
        """Geração síncrona (sem streaming)."""
        r = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        return r.json().get("response", "")


def get_ollama_client() -> OllamaClient:
    """Cria cliente Ollama a partir das variáveis de ambiente."""
    import os
    return OllamaClient(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.environ.get("OLLAMA_MODEL", "epi-assistant"),
        embed_model=os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    )
