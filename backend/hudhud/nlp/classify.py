"""Taxonomy classification with confidence-based routing.

Tier 1  keyword evidence (multilingual taxonomy terms) + embedding similarity to the
        category prototypes (only when a semantic embedder is available).
Tier 2  zero-shot NLI over the top candidates when tier-1 confidence is in the
        secondary band (transformers only).
Tier 3  LLM review when still below the secondary threshold and an LLM is configured.
Else    the article is marked ``uncertain``; no category is forced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.nlp.text import normalize_for_matching, term_pattern


@dataclass
class CategoryNode:
    id: int
    slug: str
    parent_id: int | None
    name_en: str
    name_ar: str | None
    terms: list[str]


@dataclass
class Classification:
    primary: int | None
    secondary: list[int]
    scores: dict[int, float]
    confidence: float
    route: str  # accepted | secondary | llm | uncertain
    method: str
    evidence: dict[int, list[str]] = field(default_factory=dict)


class TaxonomyClassifier:
    def __init__(self, nodes: list[CategoryNode], embedder=None):
        self.nodes = {n.id: n for n in nodes}
        self.embedder = embedder if embedder is not None and getattr(embedder, "semantic", False) else None
        self._proto: np.ndarray | None = None
        self._proto_ids: list[int] = []
        if self.embedder is not None:
            self._proto_ids = list(self.nodes)
            texts = [self._prototype_text(self.nodes[i]) for i in self._proto_ids]
            self._proto = self.embedder.embed_queries(texts)

    @classmethod
    def from_db(cls, session: Session, embedder=None) -> TaxonomyClassifier:
        nodes = []
        for c in session.scalars(select(m.Category).where(m.Category.is_emerging.is_(False))):
            terms = [t for lang_terms in (c.keywords or {}).values() for t in lang_terms]
            nodes.append(CategoryNode(c.id, c.slug, c.parent_id, c.name_en, c.name_ar, terms))
        return cls(nodes, embedder)

    @staticmethod
    def _prototype_text(n: CategoryNode) -> str:
        return f"{n.name_en} / {n.name_ar or ''}: " + ", ".join(n.terms[:12])

    def keyword_scores(self, title: str, body: str) -> tuple[dict[int, float], dict[int, list[str]]]:
        t, b = normalize_for_matching(title), normalize_for_matching(body)
        scores: dict[int, float] = {}
        evidence: dict[int, list[str]] = {}
        for node in self.nodes.values():
            s = 0.0
            for term in node.terms:
                pat = term_pattern(term)
                hits_t = len(pat.findall(t))
                hits_b = len(pat.findall(b))
                if hits_t or hits_b:
                    s += 2.0 * min(hits_t, 2) + 1.0 * min(hits_b, 3)
                    evidence.setdefault(node.id, []).append(term)
            if s:
                scores[node.id] = s
        # children support their parent
        for nid, s in list(scores.items()):
            parent = self.nodes[nid].parent_id
            if parent is not None:
                scores[parent] = scores.get(parent, 0.0) + 0.5 * s
        return scores, evidence

    def classify(self, title: str, body: str, doc_vec: np.ndarray | None = None) -> Classification:
        settings = get_settings()
        kw, evidence = self.keyword_scores(title, body)
        combined = dict(kw)
        method = "keywords"
        if self._proto is not None and doc_vec is not None:
            sims = self._proto @ doc_vec
            for nid, sim in zip(self._proto_ids, sims, strict=True):
                if sim > 0.80:  # e5 cosine sims cluster high; only strong matches count
                    combined[nid] = combined.get(nid, 0.0) + 4.0 * (float(sim) - 0.80) / 0.2
            method = "keywords+embedding"
        if not combined:
            return Classification(None, [], {}, 0.0, "uncertain", method, {})

        # prefer the most specific category: rank leaves first, roll up when no leaf has evidence
        leaves = {nid: s for nid, s in combined.items() if self.nodes[nid].parent_id is not None}
        pool = leaves or combined
        ranked = sorted(pool.items(), key=lambda kv: -kv[1])
        top_id, top = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = (top - second) / top if top else 0.0
        strength = 1.0 - math.exp(-top / 3.0)
        confidence = round(min(0.97, strength * (0.55 + 0.45 * margin)), 4)
        secondary = [nid for nid, s in ranked[1:6] if s >= 0.5 * top][:3]

        if confidence >= settings.accept_threshold:
            route = "accepted"
        elif confidence >= settings.secondary_threshold:
            route = "secondary"
        else:
            route = "llm" if settings.llm_provider != "none" and settings.anthropic_api_key else "uncertain"
        return Classification(top_id, secondary, combined, confidence, route, method, evidence)


@lru_cache
def _zero_shot_pipeline():
    import os

    import torch
    from transformers import pipeline

    # Measured on a 4-vCPU GitHub runner: torch defaults to 2 threads, and scoring the candidate
    # labels as one batch helps too (1.38 -> 0.94 s per label). Scores are unchanged.
    if (os.cpu_count() or 1) > torch.get_num_threads():
        torch.set_num_threads(os.cpu_count() or 1)
    return pipeline("zero-shot-classification", model=get_settings().zero_shot_model, device=-1, batch_size=8)


def zero_shot_rerank(text: str, labels: dict[int, str]) -> tuple[int, float, dict[int, float]]:
    """Tier-2: rerank candidate categories with multilingual NLI."""
    clf = _zero_shot_pipeline()
    names = list(labels.values())
    out: dict[str, Any] = clf(
        text[:1000], candidate_labels=names, multi_label=False, hypothesis_template="This text is about {}."
    )
    by_name = dict(zip(out["labels"], out["scores"], strict=True))
    scores = {cid: float(by_name[name]) for cid, name in labels.items()}
    best = max(scores, key=scores.get)
    return best, scores[best], scores
