import pytest

from app.services.text_cleaner import (
    BULLET,
    clean_text,
    normalize_bullets,
    normalize_tech_terms,
    normalize_text,
    strip_pii,
    word_count,
)


def test_unicode_nfkc_and_ligatures():
    assert normalize_text("ﬁnance ﬂow") == "finance flow"


def test_hyphenated_line_break_is_joined():
    assert normalize_text("Imple-\nmented caching") == "Implemented caching"


def test_hyphen_between_capitals_is_kept():
    assert "Objective-C" in normalize_text("Objective-C developer")


def test_whitespace_is_collapsed_but_lines_preserved():
    out = normalize_text("EXPERIENCE  \n\n\n\nBuilt\t\tthings   fast")
    assert out == "EXPERIENCE\n\nBuilt things fast"


def test_bullet_glyphs_are_unified():
    text = "• one\n▪ two\n● three\n- four\n* five\n\uf0b7 six"
    lines = normalize_text(text).split("\n")
    assert all(line.startswith(BULLET + " ") for line in lines)
    assert [line[2:] for line in lines] == ["one", "two", "three", "four", "five", "six"]


def test_lone_bullet_glyph_attaches_to_next_line():
    assert normalize_bullets("•\nBuilt an API") == f"{BULLET} Built an API"


def test_hyphen_inside_text_is_not_a_bullet():
    assert normalize_text("2019 - 2021") == "2019 - 2021"


def test_cid_artifacts_and_separators_removed():
    assert normalize_text("Skills (cid:127)\n--------\nPython") == "Skills\nPython"


def test_strip_pii_removes_contact_details_but_keeps_years():
    text = "jane@doe.com +91 98765 43210 https://jane.dev linkedin.com/in/jane 2019 - 2021 increased 35%"
    out = strip_pii(text)
    assert "jane@doe.com" not in out
    assert "98765" not in out
    assert "jane.dev" not in out
    assert "linkedin" not in out
    assert "2019 - 2021" in out
    assert "35%" in out


@pytest.mark.parametrize(
    "text,kept",
    [
        ("+91 98765 43210 2019 - 2021", "2019 - 2021"),
        ("(415) 555-0134 | Jun 2021", "Jun 2021"),
        ("+1 415 555 0134", ""),
        ("415.555.0134", ""),
        ("2018 - 2019 2020 - 2021", "2018 - 2019 2020 - 2021"),
        ("served 12,000 users at 3.5 ms", "served 12,000 users at 3.5 ms"),
        ("GPA 8.6/10", "GPA 8.6/10"),
    ],
)
def test_phone_stripping(text, kept):
    assert " ".join(strip_pii(text).split()).strip(" |") == kept


def test_clean_text_keeps_raw_and_separates_embedding_view():
    raw = "Jane\njane@x.com\n• Built X"
    cleaned = clean_text(raw)
    assert cleaned.raw == raw
    assert "jane@x.com" in cleaned.structured
    assert "jane@x.com" not in cleaned.for_embedding
    assert f"{BULLET} Built X" in cleaned.for_embedding


def test_tech_term_normalisation():
    out = normalize_tech_terms("C++, C#, F#, .NET, ASP.NET, Node.js, CI/CD, python3")
    for token in ("cplusplus", "csharp", "fsharp", "dotnet", "Nodejs", "cicd", "python"):
        assert token in out


def test_word_count():
    assert word_count("Built a REST API in C++ and Node.js") == 8
    assert word_count("") == 0
