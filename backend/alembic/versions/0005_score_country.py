"""country dimension on trending / blowing-up score tables

Adds `country` to app_trending_scores and app_blowing_up_scores and makes the
primary key composite (app_id, country) so scores are isolated per storefront.
Existing rows backfill to 'us', preserving current behaviour.

Revision ID: 0005_score_country
Revises: 0004_ranking_genre
"""
from alembic import op
from sqlalchemy import text

revision = "0005_score_country"
down_revision = "0004_ranking_genre"
branch_labels = None
depends_on = None

_TABLES = ("app_trending_scores", "app_blowing_up_scores")


def upgrade() -> None:
    for tbl in _TABLES:
        op.execute(text(
            f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS country VARCHAR(2) NOT NULL DEFAULT 'us'"
        ))
        # Rebuild the primary key as composite (app_id, country). DROP is
        # idempotent; the table is precomputed cache data so this is safe.
        op.execute(text(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {tbl}_pkey"))
        op.execute(text(f"ALTER TABLE {tbl} ADD CONSTRAINT {tbl}_pkey PRIMARY KEY (app_id, country)"))


def downgrade() -> None:
    for tbl in _TABLES:
        op.execute(text(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {tbl}_pkey"))
        op.execute(text(f"ALTER TABLE {tbl} ADD CONSTRAINT {tbl}_pkey PRIMARY KEY (app_id)"))
        op.execute(text(f"ALTER TABLE {tbl} DROP COLUMN IF EXISTS country"))
