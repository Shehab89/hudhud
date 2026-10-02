from hudhud.nlp.text import (
    content_hash,
    count_terms,
    detect_script,
    find_term,
    normalize_arabic,
    normalize_for_matching,
    split_sentences,
    strip_html,
)


def test_arabic_orthography_is_folded():
    assert normalize_arabic("إِعْلَان") == "اعلان"
    assert normalize_arabic("مستشفى") == "مستشفي"
    assert normalize_arabic("الحديدة") == "الحديده"
    assert normalize_arabic("الحديدة", fold_teh_marbuta=False) == "الحديدة"
    assert normalize_arabic("يـــمن") == "يمن"


def test_normalize_for_matching_folds_digits_case_and_accents():
    assert normalize_for_matching("Ṣanʿāʼ  CAFÉ") == "sanʿa' cafe"
    assert normalize_for_matching("٢٠٢٦") == "2026"
    assert normalize_for_matching("صنعاء، اليمن؟") == "صنعاء, اليمن?"
    assert normalize_for_matching(None) == ""


def test_arabic_term_matches_with_clitics_and_plural():
    text = normalize_for_matching("وبالحديدة شنت الطائرات غارات على الميناء")
    assert find_term("الحديدة", text)
    assert find_term("غارة", text)  # singular term matches the plural غارات
    assert not find_term("عدن", text)


def test_latin_term_matches_whole_words_only():
    text = normalize_for_matching("The Houthis said; Houthi forces, not Houthiland.")
    assert count_terms(["Houthi"], text) == {"Houthi": 2}
    assert not find_term("Aden", normalize_for_matching("Adenauer visited"))


def test_content_hash_ignores_orthographic_noise():
    assert content_hash("عاجل: غارة على صنعاء", None) == content_hash("عاجل:  غارة علي صنعاء")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_strip_html_and_script_detection():
    assert strip_html("<p>Aden &amp; Taiz​</p>") == "Aden & Taiz"
    assert detect_script("مرحبا hello")[0] == "Arab"
    assert detect_script("1234")[0] == "Zyyy"


def test_split_sentences_handles_arabic_question_mark():
    assert split_sentences("هل انتهى؟ نعم. Done!") == ["هل انتهى؟", "نعم.", "Done!"]
