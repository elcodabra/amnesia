#!/usr/bin/env python3
"""Pre-demo check: is this thing actually ready to be recorded?

Run this before hitting record. It exercises every claim the demo makes and
prints the live numbers the script needs, so nothing is discovered on camera.

Exits non-zero if something that must work does not.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from amnesia.agent.agent import check_stuck, measured_facts, recall  # noqa: E402
from amnesia.cards.card import build_card, render_svg  # noqa: E402
from amnesia.ingest.sessions import collect_sessions  # noqa: E402
from amnesia.mcp.server import handle  # noqa: E402
from amnesia.memory.store import get_store  # noqa: E402
from amnesia.settings import settings  # noqa: E402

OK = "\033[92m✓\033[0m"
BAD = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

failures: list[str] = []


def check(label: str, passed: bool, detail: str = "", fatal: bool = True) -> None:
    mark = OK if passed else (BAD if fatal else WARN)
    print(f" {mark} {label}" + (f": {detail}" if detail else ""))
    if not passed and fatal:
        failures.append(label)


print("\n\033[1mAMNESIA · demo readiness\033[0m\n")

# ---------------------------------------------------------------- ingestion
sessions = collect_sessions(limit=settings.distill_batch)
check("Sessions readable", bool(sessions), f"{len(sessions)} found")
clients = sorted({s.client for s in sessions})
check("More than one client", len(clients) > 1, ", ".join(clients))

# ------------------------------------------------------------ measurement
style, facts = measured_facts()
check("Active hours computed", style.active_hours > 0, f"{style.active_hours}h")
check(
    "Hours are plausible",
    style.active_hours <= style.span_days * 24,
    f"{style.active_hours}h over {style.span_days} days",
)

# --------------------------------------------------------------- detection
stuck = check_stuck()
has_stuck = "No stuck patterns" not in stuck
check("Stuck signal to show on camera", has_stuck, stuck.splitlines()[0] if has_stuck else "none",
      fatal=False)

# ------------------------------------------------------------------ memory
beliefs = get_store().all()
check("Beliefs in memory", bool(beliefs), f"{len(beliefs)} stored", fatal=False)
with_evidence = [b for b in beliefs if b.evidence_count]
check(
    "Every belief carries evidence",
    len(with_evidence) == len(beliefs),
    f"{len(with_evidence)}/{len(beliefs)}",
    fatal=bool(beliefs),
)

# -------------------------------------------------------------------- card
card = build_card(style, beliefs)
svg = render_svg(card)
check("Card renders", svg.startswith("<svg") and len(svg) > 1000, f'"{card.nickname}"')

# --------------------------------------------------------------------- mcp
tools = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
check("MCP tools exposed", len(tools) == 4, ", ".join(t["name"] for t in tools))
call = handle(
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "how_i_work", "arguments": {}}}
)
check("MCP returns real data", bool(call["result"]["content"][0]["text"]))

# ------------------------------------------------------- client registration
import json  # noqa: E402

registered = []
for name, path in (
    ("Claude Code", Path.home() / ".claude.json"),
    ("Cursor", Path.home() / ".cursor" / "mcp.json"),
):
    if path.exists():
        try:
            if "amnesia" in (json.loads(path.read_text()).get("mcpServers") or {}):
                registered.append(name)
        except (json.JSONDecodeError, OSError):
            pass
check("Registered in an editor", bool(registered), ", ".join(registered) or "run scripts/install-mcp.sh")

# ------------------------------------------------------------------- gemini
check(
    "Gemini credentials",
    settings.has_model_access,
    settings.model if settings.has_model_access else "set GOOGLE_API_KEY",
)

# -------------------------------------------------------------------- tests
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q"],
    cwd=REPO, capture_output=True, text=True,
)
last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "no output"
check("Test suite", result.returncode == 0, last)

# ----------------------------------------------------------- live numbers
print("\n\033[1mLive numbers for the script and the post\033[0m\n")
print(facts)
if beliefs:
    print(f"- Beliefs learned: {len(beliefs)}")
print(f'- Card nickname: "{card.nickname}"')
print(f"- Card line: {card.line}")

if failures:
    print(f"\n{BAD} Not ready. Fix: " + ", ".join(failures) + "\n")
    sys.exit(1)
print(f"\n{OK} Ready to record.\n")
