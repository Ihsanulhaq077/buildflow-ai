# BuildFlow AI — Construction Office & Site Operating System

Tagline: **Plan. Build. Track. Manage. Grow.**

An AI-powered, Pakistan-native construction operating system that connects BOQ →
Estimate → Budget → Procurement → Inventory → Labour → Daily Progress → Billing →
Accounting → AI Analysis into a single source of truth.

## What's Included

### Core Modules (Complete & Tested)
| Module | Status | Tests |
|--------|--------|-------|
| Authentication & JWT | ✅ | Foundation |
| Organizations (multi-tenant) | ✅ | Foundation |
| Users & RBAC | ✅ | Foundation |
| Audit Logging | ✅ | Foundation |
| Projects, Sites, Contracts | ✅ | Projects |
| Clients | ✅ | Projects |
| BOQ & Deterministic Calculations | ✅ | BOQ/Budget |
| Cost Codes, Units, Conversions | ✅ | BOQ/Budget |
| Budgets (with revisions) | ✅ | BOQ/Budget |
| Suppliers, Quotations | ✅ | Procurement |
| Purchase Requisitions (with stock check) | ✅ | Procurement |
| Purchase Orders (with budget guard) | ✅ | Procurement |
| Goods Receipts (GRN) | ✅ | Procurement |
| Inventory (warehouses, items, movements) | ✅ | Inventory |
| Stock Transfers | ✅ | Inventory |
| Material Issues & Returns | ✅ | Inventory |
| Stock Adjustments (opening/damage/waste) | ✅ | Inventory |
| Consumption Analysis | ✅ | Inventory |
| Workers | ✅ | Labour |
| Attendance (sheets, entries, approvals) | ✅ | Labour |
| Deterministic Labour Cost Calculation | ✅ | Labour |
| Labour Cost Summary | ✅ | Labour |
| Daily Logs (create, submit, reopen, PDF) | ✅ | Daily Logs |
| Missing Daily Reports | ✅ | Daily Logs |

## Technology Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic
- **Auth:** Argon2 password hashing, JWT (PyJWT) with refresh + revocation
- **Database:** SQLite (dev) / PostgreSQL (prod), pgvector-ready
- **Calculations:** Decimal-based, deterministic (no floats, no LLM for arithmetic)
- **PDF:** ReportLab for daily log export
- **Tests:** pytest, 47 integration tests

## Quick Start

### 1. Install Python dependencies
```bash
cd buildflow-ai/backend
python -m pip install -r requirements.txt
```

### 2. Configure environment
```bash
# Copy and edit .env (defaults work for local development)
cp .env.example .env
```

### 3. Run migrations
```bash
alembic upgrade head
```

### 4. Start the API server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Open Swagger docs
Visit http://localhost:8000/docs

### 6. Run tests
```bash
pytest -v
```

## API Endpoints (Summary)

- **Auth:** `/auth/register-organization`, `/auth/login`, `/auth/refresh`, `/auth/logout-all`
- **Users:** `/users/me`, `/users`, `/users` (POST)
- **Audit:** `/audit-logs`
- **Projects:** `/projects`, `/projects/{id}`, `/projects/{id}/status`, `/projects/{id}/sites`, `/projects/{id}/contracts`, `/projects/{id}/budget`, `/projects/{id}/progress`
- **Clients:** `/clients`
- **BOQ:** `/boqs`, `/boqs/{id}`, `/boqs/{id}/items`, `/boqs/{id}/calculate`, `/boqs/{id}/approve`
- **Catalog:** `/units`, `/unit-conversions`, `/cost-codes`
- **Budgets:** `/budgets/from-boq`, `/budgets/{id}/lines`, `/budgets/{id}/approve`, `/budgets/{id}/lines/{id}/revise`
- **Requisitions:** `/requisitions`, `/requisitions/stock-check`, `/requisitions/{id}/quotes`, `/requisitions/{id}/comparison`, `/requisitions/{id}/submit`, `/requisitions/{id}/approve`, `/requisitions/{id}/reject`
- **Purchase Orders:** `/purchase-orders`, `/purchase-orders/{id}/submit`, `/purchase-orders/{id}/approve`, `/purchase-orders/{id}/reject`
- **Goods Receipts:** `/goods-receipts`
- **Suppliers:** `/suppliers`, `/suppliers/{id}/approve`
- **Inventory:** `/warehouses`, `/inventory/items`, `/inventory/stock`, `/inventory/transactions`, `/inventory/issues`, `/inventory/returns`, `/inventory/transfers`, `/inventory/adjustments`, `/inventory/consumption`
- **Workers:** `/workers`
- **Attendance:** `/attendance-sheets`, `/attendance-sheets/{id}/entries`, `/attendance-sheets/{id}/submit`, `/attendance-sheets/{id}/approve`, `/labour/cost-summary`
- **Daily Logs:** `/daily-logs`, `/daily-logs/{id}/submit`, `/daily-logs/{id}/reopen`, `/daily-logs/{id}/pdf`, `/daily-logs/missing`
- **Health:** `/health`

## Multi-Tenant Security

Every tenant-owned query is scoped via `org_scoped()` in [app/deps.py](backend/app/deps.py).
Cross-tenant access returns "not found" to prevent data leakage. RBAC is enforced
via `require_permission()` decorators.

## Deterministic Calculations

All financial and inventory calculations use Python's `Decimal` type and
deterministic functions (see [boq/calculations.py](backend/app/boq/calculations.py),
[labour/calculations.py](backend/app/labour/calculations.py)). No LLM is ever used
for arithmetic.

## Project Structure

```
buildflow-ai/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entry
│   │   ├── config.py             # Pydantic settings
│   │   ├── db.py                 # SQLAlchemy engine/session
│   │   ├── security.py           # Argon2 + JWT
│   │   ├── timeutil.py           # Business timezone helpers
│   │   ├── models.py             # Core models (Org, User, Role, Permission, AuditLog)
│   │   ├── all_models.py         # Import all models (Alembic)
│   │   ├── rbac.py               # Permission catalogue + role templates
│   │   ├── deps.py               # RBAC & tenant-scoping helpers
│   │   ├── audit.py              # Audit logging helper
│   │   ├── schemas.py            # Core Pydantic schemas
│   │   ├── routers.py            # Auth, users, audit routers
│   │   ├── boq/                  # BOQ & calculation engine
│   │   ├── budgets/              # Budgets (with revisions)
│   │   ├── projects/             # Projects, sites, contracts, clients
│   │   ├── procurement/          # Requisitions, POs, GRN, suppliers
│   │   ├── inventory/            # Warehouses, items, stock, movements
│   │   ├── labour/               # Workers, attendance, cost calc
│   │   └── dailylogs/            # Daily site reports + PDF
│   ├── tests/                    # 47 integration tests
│   ├── alembic/                  # Migrations
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml            # Postgres + Redis + MinIO
├── .env.example
└── README.md
```

## Data Flow

```
BOQ → Budget → Requisition (stock check) → Quotes → PO → GRN
     → Inventory Update → Material Issue → Labour Cost
     → Daily Log → Dashboard / AI
```

## Roadmap (Next Phases)

- **Phase 4 — Finance:** Expenses, Invoices, Payments, Receivables, Payables, P&L
- **Phase 5 — Dashboards:** Role-based dashboards
- **Phase 6 — Documents:** Upload, versioning, permissions
- **Phase 7 — RAG:** Document extraction, OCR, chunking, embeddings, pgvector
- **Phase 8 — AI Assistant:** Chat with tool calling, permission-aware Q&A
- **Phase 9 — Automation:** Approval engine, event-driven workflows
- **Phase 10 — ML:** Cost overrun / delay / material forecasting
- **Phase 11 — Computer Vision:** PPE detection, site photo analysis
- **Phase 12 — Commercial:** Subscriptions, onboarding, monitoring

## License

BuildFlow AI — FYP/MVP
