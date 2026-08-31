"""HTTP surface: the chat UI, the background job endpoint and the card.

One process serves everything, because Cloud Run bills per container and a
hackathon deployment should cost close to nothing. The background pass is an
HTTP endpoint rather than a loop, so Cloud Scheduler drives it and the
container scales to zero between runs.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from amnesia.agent.agent import AmnesiaAgent, measured_facts, run_distill_pass
from amnesia.cards.card import build_card, render_svg, share_text
from amnesia.ingest.sessions import collect_sessions
from amnesia.memory.analytics import daily_breakdown, detect_stuck
from amnesia.memory.store import get_store
from amnesia.settings import settings
from amnesia.web.page import PAGE

app = FastAPI(title="Amnesia", description="Persistent memory for your AI agents")
agent = AmnesiaAgent()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class FeedbackRequest(BaseModel):
    belief_id: str
    correction: str


class IngestRequest(BaseModel):
    """Sessions pushed from a laptop to a deployed instance.

    Cloud Run cannot read local transcript files, so without this the deployed
    service has nothing to learn from. Only normalised turns travel: no file
    contents, no paths, no credentials.
    """

    sessions: list[dict]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/api/health", response_class=PlainTextResponse)
@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    """Liveness. Deliberately does no work and touches nothing.

    Served on two paths because Google's frontend intercepts `/healthz` before
    the request reaches the container, so the conventional name answers 404
    from outside while working perfectly inside.
    """
    return "ok"


@app.get("/api/memory")
def memory() -> JSONResponse:
    beliefs = sorted(
        get_store().all(),
        key=lambda b: (b.status == "active", b.evidence_count, b.confidence),
        reverse=True,
    )
    return JSONResponse(
        {
            "count": len(beliefs),
            "beliefs": [
                {
                    "id": b.id,
                    "kind": b.kind,
                    "claim": b.claim,
                    "confidence": b.confidence,
                    "evidence_count": b.evidence_count,
                    "evidence": b.evidence[:5],
                    "projects": b.projects,
                    "status": b.status,
                    "user_feedback": b.user_feedback,
                }
                for b in beliefs
            ],
        }
    )


@app.get("/api/profile")
def profile() -> JSONResponse:
    sessions = collect_sessions(limit=settings.distill_batch)
    style, _ = measured_facts()
    return JSONResponse(
        {
            "sessions": style.total_sessions,
            "active_hours": style.active_hours,
            "span_days": style.span_days,
            "chronotype": style.chronotype,
            "focus": style.focus_label,
            "peak_hour": style.peak_hour,
            "median_session_minutes": style.median_session_minutes,
            "projects": style.projects,
            "clients": style.clients,
            "context_switches": style.context_switches,
            "daily_hours": daily_breakdown(sessions),
            "stuck": [
                {"project": s.project, "severity": s.severity, "reason": s.reason}
                for s in detect_stuck(sessions)[:5]
            ],
        }
    )


@app.post("/api/chat")
def chat(req: ChatRequest) -> JSONResponse:
    reply = agent.chat(req.message, req.history)
    return JSONResponse(
        {"reply": reply.text, "tool_calls": reply.tool_calls, "memory_used": reply.memory_used}
    )


@app.post("/api/feedback")
def feedback(req: FeedbackRequest) -> JSONResponse:
    """The explicit feedback channel the Collaborative Partner track asks for.

    Separate from chat on purpose: correcting a belief is a deliberate act, and
    burying it in conversation makes it depend on the model noticing.
    """
    from amnesia.agent.agent import correct_belief

    return JSONResponse({"result": correct_belief(req.belief_id, req.correction)})


@app.post("/api/ingest")
def ingest(req: IngestRequest) -> JSONResponse:
    """Receive sessions pushed from a laptop.

    Deliberately separate from distillation: uploading is cheap and frequent,
    distilling costs model calls and runs on a schedule.
    """
    from amnesia.ingest.uploaded import save_uploaded

    saved = save_uploaded(req.sessions)
    return JSONResponse({"received": len(req.sessions), "stored": saved})


@app.post("/api/distill")
def distill_endpoint(limit: int | None = None) -> JSONResponse:
    """The background pass. Triggered by Cloud Scheduler in production."""
    return JSONResponse(run_distill_pass(limit))


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    """Remote MCP over Streamable HTTP, so ChatGPT can connect to this memory.

    The stdio bridge only works for clients that spawn a local process. ChatGPT
    connects to a URL, so the same tools are served here.
    """
    from amnesia.mcp.remote import as_sse, handle_remote

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - a malformed body is a protocol error, not a crash
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    # Notifications get 202 with no body: answering one makes a client decide
    # the server is broken.
    response = handle_remote(payload)
    if response is None:
        return Response(status_code=202)

    # Streamable HTTP allows JSON or SSE. Honour what the client asked for.
    if "text/event-stream" in (request.headers.get("accept") or ""):
        return Response(content=as_sse(response), media_type="text/event-stream")
    return JSONResponse(response)


@app.get("/mcp")
def mcp_probe() -> Response:
    """Some clients probe with GET before opening a session.

    405 is the honest answer: the endpoint exists, but this transport carries
    requests over POST. A 404 here reads as "no server".
    """
    return Response(status_code=405, headers={"Allow": "POST"})


@app.get("/api/card.svg")
def card_svg() -> Response:
    style, _ = measured_facts()
    card = build_card(style, get_store().all())
    return Response(content=render_svg(card), media_type="image/svg+xml")


@app.get("/api/card")
def card_meta() -> JSONResponse:
    style, _ = measured_facts()
    card = build_card(style, get_store().all())
    return JSONResponse(
        {"nickname": card.nickname, "line": card.line, "share_text": share_text(card)}
    )
