# Deployment, automation, costs and backups

## What runs where

| Piece | Runs | Needs |
|---|---|---|
| PostgreSQL 16 + pgvector | managed database or the `db` service in `docker-compose.yml` | persistent disk |
| Daily pipeline | GitHub Actions (`daily-ingestion.yml`) or `docker compose run --rm pipeline` from cron | `DATABASE_URL` |
| API | container `docker/backend.Dockerfile` | `DATABASE_URL`, `ADMIN_TOKEN`, `API_CORS_ORIGINS` |
| Frontend | container `docker/frontend.Dockerfile` | `API_URL` (server side), `NEXT_PUBLIC_*` at build time |

## Option 1: one small server (cheapest)

A single VPS with 2 vCPU / 4 GB RAM (8 GB if the pipeline runs there with transformer
models) runs everything with Docker Compose:

```bash
git clone <repo> && cd <repo>
cp .env.example .env    # strong POSTGRES_PASSWORD and ADMIN_TOKEN, public URLs, CORS origin
docker compose up -d --build db api frontend
docker compose run --rm pipeline hudhud migrate
docker compose run --rm pipeline hudhud seed
# daily at 03:15 UTC (crontab -e):
# 15 3 * * * cd /srv/hudhud && docker compose run --rm pipeline hudhud run >> pipeline.log 2>&1
```

Put a reverse proxy with TLS (Caddy or nginx) in front of ports 3000 and 8000; the
compose file binds them to 127.0.0.1 only. Build the pipeline image with
`INSTALL_ML=true` for transformer models.

## Option 2: managed services

* Database: any PostgreSQL 16 host that offers the `vector` extension (Supabase, Neon,
  Crunchy Bridge, AWS RDS, Google Cloud SQL, Azure Flexible Server...).
* API and frontend: any container host (Render, Fly.io, Railway, Cloud Run...) using
  the images `deploy.yml` publishes to `ghcr.io/<owner>/<repo>-backend` and
  `-frontend`.
* Pipeline: GitHub Actions.

## GitHub configuration

| Setting | Kind | Used by | Required |
|---|---|---|---|
| `DATABASE_URL` | secret | daily-ingestion | **yes** (REQUIRES CONFIGURATION) |
| `ANTHROPIC_API_KEY` | secret | daily-ingestion | no (enables the LLM tier) |
| `LLM_PROVIDER` = `anthropic` | variable | daily-ingestion | no |
| `USER_AGENT` | variable | daily-ingestion | recommended: include a contact URL |
| `DEPLOY_WEBHOOK_URL` | secret | deploy | no (without it images are published, not rolled out) |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL` | variables | deploy | yes for a public site |

Workflows:

| Workflow | Trigger | Does |
|---|---|---|
| `daily-ingestion.yml` | 03:15 UTC daily, manual (optional stage list) | install with models (cached), migrate, seed, run; fails only if every stage failed |
| `tests.yml` | push to main, PRs | Postgres + pgvector service; migration round-trip and `alembic check`; pytest with coverage; registry validation; frontend typecheck |
| `lint.yml` | push, PRs | ruff check and format, eslint, tsc, gitleaks |
| `build.yml` | push, PRs | Next.js production build; both Docker images (not pushed) |
| `deploy.yml` | push to main, `v*` tags | publish images to GHCR; call the deploy hook if set |

The database must accept connections from GitHub-hosted runners (public endpoint with
TLS and a strong password, or a self-hosted runner next to the database).

## Cost estimate

Volumes are estimates until the first weeks of live runs: 157 feeds, roughly 400–1,000
Yemen-relevant articles a day after filtering, about 8–12 KB per article including the
embedding, index and analysis rows, so **2–4 GB of database a year**.

| Item | Low-cost setup | Managed setup |
|---|---|---|
| Database | on the VPS | $20–30/month (a paid tier with ≥ 8 GB) |
| API + frontend hosting | one VPS, about $5–15/month | $10–30/month |
| Daily pipeline | GitHub Actions: free for public repositories; a private repository uses roughly 30–60 runner minutes a day (900–1,800 a month) | same |
| LLM tier (optional) | about 50 low-confidence items a day × ~1,500 tokens ≈ **$0.10–0.20/day (~$3–6/month)** with Claude Haiku 4.5; hard cap `LLM_DAILY_BUDGET_USD` (default $1/day) | same |
| **Total** | **about $5–20/month** | **about $35–70/month** |

Prices change; check the providers' current price lists. The platform works with no LLM
at all.

## Backups

* `scripts/backup_db.sh` writes a compressed `pg_dump` to `backups/` and keeps the newest
  14 (`KEEP`); `scripts/restore_db.sh` restores into an empty database (create the
  `vector` extension first if the restoring role cannot). Both were tested on a
  development database.
* Run the backup daily from cron after the pipeline, and copy dumps off the server
  (object storage with versioning). Managed databases: also enable point-in-time
  recovery.
* Dumps contain user e-mails and API-key hashes: keep them private. Everything else in
  the database can be rebuilt from the registry and a re-run, except history older than
  the feeds' look-back window, which is why backups matter.

## Operations checklist

* Rotate `ADMIN_TOKEN` and user API keys (`hudhud create-user EMAIL` re-issues a key).
* Watch `/quality` (failing feeds, drift flags) and `GET /api/v1/admin/runs`.
* Review `/api/v1/admin/annotations` weekly.
* Re-verify unverified feeds in the registry after the first live week.
