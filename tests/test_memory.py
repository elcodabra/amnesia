"""Tests for the logic that decides what Amnesia believes.

Every test here runs with no model, no network and no cloud account, because
these are the parts that must stay correct when a demo is being recorded: the
arithmetic behind the numbers on the card, and the rules that stop the memory
from filling with junk.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from amnesia.ingest.sessions import Session, Turn, _flatten_content
from amnesia.memory.analytics import Span, active_minutes, analyse, detect_stuck, merge_intervals
from amnesia.memory.distill import _belief_id, _parse_response, _to_belief
from amnesia.memory.store import Belief, JsonMemoryStore

BASE = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)


def _session(
    sid: str = "s1",
    *,
    start_min: int = 0,
    length_min: int = 30,
    project: str = "demo",
    user_texts: list[str] | None = None,
) -> Session:
    start = BASE + timedelta(minutes=start_min)
    end = start + timedelta(minutes=length_min)
    turns = [Turn(role="user", text=t, at=start) for t in (user_texts or ["do the thing"])]
    return Session(
        id=sid, client="jcode", project=project, started_at=start, ended_at=end, turns=turns
    )


# --------------------------------------------------------------------------
# Time is the number people check first on a shared card, so it has to be right.
# --------------------------------------------------------------------------


def test_overlapping_sessions_count_once() -> None:
    """Two clients open at the same time is one hour of work, not two."""
    a = _session("a", start_min=0, length_min=60)
    b = _session("b", start_min=30, length_min=60)
    assert active_minutes([a, b]) == 90.0


def test_separate_sessions_add_up() -> None:
    a = _session("a", start_min=0, length_min=30)
    b = _session("b", start_min=120, length_min=30)
    assert active_minutes([a, b]) == 60.0


def test_merge_intervals_is_stable_when_unordered() -> None:
    spans = [
        Span(BASE + timedelta(hours=2), BASE + timedelta(hours=3)),
        Span(BASE, BASE + timedelta(hours=1)),
    ]
    merged = merge_intervals(spans)
    assert len(merged) == 2
    assert merged[0].start == BASE


def test_absurd_duration_is_discarded() -> None:
    """A resumed session can look like days of work. It is clock skew, not work."""
    session = _session("long", length_min=60 * 24 * 3)
    assert session.duration_minutes == 0.0


def test_median_not_mean_decides_focus() -> None:
    """One marathon should not relabel a week of quick check-ins as deep focus."""
    sessions = [_session(f"s{i}", start_min=i * 120, length_min=5) for i in range(6)]
    sessions.append(_session("marathon", start_min=2000, length_min=600))
    assert analyse(sessions).focus_label == "rapid fire"


# --------------------------------------------------------------------------
# Stuck detection: the intervention must be rare enough to be welcome.
# --------------------------------------------------------------------------


def test_stuck_needs_more_than_a_long_session() -> None:
    """Working a long time on one thing is focus, not being stuck."""
    session = _session(
        "focused",
        length_min=180,
        user_texts=[f"next step {i}" for i in range(20)],
    )
    assert detect_stuck([session]) == []


def test_repetition_plus_frustration_is_stuck() -> None:
    texts = ["the build still fails with the same error"] * 5 + ["still broken"] * 4
    session = _session("loop", length_min=120, user_texts=texts)
    signals = detect_stuck([session])
    assert signals and signals[0].severity >= 0.5


def test_short_session_is_never_stuck() -> None:
    session = _session("short", user_texts=["still broken"] * 3)
    assert detect_stuck([session]) == []


# --------------------------------------------------------------------------
# Distillation: what the model is allowed to put into memory.
# --------------------------------------------------------------------------


def test_belief_id_is_stable_across_rewordings_of_case_and_punctuation() -> None:
    a = _belief_id("preference", "Prefers small, reviewable commits.")
    b = _belief_id("preference", "prefers small reviewable commits")
    assert a == b


def test_different_claims_get_different_ids() -> None:
    a = _belief_id("preference", "Prefers small commits")
    b = _belief_id("preference", "Prefers large commits")
    assert a != b


def test_parses_json_wrapped_in_a_fence() -> None:
    raw = '```json\n[{"kind": "preference", "claim": "x"}]\n```'
    assert _parse_response(raw) == [{"kind": "preference", "claim": "x"}]


def test_parses_json_after_preamble() -> None:
    raw = 'Here is what I found:\n[{"kind": "pattern", "claim": "y"}]'
    assert _parse_response(raw)[0]["kind"] == "pattern"


def test_unparseable_response_yields_nothing_rather_than_raising() -> None:
    assert _parse_response("I could not find anything useful.") == []


def test_belief_with_invented_evidence_is_rejected() -> None:
    """A claim citing a session that does not exist cannot be justified to the user."""
    row = {
        "kind": "preference",
        "claim": "Writes tests before implementation, consistently",
        "confidence": 0.9,
        "evidence": ["session-that-never-existed"],
    }
    assert _to_belief(row, {"real-session"}) is None


def test_inferred_confidence_is_capped_below_measurement() -> None:
    row = {
        "kind": "pattern",
        "claim": "Always refactors before adding a feature, without exception",
        "confidence": 0.99,
        "evidence": ["real-session"],
    }
    belief = _to_belief(row, {"real-session"})
    assert belief is not None and belief.confidence <= 0.75


def test_unknown_kind_is_rejected() -> None:
    row = {"kind": "vibe", "claim": "Has excellent taste in editors", "evidence": ["real-session"]}
    assert _to_belief(row, {"real-session"}) is None


# --------------------------------------------------------------------------
# Store: evidence accumulates, corrections survive.
# --------------------------------------------------------------------------


def _store() -> JsonMemoryStore:
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    return JsonMemoryStore(tmp)


def test_seeing_a_belief_again_strengthens_rather_than_duplicates() -> None:
    store = _store()
    store.upsert(Belief(id="b1", kind="preference", claim="c", confidence=0.5, evidence=["s1"]))
    store.upsert(Belief(id="b1", kind="preference", claim="c", confidence=0.5, evidence=["s2"]))
    beliefs = store.all()
    assert len(beliefs) == 1
    assert beliefs[0].evidence_count == 2


def test_a_correction_outlives_later_rederivation() -> None:
    """The distiller will re-derive a wrong belief. The user's correction wins."""
    store = _store()
    store.upsert(Belief(id="b1", kind="preference", claim="c", confidence=0.5, evidence=["s1"]))
    corrected = store.get("b1")
    assert corrected is not None
    corrected.status = "corrected"
    corrected.user_feedback = "actually the opposite"
    store.upsert(corrected)

    store.upsert(Belief(id="b1", kind="preference", claim="c", confidence=0.7, evidence=["s3"]))
    again = store.get("b1")
    assert again is not None
    assert again.status == "corrected"
    assert again.user_feedback == "actually the opposite"


def test_corrupt_store_file_does_not_lose_the_agent() -> None:
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    tmp.write_text("{ this is not json", encoding="utf-8")
    store = JsonMemoryStore(tmp)
    assert store.all() == []
    store.upsert(Belief(id="b1", kind="goal", claim="ship it", confidence=0.5, evidence=["s1"]))
    assert len(store.all()) == 1


def test_store_survives_a_round_trip_through_disk() -> None:
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    JsonMemoryStore(tmp).upsert(
        Belief(id="b1", kind="friction", claim="slow CI", confidence=0.4, evidence=["s1"])
    )
    assert json.loads(tmp.read_text())["b1"]["claim"] == "slow CI"
    assert JsonMemoryStore(tmp).get("b1").claim == "slow CI"


# --------------------------------------------------------------------------
# Ingestion: only what a person actually said.
# --------------------------------------------------------------------------


def test_content_blocks_reduce_to_text() -> None:
    content = [
        {"type": "reasoning_trace", "text": "internal"},
        {"type": "text", "text": "the real question"},
        {"type": "tool_result", "content": "noise"},
    ]
    assert _flatten_content(content) == "the real question"


def test_transcript_keeps_the_end_of_the_session() -> None:
    """The outcome lives at the end, so truncation must drop the beginning."""
    session = _session("s", user_texts=[f"turn {i}" for i in range(40)])
    text = session.transcript(limit=3)
    assert "turn 39" in text
    assert "turn 0" not in text


def test_project_name_recovered_from_flattened_dir() -> None:
    """Claude Code sessions that ended without a cwd still belong to a project."""
    from amnesia.ingest.sessions import _project_from_dir

    assert _project_from_dir("-Users-me-src-backoffice") == "backoffice"
    assert _project_from_dir("") == "unknown"
    assert _project_from_dir("-") == "unknown"


def test_root_and_home_are_not_projects() -> None:
    """Clients write "/" when they do not know; that is not a project name."""
    from pathlib import Path

    from amnesia.ingest.sessions import _project_of

    assert _project_of("/") == "unknown"
    assert _project_of(str(Path.home())) == "unknown"
    assert _project_of("/Users/me/src/thing") == "thing"


def test_container_directories_are_not_projects() -> None:
    """"src" is where projects live, not a project someone works on."""
    from amnesia.ingest.sessions import _project_of

    assert _project_of("/Users/me/src") == "unknown"
    assert _project_of("/Users/me/code") == "unknown"


def test_unknown_is_not_counted_as_a_project() -> None:
    """Absence of a project must not become the top project on the card."""
    sessions = [
        _session("a", project="unknown"),
        _session("b", start_min=120, project="unknown"),
        _session("c", start_min=240, project="real-thing"),
    ]
    projects = analyse(sessions).projects
    assert [name for name, _ in projects] == ["real-thing"]


def test_stuck_signal_names_the_client_when_the_project_is_unknown() -> None:
    """"Stuck on unknown" tells a user nothing; the tool they used tells them something."""
    session = _session(
        "loop",
        length_min=120,
        project="unknown",
        user_texts=["the build still fails with the same error"] * 5 + ["still broken"] * 4,
    )
    session.client = "claude-code"
    signals = detect_stuck([session])
    assert signals and signals[0].project == "claude-code"


def test_card_line_is_clipped_on_a_word_boundary() -> None:
    """A line cut mid-word looks like a bug on an image about to be posted."""
    from amnesia.cards.card import _fit

    assert _fit("short line", 74) == "short line"
    clipped = _fit("your custom session-tracking hooks transform rapid sprints into bulletproof work", 40)
    assert len(clipped) <= 40
    assert clipped.endswith("…")
    assert not clipped[:-1].endswith(" ")
