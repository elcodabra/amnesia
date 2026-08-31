#!/usr/bin/env python3
"""Generate the Devpost thumbnail.

Devpost shows this image next to the project title in every gallery listing,
which is where a judge decides whether to click. It has to say what the project
is in the two seconds before anyone reads a word of the description.

Written as a standalone SVG rather than reusing the Working Style Card: the card
is about one person's data, the thumbnail is about the idea.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Devpost asks for 3:2. 1200x800 is large enough to stay sharp on a retina
# gallery and small enough to stay far under the 5 MB limit.
WIDTH, HEIGHT = 1200, 800

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
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
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#64748b" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#64748b" stop-opacity="0.15"/>
    </linearGradient>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>

  <!-- The four clients, each forgetting, and the one that does not. -->
  <g font-family="Helvetica,Arial,sans-serif">
    <rect x="80" y="88" width="88" height="6" rx="3" fill="url(#accent)"/>

    <text x="80" y="230" fill="#f8fafc" font-size="86" font-weight="700">Amnesia</text>

    <text x="80" y="300" fill="#a5b4fc" font-size="34">
      Your AI agents forget you every morning.
    </text>
    <text x="80" y="352" fill="#f8fafc" font-size="34" font-weight="600">
      This one doesn't.
    </text>

    <line x1="80" y1="412" x2="1120" y2="412" stroke="#334155" stroke-width="1"/>

    <!-- Clients it reads from. Naming them is the fastest way to say what it does. -->
    <text x="80" y="464" fill="#64748b" font-size="18" letter-spacing="3">
      READS YOUR REAL SESSIONS FROM
    </text>
    <text x="80" y="516" fill="#cbd5f5" font-size="30">
      Claude Code · Cursor · Codex · jcode
    </text>

    <text x="80" y="590" fill="#64748b" font-size="18" letter-spacing="3">
      LEARNS HOW YOU ACTUALLY WORK
    </text>
    <text x="80" y="642" fill="#cbd5f5" font-size="30">
      Every belief cites the sessions behind it
    </text>

    <line x1="80" y1="700" x2="1120" y2="700" stroke="#334155" stroke-width="1"/>
    <text x="80" y="742" fill="#818cf8" font-size="22">
      Gemini 3.5 Flash · Cloud Run · Firestore · MCP
    </text>
  </g>
</svg>"""


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "thumbnail.svg"
    png_path = out_dir / "thumbnail.png"
    svg_path.write_text(SVG, encoding="utf-8")
    print(f"wrote {svg_path}")

    # qlmanage is on every Mac, so this needs no image library installed. It
    # writes <name>.svg.png next to the source, which is then renamed.
    result = subprocess.run(
        ["qlmanage", "-t", "-s", str(WIDTH), "-o", str(out_dir), str(svg_path)],
        capture_output=True,
        text=True,
    )
    produced = out_dir / f"{svg_path.name}.png"
    if not produced.exists():
        print("PNG conversion failed; the SVG is still usable")
        print(result.stdout or result.stderr)
        sys.exit(1)

    produced.replace(png_path)

    # qlmanage fits the render into a square of the requested size and pads the
    # rest, so a 3:2 source comes back 1:1 with empty bands. Devpost asks for
    # 3:2 and crops anything else, which would cut the headline in half.
    subprocess.run(
        ["sips", "-c", str(HEIGHT), str(WIDTH), str(png_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    size = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(png_path)],
        capture_output=True,
        text=True,
    ).stdout
    print(f"wrote {png_path}")
    print(size.strip().splitlines()[-2:])


if __name__ == "__main__":
    main()
