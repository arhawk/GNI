"""Ingestion adapter base class — Phase 0 interface only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, source_config: dict[str, Any]) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw_item: Any) -> dict[str, Any]:
        raise NotImplementedError

    def health_check(self, source_config: dict[str, Any]) -> dict[str, str]:
        return {"status": "unknown"}
