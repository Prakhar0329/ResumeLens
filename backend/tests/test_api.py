from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import (
    SAMPLE_JD,
    SAMPLE_RESUME_LINES,
    FakeEmbedder,
    make_image_only_pdf,
    make_pdf,
    make_settings,
)

API = "/api/v1"


def analyze(client, pdf, jd=SAMPLE_JD, save=True, filename="resume.pdf"):
    return client.post(
        f"{API}/analyze",
        files={"resume": (filename, pdf, "application/pdf")},
        data={"jd_text": jd, "save": str(save).lower()},
    )


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["models"]["skills_count"] >= 300
    assert body["llm_enabled"] is False
    assert body["config"]["weights"] == {"skill_coverage": 0.5, "semantic_similarity": 0.35, "keyword_overlap": 0.15}
    assert body["config"]["limits"]["max_jd_chars"] == 15000
    assert r.headers["X-Request-ID"]


def test_request_id_is_echoed(client):
    r = client.get(f"{API}/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_cors_preflight(client):
    r = client.options(
        f"{API}/analyze",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    r = client.options(
        f"{API}/analyze",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_analyze_valid_and_saved(client, sample_pdf):
    r = analyze(client, sample_pdf)
    assert r.status_code == 200, r.text
    body = r.json()
    expected_keys = {
        "analysis_id",
        "created_at",
        "overall_score",
        "verdict",
        "score_breakdown",
        "matched_skills",
        "missing_skills",
        "extra_skills",
        "section_scores",
        "requirement_matches",
        "suggestions",
        "resume_stats",
        "model_info",
        "stored",
        "redacted",
    }
    assert set(body) == expected_keys
    assert body["stored"] is True and body["redacted"] is False
    assert body["requirement_matches"][0]["best_chunk"]

    stored = client.get(f"{API}/analyses/{body['analysis_id']}")
    assert stored.status_code == 200
    stored_body = stored.json()
    assert stored_body["redacted"] is True
    assert all(m["best_chunk"] is None for m in stored_body["requirement_matches"])
    assert stored_body["overall_score"] == body["overall_score"]


def test_analyze_save_false_stores_nothing(client, sample_pdf):
    r = analyze(client, sample_pdf, save=False)
    assert r.status_code == 200
    assert r.json()["stored"] is False
    assert client.get(f"{API}/analyses").json()["total"] == 0
    assert_error(client.get(f"{API}/analyses/{r.json()['analysis_id']}"), 404, "not_found")


def test_wrong_file_type(client):
    assert_error(analyze(client, b"plain text resume", filename="resume.txt"), 415, "unsupported_media_type")


def test_oversized_file(client):
    big = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024 + 1)
    assert_error(analyze(client, big), 413, "file_too_large")


def test_too_many_pages(client):
    assert_error(analyze(client, make_pdf(SAMPLE_RESUME_LINES, pages=11)), 413, "too_many_pages")


def test_scanned_pdf(client):
    assert_error(analyze(client, make_image_only_pdf()), 422, "unreadable_pdf")


def test_short_jd(client, sample_pdf):
    assert_error(analyze(client, sample_pdf, jd="Python developer"), 422, "invalid_job_description")


def test_missing_fields(client):
    assert_error(client.post(f"{API}/analyze", data={"jd_text": SAMPLE_JD}), 422, "validation_error")


def test_history_pagination_and_summary(client, sample_pdf):
    ids = [analyze(client, sample_pdf).json()["analysis_id"] for _ in range(3)]
    page = client.get(f"{API}/analyses", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 3 and page["limit"] == 2 and len(page["items"]) == 2
    assert page["items"][0]["analysis_id"] == ids[-1]  # newest first
    assert set(page["items"][0]) == {"analysis_id", "created_at", "overall_score", "verdict", "top_missing_skills"}
    assert page["items"][0]["top_missing_skills"][0] == "Kubernetes"
    assert len(client.get(f"{API}/analyses", params={"offset": 2}).json()["items"]) == 1
    assert_error(client.get(f"{API}/analyses", params={"limit": 0}), 422, "validation_error")


def test_delete_one_and_all(client, sample_pdf):
    first = analyze(client, sample_pdf).json()["analysis_id"]
    analyze(client, sample_pdf)
    assert client.delete(f"{API}/analyses/{first}").json() == {"deleted": 1}
    assert_error(client.delete(f"{API}/analyses/{first}"), 404, "not_found")
    assert client.delete(f"{API}/analyses").json() == {"deleted": 1}
    assert client.get(f"{API}/analyses").json()["total"] == 0


def test_rewrite_bullet_returns_501_without_key(client):
    r = client.post(f"{API}/rewrite-bullet", json={"bullet": "Worked on the API", "target_skills": ["FastAPI"]})
    assert_error(r, 501, "feature_unavailable")


def test_rewrite_bullet_validation(client):
    assert_error(client.post(f"{API}/rewrite-bullet", json={"bullet": "x"}), 422, "validation_error")


def test_unknown_route_uses_error_format(client):
    assert_error(client.get(f"{API}/nope"), 404, "not_found")


def test_rate_limit(tmp_path, sample_pdf):
    app = create_app(make_settings(tmp_path, rate_limit_enabled=True, rate_limit_per_minute=2), FakeEmbedder())
    with TestClient(app) as c:
        assert analyze(c, sample_pdf, save=False).status_code == 200
        assert analyze(c, sample_pdf, save=False).status_code == 200
        r = analyze(c, sample_pdf, save=False)
        assert_error(r, 429, "rate_limited")
        assert int(r.headers["Retry-After"]) >= 1
        # Separate budget per endpoint.
        assert c.get(f"{API}/health").status_code == 200


def test_unhandled_errors_return_500_format(tmp_path, sample_pdf, monkeypatch):
    app = create_app(make_settings(tmp_path), FakeEmbedder())
    with TestClient(app, raise_server_exceptions=False) as c:

        def boom(*args, **kwargs):
            raise RuntimeError("secret resume text must not leak")

        monkeypatch.setattr(c.app.state.analyzer, "analyze", boom)
        r = analyze(c, sample_pdf)
        assert_error(r, 500, "internal_error")
        assert "secret" not in r.text


def test_root(client):
    assert client.get("/").json()["docs"] == "/docs"
