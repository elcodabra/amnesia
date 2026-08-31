#!/usr/bin/env python3
"""Build the Devpost image gallery.

A gallery image has one job: make a claim from the write-up visible without
anyone running the project. So each one is a real artefact from the live
service, framed on the 3:2 canvas Devpost crops to, with a caption saying what
it proves.

Everything is pulled from the deployed URL rather than from local state, because
an image of localhost proves nothing about a deployment.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

WIDTH, HEIGHT = 1200, 800
SERVICE = "https://amnesia-orkuraibfa-uc.a.run.app"
OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"


def fetch(path: str) -> dict:
    with urllib.request.urlopen(f"{SERVICE}{path}", timeout=120) as response:
        return json.loads(response.read().decode())


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def frame(title: str, subtitle: str, body: str, footer: str) -> str:
    """One gallery slide. Same furniture every time, so the set reads as a set."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1020"/>
      <stop offset="55%" stop-color="#1e1b4b"/>
      <stop offset="100%" stop-color="#312e81"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#c084fc"/>
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <g font-family="Helvetica,Arial,sans-serif">
    <rect x="72" y="72" width="72" height="5" rx="2.5" fill="url(#accent)"/>
    <text x="72" y="150" fill="#f8fafc" font-size="52" font-weight="700">{esc(title)}</text>
    <text x="72" y="196" fill="#a5b4fc" font-size="24">{esc(subtitle)}</text>
    <line x1="72" y1="236" x2="1128" y2="236" stroke="#334155" stroke-width="1"/>
    {body}
    <line x1="72" y1="700" x2="1128" y2="700" stroke="#334155" stroke-width="1"/>
    <text x="72" y="742" fill="#818cf8" font-size="20">{esc(footer)}</text>
  </g>
</svg>"""


def lines(items: list[str], y: int, size: int = 26, gap: int = 46, fill: str = "#cbd5f5") -> str:
    out = []
    for i, text in enumerate(items):
        out.append(
            f'<text x="72" y="{y + i * gap}" fill="{fill}" font-size="{size}">{esc(text)}</text>'
        )
    return "\n    ".join(out)


def wrap(text: str, width: int = 78) -> list[str]:
    """Naive word wrap. Enough for two lines of a claim on a slide."""
    words, out, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        out.append(current)
    return out


def render(name: str, svg: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    svg_path = OUT / f"{name}.svg"
    png_path = OUT / f"{name}.png"
    svg_path.write_text(svg, encoding="utf-8")

    subprocess.run(
        ["qlmanage", "-t", "-s", str(WIDTH), "-o", str(OUT), str(svg_path)],
        capture_output=True,
        text=True,
    )
    produced = OUT / f"{svg_path.name}.png"
    if not produced.exists():
        print(f"  ! {name}: PNG conversion failed")
        return svg_path
    produced.replace(png_path)
    # qlmanage pads to a square; Devpost wants 3:2 and crops anything else.
    subprocess.run(["sips", "-c", str(HEIGHT), str(WIDTH), str(png_path)], capture_output=True)
    svg_path.unlink(missing_ok=True)
    print(f"  ✓ {png_path.name}")
    return png_path


def main() -> None:
    print(f"Reading live service: {SERVICE}")
    try:
        profile = fetch("/api/profile")
        memory = fetch("/api/memory")
        card = fetch("/api/card")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not reach the service: {exc}")
        sys.exit(1)

    print("Rendering gallery:")

    # 1. The measured profile. The claim: these numbers are counted, not guessed.
    projects = ", ".join(f"{n} ({c})" for n, c in profile["projects"][:4]) or "none"
    render(
        "gallery-1-profile",
        frame(
            "Measured, not guessed",
            "Counted from timestamps in real sessions, overlapping clients counted once",
            lines(
                [
                    f"{profile['sessions']} sessions across {profile['span_days']} days",
                    f"{profile['active_hours']} active hours (union of intervals, never a sum)",
                    f"Chronotype: {profile['chronotype']}, peak hour {profile['peak_hour']}:00",
                    f"Rhythm: {profile['focus']}, median session"
                    f" {profile['median_session_minutes']} min",
                    f"Projects: {projects}",
                    f"Clients: {', '.join(f'{n} ({c})' for n, c in profile['clients'])}",
                ],
                y=300,
            ),
            "GET /api/profile · live on Cloud Run",
        ),
    )

    # 2. Beliefs with evidence. The claim: nothing is asserted that cannot be traced.
    top = sorted(memory["beliefs"], key=lambda b: b["evidence_count"], reverse=True)[:3]
    body = []
    y = 296
    for belief in top:
        body.append(
            f'<text x="72" y="{y}" fill="#38bdf8" font-size="17" letter-spacing="2">'
            f'{esc(belief["kind"].upper())} · CONFIDENCE {belief["confidence"]} · '
            f'{belief["evidence_count"]} SESSIONS CITED</text>'
        )
        for j, line in enumerate(wrap(belief["claim"], 76)[:2]):
            body.append(
                f'<text x="72" y="{y + 36 + j * 32}" fill="#e8ecf8" font-size="23">'
                f"{esc(line)}</text>"
            )
        y += 132
    render(
        "gallery-2-beliefs",
        frame(
            "Every belief cites its evidence",
            f"{memory['count']} learned from my own sessions, each traceable and correctable",
            "\n    ".join(body),
            "GET /api/memory · one click marks any of these wrong",
        ),
    )

    # 3. The stuck signal. The claim: it notices what you would not admit.
    stuck = profile.get("stuck") or []
    if stuck:
        signal = stuck[0]
        body = lines(wrap(signal["reason"], 66), y=330, size=28, gap=44, fill="#f8fafc")
        extra = (
            f'<text x="72" y="296" fill="#f472b6" font-size="19" letter-spacing="2">'
            f'SEVERITY {signal["severity"]} · {esc(signal["project"].upper())}</text>'
        )
        render(
            "gallery-3-stuck",
            frame(
                "It noticed I was going in circles",
                "The background pass flags effort that stopped converting into progress",
                extra + "\n    " + body,
                "Detected without a model: repetition, duration and wording",
            ),
        )

    # 4. The architecture, as words rather than a diagram: a diagram at gallery
    # size is unreadable, and the point is which Google services are real.
    render(
        "gallery-4-stack",
        frame(
            "Running on Google Cloud",
            "An agent that works while nobody is watching, not a web app with a model",
            lines(
                [
                    "Cloud Run · the service, scaling to zero between runs",
                    "Firestore · beliefs and their evidence, across sessions",
                    "Cloud Scheduler · hourly distillation, with or without a user",
                    "Gemini 3.5 Flash · distillation, agent tool loop, card",
                    "   ↳ falls back to flash-lite when the model is at capacity",
                    "MCP bridge · the same memory inside Claude Code and Cursor",
                ],
                y=300,
            ),
            f"{SERVICE}",
        ),
    )

    # 5. The card, as the shareable artefact it is meant to be.
    render(
        "gallery-5-card",
        frame(
            f'"{card["nickname"]}"',
            "The Working Style Card, generated from measured facts",
            lines(wrap(card["line"], 62), y=320, size=30, gap=46, fill="#f8fafc")
            + '\n    <text x="72" y="470" fill="#64748b" font-size="19" letter-spacing="2">'
            "WHY IT IS SAFE TO POST</text>"
            + "\n    "
            + lines(
                [
                    "Hours are unioned, so parallel clients are not double counted",
                    "Inference is capped below measurement, so a guess cannot outrank a count",
                    "Every claim behind it names the sessions it came from",
                ],
                y=516,
                size=23,
                gap=40,
            ),
            "GET /api/card.svg",
        ),
    )

    print(f"\nGallery written to {OUT}")
    print("Upload in this order: thumbnail, profile, beliefs, stuck, stack, card.")


if __name__ == "__main__":
    main()
