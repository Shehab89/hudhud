"""Rule-based event extraction (trigger words + gazetteer locations).

An event candidate needs a trigger AND a known location in the same sentence (or in
the headline). The event date is the article's publication date, which is the date
the event was *reported*; reports published within one day for the same type and
place are merged into one event record. Events are stored separately from articles
so the same incident can be compared across outlets.
"""

from __future__ import annotations

from dataclasses import dataclass

from observatory.nlp.gazetteer import Mention
from observatory.nlp.text import normalize_for_matching, split_sentences, term_pattern

EVENT_TRIGGERS: dict[str, dict[str, list[str]]] = {
    "airstrike": {
        "en": ["airstrike", "air strike", "air raid", "airstrikes", "strikes on"],
        "ar": ["غارة", "غارات جوية", "قصف جوي", "شن طيران"],
        "fr": ["frappe aérienne", "frappes"],
        "de": ["Luftangriff", "Luftangriffe"],
        "es": ["bombardeo aéreo", "ataque aéreo"],
    },
    "missile_attack": {
        "en": ["missile", "ballistic missile"],
        "ar": ["صاروخ", "صاروخية", "باليستي"],
        "fr": ["missile"],
        "de": ["Rakete"],
        "es": ["misil"],
    },
    "drone_attack": {
        "en": ["drone attack", "drone strike", "drones"],
        "ar": ["طائرة مسيرة", "مسيرة", "مسيّرة"],
        "fr": ["drone"],
        "de": ["Drohne"],
        "es": ["dron"],
    },
    "maritime_attack": {
        "en": ["ship attacked", "vessel attacked", "attack on ship", "targeted a ship", "tanker"],
        "ar": ["استهداف سفينة", "استهداف السفن", "سفينة", "ناقلة"],
        "fr": ["navire attaqué"],
        "de": ["Schiff angegriffen"],
        "es": ["buque atacado"],
    },
    "armed_clash": {
        "en": ["clashes", "fighting", "battle"],
        "ar": ["اشتباكات", "معارك", "مواجهات"],
        "fr": ["affrontements", "combats"],
        "de": ["Gefechte", "Kämpfe"],
        "es": ["enfrentamientos", "combates"],
    },
    "explosion": {
        "en": ["explosion", "blast", "bombing", "IED", "landmine"],
        "ar": ["انفجار", "عبوة ناسفة", "لغم"],
        "fr": ["explosion"],
        "de": ["Explosion"],
        "es": ["explosión"],
    },
    "assassination": {
        "en": ["assassination", "assassinated"],
        "ar": ["اغتيال"],
        "fr": ["assassinat"],
        "de": ["Attentat"],
        "es": ["asesinato"],
    },
    "detention": {
        "en": ["detained", "abducted", "arrested", "kidnapped"],
        "ar": ["اختطاف", "اعتقال", "احتجاز"],
        "fr": ["arrêté", "enlevé"],
        "de": ["festgenommen", "entführt"],
        "es": ["detenido", "secuestrado"],
    },
    "prisoner_exchange": {
        "en": ["prisoner exchange", "prisoner swap", "released prisoners"],
        "ar": ["تبادل الأسرى", "صفقة تبادل", "الإفراج عن أسرى"],
        "fr": ["échange de prisonniers"],
        "de": ["Gefangenenaustausch"],
        "es": ["intercambio de prisioneros"],
    },
    "protest": {
        "en": ["protest", "demonstration", "rally", "sit-in"],
        "ar": ["مظاهرة", "احتجاج", "وقفة احتجاجية", "اعتصام", "مسيرة جماهيرية"],
        "fr": ["manifestation"],
        "de": ["Protest", "Demonstration"],
        "es": ["protesta", "manifestación"],
    },
    "negotiations": {
        "en": ["talks", "negotiations", "met with", "meeting"],
        "ar": ["مفاوضات", "محادثات", "التقى", "لقاء"],
        "fr": ["négociations", "pourparlers"],
        "de": ["Verhandlungen", "Gespräche"],
        "es": ["negociaciones", "conversaciones"],
    },
    "natural_disaster": {
        "en": ["flood", "floods", "cyclone", "torrential rain", "earthquake"],
        "ar": ["سيول", "فيضانات", "إعصار", "أمطار غزيرة", "زلزال"],
        "fr": ["inondations"],
        "de": ["Überschwemmung"],
        "es": ["inundaciones"],
    },
    "disease_outbreak": {
        "en": ["cholera", "outbreak", "dengue", "measles"],
        "ar": ["كوليرا", "تفشي", "حمى الضنك", "حصبة"],
        "fr": ["choléra"],
        "de": ["Cholera"],
        "es": ["cólera"],
    },
}

_TRIGGERS = [
    (etype, term) for etype, langs in EVENT_TRIGGERS.items() for terms in langs.values() for term in terms
]


@dataclass
class EventCandidate:
    event_type: str
    location_entity_id: int
    actor_entity_ids: list[int]
    trigger: str
    evidence_sentence: str
    confidence: float


def extract_events(
    title: str, body: str, mentions: list[Mention], location_ids: set[int]
) -> list[EventCandidate]:
    """``location_ids``: entity ids that are Yemen locations (governorates and places)."""
    text = f"{title}. {body}" if body else title
    sentences = split_sentences(text) or [text]
    title_norm = normalize_for_matching(title)
    out: dict[tuple[str, int], EventCandidate] = {}
    for sentence in sentences:
        sn = normalize_for_matching(sentence)
        locs = [
            mm
            for mm in mentions
            if mm.entity_id in location_ids and normalize_for_matching(mm.surface_form) in sn
        ]
        if not locs:
            continue
        actors = sorted(
            {
                mm.entity_id
                for mm in mentions
                if mm.entity_type in ("political_actor", "armed_group", "country", "igo")
                and normalize_for_matching(mm.surface_form) in sn
            }
        )
        for etype, term in _TRIGGERS:
            if not term_pattern(term).search(sn):
                continue
            loc = locs[0].entity_id
            conf = 0.5 + (0.2 if term_pattern(term).search(title_norm) else 0.0) + (0.1 if actors else 0.0)
            key = (etype, loc)
            if key not in out or out[key].confidence < conf:
                out[key] = EventCandidate(etype, loc, actors, term, sentence, round(min(conf, 0.85), 3))
    # generic triggers ("meeting", "fighting") are weak; drop negotiations unless in the headline
    return [c for c in out.values() if c.event_type != "negotiations" or c.confidence >= 0.7]
