"""Tests for the MCP bridge.

The bridge is what makes Amnesia infrastructure rather than another chat app,
and it fails silently: a malformed response does not raise, the editor just
quietly stops listing the tools. So the protocol shape is asserted directly.
"""

from __future__ import annotations

from amnesia.mcp.server import PROTOCOL_VERSION, TOOLS, handle


def test_initialize_announces_tools() -> None:
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in response["result"]["capabilities"]


def test_notifications_are_never_answered() -> None:
    """Replying to a notification is how a client decides a server is broken."""
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_is_complete_and_described() -> None:
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "recall_me",
        "how_i_work",
        "am_i_stuck",
        "remember_about_me",
    }
    # A tool an agent cannot tell when to use is a tool it will not call.
    assert all(len(t["description"]) > 40 for t in tools)
    assert all("inputSchema" in t for t in tools)


def test_required_arguments_are_declared() -> None:
    remember = next(t for t in TOOLS if t["name"] == "remember_about_me")
    assert remember["inputSchema"]["required"] == ["claim"]


def test_unknown_tool_is_an_error_not_a_crash() -> None:
    response = handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}}
    )
    assert response["error"]["code"] == -32601


def test_unknown_method_is_reported() -> None:
    response = handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    assert "error" in response


def test_tool_call_returns_mcp_content_blocks() -> None:
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "how_i_work", "arguments": {}},
        }
    )
    content = response["result"]["content"]
    assert content[0]["type"] == "text" and content[0]["text"]


def test_bad_arguments_surface_as_a_tool_error() -> None:
    """A wrong argument must come back as a result the model can read."""
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "how_i_work", "arguments": {"unexpected": 1}},
        }
    )
    assert response["result"]["isError"] is True
