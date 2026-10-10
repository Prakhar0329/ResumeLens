import pytest
from pydantic import ValidationError

from app.config import Settings
from app.errors import RateLimitExceededError
from app.middleware import InMemoryRateLimiter


def make(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_defaults_match_documented_values():
    s = make()
    assert (s.weight_skill, s.weight_semantic, s.weight_keyword) == (0.50, 0.35, 0.15)
    assert (s.semantic_floor, s.semantic_ceiling) == (0.20, 0.75)
    assert s.max_upload_bytes == 5 * 1024 * 1024
    assert s.cors_origin_list == ["http://localhost:3000"]
    assert s.llm_enabled is False


def test_env_vars_override(monkeypatch):
    monkeypatch.setenv("WEIGHT_SKILL", "0.7")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, https://b.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = make()
    assert s.weight_skill == 0.7
    assert s.cors_origin_list == ["http://a.com", "https://b.com"]
    assert s.llm_enabled


@pytest.mark.parametrize(
    "kwargs",
    [
        {"semantic_floor": 0.8, "semantic_ceiling": 0.2},
        {"keyword_floor": 0.5, "keyword_ceiling": 0.5},
        {"weight_skill": 0, "weight_semantic": 0, "weight_keyword": 0},
        {"min_jd_chars": 500, "max_jd_chars": 100},
        {"chunk_min_words": 50, "chunk_max_words": 20},
        {"weight_skill": -1},
    ],
)
def test_invalid_settings_rejected(kwargs):
    with pytest.raises(ValidationError):
        make(**kwargs)


def test_rate_limiter_window_and_eviction(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.middleware.time.monotonic", lambda: now[0])
    limiter = InMemoryRateLimiter(limit_per_minute=2)
    limiter.check("ip")
    limiter.check("ip")
    with pytest.raises(RateLimitExceededError):
        limiter.check("ip")
    now[0] += 61
    limiter.check("ip")  # window slid
    limiter._evict(now[0] + 120)
    assert limiter._hits == {}
