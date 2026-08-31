"""Sessions uploaded from a laptop to a deployed instance.

A deployed Amnesia cannot read transcript files on someone's machine, so the
laptop pushes normalised sessions instead.

Where they are kept matters more than it looks. Cloud Run containers are
disposable: the first version wrote them to the container filesystem, and the
next revision started with an empty history, so the deployed agent silently
forgot everything it had been given. Uploaded sessions now go to the same store
as beliefs, which means Firestore in the cloud and a file locally.

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


# --------------------------------------------------------------------------
# Firestore backend, used when the service runs in the cloud
# --------------------------------------------------------------------------


def _collection():
    from google.cloud import firestore

    client = firestore.Client(project=settings.project or None)
    # A sibling of the beliefs collection rather than a subcollection: sessions
    # are evidence, beliefs are conclusions, and they are read at different
    # times by different code.
    return client.collection(f"{settings.firestore_collection}_sessions")


def _save_firestore(rows: list[dict]) -> int:
    col = _collection()
    added = 0
    for row in rows:
        session = _from_payload(row) if isinstance(row, dict) else None
        if not session:
            continue
        col.document(session.id).set(_serialise(session))
        added += 1
    return added


def _load_firestore() -> list[Session]:
    return [s for s in (_from_payload(doc.to_dict()) for doc in _collection().stream()) if s]


# --------------------------------------------------------------------------
# File backend, used locally
# --------------------------------------------------------------------------


def _cache_path() -> Path:
    return settings.local_store_path.parent / "sessions.json"


def _save_file(rows: list[dict]) -> int:
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


def _load_file() -> list[Session]:
    path = _cache_path()
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(rows, dict):
        return []
    return [s for s in (_from_payload(r) for r in rows.values()) if s]


# --------------------------------------------------------------------------
# Public interface. Firestore when configured, file otherwise, and file as the
# fallback when Firestore is unreachable: an upload that half-works is worse
# than one that lands somewhere.
# --------------------------------------------------------------------------


def save_uploaded(rows: list[dict]) -> int:
    if settings.firestore_enabled:
        try:
            return _save_firestore(rows)
        except Exception as exc:  # noqa: BLE001
            print(f"[amnesia] Firestore write failed ({exc}); falling back to file")
    return _save_file(rows)


def load_uploaded() -> list[Session]:
    sessions: list[Session] = []
    if settings.firestore_enabled:
        try:
            sessions = _load_firestore()
        except Exception as exc:  # noqa: BLE001
            print(f"[amnesia] Firestore read failed ({exc}); falling back to file")
    if not sessions:
        sessions = _load_file()
    sessions.sort(
        key=lambda s: s.ended_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )
    return sessions
