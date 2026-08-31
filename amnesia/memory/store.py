"""The memory Amnesia keeps, and where it is kept.

Two ideas hold this together.

**Every belief carries evidence.** A memory without provenance cannot be
corrected, because there is nothing to point at when it is wrong. So each
:class:`Belief` records which sessions produced it, and the UI can always
answer "why do you think that about me".

**The store is swappable.** Firestore in production, a JSON file locally. The
agent never learns which one it has, so a judge with no Google Cloud account
runs exactly the code that runs in the cloud.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from amnesia.settings import settings

# What Amnesia is allowed to believe about someone. A closed vocabulary keeps
# the distiller from inventing categories that no part of the UI can render.
BELIEF_KINDS = (
    "preference",  # how they want work done
    "pattern",  # how they actually work
    "expertise",  # what they know
    "friction",  # what repeatedly costs them time
    "goal",  # what they are trying to reach
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Belief:
    """One thing Amnesia believes about the user, with its evidence."""

    id: str
    kind: str
    claim: str
    # 0..1. Distilled inference is capped below measurement elsewhere in the
    # system: a guess must never outrank a count.
    confidence: float
    evidence: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    # Set when the user corrects a belief. Corrections are kept rather than
    # deleted: knowing what was wrong is what makes the next guess better.
    status: str = "active"
    user_feedback: str | None = None

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)


class MemoryStore(Protocol):
    def upsert(self, belief: Belief) -> None: ...
    def all(self) -> list[Belief]: ...
    def get(self, belief_id: str) -> Belief | None: ...


class JsonMemoryStore:
    """File-backed store. The local default, and the fallback in the cloud."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.local_store_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # A background distiller and a web request can write at the same time,
        # and a torn JSON file loses every belief at once.
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, dict]) -> None:
        # Write-then-rename: a crash mid-write leaves the previous file intact
        # rather than a half-written one.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, belief: Belief) -> None:
        with self._lock:
            data = self._read()
            existing = data.get(belief.id)
            if existing:
                # Merge evidence rather than replace it. A belief seen again in
                # a new session is better supported, not restated.
                merged = list(dict.fromkeys([*existing.get("evidence", []), *belief.evidence]))
                belief.evidence = merged
                belief.created_at = existing.get("created_at", belief.created_at)
                # A correction the user made outlives a later re-derivation.
                if existing.get("status") == "corrected":
                    belief.status = "corrected"
                    belief.user_feedback = existing.get("user_feedback")
            belief.updated_at = _now()
            data[belief.id] = asdict(belief)
            self._write(data)

    def all(self) -> list[Belief]:
        return [Belief(**row) for row in self._read().values()]

    def get(self, belief_id: str) -> Belief | None:
        row = self._read().get(belief_id)
        return Belief(**row) if row else None


class FirestoreMemoryStore:
    """Firestore-backed store, used when running on Google Cloud."""

    def __init__(self, collection: str | None = None) -> None:
        from google.cloud import firestore  # imported lazily: optional dependency

        self._client = firestore.Client(project=settings.project or None)
        self._col = self._client.collection(collection or settings.firestore_collection)

    def upsert(self, belief: Belief) -> None:
        doc = self._col.document(belief.id)
        snapshot = doc.get()
        if snapshot.exists:
            existing = snapshot.to_dict() or {}
            belief.evidence = list(
                dict.fromkeys([*existing.get("evidence", []), *belief.evidence])
            )
            belief.created_at = existing.get("created_at", belief.created_at)
            if existing.get("status") == "corrected":
                belief.status = "corrected"
                belief.user_feedback = existing.get("user_feedback")
        belief.updated_at = _now()
        doc.set(asdict(belief))

    def all(self) -> list[Belief]:
        return [Belief(**doc.to_dict()) for doc in self._col.stream()]

    def get(self, belief_id: str) -> Belief | None:
        snapshot = self._col.document(belief_id).get()
        return Belief(**snapshot.to_dict()) if snapshot.exists else None


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    """The process-wide store, chosen once from configuration.

    Firestore failures fall back to the file store instead of taking the agent
    down: a demo that cannot reach Firestore should still remember.
    """
    global _store
    if _store is not None:
        return _store
    if settings.firestore_enabled:
        try:
            _store = FirestoreMemoryStore()
            return _store
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the agent
            print(f"[amnesia] Firestore unavailable ({exc}); using local store")
    _store = JsonMemoryStore()
    return _store
