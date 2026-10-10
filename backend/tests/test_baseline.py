from app.services.baseline import tfidf_cosine


def test_identical_texts_score_one():
    text = "Python developer with FastAPI and PostgreSQL experience"
    assert tfidf_cosine(text, text) > 0.99


def test_related_beats_unrelated():
    jd = "Backend engineer with Python, FastAPI, PostgreSQL and Docker"
    related = "Built FastAPI services in Python backed by PostgreSQL, shipped with Docker"
    unrelated = "Pastry chef specialising in croissants and sourdough bread"
    assert tfidf_cosine(related, jd) > tfidf_cosine(unrelated, jd)
    assert tfidf_cosine(unrelated, jd) == 0.0


def test_symbol_terms_are_kept():
    assert tfidf_cosine("C++ developer", "C++") > 0
    assert tfidf_cosine("Node.js", "Node.js engineer") > 0


def test_empty_or_stopword_only_inputs():
    assert tfidf_cosine("", "anything") == 0.0
    assert tfidf_cosine("the and of", "a an the") == 0.0
