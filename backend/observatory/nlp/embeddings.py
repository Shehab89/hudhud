"""Multilingual document embeddings.

Default: intfloat/multilingual-e5-small (384 dims) via sentence-transformers, with the
"passage: " / "query: " prefixes the model was trained with. Fallback (no model
download possible): a character n-gram hashing vector. The fallback is lexical, not
semantic, and cannot align languages; results are registered under their own model
name so they are never confused with transformer embeddings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import numpy as np

from observatory.config import get_settings
from observatory.nlp.registry import use_transformers
from observatory.nlp.text import normalize_for_matching


class Embedder(Protocol):
    name: str
    version: str
    dim: int
    semantic: bool

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


class TransformerEmbedder:
    semantic = True

    def __init__(self, model_name: str, dim: int):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.dim = dim
        self.model = SentenceTransformer(model_name, device="cpu")
        native = self.model.get_sentence_embedding_dimension()
        self.truncate = native != dim
        self.version = f"st-{native}d" + (f"-trunc{dim}" if self.truncate else "")
        self.is_e5 = "e5" in model_name.lower()

    def _encode(self, texts: list[str], prefix: str) -> np.ndarray:
        texts = [f"{prefix}{t}" if self.is_e5 else t for t in texts]
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        vecs = np.asarray(vecs, dtype=np.float32)
        if self.truncate:  # Matryoshka-style truncation, then re-normalise
            vecs = vecs[:, : self.dim]
            vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        return vecs

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts, "passage: ")

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts, "query: ")


class HashingEmbedder:
    name = "observatory/hashing-embedding"
    version = "char3-5-v1"
    semantic = False

    def __init__(self, dim: int):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self.vectorizer = HashingVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            n_features=dim,
            alternate_sign=True,
            norm="l2",
            preprocessor=normalize_for_matching,
        )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform(texts).toarray().astype(np.float32)

    embed_queries = embed_documents


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if use_transformers():
        try:
            return TransformerEmbedder(s.embedding_model, s.embedding_dim)
        except Exception as exc:  # model not downloadable (offline sandbox, no HF access)
            import structlog

            structlog.get_logger().warning("embedding_model_unavailable_using_fallback", error=str(exc)[:200])
    return HashingEmbedder(s.embedding_dim)


def article_text(title: str, excerpt: str | None) -> str:
    return f"{title}. {excerpt or ''}".strip()
