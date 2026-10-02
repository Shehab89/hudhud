# Contributing

* **Sources:** edit `database/seeds/sources/*.yaml` following
  [SCHEMA.md](database/seeds/sources/SCHEMA.md). Feed URLs must be fetched before
  `verified: true`; orientation labels need public evidence URLs. Run
  `observatory check-sources`.
* **Actors and aliases:** `database/seeds/entities.yaml`. Public actors only; type each
  alias (`official`, `self_designation`, `common`, `descriptive`, `critical`) and note who
  uses it.
* **Taxonomy, frames, lexicons:** `database/seeds/*.yaml`; keep terms in several languages.
* **Code:** `ruff check . && ruff format .`, `pytest` (with `TEST_DATABASE_URL` for
  database tests), and `npm run lint && npm run typecheck` in `frontend/`. Schema changes
  need an Alembic migration (`cd backend && alembic revision --autogenerate -m "..."`).
* **Never** add code that bypasses paywalls, logins, CAPTCHAs or robots.txt, profiles
  private individuals, or produces persuasion or rankings of political actors.
