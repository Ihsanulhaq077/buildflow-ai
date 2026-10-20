"""Default role dashboards.

Each construction role gets a cockpit tailored to what it is accountable for. The templates
here are the single source of truth: organization registration seeds them, and the demo
seeder reuses them so a fresh org and a seeded org look the same.
"""
import uuid

from sqlalchemy.orm import Session

from app.dashboards.models import Dashboard, DashboardPermission, Widget
from app.models import Role, User

# role -> (dashboard name, description, is_default, [(widget title, type, data_source, chart_type, width, height)])
ROLE_TEMPLATES: dict[str, tuple[str, str, bool, list[tuple]]] = {
    "OWNER": (
        "Executive Cockpit",
        "Portfolio-wide progress, financial burn rate and risk across every project.",
        True,
        [
            ("Total Projects", "METRIC", "project.summary", None, 4, 3),
            ("Active Projects", "METRIC", "project.summary", None, 4, 3),
            ("Budget Position", "METRIC", "budget.summary", None, 4, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 4, 3),
            ("Portfolio Overview", "CHART", "overall.summary", "BAR", 12, 6),
        ],
    ),
    "PROJECT_MANAGER": (
        "Project Manager Cockpit",
        "Delivery progress, procurement pipeline and site performance for your projects.",
        True,
        [
            ("Active Projects", "METRIC", "project.summary", None, 4, 3),
            ("Pending Requisitions", "METRIC", "procurement.summary", None, 4, 3),
            ("Below Reorder Items", "METRIC", "inventory.summary", None, 4, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 4, 3),
            ("Delivery & Cost Overview", "CHART", "overall.summary", "BAR", 12, 6),
        ],
    ),
    "SITE_ENGINEER": (
        "Site Engineer Cockpit",
        "Today's site reports, material consumption and the work assigned to your crews.",
        True,
        [
            ("Daily Logs Filed", "METRIC", "dailylog.summary", None, 4, 3),
            ("Active Workers", "METRIC", "labour.summary", None, 4, 3),
            ("Stock On Hand", "METRIC", "inventory.summary", None, 4, 3),
            ("My Open Tasks", "METRIC", "task.summary", None, 4, 3),
        ],
    ),
    "FOREMAN": (
        "Foreman Cockpit",
        "Today's manpower, site report and the tasks due on your crew.",
        True,
        [
            ("Active Workers", "METRIC", "labour.summary", None, 6, 3),
            ("Daily Logs Filed", "METRIC", "dailylog.summary", None, 6, 3),
            ("My Open Tasks", "METRIC", "task.summary", None, 6, 3),
        ],
    ),
    "STOREKEEPER": (
        "Storekeeper Cockpit",
        "Stock balances, reorder triggers and the requisitions waiting on you.",
        True,
        [
            ("Tracked Items", "METRIC", "inventory.summary", None, 4, 3),
            ("Below Reorder Items", "METRIC", "inventory.summary", None, 4, 3),
            ("Pending Requisitions", "METRIC", "procurement.summary", None, 4, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 4, 3),
        ],
    ),
    "PROCUREMENT_OFFICER": (
        "Procurement Cockpit",
        "Requisition pipeline, supplier activity and stock cover for every site.",
        True,
        [
            ("Requisitions In Flight", "METRIC", "procurement.summary", None, 4, 3),
            ("Tracked Items", "METRIC", "inventory.summary", None, 4, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 4, 3),
            ("Procurement Overview", "CHART", "overall.summary", "PIE", 12, 6),
        ],
    ),
    "ACCOUNTANT": (
        "Accountant Cockpit",
        "Budget position, approved spend, expense approvals and labour cost.",
        True,
        [
            ("Budget Revised", "METRIC", "budget.summary", None, 4, 3),
            ("Actual Spend", "METRIC", "budget.summary", None, 4, 3),
            ("Pending Expenses", "METRIC", "expense.summary", None, 4, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 4, 3),
            ("Spend Breakdown", "CHART", "overall.summary", "DONUT", 12, 6),
        ],
    ),
    "HR_ADMIN": (
        "HR Cockpit",
        "Worker records, attendance and the people-related tasks on your desk.",
        True,
        [
            ("Active Workers", "METRIC", "labour.summary", None, 6, 3),
            ("Attendance Sheets", "METRIC", "labour.summary", None, 6, 3),
            ("Open Tasks", "METRIC", "task.summary", None, 6, 3),
        ],
    ),
    "SUBCONTRACTOR": (
        "Subcontractor Cockpit",
        "The tasks assigned to your crew.",
        True,
        [
            ("Open Tasks", "METRIC", "task.summary", None, 6, 3),
        ],
    ),
    "CLIENT": (
        "Client Portal",
        "Progress visibility on your project.",
        True,
        [
            ("Total Projects", "METRIC", "project.summary", None, 6, 3),
            ("Active Projects", "METRIC", "project.summary", None, 6, 3),
        ],
    ),
}


def seed_role_dashboards(db: Session, org_id, roles: dict[str, Role], owner: User | None = None) -> list[Dashboard]:
    """Create the default dashboard for every role in the organization.

    Each dashboard is targeted at its role, and a ``DashboardPermission`` row grants the
    matching role view access, so the visibility rules and the grants never drift apart.
    """
    created: list[Dashboard] = []
    for role_name, (name, description, is_default, widgets) in ROLE_TEMPLATES.items():
        role = roles.get(role_name)
        if role is None:
            continue
        dashboard = Dashboard(
            organization_id=org_id,
            name=name,
            description=description,
            dashboard_type="ROLE_BASED",
            target_role=role_name,
            is_public=False,
            is_default=is_default,
            is_active=True,
            layout_config={"columns": 12, "gap": 16},
            refresh_interval=300,
            created_by=owner.id if owner else None,
        )
        db.add(dashboard)
        db.flush()

        for i, (w_title, w_type, w_source, w_chart, w_width, w_height) in enumerate(widgets):
            db.add(Widget(
                dashboard_id=dashboard.id,
                title=w_title,
                widget_type=w_type,
                data_source=w_source,
                chart_type=w_chart,
                position=i,
                width=w_width,
                height=w_height,
                config={},
                filters={},
                is_visible=True,
            ))

        db.add(DashboardPermission(
            dashboard_id=dashboard.id,
            role_id=role.id,
            can_view=True,
            can_edit=(role_name in ("OWNER", "PROJECT_MANAGER", "ACCOUNTANT")),
            can_share=(role_name == "OWNER"),
            granted_by=owner.id if owner else None,
        ))
        created.append(dashboard)

    db.commit()
    return created
