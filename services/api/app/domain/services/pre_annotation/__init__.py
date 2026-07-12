"""Pré-anotação assistida (WS-B4) — backend plugável, OFF por padrão.

Ver ADR-0031 (adendo 2026-07-12): DINO+SAM foi removido em maio/2026 por
custo×qualidade; a retomada usa uma interface desacoplada do modelo
(`PreAnnotationBackend`) em vez de reacoplar DINO+SAM como default.
"""
from app.domain.services.pre_annotation.base import PreAnnotationBackend
from app.domain.services.pre_annotation.factory import get_pre_annotation_backend

__all__ = ["PreAnnotationBackend", "get_pre_annotation_backend"]
