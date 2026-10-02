# Yemen Media Observatory

> Working name. The final name and logo are still to be chosen; the Python package is
> called `observatory` until then.

An open-source, multilingual research platform for monitoring how media cover Yemen:
what is reported, by whom, in which language, with which words and frames, and how that
changes over time. It is built for researchers, journalists and NGOs. It describes
coverage. It does not rank political actors, recommend positions, or claim to know
what is true.

**Five measures, never merged into one "bias" score:**

| | Measure | Question it answers | Stored in |
|---|---|---|---|
| A | Source orientation | Who is the outlet (ownership, funding, documented alignment)? | `source_orientation` (+ evidence, confidence, method, validity dates) |
| B | Article sentiment | What is the overall tone of the text? | `sentiment_analysis`, `emotion_analysis` |
| C | Framing | How does the text present the issue? | `framing_analysis` (+ evidence sentence) |
| D | Topic | What is it about? | `category_assignments` (taxonomy), `topic_assignments` (topic models) |
| E | Actor-targeted sentiment | How does a sentence that names an actor read? | `targeted_sentiment` (+ the sentence) |

Every automated result records its method, model version, confidence and analysis
version. Synthetic records are flagged `is_demo` and shown as **DEMO DATA** everywhere.

## What is in the repository

```
backend/observatory/    Python package: ingestion, NLP, pipeline, API, CLI
  ingest/               polite fetching (robots.txt, retries), feed parsers, URL canonicalisation, relevance filter
  nlp/                  Arabic-aware text normalisation, language ID, embeddings, taxonomy classifier,
                        sentiment/emotion/tone, framing, gazetteer (actors/places), events, topic models
  pipeline/             daily stages: ingest -> dedup -> analyse -> topics -> metrics (+ drift, summary)
  llm/                  optional LLM tier (schema-validated, cached, budgeted)
  api/                  FastAPI app, /api/v1, OpenAPI at /docs
  review/               applying accepted human corrections
  registry/             loads the YAML registry and vocabularies into the database
  demo.py               synthetic DEMO DATA generator
backend/alembic/        database migrations (PostgreSQL 16 + pgvector)
backend/tests/          unit tests and database tests
database/seeds/         source registry (193 outlets), taxonomy, frames, actors and aliases,
                        locations, lexicons, model registry
frontend/               Next.js 16 + TypeScript + Tailwind 4, English and Arabic (RTL), light/dark
docker/                 backend and frontend images
.github/workflows/      daily-ingestion, tests, lint, build, deploy
docs/                   architecture, methodology, models, registry, deployment, quality, limitations
scripts/                backup and restore helpers
```

## Quick start (local)

Requirements: Python 3.11+, Node 22+, PostgreSQL 16 with the
[pgvector](https://github.com/pgvector/pgvector) extension (or Docker).

```bash
cp .env.example .env                       # then edit; at least DATABASE_URL and ADMIN_TOKEN

# database (Docker), or point DATABASE_URL at your own PostgreSQL 16 + pgvector
docker compose up -d db

# backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,llm]"                # add ,ml for transformer models (~2 GB, CPU is fine)
observatory migrate
observatory seed                           # registry, taxonomy, actors, locations, models
observatory run                            # fetch and analyse today's coverage
# or, offline: observatory demo-data && observatory run --stages dedup,analyse,topics,metrics
observatory serve                          # API on :8000, docs at http://localhost:8000/docs

# frontend
cd frontend && npm ci && npm run dev       # http://localhost:3000
```

Everything in Docker:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm pipeline observatory migrate
docker compose run --rm pipeline observatory seed
docker compose run --rm pipeline observatory run
```

### CLI

| Command | Does |
|---|---|
| `observatory migrate` | apply database migrations |
| `observatory seed` | load/refresh the registry and vocabularies (idempotent) |
| `observatory check-sources` | validate the YAML source registry |
| `observatory run [--stages ...]` | run the pipeline; exits non-zero only if every stage failed |
| `observatory topics [--refit]` | fit or update topic models |
| `observatory demo-data [--days N] [--purge]` | insert or remove synthetic DEMO DATA |
| `observatory create-user EMAIL [--role]` | create a researcher/annotator/admin and print an API key once |
| `observatory serve` | run the API |

### Tests

```bash
pytest                                                    # unit tests only
TEST_DATABASE_URL=postgresql+psycopg://...observatory_test pytest   # + database tests (wipes that DB)
ruff check . && ruff format --check .
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Status

What works, what needs configuration, and what is not built. "Verified" means it was run
in development; see [docs/limitations.md](docs/limitations.md) for the details.

| Area | Status |
|---|---|
| Schema, migrations, seeds | Implemented and tested (migration round-trip, `alembic check` clean) |
| Source registry | 193 outlets, 157 feeds; 92 feeds verified by fetching on 2026-10-02, 65 unverified and marked so |
| Ingestion (RSS/Atom, Google News, GDELT) | Implemented and tested against mocked HTTP. **Live fetching was not possible from the build sandbox**; first real run happens in GitHub Actions |
| Dedup, syndication, story clusters | Implemented and tested |
| NLP with transformer models | Implemented. **Not run in development** (model downloads blocked in the sandbox); runs in Docker/Actions with `.[ml]` |
| NLP fallback (lexicon, hashing embeddings) | Implemented and tested; used for all demo results |
| BERTopic | Implemented; used when installed and the corpus is large enough. k-means fallback tested |
| LLM tier (Claude Haiku 4.5) | Implemented. **REQUIRES CONFIGURATION** (`LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`); not exercised against the live API |
| API (`/api/v1`, OpenAPI) | Implemented and tested |
| Frontend (21 pages, EN/AR, RTL, dark/light) | Implemented; builds; checked in a browser on demo data |
| Human corrections | Submit via API; admin accept applies sentiment/category/frame corrections. Other types are stored only |
| Daily GitHub Action | Written. **REQUIRES CONFIGURATION**: `DATABASE_URL` secret pointing to a hosted database |
| Deploy | Publishes images to GHCR. Rolling out to a host **REQUIRES CONFIGURATION** (`DEPLOY_WEBHOOK_URL`) |
| Docker images | Written; **not built in the sandbox** (registry rate limit); built by `build.yml` in CI |
| User accounts / login UI | **NOT IMPLEMENTED** (API keys via CLI only) |
| Social media, TV, radio monitoring | **NOT IMPLEMENTED** |
| Full-text extraction | **NOT IMPLEMENTED** by design (metadata and feed excerpts only) |

## Ethics and safeguards

* Collection honours robots.txt, identifies itself, and never bypasses paywalls, logins,
  CAPTCHAs or rate limits. It stores metadata and feed excerpts and links to publishers.
* Orientation labels require public evidence; otherwise they are `unknown`.
* Only public actors are profiled. No private individuals, no inference of protected
  attributes, no persuasion, no ranking of parties or candidates.
* Sentiment and framing describe wording, not truth or intent.
* Secrets live in environment variables and repository secrets only; the browser never
  receives an API key.

## Documentation

* [Architecture](docs/architecture.md)
* [Methodology](docs/methodology.md)
* [Model selection](docs/model-selection.md)
* [Source registry](docs/source-registry.md)
* [Deployment, automation, costs and backups](docs/deployment.md)
* [Data quality and drift](docs/data-quality.md)
* [Limitations and future work](docs/limitations.md)
* [API](docs/api.md)

Inspired in part by ACAPS' [YETI](https://yemen.yeti.acaps.org/) and its
approach to structured, sourced, filterable information.

## License

Code: MIT (see [LICENSE](LICENSE)). Article texts and headlines remain the property of
their publishers; the platform stores only metadata and short excerpts and links back.
