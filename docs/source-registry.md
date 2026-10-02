# Source registry

The registry is a set of YAML files in `database/seeds/sources/` (format:
[`SCHEMA.md`](../database/seeds/sources/SCHEMA.md)). `hudhud seed` loads it
idempotently; `hudhud check-sources` validates it (also run in CI).

## Contents (as of 2026-10-02)

| File | Outlets | Main groups |
|---|---|---|
| `yemen_media.yaml` | 32 | Yemeni independent (24), local (4), state media in Aden (2) and Sana'a (2) |
| `yemen_actor_affiliated.yaml` | 12 | party, movement, council and military media (10), state bodies (2) |
| `arab_regional.yaml` | 69 | Gulf (27), international Arabic services (9), Levant (7), Iran (6), pan-Arab (5), Egypt (5), ... |
| `international.yaml` | 80 | newspapers (24), broadcasters (15), think tanks (14), humanitarian (10), aggregator queries (9), wires (7), ... |
| **Total** | **193** | 157 feeds: 147 RSS, 1 Atom, 8 Google News queries, 1 GDELT query |

* **92 feeds were verified** on 2026-10-02 (fetched, parsed, item count and newest date
  noted). **65 are unverified** (`verified: false`) with a note on why (blocked to the
  verifier, TLS error, path inferred). Unverified feeds stay active so the first real
  run tests them; failures are logged per feed, never fatal.
* Outlets with no usable feed are kept with `active: false` rather than given an
  invented URL. Their articles can still arrive through the per-language Google News
  and GDELT queries, which are attributed to the outlet when its domain is registered.
* Orientation: 81 outlets carry an evidenced label; 112 are `unknown`.

## Adding a source

1. Find the outlet's own feed (page source `<link rel="alternate">`, `/feed`, `/rss`).
   Fetch it; only then set `verified: true` and `verified_at`.
2. Set `operating_base` only from public information about where the newsroom works.
3. Add an orientation label only with evidence URLs (ownership records, academic or
   media-watchdog sources). Otherwise leave `simplified: unknown`.
4. Set `access_policy: metadata_only` unless the publisher's terms allow more.
5. `hudhud check-sources && hudhud seed`.

## Health

Each run updates `last_success_at`, `last_failure_at`, `consecutive_failures` and
`health_status` (healthy; degraded after 1–2 consecutive failures; failed from 3) on every feed and
source. The `/quality` page lists failing feeds; a feed failing for weeks should be
re-checked and fixed or deactivated in the YAML.
