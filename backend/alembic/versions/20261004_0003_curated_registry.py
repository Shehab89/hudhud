"""curated source registry: categories, tiers, selection record, separate scores

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXED = (
    "category",
    "tier",
    "region",
    "content_type",
    "yemen_political_alignment",
    "regional_alignment",
    "institutional_importance",
    "registry_status",
)


def upgrade() -> None:
    add = op.add_column
    add("sources", sa.Column("category", sa.String(40), server_default="MEDIA", nullable=False))
    add("sources", sa.Column("tier", sa.String(1), nullable=True))
    add("sources", sa.Column("region", sa.String(30), nullable=True))
    add("sources", sa.Column("platform", sa.String(20), nullable=True))
    add("sources", sa.Column("content_type", sa.String(30), server_default="journalism", nullable=False))
    add("sources", sa.Column("wikidata", sa.String(20), nullable=True))
    add(
        "sources",
        sa.Column("yemen_political_alignment", sa.String(40), server_default="unknown", nullable=False),
    )
    add("sources", sa.Column("sub_alignment", sa.Text(), nullable=True))
    add("sources", sa.Column("regional_alignment", sa.String(40), server_default="unknown", nullable=False))
    add("sources", sa.Column("domestic_political_orientation", sa.String(40), nullable=True))
    add("sources", sa.Column("institutional_importance", sa.String(10), nullable=True))
    add("sources", sa.Column("influence_score", sa.Float(), nullable=True))
    add("sources", sa.Column("reliability_score", sa.Float(), nullable=True))
    add("sources", sa.Column("classification_confidence", sa.Float(), nullable=True))
    add("sources", sa.Column("assessment_date", sa.Date(), nullable=True))
    add(
        "sources",
        sa.Column("selection", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    add(
        "sources",
        sa.Column("accounts", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    add("sources", sa.Column("holder", postgresql.JSONB(), nullable=True))
    add("sources", sa.Column("registry_status", sa.String(20), server_default="curated", nullable=False))
    for col in _INDEXED:
        op.create_index(f"ix_sources_{col}", "sources", [col])


def downgrade() -> None:
    for col in _INDEXED:
        op.drop_index(f"ix_sources_{col}", table_name="sources")
    for col in (
        "registry_status",
        "holder",
        "accounts",
        "selection",
        "assessment_date",
        "classification_confidence",
        "reliability_score",
        "influence_score",
        "institutional_importance",
        "domestic_political_orientation",
        "regional_alignment",
        "sub_alignment",
        "yemen_political_alignment",
        "wikidata",
        "content_type",
        "platform",
        "region",
        "tier",
        "category",
    ):
        op.drop_column("sources", col)
