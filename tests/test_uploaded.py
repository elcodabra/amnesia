"""Tests for sessions pushed from a laptop to a deployed instance.

This path only matters in the cloud, which is exactly why it needs tests: it is
the one part of the system that cannot be checked by running the app locally
and looking at it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import amnesia.ingest.uploaded as uploaded
from amnesia.settings import Settings


def _isolate(monkeypatch) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    monkeypatch.setattr(uploaded, "settings", Settings(local_store_path=tmp))
    return tmp


ONE = {
    "id": "s1",
    "client": "cursor",
    "project": "demo",
    "started_at": "2026-08-30T10:00:00Z",
    "ended_at": "2026-08-30T11:00:00Z",
    "turns": [{"role": "user", "text": "add rate limiting"}],
}


def test_upload_then_read_back(monkeypatch) -> None:
    _isolate(monkeypatch)
    assert uploaded.save_uploaded([ONE]) == 1
    sessions = uploaded.load_uploaded()
    assert len(sessions) == 1
    assert sessions[0].client == "cursor"
    assert sessions[0].duration_minutes == 60.0


def test_reupload_updates_rather_than_duplicates(monkeypatch) -> None:
    """A laptop re-uploading its history must not double every session."""
    _isolate(monkeypatch)
    uploaded.save_uploaded([ONE])
    uploaded.save_uploaded([ONE])
    assert len(uploaded.load_uploaded()) == 1


def test_session_without_turns_is_dropped(monkeypatch) -> None:
    _isolate(monkeypatch)
    assert uploaded.save_uploaded([{"id": "empty", "turns": []}]) == 0
    assert uploaded.load_uploaded() == []


def test_malformed_rows_do_not_break_the_batch(monkeypatch) -> None:
    _isolate(monkeypatch)
    assert uploaded.save_uploaded(["not a dict", {"no": "id"}, ONE]) == 1


def test_missing_cache_reads_as_empty(monkeypatch) -> None:
    _isolate(monkeypatch)
    assert uploaded.load_uploaded() == []
