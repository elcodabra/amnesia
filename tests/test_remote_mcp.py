"""Tests for the remote MCP transport.

ChatGPT connects to a URL rather than spawning a process, and it refuses a
connector that does not expose `search` and `fetch` by those exact names. That
requirement is invisible until a connection is rejected with no useful error,
so it is asserted here.
"""

from __future__ import annotations

import json

import pytest

from amnesia.mcp.remote import REMOTE_TOOLS, as_sse, handle_remote
from amnesia.memory.store import Belief


@pytest.fixture(autouse=True)
def _memory(monkeypatch, tmp_path):
    """A store with one known belief, so search and fetch have something real."""
    import amnesia.memory.store as store_mod
    from amnesia.memory.store import JsonMemoryStore

    store = JsonMemoryStore(tmp_path / "memory.json")
    store.upsert(
        Belief(
            id="friction-abc",
            kind="friction",
            claim="Node version drifts from .nvmrc and breaks installs",
            confidence=0.7,
            evidence=["s1", "s2"],
            projects=["backoffice"],
        )
    )
    monkeypatch.setattr(store_mod, "_store", store)
    return store


def _call(name: str, **arguments) -> str:
    response = handle_remote(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    return response["result"]["content"][0]["text"]


def test_chatgpt_required_tools_are_present_and_first() -> None:
    """ChatGPT rejects a connector without search and fetch."""
    names = [t["name"] for t in REMOTE_TOOLS]
    assert names[:2] == ["search", "fetch"]


def test_every_tool_declares_a_schema() -> None:
    assert all("inputSchema" in t and t["description"] for t in REMOTE_TOOLS)


def test_initialize_reports_the_protocol_version() -> None:
    response = handle_remote({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["protocolVersion"]
    assert response["result"]["serverInfo"]["name"] == "amnesia"


def test_notifications_get_no_response() -> None:
    assert handle_remote({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_search_returns_ids_that_fetch_accepts() -> None:
    """Search is useless to a model if it cannot then open a result."""
    found = _call("search", query="node")
    assert "friction-abc" in found
    detail = _call("fetch", id="friction-abc")
    assert ".nvmrc" in detail
    assert "2 sessions" in detail


def test_search_without_a_match_still_shows_what_is_known() -> None:
    """An empty result reads to the model as "this person has no memory"."""
    assert "friction-abc" in _call("search", query="nothing matches this at all")


def test_fetch_explains_why_confidence_is_capped() -> None:
    assert "capped below measurement" in _call("fetch", id="friction-abc")


def test_fetch_of_a_missing_id_is_a_message_not_a_crash() -> None:
    assert "No belief with id" in _call("fetch", id="does-not-exist")


def test_unknown_tool_is_a_protocol_error() -> None:
    response = handle_remote(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nope"}}
    )
    assert response["error"]["code"] == -32601


def test_stdio_tools_are_reachable_over_http_too() -> None:
    """The two transports must not drift on the tools they share."""
    assert "sessions" in _call("how_i_work").lower()


def test_sse_frame_is_well_formed() -> None:
    frame = as_sse({"jsonrpc": "2.0", "id": 1, "result": {}})
    assert frame.startswith("event: message\ndata: ")
    assert frame.endswith("\n\n")
    body = frame.split("data: ", 1)[1].strip()
    assert json.loads(body)["jsonrpc"] == "2.0"


def test_recency_questions_get_sessions_not_beliefs(monkeypatch) -> None:
    """Observed live: ChatGPT asked three recency questions in a row.

    Each returned the same evidence-ranked beliefs, so it rephrased and tried
    again instead of answering. "What did I do recently" is a question about
    time, and beliefs are ordered by evidence, which is the wrong axis.
    """
    from datetime import datetime, timezone

    import amnesia.mcp.remote as remote
    from amnesia.ingest.sessions import Session, Turn

    session = Session(
        id="s-recent",
        client="cursor",
        project="backoffice",
        started_at=datetime(2026, 8, 30, 10, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 30, 11, tzinfo=timezone.utc),
        turns=[Turn(role="user", text="fix the failing checkout test")],
    )
    monkeypatch.setattr(
        "amnesia.ingest.sessions.collect_sessions", lambda limit=10: [session]
    )

    for question in (
        "my most recent activities, newest first",
        "what did I work on lately",
        "what did I do today",
    ):
        answer = remote._search(question)
        assert "s-recent" in answer, question
        assert "checkout test" in answer, question
        assert "2026-08-30" in answer, question


def test_topic_questions_still_return_beliefs() -> None:
    """Fixing recency must not break the question the tool was built for."""
    from amnesia.mcp.remote import _search

    assert "friction-abc" in _search("nvmrc")


def test_recency_falls_back_to_beliefs_when_no_sessions(monkeypatch) -> None:
    """An empty answer reads as "no memory"; showing what is known is better."""
    import amnesia.mcp.remote as remote

    monkeypatch.setattr("amnesia.ingest.sessions.collect_sessions", lambda limit=10: [])
    assert "friction-abc" in remote._search("what did I do recently")
