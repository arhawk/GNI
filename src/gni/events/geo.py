"""Coarse country centroids / place hints for optional map pins (not event classification)."""

from __future__ import annotations

from typing import Any

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

# Place name → (label, country_id | None, precision).
# Maritime / contested waters must NOT bind a country centroid as fake event coords.
PLACE_HINTS: dict[str, tuple[str, str | None, str]] = {
    "beijing": ("Beijing", "CN", "city"),
    "shanghai": ("Shanghai", "CN", "city"),
    "washington": ("Washington", "US", "city"),
    "brussels": ("Brussels", "BE", "city"),
    "moscow": ("Moscow", "RU", "city"),
    "berlin": ("Berlin", "DE", "city"),
    "tokyo": ("Tokyo", "JP", "city"),
    "london": ("London", "GB", "city"),
    "paris": ("Paris", "FR", "city"),
    "new delhi": ("New Delhi", "IN", "city"),
    "canberra": ("Canberra", "AU", "city"),
    "geneva": ("Geneva", "CH", "city"),
    "taiwan": ("Taiwan", "TW", "region"),
    "south china sea": ("South China Sea", None, "maritime"),
    "east china sea": ("East China Sea", None, "maritime"),
    "taiwan strait": ("Taiwan Strait", None, "maritime"),
    "南海": ("South China Sea", None, "maritime"),
    "东海": ("East China Sea", None, "maritime"),
    "台海": ("Taiwan Strait", None, "maritime"),
    "海域": ("Maritime area", None, "maritime"),
}

# City-level labels that may receive map pins (country centroid only as last resort for city/region).
CITY_PRECISION = frozenset({"city"})
NO_COORD_PRECISION = frozenset({"maritime", "unknown"})


def centroid(country_id: str | None) -> tuple[float, float] | None:
    if not country_id:
        return None
    return COUNTRY_CENTROIDS.get(country_id.upper())


def guess_location_from_text(text: str | None) -> tuple[str | None, str | None]:
    """Heuristic EVENT_LOCATION from known place names in title/spans. Empty if unknown."""
    spec = location_pin_spec(text=text)
    if not spec["label"]:
        return None, None
    return spec["label"], spec["country_id"]


def location_pin_spec(
    *,
    text: str | None = None,
    label: str | None = None,
    country_id: str | None = None,
) -> dict[str, Any]:
    """Resolve geographic precision + optional map coords.

    Maritime / unknown → coords null (never fake Beijing/capital pins).
    City-level with known country → optional capital/city centroid for map only.
    """
    precision = "unknown"
    conf = 0.2
    evidence: dict[str, Any] = {"mode": "heuristic"}
    resolved_label = label
    resolved_cid = country_id.upper() if country_id else None

    hay = (text or label or "").lower()
    if hay:
        for key in sorted(PLACE_HINTS.keys(), key=len, reverse=True):
            if key in hay:
                resolved_label, hint_cid, precision = PLACE_HINTS[key]
                if hint_cid:
                    resolved_cid = hint_cid
                elif precision == "maritime":
                    resolved_cid = None
                conf = 0.55 if precision == "city" else 0.4
                evidence = {"matched": key, "mode": "place_hint"}
                break

    if precision == "maritime" or "sea" in (resolved_label or "").lower() or "海峡" in (
        resolved_label or ""
    ):
        precision = "maritime"
        resolved_cid = None
        conf = min(conf, 0.45)
        evidence["no_country_centroid"] = True

    lat = lon = None
    if precision in CITY_PRECISION and resolved_cid:
        coords = centroid(resolved_cid)
        if coords:
            lat, lon = coords
            evidence["coord_basis"] = "country_centroid_for_city"
            conf = max(conf, 0.5)
    elif precision in NO_COORD_PRECISION or precision == "region":
        lat = lon = None
    elif precision == "country" and resolved_cid:
        # Country-only: still no pin by default (too coarse for EVENT_LOCATION map).
        lat = lon = None
        evidence["coord_basis"] = "suppressed_country_only"

    return {
        "label": resolved_label,
        "country_id": resolved_cid,
        "geographic_precision": precision,
        "confidence": conf,
        "lat": lat,
        "lon": lon,
        "evidence": evidence,
    }
