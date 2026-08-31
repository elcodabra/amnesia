#!/usr/bin/env python3
"""Push local session history to a deployed Amnesia.

Cloud Run has no access to a laptop's transcript files, so the deployed service
would otherwise start empty. This uploads the normalised sessions rather than
the raw files: no file contents, no paths, no credentials leave the machine.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

# Run as a script from anywhere, not only from the repo root with PYTHONPATH
# set. A setup step that fails on the obvious invocation is a setup step that
# will be reported as broken.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from amnesia.ingest.sessions import collect_sessions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Base URL of the deployed service")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    sessions = collect_sessions(limit=args.limit)
    payload = {
        "sessions": [
            {
                "id": s.id,
                "client": s.client,
                "project": s.project,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "turns": [
                    {"role": t.role, "text": t.text[:2000]} for t in s.turns[-40:]
                ],
            }
            for s in sessions
        ]
    }

    request = urllib.request.Request(
        args.url.rstrip("/") + "/api/ingest",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
