"""Dictionary-based actor and place recognition from the entity alias table.

Deterministic and explainable: every mention stores the exact surface form, the
alias it matched (so terminology can be compared across outlets) and the sentence.
Overlapping matches resolve to the longest one ("عبدالملك الحوثي" beats "الحوثي").
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatory.db import models as m
from observatory.nlp.text import normalize_for_matching, split_sentences, term_pattern


@dataclass(frozen=True)
class AliasEntry:
    alias_id: int
    entity_id: int
    entity_type: str
    normalized: str
    language: str
    probe: str  # cheap substring pre-filter


@dataclass
class Mention:
    alias_id: int
    entity_id: int
    entity_type: str
    surface_form: str
    field: str
    start: int
    end: int
    sentence: str


class Gazetteer:
    def __init__(self, entries: list[AliasEntry]):
        self.entries = sorted(entries, key=lambda e: -len(e.normalized))

    @classmethod
    def from_db(cls, session: Session) -> Gazetteer:
        rows = session.execute(
            select(
                m.EntityAlias.id,
                m.EntityAlias.entity_id,
                m.Entity.entity_type,
                m.EntityAlias.normalized_form,
                m.EntityAlias.language,
            )
            .join(m.Entity, m.Entity.id == m.EntityAlias.entity_id)
            .where(m.EntityAlias.match.is_(True))
        ).all()
        entries = []
        for alias_id, entity_id, etype, norm, lang in rows:
            core = norm[2:] if norm.startswith("ال") and len(norm) > 4 else norm
            entries.append(AliasEntry(alias_id, entity_id, etype, norm, lang, core[:3]))
        return cls(entries)

    def find(self, text: str, field: str) -> list[Mention]:
        """Find mentions in ``text``. Offsets refer to the normalised text, which keeps a
        1:1 character correspondence with the original for most inputs; the stored
        sentence is taken from the original text."""
        if not text:
            return []
        norm = normalize_for_matching(text)
        taken: list[tuple[int, int]] = []
        found: list[Mention] = []
        sentences = split_sentences(text) or [text]
        norm_sentences = [normalize_for_matching(s) for s in sentences]
        for e in self.entries:
            if e.probe not in norm:
                continue
            for match in term_pattern(e.normalized).finditer(norm):
                s, t = match.span()
                if any(s < b and t > a for a, b in taken):
                    continue
                taken.append((s, t))
                surface = norm[s:t].strip()
                sentence = next(
                    (orig for orig, ns in zip(sentences, norm_sentences, strict=False) if surface in ns),
                    sentences[0],
                )
                found.append(
                    Mention(
                        e.alias_id,
                        e.entity_id,
                        e.entity_type,
                        _original_span(text, norm, s, t),
                        field,
                        s,
                        t,
                        sentence,
                    )
                )
        return sorted(found, key=lambda x: x.start)


def _original_span(original: str, norm: str, s: int, t: int) -> str:
    """Best-effort surface form in the original script/casing."""
    if len(original) == len(norm):
        return original[s:t].strip()
    return norm[s:t].strip()
