"""countries reference table + rankings.country dimension

Adds the country-priority reference table (``countries``) and the per-storefront
dimension on ``rankings``, seeding the high-value storefronts with tuned
tier / weight / SLA. Long-tail storefronts are auto-registered as tier 4 by the
acquisition layer later, so this seed only carries the countries that need
elevated priority.

Uses idempotent DDL (IF NOT EXISTS) per this project's migration convention, so
it is safe on a fresh database where the baseline's create_all may already have
built the ``countries`` table / ``rankings.country`` column.

Revision ID: 0002_countries
Revises: 0001_baseline
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0002_countries"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

_DDL = [
    """CREATE TABLE IF NOT EXISTS countries (
        code        VARCHAR(2) PRIMARY KEY,
        name        VARCHAR(100) NOT NULL,
        tier        INTEGER NOT NULL DEFAULT 4,
        weight      DOUBLE PRECISION NOT NULL DEFAULT 0.1,
        sla_hours   INTEGER NOT NULL DEFAULT 720,
        enabled     BOOLEAN NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )""",
    "ALTER TABLE rankings ADD COLUMN IF NOT EXISTS country VARCHAR(2) NOT NULL DEFAULT 'us'",
    "CREATE INDEX IF NOT EXISTS idx_ranking_country_chart_date "
    "ON rankings (country, chart_type, recorded_at)",
]

# (tier, weight, sla_hours) -> [(code, name), ...]
# High-value storefronts only; everything else defaults to tier 4 on first sight.
_SEED = {
    (1, 1.0, 12): [
        ("us", "United States"), ("cn", "China"), ("jp", "Japan"),
        ("gb", "United Kingdom"), ("de", "Germany"), ("kr", "South Korea"),
        ("fr", "France"), ("ca", "Canada"), ("au", "Australia"), ("tw", "Taiwan"),
    ],
    (2, 0.5, 72): [
        ("it", "Italy"), ("es", "Spain"), ("nl", "Netherlands"), ("br", "Brazil"),
        ("in", "India"), ("mx", "Mexico"), ("tr", "Turkey"), ("sa", "Saudi Arabia"),
        ("se", "Sweden"), ("ch", "Switzerland"), ("hk", "Hong Kong"),
        ("sg", "Singapore"), ("ae", "United Arab Emirates"), ("th", "Thailand"),
        ("id", "Indonesia"), ("pl", "Poland"), ("ru", "Russia"), ("be", "Belgium"),
        ("at", "Austria"), ("no", "Norway"), ("dk", "Denmark"), ("fi", "Finland"),
        ("ie", "Ireland"),
    ],
    (3, 0.25, 240): [
        ("pt", "Portugal"), ("gr", "Greece"), ("cz", "Czechia"), ("hu", "Hungary"),
        ("ro", "Romania"), ("il", "Israel"), ("za", "South Africa"),
        ("ar", "Argentina"), ("cl", "Chile"), ("co", "Colombia"), ("my", "Malaysia"),
        ("ph", "Philippines"), ("vn", "Vietnam"), ("nz", "New Zealand"),
        ("ua", "Ukraine"), ("eg", "Egypt"), ("ng", "Nigeria"), ("pk", "Pakistan"),
        ("kz", "Kazakhstan"), ("qa", "Qatar"), ("kw", "Kuwait"), ("ec", "Ecuador"),
        ("pe", "Peru"), ("ma", "Morocco"), ("sk", "Slovakia"),
    ],
}


def upgrade() -> None:
    conn = op.get_bind()
    for sql in _DDL:
        conn.execute(text(sql))
    # Seed high-value storefronts (idempotent; existing rows are left untouched).
    stmt = text(
        "INSERT INTO countries (code, name, tier, weight, sla_hours, enabled) "
        "VALUES (:code, :name, :tier, :weight, :sla, TRUE) "
        "ON CONFLICT (code) DO NOTHING"
    )
    for (tier, weight, sla), rows in _SEED.items():
        for code, name in rows:
            conn.execute(stmt, {"code": code, "name": name, "tier": tier,
                                "weight": weight, "sla": sla})


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ranking_country_chart_date")
    op.execute("ALTER TABLE rankings DROP COLUMN IF EXISTS country")
    op.execute("DROP TABLE IF EXISTS countries")
