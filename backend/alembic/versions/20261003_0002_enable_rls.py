"""enable row level security on all tables

Hosted Postgres services such as Supabase expose the public schema through a REST API.
With RLS enabled and no policies, those API roles can read nothing. The pipeline and the
Hudhud API connect as the table owner, which RLS does not restrict.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOOP = """
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = current_schema() LOOP
    EXECUTE format('ALTER TABLE %I {action} ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_LOOP.format(action="ENABLE"))


def downgrade() -> None:
    op.execute(_LOOP.format(action="DISABLE"))
