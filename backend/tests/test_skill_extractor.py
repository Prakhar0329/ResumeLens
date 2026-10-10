import json

import pytest

from app.main import DATA_DIR
from app.services.skill_extractor import VALID_CATEGORIES, SkillExtractor, load_skills, load_spacy


def names(extractor, text):
    return extractor.extract_names(text)


def test_dataset_size_and_categories():
    skills = load_skills(DATA_DIR / "skills.json")
    assert len(skills) >= 300
    assert {s["category"] for s in skills} == VALID_CATEGORIES


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Wrote drivers in C++ and tools in C#", ["C++", "C#"]),
        ("Firmware for microcontrollers", ["Embedded Systems"]),
        ("Services on .NET and ASP.NET Core", [".NET", "ASP.NET"]),
        ("Backend in Node.js, frontend in Next.js", ["Node.js", "Next.js"]),
        ("Set up CI/CD pipelines", ["CI/CD"]),
        ("Models with scikit-learn", ["scikit-learn"]),
        ("Used sklearn daily", ["scikit-learn"]),
        ("C/C++ programming", ["C", "C++"]),
        ("F# scripts", ["F#"]),
    ],
)
def test_tricky_tokens(skill_extractor, text, expected):
    assert names(skill_extractor, text) == expected


def test_alias_resolution_and_dedup(skill_extractor):
    found = skill_extractor.extract("postgres, PostgreSQL and psql; k8s and Kubernetes; JS and javascript")
    by_name = {s.name: s.count for s in found}
    assert by_name == {"PostgreSQL": 3, "Kubernetes": 2, "JavaScript": 2}


def test_case_sensitive_strict_aliases(skill_extractor):
    assert names(skill_extractor, "Microservices in Go and Rust") == ["Microservices", "Go", "Rust"]
    assert names(skill_extractor, "I go to the gym and rust is bad") == []
    assert names(skill_extractor, "Advanced Excel") == ["Microsoft Excel"]
    assert names(skill_extractor, "I excel at teamwork") == ["Teamwork"]


def test_rest_is_not_matched_in_plain_english(skill_extractor):
    assert names(skill_extractor, "the rest of the team") == []
    assert names(skill_extractor, "Designed RESTful APIs") == ["REST"]


def test_longest_match_wins(skill_extractor):
    assert names(skill_extractor, "Spring Boot services") == ["Spring Boot"]
    assert names(skill_extractor, "React Native app") == ["React Native"]


def test_categories(skill_extractor):
    found = {s.name: s.category for s in skill_extractor.extract("Python, React, Docker, AWS, leadership")}
    assert found == {
        "Python": "language",
        "React": "frontend",
        "Docker": "devops",
        "AWS": "cloud",
        "Leadership": "soft_skill",
    }
    assert skill_extractor.category_of("PostgreSQL") == "database"


def test_empty_text(skill_extractor):
    assert skill_extractor.extract("   ") == []


def test_blank_spacy_fallback_gives_same_matches(monkeypatch):
    nlp, name = load_spacy("definitely_not_a_model_xyz")
    assert name == "blank:en"
    extractor = SkillExtractor(nlp, load_skills(DATA_DIR / "skills.json"))
    assert extractor.extract_names("C++ and Node.js with Docker") == ["C++", "Node.js", "Docker"]


def test_invalid_dataset_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"skills": [{"canonical": "X", "category": "nope", "aliases": ["x"]}]}))
    with pytest.raises(ValueError, match="Unknown category"):
        load_skills(bad)
    dup = tmp_path / "dup.json"
    entry = {"canonical": "X", "category": "tools", "aliases": ["x"]}
    dup.write_text(json.dumps({"skills": [entry, entry]}))
    with pytest.raises(ValueError, match="Duplicate"):
        load_skills(dup)
