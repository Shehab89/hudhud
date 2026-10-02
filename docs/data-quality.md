# Data quality and drift

## Per-article technical quality

`articles.quality_score` (0–1) with its parts in `quality_detail`: has a date, has an
author, excerpt length, plausible headline length, language-detection confidence. It
measures **completeness of the record only**, not reliability or accuracy. Articles
whose date had to be estimated are flagged `published_at_estimated`.

## Source and feed health

Every run records per feed and per source: last success, last failure, consecutive
failures and health (`healthy`, `degraded`, `failed`), and stores each failure in
`pipeline_errors` (stage, error type, HTTP status, retry count). The `/quality` page and
`GET /api/v1/quality` show failing feeds, collection by day, language coverage and the
share of uncertain labels.

## Uncertainty

Labels below the confidence thresholds are stored as `uncertain` rather than forced.
The share of uncertain sentiment and category labels is reported on `/quality`; a rising
share is a signal that the models fit the incoming text poorly.

## Drift checks

Run daily by the metrics stage, comparing the last 7 days with the 7 before using
Jensen–Shannon divergence:

| Check | Flag above |
|---|---|
| language distribution | 0.10 |
| source-group distribution | 0.15 |
| sentiment distribution | 0.10 |
| top-500 vocabulary | 0.35 |

Flags are stored in `drift_reports` and shown on `/quality`. A flag is a prompt to look,
not a finding: it can mean a feed broke, a new outlet started publishing a lot, a model
or lexicon changed, or coverage really shifted.

## Known data-quality issues (demo / fallback mode)

* The fallback hashing embeddings are lexical, so topics fitted on them separate by
  language; transformer embeddings align languages.
* Arabic keyword topic labels show normalised forms (for example ه for ة).
* Category keyword scores are evidence weights and can exceed 1 before calibration;
  only the confidence (0–1) is used for routing.
* The alias "الأممية" for the UN overlaps with "المبعوث الأممي" (the UN envoy), so some
  envoy mentions also count as UN mentions.

## Reporting problems

Use the corrections API (`POST /api/v1/annotations`) for wrong labels, and open an issue
for wrong registry entries, with evidence links.
