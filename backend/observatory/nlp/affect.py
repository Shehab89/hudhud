"""Sentiment (polarity + intensity), emotions and political/emotional tone.

All outputs are probability-like distributions with a confidence, the method used and
the evidence words or sentence. A political-news caveat applies throughout: much
news text is reported speech, so negative wording often describes events rather than
the outlet's stance. These are descriptive features of the text, not of the outlet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from observatory.config import get_settings
from observatory.nlp.text import normalize_for_matching, term_pattern

EMOTIONS = ["anger", "fear", "sadness", "joy", "disgust", "surprise", "hope", "frustration", "anxiety"]
TONES = [
    "threatening",
    "accusatory",
    "conciliatory",
    "confrontational",
    "alarmist",
    "reassuring",
    "celebratory",
    "critical",
    "defensive",
    "supportive",
    "dismissive",
]


@dataclass
class AffectResult:
    label: str
    scores: dict[str, float]
    confidence: float
    method: str
    intensity: float | None = None
    evidence: list[str] = field(default_factory=list)


@lru_cache
def _lexicons(seeds_dir: str) -> dict:
    return yaml.safe_load((Path(seeds_dir) / "lexicons.yaml").read_text(encoding="utf-8"))


def _lex() -> dict:
    return _lexicons(str(get_settings().seeds_dir))


def _hits(words_by_lang: dict[str, list[str]], norm_text: str) -> list[str]:
    found = []
    for words in words_by_lang.values():
        for w in words:
            if term_pattern(w).search(norm_text):
                found.append(w)
    return found


# ---------------------------------------------------------------- lexicon (tier 1 fallback)


def lexicon_sentiment(text: str) -> AffectResult:
    norm = normalize_for_matching(text)
    lex = _lex()["sentiment"]
    pos = _hits(lex["positive"], norm)
    neg = _hits(lex["negative"], norm)
    p, n = len(pos), len(neg)
    total = p + n
    if total == 0:
        return AffectResult(
            "neutral", {"positive": 0.1, "neutral": 0.8, "negative": 0.1}, 0.4, "lexicon", 0.0
        )
    pos_share = (p + 0.5) / (total + 1.0)
    neg_share = (n + 0.5) / (total + 1.0)
    strength = min(1.0, total / 4.0)
    scores = {
        "positive": round(pos_share * strength, 4),
        "negative": round(neg_share * strength, 4),
    }
    scores["neutral"] = round(max(0.0, 1.0 - scores["positive"] - scores["negative"]), 4)
    label = max(scores, key=scores.get)
    intensity = round(abs(scores["positive"] - scores["negative"]), 4)
    # lexicon confidence is capped: it cannot read negation, reported speech or irony
    confidence = round(min(0.7, 0.35 + 0.1 * total) * (0.6 + 0.4 * abs(pos_share - neg_share)), 4)
    return AffectResult(label, scores, confidence, "lexicon", intensity, pos + neg)


def lexicon_distribution(kind: str, text: str) -> AffectResult:
    norm = normalize_for_matching(text)
    table = _lex()[kind]
    counts = {k: len(_hits(v, norm)) for k, v in table.items()}
    total = sum(counts.values())
    if total == 0:
        return AffectResult("none", {k: 0.0 for k in table}, 0.3, "lexicon", None)
    scores = {k: round(v / total, 4) for k, v in counts.items()}
    label = max(scores, key=scores.get)
    evidence = [w for k, v in table.items() if counts[k] for w in _hits(v, norm)]
    confidence = round(min(0.65, 0.3 + 0.1 * total) * scores[label], 4)
    return AffectResult(label, scores, confidence, "lexicon", None, evidence[:10])


# ---------------------------------------------------------------- transformers


@lru_cache
def _sentiment_pipe(model: str):
    from transformers import pipeline

    return pipeline("text-classification", model=model, top_k=None, truncation=True, device=-1)


_LABEL_MAP = {
    "positive": "positive",
    "neutral": "neutral",
    "negative": "negative",
    "pos": "positive",
    "neu": "neutral",
    "neg": "negative",
    "label_0": "negative",
    "label_1": "neutral",
    "label_2": "positive",
}


def transformer_sentiment(text: str, language: str | None) -> AffectResult:
    s = get_settings()
    model = s.sentiment_model_ar if language == "ar" else s.sentiment_model
    out = _sentiment_pipe(model)(text[:1500])
    rows = out[0] if out and isinstance(out[0], list) else out
    scores = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    for r in rows:
        key = _LABEL_MAP.get(str(r["label"]).lower())
        if key:
            scores[key] = round(float(r["score"]), 4)
    label = max(scores, key=scores.get)
    intensity = round(abs(scores["positive"] - scores["negative"]), 4)
    return AffectResult(label, scores, scores[label], f"model:{model}", intensity)


def zero_shot_distribution(kind: str, text: str) -> AffectResult:
    from observatory.nlp.classify import _zero_shot_pipeline

    labels = EMOTIONS if kind == "emotion" else TONES
    template = (
        "The emotion expressed in this text is {}." if kind == "emotion" else "The tone of this text is {}."
    )
    out = _zero_shot_pipeline()(
        text[:1000], candidate_labels=labels, multi_label=True, hypothesis_template=template
    )
    scores = {lab: round(float(sc), 4) for lab, sc in zip(out["labels"], out["scores"], strict=True)}
    label = max(scores, key=scores.get)
    return AffectResult(label, scores, scores[label], f"model:{get_settings().zero_shot_model}")


# ---------------------------------------------------------------- facade


def analyse_sentiment(text: str, language: str | None, use_models: bool) -> AffectResult:
    if use_models:
        try:
            return transformer_sentiment(text, language)
        except Exception:  # model unavailable at runtime -> fall back, recorded via method
            pass
    return lexicon_sentiment(text)


def analyse_distribution(kind: str, text: str, use_models: bool) -> AffectResult:
    if use_models:
        try:
            return zero_shot_distribution(kind, text)
        except Exception:
            pass
    return lexicon_distribution(kind, text)
