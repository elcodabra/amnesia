"""Remote MCP over HTTP, so ChatGPT can connect.

The stdio bridge works for editors that spawn a local process. ChatGPT cannot
spawn anything: it connects to a URL. This is the same tool surface reached over
Streamable HTTP instead.

Two extra tools exist only for ChatGPT: `search` and `fetch`. Its connector
contract requires both by name, and refuses a server without them. They are
thin wrappers over the same memory, not a second implementation.
"""

from __future__ import annotations

import json

from amnesia.mcp.server import HANDLERS, TOOLS, handle
from amnesia.memory.store import get_store

PROTOCOL_VERSION = "2024-11-05"


def _search(query: str = "") -> str:
    """ChatGPT's required search tool, over stored beliefs.

    Returns the id alongside each result, because `fetch` is only useful if the
    model can tell it which record to open.
    """
    needle = (query or "").lower().strip()
    beliefs = [b for b in get_store().all() if b.status == "active"]
    if needle:
        matched = [
            b
            for b in beliefs
            if needle in b.claim.lower()
            or needle in b.kind.lower()
            or any(needle in p.lower() for p in b.projects)
        ]
        # An empty result reads to the model as "this person has no memory",
        # which is worse than showing what is actually known.
        beliefs = matched or beliefs
    ranked = sorted(beliefs, key=lambda b: (b.evidence_count, b.confidence), reverse=True)
    if not ranked:
        return "Nothing learned yet. Run the background pass over recent sessions."
    return "\n".join(
        f"[{b.id}] ({b.kind}, {b.evidence_count} sessions) {b.claim}" for b in ranked[:10]
    )


def _fetch(id: str = "") -> str:  # noqa: A002 - the connector contract names it `id`
    """ChatGPT's required fetch tool: one belief, with its evidence."""
    belief = get_store().get(id)
    if not belief:
        return f"No belief with id {id}."
    lines = [
        f"Claim: {belief.claim}",
        f"Kind: {belief.kind}",
        f"Confidence: {belief.confidence} (inference is capped below measurement)",
        f"Evidence: {belief.evidence_count} sessions — {', '.join(belief.evidence[:6])}",
        f"Status: {belief.status}",
    ]
    if belief.projects:
        lines.append(f"Projects: {', '.join(belief.projects)}")
    if belief.user_feedback:
        lines.append(f"User correction: {belief.user_feedback}")
    return "\n".join(lines)


CHATGPT_TOOLS = [
    {
        "name": "search",
        "description": (
            "Search what Amnesia has learned about this developer from their real coding "
            "sessions: preferences, working patterns, expertise and recurring friction. "
            "Call this before advising them on any technical task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for. Empty returns all."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch",
        "description": (
            "Open one belief by id and see the evidence behind it: which sessions produced "
            "it, its confidence, and any correction the user has made."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Belief id from search."}},
            "required": ["id"],
        },
    },
]

REMOTE_TOOLS = [*CHATGPT_TOOLS, *TOOLS]
REMOTE_HANDLERS = {**HANDLERS, "search": _search, "fetch": _fetch}


def handle_remote(request: dict) -> dict | None:
    """Handle one JSON-RPC request from a remote client."""
    method = request.get("method")
    request_id = request.get("id")

    if request_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "amnesia", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": REMOTE_TOOLS}}

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        fn = REMOTE_HANDLERS.get(name)
        if not fn:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }
        try:
            text = fn(**(params.get("arguments") or {}))
        except Exception as exc:  # noqa: BLE001 - a tool error is a result, not a crash
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool failed: {exc}"}],
                    "isError": True,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }

    # Delegate anything else to the stdio implementation, so the two transports
    # cannot drift on the parts they share.
    return handle(request)


def as_sse(payload: dict) -> str:
    """Wrap a JSON-RPC response as a Server-Sent Event.

    Streamable HTTP lets a server answer with plain JSON or with an SSE stream.
    ChatGPT asks for SSE, so a single-event stream is the smallest correct
    answer to a request that has exactly one response.
    """
    return f"event: message\ndata: {json.dumps(payload)}\n\n"
