from app.services.chunker import (
    chunk_resume,
    clean_jd,
    extract_bullets,
    looks_like_role_header,
    split_jd_requirements,
    split_sentences,
    tag_requirement,
    top_requirements,
)
from app.services.section_splitter import Section
from app.services.text_cleaner import BULLET, word_count

B = BULLET + " "


def test_split_sentences():
    assert split_sentences("Built X. Reduced Y by 30%! Is it? Yes") == [
        "Built X.",
        "Reduced Y by 30%!",
        "Is it?",
        "Yes",
    ]


def test_wrapped_bullet_lines_are_joined():
    text = f"{B}Built a payments service using FastAPI and\nPostgreSQL for 3 teams\n{B}Reduced costs by 20%"
    bullets = extract_bullets([Section("experience", text, "Experience")])
    assert [b.text for b in bullets] == [
        "Built a payments service using FastAPI and PostgreSQL for 3 teams",
        "Reduced costs by 20%",
    ]


def test_lowercase_continuation_joined():
    bullets = extract_bullets([Section("projects", f"{B}Designed a cache layer\nthat cut latency in half", None)])
    assert bullets[0].text == "Designed a cache layer that cut latency in half"


def test_fallback_bullets_without_glyphs_skip_role_headers():
    text = (
        "Software Engineer, Acme  Jun 2023 - Aug 2023\n"
        "Built a REST API in Python serving many daily users\n"
        "Reduced latency by 35% using Redis caching layers"
    )
    bullets = extract_bullets([Section("experience", text, None)])
    assert len(bullets) == 2
    assert all("Acme" not in b.text for b in bullets)


def test_role_header_detection():
    assert looks_like_role_header("Data Intern, Foo Inc  May 2022 - Present")
    assert looks_like_role_header("Backend Engineer 2019 - 2021")
    assert not looks_like_role_header("Built a REST API in Python")


def test_chunks_respect_word_bounds_and_keep_sections():
    long_bullet = B + " ".join(f"word{i}" for i in range(200))
    sections = [
        Section("experience", f"{B}Built a payments API in FastAPI with tests\n{long_bullet}", None),
        Section("skills", "Python, SQL\nDocker, Git", None),
    ]
    chunks = chunk_resume(sections, min_words=15, max_words=80)
    assert {c.section for c in chunks} == {"experience", "skills"}
    assert all(word_count(c.text) <= 80 for c in chunks)
    assert chunks[0].text == "Built a payments API in FastAPI with tests"


def test_short_units_are_merged():
    sections = [Section("skills", "Python\nSQL\nDocker\nGit", None)]
    chunks = chunk_resume(sections, min_words=15, max_words=80)
    assert len(chunks) == 1
    assert chunks[0].text == "Python SQL Docker Git"


def test_short_header_is_prefixed_to_next_bullet():
    sections = [Section("experience", f"Acme Corp\n{B}Built a REST API in Python serving daily users", None)]
    chunks = chunk_resume(sections)
    assert chunks[0].text.startswith("Acme Corp Built")


def test_tag_requirement_cues():
    assert tag_requirement("Experience with Kafka is a plus") == "preferred"
    assert tag_requirement("Nice to have: Terraform") == "preferred"
    assert tag_requirement("Must have 3+ years of Python") == "required"
    assert tag_requirement("At least 2 years with SQL") == "required"
    assert tag_requirement("Build dashboards") == "unspecified"
    assert tag_requirement("Build dashboards", "required") == "required"
    assert tag_requirement("Build dashboards", "skip") == "unspecified"


def test_jd_sections_drive_tags_and_boilerplate_is_skipped():
    jd = clean_jd(
        "About us:\nWe use Golang everywhere and love it.\n"
        "Requirements:\n- Python and SQL experience\n- Docker in production\n"
        "Nice to have:\n- Terraform and AWS knowledge\n"
        "Responsibilities:\n- Design scalable microservices\n"
        "Benefits:\n- Free lunch every single day\n"
    )
    reqs = split_jd_requirements(jd)
    by_text = {r.text: r.tag for r in reqs}
    assert by_text["Python and SQL experience"] == "required"
    assert by_text["Terraform and AWS knowledge"] == "preferred"
    assert by_text["Design scalable microservices"] == "unspecified"
    assert not any("Golang" in t or "lunch" in t for t in by_text)


def test_unknown_colon_heading_resets_context():
    reqs = split_jd_requirements(
        clean_jd("Requirements:\n- Python and SQL experience\nOur tools:\n- We use Jira daily")
    )
    assert {r.text: r.tag for r in reqs}["We use Jira daily"] == "unspecified"


def test_unstructured_jd_falls_back_to_sentences():
    reqs = split_jd_requirements("Hi.")
    assert len(reqs) == 1 and reqs[0].text == "Hi."


def test_max_requirements_cap():
    jd = "\n".join(f"- Requirement number {i} about Python" for i in range(100))
    assert len(split_jd_requirements(jd, max_requirements=10)) == 10


def test_top_requirements_orders_by_tag_then_position():
    jd = clean_jd("- Build dashboards for teams\n- Kafka experience is a plus\n- Must know Python well")
    tags = [r.tag for r in top_requirements(split_jd_requirements(jd), 3)]
    assert tags == ["required", "unspecified", "preferred"]
