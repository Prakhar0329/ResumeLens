"""TF-IDF baseline: lexical similarity between the full resume and the full JD.

Used as the ``keyword_overlap`` signal and, on its own, as the baseline the evaluation
harness compares the embedding method against.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.text_cleaner import normalize_tech_terms


def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        lowercase=True,
        strip_accents="unicode",
    )


def tfidf_cosine(resume_text: str, jd_text: str) -> float:
    """Cosine similarity of TF-IDF vectors fitted on just the two documents.

    Tech names are normalised first (C++ -> cplusplus, Node.js -> nodejs) so the default
    token pattern does not drop the symbols. Returns 0.0 if either text has no usable terms.
    """
    docs = [normalize_tech_terms(resume_text), normalize_tech_terms(jd_text)]
    if not all(d.strip() for d in docs):
        return 0.0
    try:
        matrix = build_vectorizer().fit_transform(docs)
    except ValueError:  # empty vocabulary (e.g. only stop words)
        return 0.0
    return float(cosine_similarity(matrix[0], matrix[1])[0, 0])
