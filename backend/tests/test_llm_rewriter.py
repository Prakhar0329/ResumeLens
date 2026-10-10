import types

import anthropic
import httpx
import pytest

from app.errors import FeatureUnavailableError, UpstreamServiceError
from app.services import llm_rewriter
from app.services.llm_rewriter import build_user_message, enforce_no_new_numbers, rewrite
from tests.conftest import make_settings


def test_disabled_without_key(tmp_path):
    with pytest.raises(FeatureUnavailableError) as exc:
        rewrite("Worked on the API", ["FastAPI"], settings=make_settings(tmp_path))
    assert exc.value.status_code == 501


def test_user_message_wraps_inputs_as_data():
    msg = build_user_message(" Worked on API ", ["FastAPI", " "], None)
    assert "<bullet>Worked on API</bullet>" in msg
    assert "<target_skills>FastAPI</target_skills>" in msg
    assert "(none provided)" in msg


def test_new_numbers_are_replaced_but_existing_kept():
    out = enforce_no_new_numbers(
        "Built S3 uploads for 3 teams",
        "Built S3 uploads for 3 teams, cutting latency 40% for [N users] and 2x throughput",
    )
    assert out == "Built S3 uploads for 3 teams, cutting latency [X]% for [N users] and [X]x throughput"


def _fake_client(text=None, error=None):
    class Messages:
        def create(self, **kwargs):
            assert kwargs["system"] == llm_rewriter.SYSTEM_PROMPT
            if error is not None:
                raise error
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)])

    class Client:
        def __init__(self, api_key, timeout):
            assert api_key == "test-key"
            self.messages = Messages()

    return Client


def test_rewrite_success_cleans_and_guards(monkeypatch, tmp_path):
    monkeypatch.setattr(anthropic, "Anthropic", _fake_client('• "Built a FastAPI service cutting latency by 50%"'))
    result = rewrite(
        "Worked on the API", ["FastAPI"], "Backend role", settings=make_settings(tmp_path, anthropic_api_key="test-key")
    )
    assert result.rewritten == "Built a FastAPI service cutting latency by [X]%"
    assert result.placeholders == ["[X]"]
    assert result.model == "claude-haiku-4-5-20251001"


def test_rewrite_empty_output(monkeypatch, tmp_path):
    monkeypatch.setattr(anthropic, "Anthropic", _fake_client("   "))
    with pytest.raises(UpstreamServiceError):
        rewrite("Worked on the API", [], settings=make_settings(tmp_path, anthropic_api_key="test-key"))


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIStatusError(
            "boom",
            response=httpx.Response(500, request=httpx.Request("POST", "https://api.anthropic.com")),
            body=None,
        ),
        anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
    ],
)
def test_provider_errors_map_to_502(monkeypatch, tmp_path, error):
    monkeypatch.setattr(anthropic, "Anthropic", _fake_client(error=error))
    with pytest.raises(UpstreamServiceError) as exc:
        rewrite("Worked on the API", [], settings=make_settings(tmp_path, anthropic_api_key="test-key"))
    assert exc.value.status_code == 502
