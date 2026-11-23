"""LLM provider abstraction — Phase 0 interface only (no live API calls)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    @abstractmethod
    def analyze(self, article: dict[str, Any], *, schema: dict[str, Any], prompt_version: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class NullLLMProvider(BaseLLMProvider):
    """Safe default for Phase 0 / tests — does not contact external APIs."""

    def analyze(self, article: dict[str, Any], *, schema: dict[str, Any], prompt_version: str) -> dict[str, Any]:
        raise RuntimeError("NullLLMProvider: live analysis is not enabled in Phase 0")

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("NullLLMProvider: live generation is not enabled in Phase 0")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("NullLLMProvider: live embedding is not enabled in Phase 0")
