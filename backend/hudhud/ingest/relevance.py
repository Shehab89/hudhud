"""Yemen-relevance filter for general (non-Yemen-specific) feeds."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from hudhud.config import get_settings
from hudhud.nlp.text import find_term, normalize_for_matching


@lru_cache
def _terms(seeds_dir: str) -> tuple[list[str], list[str]]:
    data = yaml.safe_load((Path(seeds_dir) / "yemen_relevance.yaml").read_text(encoding="utf-8"))
    strong = [t for terms in data.get("strong", {}).values() for t in terms]
    weak = [t for terms in data.get("weak", {}).values() for t in terms]
    return strong, weak


def yemen_relevance(title: str, summary: str = "") -> float:
    """0..1 score. A strong term in the title => 1.0; in the summary => 0.8;
    only weak terms => 0.4; nothing => 0."""
    strong, weak = _terms(str(get_settings().seeds_dir))
    t = normalize_for_matching(title)
    s = normalize_for_matching(summary)
    if any(find_term(term, t) for term in strong):
        return 1.0
    if any(find_term(term, s) for term in strong):
        return 0.8
    if any(find_term(term, t + " " + s) for term in weak):
        return 0.4
    return 0.0


RELEVANCE_THRESHOLD = 0.75
