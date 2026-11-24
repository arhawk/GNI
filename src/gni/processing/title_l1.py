"""Rule-based L1 title screening (no LLM)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from gni.processing.hashutil import sha256_text
from gni.processing.normalize import normalize_whitespace

def _default_dict_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "configs" / "china_entity_dictionary_v0.1.yaml",
        Path.cwd() / "configs" / "china_entity_dictionary_v0.1.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


DEFAULT_DICT_PATH = _default_dict_path()


@dataclass
class TitleScreenResult:
    label: str
    priority: str
    matched_entities: list[dict[str, Any]] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    confidence: float | None = None
    requires_human_review: bool = False
    rule_version: str = "title_l1_rules_v0.2"
    entity_dictionary_version: str = "china_entity_dictionary_v0.2"
    input_hash: str | None = None


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    return t.casefold()


def _compile_alias(alias: str) -> re.Pattern[str]:
    # Word-ish boundary for Latin; allow CJK without strict boundaries.
    a = re.escape(alias.strip())
    if re.search(r"[A-Za-z]", alias):
        return re.compile(rf"(?<![A-Za-z0-9]){a}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(a)


@lru_cache(maxsize=4)
def load_dictionary(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _default_dict_path()
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    compiled: list[dict[str, Any]] = []
    for ent in data.get("entities") or []:
        patterns = []
        for alias in ent.get("aliases") or []:
            if not alias:
                continue
            patterns.append((_compile_alias(str(alias)), str(alias)))
        compiled.append({**ent, "_patterns": patterns})
    data["_compiled"] = compiled
    return data


def screen_title(
    title: str | None,
    *,
    summary: str | None = None,
    dict_path: str | None = None,
) -> TitleScreenResult:
    dict_data = load_dictionary(dict_path)
    blob = normalize_whitespace(f"{title or ''}\n{summary or ''}")
    folded = _fold(blob)
    input_hash = sha256_text(folded)

    matches: list[dict[str, Any]] = []
    scopes: set[str] = set()
    for ent in dict_data.get("_compiled") or []:
        hit_aliases: list[str] = []
        for pattern, alias in ent.get("_patterns") or []:
            if pattern.search(blob) or pattern.search(folded):
                hit_aliases.append(alias)
        if hit_aliases:
            scope = ent.get("inclusion_scope") or "secondary"
            scopes.add(scope)
            matches.append(
                {
                    "entity_id": ent.get("entity_id"),
                    "canonical_name": ent.get("canonical_name"),
                    "entity_type": ent.get("entity_type"),
                    "inclusion_scope": scope,
                    "aliases_hit": hit_aliases,
                    "ambiguity_notes": ent.get("ambiguity_notes"),
                }
            )

    rule_version = dict_data.get("rule_version") or "title_l1_rules_v0.1"
    dict_version = dict_data.get("version") or "china_entity_dictionary_v0.1"

    if not matches:
        return TitleScreenResult(
            label="no_match",
            priority="P3",
            reason_codes=["title_no_entity_hit"],
            confidence=0.55,
            rule_version=rule_version,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    if "ambiguous" in scopes and scopes <= {"ambiguous"}:
        return TitleScreenResult(
            label="uncertain",
            priority="P2",
            matched_entities=matches,
            reason_codes=["ambiguous_entity_only"],
            confidence=0.45,
            requires_human_review=True,
            rule_version=rule_version,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    if "core" in scopes:
        return TitleScreenResult(
            label="explicit_relevant",
            priority="P1",
            matched_entities=matches,
            reason_codes=["core_entity_hit"],
            confidence=0.85,
            rule_version=rule_version,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    return TitleScreenResult(
        label="likely_relevant",
        priority="P2",
        matched_entities=matches,
        reason_codes=["secondary_or_company_hit"],
        confidence=0.7,
        requires_human_review=any(m.get("ambiguity_notes") for m in matches),
        rule_version=rule_version,
        entity_dictionary_version=dict_version,
        input_hash=input_hash,
    )
