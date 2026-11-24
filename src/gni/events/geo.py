"""Coarse country centroids for optional map pins (not event classification)."""

from __future__ import annotations

# Approximate capital / representative points for monitored countries + common actors.
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "US": (38.9, -77.0),
    "RU": (55.75, 37.62),
    "DE": (52.52, 13.40),
    "IN": (28.61, 77.21),
    "AU": (-35.28, 149.13),
    "CN": (39.90, 116.40),
    "JP": (35.68, 139.69),
    "GB": (51.50, -0.12),
    "FR": (48.86, 2.35),
    "EU": (50.85, 4.35),  # Brussels stand-in for EU announcements
}


def centroid(country_id: str | None) -> tuple[float, float] | None:
    if not country_id:
        return None
    return COUNTRY_CENTROIDS.get(country_id.upper())
