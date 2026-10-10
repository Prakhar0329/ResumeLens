import pytest

from app.services.section_splitter import detect_heading, split_sections


@pytest.mark.parametrize(
    "line,expected",
    [
        ("EXPERIENCE", "experience"),
        ("Work Experience", "experience"),
        ("Professional Experience:", "experience"),
        ("Internships", "experience"),
        ("E X P E R I E N C E", "experience"),
        ("Projects", "projects"),
        ("Academic Projects |", "projects"),
        ("Technical Skills", "skills"),
        ("Skills & Tools", "skills"),
        ("Tech Stack", "skills"),
        ("Education", "education"),
        ("Relevant Coursework", "education"),
        ("Professional Summary", "summary"),
        ("Objective", "summary"),
        ("Profile", "summary"),
        ("Certifications", "other"),
        ("Achievements & Awards", "other"),
        ("1. Publications", "other"),
    ],
)
def test_detects_headings(line, expected):
    assert detect_heading(line) == expected


@pytest.mark.parametrize(
    "line",
    ["Python, Java, SQL", "Built a REST API with FastAPI", "• Experience", "", "Languages: English, Hindi"],
)
def test_ignores_non_headings(line):
    assert detect_heading(line) is None


def test_long_line_is_not_heading():
    assert detect_heading("Experience " * 12) is None


def test_split_orders_sections_and_short_preamble_is_summary():
    text = "Jane Doe\nSoftware engineer\nEXPERIENCE\nBuilt things\nSKILLS\nPython\nEDUCATION\nB.Tech"
    sections = split_sections(text)
    assert [s.section for s in sections] == ["summary", "experience", "skills", "education"]
    assert sections[1].text == "Built things"
    assert sections[1].heading == "EXPERIENCE"
    assert sections[0].heading is None


def test_long_preamble_goes_to_other():
    preamble = " ".join(["word"] * 120)
    sections = split_sections(f"{preamble}\nSKILLS\nPython")
    assert sections[0].section == "other"


def test_certifications_map_to_other_and_empty_sections_dropped():
    sections = split_sections("PROJECTS\n\nCERTIFICATIONS\nAWS Certified Developer")
    assert [s.section for s in sections] == ["other"]


def test_no_headings_returns_single_section():
    sections = split_sections("Just some text without any headings at all.")
    assert len(sections) == 1
