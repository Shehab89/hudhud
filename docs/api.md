# API

Base path `/api/v1`. Interactive documentation: `/docs` (Swagger) and `/redoc`; schema
at `/openapi.json`. Responses are JSON unless an export format is requested.

## Common filters

Most list and aggregate endpoints accept:

| Parameter | Meaning |
|---|---|
| `date_from`, `date_to` | ISO dates; default the last 30 days; at most 366 days |
| `language` | ISO 639-1 code |
| `source` | source slug (repeatable) |
| `source_group` | e.g. `yemen_independent`, `arab_gulf` (repeatable) |
| `operating_base` | `sanaa_controlled`, `government_controlled`, `stc_controlled`, `outside_yemen`, `unknown` |
| `category` | taxonomy slug |
| `entity` | actor slug |
| `demo` | `include` (default), `exclude`, `only` |

Duplicates are excluded from counts unless stated otherwise.

## Endpoints

| Area | Endpoints |
|---|---|
| Overview | `GET /overview`, `GET /timeline?split=none|language|operating_base|source_group|sentiment|category`, `GET /summary/{day}` |
| Articles | `GET /articles?q=`, `GET /articles/{id}` (all five measures with provenance), `GET /stories/{id}`, `GET /search?q=&mode=hybrid|keyword|semantic` |
| Taxonomy | `GET /categories`, `GET /categories/{slug}`, `GET /trends?dimension=category|topic` |
| Topics | `GET /topic-models`, `GET /topics?scope=`, `GET /topics/{id}` |
| Sources | `GET /sources`, `GET /sources/{slug}`, `GET /compare/sources?slugs=a,b` |
| Actors | `GET /actors`, `GET /actors/{slug}`, `GET /terminology?entity=` |
| Events | `GET /events`, `GET /events/{id}`, `GET /geography` |
| Landscape | `GET /media-landscape`, `GET /compare/narratives?group_by=operating_base|source_group|language` |
| Research | `GET /export/articles?format=csv|json|bibtex|ris&limit=` (≤ 10,000) |
| Account (X-API-Key) | `GET/POST /saved-queries`, `DELETE /saved-queries/{id}`, `POST /annotations` |
| Meta | `GET /meta`, `GET /models`, `GET /quality`, `GET /health` (root) |
| Admin (X-Admin-Token) | `GET /admin/runs`, `GET /admin/errors`, `GET /admin/annotations`, `PATCH /admin/annotations/{id}`, `GET /admin/llm-calls` |

## Examples

```bash
# Red Sea coverage from outlets based outside Yemen, last two weeks
curl "http://localhost:8000/api/v1/articles?q=Red%20Sea&operating_base=outside_yemen&date_from=2026-09-18"

# Which names do outlets use for Ansar Allah?
curl "http://localhost:8000/api/v1/terminology?entity=ansar-allah"

# Export for a reference manager
curl -o yemen.ris "http://localhost:8000/api/v1/export/articles?format=ris&category=humanitarian&demo=exclude"

# Submit a correction
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"article_id": 123, "target_type": "sentiment", "corrected_value": {"polarity": "neutral"}, "note": "reported speech"}' \
  http://localhost:8000/api/v1/annotations
```

Rate limit: `API_RATE_LIMIT` per client IP (default 120/minute). Public GET responses
are cacheable for 5 minutes.
