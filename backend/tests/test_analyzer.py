import pytest

from app.errors import InvalidJobDescriptionError
from app.services.analyzer import redact_for_storage, sha256_hex
from tests.conftest import NO_SKILL_JD, SAMPLE_JD


def test_full_analysis(analyzer, sample_pdf):
    result = analyzer.analyze(sample_pdf, SAMPLE_JD)
    assert 0 <= result.overall_score <= 100
    assert result.overall_score == round(result.overall_score, 1)
    w = result.score_breakdown.weights
    assert w.skill_coverage + w.semantic_similarity + w.keyword_overlap == pytest.approx(1.0, abs=1e-3)

    matched = {s.name: s.in_jd_as for s in result.matched_skills}
    missing = {s.name: s.in_jd_as for s in result.missing_skills}
    assert matched["Python"] == "required"
    assert matched["AWS"] == "preferred"
    assert missing["Kubernetes"] == "required"
    assert missing["Terraform"] == "preferred"
    assert "Go" not in matched and "Go" not in missing  # only mentioned under "Benefits"
    assert {e.name for e in result.extra_skills} >= {"C++", "C#"}

    tags = [s.in_jd_as for s in result.missing_skills]
    assert tags == sorted(tags, key={"required": 0, "unspecified": 1, "preferred": 2}.get)

    assert {s.section for s in result.section_scores} >= {"experience", "projects", "skills"}
    assert 0 < len(result.requirement_matches) <= 10
    assert result.requirement_matches[0].requirement_type == "required"
    assert all(m.best_chunk for m in result.requirement_matches)

    assert result.resume_stats.pages == 1
    assert result.resume_stats.bullet_count == 5
    assert result.resume_stats.bullets_with_numbers_pct == 40.0
    assert "weak_action_verbs" in {s.type for s in result.suggestions}
    assert result.model_info.spacy_model in ("en_core_web_sm", "blank:en")
    assert not result.stored and not result.redacted


def test_no_pii_in_result(analyzer, sample_pdf):
    blob = analyzer.analyze(sample_pdf, SAMPLE_JD).model_dump_json()
    assert "jane.doe@example.com" not in blob
    assert "555 0134" not in blob
    assert "github.com" not in blob


def test_zero_skill_jd_redistributes(analyzer, sample_pdf):
    result = analyzer.analyze(sample_pdf, NO_SKILL_JD)
    assert result.score_breakdown.skill_weight_redistributed
    assert result.score_breakdown.weights.skill_coverage == 0
    assert result.matched_skills == [] and result.missing_skills == []
    assert "no_skills_in_jd" in {s.type for s in result.suggestions}


@pytest.mark.parametrize("jd", ["too short", "x" * 15001])
def test_jd_length_validation(analyzer, jd):
    with pytest.raises(InvalidJobDescriptionError):
        analyzer.validate_jd(jd)


def test_extra_skills_capped(analyzer):
    resume = analyzer.prepare_resume_text(
        "SKILLS\nPython Java Go Rust Ruby PHP Kotlin Scala Perl Lua Haskell Elixir Erlang Clojure Dart "
        "Julia MATLAB Fortran COBOL Groovy",
        pages=1,
    )
    jd = analyzer.prepare_jd(SAMPLE_JD)
    _, _, extra = analyzer._skill_lists(resume, jd)
    assert len(extra) == analyzer.settings.max_extra_skills


def test_redaction_removes_resume_excerpts(analyzer, sample_pdf):
    result = analyzer.analyze(sample_pdf, SAMPLE_JD)
    stored = redact_for_storage(result)
    assert stored.stored and stored.redacted
    assert all(m.best_chunk is None for m in stored.requirement_matches)
    assert all(m.best_chunk for m in result.requirement_matches)  # original untouched


def test_sha256():
    assert sha256_hex("abc") == sha256_hex(b"abc")
    assert len(sha256_hex(b"")) == 64
