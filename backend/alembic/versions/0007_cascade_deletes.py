"""cascade deletes for app and keyword child tables

Adds ON DELETE CASCADE to foreign keys that previously defaulted to
NO ACTION. This lets deleting an app or keyword cleanly remove its
derived rows without manual cleanup, and avoids FK-violation errors.

Tables touched:
  rankings, reviews, app_versions, app_analytics,
  app_keywords, opportunities, app_market_weakness,
  feature_gaps, keyword_trends

Revision ID: 0007_cascade_deletes
Revises: 0006_billing_provider
"""
from alembic import op
from sqlalchemy import text

revision = "0007_cascade_deletes"
down_revision = "0006_billing_provider"
branch_labels = None
depends_on = None


# FKs to recreate with ON DELETE CASCADE.
# Format: (table_name, column_name, referenced_table)
_CASCADE_FKS = [
    ("rankings", "app_id", "apps"),
    ("reviews", "app_id", "apps"),
    ("app_versions", "app_id", "apps"),
    ("app_analytics", "app_id", "apps"),
    ("app_keywords", "app_id", "apps"),
    ("app_keywords", "keyword_id", "keywords"),
    ("opportunities", "app_id", "apps"),
    ("app_market_weakness", "app_id", "apps"),
    ("feature_gaps", "app_id", "apps"),
    ("keyword_trends", "keyword_id", "keywords"),
]


def _upgrade_table(table: str, column: str, ref_table: str) -> None:
    """Drop the existing FK (if any) and add it back with ON DELETE CASCADE."""
    op.execute(text(
        f"""
        DO $$
        DECLARE
            con_name text;
        BEGIN
            SELECT tc.constraint_name INTO con_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = '{table}'
              AND kcu.column_name = '{column}'
            LIMIT 1;

            IF con_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', con_name);
            END IF;
        END $$;
        """
    ))
    op.execute(text(
        f"""
        ALTER TABLE {table}
        ADD CONSTRAINT {table}_{column}_fkey
        FOREIGN KEY ({column}) REFERENCES {ref_table}(id)
        ON DELETE CASCADE
        """
    ))


def _downgrade_table(table: str, column: str, ref_table: str) -> None:
    """Revert the FK to ON DELETE NO ACTION (the pre-migration default)."""
    op.execute(text(
        f"""
        ALTER TABLE {table}
        DROP CONSTRAINT IF EXISTS {table}_{column}_fkey
        """
    ))
    op.execute(text(
        f"""
        ALTER TABLE {table}
        ADD CONSTRAINT {table}_{column}_fkey
        FOREIGN KEY ({column}) REFERENCES {ref_table}(id)
        """
    ))


def upgrade() -> None:
    for table, column, ref_table in _CASCADE_FKS:
        _upgrade_table(table, column, ref_table)


def downgrade() -> None:
    for table, column, ref_table in _CASCADE_FKS:
        _downgrade_table(table, column, ref_table)
