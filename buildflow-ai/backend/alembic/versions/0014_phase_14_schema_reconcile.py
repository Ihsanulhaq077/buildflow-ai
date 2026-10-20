"""
Phase 14 - Schema reconciliation.

Several tables drift between models and migrations. On a fresh database ``alembic upgrade head``
would leave a broken schema (missing columns, wrong column names, and missing tables for the
documents/rag subsystem). This migration reconciles every drift so the whole app boots.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_phase_14_schema_reconcile"
down_revision = "0013_phase_13_tasks_expenses"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    """Re-inspect on every call so callers never act on stale column lists."""
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add_missing_timestamps(table: str) -> None:
    """BaseMixin gives every model created_at/updated_at; add whichever the table lacks."""
    if table not in _table_names():
        return
    cols = _columns(table)
    for name in ("created_at", "updated_at"):
        if name not in cols:
            op.add_column(table, sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def _rename_column(table: str, old: str, new: str) -> None:
    """Rename a column if the old name is present and the new one is not."""
    if table not in _table_names():
        return
    cols = _columns(table)
    if old in cols and new not in cols:
        op.get_bind().execute(sa.text(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}"))


def upgrade():
    insp = sa.inspect(op.get_bind())

    # --- widgets: missing updated_at (model inherits BaseMixin) ---
    if "widgets" in insp.get_table_names():
        if "updated_at" not in _columns("widgets"):
            op.add_column("widgets", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # --- dashboard_permissions: DB has granted_at, model uses created_at/updated_at ---
    if "dashboard_permissions" in insp.get_table_names():
        _add_missing_timestamps("dashboard_permissions")

    # --- system_events: DB column is "metadata", model is event_metadata ---
    if "system_events" in insp.get_table_names():
        _rename_column("system_events", "metadata", "event_metadata")
        _add_missing_timestamps("system_events")

    # --- forecasts: DB column is "metadata", model is forecast_metadata ---
    if "forecasts" in insp.get_table_names():
        _rename_column("forecasts", "metadata", "forecast_metadata")
        if "forecast_metadata" not in _columns("forecasts"):
            op.add_column("forecasts", sa.Column("forecast_metadata", sa.Text, nullable=True))

    # --- chat_messages / tool_calls: missing updated_at (BaseMixin) ---
    for table in ("chat_messages", "tool_calls"):
        if table in insp.get_table_names():
            _add_missing_timestamps(table)

    # --- missing tables for the documents/rag subsystem ---
    if "documents" not in _table_names():
        op.create_table(
            "documents",
            sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=True, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_type", sa.String(20), nullable=False),
            sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
            sa.Column("mime_type", sa.String(255), nullable=True),
            sa.Column("storage_path", sa.String(500), nullable=False),
            sa.Column("blob_key", sa.String(500), nullable=True),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(30), nullable=False, server_default="UPLOADED"),
            sa.Column("tags", sa.Text, nullable=True),
            sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "doc_versions" not in _table_names():
        op.create_table(
            "doc_versions",
            sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
            sa.Column("storage_path", sa.String(500), nullable=False),
            sa.Column("etag", sa.String(128), nullable=True),
            sa.Column("text", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "doc_access_policies" not in _table_names():
        op.create_table(
            "doc_access_policies",
            sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("can_read", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("can_write", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("granted_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "doc_chunks" not in _table_names():
        op.create_table(
            "doc_chunks",
            sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("doc_id", sa.Uuid, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("chunk_index", sa.Integer, nullable=False),
            sa.Column("text", sa.Text, nullable=False),
            sa.Column("char_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("page", sa.Integer, nullable=True),
            # Postgres stores vectors as an array; SQLite (dev) uses a JSON array.
            sa.Column("embedding", sa.JSON, nullable=True),
            sa.Column("token_estimate", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("doc_id", "chunk_index", name="uq_doc_chunk_index"),
        )


def downgrade():
    for table in ("doc_chunks", "doc_access_policies", "doc_versions", "documents"):
        if table in _table_names():
            op.drop_table(table)
