"""Stage 2: deduplication, syndication detection and story clustering.

Layers (cheapest first):
1. canonical URL hash (enforced at insert; see ingest.py)
2. exact content hash of normalised title + excerpt         -> duplicate
3. MinHash LSH over title shingles, confirmed by fuzzy ratio -> duplicate (same outlet)
                                                               same_story / syndicated_from (other outlets)
4. embedding similarity (analyse stage, see ``semantic_links``) -> same_story / similar

Story clusters are connected components of duplicate / syndicated_from / same_story
edges. Each cluster stores ``source_count`` and ``independent_source_count`` so the
platform can tell "50 sites republished one wire story" from "50 outlets covered it".
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

import structlog
from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from observatory.config import get_settings
from observatory.db import models as m

log = structlog.get_logger()
CLUSTER_RELATIONS = ("duplicate", "syndicated_from", "same_story")
NUM_PERM = 64
STORY_HORIZON = dt.timedelta(hours=48)
MAX_STORY_LINKS = 3
REPOST_WINDOW = dt.timedelta(hours=12)


def _shingles(text: str, k: int = 3) -> set[str]:
    words = text.split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)} | set(words)


def _minhash(text: str) -> MinHash:
    mh = MinHash(num_perm=NUM_PERM, seed=7)
    for s in _shingles(text):
        mh.update(s.encode("utf-8"))
    return mh


def _add_relation(
    session: Session, a: int, b: int, rel: str, score: float, method: str, model_version_id: int | None = None
) -> None:
    exists = session.scalar(
        select(m.ArticleRelation.id).where(
            m.ArticleRelation.from_article_id == a,
            m.ArticleRelation.to_article_id == b,
            m.ArticleRelation.relation_type == rel,
        )
    )
    if exists is None:
        session.add(
            m.ArticleRelation(
                from_article_id=a,
                to_article_id=b,
                relation_type=rel,
                similarity_score=round(score, 4),
                method=method,
                model_version_id=model_version_id,
            )
        )


def _window_articles(session: Session, start: dt.datetime) -> list[m.Article]:
    return list(
        session.scalars(
            select(m.Article)
            .where(m.Article.published_at >= start, m.Article.deleted_at.is_(None))
            .order_by(m.Article.published_at, m.Article.id)
        )
    )


def run_dedup(session: Session) -> dict:
    s = get_settings()
    new_ids = set(session.scalars(select(m.Article.id).where(m.Article.processing_status == "new")))
    if not new_ids:
        return {"new": 0}
    earliest = session.scalar(
        select(m.Article.published_at)
        .where(m.Article.id.in_(new_ids))
        .order_by(m.Article.published_at)
        .limit(1)
    )
    window_start = earliest - dt.timedelta(days=s.dedup_window_days)
    arts = _window_articles(session, window_start)
    by_id = {a.id: a for a in arts}
    stats = {
        "new": len(new_ids),
        "exact_duplicates": 0,
        "near_duplicates": 0,
        "syndicated": 0,
        "same_story": 0,
    }

    # --- exact content hash
    first_by_hash: dict[str, m.Article] = {}
    for a in arts:
        prior = first_by_hash.get(a.content_hash)
        if prior is None:
            first_by_hash[a.content_hash] = a
            continue
        if prior.source_id != a.source_id and a.published_at - prior.published_at > STORY_HORIZON:
            first_by_hash[a.content_hash] = a  # identical boilerplate weeks apart is not syndication
            continue
        if a.id in new_ids and a.duplicate_of_id is None:
            if prior.source_id == a.source_id:
                a.duplicate_of_id, a.canonical_article_id, a.similarity_score = prior.id, prior.id, 1.0
                _add_relation(session, a.id, prior.id, "duplicate", 1.0, "content_hash")
                stats["exact_duplicates"] += 1
            else:
                a.is_syndicated, a.similarity_score = True, 1.0
                a.canonical_article_id = prior.canonical_article_id or prior.id
                _add_relation(session, a.id, prior.id, "syndicated_from", 1.0, "content_hash")
                stats["syndicated"] += 1

    # --- near-duplicate titles via MinHash LSH
    lsh = MinHashLSH(threshold=0.5, num_perm=NUM_PERM)
    hashes = {}
    for a in arts:
        if not a.title_normalized or len(a.title_normalized.split()) < 4:
            continue
        mh = _minhash(a.title_normalized)
        hashes[a.id] = mh
        lsh.insert(str(a.id), mh)
    threshold = s.title_near_dup_threshold * 100
    for aid in sorted(new_ids & hashes.keys(), key=lambda i: (by_id[i].published_at, i)):
        a = by_id[aid]
        if a.duplicate_of_id is not None:
            continue
        same_src, other_src = [], []
        for cand in lsh.query(hashes[aid]):
            b = by_id[int(cand)]
            # link the newer article to older ones only, and only within the story horizon:
            # the same headline about a different day's event is a different story
            if b.id == aid or (b.published_at, b.id) > (a.published_at, a.id):
                continue
            if a.published_at - b.published_at > STORY_HORIZON:
                continue
            title_sim = fuzz.token_set_ratio(a.title_normalized, b.title_normalized)
            if title_sim < threshold:
                continue
            body_sim = (
                fuzz.ratio(a.excerpt_normalized or "", b.excerpt_normalized or "") / 100.0
                if a.excerpt_normalized and b.excerpt_normalized
                else 0.0
            )
            (same_src if b.source_id == a.source_id else other_src).append((title_sim / 100.0, body_sim, b))
        # same outlet: a re-post is a duplicate if the body matches or it reappeared within hours
        dup = [x for x in same_src if x[1] >= 0.95 or a.published_at - x[2].published_at <= REPOST_WINDOW]
        if dup:
            score, body_sim, b = max(dup, key=lambda x: (x[0] + x[1], -x[2].id))
            a.duplicate_of_id, a.canonical_article_id = b.id, b.canonical_article_id or b.id
            a.similarity_score = max(score, body_sim)
            _add_relation(session, a.id, b.id, "duplicate", a.similarity_score, "title_minhash")
            stats["near_duplicates"] += 1
            continue
        if not other_src:
            continue
        # other outlets: syndication when the copy is (nearly) verbatim, else the same story
        no_body = not a.excerpt_normalized
        synd = [
            x for x in other_src if x[1] >= 0.9 or (no_body and x[0] >= 0.97 and x[2].language == a.language)
        ]
        if synd and not a.is_syndicated:
            score, body_sim, b = min(synd, key=lambda x: (x[2].published_at, x[2].id))  # earliest copy
            a.is_syndicated = True
            a.canonical_article_id = a.canonical_article_id or b.canonical_article_id or b.id
            _add_relation(session, a.id, b.id, "syndicated_from", max(score, body_sim), "title_minhash")
            stats["syndicated"] += 1
        for score, _body, b in sorted(other_src, key=lambda x: -x[0])[:MAX_STORY_LINKS]:
            if not synd or b.id != a.canonical_article_id:
                _add_relation(session, a.id, b.id, "same_story", score, "title_minhash")
                stats["same_story"] += 1
        a.similarity_score = max(a.similarity_score or 0.0, max(x[0] for x in other_src))

    for aid in new_ids:
        by_id[aid].processing_status = "deduped"
    session.flush()
    stats["clusters"] = rebuild_story_clusters(session, window_start)
    session.commit()
    log.info("dedup_done", **stats)
    return stats


def semantic_links(session: Session, article_ids: list[int], model_version_id: int, semantic: bool) -> int:
    """Embedding-based same-story / similar edges against the recent window (pgvector)."""
    s = get_settings()
    if not article_ids:
        return 0
    same = s.semantic_same_story_threshold if semantic else 0.97
    related = s.semantic_related_threshold if semantic else 0.90
    n = 0
    for aid in article_ids:
        a = session.get(m.Article, aid)
        emb = session.scalar(
            select(m.ArticleEmbedding.embedding).where(
                m.ArticleEmbedding.article_id == aid, m.ArticleEmbedding.model_version_id == model_version_id
            )
        )
        if a is None or emb is None:
            continue
        lo = a.published_at - dt.timedelta(days=s.dedup_window_days)
        dist = m.ArticleEmbedding.embedding.cosine_distance(emb)
        rows = session.execute(
            select(m.ArticleEmbedding.article_id, (1 - dist).label("sim"), m.Article.source_id)
            .join(m.Article, m.Article.id == m.ArticleEmbedding.article_id)
            .where(
                m.ArticleEmbedding.model_version_id == model_version_id,
                m.ArticleEmbedding.article_id != aid,
                m.Article.published_at.between(lo, a.published_at),
                m.Article.duplicate_of_id.is_(None),
            )
            .order_by(dist)
            .limit(10)
        ).all()
        for other_id, sim, other_source in rows:
            if sim >= same and other_source != a.source_id:
                _add_relation(session, aid, other_id, "same_story", float(sim), "embedding", model_version_id)
                n += 1
            elif sim >= related:
                _add_relation(session, aid, other_id, "similar", float(sim), "embedding", model_version_id)
                n += 1
    session.flush()
    return n


def rebuild_story_clusters(session: Session, window_start: dt.datetime) -> int:
    """Union-find over cluster edges for articles in the window; idempotent."""
    arts = _window_articles(session, window_start)
    ids = [a.id for a in arts]
    if not ids:
        return 0
    parent = {i: i for i in ids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges = session.execute(
        select(m.ArticleRelation.from_article_id, m.ArticleRelation.to_article_id).where(
            m.ArticleRelation.relation_type.in_(CLUSTER_RELATIONS),
            or_(m.ArticleRelation.from_article_id.in_(ids), m.ArticleRelation.to_article_id.in_(ids)),
        )
    ).all()
    for a, b in edges:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[m.Article]] = defaultdict(list)
    for a in arts:
        groups[find(a.id)].append(a)

    # Keep cluster ids stable across runs: a group reuses the cluster its earliest
    # article already belonged to; clusters left without members are deleted.
    old_of = {a.id: a.story_cluster_id for a in arts}
    old_cluster_ids = {c for c in old_of.values() if c}
    reused: set[int] = set()
    count = 0
    for members in groups.values():
        rep = min(members, key=lambda x: (x.published_at, x.id))
        independent = {x.source_id for x in members if not x.is_syndicated and x.duplicate_of_id is None}
        cid = next(
            (
                old_of[x.id]
                for x in sorted(members, key=lambda x: (x.published_at, x.id))
                if old_of[x.id] and old_of[x.id] not in reused
            ),
            None,
        )
        cluster = session.get(m.StoryCluster, cid) if cid else None
        if cluster is None:
            cluster = m.StoryCluster()
            session.add(cluster)
        cluster.representative_article_id = rep.id
        cluster.first_seen_at = min(x.published_at for x in members)
        cluster.last_seen_at = max(x.published_at for x in members)
        cluster.article_count = len(members)
        cluster.source_count = len({x.source_id for x in members})
        cluster.independent_source_count = len(independent)
        cluster.language_count = len({x.language for x in members if x.language})
        session.flush()
        reused.add(cluster.id)
        for x in members:
            x.story_cluster_id = cluster.id
        count += 1
    session.flush()
    orphaned = old_cluster_ids - reused
    if orphaned:
        still_used = set(
            session.scalars(
                select(m.Article.story_cluster_id).where(m.Article.story_cluster_id.in_(orphaned))
            )
        )
        session.execute(
            update(m.StoryCluster)
            .where(m.StoryCluster.id.in_(orphaned - still_used))
            .values(representative_article_id=None)
        )
        session.execute(delete(m.StoryCluster).where(m.StoryCluster.id.in_(orphaned - still_used)))
    return count
