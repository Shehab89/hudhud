"""Check the curated registry against the live web (runs in CI, where the runner has internet).

1. Feeds: fetch every listed feed (candidates included) the same way the pipeline does
   (robots.txt honoured, identifying user agent, no bypassing), parse it, and record the
   status, item count, newest item date and the share of Yemen-relevant items.
2. Discovery: for sources where no listed feed worked, look for feeds the source itself
   publishes: feed links its homepage declares (<link rel="alternate">) and the public
   preview of its listed Telegram channels. (YouTube channel feeds are robots-disallowed.)
   Every candidate is fetched and parsed the same way; nothing is guessed from URL patterns.
4. Candidates: Wikidata queries for public figures who currently hold a Yemeni public
   office or are Yemeni public figures with a listed X, Telegram or YouTube account, and for
   diplomatic missions in or of Yemen. These are suggestions for review only: nothing is
   added to the registry automatically, and every figure keeps its Wikidata citation.
3. Wikidata: for each source, find its Wikidata item (the record's `wikidata` id, or a
   name search accepted only when the item's official website or a social handle matches
   the record) and read its social handles and dated follower counts (P8687).

Writes feeds_check.json, discovered.json, wikidata.json, candidates.json and registry_check.md into the directory given as
the first argument. It changes nothing in the registry: results are folded in by hand,
with the Wikidata item cited as the source of any figure taken from it.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from hudhud.config import get_settings
from hudhud.ingest.feeds import PARSERS, FeedParseError
from hudhud.ingest.http import Fetcher, FetchError
from hudhud.ingest.relevance import RELEVANCE_THRESHOLD, yemen_relevance

ROOT = Path(__file__).resolve().parents[1]
WD_API = "https://www.wikidata.org/w/api.php"
WD_SPARQL = "https://query.wikidata.org/sparql"
YEMEN = "Q805"
# Wikidata properties
P_WEBSITE, P_X, P_YT, P_TG, P_FB, P_IG = "P856", "P2002", "P2397", "P3789", "P2013", "P2003"
P_FOLLOWERS, P_TIME, P_X_ID = "P8687", "P585", "P6552"
HANDLE_PROPS = {P_X: "x", P_YT: "youtube", P_TG: "telegram", P_FB: "facebook", P_IG: "instagram"}
QUALIFIER_PLATFORM = {
    P_X_ID: "x",
    P_X: "x",
    P_YT: "youtube",
    P_TG: "telegram",
    P_FB: "facebook",
    P_IG: "instagram",
}


def load_registry() -> list[dict]:
    out = []
    for path in sorted((ROOT / "database/seeds/sources").glob("*.yaml")):
        for rec in yaml.safe_load(path.read_text()) or []:
            rec["_file"] = path.name
            out.append(rec)
    return out


def domain(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.").lower()


# ---------------------------------------------------------------- feeds


def check_one(fetcher: Fetcher, sid: str, url: str, ftype: str) -> dict:
    row = {"id": sid, "url": url, "type": ftype, "checked_at": dt.date.today().isoformat()}
    try:
        res = fetcher.get(url)
        items = PARSERS.get(ftype, PARSERS["rss"])(res.content)
        dates = [i.published_at for i in items if i.published_at]
        relevant = sum(1 for i in items if yemen_relevance(i.title, i.summary) >= RELEVANCE_THRESHOLD)
        row.update(
            ok=True,
            status=res.status,
            items=len(items),
            newest=max(dates).isoformat() if dates else None,
            yemen_relevant=relevant,
            sample=[i.title[:140] for i in items[:3]],
        )
    except FetchError as exc:
        row.update(ok=False, error=exc.error_type, detail=str(exc)[:200], status=exc.status)
    except FeedParseError as exc:
        row.update(ok=False, error="parse_error", detail=str(exc)[:200])
    except Exception as exc:  # report, never crash the check
        row.update(ok=False, error=type(exc).__name__, detail=str(exc)[:200])
    return row


def check_feeds(fetcher: Fetcher, records: list[dict]) -> list[dict]:
    return [
        check_one(fetcher, rec["id"], f["url"], f.get("type", "rss"))
        for rec in records
        for f in rec.get("feeds") or []
    ]


# ---------------------------------------------------------------- discovery

SOCIAL_HOSTS = {"x.com", "twitter.com", "t.me", "youtube.com", "facebook.com", "instagram.com", "tiktok.com"}
FEED_TYPES = {"application/rss+xml": "rss", "application/atom+xml": "atom"}
MAX_AUTODISCOVERED = 3


def _homepage_feeds(fetcher: Fetcher, url: str) -> list[tuple[str, str, str]]:
    from lxml import html as lxml_html

    res = fetcher.get(url)
    doc = lxml_html.fromstring(res.content)
    out = []
    for link in doc.xpath('//link[@rel="alternate"][@href]'):
        ftype = FEED_TYPES.get((link.get("type") or "").lower())
        href = urljoin(res.url or url, link.get("href"))
        if ftype and "comment" not in href.lower() and href not in [o[0] for o in out]:
            out.append((href, ftype, f"declared by {url}"))
    return out[:MAX_AUTODISCOVERED]


def discover(fetcher: Fetcher, records: list[dict], checked: list[dict]) -> list[dict]:
    working = {r["id"] for r in checked if r.get("ok") and r.get("items")}
    results = []
    for rec in records:
        if rec["id"] in working:
            continue
        known = {f["url"] for f in rec.get("feeds") or []}
        cands: list[tuple[str, str, str]] = []
        if domain(rec.get("url")) not in SOCIAL_HOSTS:
            try:
                cands += _homepage_feeds(fetcher, rec["url"])
            except Exception as exc:  # unreachable homepages are reported by the feed check
                results.append(
                    {
                        "id": rec["id"],
                        "url": rec["url"],
                        "ok": False,
                        "stage": "homepage",
                        "error": getattr(exc, "error_type", type(exc).__name__),
                    }
                )
        for acc in rec.get("accounts") or []:
            try:
                if acc.get("platform") == "telegram" and acc.get("handle"):
                    handle = acc["handle"].lstrip("@")
                    cands.append(
                        (f"https://t.me/s/{handle}", "telegram_public", f"public preview of {acc['url']}")
                    )
            except Exception as exc:
                results.append(
                    {
                        "id": rec["id"],
                        "url": acc.get("url"),
                        "ok": False,
                        "stage": "account",
                        "error": getattr(exc, "error_type", type(exc).__name__),
                    }
                )
        for url, ftype, how in cands:
            if url in known:
                continue
            known.add(url)
            row = check_one(fetcher, rec["id"], url, ftype)
            row["found_by"] = how
            results.append(row)
    return results


# ---------------------------------------------------------------- wikidata


class Wikidata:
    def __init__(self) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": get_settings().user_agent}, timeout=30, follow_redirects=True
        )

    def _get(self, **params) -> dict:
        params |= {"format": "json"}
        for attempt in range(4):
            r = self.client.get(WD_API, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            time.sleep(0.2)  # be gentle
            return r.json()
        r.raise_for_status()
        return {}

    def search(self, name: str, lang: str) -> list[str]:
        data = self._get(
            action="wbsearchentities", search=name, language=lang, uselang=lang, limit=5, type="item"
        )
        return [x["id"] for x in data.get("search", [])]

    def entities(self, ids: list[str]) -> dict[str, dict]:
        out = {}
        for i in range(0, len(ids), 50):
            data = self._get(
                action="wbgetentities", ids="|".join(ids[i : i + 50]), props="claims|labels|sitelinks"
            )
            out.update(data.get("entities", {}))
        return out


def _values(ent: dict, prop: str) -> list:
    vals = []
    for c in ent.get("claims", {}).get(prop, []):
        if c.get("rank") == "deprecated":
            continue
        dv = c.get("mainsnak", {}).get("datavalue", {})
        if "value" in dv:
            vals.append(dv["value"])
    return vals


def summarise(ent: dict) -> dict:
    handles: dict[str, list[str]] = {}
    for prop, platform in HANDLE_PROPS.items():
        vs = [str(v) for v in _values(ent, prop)]
        if vs:
            handles[platform] = vs
    followers: dict[str, dict] = {}
    for c in ent.get("claims", {}).get(P_FOLLOWERS, []):
        if c.get("rank") == "deprecated":
            continue
        try:
            amount = int(float(c["mainsnak"]["datavalue"]["value"]["amount"]))
        except (KeyError, ValueError, TypeError):
            continue
        quals = c.get("qualifiers", {})
        platform = next((QUALIFIER_PLATFORM[q] for q in quals if q in QUALIFIER_PLATFORM), None)
        when = None
        for q in quals.get(P_TIME, []):
            t = q.get("datavalue", {}).get("value", {}).get("time")
            if t:
                when = t.lstrip("+")[:10]
        if not platform or not when:
            continue  # an unattributed or undated count is not usable evidence
        if platform not in followers or when > followers[platform]["as_of"]:
            followers[platform] = {"value": amount, "as_of": when}
    return {
        "websites": [str(v) for v in _values(ent, P_WEBSITE)],
        "handles": handles,
        "followers": followers,
        "label_en": ent.get("labels", {}).get("en", {}).get("value"),
        "enwiki": ent.get("sitelinks", {}).get("enwiki", {}).get("title"),
    }


def match(rec: dict, info: dict) -> str | None:
    """Accept a Wikidata item only on a hard identifier match, never on the name alone."""
    rec_domain = domain(rec.get("url"))
    if rec_domain and any(domain(w) == rec_domain for w in info["websites"]):
        return "official_website"
    for acc in rec.get("accounts") or []:
        for h in info["handles"].get(acc.get("platform"), []):
            if h.lower().lstrip("@") == str(acc.get("handle", "")).lower().lstrip("@"):
                return f"{acc['platform']}_handle"
    if rec.get("platform") == "x" and rec_domain in ("x.com", "twitter.com"):
        handle = urlparse(rec["url"]).path.strip("/").split("/")[0].lower()
        if handle and handle in [h.lower() for h in info["handles"].get("x", [])]:
            return "x_handle"
    return None


def enrich(records: list[dict]) -> dict:
    wd = Wikidata()
    out: dict[str, dict] = {}
    for rec in records:
        try:
            if rec.get("wikidata"):
                ent = wd.entities([rec["wikidata"]]).get(rec["wikidata"])
                if ent:
                    out[rec["id"]] = {"qid": rec["wikidata"], "matched_by": "record", **summarise(ent)}
                continue
            cands: list[str] = []
            for name, lang in ((rec.get("name"), "en"), (rec.get("name_native"), "ar")):
                if name:
                    cands += [c for c in wd.search(name.split(" (")[0], lang) if c not in cands]
            if not cands:
                continue
            for qid, ent in wd.entities(cands[:8]).items():
                info = summarise(ent)
                how = match(rec, info)
                if how:
                    out[rec["id"]] = {"qid": qid, "matched_by": how, **info}
                    break
        except httpx.HTTPError as exc:
            out.setdefault("_errors", {})[rec["id"]] = str(exc)[:200]
    return out


# ---------------------------------------------------------------- candidates

CANDIDATE_QUERIES = {
    # People holding a public office whose jurisdiction or country is Yemen, with no end date.
    "office_holders": """
SELECT DISTINCT ?item ?role WHERE {
  ?item p:P39 ?st . ?st ps:P39 ?pos .
  FILTER NOT EXISTS { ?st pq:P582 [] }
  { ?pos wdt:P1001 wd:%(yemen)s } UNION { ?pos wdt:P17 wd:%(yemen)s }
  FILTER EXISTS { ?item wdt:P2002|wdt:P3789|wdt:P2397 [] }
  ?pos rdfs:label ?role . FILTER(LANG(?role) = "en")
}""",
    # Living Yemeni citizens with an X, Telegram or YouTube account (politicians, journalists,
    # analysts); occupation is shown so private individuals can be ruled out on review.
    "yemeni_public_figures": """
SELECT DISTINCT ?item ?role WHERE {
  ?item wdt:P27 wd:%(yemen)s ; wdt:P31 wd:Q5 .
  FILTER EXISTS { ?item wdt:P2002|wdt:P3789|wdt:P2397 [] }
  FILTER NOT EXISTS { ?item wdt:P570 [] }
  OPTIONAL { ?item wdt:P106 ?occ . ?occ rdfs:label ?role . FILTER(LANG(?role) = "en") }
}""",
    # Embassies and missions located in Yemen, or operated by Yemen.
    "diplomatic_missions": """
SELECT DISTINCT ?item ?role WHERE {
  ?item wdt:P31 ?type . ?type rdfs:label "embassy"@en .
  { ?item wdt:P17 wd:%(yemen)s } UNION { ?item wdt:P137 wd:%(yemen)s }
  BIND("embassy" AS ?role)
}""",
}


def sparql(client: httpx.Client, query: str) -> list[dict]:
    for attempt in range(3):
        r = client.get(WD_SPARQL, params={"query": query, "format": "json"})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["results"]["bindings"]
    r.raise_for_status()
    return []


def candidates(records: list[dict]) -> dict:
    """Suggestions for review: public figures and missions not yet in the registry."""
    wd = Wikidata()
    have = {rec.get("wikidata") for rec in records if rec.get("wikidata")}
    have_handles = {
        (a.get("platform"), str(a.get("handle", "")).lower().lstrip("@"))
        for rec in records
        for a in rec.get("accounts") or []
    }
    roles: dict[str, dict[str, set]] = {}
    out: dict = {"queries": {}, "candidates": []}
    for name, q in CANDIDATE_QUERIES.items():
        try:
            rows = sparql(wd.client, q % {"yemen": YEMEN})
        except httpx.HTTPError as exc:
            out["queries"][name] = f"error: {str(exc)[:200]}"
            continue
        out["queries"][name] = len(rows)
        for row in rows:
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            entry = roles.setdefault(qid, {"found_by": set(), "roles": set()})
            entry["found_by"].add(name)
            if row.get("role"):
                entry["roles"].add(row["role"]["value"])
    ids = [q for q in roles if q not in have]
    for qid, ent in wd.entities(ids).items():
        info = summarise(ent)
        handles = info["handles"]
        if any((p, h.lower().lstrip("@")) in have_handles for p, hs in handles.items() for h in hs):
            continue
        best = max((f["value"] for f in info["followers"].values()), default=0)
        out["candidates"].append(
            {
                "qid": qid,
                "wikidata": f"https://www.wikidata.org/wiki/{qid}",
                "label_en": info["label_en"],
                "label_ar": ent.get("labels", {}).get("ar", {}).get("value"),
                "found_by": sorted(roles[qid]["found_by"]),
                "roles": sorted(roles[qid]["roles"]),
                "websites": info["websites"],
                "handles": handles,
                "followers": info["followers"],
                "max_followers": best,
                "enwiki": info["enwiki"],
            }
        )
    out["candidates"].sort(key=lambda c: -c["max_followers"])
    return out


# ---------------------------------------------------------------- report


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    records = load_registry()
    fetcher = Fetcher(sleep=time.sleep)
    try:
        feeds = check_feeds(fetcher, records)
        (out / "feeds_check.json").write_text(json.dumps(feeds, ensure_ascii=False, indent=1))
        found = discover(fetcher, records, feeds)
        (out / "discovered.json").write_text(json.dumps(found, ensure_ascii=False, indent=1))
    finally:
        fetcher.close()
    wiki = enrich(records)
    (out / "wikidata.json").write_text(json.dumps(wiki, ensure_ascii=False, indent=1))
    try:
        cands = candidates(records)
    except Exception as exc:  # suggestions are optional; never fail the check for them
        cands = {"error": str(exc)[:300], "candidates": []}
    (out / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1))

    ok = [f for f in feeds if f.get("ok")]
    new = [f for f in found if f.get("ok") and f.get("items")]
    md = [
        "# Registry check\n",
        f"Sources: {len(records)}. Feeds checked: {len(feeds)}, parsed: {len(ok)}.",
        f"Feeds discovered and parsed for sources without a working feed: {len(new)}.",
        f"Wikidata items matched: {len([k for k in wiki if not k.startswith('_')])}.",
        f"Wikidata candidates for review: {len(cands['candidates'])} {cands.get('queries', cands.get('error'))}.\n",
        "## Listed feeds\n",
        "| Source | Type | Feed | Result | Items | Yemen-relevant | Newest |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in feeds + [{"id": "", "url": ""}] + found:
        if not f["id"]:
            md += [
                "",
                "## Discovered feeds\n",
                "| Source | Type | Feed | Result | Items | Yemen-relevant | Newest |",
                "|---|---|---|---|---|---|---|",
            ]
            continue
        result = "ok" if f.get("ok") else f"{f.get('error')} {f.get('status') or ''}".strip()
        md.append(
            f"| {f['id']} | {f.get('type', f.get('stage', ''))} | {f['url']} | {result} | {f.get('items', '')} | "
            f"{f.get('yemen_relevant', '')} | {(f.get('newest') or '')[:10]} |"
        )
    (out / "registry_check.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:4]))


if __name__ == "__main__":
    main()
