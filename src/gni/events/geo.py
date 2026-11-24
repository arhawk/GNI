"""Coarse country centroids / place hints for optional map pins (not event classification)."""

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
    "BE": (50.85, 4.35),
}

# Place name → (label, country_id). Never treat reporting source country as event site.
PLACE_HINTS: dict[str, tuple[str, str]] = {
    "beijing": ("Beijing", "CN"),
    "shanghai": ("Shanghai", "CN"),
    "washington": ("Washington", "US"),
    "brussels": ("Brussels", "BE"),
    "moscow": ("Moscow", "RU"),
    "berlin": ("Berlin", "DE"),
    "tokyo": ("Tokyo", "JP"),
    "london": ("London", "GB"),
    "paris": ("Paris", "FR"),
    "new delhi": ("New Delhi", "IN"),
    "canberra": ("Canberra", "AU"),
    "geneva": ("Geneva", "CH"),
    "taiwan": ("Taiwan", "TW"),
    "south china sea": ("South China Sea", "CN"),
}


def centroid(country_id: str | None) -> tuple[float, float] | None:
    if not country_id:
        return None
    return COUNTRY_CENTROIDS.get(country_id.upper())


def guess_location_from_text(text: str | None) -> tuple[str | None, str | None]:
    """Heuristic EVENT_LOCATION from known place names in title/spans. Empty if unknown."""
    if not text:
        return None, None
    lower = text.lower()
    # longer keys first
    for key in sorted(PLACE_HINTS.keys(), key=len, reverse=True):
        if key in lower:
            label, cid = PLACE_HINTS[key]
            return label, cid
    return None, None
