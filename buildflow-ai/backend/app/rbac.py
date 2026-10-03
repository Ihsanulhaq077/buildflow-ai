"""Default permission catalogue and role templates.
Roles are copied per organization at registration and can then be edited (configurable RBAC)."""

PERMISSIONS = {
    "users.read": "View users",
    "users.manage": "Create/update users",
    "roles.read": "View roles",
    "audit.read": "View audit logs",
    "projects.read": "View projects",
    "projects.manage": "Create/update projects",
    "catalog.manage": "Manage cost codes, units and conversions",
    "boq.read": "View BOQs",
    "boq.manage": "Create/edit draft BOQs",
    "boq.approve": "Approve BOQs",
    "budgets.read": "View budgets",
    "budgets.manage": "Create/edit draft budgets",
    "budgets.approve": "Approve budgets and budget revisions",
    "requisitions.create": "Create purchase requisitions",
    "procurement.read": "View suppliers, requisitions, quotes, POs, receipts",
    "procurement.manage": "Manage suppliers, quotes and draft POs",
    "procurement.approve": "Approve requisitions and POs (within role approval limit)",
    "suppliers.approve": "Approve new suppliers",
    "grn.create": "Receive goods (GRN)",
    "inventory.read": "View stock and movements",
    "inventory.manage": "Manage warehouses, items and transfers",
    "inventory.issue": "Issue/return material to projects",
    "inventory.adjust": "Post stock adjustments, damage, waste, opening stock",
    "workers.manage": "Create/edit workers and their rates",
    "attendance.read": "View attendance (without pay data)",
    "attendance.submit": "Submit attendance",
    "attendance.approve": "Approve/reject attendance (posts labour cost)",
    "labour.read": "View wage rates, labour cost and wage register",
    "dailylog.read": "View daily site reports and progress",
    "dailylog.submit": "Create and submit daily site reports",
    "dailylog.approve": "Reopen submitted daily reports",
    "finance.read": "View financial data",
    "finance.manage": "Manage accounting",
}

ALL = list(PERMISSIONS)

# name -> (permissions, approval_limit_pkr)
DEFAULT_ROLES: dict[str, tuple[list[str], int]] = {
    "OWNER": (ALL, 10**12),
    "PROJECT_MANAGER": ([
        "users.read", "projects.read", "projects.manage", "boq.read", "boq.manage", "budgets.read",
        "budgets.manage", "requisitions.create", "procurement.read", "procurement.approve", "grn.create",
        "inventory.read", "inventory.manage", "inventory.issue", "inventory.adjust", "dailylog.submit",
        "attendance.submit", "finance.read", "workers.manage", "attendance.read", "attendance.approve",
        "labour.read", "dailylog.read", "dailylog.approve"], 50_000),
    "SITE_ENGINEER": ([
        "projects.read", "boq.read", "requisitions.create", "procurement.read", "inventory.read",
        "inventory.issue", "dailylog.submit", "attendance.submit", "attendance.read", "dailylog.read"], 0),
    "FOREMAN": (["attendance.submit", "attendance.read", "dailylog.submit", "dailylog.read"], 0),
    "WORKER": ([], 0),
    "STOREKEEPER": ([
        "projects.read", "requisitions.create", "procurement.read", "grn.create", "inventory.read",
        "inventory.manage", "inventory.issue"], 0),
    "PROCUREMENT_OFFICER": ([
        "projects.read", "boq.read", "budgets.read", "requisitions.create", "procurement.read",
        "procurement.manage", "inventory.read", "inventory.manage"], 0),
    "ACCOUNTANT": ([
        "projects.read", "boq.read", "budgets.read", "procurement.read", "inventory.read", "finance.read",
        "finance.manage", "labour.read", "attendance.read"], 0),
    "HR_ADMIN": (["users.read", "users.manage", "attendance.submit", "attendance.read", "workers.manage",
                  "labour.read"], 0),
    "SUBCONTRACTOR": ([], 0),
    "CLIENT": ([], 0),  # no access until project-level membership exists (later phase)
}
