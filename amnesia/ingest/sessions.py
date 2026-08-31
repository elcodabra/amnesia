"""Reading real AI coding sessions off this machine.

Amnesia's premise is that the evidence about how someone works already exists:
every AI coding client writes a transcript. Nothing needs to be installed, and
no new tracking is introduced. We read what is already on disk.

Each client is read by a small adapter that knows only its own layout, and all
of them produce the same :class:`Session`, so the rest of the system never
learns which tool a session came from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

# Long transcripts are cheap to read and expensive to send to a model. Each
# turn is clipped: the shape of a session survives truncation, and the
# distiller reads for pattern rather than for detail.
MAX_TURN_CHARS = 2_000
MAX_TURNS_PER_SESSION = 60


@dataclass
class Turn:
    role: str
    text: str
    at: datetime | None = None


@dataclass
class Session:
    """One AI coding session, normalised across clients."""

    id: str
    client: str
    project: str
    started_at: datetime | None
    ended_at: datetime | None
    turns: list[Turn] = field(default_factory=list)
    model: str | None = None

    @property
    def duration_minutes(self) -> float:
        if not self.started_at or not self.ended_at:
            return 0.0
        secs = (self.ended_at - self.started_at).total_seconds()
        # A negative or absurd span means clock skew or a resumed session, not
        # a month of continuous work. Discard rather than let it poison totals.
        return round(secs / 60, 1) if 0 <= secs <= 60 * 60 * 12 else 0.0

    @property
    def user_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "user"]

    def transcript(self, limit: int = MAX_TURNS_PER_SESSION) -> str:
        """Readable transcript for the model, newest turns kept.

        The end of a session is where the outcome is: whether the bug was
        fixed, whether the user gave up, what they asked for last.
        """
        kept = self.turns[-limit:]
        lines = [f"{t.role}: {t.text[:MAX_TURN_CHARS]}" for t in kept if t.text.strip()]
        return "\n".join(lines)


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _flatten_content(content: object) -> str:
    """Turn a client's content payload into plain text.

    Tool calls, reasoning traces and images are dropped. What is left is what a
    person actually said and what the assistant actually replied, which is the
    only part that says anything about how someone works.
    """
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(p.strip() for p in parts if p.strip()).strip()


def _project_of(path: str | None) -> str:
    if not path:
        return "unknown"
    return Path(path).name or "unknown"


# --------------------------------------------------------------------------
# jcode
# --------------------------------------------------------------------------


def read_jcode_sessions(root: Path | None = None) -> Iterator[Session]:
    root = root or Path.home() / ".jcode" / "sessions"
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(raw, dict) or not isinstance(raw.get("messages"), list):
            continue

        turns: list[Turn] = []
        for msg in raw["messages"]:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            text = _flatten_content(msg.get("content"))
            # A session's own system reminders describe the harness, not the
            # person. Left in, the distiller "learns" the boilerplate.
            if not text or text.startswith("<system-reminder>"):
                continue
            turns.append(Turn(role=role, text=text, at=_parse_ts(msg.get("timestamp"))))

        if not turns:
            continue
        # `last_active_at` tracks the process, not the conversation, and on a
        # resumed session it can predate the final turn, which reads as a
        # zero-length session. The turns themselves are the honest bound.
        stamps = [t.at for t in turns if t.at]
        yield Session(
            id=str(raw.get("id") or path.stem),
            client="jcode",
            project=_project_of(raw.get("working_dir")),
            started_at=min(stamps) if stamps else _parse_ts(raw.get("created_at")),
            ended_at=max(stamps) if stamps else _parse_ts(raw.get("updated_at")),
            turns=turns,
            model=raw.get("model"),
        )


# --------------------------------------------------------------------------
# Claude Code
# --------------------------------------------------------------------------


def read_claude_sessions(root: Path | None = None) -> Iterator[Session]:
    root = root or Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        turns: list[Turn] = []
        cwd: str | None = None
        model: str | None = None
        stamps: list[datetime] = []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or rec.get("type") not in ("user", "assistant"):
                continue
            cwd = cwd or rec.get("cwd")
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            model = model or msg.get("model")
            text = _flatten_content(msg.get("content"))
            if not text:
                continue
            at = _parse_ts(rec.get("timestamp"))
            if at:
                stamps.append(at)
            turns.append(Turn(role=str(rec.get("type")), text=text, at=at))

        if not turns:
            continue
        yield Session(
            id=path.stem,
            client="claude-code",
            project=_project_of(cwd),
            started_at=min(stamps) if stamps else None,
            ended_at=max(stamps) if stamps else None,
            turns=turns,
            model=model,
        )


# --------------------------------------------------------------------------
# Codex
# --------------------------------------------------------------------------


def read_codex_sessions(root: Path | None = None) -> Iterator[Session]:
    root = root or Path.home() / ".codex" / "sessions"
    if not root.is_dir():
        return
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        turns: list[Turn] = []
        stamps: list[datetime] = []
        cwd: str | None = None
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            cwd = cwd or rec.get("cwd")
            payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else rec
            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue
            text = _flatten_content(payload.get("content"))
            if not text:
                continue
            at = _parse_ts(rec.get("timestamp") or payload.get("timestamp"))
            if at:
                stamps.append(at)
            turns.append(Turn(role=str(role), text=text, at=at))

        if not turns:
            continue
        yield Session(
            id=path.stem,
            client="codex",
            project=_project_of(cwd),
            started_at=min(stamps) if stamps else None,
            ended_at=max(stamps) if stamps else None,
            turns=turns,
        )


READERS = {
    "jcode": read_jcode_sessions,
    "claude-code": read_claude_sessions,
    "codex": read_codex_sessions,
}


def collect_sessions(limit: int = 40, clients: Iterable[str] | None = None) -> list[Session]:
    """Newest sessions available to this instance.

    Locally that means transcripts on disk. On Cloud Run there are no local
    transcripts, so it means whatever a laptop has uploaded. Both are read and
    merged rather than chosen between, because a developer running the service
    locally against an uploaded history should see one timeline, not two.

    Interleaved by recency rather than concatenated per client, so a limit does
    not silently mean "only jcode".
    """
    wanted = list(clients) if clients else list(READERS)
    found: list[Session] = []
    for name in wanted:
        reader = READERS.get(name)
        if not reader:
            continue
        for session in reader():
            found.append(session)
            # Read a generous slice per client, then sort globally: a client
            # that has been quiet should not crowd out a busy one.
            if len([s for s in found if s.client == name]) >= limit:
                break

    # Imported here rather than at module scope: the uploaded cache imports
    # settings, and settings must stay free to import this module.
    from amnesia.ingest.uploaded import load_uploaded

    seen = {s.id for s in found}
    found.extend(s for s in load_uploaded() if s.id not in seen)

    found.sort(key=lambda s: s.ended_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return found[:limit]
