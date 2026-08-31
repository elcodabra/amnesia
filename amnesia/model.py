"""One way to reach Gemini, with a fallback that keeps a demo alive.

Three parts of the system call the model, and each was building its own client
and handling its own failures. This centralises both, and adds the thing a live
demo actually needs: when the preferred model returns 503 because everyone else
is also using it, the call moves to the next model rather than failing.

Fallbacks stay within the same model generation, so a degraded run still meets
the requirement it was chosen for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amnesia.settings import settings

# Failures worth retrying on another model: capacity and rate limits, not bad
# requests. Retrying a malformed prompt on three models just fails three times.
RETRYABLE = ("503", "UNAVAILABLE", "overloaded", "429", "RESOURCE_EXHAUSTED")


@dataclass
class ModelReply:
    text: str
    model: str
    raw: Any = None


class NoModelAccess(RuntimeError):
    """Raised when no credentials are configured at all."""


_client = None


def get_client():
    """The process-wide GenAI client."""
    global _client
    if _client is None:
        if not settings.has_model_access:
            raise NoModelAccess(
                "No Gemini credentials: set GOOGLE_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI "
                "with GOOGLE_CLOUD_PROJECT."
            )
        from google import genai

        # An API key and a project/location are mutually exclusive: the Gemini
        # API rejects the call outright when both are passed. Cloud Run sets
        # GOOGLE_CLOUD_PROJECT on every service, so this combination happens by
        # default rather than by mistake, and the key is the explicit choice.
        if settings.use_vertex:
            _client = genai.Client(
                vertexai=True,
                project=settings.project or None,
                location=settings.location,
            )
        else:
            _client = genai.Client(api_key=settings.google_api_key)
    return _client


def model_chain() -> list[str]:
    """Preferred model first, then fallbacks, without repeats."""
    return list(dict.fromkeys([settings.model, *settings.fallback_models]))


def _is_retryable(exc: Exception) -> bool:
    message = str(exc)
    return any(token in message for token in RETRYABLE)


def generate(contents: Any, config: Any = None) -> ModelReply:
    """Generate content, moving to the next model on a capacity failure."""
    client = get_client()
    last: Exception | None = None

    for model in model_chain():
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            return ModelReply(text=response.text or "", model=model, raw=response)
        except Exception as exc:  # noqa: BLE001 - decide by failure kind, below
            last = exc
            if not _is_retryable(exc):
                raise
            print(f"[amnesia] {model} unavailable, trying next model")

    raise last if last else RuntimeError("No model available")
