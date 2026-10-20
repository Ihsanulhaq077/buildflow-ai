"""
Phase 8 - AI Assistant tables.

Creates:
- chat_sessions
- chat_messages
- tool_calls
"""
from alembic import op
import sqlalchemy as sa
import uuid as uuid_module


# revision identifiers, used by Alembic.
revision = "0008_phase_8_ai_assistant"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=True, default=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("session_id", sa.Uuid, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=True, default="user"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("tool_call_id", sa.String(100), nullable=True),
        sa.Column("message_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("session_id", sa.Uuid, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("message_id", sa.Uuid, sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("arguments", sa.JSON, nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=True, default="pending"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True, default=0),
    )


def downgrade():
    op.drop_table("tool_calls")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")