"""Sessions uploaded from a laptop to a deployed instance.

A deployed Amnesia cannot read transcript files on someone's machine, so the
laptop pushes normalised sessions instead. They are kept in the same store as
beliefs, which means one backend to configure and one thing to back up.

This is also the honest privacy boundary: what leaves the machine is turns of
conversation, already stripped of tool output, file contents and reasoning
traces by the ingest layer.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from amnesia.ingest.sessions import Session, Turn, _parse_ts
from amnesia.settings import settings


def _cache_path() -> Path:
    return settings.local_store_path.parent / "sessions.json"


def _from_payload(row: dict) -> Session | None:
    sid = str(row.get("id") or "").strip()
    if not sid:
        return None
    turns = [
        Turn(role=str(t.get("role", "user")), text=str(t.get("text", "")))
        for t in row.get("turns", [])
        if isinstance(t, dict) and str(t.get("text", "")).strip()
    ]
    if not turns:
        return None
    return Session(
        id=sid,
        client=str(row.get("client", "unknown")),
        project=str(row.get("project", "unknown")),
        started_at=_parse_ts(row.get("started_at")),
        ended_at=_parse_ts(row.get("ended_at")),
        turns=turns,
    )


def _serialise(session: Session) -> dict:
    return {
        "id": session.id,
        "client": session.client,
        "project": session.project,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "turns": [{"role": t.role, "text": t.text} for t in session.turns],
    }


def save_uploaded(rows: list[dict]) -> int:
    """Merge uploaded sessions into the cache, keyed by session id."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, dict] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = {}

    added = 0
    for row in rows:
        session = _from_payload(row) if isinstance(row, dict) else None
        if session:
            existing[session.id] = _serialise(session)
            added += 1

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return added


def load_uploaded() -> list[Session]:
    path = _cache_path()
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(rows, dict):
        return []
    sessions = [s for s in (_from_payload(r) for r in rows.values()) if s]
    sessions.sort(
        key=lambda s: s.ended_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )
    return sessions
