"""Fold the results of a live registry check back into the curated registry.

    python scripts/registry_apply.py <snapshot_dir>            # show what would change
    python scripts/registry_apply.py <snapshot_dir> --write    # change the YAML files

<snapshot_dir> holds feeds_check.json and wikidata.json written by registry_check.py in CI
(published on the live-snapshot branch). Rules:

* A feed is marked verified only when it was fetched and parsed with at least one item.
* A feed that is gone (404/410), refused (401/403, robots.txt) or unparseable is deactivated.
  Transient failures (timeouts, 5xx, rate limits) change nothing but are reported.
* A source with no active feed left is registry-only (active: false), and a registry-only
  source with a newly verified feed is collected again.
* Wikidata follower counts are added as audience evidence only when the item matched the
  record by a hard identifier (official website or handle), the count names its platform
  and date, the date is recent enough, and the record has no figure for that metric yet.
  The Wikidata item is cited as the source. Researched figures are never overwritten.
* A handle is added from Wikidata only when the record has no account on that platform and
  Wikidata lists exactly one handle for it; the Wikidata item is cited as handle evidence.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "database/seeds/sources"
METRIC = {
    "x": "x_followers",
    "youtube": "youtube_subscribers",
    "telegram": "telegram_subscribers",
    "facebook": "facebook_followers",
    "instagram": "instagram_followers",
}
ACCOUNT_URL = {
    "x": "https://x.com/{}",
    "telegram": "https://t.me/{}",
    "facebook": "https://www.facebook.com/{}",
    "instagram": "https://www.instagram.com/{}",
}
# Counts older than this are reported but not used as current audience evidence.
MAX_AGE_DAYS = 3 * 365
GONE = {"robots_disallowed", "access_restricted", "parse_error"}


def _gone(row: dict) -> bool:
    if row.get("error") in GONE:
        return True
    return row.get("error") == "http_error" and row.get("status") in (404, 410)


def _load() -> dict[Path, tuple[str, list[dict]]]:
    files = {}
    for path in sorted(REGISTRY.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        header = "".join(line + "\n" for line in text.splitlines() if line.startswith("#"))
        if header and not text.startswith("#"):
            header = ""
        files[path] = (header, yaml.safe_load(text) or [])
    return files


def apply_feeds(recs: dict[str, dict], feeds: list[dict], log: list[str]) -> None:
    for row in feeds:
        rec = recs.get(row["id"])
        if not rec:
            continue
        feed = next((f for f in rec.get("feeds") or [] if f["url"] == row["url"]), None)
        if feed is None:
            continue
        when = row.get("checked_at")
        if row.get("ok") and row.get("items"):
            if not feed.get("verified") or feed.get("active") is False:
                log.append(f"verified  {row['id']}: {row['url']} ({row['items']} items)")
            feed["verified"] = True
            feed["verified_at"] = dt.date.fromisoformat(when) if when else None
            feed.pop("active", None)
        elif row.get("ok"):
            log.append(f"empty     {row['id']}: {row['url']} parsed with no items")
        elif _gone(row):
            if feed.get("active", True):
                log.append(
                    f"disabled  {row['id']}: {row['url']} ({row.get('error')} {row.get('status') or ''})"
                )
            feed["verified"] = False
            feed["active"] = False
            note = f"check {when}: {row.get('error')} {row.get('status') or ''}".strip()
            feed["notes"] = " ".join(x for x in (feed.get("notes"), note) if x and note not in x) or note
        else:
            log.append(f"transient {row['id']}: {row['url']} ({row.get('error')} {row.get('status') or ''})")

    for rec in recs.values():
        live = [f for f in rec.get("feeds") or [] if f.get("active", True)]
        if not live and rec.get("active", True):
            rec["active"] = False
            log.append(f"registry-only {rec['id']}: no active feed left")
        elif rec.get("active") is False and any(f.get("verified") for f in live):
            rec["active"] = True
            log.append(f"collected {rec['id']}: has a verified feed again")


def apply_wikidata(recs: dict[str, dict], wiki: dict, today: dt.date, log: list[str]) -> None:
    for sid, info in wiki.items():
        rec = recs.get(sid)
        if sid.startswith("_") or not rec or not info.get("qid"):
            continue
        qid = info["qid"]
        cite = f"https://www.wikidata.org/wiki/{qid}"
        if not rec.get("wikidata"):
            rec["wikidata"] = qid
            log.append(f"wikidata  {sid}: {qid} (matched by {info.get('matched_by')})")

        sel = rec.setdefault("selection", {})
        have = {a.get("metric") for a in sel.get("audience_evidence") or []}
        for platform, f in (info.get("followers") or {}).items():
            metric = METRIC.get(platform)
            if not metric or metric in have:
                continue
            try:
                as_of = dt.date.fromisoformat(f["as_of"][:10].replace("-00", "-01"))
            except ValueError:
                continue
            if (today - as_of).days > MAX_AGE_DAYS:
                log.append(f"too old   {sid}: {metric}={f['value']} as of {as_of} ({cite})")
                continue
            sel.setdefault("audience_evidence", []).append(
                {"metric": metric, "value": f["value"], "as_of": as_of, "source_url": cite}
            )
            log.append(f"audience  {sid}: {metric}={f['value']} as of {as_of} ({cite})")

        platforms = {a.get("platform") for a in rec.get("accounts") or []}
        for platform, handles in (info.get("handles") or {}).items():
            if platform in platforms or len(handles) != 1 or platform not in ACCOUNT_URL:
                continue
            handle = handles[0].lstrip("@")
            rec.setdefault("accounts", []).append(
                {
                    "platform": platform,
                    "handle": handle,
                    "url": ACCOUNT_URL[platform].format(handle),
                    "handle_evidence": cite,
                }
            )
            log.append(f"account   {sid}: {platform} {handle} ({cite})")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    snap = Path(args[0])
    feeds = json.loads((snap / "feeds_check.json").read_text())
    wiki_path = snap / "wikidata.json"
    wiki = json.loads(wiki_path.read_text()) if wiki_path.exists() else {}

    files = _load()
    recs = {r["id"]: r for _, rs in files.values() for r in rs}
    log: list[str] = []
    apply_feeds(recs, feeds, log)
    apply_wikidata(recs, wiki, dt.date.today(), log)
    print("\n".join(log) or "no changes")
    print(f"{len(log)} changes")

    if "--write" in sys.argv:
        for path, (header, rs) in files.items():
            text = yaml.safe_dump(rs, allow_unicode=True, sort_keys=False, width=110)
            path.write_text(header + text, encoding="utf-8")
        print("registry files updated; run scripts/registry_table.py to refresh docs/")


if __name__ == "__main__":
    main()
