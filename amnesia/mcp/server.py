"""MCP bridge: the same memory, inside the editors you already use.

A web UI proves the agent works. This proves it is infrastructure. Once Amnesia
speaks MCP, Claude Code and Cursor answer from the same memory that the
background pass fills, which is the whole claim of the project: your agents stop
meeting you for the first time.

Implemented against stdio JSON-RPC directly rather than through a framework,
because the protocol surface needed here is four tools and no sessions, and a
dependency-free bridge is one less thing to install before a demo.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from amnesia.agent.agent import check_stuck, measured_facts, recall, remember_this

PROTOCOL_VERSION = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "recall_me",
        "description": (
            "What Amnesia knows about this developer: their preferences, working patterns, "
            "expertise and recurring friction, learned from their real coding sessions across "
            "every AI client. Call this before planning work for them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Optional filter, e.g. a project name or a subject.",
                }
            },
        },
    },
    {
        "name": "how_i_work",
        "description": (
            "Measured facts about how this developer has actually been working recently: "
            "active hours, chronotype, session rhythm, projects and context switching. "
            "Counted from timestamps, not inferred."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "am_i_stuck",
        "description": (
            "Recent sessions where effort stopped converting into progress: repeated asks, "
            "long single-thread sessions, wording that says the fix is not landing."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember_about_me",
        "description": (
            "Store something this developer just told you about how they work, so every "
            "other AI client knows it too. Use when they state a preference or correct you."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "The durable fact, in one sentence."},
                "kind": {
                    "type": "string",
                    "enum": ["preference", "pattern", "expertise", "friction", "goal"],
                },
            },
            "required": ["claim"],
        },
    },
]


def _how_i_work() -> str:
    _, facts = measured_facts()
    return facts


HANDLERS: dict[str, Callable[..., str]] = {
    "recall_me": lambda topic="": recall(topic),
    "how_i_work": _how_i_work,
    "am_i_stuck": lambda: check_stuck(),
    "remember_about_me": lambda claim, kind="preference": remember_this(claim, kind),
}


def _result(request_id: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: dict) -> dict | None:
    """Handle one JSON-RPC request. Returns None for notifications."""
    method = request.get("method")
    request_id = request.get("id")

    # Notifications carry no id and must not be answered. Replying to one is
    # the classic way an MCP client decides the server is broken.
    if request_id is None:
        return None

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "amnesia", "version": "0.1.0"},
            },
        )

    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        handler = HANDLERS.get(name)
        if not handler:
            return _error(request_id, -32601, f"Unknown tool: {name}")
        try:
            text = handler(**(params.get("arguments") or {}))
        except Exception as exc:  # noqa: BLE001 - a tool error is a result, not a crash
            return _result(
                request_id,
                {"content": [{"type": "text", "text": f"Tool failed: {exc}"}], "isError": True},
            )
        return _result(request_id, {"content": [{"type": "text", "text": text}]})

    return _error(request_id, -32601, f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
