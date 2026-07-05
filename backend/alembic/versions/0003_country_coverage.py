"""countries.charts_last_covered_at — per-country coverage tracking

Adds the timestamp that drives SLA-weighted top-charts rotation: a storefront
becomes "due" once `now - charts_last_covered_at > sla_hours`, and the
country_charts job picks the most-overdue storefronts each run so high tiers
refresh often and the long tail never starves.

Idempotent DDL per project convention.

Revision ID: 0003_country_coverage
Revises: 0002_countries
"""
from alembic import op
from sqlalchemy import text

revision = "0003_country_coverage"
down_revision = "0002_countries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE countries ADD COLUMN IF NOT EXISTS charts_last_covered_at TIMESTAMPTZ"
    ))


def downgrade() -> None:
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS charts_last_covered_at")
