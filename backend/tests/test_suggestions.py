from app.services.chunker import Bullet
from app.services.suggestions import (
    SuggestionContext,
    generate_suggestions,
    has_metric,
    metrics_pct,
    starts_with_phrase,
)

GOOD_BULLETS = [
    Bullet("Built a payments API serving 12,000 users", "experience"),
    Bullet("Reduced latency by 35% with Redis", "experience"),
    Bullet("Automated deploys, cutting release time 4x", "projects"),
    Bullet("Designed a schema handling $2M in daily volume", "projects"),
]


def ctx(verbs, **overrides):
    values = dict(
        missing_required=[],
        missing_preferred=[],
        jd_has_skills=True,
        sections_present={"summary", "experience", "projects", "skills", "education"},
        bullets=GOOD_BULLETS,
        word_count=450,
        pages=1,
        semantic_score=70.0,
        keyword_score=60.0,
        weakest_requirement="Experience with Kubernetes",
        verbs=verbs,
    )
    values.update(overrides)
    return SuggestionContext(**values)


def types(suggestions):
    return [s["type"] for s in suggestions]


def test_strong_resume_gets_no_suggestions(verbs):
    assert generate_suggestions(ctx(verbs)) == []


def test_has_metric_ignores_years():
    assert has_metric("Improved accuracy by 12%")
    assert has_metric("Served 1,200 users")
    assert has_metric("Saved $3k per month")
    assert not has_metric("Intern, Jun 2021 - Aug 2022")
    assert not has_metric("Built a dashboard")


def test_metrics_pct():
    assert metrics_pct([]) == 0.0
    assert metrics_pct(GOOD_BULLETS[:2] + [Bullet("Built UI", "projects")] * 2) == 50.0


def test_starts_with_phrase_requires_word_boundary():
    assert starts_with_phrase("Responsible for APIs", ["responsible for"]) == "responsible for"
    assert starts_with_phrase("Used Docker", ["used"]) == "used"
    assert starts_with_phrase("Userland tools", ["used"]) is None


def test_missing_required_skills_are_high_priority_and_capped(verbs):
    missing = [f"Skill{i}" for i in range(7)]
    out = generate_suggestions(ctx(verbs, missing_required=missing))
    assert types(out).count("missing_required_skill") == 5
    assert "missing_required_skills_summary" in types(out)
    assert all(s["priority"] == "high" for s in out if s["type"].startswith("missing_required"))


def test_missing_preferred(verbs):
    out = generate_suggestions(ctx(verbs, missing_preferred=[f"P{i}" for i in range(10)]))
    msg = next(s["message"] for s in out if s["type"] == "missing_preferred_skills")
    assert "and 2 more" in msg


def test_zero_skill_jd_is_explained(verbs):
    assert "no_skills_in_jd" in types(generate_suggestions(ctx(verbs, jd_has_skills=False)))


def test_no_quantified_metrics(verbs):
    bullets = [Bullet("Built a REST API with FastAPI", "experience")] * 3
    out = generate_suggestions(ctx(verbs, bullets=bullets))
    assert "no_quantified_metrics" in types(out)


def test_few_quantified_metrics(verbs):
    bullets = [Bullet("Built API", "experience")] * 4 + [Bullet("Cut costs 10%", "experience")]
    assert "few_quantified_metrics" in types(generate_suggestions(ctx(verbs, bullets=bullets)))


def test_length_rules(verbs):
    assert "resume_too_short" in types(generate_suggestions(ctx(verbs, word_count=120)))
    assert "resume_too_long" in types(generate_suggestions(ctx(verbs, pages=3)))
    assert "resume_too_long" in types(generate_suggestions(ctx(verbs, word_count=1500)))


def test_section_rules(verbs):
    out = generate_suggestions(ctx(verbs, sections_present={"summary"}))
    assert {"no_sections_detected", "skills_section_missing", "experience_section_missing"} <= set(types(out))


def test_no_bullets(verbs):
    assert "no_bullets" in types(generate_suggestions(ctx(verbs, bullets=[])))


def test_weak_verbs_detected_and_message_has_no_resume_text(verbs):
    bullets = GOOD_BULLETS + [Bullet("Responsible for the secret Zeta project", "experience")]
    out = generate_suggestions(ctx(verbs, bullets=bullets))
    msg = next(s["message"] for s in out if s["type"] == "weak_action_verbs")
    assert "'responsible for'" in msg
    assert "Zeta" not in msg


def test_few_strong_verbs(verbs):
    bullets = [Bullet(f"Payments service number {i} with 10 users", "experience") for i in range(4)]
    assert "few_strong_verbs" in types(generate_suggestions(ctx(verbs, bullets=bullets)))


def test_long_bullets(verbs):
    long = Bullet("Built " + "very " * 45 + "long thing with 3 parts", "experience")
    out = generate_suggestions(ctx(verbs, bullets=GOOD_BULLETS + [long, long]))
    assert "long_bullets" in types(out)


def test_alignment_rules(verbs):
    out = generate_suggestions(ctx(verbs, semantic_score=10, keyword_score=5))
    assert {"low_semantic_alignment", "low_keyword_overlap"} <= set(types(out))
    msg = next(s["message"] for s in out if s["type"] == "low_semantic_alignment")
    assert "Kubernetes" in msg


def test_sorted_by_priority(verbs):
    out = generate_suggestions(ctx(verbs, missing_required=["X"], word_count=100, keyword_score=0))
    order = {"high": 0, "medium": 1, "low": 2}
    ranks = [order[s["priority"]] for s in out]
    assert ranks == sorted(ranks)
