"""Phase 12 - Commercial tables.

Creates:
- subscriptions
- onboarding_progress
- billing_info
- system_events
"""
from alembic import op
import sqlalchemy as sa
import uuid as uuid_module


# revision identifiers, used by Alembic.
revision = "0012_phase_12_commercial"
down_revision = "0011_phase_11_cv"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monthly_limit", sa.Integer, nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_subscription_org"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "onboarding_progress",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("current_step", sa.String(30), nullable=False),
        sa.Column("completed_steps", sa.Text, nullable=False),
        sa.Column("step_data", sa.Text, nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_onboarding_org"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "billing_info",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("card_last4", sa.String(4), nullable=True),
        sa.Column("billing_email", sa.String(255), nullable=False),
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("is_valid", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("metadata", sa.Text, nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("system_events")
    op.drop_table("billing_info")
    op.drop_table("onboarding_progress")
    op.drop_table("subscriptions")