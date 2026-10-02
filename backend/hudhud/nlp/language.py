"""Language identification (lingua, offline) with script-based fallback.

Dialect identification for Arabic (Yemeni vs Gulf vs Egyptian ...) is NOT reliable
on headline + excerpt length text; the platform records "ar" and leaves dialect
unknown rather than guessing (see docs/methodology.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from hudhud.nlp.text import detect_script

_LINGUA_CODES = {
    "ARABIC": "ar",
    "ENGLISH": "en",
    "FRENCH": "fr",
    "GERMAN": "de",
    "SPANISH": "es",
    "ITALIAN": "it",
    "TURKISH": "tr",
    "PERSIAN": "fa",
    "RUSSIAN": "ru",
    "CHINESE": "zh",
    "URDU": "ur",
    "JAPANESE": "ja",
}


@dataclass
class LanguageResult:
    language: str | None
    confidence: float
    script: str
    mixed: bool
    method: str


@lru_cache
def _detector():
    from lingua import Language, LanguageDetectorBuilder

    langs = [getattr(Language, name) for name in _LINGUA_CODES]
    return LanguageDetectorBuilder.from_languages(*langs).with_preloaded_language_models().build()


def detect_language(text: str, hint: str | None = None) -> LanguageResult:
    script, shares = detect_script(text)
    # mixed = two scripts each carrying at least 20% of letters (e.g. Arabic with English names)
    mixed = sum(1 for v in shares.values() if v >= 0.2) > 1
    if not text.strip():
        return LanguageResult(hint, 0.0, script, mixed, "none")
    try:
        values = _detector().compute_language_confidence_values(text)
    except Exception:  # pragma: no cover - lingua missing
        values = []
    if values:
        top = values[0]
        code = _LINGUA_CODES.get(top.language.name)
        conf = float(top.value)
        # short Arabic-script text: lingua sometimes confuses ar/fa/ur; trust the feed hint
        if hint and hint != code and conf < 0.6 and hint in _LINGUA_CODES.values():
            return LanguageResult(hint, 0.6, script, mixed, "feed_hint")
        return LanguageResult(code, round(conf, 4), script, mixed, "lingua")
    fallback = {"Arab": "ar", "Cyrl": "ru", "Hani": "zh"}.get(script, hint)
    return LanguageResult(fallback, 0.5 if fallback else 0.0, script, mixed, "script")
