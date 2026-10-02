from hudhud.ingest.relevance import RELEVANCE_THRESHOLD, yemen_relevance


def test_yemen_in_title_is_relevant():
    assert yemen_relevance("Floods hit Yemen's Marib province") == 1.0
    assert yemen_relevance("سيول تضرب محافظة مأرب في اليمن") == 1.0


def test_yemen_only_in_summary_scores_lower_but_passes():
    score = yemen_relevance("Shipping insurers raise premiums", "after attacks claimed by Yemen's Houthis")
    assert RELEVANCE_THRESHOLD <= score < 1.0


def test_unrelated_story_is_filtered():
    assert (
        yemen_relevance("Football results from Europe", "Late goals decide the match") < RELEVANCE_THRESHOLD
    )
