"""Tests for model access and its fallback.

This is the code that runs while a demo is being recorded and the popular model
is returning 503 because everyone else is demoing too. It is worth testing
precisely because it only matters when something is already going wrong.
"""

from __future__ import annotations

import pytest

import amnesia.model as model_layer
from amnesia.settings import Settings


class _FakeModels:
    def __init__(self, fail_on: set[str], error: str) -> None:
        self.fail_on = fail_on
        self.error = error
        self.tried: list[str] = []

    def generate_content(self, model: str, contents, config=None):  # noqa: ANN001
        self.tried.append(model)
        if model in self.fail_on:
            raise RuntimeError(self.error)
        return type("R", (), {"text": f"reply from {model}"})()


class _FakeClient:
    def __init__(self, models: _FakeModels) -> None:
        self.models = models


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.setattr(
        model_layer,
        "settings",
        Settings(model="primary", fallback_models=("backup", "last-resort")),
    )
    def install(fail_on: set[str], error: str = "503 UNAVAILABLE overloaded") -> _FakeModels:
        models = _FakeModels(fail_on, error)
        monkeypatch.setattr(model_layer, "get_client", lambda: _FakeClient(models))
        return models

    return install


def test_preferred_model_is_used_when_healthy(chain) -> None:
    models = chain(set())
    assert model_layer.generate("hi").model == "primary"
    assert models.tried == ["primary"]


def test_capacity_failure_moves_to_the_next_model(chain) -> None:
    """503 is what a busy model returns, and a demo cannot wait for capacity."""
    models = chain({"primary"})
    reply = model_layer.generate("hi")
    assert reply.model == "backup"
    assert models.tried == ["primary", "backup"]


def test_it_keeps_going_down_the_chain(chain) -> None:
    models = chain({"primary", "backup"})
    assert model_layer.generate("hi").model == "last-resort"
    assert len(models.tried) == 3


def test_a_bad_request_is_not_retried_on_other_models(chain) -> None:
    """Retrying a malformed prompt three times just fails three times."""
    models = chain({"primary", "backup", "last-resort"}, error="400 INVALID_ARGUMENT")
    with pytest.raises(RuntimeError, match="INVALID_ARGUMENT"):
        model_layer.generate("hi")
    assert models.tried == ["primary"]


def test_rate_limits_are_treated_as_retryable(chain) -> None:
    models = chain({"primary"}, error="429 RESOURCE_EXHAUSTED")
    assert model_layer.generate("hi").model == "backup"


def test_exhausting_every_model_raises_the_last_error(chain) -> None:
    chain({"primary", "backup", "last-resort"})
    with pytest.raises(RuntimeError, match="UNAVAILABLE"):
        model_layer.generate("hi")


def test_chain_has_no_duplicates(monkeypatch) -> None:
    """A fallback that repeats the preferred model wastes a call on a busy one."""
    monkeypatch.setattr(
        model_layer, "settings", Settings(model="primary", fallback_models=("primary", "backup"))
    )
    assert model_layer.model_chain() == ["primary", "backup"]


def test_missing_credentials_are_reported_clearly(monkeypatch) -> None:
    monkeypatch.setattr(model_layer, "settings", Settings(google_api_key="", use_vertex=False))
    monkeypatch.setattr(model_layer, "_client", None)
    with pytest.raises(model_layer.NoModelAccess, match="GOOGLE_API_KEY"):
        model_layer.get_client()


def test_api_key_and_project_are_never_sent_together(monkeypatch) -> None:
    """Cloud Run sets GOOGLE_CLOUD_PROJECT on every service.

    Passing it alongside an API key makes the Gemini API reject the call with
    "does not support project/location", which only shows up once deployed.
    """
    captured: dict = {}

    class _Genai:
        @staticmethod
        def Client(**kwargs):  # noqa: N802 - mirrors the SDK's name
            captured.update(kwargs)
            return object()

    monkeypatch.setattr(
        model_layer,
        "settings",
        Settings(google_api_key="key", use_vertex=False, project="some-project"),
    )
    monkeypatch.setattr(model_layer, "_client", None)
    monkeypatch.setattr("google.genai.Client", _Genai.Client, raising=False)

    model_layer.get_client()
    assert captured.get("api_key") == "key"
    assert "project" not in captured
    assert "location" not in captured


def test_vertex_mode_sends_project_and_no_key(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        model_layer,
        "settings",
        Settings(google_api_key="key", use_vertex=True, project="p", location="us-central1"),
    )
    monkeypatch.setattr(model_layer, "_client", None)
    monkeypatch.setattr(
        "google.genai.Client",
        lambda **kw: (captured.update(kw), object())[1],
        raising=False,
    )

    model_layer.get_client()
    assert captured.get("vertexai") is True
    assert captured.get("project") == "p"
    assert "api_key" not in captured
