"""
Tests: domain/services/propagation_provider.py — resolução do provider de
GPU da propagação semeada (edge vs nuvem de terceiro).

Cobre:
- resolve_propagation_provider: request explícito > env
  PROPAGATION_GPU_PROVIDER > default runpod; valor inválido levanta
  InvalidGpuProviderError.
- is_offsite/is_onsite: wrappers finos sobre app.constants, aceitam str
  ou GpuProvider.
"""
from __future__ import annotations

import pytest

from app.constants import GpuProvider
from app.domain.services.propagation_provider import (
    InvalidGpuProviderError,
    is_offsite,
    is_onsite,
    resolve_propagation_provider,
)


class TestResolvePropagationProvider:
    def test_no_request_no_env_defaults_to_runpod(self, monkeypatch) -> None:
        monkeypatch.delenv("PROPAGATION_GPU_PROVIDER", raising=False)
        assert resolve_propagation_provider(None) == GpuProvider.RUNPOD

    def test_explicit_request_wins_over_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PROPAGATION_GPU_PROVIDER", "edge")
        assert resolve_propagation_provider("runpod") == GpuProvider.RUNPOD

    def test_env_used_when_no_explicit_request(self, monkeypatch) -> None:
        monkeypatch.setenv("PROPAGATION_GPU_PROVIDER", "edge")
        assert resolve_propagation_provider(None) == GpuProvider.EDGE

    def test_empty_string_request_falls_back_to_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PROPAGATION_GPU_PROVIDER", "edge")
        assert resolve_propagation_provider("") == GpuProvider.EDGE

    def test_request_is_case_insensitive_and_stripped(self, monkeypatch) -> None:
        monkeypatch.delenv("PROPAGATION_GPU_PROVIDER", raising=False)
        assert resolve_propagation_provider(" EDGE ") == GpuProvider.EDGE

    def test_invalid_request_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("PROPAGATION_GPU_PROVIDER", raising=False)
        with pytest.raises(InvalidGpuProviderError, match="provider inválido"):
            resolve_propagation_provider("gcp")

    def test_invalid_env_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("PROPAGATION_GPU_PROVIDER", "not-a-provider")
        with pytest.raises(InvalidGpuProviderError):
            resolve_propagation_provider(None)


class TestIsOffsiteOnsite:
    def test_runpod_is_offsite(self) -> None:
        assert is_offsite(GpuProvider.RUNPOD) is True
        assert is_onsite(GpuProvider.RUNPOD) is False

    def test_edge_is_onsite(self) -> None:
        assert is_onsite(GpuProvider.EDGE) is True
        assert is_offsite(GpuProvider.EDGE) is False

    def test_accepts_plain_string(self) -> None:
        assert is_offsite("vast_ai") is True
        assert is_onsite("local") is True
