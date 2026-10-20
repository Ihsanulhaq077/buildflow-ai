"""
Phase 13 - Role-scoped tasks and accountant expenses.

Creates:
- tasks
- expenses

Also:
- adds the missing `dashboards.is_active` column (present in the dev database but never
  created by migration 0009, so a fresh `alembic upgrade head` produced a broken schema)
- seeds the new dashboard/task/expense permission codes and grants them to existing
  roles according to `app.rbac.DEFAULT_ROLES`
"""
import uuid

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0013_phase_13_tasks_expenses"
down_revision = "0012_phase_12_commercial"
branch_labels = None
depends_on = None


NEW_PERMISSIONS = {
    "dashboards.read": "View dashboards",
    "dashboards.manage": "Create/edit/delete dashboards and widgets",
    "tasks.read": "View tasks",
    "tasks.manage": "Create/update/delete tasks",
    "expenses.read": "View expenses",
    "expenses.manage": "Create/update/delete expenses",
}

# Roles that get which new permissions. Mirrors app.rbac.DEFAULT_ROLES.
ROLE_GRANTS = {
    "OWNER": list(NEW_PERMISSIONS),
    "PROJECT_MANAGER": ["dashboards.read", "dashboards.manage", "tasks.read", "tasks.manage"],
    "SITE_ENGINEER": ["dashboards.read", "tasks.read", "tasks.manage"],
    "FOREMAN": ["dashboards.read", "tasks.read", "tasks.manage"],
    "WORKER": ["dashboards.read", "tasks.read"],
    "STOREKEEPER": ["dashboards.read", "tasks.read", "tasks.manage"],
    "PROCUREMENT_OFFICER": ["dashboards.read", "dashboards.manage", "tasks.read", "tasks.manage"],
    "ACCOUNTANT": ["dashboards.read", "dashboards.manage", "tasks.read", "tasks.manage",
                   "expenses.read", "expenses.manage"],
    "HR_ADMIN": ["dashboards.read", "tasks.read", "tasks.manage"],
    "SUBCONTRACTOR": ["dashboards.read", "tasks.read"],
    "CLIENT": ["dashboards.read"],
}


def _create_tasks():
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("dashboard_id", sa.Uuid, sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("target_role", sa.String(50), nullable=True, index=True),
        sa.Column("assigned_to", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="TODO"),
        sa.Column("priority", sa.String(20), nullable=False, default="MEDIUM"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("created_by", sa.Uuid, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def _create_expenses():
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("cost_code_id", sa.Uuid, sa.ForeignKey("cost_codes.id"), nullable=True, index=True),
        sa.Column("expense_no", sa.String(30), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, default="OTHER"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column("expense_date", sa.Date, nullable=False),
        sa.Column("vendor", sa.String(200), nullable=True),
        sa.Column("reference_no", sa.String(100), nullable=True),
        sa.Column("payment_method", sa.String(30), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="DRAFT"),
        sa.Column("is_billable", sa.Boolean, nullable=False, default=False),
        sa.Column("created_by", sa.Uuid, nullable=True),
        sa.Column("decided_by", sa.Uuid, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def _fix_dashboards_table(bind, inspector):
    """`dashboards.is_active` is required by the model (soft delete) but was never created by
    migration 0009. Add it where missing so fresh databases match the models."""
    if "dashboards" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("dashboards")}
    if "is_active" not in cols:
        op.add_column("dashboards", sa.Column("is_active", sa.Boolean, nullable=True, default=True))
        bind.execute(sa.text("UPDATE dashboards SET is_active = 1 WHERE is_active IS NULL"))
    if "created_by" not in cols:
        op.add_column("dashboards", sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True))


def _seed_permissions(bind):
    """Seed the new permission codes and grant them to roles that already exist."""
    for code, description in NEW_PERMISSIONS.items():
        perm = bind.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}).first()
        if perm is None:
            bind.execute(sa.text(
                "INSERT INTO permissions (id, code, description, created_at, updated_at) "
                "VALUES (:id, :code, :desc, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {"id": str(uuid.uuid4()), "code": code, "desc": description})
        else:
            bind.execute(sa.text("UPDATE permissions SET description = :d WHERE code = :c"),
                         {"d": description, "c": code})

    for role_name, codes in ROLE_GRANTS.items():
        roles = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :n"), {"n": role_name}).fetchall()
        for (role_id,) in roles:
            for code in codes:
                perm = bind.execute(
                    sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}).first()
                if perm is None:
                    continue
                exists = bind.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :r AND permission_id = :p"),
                    {"r": str(role_id), "p": str(perm[0])}).first()
                if not exists:
                    bind.execute(sa.text(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) "
                        "VALUES (:r, :p)"), {"r": str(role_id), "p": str(perm[0])})


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "tasks" not in existing:
        _create_tasks()
    if "expenses" not in existing:
        _create_expenses()

    _fix_dashboards_table(bind, sa.inspect(bind))
    _seed_permissions(bind)


def downgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "expenses" in existing:
        op.drop_table("expenses")
    if "tasks" in existing:
        op.drop_table("tasks")
