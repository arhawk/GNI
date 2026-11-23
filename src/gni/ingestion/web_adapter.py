"""Web adapter placeholder — not implemented in P1-A."""

from __future__ import annotations

from typing import Any

from gni.ingestion.base import BaseAdapter


class WebAdapter(BaseAdapter):
    def fetch(self, source_config: dict[str, Any]) -> list[Any]:
        raise NotImplementedError("WebAdapter is a P1-A placeholder; not production-ready")

    def parse(self, raw_item: Any) -> dict[str, Any]:
        raise NotImplementedError("WebAdapter is a P1-A placeholder; not production-ready")
