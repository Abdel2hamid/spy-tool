"""rankings.genre — chart scope (overall vs per-genre)

Distinguishes an overall (all-genres) chart rank from a within-genre chart rank
so per-genre top charts can be stored and queried. 'all' = overall.

Idempotent DDL per project convention.

Revision ID: 0004_ranking_genre
Revises: 0003_country_coverage
"""
from alembic import op
from sqlalchemy import text

revision = "0004_ranking_genre"
down_revision = "0003_country_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE rankings ADD COLUMN IF NOT EXISTS genre VARCHAR(40) NOT NULL DEFAULT 'all'"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_ranking_cc_chart_genre_date "
        "ON rankings (country, chart_type, genre, recorded_at)"
    ))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ranking_cc_chart_genre_date")
    op.execute("ALTER TABLE rankings DROP COLUMN IF EXISTS genre")
