"""The agent: what it knows, what it asks, and what it learns.

The track asks for a partner that leads, asks clarifying questions and captures
feedback. The design follows from one observation: a generic assistant asks
generic questions, because it starts from nothing. Amnesia starts from what it
already believes about you, so its questions are about the gaps, and answering
one permanently removes it.

The tool surface is deliberately small and each tool does one thing, so the
model's reasoning chain stays legible in traces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from amnesia.ingest.sessions import collect_sessions
from amnesia.memory.analytics import WorkingStyle, analyse, detect_stuck
from amnesia.memory.distill import _belief_id, distill
from amnesia.memory.store import Belief, get_store
from amnesia.settings import settings

SYSTEM_PROMPT = """You are Amnesia, the persistent memory and working partner of one developer.

You already know things about this person, listed under WHAT YOU KNOW. Never
ask about something you already know; refer to it instead, so they can feel
that you remember.

How you work:
1. Ground yourself in what you know before answering anything.
2. If the task is underspecified, ask ONE sharp clarifying question that your
   memory cannot already answer. One question, not a list.
3. Point out relevant friction you have observed before, unprompted.
4. When they tell you something new about how they work, call remember_this.
5. When they correct you, call correct_belief. A correction outranks anything
   you inferred.

Be brief. You are a colleague who has worked with them for months, not a
chatbot meeting them for the first time.

WHAT YOU KNOW:
{memory}

MEASURED FACTS (counted, not guessed):
{facts}
"""


@dataclass
class AgentReply:
    text: str
    tool_calls: list[str] = field(default_factory=list)
    memory_used: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Tools. Each is a plain function so it can be unit-tested without a model,
# and each returns a string because that is what the model consumes.
# --------------------------------------------------------------------------


def recall(topic: str = "") -> str:
    """Return what is known about the user, optionally filtered by topic."""
    beliefs = [b for b in get_store().all() if b.status == "active"]
    if topic:
        needle = topic.lower()
        beliefs = [
            b
            for b in beliefs
            if needle in b.claim.lower() or any(needle in p.lower() for p in b.projects)
        ]
    if not beliefs:
        return "Nothing known yet. Run a distill pass over recent sessions first."
    # Evidence before confidence: a claim seen in five sessions beats one the
    # model merely felt strongly about.
    ranked = sorted(beliefs, key=lambda b: (b.evidence_count, b.confidence), reverse=True)
    return "\n".join(
        f"- [{b.kind}] {b.claim} (confidence {b.confidence}, {b.evidence_count} sessions)"
        for b in ranked[:12]
    )


def remember_this(claim: str, kind: str = "preference", confidence: float = 0.9) -> str:
    """Store something the user stated directly about how they work.

    Stated facts are trusted far above distilled ones: the person is the
    authority on their own preferences, so this is allowed above the inference
    ceiling.
    """
    belief = Belief(
        id=_belief_id(kind, claim),
        kind=kind,
        claim=claim.strip(),
        confidence=min(confidence, 0.95),
        evidence=[f"stated-by-user:{_now()}"],
    )
    get_store().upsert(belief)
    return f"Remembered: {belief.claim}"


def correct_belief(belief_id: str, correction: str) -> str:
    """Record that a belief was wrong, and why.

    The old belief is marked corrected rather than deleted. Keeping the mistake
    is what lets the system explain itself later, and what stops the next
    distill pass from confidently re-deriving it.
    """
    store = get_store()
    belief = store.get(belief_id)
    if not belief:
        return f"No belief with id {belief_id}."
    belief.status = "corrected"
    belief.user_feedback = correction
    belief.confidence = 0.1
    store.upsert(belief)

    replacement = Belief(
        id=_belief_id(belief.kind, correction),
        kind=belief.kind,
        claim=correction.strip(),
        confidence=0.95,
        evidence=[f"correction-of:{belief_id}"],
    )
    store.upsert(replacement)
    return f"Corrected. Replaced with: {replacement.claim}"


def check_stuck(limit: int = 20) -> str:
    """Report sessions that look like the user was going in circles."""
    signals = detect_stuck(collect_sessions(limit=limit))
    if not signals:
        return "No stuck patterns in recent sessions."
    return "\n".join(
        f"- {s.project} (severity {s.severity}): {s.reason}" for s in signals[:5]
    )


def measured_facts(limit: int = 40) -> tuple[WorkingStyle, str]:
    """Counted facts about recent work, as text for the prompt."""
    style = analyse(collect_sessions(limit=limit))
    text = (
        f"- {style.total_sessions} sessions over {style.span_days} days, "
        f"{style.active_hours} active hours (overlapping sessions counted once)\n"
        f"- Chronotype: {style.chronotype}, peak hour {style.peak_hour}:00 local\n"
        f"- Rhythm: {style.focus_label}, median session {style.median_session_minutes} min\n"
        f"- Projects: {', '.join(f'{n} ({c})' for n, c in style.projects[:5])}\n"
        f"- Clients: {', '.join(f'{n} ({c})' for n, c in style.clients)}\n"
        f"- Project switches between consecutive sessions: {style.context_switches}"
    )
    return style, text


TOOLS = {
    "recall": recall,
    "remember_this": remember_this,
    "correct_belief": correct_belief,
    "check_stuck": check_stuck,
}

TOOL_SCHEMA = [
    {
        "name": "recall",
        "description": "Look up what is already known about the user before asking them anything.",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "Optional filter."}},
        },
    },
    {
        "name": "remember_this",
        "description": "Store a new fact the user stated about how they work.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["preference", "pattern", "expertise", "friction", "goal"],
                },
            },
            "required": ["claim"],
        },
    },
    {
        "name": "correct_belief",
        "description": "Mark a belief wrong and replace it with what the user says is true.",
        "parameters": {
            "type": "object",
            "properties": {
                "belief_id": {"type": "string"},
                "correction": {"type": "string"},
            },
            "required": ["belief_id", "correction"],
        },
    },
    {
        "name": "check_stuck",
        "description": "Check recent sessions for signs the user was going in circles.",
        "parameters": {"type": "object", "properties": {}},
    },
]


class AmnesiaAgent:
    """Gemini agent with memory, tools and a bias toward asking one good question."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=settings.use_vertex or None,
                api_key=settings.google_api_key or None,
                project=settings.project or None,
                location=settings.location if settings.use_vertex else None,
            )
        return self._client

    def system_prompt(self) -> str:
        _, facts = measured_facts()
        return SYSTEM_PROMPT.format(memory=recall(), facts=facts)

    def chat(self, message: str, history: list[dict] | None = None) -> AgentReply:
        if not settings.has_model_access:
            # Without a key the agent still answers from memory. A judge who
            # skips credentials should see memory work, not a stack trace.
            return AgentReply(
                text=(
                    "No Gemini credentials configured, answering from memory only.\n\n"
                    + recall(message)
                ),
                memory_used=len(get_store().all()),
            )

        from google.genai import types

        client = self._get_client()
        contents = []
        for turn in history or []:
            contents.append(
                types.Content(
                    role=turn.get("role", "user"),
                    parts=[types.Part(text=str(turn.get("text", "")))],
                )
            )
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt(),
            tools=[types.Tool(function_declarations=TOOL_SCHEMA)],
            temperature=0.7,
        )

        called: list[str] = []
        # Bounded loop rather than while-true: a tool loop that cannot end is
        # the classic way an agent burns a budget in the background.
        for _ in range(4):
            try:
                response = client.models.generate_content(
                    model=settings.model, contents=contents, config=config
                )
            except Exception as exc:  # noqa: BLE001
                return AgentReply(text=f"Model call failed: {exc}", tool_calls=called)

            calls = getattr(response, "function_calls", None) or []
            if not calls:
                return AgentReply(
                    text=response.text or "(no reply)",
                    tool_calls=called,
                    memory_used=len(get_store().all()),
                )

            contents.append(response.candidates[0].content)
            parts = []
            for call in calls:
                fn = TOOLS.get(call.name)
                args = dict(call.args or {})
                called.append(f"{call.name}({json.dumps(args, ensure_ascii=False)[:80]})")
                try:
                    result = fn(**args) if fn else f"Unknown tool {call.name}"
                except Exception as exc:  # noqa: BLE001 - report, do not abort the turn
                    result = f"Tool error: {exc}"
                parts.append(
                    types.Part.from_function_response(name=call.name, response={"result": result})
                )
            contents.append(types.Content(role="user", parts=parts))

        return AgentReply(text="Stopped after too many tool calls.", tool_calls=called)


def run_distill_pass(limit: int | None = None) -> dict:
    """One background pass: read sessions, distill beliefs, flag stuck work."""
    sessions = collect_sessions(limit=limit or settings.distill_batch)
    result = distill(sessions)
    stuck = detect_stuck(sessions)
    return {
        "sessions_read": result.sessions_read,
        "beliefs_learned": len(result.beliefs),
        "claims": [b.claim for b in result.beliefs],
        "stuck_signals": [
            {"project": s.project, "severity": s.severity, "reason": s.reason} for s in stuck[:5]
        ],
        "error": result.error,
        "ran_at": _now(),
    }
