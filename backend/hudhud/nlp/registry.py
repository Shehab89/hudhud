"""Model registry helpers and backend resolution.

Every analytical row references a ``model_versions`` row, so results stay traceable when
models change. ``version`` encodes the backend actually used; for example an embedding
produced by the hashing fallback is recorded under ``hudhud/hashing-embedding``,
never under the transformer model it stands in for.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m

ANALYSIS_VERSION = "2026.10.1"


@lru_cache
def transformers_available() -> bool:
    return all(
        importlib.util.find_spec(mod) is not None
        for mod in ("torch", "transformers", "sentence_transformers")
    )


def use_transformers() -> bool:
    backend = get_settings().nlp_backend
    if backend == "fallback":
        return False
    if backend == "transformers":
        return True
    return transformers_available()


def model_version_id(
    session: Session,
    name: str,
    version: str = "default",
    parameters: dict[str, Any] | None = None,
    provider: str = "huggingface",
) -> int:
    mod = session.scalar(select(m.Model).where(m.Model.name == name))
    if mod is None:
        mod = m.Model(name=name, provider=provider)
        session.add(mod)
        session.flush()
    mv = session.scalar(
        select(m.ModelVersion).where(m.ModelVersion.model_id == mod.id, m.ModelVersion.version == version)
    )
    if mv is None:
        mv = m.ModelVersion(model_id=mod.id, version=version, parameters=parameters or {})
        session.add(mv)
        session.flush()
    return mv.id
