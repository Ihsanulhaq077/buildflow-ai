# BuildFlow AI — Implementation Plan

**Target:** Complete, working BuildFlow AI construction ERP with AI + automation
**Status:** Phase 1 ready — Setting up the foundation
**Priority:** P0 — Must Have

---

## Phase 1 — Foundation (Week 1)

### 1.1 Repository Setup

Files created:
- `buildflow-ai/` (monorepo root)
  - `README.md`
  - `docker-compose.yml`
  - `.env.example`
  - `CLAUDE.md`
  - `docs/` (already created)
  - `backend/`
    - `app/`
    - `ml/`
    - `cv/`
    - `tests/`
  - `apps/`
    - `infrastructure/`

### 1.2 Infrastructure

Set up Docker for:
- PostgreSQL + pgvector (database)
- Redis (cache/queue/events)
- Local object storage

### 1.3 Authentication & Authorization

Core services:
- **auth/**: JWT refresh tokens, secure password hashing, session management
- **users/**: User management, profile, preferences
- **organizations/**: Multi-tenant isolation, company registration
- **roles/**: Role definitions, permission hierarchy
- **permissions/**: Permission checking, RBAC enforcement
- **audit/**: All action audit logging

Database schema (minimum):
```sql
Table: organizations
  id PK
  name
  created_at
  updated_at

Table: users
  id PK
  organization_id FK
  email
  password_hash
  name
  role_id FK
  active
  created_at

Table: roles
  id PK
  organization_id FK
  name
  permissions JSONB

Table: permissions
  id PK
  name
  resource
  action

Table: audit_logs
  id PK
  user_id FK
  organization_id FK
  action
  entity
  entity_id
  before JSONB
  after JSONB
  timestamp
```

### 1.4 Basic UI & API

Backend API endpoints (OpenAPI documented):
```
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout

GET    /organizations
POST   /organizations

GET    /projects
POST   /projects
GET    /projects/{id}

GET    /users
POST   /users
GET    /users/{id}

GET    /roles
GET    /permissions
```

Frontend (Next.js) with:
- Login/Register
- User dashboard
- Organization selector
- Basic navigation