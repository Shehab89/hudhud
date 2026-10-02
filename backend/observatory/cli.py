"""Command-line entry point: ``observatory <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from observatory.config import get_settings
from observatory.logging import configure_logging


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_migrate(_args) -> int:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")
    return 0


def cmd_seed(_args) -> int:
    from observatory.db.session import session_scope
    from observatory.registry.seed import seed_all

    with session_scope() as s:
        _print(seed_all(s))
    return 0


def cmd_run(args) -> int:
    from observatory.db.session import session_scope
    from observatory.pipeline.run import STAGES, run_pipeline

    stages = tuple(args.stages.split(",")) if args.stages else STAGES
    unknown = set(stages) - set(STAGES)
    if unknown:
        print(f"unknown stages: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    with session_scope() as s:
        run = run_pipeline(
            s, stages, trigger=args.trigger, run_type="daily" if stages == STAGES else "partial"
        )
        _print({"run_id": run.id, "status": run.status, "stats": run.stats})
        # exit non-zero only when nothing worked, so one dead feed never fails the workflow
        return 1 if run.status == "failed" else 0


def cmd_topics(args) -> int:
    from observatory.db.session import session_scope
    from observatory.pipeline.topics_stage import run_topics

    with session_scope() as s:
        _print(run_topics(s, force_refit=args.refit))
    return 0


def cmd_demo(args) -> int:
    from observatory import demo
    from observatory.db.session import session_scope

    with session_scope() as s:
        if args.purge:
            _print(demo.purge(s))
        else:
            _print(demo.generate(s, days=args.days, stories_per_day=args.per_day))
            print(
                "DEMO DATA inserted. Run `observatory run --stages dedup,analyse,topics,metrics` to analyse it.",
                file=sys.stderr,
            )
    return 0


def cmd_check_sources(_args) -> int:
    """Validate the YAML source registry without touching the database."""
    import yaml

    from observatory.registry.seed import validate_source

    problems, n = [], 0
    for f in sorted((get_settings().seeds_dir / "sources").glob("*.yaml")):
        for rec in yaml.safe_load(f.read_text()) or []:
            n += 1
            problems += [f"{f.name}:{rec.get('id')}: {p}" for p in validate_source(rec)]
    _print({"sources": n, "problems": problems})
    return 1 if problems else 0


def cmd_serve(_args) -> int:
    import uvicorn

    uvicorn.run(
        "observatory.api.main:app",
        host="0.0.0.0",  # noqa: S104  (inside a container; put a reverse proxy in front)
        port=int(__import__("os").environ.get("PORT", "8000")),
        proxy_headers=True,
    )
    return 0


def cmd_create_user(args) -> int:
    """Create a researcher/annotator/admin user and print a new API key once."""
    import secrets

    from sqlalchemy import select

    from observatory.api.deps import hash_api_key
    from observatory.db import models as m
    from observatory.db.session import session_scope

    key = "obs_" + secrets.token_urlsafe(32)
    with session_scope() as s:
        user = s.scalar(select(m.User).where(m.User.email == args.email))
        if user is None:
            user = m.User(email=args.email, display_name=args.name, role=args.role)
            s.add(user)
        user.role, user.api_key_hash = args.role, hash_api_key(key)
    print(f"API key for {args.email} (shown once, store it securely):\n{key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="observatory", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply database migrations").set_defaults(fn=cmd_migrate)
    sub.add_parser("seed", help="load registry seeds (sources, taxonomy, actors, models)").set_defaults(
        fn=cmd_seed
    )
    sub.add_parser("check-sources", help="validate the source registry YAML").set_defaults(
        fn=cmd_check_sources
    )
    r = sub.add_parser("run", help="run the pipeline (all stages by default)")
    r.add_argument("--stages", help="comma-separated subset of ingest,dedup,analyse,topics,metrics")
    r.add_argument("--trigger", default="manual")
    r.set_defaults(fn=cmd_run)
    t = sub.add_parser("topics", help="fit or update topic models")
    t.add_argument("--refit", action="store_true", help="force a full refit")
    t.set_defaults(fn=cmd_topics)
    d = sub.add_parser("demo-data", help="insert (or --purge) synthetic DEMO DATA")
    d.add_argument("--days", type=int, default=45)
    d.add_argument("--per-day", type=int, default=7)
    d.add_argument("--purge", action="store_true")
    d.set_defaults(fn=cmd_demo)
    u = sub.add_parser("create-user", help="create a user (or rotate their key) and print an API key")
    u.add_argument("email")
    u.add_argument("--name")
    u.add_argument("--role", choices=["researcher", "annotator", "admin"], default="researcher")
    u.set_defaults(fn=cmd_create_user)
    sub.add_parser("serve", help="run the API with uvicorn").set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    configure_logging()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
