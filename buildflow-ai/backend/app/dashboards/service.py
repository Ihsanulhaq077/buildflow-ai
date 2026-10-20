"""Dashboards service - data aggregation and analytics."""
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import User
from app.dashboards.models import Dashboard, DashboardPermission, Widget

log = logging.getLogger("buildflow.dashboards")


class DashboardService:
    """Manage dashboards and widgets.

    Dashboards are visible to a user when they are:
      * targeted at the user's role (``target_role``),
      * public,
      * created by the user, or
      * explicitly granted through ``DashboardPermission``.

    An OWNER sees every dashboard in the organization.
    """

    def __init__(self, db: Session, org_id: uuid.UUID | str, user: User):
        self.db = db
        self.org_id = uuid.UUID(str(org_id))
        self.user = user

    @property
    def _is_owner(self) -> bool:
        return bool(self.user.role and self.user.role.name == "OWNER")

    @property
    def _role_name(self) -> Optional[str]:
        return self.user.role.name if self.user.role else None

    def _visibility_clause(self):
        """SQL clause restricting dashboards to those this user may see."""
        if self._is_owner:
            return None
        granted = select(DashboardPermission.dashboard_id).where(
            DashboardPermission.can_view.is_(True),
            or_(
                DashboardPermission.role_id == self.user.role_id,
                DashboardPermission.user_id == self.user.id,
            ),
        )
        return or_(
            Dashboard.target_role == self._role_name,
            Dashboard.is_public.is_(True),
            Dashboard.created_by == self.user.id,
            Dashboard.id.in_(granted),
        )

    # --- Dashboard CRUD ---

    def create_dashboard(self, data: dict) -> Dashboard:
        """Create a new dashboard."""
        dashboard = Dashboard(
            organization_id=self.org_id,
            name=data.get("name", "New Dashboard"),
            description=data.get("description", ""),
            dashboard_type=data.get("dashboard_type", "CUSTOM"),
            target_role=data.get("target_role"),
            layout_config=data.get("layout_config", {}),
            refresh_interval=data.get("refresh_interval", 300),
            is_default=data.get("is_default", False),
            is_public=data.get("is_public", False),
            created_by=self.user.id,
        )
        self.db.add(dashboard)
        self.db.commit()
        return dashboard

    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get a dashboard by ID, honouring role visibility."""
        try:
            dash_id = uuid.UUID(str(dashboard_id))
        except (ValueError, AttributeError, TypeError):
            return None
        stmt = select(Dashboard).where(
            Dashboard.id == dash_id,
            Dashboard.organization_id == self.org_id,
            Dashboard.is_active.is_(True),
        )
        clause = self._visibility_clause()
        if clause is not None:
            stmt = stmt.where(clause)
        return self.db.scalar(stmt)

    def list_dashboards(
        self,
        limit: int = 50,
        offset: int = 0,
        dashboard_type: Optional[str] = None,
        is_default: Optional[bool] = None,
        target_role: Optional[str] = None,
        include_all: bool = False,
    ) -> List[Dashboard]:
        """List dashboards visible to the caller.

        ``include_all`` returns every dashboard in the organization instead of just the
        ones this user's role can see.
        """
        stmt = select(Dashboard).where(
            Dashboard.organization_id == self.org_id,
            Dashboard.is_active.is_(True),
        )
        if not include_all:
            clause = self._visibility_clause()
            if clause is not None:
                stmt = stmt.where(clause)
        if dashboard_type:
            stmt = stmt.where(Dashboard.dashboard_type == dashboard_type)
        if is_default is not None:
            stmt = stmt.where(Dashboard.is_default == is_default)
        if target_role:
            stmt = stmt.where(Dashboard.target_role == target_role)
        stmt = stmt.order_by(Dashboard.created_at.desc()).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    def get_default_dashboard(self, role_name: Optional[str] = None) -> Optional[Dashboard]:
        """The dashboard a user lands on: their role's default, else any role dashboard,
        else any public default, else the first visible one."""
        role = role_name or self._role_name
        stmt = select(Dashboard).where(
            Dashboard.organization_id == self.org_id,
            Dashboard.is_active.is_(True),
        )
        if not self._is_owner:
            clause = self._visibility_clause()
            if clause is not None:
                stmt = stmt.where(clause)
        rows = list(self.db.scalars(stmt.order_by(
            Dashboard.is_default.desc(), Dashboard.created_at.desc())))
        if not rows:
            return None
        for d in rows:
            if d.target_role == role and d.is_default:
                return d
        for d in rows:
            if d.target_role == role:
                return d
        for d in rows:
            if d.is_default:
                return d
        return rows[0]

    def update_dashboard(self, dashboard_id: str, data: dict) -> Optional[Dashboard]:
        """Update a dashboard."""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return None
        for key, value in data.items():
            if hasattr(dashboard, key):
                setattr(dashboard, key, value)
        self.db.commit()
        return dashboard

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Soft-delete a dashboard."""
        dashboard = self.get_dashboard(dashboard_id)
        if dashboard:
            dashboard.is_active = False
            self.db.commit()
            return True
        return False

    # --- Widget CRUD ---

    def add_widget(self, dashboard_id: str, data: dict) -> Widget:
        """Add a widget to a dashboard."""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        widget = Widget(
            dashboard_id=dashboard.id,
            title=data.get("title", "New Widget"),
            widget_type=data.get("widget_type", "METRIC"),
            data_source=data.get("data_source", ""),
            chart_type=data.get("chart_type"),
            position=data.get("position", 0),
            width=data.get("width", 6),
            height=data.get("height", 4),
            config=data.get("config", {}),
            filters=data.get("filters", {}),
            refresh_interval=data.get("refresh_interval"),
            is_visible=data.get("is_visible", True),
        )
        self.db.add(widget)
        self.db.commit()
        return widget

    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get a widget by ID."""
        try:
            wid = uuid.UUID(str(widget_id))
        except (ValueError, AttributeError, TypeError):
            return None
        stmt = select(Widget).where(
            Widget.id == wid,
            Widget.dashboard_id.in_(
                select(Dashboard.id).where(
                    Dashboard.organization_id == self.org_id
                )
            )
        )
        return self.db.scalar(stmt)

    def update_widget(self, widget_id: str, data: dict) -> Optional[Widget]:
        """Update a widget."""
        widget = self.get_widget(widget_id)
        if not widget:
            return None
        for key, value in data.items():
            if hasattr(widget, key):
                setattr(widget, key, value)
        self.db.commit()
        return widget

    def delete_widget(self, widget_id: str) -> bool:
        """Delete a widget."""
        widget = self.get_widget(widget_id)
        if widget:
            self.db.delete(widget)
            self.db.commit()
            return True
        return False

    def list_widgets(self, dashboard_id: str) -> List[Widget]:
        """List widgets for a dashboard."""
        try:
            dash_id = uuid.UUID(str(dashboard_id))
        except (ValueError, AttributeError, TypeError):
            return []
        stmt = select(Widget).where(
            Widget.dashboard_id == dash_id,
            Widget.is_visible.is_(True)
        ).order_by(Widget.position)
        return self.db.scalars(stmt).all()


class DashboardDataService:
    """Aggregate data for dashboard widgets."""

    def __init__(self, db: Session, org_id: uuid.UUID | str):
        self.db = db
        self.org_id = uuid.UUID(str(org_id))

    def get_project_summary(self) -> Dict:
        """Get project summary for dashboards."""
        from app.projects.models import Project

        stmt = select(func.count(Project.id)).where(
            Project.organization_id == self.org_id,
            Project.deleted_at.is_(None)
        )
        total = self.db.scalar(stmt) or 0

        stmt = select(func.count(Project.id)).where(
            Project.organization_id == self.org_id,
            Project.deleted_at.is_(None),
            Project.status.in_(["ACTIVE", "APPROVED"])
        )
        active = self.db.scalar(stmt) or 0

        return {"total_projects": total, "active_projects": active}

    def get_budget_summary(self) -> Dict:
        """Get budget summary for dashboards."""
        from app.budgets.models import Budget, BudgetLine

        stmt = select(func.count(Budget.id)).where(
            Budget.organization_id == self.org_id
        )
        total = self.db.scalar(stmt) or 0

        revised = self.db.scalar(
            select(func.coalesce(func.sum(BudgetLine.revised_amount), 0)).where(
                BudgetLine.organization_id == self.org_id))
        actual = self.db.scalar(
            select(func.coalesce(func.sum(BudgetLine.actual_amount), 0)).where(
                BudgetLine.organization_id == self.org_id))
        committed = self.db.scalar(
            select(func.coalesce(func.sum(BudgetLine.committed_amount), 0)).where(
                BudgetLine.organization_id == self.org_id))
        return {"total_budgets": total, "revised_amount": revised, "actual_amount": actual,
                "committed_amount": committed}

    def get_procurement_summary(self) -> Dict:
        """Get procurement summary for dashboards."""
        from app.procurement.models import PurchaseRequisition

        stmt = select(func.count(PurchaseRequisition.id)).where(
            PurchaseRequisition.organization_id == self.org_id
        )
        total = self.db.scalar(stmt) or 0

        pending = self.db.scalar(
            select(func.count(PurchaseRequisition.id)).where(
                PurchaseRequisition.organization_id == self.org_id,
                PurchaseRequisition.status == "SUBMITTED"))

        return {"total_requisitions": total, "pending_requisitions": pending}

    def get_inventory_summary(self) -> Dict:
        """Get inventory summary for dashboards."""
        from app.inventory.models import InventoryItem, StockBalance

        total = self.db.scalar(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.organization_id == self.org_id)) or 0

        qty = self.db.scalar(
            select(func.coalesce(func.sum(StockBalance.quantity), 0)).where(
                StockBalance.organization_id == self.org_id)) or 0

        below = 0
        for b in self.db.scalars(select(StockBalance).where(
                StockBalance.organization_id == self.org_id)):
            item = self.db.get(InventoryItem, b.item_id)
            if item and item.reorder_level and b.quantity <= item.reorder_level:
                below += 1

        return {"total_items": total, "total_quantity": qty, "below_reorder": below}

    def get_labour_summary(self) -> Dict:
        """Get labour summary for dashboards."""
        from app.labour.models import AttendanceSheet, Worker

        sheets = self.db.scalar(
            select(func.count(AttendanceSheet.id)).where(
                AttendanceSheet.organization_id == self.org_id)) or 0

        workers = self.db.scalar(
            select(func.count(Worker.id)).where(
                Worker.organization_id == self.org_id,
                Worker.is_active.is_(True))) or 0

        return {"total_attendance_sheets": sheets, "active_workers": workers}

    def get_dailylog_summary(self) -> Dict:
        """Get daily log summary for dashboards."""
        from app.dailylogs.models import DailyLog

        total = self.db.scalar(
            select(func.count(DailyLog.id)).where(
                DailyLog.organization_id == self.org_id)) or 0

        submitted = self.db.scalar(
            select(func.count(DailyLog.id)).where(
                DailyLog.organization_id == self.org_id,
                DailyLog.status == "SUBMITTED")) or 0

        return {"total_daily_logs": total, "submitted_daily_logs": submitted}

    def get_expense_summary(self) -> Dict:
        """Get expense summary for dashboards (accountant module)."""
        from app.expenses.models import Expense

        total = self.db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.organization_id == self.org_id,
                Expense.is_active.is_(True),
                Expense.status == "APPROVED")) or 0

        pending = self.db.scalar(
            select(func.count(Expense.id)).where(
                Expense.organization_id == self.org_id,
                Expense.is_active.is_(True),
                Expense.status == "SUBMITTED")) or 0

        pending_amount = self.db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.organization_id == self.org_id,
                Expense.is_active.is_(True),
                Expense.status == "SUBMITTED")) or 0

        return {"approved_amount": total, "pending_count": pending, "pending_amount": pending_amount}

    def get_task_summary(self, role_name: str | None = None) -> Dict:
        """Get task summary for dashboards."""
        from app.tasks.models import Task

        q = select(func.count(Task.id)).where(
            Task.organization_id == self.org_id,
            Task.is_active.is_(True))
        total = self.db.scalar(q) or 0

        open_q = select(func.count(Task.id)).where(
            Task.organization_id == self.org_id,
            Task.is_active.is_(True),
            Task.status.in_(["TODO", "IN_PROGRESS", "BLOCKED"]))
        open_count = self.db.scalar(open_q) or 0

        done = self.db.scalar(
            select(func.count(Task.id)).where(
                Task.organization_id == self.org_id,
                Task.is_active.is_(True),
                Task.status == "DONE")) or 0

        return {"total_tasks": total, "open_tasks": open_count, "completed_tasks": done}

    def get_overall_summary(self) -> Dict:
        """Get overall summary for a dashboard."""
        return {
            "projects": self.get_project_summary(),
            "budgets": self.get_budget_summary(),
            "procurement": self.get_procurement_summary(),
            "inventory": self.get_inventory_summary(),
            "labour": self.get_labour_summary(),
            "dailylogs": self.get_dailylog_summary(),
            "expenses": self.get_expense_summary(),
            "tasks": self.get_task_summary(),
        }
