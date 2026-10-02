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


def test_words_that_merely_start_like_yemen_or_taiz_are_not_relevant():
    # Real false positives from the first live run: يمنع ("prevents"), يمنح ("grants"), تعزيز ("strengthening").
    assert yemen_relevance("القضاء الأميركي يمنع «مؤقتاً» بناء جدار حدودي في ولاية تكساس") == 0.0
    assert yemen_relevance("الركراكي يمنح فوز تواركة أمام تمارة") == 0.0
    assert yemen_relevance("وزير الطاقة: نتطلع إلى تعزيز التعاون بين البلدين") == 0.0


def test_arabic_inflections_of_yemen_still_match():
    assert yemen_relevance("الحكومة اليمنية تعلن موازنة جديدة") == 1.0
    assert yemen_relevance("وفد يمني يصل إلى الرياض") == 1.0
    assert yemen_relevance("مواجهات في تعز وصنعاء") == 1.0
    assert yemen_relevance("لليمنيين في الخارج") == 1.0
