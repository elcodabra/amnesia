"""The Working Style Card.

The card is the answer to "why would anyone share this". A list of beliefs is
useful; a portrait of how you work is something people post. It is generated
from measured facts first, with the model adding only a nickname and one line
of interpretation, so the numbers on a shared card are always real.

Rendered as inline SVG so it needs no image library, no fonts and no storage
bucket, and it can be embedded straight into the page or saved as a file.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from amnesia.memory.analytics import WorkingStyle
from amnesia.memory.store import Belief
from amnesia.settings import settings

NICKNAME_PROMPT = """Here is a developer's measured working profile:

- {sessions} AI coding sessions over {days} days, {hours} active hours
- Chronotype: {chronotype} (peak hour {peak}:00 local)
- Session rhythm: {focus} (median {median} minutes)
- Projects: {projects}
- Context switches between projects: {switches}

And what has been learned about how they work:
{beliefs}

Give them a two-or-three word nickname that captures their working style, plus
one sentence (max 18 words) they would find flattering but true. Be specific to
this data, never generic.

Return ONLY JSON: {{"nickname": "...", "line": "..."}}
"""


@dataclass
class Card:
    nickname: str
    line: str
    style: WorkingStyle
    top_beliefs: list[str]


def _fallback_nickname(style: WorkingStyle) -> tuple[str, str]:
    """A card must render before any model call succeeds.

    The nickname is the one place a model is allowed to be decorative, so its
    absence should degrade the card, never block it.
    """
    nickname = f"The {style.chronotype.title()}"
    line = (
        f"{style.active_hours} hours across {len(style.projects)} projects, "
        f"mostly {style.focus_label}."
    )
    return nickname, line


def build_card(style: WorkingStyle, beliefs: list[Belief]) -> Card:
    ranked = sorted(beliefs, key=lambda b: (b.evidence_count, b.confidence), reverse=True)
    top = [b.claim for b in ranked[:3]]
    nickname, line = _fallback_nickname(style)

    if settings.has_model_access:
        try:
            from google import genai

            client = genai.Client(
                vertexai=settings.use_vertex or None,
                api_key=settings.google_api_key or None,
                project=settings.project or None,
                location=settings.location if settings.use_vertex else None,
            )
            prompt = NICKNAME_PROMPT.format(
                sessions=style.total_sessions,
                days=style.span_days,
                hours=style.active_hours,
                chronotype=style.chronotype,
                peak=style.peak_hour if style.peak_hour is not None else "?",
                focus=style.focus_label,
                median=style.median_session_minutes,
                projects=", ".join(name for name, _ in style.projects[:4]) or "unknown",
                switches=style.context_switches,
                beliefs="\n".join(f"- {c}" for c in top) or "- nothing distilled yet",
            )
            response = client.models.generate_content(model=settings.model, contents=prompt)
            import json
            import re

            text = re.sub(r"^```(?:json)?|```$", "", (response.text or "").strip()).strip()
            parsed = json.loads(text)
            nickname = str(parsed.get("nickname") or nickname)[:40]
            line = str(parsed.get("line") or line)[:140]
        except Exception:  # noqa: BLE001 - decoration must never break the card
            pass

    return Card(nickname=nickname, line=line, style=style, top_beliefs=top)


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def render_svg(card: Card) -> str:
    """Self-contained SVG. No external fonts, no images, safe to embed."""
    s = card.style
    stats = [
        (f"{s.active_hours}h", "active"),
        (str(s.total_sessions), "sessions"),
        (str(len(s.projects)), "projects"),
        (f"{s.peak_hour:02d}:00" if s.peak_hour is not None else "--", "peak"),
    ]
    stat_svg = ""
    for i, (value, label) in enumerate(stats):
        x = 60 + i * 145
        stat_svg += (
            f'<text x="{x}" y="330" fill="#f8fafc" font-size="34" font-weight="700" '
            f'font-family="Helvetica,Arial,sans-serif">{_esc(value)}</text>'
            f'<text x="{x}" y="356" fill="#94a3b8" font-size="14" letter-spacing="1.5" '
            f'font-family="Helvetica,Arial,sans-serif">{_esc(label.upper())}</text>'
        )

    belief_svg = ""
    for i, claim in enumerate(card.top_beliefs[:3]):
        # Clipping beats wrapping here: a card is a glance, and a long claim is
        # better read in the app than squeezed onto three lines.
        text = claim if len(claim) <= 68 else claim[:65] + "..."
        belief_svg += (
            f'<text x="60" y="{420 + i * 34}" fill="#cbd5f5" font-size="16" '
            f'font-family="Helvetica,Arial,sans-serif">• {_esc(text)}</text>'
        )

    tags = " · ".join([s.chronotype, s.focus_label, *(n for n, _ in s.projects[:2])])

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="680" height="580" viewBox="0 0 680 580">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="55%" stop-color="#1e1b4b"/>
      <stop offset="100%" stop-color="#312e81"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#c084fc"/>
    </linearGradient>
  </defs>
  <rect width="680" height="580" rx="28" fill="url(#bg)"/>
  <rect x="60" y="58" width="72" height="5" rx="2.5" fill="url(#accent)"/>
  <text x="60" y="104" fill="#94a3b8" font-size="15" letter-spacing="3.5"
        font-family="Helvetica,Arial,sans-serif">AMNESIA · WORKING STYLE CARD</text>
  <text x="60" y="176" fill="#f8fafc" font-size="46" font-weight="700"
        font-family="Helvetica,Arial,sans-serif">{_esc(card.nickname)}</text>
  <text x="60" y="216" fill="#a5b4fc" font-size="18"
        font-family="Helvetica,Arial,sans-serif">{_esc(card.line[:74])}</text>
  <line x1="60" y1="252" x2="620" y2="252" stroke="#334155" stroke-width="1"/>
  {stat_svg}
  <text x="60" y="398" fill="#64748b" font-size="13" letter-spacing="2.5"
        font-family="Helvetica,Arial,sans-serif">WHAT MY AI KNOWS ABOUT ME</text>
  {belief_svg}
  <line x1="60" y1="512" x2="620" y2="512" stroke="#334155" stroke-width="1"/>
  <text x="60" y="540" fill="#64748b" font-size="13"
        font-family="Helvetica,Arial,sans-serif">{_esc(tags[:64])}</text>
  <text x="620" y="540" fill="#818cf8" font-size="13" text-anchor="end"
        font-family="Helvetica,Arial,sans-serif">built with Gemini on Google Cloud</text>
</svg>"""


def share_text(card: Card) -> str:
    """The caption that ships with the card."""
    s = card.style
    return (
        f"My AI agents used to forget me every morning. I built Amnesia so they don't.\n\n"
        f"It read {s.total_sessions} of my real coding sessions and called me "
        f"\"{card.nickname}\": {s.active_hours} active hours, {s.chronotype}, {s.focus_label}.\n\n"
        f"#AllThingsAgenticHackathon"
    )
