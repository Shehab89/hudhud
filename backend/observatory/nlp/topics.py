"""Hybrid topic modelling.

Primary: BERTopic-style pipeline (multilingual embeddings -> UMAP -> HDBSCAN ->
c-TF-IDF), used when BERTopic is installed, embeddings are semantic and the corpus is
large enough. Fallback: k-means on the same embeddings + the same c-TF-IDF. Both keep
the raw statistical representation; human-readable labels (keywords or LLM) are
stored alongside it, never instead of it.

Daily runs assign new articles to the current model's topics by nearest centroid
(incremental); a full refit runs when the model is older than
``topic_full_retrain_days`` or the corpus has grown substantially. Topics from every
fit are linked to persistent ``global_topics`` by centroid similarity, which gives
topic continuity across refits and cross-lingual alignment (the embedding space is
shared across languages).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from sklearn.feature_extraction.text import CountVectorizer

from observatory.config import get_settings
from observatory.nlp.text import normalize_for_matching

TOKEN_PATTERN = r"(?u)\b[^\W\d_][^\W_]{2,}\b"


@lru_cache
def stopwords(seeds_dir: str) -> frozenset[str]:
    data = yaml.safe_load((Path(seeds_dir) / "stopwords.yaml").read_text(encoding="utf-8"))
    return frozenset(normalize_for_matching(w) for words in data.values() for w in words)


def _vectorizer(min_df: int = 2) -> CountVectorizer:
    stops = stopwords(str(get_settings().seeds_dir))
    return CountVectorizer(
        preprocessor=normalize_for_matching,
        token_pattern=TOKEN_PATTERN,
        stop_words=list(stops),
        ngram_range=(1, 2),
        min_df=min_df,
        max_df=0.5,
    )


@dataclass
class FittedTopic:
    index: int
    terms: list[tuple[str, float]]
    size: int
    centroid: np.ndarray
    member_rows: list[int]
    assign_threshold: float
    coherence: float | None = None


@dataclass
class TopicFit:
    algorithm: str
    topics: list[FittedTopic]
    assignments: list[int]  # topic index per document, -1 = outlier
    probabilities: list[float]
    metrics: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)


def ctfidf(
    docs: list[str], labels: list[int], top_n: int = 10
) -> tuple[dict[int, list[tuple[str, float]]], np.ndarray, CountVectorizer]:
    """Class-based TF-IDF (Grootendorst 2022): treat each cluster as one document."""
    clusters = sorted({lab for lab in labels if lab >= 0})
    vec = _vectorizer(min_df=2 if len(docs) >= 50 else 1)
    try:
        X = vec.fit_transform(docs)
    except ValueError:  # empty vocabulary
        return {c: [] for c in clusters}, np.zeros((0, 0)), vec
    lab = np.asarray(labels)
    rows = []
    for c in clusters:
        rows.append(np.asarray(X[lab == c].sum(axis=0)).ravel())
    if not rows:
        return {}, X, vec
    tf = np.vstack(rows).astype(np.float64)
    tf_norm = tf / (tf.sum(axis=1, keepdims=True) + 1e-12)
    avg_words = tf.sum() / max(len(clusters), 1)
    idf = np.log(1.0 + avg_words / (tf.sum(axis=0) + 1e-12))
    scores = tf_norm * idf
    vocab = np.asarray(vec.get_feature_names_out())
    reps = {}
    for i, c in enumerate(clusters):
        order = np.argsort(-scores[i])[:top_n]
        reps[c] = [(str(vocab[j]), round(float(scores[i, j]), 5)) for j in order if scores[i, j] > 0]
    return reps, X, vec


def npmi_coherence(X, vec: CountVectorizer, terms: list[str]) -> float | None:
    """Mean NPMI of top-term pairs using document co-occurrence in the corpus itself."""
    if X is None or X.shape[0] == 0 or len(terms) < 2:
        return None
    vocab = {t: i for i, t in enumerate(vec.get_feature_names_out())}
    idx = [vocab[t] for t in terms if t in vocab]
    if len(idx) < 2:
        return None
    B = (X[:, idx] > 0).astype(np.float64)
    n = B.shape[0]
    p = np.asarray(B.sum(axis=0)).ravel() / n
    co = (B.T @ B).toarray() / n if hasattr(B, "toarray") else (B.T @ B) / n
    vals = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            pab = co[a, b]
            if pab <= 0:
                vals.append(-1.0)
                continue
            pmi = math.log(pab / (p[a] * p[b] + 1e-12))
            vals.append(pmi / (-math.log(pab) + 1e-12))
    return round(float(np.mean(vals)), 4) if vals else None


def _kmeans(emb: np.ndarray) -> tuple[list[int], list[float], dict]:
    from sklearn.cluster import KMeans

    n = len(emb)
    k = int(min(40, max(3, round(math.sqrt(n / 2)))))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(emb)
    d = km.transform(emb)
    probs = (1.0 / (1.0 + d.min(axis=1))).tolist()
    return labels.tolist(), probs, {"k": k, "random_state": 42}


def _bertopic_clusters(docs: list[str], emb: np.ndarray) -> tuple[list[int], list[float], dict]:
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP

    n = len(docs)
    params = {
        "umap_n_neighbors": 15,
        "umap_n_components": 5,
        "hdbscan_min_cluster_size": max(8, n // 150),
        "random_state": 42,
    }
    model = BERTopic(
        umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42),
        hdbscan_model=HDBSCAN(
            min_cluster_size=params["hdbscan_min_cluster_size"],
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        ),
        vectorizer_model=_vectorizer(),
        calculate_probabilities=False,
        verbose=False,
    )
    topics, probs = model.fit_transform(docs, embeddings=emb)
    probs = [float(p) if p is not None else 0.0 for p in (probs if probs is not None else [0.0] * n)]
    return list(map(int, topics)), probs, params


def fit_topics(docs: list[str], emb: np.ndarray, semantic: bool) -> TopicFit:
    n = len(docs)
    algorithm = "kmeans_ctfidf"
    labels: list[int]
    try:
        if semantic and n >= 200:
            labels, probs, params = _bertopic_clusters(docs, emb)
            algorithm = "bertopic"
            if sum(1 for x in labels if x >= 0) < 0.3 * n:  # mostly outliers -> fall back
                raise ValueError("too many outliers")
        else:
            raise ImportError
    except (ImportError, ValueError):
        labels, probs, params = _kmeans(emb)
        algorithm = "kmeans_ctfidf"

    reps, X, vec = ctfidf(docs, labels)
    topics = []
    for c, terms in reps.items():
        rows = [i for i, lab in enumerate(labels) if lab == c]
        cent = emb[rows].mean(axis=0)
        cent = cent / (np.linalg.norm(cent) + 1e-12)
        sims = emb[rows] @ cent
        topics.append(
            FittedTopic(
                index=int(c),
                terms=terms,
                size=len(rows),
                centroid=cent,
                member_rows=rows,
                assign_threshold=float(np.percentile(sims, 10)) if len(rows) > 1 else 0.0,
                coherence=npmi_coherence(X, vec, [t for t, _ in terms[:10]]),
            )
        )
    top_terms = [t for tp in topics for t, _ in tp.terms[:10]]
    metrics = {
        "n_topics": len(topics),
        "outlier_ratio": round(sum(1 for x in labels if x < 0) / max(n, 1), 4),
        "diversity": round(len(set(top_terms)) / max(len(top_terms), 1), 4),
        "mean_coherence_npmi": round(
            float(np.mean([t.coherence for t in topics if t.coherence is not None])), 4
        )
        if any(t.coherence is not None for t in topics)
        else None,
    }
    return TopicFit(algorithm, topics, labels, probs, metrics, params)


def assign_incremental(
    emb: np.ndarray, centroids: np.ndarray, thresholds: np.ndarray
) -> list[tuple[int, float]]:
    """Nearest-centroid assignment for new documents; -1 when below the topic's threshold."""
    if len(centroids) == 0:
        return [(-1, 0.0)] * len(emb)
    sims = emb @ centroids.T
    best = sims.argmax(axis=1)
    out = []
    for i, j in enumerate(best):
        s = float(sims[i, j])
        out.append((int(j), s) if s >= thresholds[j] else (-1, s))
    return out


def keyword_label(terms: list[tuple[str, float]], n: int = 4) -> str:
    words = []
    for t, _ in terms:
        if any(t in w or w in t for w in words):
            continue
        words.append(t)
        if len(words) == n:
            break
    return " · ".join(words) if words else "(no distinctive terms)"
