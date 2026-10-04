# Source registry format (v2: curated top sources)

Hudhud monitors a **small, curated source universe**, not every outlet that ever
mentions Yemen. Each `*.yaml` file in this folder is a list of source records loaded
by `hudhud seed`. Files under `archive/` are the earlier, broader registry; they are
kept for reference and are **not** loaded.

The registry answers two separate questions about every source, and keeps them apart:

* **Influence** (`scores.influence_score`, 0 to 100): how much audience and weight the
  source has in Yemen discourse. Computed by the loader from the structured indicators
  under `selection`, never typed in by hand.
* **Institutional importance** (`selection.institutional_importance.level`): whether the
  source speaks for an institution whose position matters (a ministry, an embassy, a UN
  office), regardless of audience size.

A Saudi embassy account can have high institutional importance and a low influence
score. Being official never raises the influence score, and never raises reliability.

## Record

```yaml
- id: saudi-mofa                   # stable slug, unique across all files, [a-z0-9-]
  name: Ministry of Foreign Affairs of Saudi Arabia
  name_native: وزارة الخارجية السعودية
  category: OFFICIAL_GOVERNMENT    # see "Categories"
  tier: B                          # A = selected for audience/influence
                                   # B = selected for institutional importance
  url: https://www.mofa.gov.sa/    # homepage, or the account URL for a SOCIAL_ACCOUNT
  country: SA                      # ISO 3166-1 alpha-2 of the source's base ("XX" if unclear)
  region: gulf                     # the political/media system it belongs to (see "Regions")
  languages: [ar, en]              # ISO 639-1
  platform: website                # primary platform: website | x | telegram | youtube |
                                   # facebook | instagram | tv | radio | wire
  source_type: government          # news_agency | newspaper | news_website | tv | radio | wire |
                                   # government | diplomatic | intergovernmental | humanitarian |
                                   # party | movement | person | think_tank | research | aggregator
  content_type: official_statement # optional; defaults from category (see below)
  wikidata: Q123456                # optional Wikidata item, used to cross-check handles
  operating_base: outside_yemen    # Yemeni sources: sanaa_controlled | government_controlled |
                                   # stc_controlled | outside_yemen | unknown
  holder:                          # SOCIAL_ACCOUNT only
    kind: person                   # person | organization
    role: Head of the Ansar Allah negotiating delegation   # public role that justifies monitoring
    affiliation: ansar-allah       # optional id of another record
    public_figure: true            # REQUIRED true: private individuals are never monitored
  accounts:                        # official social accounts of this source
    - platform: x                  # x | telegram | youtube | facebook | instagram | tiktok
      handle: KSAmofa
      url: https://x.com/KSAmofa
      handle_evidence: https://www.mofa.gov.sa/   # page that links to or confirms the account
      followers: 5000000           # optional, only with followers_source
      followers_as_of: 2026-09-30
      followers_source: https://...
  feeds:                           # what the pipeline collects (see "Feeds")
    - url: https://www.example.org/rss
      type: rss                    # rss | atom | youtube | telegram_public | sitemap | api |
                                   # google_news_query | gdelt_query
      verified: false              # true ONLY after the feed was fetched and parsed
      verified_at: null
      yemen_filter: true           # true if items must be keyword-filtered for Yemen
      notes: "candidate, listed on https://..."
  selection:                       # the transparent selection record
    reason: Official foreign-policy voice of the state leading the coalition in Yemen.
    audience_evidence:             # measurable reach; every item needs source_url
      - metric: x_followers        # x_followers | youtube_subscribers | facebook_followers |
                                   # telegram_subscribers | instagram_followers |
                                   # monthly_visits | tv_reach | print_circulation
        value: 5000000
        as_of: 2026-09
        source_url: https://...
    influence_evidence:            # qualitative indicators, each high | medium | low
      regional_importance: high
      cited_by_other_media: high
      historical_importance: medium
      note: Statements are routinely quoted by Arab and international media.
      urls: [https://...]
    yemen_coverage:
      frequency: weekly            # daily | weekly | monthly | occasional
      evidence: Issues Yemen statements several times a month.
      urls: []
    institutional_importance:
      level: high                  # high | medium | low | none
      note: Saudi Arabia leads the coalition supporting the PLC government.
  alignment:                       # classification; nothing here without evidence
    yemen_political_alignment: not_applicable   # see "Alignment values"
    sub_alignment: ""              # free text, e.g. "Tareq Saleh's National Resistance"
    regional_alignment: saudi      # see "Alignment values"
    domestic_political_orientation: state_aligned   # label from docs/methodology.md
    classification_confidence: 0.95  # 0-1
    classification_evidence: It is the Saudi government's own foreign ministry.
    evidence_urls: [https://www.mofa.gov.sa/]
    method: manual_research        # manual_research | academic_source | media_watchdog |
                                   # ownership_analysis | editorial_analysis | self_description |
                                   # LLM_assisted | unknown
    assessment_date: 2026-10-04
    review_status: draft           # draft | reviewed | disputed
  scores:
    reliability_score: null        # NOT ASSESSED. Only with reliability_evidence_urls, and
                                   # never derived from category or official status.
  access_policy: metadata_only     # metadata_only | excerpt | full_text_permitted
  active: true                     # false while no collectable feed is verified
  notes: ""
```

## Categories

| category | default tier | default content_type | label shown to users |
|---|---|---|---|
| `MEDIA` | A | `journalism` | Journalism |
| `POLITICAL_ORGANIZATION` | B | `political_statement` | Political statement |
| `SOCIAL_ACCOUNT` | A (B for officials' accounts) | `social_post` | Social post |
| `OFFICIAL_GOVERNMENT` | B | `official_statement` | Official statement |
| `DIPLOMATIC_MISSION` | B | `official_statement` | Official statement |
| `INTERNATIONAL_INSTITUTION` | B | `institutional_publication` | Institutional publication |
| `THINK_TANK` | A | `analysis` | Analysis |
| `RESEARCH_ORGANIZATION` | A | `analysis` | Analysis |

Institutional accounts (a ministry's X account) belong to the institution's record under
`accounts`. A person's own account (a minister, an envoy, a journalist) is a separate
`SOCIAL_ACCOUNT` record whose `holder.role` names the public role.

## Regions

`yemen` (Yemeni sources wherever they are based), `gulf`, `iraq`, `levant`, `egypt`,
`maghreb`, `iran`, `turkey`, `europe`, `north_america`, `russia`, `asia`, `africa`,
`global` (international institutions and wires without a home audience).

## Alignment values

`yemen_political_alignment` is the Yemeni camp a source belongs to or is documented to
back: `plc_government`, `ansar_allah`, `stc`, `islah`, `gpc_sanaa`, `gpc_plc`,
`national_resistance`, `hadramawt`, `southern_other`, `independent`, `mixed`,
`none_documented`, `not_applicable` (foreign states, international institutions),
`unknown`.

`regional_alignment` is the foreign state or axis a source belongs to or is documented to
back: `saudi`, `uae`, `qatar`, `oman`, `kuwait`, `iran_axis`, `turkey`, `egypt`, `us`,
`uk`, `eu`, `russia`, `china`, `none_documented`, `not_applicable`, `unknown`.

Every value other than `unknown`, `not_applicable` and `none_documented` needs at least
one `evidence_urls` entry. `none_documented` needs `classification_evidence` saying what
was checked.

## Influence score (rubric v1)

Computed by the loader and stored with its components:

| indicator | points |
|---|---|
| reach: largest `audience_evidence` value, `clamp((log10(value) - 3) * 10, 0, 40)` | 0 to 40 (1k = 0, 10k = 10, 100k = 20, 1M = 30, 10M = 40) |
| Yemen coverage frequency: daily / weekly / monthly / occasional | 25 / 15 / 8 / 0 |
| regional importance: high / medium / low (tier A only) | 15 / 8 / 0 |
| cited by other media: high / medium / low | 10 / 5 / 0 |
| historical importance in Yemen discourse: high / medium / low (tier A only) | 10 / 5 / 0 |

* No score without a citable audience figure: influence is first of all reach.
* No score from fewer than two indicators.
* For tier B sources, regional and historical importance are recorded but not scored,
  because for an institution they restate its rank, which is already recorded as
  institutional importance. An official source cannot gain influence from being official.
* Institutional importance is never an input.

## Feeds

* `rss`, `atom`: a feed URL published by the source.
* `youtube`: `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` (YouTube's public
  channel feed). Titles and descriptions only.
* `telegram_public`: `https://t.me/s/<channel>`, the public web preview of a public
  channel. Collected only where robots.txt allows it.
* X (Twitter) accounts are registered under `accounts` but **not collected**: the X API is
  paid and scraping X is not permitted. Status: REQUIRES CONFIGURATION.

## Rules

1. Never invent a source, an account handle, a follower count or a feed URL. Every
   number has a `source_url`; every handle has a `handle_evidence` page.
2. Never assign an alignment without evidence. When unsure, use `unknown`.
3. Alignment describes documented affiliation or editorial position. It says nothing
   about accuracy or truthfulness.
4. Official sources are analysed as discourse and labelled as official statements. An
   official source tells us what the institution says, not what happened.
5. Do not add a source because it occasionally mentions Yemen, and do not fill a quota.
6. Only public figures in their public role are monitored, never private individuals.
