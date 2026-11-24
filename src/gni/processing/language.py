"""Language detection helpers."""

from __future__ import annotations


def detect_language(text: str | None, fallback: str | None = None) -> str | None:
    sample = (text or "").strip()
    if len(sample) < 20:
        return fallback
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        return detect(sample)
    except Exception:  # noqa: BLE001
        return fallback
