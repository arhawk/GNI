"""Fixed V1.0 taxonomy loader and validators (4 boards x 15 topics)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

TAXONOMY_V1_VERSION = "taxonomy_v1.0"
DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "configs" / "topics_taxonomy_v1.yaml"


@dataclass(frozen=True)
class BoardDef:
    id: str
    name_zh: str
    name_en: str


@dataclass(frozen=True)
class TopicDef:
    id: str
    board_id: str
    name_zh: str
    name_en: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class TaxonomyV1:
    version: str
    boards: tuple[BoardDef, ...]
    topics: tuple[TopicDef, ...]
    board_by_id: dict[str, BoardDef]
    topic_by_id: dict[str, TopicDef]
    topics_by_board: dict[str, tuple[TopicDef, ...]]


@lru_cache(maxsize=4)
def load_taxonomy_v1(path: str | Path | None = None) -> TaxonomyV1:
    cfg_path = Path(path) if path else DEFAULT_TAXONOMY_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    boards = tuple(
        BoardDef(id=str(b["id"]), name_zh=str(b["name_zh"]), name_en=str(b.get("name_en", "")))
        for b in (raw.get("boards") or [])
    )
    board_by_id = {b.id: b for b in boards}
    topics = tuple(
        TopicDef(
            id=str(t["id"]),
            board_id=str(t["board_id"]),
            name_zh=str(t["name_zh"]),
            name_en=str(t.get("name_en", "")),
            keywords=tuple(str(k) for k in (t.get("keywords") or [])),
        )
        for t in (raw.get("topics") or [])
    )
    topic_by_id = {t.id: t for t in topics}
    for t in topics:
        if t.board_id not in board_by_id:
            raise ValueError(f"Topic {t.id!r} references unknown board_id {t.board_id!r}")
    if len(boards) != 4 or len(topics) != 15:
        raise ValueError(
            f"V1.0 taxonomy must have exactly 4 boards and 15 topics, got {len(boards)} and {len(topics)}"
        )
    topics_by_board = {
        b.id: tuple(t for t in topics if t.board_id == b.id) for b in boards
    }
    return TaxonomyV1(
        version=str(raw.get("taxonomy_version") or TAXONOMY_V1_VERSION),
        boards=boards,
        topics=topics,
        board_by_id=board_by_id,
        topic_by_id=topic_by_id,
        topics_by_board=topics_by_board,
    )


def normalize_topic_ids(topic_ids: Iterable[str] | None) -> list[str]:
    """Validate against fixed 15 V1.0 topic IDs, deduplicating in stable order."""
    tax = load_taxonomy_v1()
    seen: set[str] = set()
    out: list[str] = []
    for raw in topic_ids or ():
        tid = str(raw or "").strip()
        if tid in tax.topic_by_id and tid not in seen:
            seen.add(tid)
            out.append(tid)
    return out


def boards_for_topics(topic_ids: Iterable[str] | None) -> list[str]:
    """Derive deduplicated board_ids from valid topic_ids in canonical board order."""
    tax = load_taxonomy_v1()
    valid_topics = normalize_topic_ids(topic_ids)
    matched_boards = {tax.topic_by_id[tid].board_id for tid in valid_topics}
    return [b.id for b in tax.boards if b.id in matched_boards]


def taxonomy_prompt_block() -> str:
    """Compact prompt block listing the fixed 4 boards x 15 topics for LLM classification."""
    tax = load_taxonomy_v1()
    lines = ["Fixed V1.0 Topics (multi-label; return ONLY IDs from this list):"]
    for b in tax.boards:
        tlist = ", ".join(f"{t.id} ({t.name_zh})" for t in tax.topics_by_board[b.id])
        lines.append(f"- {b.id} ({b.name_zh}): {tlist}")
    return "\n".join(lines)
