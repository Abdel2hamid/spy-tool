"""provider-agnostic billing identity on subscriptions

Generalises the Stripe-specific billing columns so any payment gateway
(Stripe today, Airwallex next) can back a subscription. Adds `provider`,
`provider_customer_id`, `provider_subscription_id` and backfills them from the
legacy `stripe_*` columns (which are retained transitionally).

Revision ID: 0006_billing_provider
Revises: 0005_score_country
"""
from alembic import op
from sqlalchemy import text

revision = "0006_billing_provider"
down_revision = "0005_score_country"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider VARCHAR(30) NOT NULL DEFAULT 'stripe'"
    ))
    op.execute(text(
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider_customer_id VARCHAR(255)"
    ))
    op.execute(text(
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider_subscription_id VARCHAR(255)"
    ))
    # Backfill from the legacy Stripe columns.
    op.execute(text(
        "UPDATE subscriptions SET provider_customer_id = stripe_customer_id "
        "WHERE provider_customer_id IS NULL AND stripe_customer_id IS NOT NULL"
    ))
    op.execute(text(
        "UPDATE subscriptions SET provider_subscription_id = stripe_subscription_id "
        "WHERE provider_subscription_id IS NULL AND stripe_subscription_id IS NOT NULL"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_sub_provider_customer "
        "ON subscriptions (provider, provider_customer_id)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS idx_sub_provider_customer"))
    op.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS provider_subscription_id"))
    op.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS provider_customer_id"))
    op.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS provider"))
