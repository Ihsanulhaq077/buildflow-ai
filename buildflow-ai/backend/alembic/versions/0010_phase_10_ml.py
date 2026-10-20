"""Phase 10 - ML forecasting tables.

Creates:
- forecasts
- model_metadata
"""
from alembic import op
import sqlalchemy as sa
import uuid as uuid_module


# revision identifiers, used by Alembic.
revision = "0010_phase_10_ml"
down_revision = "0009_phase_9_dashboards"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("forecast_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("predicted_value", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("lower_bound", sa.Float, nullable=True),
        sa.Column("upper_bound", sa.Float, nullable=True),
        sa.Column("metadata", sa.Text, nullable=True, default="{}"),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "model_metadata",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("features", sa.Text, nullable=True, default="{}"),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("model_metadata")
    op.drop_table("forecasts")