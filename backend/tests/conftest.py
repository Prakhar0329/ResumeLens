"""Shared fixtures.

* PDFs are generated in memory with reportlab, so the repo contains no binary files.
* ``FakeEmbedder`` is a deterministic hashed bag-of-words embedder. It keeps the test
  suite fast and offline; the real sentence-transformers model is exercised only by
  tests marked ``slow`` (run them with ``pytest -m slow``).
"""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import Settings
from app.main import DATA_DIR, build_analyzer, create_app
from app.services.analyzer import ResumeAnalyzer
from app.services.skill_extractor import SkillExtractor
from app.services.suggestions import VerbLists

FAKE_DIM = 512


class FakeEmbedder:
    """Deterministic stand-in for sentence-transformers: hashed word counts, L2-normalised."""

    model_name = "fake-hash-embedder"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def loaded(self) -> bool:
        return True

    def load(self) -> None:
        return None

    def encode(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        out = np.zeros((len(texts), FAKE_DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % FAKE_DIM] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


# --------------------------------------------------------------------- PDFs
def make_pdf(lines: list[str], pages: int = 1) -> bytes:
    """Render text lines onto one or more letter-size pages."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    for _ in range(pages):
        y = 750
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 14
            if y < 50:
                pdf.showPage()
                y = 750
        pdf.showPage()
    pdf.save()
    return buf.getvalue()


def make_image_only_pdf() -> bytes:
    """A 'scanned' PDF: one page containing only an image, no text layer."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    image = Image.new("RGB", (300, 300), "white")
    pdf.drawImage(ImageReader(image), 50, 400, 300, 300)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def make_encrypted_pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter, encrypt="secret-password")
    y = 750
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 14
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


SAMPLE_RESUME_LINES = [
    "Jane Doe",
    "jane.doe@example.com | +1 415 555 0134 | github.com/janedoe",
    "SUMMARY",
    "Backend-focused software engineer who builds reliable Python and Node.js services.",
    "EXPERIENCE",
    "Software Engineer Intern, Acme Corp  Jun 2023 - Aug 2023",
    "- Built a REST API in Python with FastAPI and PostgreSQL serving 12,000 daily users",
    "- Reduced p95 latency by 35% by adding Redis caching and query optimization",
    "- Responsible for writing unit tests with pytest and setting up GitHub Actions CI/CD",
    "PROJECTS",
    "- Developed a React and TypeScript dashboard deployed on AWS with Docker",
    "- Worked on a C++ path planner and a small C# Unity game",
    "SKILLS",
    "Python, JavaScript, TypeScript, C++, C#, SQL, Git, Linux, Agile",
    "EDUCATION",
    "B.Tech in Computer Science, Example University, 2020 - 2024, GPA 8.6/10",
]

SAMPLE_JD = """Backend Engineer

About us:
We are a fintech startup building payment tools.

Requirements:
- 2+ years of experience building REST APIs with Python and FastAPI
- Strong SQL skills and experience with PostgreSQL
- Experience with Docker and Kubernetes in production
- Must have experience writing unit tests

Nice to have:
- Experience with Kafka or RabbitMQ is a plus
- Familiarity with Terraform and AWS

Responsibilities:
- Design and build scalable microservices
- Collaborate with frontend engineers who use React

Benefits:
- Free lunch and Golang conference tickets
"""

NO_SKILL_JD = (
    "We are looking for a friendly and reliable person to greet visitors at our office front desk. "
    "You will answer phones, welcome guests warmly and keep the reception area tidy every day. "
    "Prior hospitality work would be ideal but is not required for this role."
)


@pytest.fixture(scope="session")
def sample_pdf() -> bytes:
    return make_pdf(SAMPLE_RESUME_LINES)


@pytest.fixture(scope="session")
def skill_extractor() -> SkillExtractor:
    extractor, _ = SkillExtractor.from_files(DATA_DIR / "skills.json", "en_core_web_sm")
    return extractor


@pytest.fixture(scope="session")
def verbs() -> VerbLists:
    return VerbLists.from_files(DATA_DIR / "weak_verbs.json", DATA_DIR / "strong_verbs.json")


def make_settings(tmp_dir: Path, **overrides) -> Settings:
    values = {
        "database_url": f"sqlite:///{(tmp_dir / 'test.db').as_posix()}",
        "preload_models": False,
        "rate_limit_enabled": False,
        "anthropic_api_key": None,
        "cors_origins": "http://localhost:3000",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture(scope="session")
def analyzer(tmp_path_factory: pytest.TempPathFactory) -> ResumeAnalyzer:
    return build_analyzer(make_settings(tmp_path_factory.mktemp("an")), FakeEmbedder())


@pytest.fixture(scope="module")
def app_client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    app = create_app(make_settings(tmp_path_factory.mktemp("api")), embedder=FakeEmbedder())
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(app_client: TestClient) -> Iterator[TestClient]:
    """Module-scoped app (spaCy loads once) with a clean DB and rate limiter per test."""
    app_client.delete("/api/v1/analyses")
    app_client.app.state.rate_limiter.reset()
    yield app_client
