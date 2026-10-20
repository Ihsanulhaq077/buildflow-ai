"""Data purge service - remove manually entered data for an organization.

Two scopes are supported:

``operational``
    Everything the organization produced while using the app: projects, BOQs, budgets,
    purchases, receipts, labour, site reports, documents, tasks, expenses, AI chats and
    forecasts. Master data (clients, sites, suppliers, workers, cost codes, units) and the
    account itself (organization, users, roles, dashboards) are left alone.

``all``
    As above, plus the master data. The organization, its users, its roles and the role
    dashboards survive so the account stays usable.

The purge is destructive and irreversible, so the caller must confirm with the exact
confirmation phrase.
"""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import User

# Confirmation phrase the caller must send back.
CONFIRMATION_PHRASE = "DELETE MY DATA"

# Operational data: produced while running the app.
OPERATIONAL_TABLES: tuple[str, ...] = (
    "daily_log_progress",
    "daily_logs",
    "attendance_entries",
    "attendance_sheets",
    "workers",
    "material_issue_lines",
    "material_issues",
    "stock_transactions",
    "stock_balances",
    "grn_lines",
    "goods_receipts",
    "po_lines",
    "purchase_orders",
    "quote_lines",
    "supplier_quotes",
    "requisition_lines",
    "purchase_requisitions",
    "budget_revisions",
    "budget_lines",
    "budgets",
    "boq_items",
    "boqs",
    "contracts",
    "detection_results",
    "site_photos",
    "forecasts",
    "model_metadata",
    "expenses",
    "tasks",
    "ppe_registrations",
    "onboarding_progress",
    "chat_messages",
    "tool_calls",
    "chat_sessions",
    "system_events",
    "doc_chunks",
    "doc_versions",
    "doc_access_policies",
    "documents",
)

# Master data: reference lists the organization maintains by hand.
MASTER_TABLES: tuple[str, ...] = (
    "inventory_items",
    "warehouses",
    "units",
    "unit_conversions",
    "cost_codes",
    "sites",
    "clients",
    "suppliers",
    "projects",
)

# Never purged, whatever the scope: the account itself and the RBAC scaffolding.
PROTECTED_TABLES: tuple[str, ...] = (
    "organizations",
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "audit_logs",
    "dashboards",
    "widgets",
    "dashboard_permissions",
    "billing_info",
    "subscriptions",
)


class PurgeService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.org_id = user.organization_id

    @property
    def org_key(self) -> str:
        """The organization id as a plain string, which is what the Uuid columns bind."""
        return str(self.org_id)

    def _org_value(self, column):
        """The org id in the form this column's type expects.

        Most tables use ``Uuid(as_uuid=True)`` and want a real ``uuid.UUID``; the ML tables
        use a Postgres ``UUID(as_uuid=False)`` and want a string.
        """
        as_uuid = getattr(column.type, "as_uuid", True)
        return self.org_id if as_uuid else str(self.org_id)

    def _org_scoped_tables(self) -> list[str]:
        """Tables that carry an organization_id column."""
        from app.models import Base
        out = []
        for name in Base.metadata.tables:
            cols = Base.metadata.tables[name].columns
            if "organization_id" in cols:
                out.append(name)
        return out

    def inventory(self) -> dict:
        """Row counts per table for this organization, so the UI can show what will go."""
        from app.models import Base

        counts: dict[str, int] = {}
        for name in self._org_scoped_tables():
            table = Base.metadata.tables[name]
            stmt = select(func.count()).select_from(table).where(
                table.c.organization_id == self._org_value(table.c.organization_id))
            counts[name] = self.db.scalar(stmt) or 0
        return counts

    def preview(self, scope: str = "operational") -> dict:
        """What a purge at this scope would remove."""
        counts = self.inventory()
        targets = self._targets(scope)
        will_delete = {t: counts.get(t, 0) for t in targets}
        kept = {t: counts.get(t, 0) for t in counts if t not in targets}
        return {
            "scope": scope,
            "tables_to_delete": will_delete,
            "tables_to_keep": kept,
            "total_rows_to_delete": sum(will_delete.values()),
        }

    def _targets(self, scope: str) -> list[str]:
        if scope == "all":
            tables = list(OPERATIONAL_TABLES) + list(MASTER_TABLES)
        elif scope == "operational":
            tables = list(OPERATIONAL_TABLES)
        else:
            raise ValueError(f"Unknown scope '{scope}'")
        # Never touch protected tables, even if a name collides.
        return [t for t in tables if t not in PROTECTED_TABLES]

    def purge(self, scope: str = "operational", confirmation: str = "") -> dict:
        """Delete the organization's data. Requires the exact confirmation phrase."""
        if confirmation != CONFIRMATION_PHRASE:
            raise ValueError(f"Confirmation phrase must be exactly '{CONFIRMATION_PHRASE}'")

        from app.models import Base

        targets = self._targets(scope)
        deleted: dict[str, int] = {}

        # Delete children first: they reference org-owned rows but carry no org column.
        child_parents = {
            "chat_messages": ("chat_sessions", "session_id"),
            "tool_calls": ("chat_sessions", "session_id"),
            "doc_chunks": ("documents", "doc_id"),
            "doc_versions": ("documents", "document_id"),
            "doc_access_policies": ("documents", "document_id"),
        }
        for name, (parent, parent_col) in child_parents.items():
            if name not in targets:
                continue
            parent_ids = list(self.db.scalars(
                select(Base.metadata.tables[parent].c.id).where(
                    Base.metadata.tables[parent].c.organization_id ==
                    self._org_value(
                        Base.metadata.tables[parent].c.organization_id))))
            if not parent_ids:
                continue
            table = Base.metadata.tables[name]
            result = self.db.execute(delete(table).where(table.c[parent_col].in_(parent_ids)))
            deleted[name] = result.rowcount or 0

        # Now the org-scoped tables themselves.
        for name in targets:
            if name in child_parents:
                continue
            table = Base.metadata.tables.get(name)
            if table is None or "organization_id" not in table.c:
                continue
            result = self.db.execute(
                delete(table).where(table.c.organization_id ==
                                    self._org_value(table.c.organization_id)))
            deleted[name] = result.rowcount or 0

        self.db.commit()
        return {
            "scope": scope,
            "deleted": {k: v for k, v in deleted.items() if v},
            "total_rows_deleted": sum(deleted.values()),
        }
