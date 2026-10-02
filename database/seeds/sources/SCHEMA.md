# Source registry format

Each `*.yaml` file in this folder is a list of source records. Files are loaded into
the `sources`, `source_feeds` and `source_orientation` tables by
`python -m hudhud.cli seed`. Edit the YAML, not the code.

```yaml
- id: al-masirah                 # stable slug, unique across all files, [a-z0-9-]
  name: Al-Masirah               # common English name
  name_native: قناة المسيرة       # name in its own script (optional)
  url: https://www.almasirah.net/ # homepage
  country: YE                    # ISO 3166-1 alpha-2 of the outlet's base ("XX" if unclear)
  languages: [ar]                # ISO 639-1
  source_type: tv                # news_agency | newspaper | news_website | tv | radio | wire |
                                 # investigative | think_tank | humanitarian | government |
                                 # aggregator | magazine | fact_checker
  source_group: yemen_actor_affiliated   # see "Source groups" below
  geographic_focus: [national]   # national | aden | sanaa | taiz | marib | hadramawt |
                                 # hodeidah | south | regional_mena | global ...
  operating_base: sanaa_controlled  # where the newsroom operates: sanaa_controlled |
                                 # government_controlled | stc_controlled | outside_yemen | unknown
  yemen_coverage: primary        # primary (Yemen is the main beat) | high | medium | low
  feeds:
    - url: https://www.example.com/rss
      type: rss                  # rss | atom | sitemap | api | google_news_query | gdelt_query
      verified: true             # true ONLY if you fetched it and it returned a parseable feed
      verified_at: 2026-10-02
      yemen_filter: false        # true if the feed is general and items must be keyword-filtered
      notes: ""
  ownership:
    description: ""              # only what is publicly documented
    evidence_urls: []
  orientation:                   # OMIT or set simplified: unknown when evidence is thin
    simplified: unknown          # see the list in docs/methodology.md
    dimensions:                  # optional; each key from the dimension list
      institutional_alignment: { value: "Ansar Allah (Houthi) movement", confidence: 0.9 }
    confidence: 0.0              # 0-1, overall
    evidence: ""                 # one or two sentences, what the evidence says
    evidence_urls: []            # REQUIRED if simplified != unknown
    method: unknown              # manual_research | academic_source | media_watchdog |
                                 # ownership_analysis | editorial_analysis | hyperlink_network |
                                 # LLM_assisted | community_annotation | unknown
    last_reviewed: 2026-10-02
    review_status: draft         # draft | reviewed | disputed
  access_policy: metadata_only   # metadata_only | excerpt | full_text_permitted
  active: true                   # false if no working feed was found (kept for the record)
  notes: ""
```

## Source groups

`yemen_independent`, `yemen_state_irg` (internationally recognised government),
`yemen_state_sanaa` (Sanaa / Ansar Allah-run state institutions),
`yemen_actor_affiliated` (party, movement, council or military media),
`yemen_local`, `arab_gulf`, `arab_egypt`, `arab_levant`, `arab_iraq`,
`arab_maghreb`, `arab_pan`, `international_arabic_service`, `iran`, `turkey`,
`international_wire`, `international_broadcaster`, `international_newspaper`,
`international_humanitarian`, `think_tank_research`, `aggregator`.

## Rules

1. Never invent a source or a feed URL. `verified: true` means the feed was fetched
   and parsed on `verified_at`.
2. Never assign a political orientation without at least one evidence URL. When
   unsure, use `simplified: unknown`.
3. Orientation describes the outlet's documented affiliation or editorial position. It
   says nothing about accuracy, quality or truthfulness.
