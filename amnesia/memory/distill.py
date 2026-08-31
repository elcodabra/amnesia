"""Turning raw sessions into beliefs, using Gemini.

This is the part that makes Amnesia more than a log viewer. A transcript says
what happened; a belief says what it means. The distiller reads a batch of
sessions and proposes a small number of durable claims about how this person
works.

Two constraints shape the prompt:

* **Every claim must cite sessions.** A claim with no evidence cannot be shown
  to the user honestly, and it cannot be corrected.
* **Inference stays below measurement.** Confidence is capped, because a model
  reading six transcripts is guessing, and a guess must never outrank a
  counted fact when the two are ranked together.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from amnesia.ingest.sessions import Session
from amnesia.memory.store import BELIEF_KINDS, Belief, get_store
from amnesia.settings import settings

# Ceiling on anything a model inferred from transcripts. Measured facts (hours
# worked, projects touched) are counted, not inferred, and are allowed above it.
MAX_INFERRED_CONFIDENCE = 0.75

DISTILL_PROMPT = """You are the memory of a personal AI assistant.

Below are real AI coding sessions belonging to one developer. Your job is to
extract durable facts about HOW THIS PERSON WORKS: things that will still be
true next month and that would help another AI assistant work with them well.

Rules:
- Extract at most {max_beliefs} claims. Fewer, sharper claims beat many vague ones.
- Each claim must be specific enough to be wrong. "Likes clean code" is useless;
  "Rejects code comments that restate the code, asks for the reason instead" is useful.
- Never describe a single incident. A claim must be a pattern across the material.
- Never include secrets, credentials, file contents or personal identifiers.
- Cite the session ids that support each claim.
- kind must be one of: {kinds}

Return ONLY a JSON array, no prose, no markdown fence:
[
  {{"kind": "preference", "claim": "...", "confidence": 0.6, "evidence": ["session-id"], "projects": ["repo"]}}
]

SESSIONS:
{sessions}
"""


@dataclass
class DistillResult:
    beliefs: list[Belief]
    sessions_read: int
    model_used: str | None
    error: str | None = None


def _belief_id(kind: str, claim: str) -> str:
    """Stable id from the claim itself.

    Keyed by content rather than by run, so restating a belief in a later pass
    strengthens the existing one instead of creating a near-duplicate. The
    claim is normalised first: punctuation and case should not fork a belief.
    """
    normalised = re.sub(r"[^a-z0-9 ]", "", claim.lower()).strip()
    normalised = re.sub(r"\s+", " ", normalised)
    digest = hashlib.sha256(f"{kind}:{normalised}".encode()).hexdigest()[:16]
    return f"{kind}-{digest}"


def _render_sessions(sessions: list[Session]) -> str:
    blocks = []
    for s in sessions:
        header = (
            f"### session_id={s.id} client={s.client} project={s.project} "
            f"minutes={s.duration_minutes} turns={len(s.turns)}"
        )
        blocks.append(f"{header}\n{s.transcript(limit=24)}")
    return "\n\n".join(blocks)


def _parse_response(text: str) -> list[dict]:
    """Read the model's JSON, tolerating the ways models wrap it.

    Asking for bare JSON works most of the time; a fenced block or a sentence
    of preamble is common enough that failing on it would make the pipeline
    flaky for no reason.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    return [row for row in parsed if isinstance(row, dict)] if isinstance(parsed, list) else []


def _to_belief(row: dict, known_sessions: set[str]) -> Belief | None:
    kind = str(row.get("kind", "")).strip().lower()
    claim = str(row.get("claim", "")).strip()
    if kind not in BELIEF_KINDS or len(claim) < 15:
        return None

    try:
        confidence = float(row.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    # Only evidence we can actually resolve. A model that invents a session id
    # produces a claim the UI cannot justify, which is worse than no claim.
    evidence = [e for e in row.get("evidence", []) if isinstance(e, str) and e in known_sessions]
    if not evidence:
        return None

    return Belief(
        id=_belief_id(kind, claim),
        kind=kind,
        claim=claim,
        confidence=round(min(max(confidence, 0.1), MAX_INFERRED_CONFIDENCE), 2),
        evidence=evidence,
        projects=[p for p in row.get("projects", []) if isinstance(p, str)][:5],
    )


def distill(sessions: list[Session], max_beliefs: int = 8, persist: bool = True) -> DistillResult:
    """Read sessions, propose beliefs, and store them with their evidence."""
    if not sessions:
        return DistillResult(beliefs=[], sessions_read=0, model_used=None, error="no sessions found")
    if not settings.has_model_access:
        return DistillResult(
            beliefs=[],
            sessions_read=len(sessions),
            model_used=None,
            error="no Gemini credentials: set GOOGLE_API_KEY or use Vertex AI",
        )

    from google import genai

    client = genai.Client(
        vertexai=settings.use_vertex or None,
        api_key=settings.google_api_key or None,
        project=settings.project or None,
        location=settings.location if settings.use_vertex else None,
    )
    prompt = DISTILL_PROMPT.format(
        max_beliefs=max_beliefs,
        kinds=", ".join(BELIEF_KINDS),
        sessions=_render_sessions(sessions),
    )

    try:
        response = client.models.generate_content(model=settings.model, contents=prompt)
        text = response.text or ""
    except Exception as exc:  # noqa: BLE001 - a failed pass must not kill the job
        return DistillResult(
            beliefs=[], sessions_read=len(sessions), model_used=settings.model, error=str(exc)
        )

    known = {s.id for s in sessions}
    beliefs: list[Belief] = []
    for row in _parse_response(text):
        belief = _to_belief(row, known)
        if belief:
            beliefs.append(belief)

    if persist:
        store = get_store()
        for belief in beliefs:
            store.upsert(belief)

    return DistillResult(beliefs=beliefs, sessions_read=len(sessions), model_used=settings.model)
