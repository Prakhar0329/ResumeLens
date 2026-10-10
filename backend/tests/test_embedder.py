import sys
import types

import numpy as np
import pytest

from app.services.embedder import Embedder, EmbeddingCache, cosine_matrix
from tests.conftest import FakeEmbedder


class _FakeST:
    instances = 0

    def __init__(self, name, device=None, cache_folder=None):
        _FakeST.instances += 1
        self.name, self.device, self.cache_folder = name, device, cache_folder

    def get_sentence_embedding_dimension(self):
        return 4

    def encode(self, texts, batch_size, normalize_embeddings, convert_to_numpy, show_progress_bar):
        assert normalize_embeddings is True
        vecs = np.ones((len(texts), 4), dtype=np.float64)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


@pytest.fixture
def fake_st(monkeypatch):
    _FakeST.instances = 0
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return _FakeST


def test_embedder_loads_once_on_cpu_and_normalises(fake_st):
    emb = Embedder("all-MiniLM-L6-v2", batch_size=8, cache_dir="/tmp/models")
    assert not emb.loaded
    out = emb.encode(["a", "b"])
    emb.load()
    assert emb.loaded and fake_st.instances == 1
    assert out.shape == (2, 4) and out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert emb.encode([]).shape == (0, 4)


def test_cache_encodes_each_unique_text_once():
    fake = FakeEmbedder()
    cache = EmbeddingCache(fake)
    cache.encode(["a b", "c d", "a b"])
    cache.encode(["c d", "e f"])
    assert fake.calls == [["a b", "c d"], ["e f"]]
    assert cache.encode(["a b"]).shape == (1, 512)
    assert cache.encode([]).shape == (0, 0)


def test_cosine_matrix():
    a = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    b = np.array([[1.0, 0.0]], dtype=np.float32)
    assert np.allclose(cosine_matrix(a, b), [[1.0], [0.0]])
    assert cosine_matrix(np.zeros((0, 2)), b).shape == (0, 1)


@pytest.mark.slow
def test_real_model_paraphrase_similarity():
    """Downloads all-MiniLM-L6-v2 (~90 MB) on first run. Run with: pytest -m slow"""
    pytest.importorskip("sentence_transformers")
    emb = Embedder("all-MiniLM-L6-v2")
    vecs = emb.encode(
        [
            "Built REST APIs in Python",
            "Developed Python web services exposing HTTP endpoints",
            "Baked sourdough bread every morning",
        ]
    )
    sim = cosine_matrix(vecs, vecs)
    assert sim[0, 1] > sim[0, 2]
