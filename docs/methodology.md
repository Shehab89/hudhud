# Methodology

This document explains what each number on the platform means, how it is produced and
how far it can be trusted. The same text, shortened, is on the `/methodology` page in
English and Arabic.

## 1. Five measures, kept apart

The platform never combines its measures into a single "bias" score. Each one answers a
different question and is stored, displayed and exported separately.

| | Measure | Unit | Not to be read as |
|---|---|---|---|
| A | **Source orientation**: ownership, funding, documented editorial or institutional alignment | outlet, for a date range | a reliability or accuracy rating |
| B | **Article sentiment**: overall tone; plus emotions and political tone (accusatory, conciliatory, alarmist...) | article | the outlet's attitude, or the truth of events |
| C | **Framing**: how the issue is presented (humanitarian, security, sovereignty...) | article, with the evidence sentence | a judgement of the framing |
| D | **Topic**: curated taxonomy categories, plus data-driven topics | article | importance (volume is not importance) |
| E | **Actor-targeted sentiment**: tone of a sentence that names an actor | sentence | an assessment of the actor's conduct |

A typical research question combines them explicitly: *"How did outlets based in
Sana'a-controlled areas (A, operating base) frame (C) Red Sea shipping coverage (D) in
September, and which terms did they use for the coalition (terminology)?"*

## 2. Source selection and classification (A)

### A curated universe, not every outlet

Hudhud monitors a small, curated set of top sources rather than every outlet that ever
mentions Yemen. The registry (`database/seeds/sources/`, format in `SCHEMA.md`) holds:

| category | selected for | content label |
|---|---|---|
| `MEDIA` | audience and sustained Yemen coverage (tier A) | Journalism |
| `SOCIAL_ACCOUNT` | public figures: officials (tier B), journalists and analysts (tier A) | Social post |
| `OFFICIAL_GOVERNMENT` | institutional importance (tier B) | Official statement |
| `DIPLOMATIC_MISSION` | institutional importance (tier B) | Official statement |
| `INTERNATIONAL_INSTITUTION` | institutional importance (tier B) | Institutional publication |
| `POLITICAL_ORGANIZATION` | institutional importance (tier B) | Political statement |
| `THINK_TANK`, `RESEARCH_ORGANIZATION` | influence on Yemen analysis (tier A) | Analysis |

Every record carries a **selection record**: the reason it was selected, audience
evidence (each figure with its source URL and date), influence evidence, how often it
covers Yemen, and its institutional importance with a note. The earlier broad registry
is kept in `sources/archive/` for reference and is not collected.

The full list, with every selection-record field, is published in
[source-selection.md](source-selection.md) and [source-selection.csv](source-selection.csv)
(generated from the registry by `scripts/registry_table.py`). Candidates that were
considered and not selected are listed with the reason in
`database/seeds/sources/EXCLUDED.md`. Feeds are checked against the live web in CI
(`scripts/registry_check.py`), and only feeds that were fetched and parsed are marked
verified.

### Influence and institutional importance are different things

* **Influence** (0 to 100) is computed by the loader from the evidence (rubric
  `influence-v1` in `SCHEMA.md`): reach from the largest cited audience figure, Yemen
  coverage frequency, citations by other media, and for tier A sources regional and
  historical importance. There is no score without a citable audience figure.
* **Institutional importance** (high, medium, low) records whether a source speaks for
  an institution whose position matters, whatever its audience. A Saudi embassy can
  have high institutional importance and low influence.
* For tier B sources, regional and historical importance are recorded but not scored,
  so being official can never raise the influence score.
* **Reliability** is not assessed (empty) unless a record cites evidence for it. It is
  never derived from category, and official sources are not treated as more reliable.

### Official sources are analysed as discourse

Ministries, embassies, UN offices and party channels go through the same analysis as
media (topics, actors, tone, places, framing, events), and every item from them is
labelled as an official statement, institutional publication or political statement.
An official statement shows what an institution says; it does not show what happened.

### Classification (measure A)

* `yemen_political_alignment`: the Yemeni camp a source belongs to or is documented to
  back (`plc_government`, `ansar_allah`, `stc`, `islah`, `gpc_sanaa`, `gpc_plc`,
  `national_resistance`, `hadramawt`, `southern_other`, `independent`, `mixed`,
  `none_documented`, `not_applicable`, `unknown`).
* `regional_alignment`: the foreign state or axis it belongs to or is documented to back
  (`saudi`, `uae`, `qatar`, `oman`, `iran_axis`, `us`, `uk`, ...).
* `sub_alignment` (free text) and `domestic_political_orientation` (a label from the list
  below), with a confidence, the evidence text and URLs, the method, an assessment date
  and a review status.
* Stored in `source_orientation` with validity dates (`valid_from`, `valid_to`): a
  change adds a new row and history is not rewritten.
* Labels for `domestic_political_orientation`: `state_aligned`, `movement_aligned`,
  `state_funded`, `public_service`, `intergovernmental`, `opposition_aligned`,
  `independent`, `mixed`, the ideological labels (`left` ... `far_right`, `islamist`,
  `secular`, `nationalist`, ...) and `unknown`.
* Methods: `manual_research`, `academic_source`, `media_watchdog`,
  `ownership_analysis`, `editorial_analysis`, `self_description`, `LLM_assisted`,
  `community_annotation`, `unknown`.
* **Rule:** no alignment other than `unknown`, `not_applicable` or `none_documented`
  without at least one public evidence URL (enforced by `hudhud check-sources` and the
  seed loader). `none_documented` must say what was checked.
* **Operating base** (`sanaa_controlled`, `government_controlled`, `stc_controlled`,
  `outside_yemen`, `unknown`) records where a Yemeni newsroom works. It is a location
  fact used to split charts, not an orientation.

### Comparison

`/compare/groups` compares groups of sources defined by these attributes, with presets
for Saudi media against Saudi government statements, Government/PLC against Houthi
against STC, Saudi against UAE against Iran against the US and UK (official voices),
and international media against foreign ministries against embassies. Groups are
compared on what they published; no group is treated as more truthful than another.

## 3. Collection

* Inputs: publisher RSS/Atom feeds, the public web preview of public Telegram channels
  (`t.me/s/<channel>`, only where robots.txt allows), Google News RSS search queries and
  the GDELT DOC 2.0 API. X (Twitter) accounts are registered but not collected: the X API
  is paid and scraping X is not permitted (REQUIRES CONFIGURATION). Posts of those accounts
  enter only when a member pastes them (`docs/social-post-import.md`), so they are a sample
  and not a complete record. YouTube channels are
  registered but not collected either, because YouTube's robots.txt disallows its
  channel feeds. Sites whose robots.txt or anti-bot protection refuses our crawler are
  recorded as such and skipped, never worked around. Aggregator items are attributed to the original publisher when its domain is
  in the registry.
* Politeness: robots.txt honoured, identifying user agent with a contact URL,
  conditional requests (ETag / Last-Modified), concurrency cap, retries only on
  network errors and 5xx. HTTP 401/403/451 and 429 are recorded, never worked around.
* Stored: URL, canonical URL, headline, feed excerpt (max 600 characters), author,
  dates, language. Full article texts are not fetched or stored.
* General feeds pass a Yemen-relevance filter: a strong term (Yemen, Sana'a, Houthi,
  اليمن, عدن ...) in the headline scores 1.0, in the excerpt 0.8; weak terms alone 0.4;
  the threshold is 0.75.
* Look-back window: 3 days by default, so a missed day is recovered next run.

## 4. Language and Arabic text

* Language is detected per article (lingua, with script heuristics) with a confidence;
  mixed-script items are flagged. Texts are never replaced by translations.
* Arabic matching normalises alef/hamza variants, alef maqsura, ta marbuta,
  diacritics, tatweel and Arabic-Indic digits, and accepts attached proclitics (و ف ب
  ل ك ال), so `غارة` matches `وبالغارات`. There is no stemming: names are not
  over-normalised. Originals are always stored untouched.

## 5. Duplicates, syndication and stories

1. Canonical URL (tracking parameters, AMP paths, `www.`/`m.` removed): one row per URL.
2. Identical normalised headline + excerpt: same outlet = duplicate; other outlet within
   48 hours = syndicated copy.
3. Near-identical headline (MinHash LSH, confirmed by token-set ratio ≥ 0.88), only
   against *older* articles within 48 hours:
   * same outlet: duplicate if the body matches (≥ 0.95) or it reappeared within 12 hours;
   * other outlet: syndicated if the excerpt is ≥ 0.9 similar, otherwise `same_story`
     (at most three links per article).
4. Embedding similarity (analyse stage): `same_story` / `similar` edges.

Story clusters are connected components of duplicate, syndication and same-story edges.
Each cluster stores `source_count` and `independent_source_count`, so "40 sites
republished one wire story" is distinguishable from "40 outlets covered it".
Duplicates are excluded from all counts by default.

## 6. Classification and confidence routing (D)

Every automated label has a confidence in [0, 1]:

| Confidence | Route |
|---|---|
| ≥ 0.85 | accepted |
| 0.60 – 0.85 | re-scored by a secondary model (multilingual zero-shot NLI) |
| < 0.60 | sent to the LLM tier if configured |
| still low | stored as `uncertain`; nothing is forced |

The tier-1 classifier combines multilingual keyword evidence from the taxonomy with
embedding similarity to category prototypes (semantic embeddings only). The route taken
is stored on each assignment (`accepted | secondary | llm | uncertain | human`).

The taxonomy (`database/seeds/taxonomy.yaml`) has 18 top-level categories (politics,
conflict & security, Houthis/Ansar Allah, southern Yemen, international relations,
economy, humanitarian, society, religion, tribes, environment, agriculture,
infrastructure, media & information, sports, culture, history, technology) with
subcategories and keywords in several languages.

## 7. Topic models (D)

* Primary: BERTopic-style (multilingual embeddings → UMAP → HDBSCAN → class-based
  TF-IDF) when BERTopic is installed and the corpus is large enough. Fallback: k-means
  on the same embeddings with the same c-TF-IDF.
* Models are fitted globally and per top-level category. NPMI coherence and topic
  diversity are stored with every model.
* Labels: top c-TF-IDF terms always; an LLM label (EN and AR) when enabled, stored next
  to the terms, never instead of them.
* Daily: new articles are assigned to the nearest topic centroid. Weekly (or after
  substantial growth): full refit; topics are linked to persistent `global_topics` by
  centroid similarity for continuity across refits and across languages.

## 8. Sentiment, emotion and tone (B)

* Transformer backend: `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual`,
  with `CAMeL-Lab/bert-base-arabic-camelbert-mix-sentiment` for Arabic; emotions and
  tone via zero-shot NLI.
* Fallback backend: a transparent multilingual lexicon (`database/seeds/lexicons.yaml`),
  labelled `method = lexicon`.
* Output: polarity (positive / neutral / negative / uncertain), a probability
  distribution, intensity, confidence, evidence words.
* Caveat: most news is neutral reporting of negative events. A negative label usually
  reflects the events described, not the outlet's stance.

## 9. Framing (C)

18 frames (`database/seeds/frames.yaml`): conflict, humanitarian, security, economic,
sovereignty, sectarian, national unity, separatist, anti-corruption, governance, foreign
intervention, proxy war, peace, resistance, terrorism, victimisation, legitimacy,
identity. Each has cue terms in several languages and an NLI hypothesis.

A frame is stored only with its evidence sentence, quoted from the article. LLM frame
suggestions are kept only when their quote is a verbatim substring of the article.

## 10. Actors, terminology and targeted sentiment (E)

* `database/seeds/entities.yaml` lists political actors, armed groups, states,
  international organisations and public figures with aliases in many languages.
* Each alias is typed `official | self_designation | common | descriptive | critical`
  with a note on typical usage (for example *أنصار الله* self-designation, *الحوثيين*
  common, *الانقلابيين* critical, *de facto authorities* descriptive). The
  terminology view counts which outlets use which form; the choice of name is itself
  data.
* Targeted sentiment is computed per sentence that names an actor and is clearly polar;
  the sentence is shown with the label.
* Only public actors and public figures in their public role are profiled.

## 11. Events

An event candidate needs a trigger term (airstrike, clashes, cholera, flood, protest,
prisoner exchange...) and a known place in the same sentence or headline. Reports of the
same type and place within a day are merged. These are *reports in coverage*, dated by
publication, not verified incident data; for incident data use ACLED or similar.

## 12. Trends

7-day windows compared with the previous 7 days:
* **emerging**: growth ≥ +100 % with ≥ 5 articles from ≥ 3 outlets;
* **declining**: growth ≤ −50 % from ≥ 5 articles;
* otherwise stable. Volume never implies importance.

## 13. Daily summary

Generated from aggregates with fixed English and Arabic templates (`method =
template`): counts, most-covered themes, emerging themes, most-mentioned actors and
the split by newsroom location. It reports what was published, not what happened, and
never evaluates actors.

## 14. Human review

Registered users submit corrections through `POST /api/v1/annotations`. An admin
accepts or rejects them. Accepted corrections to **sentiment**, **category** and
**frame** become the current result (`method = human`, confidence 1.0), and the
model's earlier output is kept (`is_current = false`) for evaluation. Other correction
types are stored and exported for evaluation and retraining only.

## 15. Reproducibility

Each result stores the model and version, method, confidence, prompt template version
(LLM) and analysis version. Each pipeline run stores its git commit and stage
statistics. Demo records are flagged `is_demo` and excluded from nothing silently:
filters (`demo=include|exclude|only`) make the choice explicit.
