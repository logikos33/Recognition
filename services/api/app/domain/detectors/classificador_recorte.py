"""Classificador de recorte — caminho 2 da ADR-0067, no lado SERVIDO.

Pessoa (âncora) → recorte → veredito `{com | sem | nao_visivel}` com confiança.

═══ O QUE ESTE MÓDULO RECUSA FAZER ═══

**Uma classe só vira violação se PASSOU a régua.** O artefato carrega a própria
`regua.json`, e uma família cuja classe não passou simplesmente não emite
veredito de violação — o veredito sai como `nao_visivel` (abstenção). Não é
configuração que alguém possa esquecer de ligar: a medida viaja com o modelo.

Régua medida em 2026-08-25, campo virgem, verdade 100% humana, DEPOIS de
remover quase-duplicatas:

    luvas/sem     96%  (n=27, base 78%, ganho +19%)
    mascara/sem  100%  (n=16, base 51%, ganho +49%)
    oculos/com    91%  (n=11, base 54%, ganho +37%)
    oculos/sem    90%  (n=10, base 46%, ganho +44%)

Para comparação, o DETECTOR no mesmo campo: `Sem Luvas` 25% (n=4),
`Sem mascara` 0% (n=6).

═══ ABSTENÇÃO ═══

`nao_visivel` é abstenção, JAMAIS violação (ADR-0067). Sai em três situações,
todas registradas no resultado:

  · confiança abaixo do limiar da família;
  · a classe prevista não passou a régua;
  · a família não tem modelo treinado.

⚠️ **Limitação declarada do v1:** a abstenção vem da CONFIANÇA, não de uma
classe aprendida. A aba Classificar não grava nada para "não visível", então o
acervo não tem exemplo rotulado assim. Uma pessoa de costas produz confiança
baixa e cai na abstenção por esse caminho — o que funciona, mas por acidente,
não por ter aprendido.

═══ LICENÇA ═══

DINOv2 ViT-S/14 — Apache 2.0, sha256 pinado em `docs/WEIGHTS_LICENSES.md`,
verificado fail-closed. Cabeça linear treinada por nós. Zero AGPL.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

PESO_URL = (
    "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth"
)
PESO_SHA256 = "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9"

#: Onde as cabeças e a régua vivem no R2, por tenant.
PREFIXO_R2 = "models/{tenant}/classificador-recorte/{versao}"

#: Limiar de confiança por família. Abaixo disto = abstenção.
#: 0,90 é o limiar em que a régua foi medida — usar outro invalidaria a medida.
LIMIAR_PADRAO = 0.90

_cache: dict[str, Any] = {}
_trava = threading.Lock()


def _cache_dir() -> str:
    d = os.environ.get("MODEL_CACHE_DIR", "/tmp/models")
    os.makedirs(d, exist_ok=True)
    return d


#: Cópia do peso no NOSSO storage. Runtime não deve depender de
#: `dl.fbaipublicfiles.com` estar de pé: um site de terceiro fora do ar viraria
#: "classificador não carregou" no meio de um turno. A URL oficial fica como
#: último recurso e para reprovisionar.
PESO_R2 = "models/pretrained/dinov2_vits14_pretrain.pth"


def _confere(caminho: str) -> bool:
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest() == PESO_SHA256


def _baixa_backbone() -> str:
    """Obtém e VERIFICA o DINOv2. Peso que não bate o hash não carrega.

    Ordem: cache local → R2 (nosso) → URL oficial da Meta. O sha256 é conferido
    em TODAS as três — a origem muda, a garantia não.
    """
    destino = os.path.join(_cache_dir(), "dinov2_vits14.pth")
    if os.path.exists(destino):
        if _confere(destino):
            return destino
        logger.warning("dinov2_hash_divergente_no_cache: rebaixando")
        os.unlink(destino)

    try:
        from app.infrastructure.storage.local_storage import (  # noqa: PLC0415
            get_storage,
        )

        with open(destino, "wb") as f:
            f.write(get_storage(None).download_bytes(PESO_R2))
        if _confere(destino):
            logger.info("dinov2_do_r2: %s", PESO_R2)
            return destino
        logger.warning("dinov2_do_r2_com_hash_errado: caindo para a URL oficial")
        os.unlink(destino)
    except Exception as exc:  # noqa: BLE001 — R2 é o caminho preferido, não o único
        logger.warning("dinov2_r2_indisponivel: %s — caindo para a URL oficial", exc)

    logger.info("dinov2_baixando_da_origem: ~84MB")
    urllib.request.urlretrieve(PESO_URL, destino)  # noqa: S310 — URL fixa oficial
    if not _confere(destino):
        os.unlink(destino)
        raise RuntimeError("sha256 do DINOv2 divergiu — não carregando")
    return destino


class ClassificadorRecorte:
    """Carrega backbone + cabeças + régua de um tenant. Singleton por tenant."""

    def __init__(self, tenant_id: str, versao: str = "v1") -> None:
        self.tenant_id = tenant_id
        self.versao = versao
        self._backbone = None
        self._cabecas: dict[str, dict] = {}
        self._regua: dict[str, dict] = {}
        self.pronto = False
        self.ultimo_erro: str | None = None

    def carregar(self) -> bool:
        try:
            import torch
            from torch import nn

            from app.infrastructure.storage.local_storage import (  # noqa: PLC0415
                get_storage,
            )

            armazenamento = get_storage(self.tenant_id)
            prefixo = PREFIXO_R2.format(tenant=self.tenant_id, versao=self.versao)

            self._regua = json.loads(
                armazenamento.download_bytes(f"{prefixo}/regua.json")
            )

            self._backbone = torch.hub.load(  # noqa: S614 — repo oficial Meta
                "facebookresearch/dinov2", "dinov2_vits14", pretrained=False
            )
            self._backbone.load_state_dict(
                torch.load(_baixa_backbone(), map_location="cpu", weights_only=True)
            )
            self._backbone.eval()

            for familia in ("mascara", "luvas", "oculos", "auditiva"):
                try:
                    bruto = armazenamento.download_bytes(f"{prefixo}/{familia}.pt")
                except Exception:  # noqa: BLE001 — família sem modelo é normal
                    continue
                caminho = os.path.join(_cache_dir(), f"clf_{familia}.pt")
                with open(caminho, "wb") as f:
                    f.write(bruto)
                estado = torch.load(caminho, map_location="cpu", weights_only=False)
                cabeca = nn.Linear(estado["dim"], len(estado["classes"]))
                cabeca.load_state_dict(estado["peso"])
                cabeca.eval()
                self._cabecas[familia] = {
                    "cabeca": cabeca,
                    "classes": estado["classes"],
                }

            self.pronto = bool(self._cabecas)
            if not self.pronto:
                self.ultimo_erro = "nenhuma cabeça carregada"
            logger.info(
                "classificador_recorte_pronto: tenant=%s familias=%s aprovadas=%s",
                self.tenant_id, sorted(self._cabecas),
                sorted(k for k, v in self._regua.items() if v.get("passa")),
            )
            return self.pronto
        except Exception as exc:
            self.ultimo_erro = str(exc)[:200]
            logger.error(
                "classificador_recorte_falhou: tenant=%s err=%s",
                self.tenant_id, exc, exc_info=True,
            )
            return False

    def _passou_a_regua(self, familia: str, classe: str) -> bool:
        """A classe pode gerar violação? A medida viaja com o modelo."""
        return bool(self._regua.get(f"{familia}/{classe}", {}).get("passa"))

    def julgar(self, imagem_bytes: bytes) -> dict[str, dict]:
        """`{familia: {veredito, confianca, pode_alertar, motivo}}`.

        `veredito` ∈ {com, sem, incorreto, nao_visivel}. `pode_alertar` só é
        True para veredito de AUSÊNCIA de classe que passou a régua e com
        confiança acima do limiar — as três condições, sempre.
        """
        if not self.pronto:
            return {}

        import io

        import numpy as np
        import torch
        from PIL import Image

        media = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        desvio = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        with Image.open(io.BytesIO(imagem_bytes)) as im:
            arr = np.asarray(im.convert("RGB").resize((224, 224)), dtype=np.float32)
        arr = (arr / 255.0 - media) / desvio
        tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)

        with torch.no_grad():
            emb = self._backbone(tensor)

        saida: dict[str, dict] = {}
        for familia, peca in self._cabecas.items():
            with torch.no_grad():
                prob = torch.softmax(peca["cabeca"](emb), dim=1)[0]
            conf, idx = float(prob.max()), int(prob.argmax())
            classe = peca["classes"][idx]

            if conf < LIMIAR_PADRAO:
                saida[familia] = {
                    "veredito": "nao_visivel", "confianca": round(conf, 3),
                    "pode_alertar": False, "motivo": "confiança abaixo do limiar",
                }
                continue
            if classe != "sem":
                # presença ou uso incorreto: telemetria, nunca alerta de ausência
                saida[familia] = {
                    "veredito": classe, "confianca": round(conf, 3),
                    "pode_alertar": False, "motivo": "não é ausência",
                }
                continue
            if not self._passou_a_regua(familia, classe):
                saida[familia] = {
                    "veredito": "nao_visivel", "confianca": round(conf, 3),
                    "pode_alertar": False,
                    "motivo": f"{familia}/{classe} não passou a régua",
                }
                continue
            saida[familia] = {
                "veredito": "sem", "confianca": round(conf, 3),
                "pode_alertar": True, "motivo": "ausência sustentada pela régua",
            }
        return saida


def classificador_do_tenant(tenant_id: str, versao: str = "v1"):
    """Singleton por tenant. `None` se não carregar — o caller ABSTÉM."""
    chave = f"{tenant_id}:{versao}"
    with _trava:
        c = _cache.get(chave)
        if c is None:
            c = ClassificadorRecorte(tenant_id, versao)
            c.carregar()
            _cache[chave] = c
    return c if c.pronto else None
