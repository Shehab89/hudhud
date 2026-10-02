# Limitations and future work

## What was and was not verified during the build

| Claim | Status |
|---|---|
| Full pipeline (dedup → analyse → topics → metrics) on ~950 DEMO DATA articles | run successfully, about 40 s, fallback NLP |
| 67 automated tests (unit + PostgreSQL), migration round-trip, `alembic check` | passing |
| API endpoints | tested (pytest + a 36-endpoint smoke run) |
| Frontend | type-checks, lints, production build passes; all pages checked in EN and AR in a browser, light and dark, desktop and mobile width |
| Live feed fetching | **NOT VERIFIED**: the build sandbox could not reach news sites. Parsers and the fetcher are tested with recorded and mocked responses. 92 feed URLs were checked separately with a web fetcher |
| Transformer models, BERTopic | **NOT RUN**: the sandbox could not download models. The code paths exist and fall back safely; first exercised in Docker/Actions |
| LLM tier | **NOT RUN against the live API** (no key configured). REQUIRES CONFIGURATION |
| Docker images | **NOT BUILT** in the sandbox (registry rate limit); built in CI by `build.yml` |
| GitHub workflows | YAML validated; **not yet run** (no repository yet) |
| Model accuracy on Yemeni news | **NOT MEASURED** (no labelled evaluation set yet) |

## Methodological limits

* **Coverage bias.** The corpus is what outlets publish in feeds. Many Yemeni outlets
  have no working feed, and social media, Telegram, television and radio, where much
  Yemeni discourse happens, are not monitored.
* **Excerpts, not full texts.** Analysis runs on headline + feed excerpt (≤ 600
  characters), which limits framing and targeted-sentiment recall. This is deliberate
  (copyright, publisher terms).
* **Model error.** Sentiment models were trained on social media; zero-shot
  classifiers are general-purpose; Arabic dialects, sarcasm and reported speech are
  hard. Compare groups and trends, not single articles.
* **Orientation is sparse.** 112 of 193 outlets are `unknown`; labels are drafts
  (`review_status: draft`) pending expert review.
* **Operating base is approximate** for outlets with several bureaus or that moved.
* **Events are reports**, dated by publication and located by gazetteer; they are not
  verified incidents and are not casualty data.
* **Fallback mode is lexical.** Without transformer models, topics separate by language
  and semantic search is keyword-like. Results record which backend produced them.

## NOT IMPLEMENTED

* User registration and login in the web interface (API keys are issued with the CLI).
* An annotation interface in the frontend (corrections go through the API; the admin
  console lists and reviews them).
* Applying accepted corrections other than sentiment, category and frame.
* Social media, Telegram, YouTube, TV/radio transcript ingestion.
* Full-text extraction (by design; `access_policy` exists for publishers that permit it).
* Machine translation of excerpts.
* Claim matching and fact-check linking beyond the `claims` table structure.
* Email or webhook alerts for new trends.
* A labelled benchmark set and per-language accuracy figures.

## Future improvements (suggested order)

1. Run live for two weeks; fix or deactivate failing feeds; re-verify the 65 unverified
   feeds.
2. Build a small labelled evaluation set (Arabic and English) and fill
   `model_benchmarks`; calibrate thresholds per language.
3. Expert review of orientation labels and operating bases with Yemeni media researchers.
4. Annotation UI and accounts, so corrections come from more people.
5. Telegram public channels (many Yemeni outlets publish there first), with the same
   ethics rules.
6. Upgrade embeddings (Qwen3-Embedding-0.6B truncated to 384 dims) once CPU time allows.
7. Translation of excerpts for cross-language reading (kept separate from originals).
8. Alerts for emerging topics, and scheduled reports for subscribers.
