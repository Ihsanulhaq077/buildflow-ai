"""
Phase 9 - Dashboards tables.

Creates:
- dashboards
- widgets
- dashboard_permissions
"""
from alembic import op
import sqlalchemy as sa
import uuid as uuid_module


# revision identifiers, used by Alembic.
revision = "0009_phase_9_dashboards"
down_revision = "0008_phase_8_ai_assistant"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dashboards",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("dashboard_type", sa.String(20), nullable=True, default="CUSTOM"),
        sa.Column("target_role", sa.String(50), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=True, default=False),
        sa.Column("is_default", sa.Boolean, nullable=True, default=False),
        sa.Column("layout_config", sa.JSON, nullable=True),
        sa.Column("refresh_interval", sa.Integer, nullable=True, default=300),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "widgets",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dashboard_id", sa.Uuid, sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("widget_type", sa.String(20), nullable=False),
        sa.Column("data_source", sa.String(100), nullable=False),
        sa.Column("chart_type", sa.String(20), nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("width", sa.Integer, nullable=True, default=6),
        sa.Column("height", sa.Integer, nullable=True, default=4),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("filters", sa.JSON, nullable=True),
        sa.Column("refresh_interval", sa.Integer, nullable=True),
        sa.Column("is_visible", sa.Boolean, nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "dashboard_permissions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dashboard_id", sa.Uuid, sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), index=True, nullable=True),
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("roles.id"), index=True, nullable=True),
        sa.Column("can_view", sa.Boolean, nullable=True, default=True),
        sa.Column("can_edit", sa.Boolean, nullable=True, default=False),
        sa.Column("can_share", sa.Boolean, nullable=True, default=False),
        sa.Column("granted_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("dashboard_permissions")
    op.drop_table("widgets")
    op.drop_table("dashboards")