"""Frame detection. Separate from sentiment, topic and source orientation.

Tier 1: multilingual cue lexicon per frame; the evidence sentence is the article
sentence with the most cue hits (always quoted from the article, never generated).
Tier 2 (transformers): zero-shot NLI with the frame's hypothesis, used to confirm or
reject lexicon candidates and to score frames without lexical cues.
"""

from __future__ import annotations

from dataclasses import dataclass

from hudhud.nlp.text import normalize_for_matching, split_sentences, term_pattern


@dataclass
class FrameSpec:
    id: int
    slug: str
    hypothesis: str | None
    cues: list[str]


@dataclass
class FrameHit:
    frame_id: int
    slug: str
    score: float
    confidence: float
    evidence_sentence: str | None
    method: str


def detect_frames(
    text: str, frames: list[FrameSpec], use_models: bool = False, min_score: float = 0.35
) -> list[FrameHit]:
    sentences = split_sentences(text) or [text]
    norm_sentences = [normalize_for_matching(s) for s in sentences]
    hits: list[FrameHit] = []
    for fr in frames:
        per_sentence = []
        for orig, ns in zip(sentences, norm_sentences, strict=True):
            n = sum(1 for c in fr.cues if term_pattern(c).search(ns))
            per_sentence.append((n, orig))
        total = sum(n for n, _ in per_sentence)
        if total == 0:
            continue
        best_n, best_sentence = max(per_sentence, key=lambda x: x[0])
        score = round(min(1.0, 0.3 + 0.2 * total), 4)
        hits.append(
            FrameHit(fr.id, fr.slug, score, round(min(0.65, score * 0.8), 4), best_sentence, "lexicon")
        )

    if use_models and hits:
        try:
            from hudhud.nlp.classify import _zero_shot_pipeline

            clf = _zero_shot_pipeline()
            by_slug = {f.slug: f for f in frames}
            hyps = [by_slug[h.slug].hypothesis or f"This text uses a {h.slug} frame." for h in hits]
            out = clf(text[:1000], candidate_labels=hyps, multi_label=True, hypothesis_template="{}")
            nli = dict(zip(out["labels"], out["scores"], strict=True))
            for h, hyp in zip(hits, hyps, strict=True):
                p = float(nli.get(hyp, 0.0))
                h.score = round(0.4 * h.score + 0.6 * p, 4)
                h.confidence = round(p, 4)
                h.method = "lexicon+zero_shot"
        except Exception:
            pass
    return sorted([h for h in hits if h.score >= min_score], key=lambda h: -h.score)
