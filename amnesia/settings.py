"""Configuration for Amnesia.

Every value has a working default so a judge can clone the repo and run it
without a Google Cloud account. Cloud services upgrade the deployment; they are
never required to see the agent work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, resolved once at import time."""

    # --- model -------------------------------------------------------------
    # Gemini 3.5 Flash is the hackathon requirement and also the right pick:
    # distillation runs over every session, so per-call cost matters more than
    # peak reasoning.
    model: str = field(default_factory=lambda: os.environ.get("AMNESIA_MODEL", "gemini-3.5-flash"))
    google_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_API_KEY", ""))
    use_vertex: bool = field(default_factory=lambda: _flag("GOOGLE_GENAI_USE_VERTEXAI"))
    project: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", ""))
    location: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )

    # --- memory store ------------------------------------------------------
    # Firestore in the cloud, JSON on disk locally. Same interface either way.
    firestore_enabled: bool = field(default_factory=lambda: _flag("AMNESIA_USE_FIRESTORE"))
    firestore_collection: str = field(
        default_factory=lambda: os.environ.get("AMNESIA_COLLECTION", "amnesia_memory")
    )
    local_store_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("AMNESIA_STORE", str(Path.home() / ".amnesia" / "memory.json"))
        )
    )

    # --- optional Personal Context Engine ----------------------------------
    # Amnesia can federate with an existing Personal Context Engine. Absent one,
    # it stands alone on locally ingested sessions.
    context_engine_url: str = field(
        default_factory=lambda: os.environ.get("CONTEXT_ENGINE_URL", "").rstrip("/")
    )
    context_engine_key: str = field(
        default_factory=lambda: os.environ.get("CONTEXT_ENGINE_API_KEY", "")
    )

    # --- ingestion ---------------------------------------------------------
    owner: str = field(default_factory=lambda: os.environ.get("AMNESIA_OWNER", "me"))
    # A turn shorter than this is a typo fix, not a working session.
    min_turn_ms: int = field(default_factory=lambda: _int("AMNESIA_MIN_TURN_MS", 20_000))
    # How many sessions one background pass distills. Bounded so a scheduled
    # run has a predictable cost ceiling.
    distill_batch: int = field(default_factory=lambda: _int("AMNESIA_DISTILL_BATCH", 40))

    @property
    def has_model_access(self) -> bool:
        """True when a Gemini call can actually be made."""
        return bool(self.google_api_key) or (self.use_vertex and bool(self.project))


settings = Settings()
