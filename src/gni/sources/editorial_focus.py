"""Editorial focus helpers: active sources must be international / China desks.

GNI monitors other countries' official media for China-related and international
coverage — not domestic livelihood / local admin feeds. See docs/BLUEPRINT_V4.md
and docs/PRODUCT_SCOPE.md.
"""

from __future__ import annotations

import re
from typing import Iterable

# Source IDs known to fail the international/China topic mix (domestic-admin or
# site-wide domestic mix). Must not be active.
ACTIVE_EDITORIAL_DENYLIST: frozenset[str] = frozenset(
    {
        "in_niti",
        "in_pib_hindi",
        "ru_ria",  # site-wide domestic mix
        "ru_tass_russian",  # site-wide domestic mix
        "au_abc_top",  # Top Stories domestic-heavy
        "de_dw_german",  # DE-all domestic/EU-heavy below bar
        "us_defense_news",  # domestic DoD lifestyle/ops mix
    }
)

EDITORIAL_FOCUS_INTERNATIONAL_OR_CHINA = "international_or_china"

# Minimum share of titles that must match china OR international keywords.
DEFAULT_MIN_INTL_OR_CHINA_RATIO = 0.35

# Explicit Asia / foreign / China desks may pass with a lower title ratio.
DESK_MIN_RATIO = 0.20

CHINA_TITLE_RE = re.compile(
    r"china|chinese|beijing|taiwan|taipei|xinjiang|uyghur|hong\s*kong|huawei|"
    r"belt\s*and\s*road|prc|\bpla\b|xi\s*jinping|south\s*china\s*sea|tibet|macau|"
    r"shanghai|guangzhou|"
    r"китай|китая|китайск|пекин|тайван|синцзян|гонконг|\bкнр\b|"
    r"चीन|चीनी|बीजिंग|ताइवान|"
    r"中国|中國|北京|台湾|台灣|新疆|香港|华为|一帶一路|一带一路",
    re.IGNORECASE,
)

INTL_TITLE_RE = re.compile(
    r"(?:"
    r"\b(?:foreign|diplomat|diplomacy|embassy|ambassador|international|world|"
    r"global|geopolit|bilateral|multilateral|united\s+nations|\bun\b|unsc|"
    r"nato|g7|g20|asean|apec|quad|indo[- ]pacific|asia[- ]pacific|\basia\b|"
    r"pacific\b|europe|european(?:\s+union)?|\beu\b|ukraine|russia|moscow|"
    r"washington|pentagon|state\s+department|defense|defence|military|"
    r"sanctions|trade\s+war|tariff|summit|treaty|alliance|invasion|conflict|"
    r"\bwar\b|missile|nuclear|middle\s+east|gaza|israel|iran|north\s+korea|"
    r"korea|japan|india|bangladesh|nepal|uae|singapore|solomon|germany|"
    r"australia|france|britain|\buk\b|africa|climate|global\s+south|"
    r"außenpolitik|ausland|diplomatie|"
    r"внешн\w*|международ\w*|дипломат\w*|посольств\w*|войн\w*|украин\w*"
    r")\b|"
    r"विदेश|अंतरराष्ट्रीय|कूटनीति|पश्चिम\s*एशिया"
    r")",
    re.IGNORECASE,
)

# URL/name signals that the feed is an explicit international / Asia / China desk.
DESK_HINT_RE = re.compile(
    r"(?:asia|asien|china|world|international|foreign|external.?affairs|"
    r"west.?asia|indo.?pacific|pacific|diplomat|sputnik|tass\.com|"
    r"rfa\.org|mid\.ru|mea\.|dfat|foreignminister|kremlin|rt\.com|"
    r"feed/26458|feed/1556)",
    re.IGNORECASE,
)


def title_is_china(title: str | None) -> bool:
    return bool(title and CHINA_TITLE_RE.search(title))


def title_is_international(title: str | None) -> bool:
    return bool(title and INTL_TITLE_RE.search(title))


def title_is_intl_or_china(title: str | None) -> bool:
    return title_is_china(title) or title_is_international(title)


def score_titles(titles: Iterable[str | None]) -> dict[str, float | int]:
    items = [t for t in titles if t is not None]
    n = len(items)
    if n == 0:
        return {"n": 0, "china": 0, "intl_or_china": 0, "rate": 0.0}
    china = sum(1 for t in items if title_is_china(t))
    either = sum(1 for t in items if title_is_intl_or_china(t))
    return {
        "n": n,
        "china": china,
        "intl_or_china": either,
        "rate": either / n,
    }


def is_explicit_intl_desk(*, source_id: str, name: str, feed_url: str) -> bool:
    blob = f"{source_id} {name} {feed_url}"
    return bool(DESK_HINT_RE.search(blob))


def passes_editorial_focus(
    titles: Iterable[str | None],
    *,
    source_id: str = "",
    name: str = "",
    feed_url: str = "",
    min_ratio: float = DEFAULT_MIN_INTL_OR_CHINA_RATIO,
    desk_min_ratio: float = DESK_MIN_RATIO,
) -> tuple[bool, dict[str, float | int | bool]]:
    """Return (pass, score_detail). Empty feeds fail."""
    score = score_titles(titles)
    desk = is_explicit_intl_desk(source_id=source_id, name=name, feed_url=feed_url)
    threshold = desk_min_ratio if desk else min_ratio
    n = int(score["n"])
    rate = float(score["rate"])
    ok = n > 0 and rate >= threshold
    detail: dict[str, float | int | bool] = {
        **score,
        "desk": desk,
        "threshold": threshold,
        "pass": ok,
    }
    return ok, detail
