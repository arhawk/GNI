"""Meilisearch HTTP client (optional). Falls back when unreachable."""

from __future__ import annotations

from typing import Any

import httpx

from gni.core.config import get_settings

ARTICLES_INDEX = "gni_articles"
EVENTS_INDEX = "gni_events"


def meili_config() -> tuple[str, str]:
    s = get_settings()
    url = (getattr(s, "meili_url", None) or "").rstrip("/")
    key = getattr(s, "meili_key", None) or ""
    return url, key


def meili_available(timeout: float = 1.5) -> bool:
    url, key = meili_config()
    if not url:
        return False
    try:
        r = httpx.get(
            f"{url}/health",
            headers=_headers(key),
            timeout=timeout,
        )
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _headers(key: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def ensure_indexes() -> None:
    url, key = meili_config()
    if not url:
        return
    with httpx.Client(timeout=10.0) as client:
        for index, primary in ((ARTICLES_INDEX, "id"), (EVENTS_INDEX, "id")):
            client.post(
                f"{url}/indexes",
                headers=_headers(key),
                json={"uid": index, "primaryKey": primary},
            )
            client.patch(
                f"{url}/indexes/{index}/settings",
                headers=_headers(key),
                json={
                    "searchableAttributes": ["title", "summary", "content"],
                    "displayedAttributes": ["id", "title", "summary", "kind"],
                },
            )


def upsert_documents(index: str, docs: list[dict[str, Any]]) -> dict[str, Any]:
    url, key = meili_config()
    if not url or not docs:
        return {"enqueued": False, "reason": "no_url_or_empty"}
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{url}/indexes/{index}/documents",
            headers=_headers(key),
            json=docs,
        )
        r.raise_for_status()
        return r.json()


def search_index(index: str, q: str, *, limit: int = 20) -> list[dict[str, Any]]:
    url, key = meili_config()
    if not url:
        return []
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{url}/indexes/{index}/search",
            headers=_headers(key),
            json={"q": q, "limit": limit},
        )
        r.raise_for_status()
        return list((r.json() or {}).get("hits") or [])


def delete_all_documents(index: str) -> None:
    url, key = meili_config()
    if not url:
        return
    with httpx.Client(timeout=30.0) as client:
        client.delete(f"{url}/indexes/{index}/documents", headers=_headers(key))
