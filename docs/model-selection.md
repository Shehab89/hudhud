# Model selection

Constraints that drove the choices: Arabic and English first, then French, German,
Spanish, Italian, Turkish, Persian, Russian and Chinese; a daily batch on **CPU** (GitHub
Actions runners: 4 vCPU, 16 GB RAM, no GPU); open licences; reproducible versions; and a
working system with no paid API at all.

The registry of candidate and default models is `database/seeds/models.yaml` (loaded
into `models` / `model_versions`); every result points at the exact version that
produced it.

## Embeddings

| Model | Dims | Size | Languages | CPU cost | Verdict |
|---|---|---|---|---|---|
| **intfloat/multilingual-e5-small** (MIT) | 384 | 118M | ~100 incl. Arabic | low | **default**: good multilingual retrieval for its size, fits the daily batch |
| Qwen/Qwen3-Embedding-0.6B (Apache-2.0) | up to 1024 (Matryoshka, truncatable to 384) | 600M | 100+ | ~5x e5-small | upgrade candidate; no schema change if truncated to 384 |
| BAAI/bge-m3 (MIT) | 1024 | 568M | 100+ | ~5x | upgrade candidate; needs a schema change (vector 1024) |
| observatory/hashing-embedding | 384 | none | any | negligible | fallback only: character n-gram hashing, lexical, **not cross-lingual** |

## Sentiment

| Model | Languages | Notes | Verdict |
|---|---|---|---|
| **cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual** | ar, en, fr, de, es, it, ... | trained on tweets; domain shift to news expected | **default** for non-Arabic |
| **CAMeL-Lab/bert-base-arabic-camelbert-mix-sentiment** (Apache-2.0) | Arabic (MSA + dialects) | Arabic-specific | **default** for Arabic |
| observatory/lexicon | ar, en, fr, de, es | transparent, deterministic | fallback |

## Zero-shot (categories, frames, emotions, tone)

| Model | Verdict |
|---|---|
| **MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7** (MIT) | **secondary model** in confidence routing (0.60–0.85 band); 100 languages |

## Named entities

The default is a curated **gazetteer** (aliases in many languages, typed by usage), which
is what terminology analysis needs. `Davlan/xlm-roberta-base-ner-hrl` can be switched on
(`USE_TRANSFORMER_NER=true`) to surface names missing from the gazetteer for curation.

## Topic modelling

BERTopic (UMAP + HDBSCAN + c-TF-IDF) on the multilingual embeddings when installed and
the corpus is large enough; k-means + c-TF-IDF otherwise. Both report NPMI coherence and
diversity.

## LLM tier

| Model | Use | Why |
|---|---|---|
| **claude-haiku-4-5** (Anthropic API, optional) | topic labels (EN/AR), low-confidence categories and frames, ambiguity review | strong Arabic, structured outputs with schema validation, low price ($1 / $5 per million input / output tokens at the time of writing) |

Calls use versioned prompt templates and Pydantic schemas; invalid responses are retried
and then stored as failures; responses are cached by (template, input hash, model); a
daily budget (`LLM_DAILY_BUDGET_USD`, default $1) and per-run cap
(`LLM_MAX_ARTICLES_PER_RUN`, default 50) are enforced; evidence quotes must be verbatim
substrings of the article.

## Benchmarks

**NOT YET MEASURED.** `model_benchmarks` exists for per-language accuracy/F1 on a
labelled sample, but no labelled Yemen-news evaluation set exists yet. Building one
(roughly 300 Arabic and 300 English headlines with excerpts, double-annotated for
sentiment, category and frame) is the first recommended research task; accepted human
corrections accumulate towards it. Until then, treat model outputs as indicative and
compare groups, not single articles.

## Switching models

Change `EMBEDDING_MODEL`, `SENTIMENT_MODEL`, `SENTIMENT_MODEL_AR`, `ZERO_SHOT_MODEL` or
`LLM_MODEL` in the environment. The next run registers the new model version, analysis
rows carry it, and a full re-analysis can be triggered by resetting
`processing_status`. Changing embedding dimensions requires a migration.
