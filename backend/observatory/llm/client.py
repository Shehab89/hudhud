"""Tier-2 LLM calls with strict schemas, validation, caching, versioned prompts and a budget.

* Optional: disabled unless LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY are set.
* Every call uses a versioned prompt template (``prompt_templates`` table) and a
  Pydantic schema; responses are validated, invalid ones retried, and failures stored.
* Responses are cached by (template, input hash, model): duplicates never re-bill.
* Evidence quotes returned by the model are checked against the article text and
  dropped when they are not verbatim substrings (no fabricated evidence).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatory.config import get_settings
from observatory.db import models as m

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

# USD per million tokens (input, output). Source: Anthropic pricing, checked 2026-10-02.
PRICING = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}


# ---------------------------------------------------------------- schemas


class TopicLabel(BaseModel):
    label_en: str = Field(description="Short descriptive topic name in English, max 10 words")
    label_ar: str = Field(description="The same name in Modern Standard Arabic")
    description: str = Field(description="One or two neutral sentences describing what the articles cover")
    confidence: float = Field(ge=0, le=1)
    uncertainties: list[str] = Field(default_factory=list)


class FrameEvidence(BaseModel):
    frame: str
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str = Field(description="Verbatim sentence copied from the article")


class ArticleReview(BaseModel):
    primary_category: str = Field(description="One slug from the provided category list, or 'uncertain'")
    secondary_categories: list[str] = Field(default_factory=list)
    frames: list[FrameEvidence] = Field(default_factory=list)
    summary: str = Field(description="Neutral 1-2 sentence summary; no quotes, no judgement")
    confidence: float = Field(ge=0, le=1)
    uncertainties: list[str] = Field(default_factory=list)


PROMPTS: dict[str, dict[str, Any]] = {
    "topic_label": {
        "version": "1.0",
        "schema": TopicLabel,
        "system": (
            "You name topic clusters for a non-partisan research platform about media coverage of Yemen. "
            "Describe what the articles are about using neutral wording. Do not adopt any outlet's "
            "terminology as your own, do not judge actors, and do not speculate beyond the evidence."
        ),
        "template": (
            "Statistical topic representation (c-TF-IDF terms with weights):\n{terms}\n\n"
            "Representative headlines (various outlets and languages):\n{headlines}\n\n"
            "Return a topic name in English and Arabic, a short neutral description, your confidence and any uncertainties."
        ),
    },
    "article_review": {
        "version": "1.0",
        "schema": ArticleReview,
        "system": (
            "You annotate news articles about Yemen for a research platform. Classify, do not opine. "
            "Frames describe how the text presents the issue, not whether it is true. Every frame needs a "
            "verbatim evidence sentence copied exactly from the article. If evidence is insufficient, say "
            "'uncertain' and list the uncertainty instead of guessing."
        ),
        "template": (
            "Allowed category slugs:\n{categories}\n\nAllowed frames:\n{frames}\n\n"
            "Article (language: {language}):\nTITLE: {title}\nTEXT: {text}"
        ),
    },
}


class LLMUnavailable(Exception):
    pass


class LLMClient:
    def __init__(self, session: Session):
        self.s = get_settings()
        self.session = session
        if self.s.llm_provider != "anthropic" or not self.s.anthropic_api_key:
            raise LLMUnavailable("LLM disabled (set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY)")
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=self.s.anthropic_api_key, max_retries=2, timeout=60)

    def _template_row(self, name: str) -> m.PromptTemplate:
        p = PROMPTS[name]
        row = self.session.scalar(
            select(m.PromptTemplate).where(
                m.PromptTemplate.name == name, m.PromptTemplate.version == p["version"]
            )
        )
        if row is None:
            row = m.PromptTemplate(
                name=name,
                version=p["version"],
                template=p["system"] + "\n---\n" + p["template"],
                json_schema=p["schema"].model_json_schema(),
                model=self.s.llm_model,
                temperature=0.0,
            )
            self.session.add(row)
            self.session.flush()
        return row

    def spent_today(self) -> float:
        start = dt.datetime.combine(dt.date.today(), dt.time.min, tzinfo=dt.UTC)
        return float(
            self.session.scalar(
                select(func.coalesce(func.sum(m.LLMCall.cost_usd), 0.0)).where(m.LLMCall.created_at >= start)
            )
            or 0.0
        )

    def call(self, name: str, **fields: Any) -> BaseModel | None:
        p = PROMPTS[name]
        schema: type[BaseModel] = p["schema"]
        tpl = self._template_row(name)
        user = p["template"].format(**fields)
        input_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        cached = self.session.scalar(
            select(m.LLMCall).where(
                m.LLMCall.prompt_template_id == tpl.id,
                m.LLMCall.input_hash == input_hash,
                m.LLMCall.model == self.s.llm_model,
            )
        )
        if cached is not None and cached.valid and cached.response is not None:
            return schema.model_validate(cached.response)
        if self.spent_today() >= self.s.llm_daily_budget_usd:
            log.warning("llm_budget_exhausted", budget=self.s.llm_daily_budget_usd)
            return None

        record = cached or m.LLMCall(prompt_template_id=tpl.id, input_hash=input_hash, model=self.s.llm_model)
        self.session.add(record)
        attempts, last_error, parsed = 0, None, None
        tokens_in = tokens_out = 0
        while attempts < 3 and parsed is None:
            attempts += 1
            try:
                resp = self.client.messages.parse(
                    model=self.s.llm_model,
                    max_tokens=2048,
                    system=p["system"],
                    messages=[{"role": "user", "content": user}],
                    output_format=schema,
                )
                tokens_in += resp.usage.input_tokens
                tokens_out += resp.usage.output_tokens
                if resp.stop_reason == "refusal":
                    last_error = "refusal"
                    break
                parsed = schema.model_validate(resp.parsed_output.model_dump())
            except ValidationError as exc:
                last_error = f"invalid output: {exc.errors()[:2]}"
            except self._anthropic.RateLimitError as exc:
                last_error = f"rate limited: {exc}"
                break
            except self._anthropic.APIStatusError as exc:
                last_error = f"api status {exc.status_code}"
                if exc.status_code < 500:
                    break
            except self._anthropic.APIConnectionError as exc:
                last_error = f"connection: {exc}"
        price_in, price_out = PRICING.get(self.s.llm_model, (1.0, 5.0))
        record.attempts = attempts
        record.input_tokens, record.output_tokens = tokens_in, tokens_out
        record.cost_usd = round(tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out, 6)
        record.valid = parsed is not None
        record.response = json.loads(parsed.model_dump_json()) if parsed else None
        record.error = None if parsed else last_error
        self.session.flush()
        return parsed


def verbatim_or_none(quote: str | None, text: str) -> str | None:
    """Keep an LLM-supplied evidence quote only if it appears in the article text."""
    if not quote:
        return None
    q = " ".join(quote.split())
    return q if q and q in " ".join(text.split()) else None
