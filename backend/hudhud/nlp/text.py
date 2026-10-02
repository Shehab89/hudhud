"""Text normalisation for matching, hashing and search.

The original text is always stored untouched. These functions produce *derived*
forms used for matching only. Arabic normalisation is deliberately conservative:
it folds orthographic variation (alef forms, alef maqsura, ta marbuta, diacritics,
tatweel, digits) but does not stem, so names are not over-normalised.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from functools import lru_cache

ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
ALEF_VARIANTS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
YEH_VARIANTS = str.maketrans({"ى": "ي", "ی": "ي", "ئ": "ي"})
TEH_MARBUTA = str.maketrans({"ة": "ه"})
WAW_HAMZA = str.maketrans({"ؤ": "و"})
KAF_PERSIAN = str.maketrans({"ک": "ك"})
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ARABIC_PUNCT = str.maketrans({"،": ",", "؛": ";", "؟": "?", "«": '"', "»": '"'})
ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

ARABIC_CHAR = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]")
LATIN_CHAR = re.compile(r"[A-Za-zÀ-ɏ]")
CYRILLIC_CHAR = re.compile(r"[Ѐ-ӿ]")
CJK_CHAR = re.compile(r"[一-鿿぀-ヿ]")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(TAG_RE.sub(" ", text))
    return WS_RE.sub(" ", ZERO_WIDTH.sub("", text)).strip()


def normalize_arabic(text: str, fold_teh_marbuta: bool = True) -> str:
    text = ARABIC_DIACRITICS.sub("", text).replace(TATWEEL, "")
    text = text.translate(ALEF_VARIANTS).translate(YEH_VARIANTS).translate(WAW_HAMZA).translate(KAF_PERSIAN)
    if fold_teh_marbuta:
        text = text.translate(TEH_MARBUTA)
    return text


def normalize_for_matching(text: str | None) -> str:
    """Lowercased, accent- and Arabic-orthography-folded form used for matching and search."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", ZERO_WIDTH.sub("", text))
    text = text.translate(ARABIC_DIGITS).translate(ARABIC_PUNCT)
    text = normalize_arabic(text)
    text = text.replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    # strip Latin accents (é -> e) but keep non-Latin scripts intact
    decomposed = unicodedata.normalize("NFD", text)
    text = "".join(c for c in decomposed if not (unicodedata.category(c) == "Mn" and ord(c) < 0x0600))
    text = unicodedata.normalize("NFC", text).lower()
    return WS_RE.sub(" ", text).strip()


def content_hash(*parts: str | None) -> str:
    joined = "\n".join(normalize_for_matching(p) for p in parts if p)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def detect_script(text: str) -> tuple[str, dict[str, float]]:
    """Dominant script and share of each script among letters."""
    counts = {
        "Arab": len(ARABIC_CHAR.findall(text)),
        "Latn": len(LATIN_CHAR.findall(text)),
        "Cyrl": len(CYRILLIC_CHAR.findall(text)),
        "Hani": len(CJK_CHAR.findall(text)),
    }
    total = sum(counts.values()) or 1
    shares = {k: v / total for k, v in counts.items() if v}
    dominant = max(counts, key=counts.get) if any(counts.values()) else "Zyyy"
    return dominant, shares


SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟。])\s+|\n+|(?<=[.!?؟])(?=[\"'«»])")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENTENCE_SPLIT.split(text or "") if p and p.strip()]
    return [p for p in parts if len(p) > 2]


# ---------------------------------------------------------------- term matching

# Arabic proclitics that may attach to a word: conjunctions, prepositions, article.
_AR_PREFIX = r"(?:[وفبلك]{0,2}(?:ال|لل)?)"
# Arabic suffixes in normalised form (ة->ه): nisba adjective, plurals, duals and pronouns.
# A whitelist, not "any 0-3 letters": يمن must not match يمنع or يمنح, nor تعز match تعزيز.
_AR_SUFFIX = r"(?:يه|يين|يون|يان|ي|ون|ين|ات|ان|ه|ها|هم|هما|هن|كم|نا)?"
_LATIN_SUFFIX = r"(?:s|es|'s|i|is|n|en|e|ite|ites|ien|iens|ienne|iennes|isch|ische|ischen|í|íes)?"


def _is_arabic(term: str) -> bool:
    return bool(ARABIC_CHAR.search(term))


@lru_cache(maxsize=20000)
def term_pattern(term: str) -> re.Pattern[str]:
    """Regex matching a normalised term as a whole word, tolerant to clitics/inflection."""
    norm = normalize_for_matching(term)
    escaped = re.escape(norm).replace(r"\ ", r"\s+")
    if _is_arabic(norm):
        # drop a leading definite article from the term; prefix group re-adds it
        if norm.startswith("ال") and len(norm) > 4:
            norm = norm[2:]
            escaped = re.escape(norm).replace(r"\ ", r"\s+")
        # feminine ending: غارة (normalised غاره) should also match the plural غارات
        if norm.endswith("ه") and len(norm) > 3 and " " not in norm:
            escaped = re.escape(norm[:-1]) + "(?:ه|ات|ت)"
        return re.compile(rf"(?<![\w]){_AR_PREFIX}{escaped}{_AR_SUFFIX}(?![\w])")
    if CYRILLIC_CHAR.search(norm):
        return re.compile(rf"(?<![\w]){escaped}\w{{0,4}}(?![\w])")
    if CJK_CHAR.search(norm):
        return re.compile(escaped)
    return re.compile(rf"(?<![\w]){escaped}{_LATIN_SUFFIX}(?![\w])")


def find_term(term: str, normalized_text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in term_pattern(term).finditer(normalized_text)]


def count_terms(terms: list[str], normalized_text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in terms:
        n = len(term_pattern(t).findall(normalized_text))
        if n:
            out[t] = n
    return out
