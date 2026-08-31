"""Facts that are counted, not inferred.

Everything here is arithmetic over session metadata. That matters for two
reasons: it works with no model and no network, so the agent is never empty on
a first run, and it gives the ranking layer something a language model cannot
outrank. When a measured fact and a distilled belief disagree, the measurement
wins.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from amnesia.ingest.sessions import Session


@dataclass
class Span:
    start: datetime
    end: datetime


def merge_intervals(spans: list[Span]) -> list[Span]:
    """Union of overlapping spans.

    Summing session durations double-counts every parallel session, and running
    two agents at once is normal. Someone with three clients open for an hour
    worked one hour, not three.
    """
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: s.start)
    merged = [ordered[0]]
    for span in ordered[1:]:
        last = merged[-1]
        if span.start <= last.end:
            if span.end > last.end:
                merged[-1] = Span(last.start, span.end)
        else:
            merged.append(span)
    return merged


def active_minutes(sessions: list[Session]) -> float:
    spans = [
        Span(s.started_at, s.ended_at)
        for s in sessions
        if s.started_at and s.ended_at and s.ended_at > s.started_at
    ]
    total = sum((s.end - s.start).total_seconds() for s in merge_intervals(spans))
    return round(total / 60, 1)


@dataclass
class WorkingStyle:
    """A measured portrait of how someone worked."""

    total_sessions: int
    active_hours: float
    projects: list[tuple[str, int]]
    clients: list[tuple[str, int]]
    peak_hour: int | None
    peak_hour_share: float
    longest_session_minutes: float
    median_session_minutes: float
    context_switches: int
    late_night_share: float
    span_days: int

    @property
    def chronotype(self) -> str:
        if self.peak_hour is None:
            return "unknown"
        if self.late_night_share >= 0.25:
            return "night owl"
        if self.peak_hour < 10:
            return "early bird"
        if self.peak_hour < 15:
            return "morning maker"
        return "afternoon builder"

    @property
    def focus_label(self) -> str:
        """Whether the work looks deep or fragmented.

        Judged by median session length rather than mean: one nine-hour session
        should not turn a week of ten-minute check-ins into "deep focus".
        """
        if self.median_session_minutes >= 45:
            return "deep focus"
        if self.median_session_minutes >= 15:
            return "steady sprints"
        return "rapid fire"


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def analyse(sessions: list[Session]) -> WorkingStyle:
    real = [s for s in sessions if s.started_at]
    durations = [s.duration_minutes for s in sessions if s.duration_minutes > 0]

    # Local wall clock is what a person recognises about themselves. Timestamps
    # are UTC, so convert before judging anyone a night owl.
    local_hours = Counter(s.started_at.astimezone().hour for s in real)
    peak_hour, peak_count = (local_hours.most_common(1)[0] if local_hours else (None, 0))
    late = sum(count for hour, count in local_hours.items() if hour >= 22 or hour < 5)

    # How often work moved between projects, in time order. A high count with
    # few projects means thrash; with many projects it just means breadth.
    ordered = sorted(real, key=lambda s: s.started_at)
    switches = sum(
        1 for a, b in zip(ordered, ordered[1:]) if a.project != b.project
    )

    stamps = [s.started_at for s in real]
    span_days = (max(stamps) - min(stamps)).days + 1 if stamps else 0

    # "unknown" is the absence of a project, not a project. Counted, it would
    # top the list on any machine where one client omits the working directory,
    # and the headline number of projects would be wrong.
    projects = Counter(s.project for s in sessions if s.project != "unknown")

    return WorkingStyle(
        total_sessions=len(sessions),
        active_hours=round(active_minutes(sessions) / 60, 1),
        projects=projects.most_common(6),
        clients=Counter(s.client for s in sessions).most_common(),
        peak_hour=peak_hour,
        peak_hour_share=round(peak_count / len(real), 2) if real else 0.0,
        longest_session_minutes=max(durations) if durations else 0.0,
        median_session_minutes=_median(durations),
        context_switches=switches,
        late_night_share=round(late / len(real), 2) if real else 0.0,
        span_days=span_days,
    )


@dataclass
class StuckSignal:
    """A session that looks like someone going in circles."""

    session_id: str
    project: str
    reason: str
    severity: float
    evidence: str


# Words a person uses when the assistant is not working. Deliberately short and
# multilingual: this is a trigger for asking a question, not a verdict.
FRUSTRATION = (
    "still broken", "still failing", "doesn't work", "does not work", "not working",
    "same error", "again", "no ", "wrong", "revert", "undo", "нет", "не работает",
    "опять", "снова", "всё ещё", "не то",
)


def detect_stuck(sessions: list[Session], min_turns: int = 8) -> list[StuckSignal]:
    """Find sessions where effort stopped converting into progress.

    Three signals, all cheap and all observable without a model: a long session
    on one project, repeated near-identical asks, and frustration wording. Any
    one alone is weak, which is why the severities add rather than trigger
    individually.
    """
    signals: list[StuckSignal] = []
    for session in sessions:
        user_turns = session.user_turns
        if len(user_turns) < min_turns:
            continue

        texts = [t.text.lower().strip() for t in user_turns]
        severity = 0.0
        reasons: list[str] = []

        repeats = Counter(t[:60] for t in texts if len(t) > 12)
        worst_repeat, repeat_count = (repeats.most_common(1)[0] if repeats else ("", 0))
        if repeat_count >= 3:
            severity += 0.4
            reasons.append(f"asked nearly the same thing {repeat_count} times")

        frustrated = sum(1 for t in texts if any(w in t for w in FRUSTRATION))
        if frustrated >= 3:
            severity += 0.3
            reasons.append(f"{frustrated} turns signal the fix is not landing")

        if session.duration_minutes >= 90 and len(user_turns) >= 15:
            severity += 0.3
            reasons.append(
                f"{session.duration_minutes:.0f} minutes and {len(user_turns)} asks on one thread"
            )

        if severity >= 0.5:
            signals.append(
                StuckSignal(
                    session_id=session.id,
                    # Naming the client is more useful than naming nothing: on
                    # a session whose project could not be resolved, "unknown"
                    # tells the user less than the tool they were using.
                    project=session.project if session.project != "unknown" else session.client,
                    reason="; ".join(reasons),
                    severity=round(min(severity, 1.0), 2),
                    evidence=worst_repeat or texts[-1][:60],
                )
            )

    signals.sort(key=lambda s: s.severity, reverse=True)
    return signals


def daily_breakdown(sessions: list[Session]) -> dict[str, float]:
    """Active hours per local day, unioned so parallel clients count once."""
    by_day: dict[str, list[Session]] = defaultdict(list)
    for session in sessions:
        if session.started_at:
            by_day[session.started_at.astimezone().date().isoformat()].append(session)
    return {day: round(active_minutes(items) / 60, 1) for day, items in sorted(by_day.items())}
