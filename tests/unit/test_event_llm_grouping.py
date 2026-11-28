"""Standardized actor/action keys from analysis LLM + daily batch LLM grouping (LLM stubbed)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from gni.core.contracts import ArticleEventCandidateContract
from gni.events.extract import extract_from_structured_candidates
from gni.events.fingerprint import FingerprintCard, allowed_action_keys, allowed_actor_keys
from gni.events.llm_grouping import (
    build_grouping_prompt,
    cluster_cards_daily,
    group_cards_with_llm,
    make_cached_llm_call,
    parse_grouping_response,
)
from gni.events.match import cluster_fingerprints

T0 = datetime(2026, 11, 26, 6, 0, tzinfo=timezone.utc)


def _keyed(article_id: str, actor_key: str, action_key: str, *, when: datetime = T0, obj: str = "tariffs") -> FingerprintCard:
    return FingerprintCard(
        article_id=article_id,
        actor="unrecognized actor text",
        action="unrecognized action text",
        object=obj,
        summary=f"{actor_key} {action_key} {obj}",
        published_at=when,
        confidence=0.6,
        llm_actor_key=actor_key,
        llm_action_key=action_key,
    )


def _unkeyed(article_id: str, *, when: datetime = T0) -> FingerprintCard:
    return FingerprintCard(
        article_id=article_id,
        actor="unrecognized actor text",
        action="unrecognized action text",
        object="something",
        summary="something happened",
        published_at=when,
    )


# ---------- step 1: standardized keys ----------


def test_llm_keys_take_precedence_over_dictionaries():
    card = FingerprintCard(
        article_id="a1",
        actor="China",
        action="sign",
        llm_actor_key="us",
        llm_action_key="SANCTION",
    )
    assert card.actor_key == "us"
    assert card.action_key == "SANCTION"
    assert card.is_insufficient is False
    fp = card.to_fingerprint_dict()
    assert fp["llm_actor_key"] == "us"
    assert fp["llm_action_key"] == "SANCTION"


def test_invalid_llm_actor_key_falls_back_to_dictionary():
    card = FingerprintCard(article_id="a1", actor="China", action="sign", llm_actor_key="martian")
    assert card.actor_key == "china"  # dictionary fallback
    assert card.to_fingerprint_dict()["llm_actor_key"] is None


def test_invalid_llm_action_key_falls_back_to_dictionary():
    card = FingerprintCard(article_id="a1", actor="unknown", action="gibberish words", llm_action_key="NOT_A_KEY")
    assert card.action_key is None  # dictionary has no mapping; invalid LLM key ignored
    assert card.is_insufficient is True


def test_extract_reads_llm_keys_from_structured_candidates():
    structured = {
        "event_candidates": [
            {
                "event_relation": "new_event_candidate",
                "actor": "Trump administration",
                "action": "announced plans",
                "object": "tariffs on chips",
                "actor_key": "us",
                "action_key": "ANNOUNCE",
                "confidence": 0.8,
            },
            {
                "event_relation": "new_event_candidate",
                "actor": "Someone",
                "action": "did a thing",
                "object": "x",
                "actor_key": "not-in-vocab",
                "action_key": "bogus",
            },
        ]
    }
    cards = extract_from_structured_candidates(article_id="a1", structured=structured, published_at=T0)
    assert len(cards) == 2
    assert cards[0].llm_actor_key == "us"
    assert cards[0].llm_action_key == "ANNOUNCE"
    assert cards[1].llm_actor_key is None
    assert cards[1].llm_action_key is None


def test_contract_preserves_actor_and_action_keys():
    cand = ArticleEventCandidateContract.model_validate(
        {"actor": "China", "action": "x", "actor_key": "china", "action_key": "WARN"}
    )
    dumped = cand.model_dump()
    assert dumped["actor_key"] == "china"
    assert dumped["action_key"] == "WARN"


def test_vocabularies_are_nonempty_and_sorted():
    assert "us" in allowed_actor_keys() and "china" in allowed_actor_keys()
    assert "SANCTION" in allowed_action_keys()


# ---------- step 2: batch grouping validation ----------


def test_prompt_lists_every_card_with_positional_id():
    cards = [_keyed("a1", "us", "SANCTION"), _keyed("a2", "china", "WARN")]
    prompt = build_grouping_prompt(cards)
    assert "[c0]" in prompt and "[c1]" in prompt
    assert "[c2]" not in prompt


def test_parse_accepts_valid_groups_and_drops_singletons():
    payload = {"groups": [{"title": "t", "card_ids": ["c0", "c2"]}, {"title": "solo", "card_ids": ["c1"]}]}
    assert parse_grouping_response(payload, 3) == [[0, 2]]


def test_parse_rejects_unknown_card_id():
    payload = {"groups": [{"title": "t", "card_ids": ["c0", "c9"]}]}
    assert parse_grouping_response(payload, 3) is None


def test_parse_rejects_card_in_two_groups():
    payload = {
        "groups": [
            {"title": "a", "card_ids": ["c0", "c1"]},
            {"title": "b", "card_ids": ["c1", "c2"]},
        ]
    }
    assert parse_grouping_response(payload, 3) is None


def test_parse_rejects_malformed_payload():
    assert parse_grouping_response(None, 3) is None
    assert parse_grouping_response({"groups": "nope"}, 3) is None
    assert parse_grouping_response({"groups": [{"card_ids": "c0"}]}, 3) is None
    assert parse_grouping_response({"groups": [42]}, 3) is None


def test_group_cards_with_llm_builds_clusters_and_keeps_unassigned_keyed_singletons():
    cards = [
        _keyed("a1", "us", "SANCTION"),
        _keyed("a2", "us", "SANCTION"),
        _keyed("a3", "china", "WARN"),
        _unkeyed("a4"),  # insufficient and unassigned -> dropped
    ]
    seen_prompts: list[str] = []

    def call(prompt: str):
        seen_prompts.append(prompt)
        return {"groups": [{"title": "sanctions", "card_ids": ["c0", "c1"]}]}

    clusters = group_cards_with_llm(cards, call=call)
    assert clusters is not None
    assert len(seen_prompts) == 1
    sizes = sorted(len(c.article_ids) for c in clusters)
    assert sizes == [1, 2]  # one 2-article group + the unassigned keyed card
    grouped = next(c for c in clusters if len(c.article_ids) == 2)
    assert set(grouped.article_ids) == {"a1", "a2"}


def test_group_cards_with_llm_returns_none_when_call_fails():
    cards = [_keyed("a1", "us", "SANCTION"), _keyed("a2", "us", "SANCTION")]
    assert group_cards_with_llm(cards, call=lambda p: None) is None
    assert group_cards_with_llm(cards, call=lambda p: {"groups": [{"card_ids": ["c0", "c7"]}]}) is None


def test_cluster_cards_daily_without_llm_matches_rule_path():
    cards = [_keyed("a1", "us", "SANCTION"), _keyed("a2", "us", "SANCTION"), _keyed("a3", "china", "WARN")]
    clusters, stats = cluster_cards_daily(cards, call=None, use_llm=False)
    legacy = cluster_fingerprints(cards, use_llm=False)
    assert len(clusters) == len(legacy)
    assert stats["llm_days"] == 0


def test_cluster_cards_daily_falls_back_per_day_on_invalid_llm():
    day1 = [_keyed("a1", "us", "SANCTION"), _keyed("a2", "us", "SANCTION")]
    day2 = [_keyed("b1", "china", "WARN", when=datetime(2026, 11, 27, 6, 0, tzinfo=timezone.utc))]

    def bad_call(prompt: str):
        return {"groups": [{"card_ids": ["c0", "c5"]}]}  # unknown id -> reject

    clusters, stats = cluster_cards_daily(day1 + day2, call=bad_call, use_llm=False)
    assert stats["days"] == 2
    assert stats["rule_fallback_days"] == 2
    assert stats["llm_days"] == 0
    assert clusters


def test_cluster_cards_daily_uses_llm_per_day():
    day1 = [_keyed("a1", "us", "SANCTION"), _keyed("a2", "us", "SANCTION")]
    day2 = [_keyed("b1", "china", "WARN", when=datetime(2026, 11, 27, 6, 0, tzinfo=timezone.utc))]
    calls: list[str] = []

    def call(prompt: str):
        calls.append(prompt)
        return {"groups": [{"card_ids": ["c0", "c1"]}]} if "[c1]" in prompt else {"groups": []}

    clusters, stats = cluster_cards_daily(day1 + day2, call=call, use_llm=False)
    assert len(calls) == 2  # one call per day
    assert stats == {"days": 2, "llm_days": 2, "rule_fallback_days": 0}
    assert sorted(len(c.article_ids) for c in clusters) == [1, 2]


def test_cached_llm_call_hits_provider_once(tmp_path):
    counter = {"n": 0}

    class FakeProvider:
        def generate_json(self, **kwargs):
            counter["n"] += 1
            return SimpleNamespace(parsed={"groups": []})

    call = make_cached_llm_call(provider=FakeProvider(), model="m", cache_dir=tmp_path)
    assert call("same prompt") == {"groups": []}
    assert call("same prompt") == {"groups": []}
    assert counter["n"] == 1
    assert call("other prompt") == {"groups": []}
    assert counter["n"] == 2


def test_cached_llm_call_returns_none_on_provider_error(tmp_path):
    class BrokenProvider:
        def generate_json(self, **kwargs):
            raise RuntimeError("HTTP 500")

    call = make_cached_llm_call(provider=BrokenProvider(), model="m", cache_dir=tmp_path)
    assert call("prompt") is None
    assert not any(tmp_path.iterdir())
