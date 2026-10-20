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
| Dashboards (role-based, widgets, analytics) | ✅ | Phase 9 |
| AI Assistant (chat, tool calling, RAG Q&A) | ✅ | Phase 8 |

## New in This Merge: AI Assistant & Dashboards

The AI Assistant and Dashboards modules have been merged into the core `buildflow-ai/`
application — no separate projects, no blind copying. Each was analyzed, integrated, and
tested against the unified codebase.

### Phase 8 — AI Assistant (complete)

A chat interface with tool calling that lets users ask questions and execute actions
naturally:

- **Sessions & messages** — persistent chat history per session, optional project context
- **20+ integrated tools** covering every ERP module: RAG document search, projects, BOQ,
  budgets, procurement (requisitions, POs, quotes, GRN), inventory, labour, daily logs,
  and document access
- **Permission-aware responses** — every tool result is filtered by the caller's role and
  organization; the assistant never exposes data outside the user's tenant
- **RAG integration** — semantic search over uploaded documents with embedding-based
  retrieval

Key files: `app/ai_assistant/{models.py, schemas.py, service.py, routes.py}`, migration
`0008_phase_8_ai_assistant.py`.

### Phase 9 — Dashboards (complete)

Role-based dashboards with a pluggable widget system and an analytics data layer:

- **Dashboard CRUD** — role-based templates and custom dashboards, with public/shareable
  views, default dashboards per role, and a layout config
- **Widget system** — metric, chart, table, list, progress, gauge, timeline, map, calendar
  widgets with data sources (project, budget, procurement, inventory, labour, dailylog
  summaries) and chart-type choices (bar, line, pie, donut, scatter, area, heatmap, etc.)
- **Dashboard data endpoint** — `GET /dashboards/{id}/data` returns every widget with its
  live aggregated data, rendered with the widget's config and filters
- **Access control** — dashboard-level permissions (view/edit/share) for users and roles

Key files: `app/dashboards/{models.py, schemas.py, service.py, routes.py}`, migration
`0009_phase_9_dashboards.py`.

### What changed during the merge

- One shared permission system (`app/deps.py`) — no separate auth stack for either module
- One data access path (`app.db.get_db`, `org_scoped`) — zero cross-tenant leakage
- One Alembic history (`0008_phase_8_ai_assistant.py` → `0009_phase_9_dashboards.py`),
  imported via `app/all_models.py`
- No duplicate models, routes, or business logic — each module reuses existing ERP
  services rather than re-implementing them

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

### Phase 8 — AI Assistant
- **Sessions:** `POST /ai/sessions` (create), `GET /ai/sessions` (list)
- **Session detail:** `GET /ai/sessions/{id}`, `DELETE /ai/sessions/{id}`
- **Messages:** `GET /ai/sessions/{id}/messages`
- **Chat:** `POST /ai/chat` (send message, get response)
- **Tools:** `POST /ai/tools/execute` (tool execution, RAG search, project ops, etc.)

### Phase 9 — Dashboards
- **Dashboards:** `GET /dashboards` (list), `POST /dashboards` (create)
- **Dashboard CRUD:** `GET /dashboards/{id}`, `PUT /dashboards/{id}`, `DELETE /dashboards/{id}`
- **Dashboard data:** `GET /dashboards/{id}/data` (widgets + live aggregation)
- **Widgets:** `GET /dashboards/{id}/widgets`, `POST /dashboards/{id}/widgets` (add)
- **Widget CRUD:** `PUT /dashboards/{id}/widgets/{wid}`, `DELETE /dashboards/{id}/widgets/{wid}`

### Phase 10 — ML Forecasting
- **Cost Overrun Prediction:** `POST /ml/cost-overrun` (predict project cost overruns)
- **Delay Prediction:** `POST /ml/delay` (predict project delays in days)
- **Material Forecast:** `POST /ml/material` (predict material quantity needs)
- **Batch Predictions:** `POST /ml/batch` (run multiple forecast types)
- **Risk Assessment:** `GET /ml/risk/{project_id}` (comprehensive project risk)
- **Forecast History:** `GET /ml/forecasts` (list), `GET /ml/forecasts/{id}` (get)
- **Model Management:** `POST /ml/models`, `GET /ml/models`, `POST /ml/models/{name}/{v}/activate`
- **Statistics:** `GET /ml/stats`

### Phase 11 — Computer Vision
- **Detection Results:** `POST /cv/detections`, `GET /cv/detections/{id}`, `GET /cv/detections`
- **Site Photos:** `POST /cv/photos`, `GET /cv/photos/{id}`, `GET /cv/photos`
- **Photo Analysis:** `POST /cv/photos/{id}/analyze`, `GET /cv/photos/{id}/analysis`
- **PPE Registration:** `POST /cv/ppe-registrations`, `GET /cv/ppe-registrations/{role}`, `GET /cv/ppe-registrations`
- **Statistics:** `GET /cv/stats`

### Phase 12 — Commercial
- **Subscriptions:** `POST /commercial/subscription`, `GET /commercial/subscription`
- **Onboarding:** `POST /commercial/onboarding`, `GET /commercial/onboarding/complete`
- **Billing:** `POST /commercial/billing`, `GET /commercial/billing`, `PUT /commercial/billing/card`
- **System Events:** `POST /commercial/events`, `GET /commercial/events`, `POST /commercial/events/{id}/resolve`
- **Statistics:** `GET /commercial/stats`

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
