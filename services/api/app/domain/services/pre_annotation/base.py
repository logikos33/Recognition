"""
Recognition — Pre-Annotation Backend (Abstract).

Interface plugável para geração de caixas sugeridas (HITL). Mesma forma de
`infrastructure/storage/base.py::StorageStrategy` — permite trocar de
implementação sem mudar a camada de serviço/rotas.

Backends conhecidos (nenhum é o default — ver factory.py):
  - DinoSamHttpBackend: proxy pro microserviço pre-annotation-service
    (DINO+SAM), removido do caminho de produção em maio/2026 por custo×
    qualidade — disponível como opção, não como default.
  - Candidato a avaliar antes de qualquer tenant ligar a flag de verdade:
    Jetson Platform Services (VLM/zero-shot nativo do edge da Logikos) —
    processa no próprio hardware do cliente, sem custo de GPU cloud por
    chamada. Não implementado nesta PR (ver ADR-0031, adendo).
"""
from abc import ABC, abstractmethod


class PreAnnotationBackend(ABC):
    """Abstração de backend de pré-anotação (propõe caixas pra revisão humana)."""

    @abstractmethod
    def predict_and_store(self, frame_id: str, module_code: str) -> int:
        """Gera sugestões para o frame e persiste em
        `training_frames.pre_annotations` (formato já consumido por
        `annotation_service.get_frame_annotations`: lista de dicts com
        `bbox` normalizado [0,1] + `confidence` + `class`/`label`).

        Cada implementação decide como persistir (chamada HTTP a um
        microserviço com acesso próprio ao banco, ou escrita direta via
        FrameRepository — a interface não impõe qual). Retorna a
        quantidade de anotações propostas (0 se nenhuma). Levanta exceção
        em falha de comunicação/backend — o caller decide como expor isso
        na API.
        """
        ...
