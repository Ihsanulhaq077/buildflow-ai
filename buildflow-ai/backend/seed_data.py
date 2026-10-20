#!/usr/bin/env python3
"""
Seed script for BuildFlow AI database - populates demo data for role-based dashboards
and comprehensive frontend functionality.

This script creates:
- Organizations and roles
- Users with different roles
- Projects with clients
- Inventory items, warehouses, stock balances
- Suppliers and requisitions
- Dashboards for each role
- Workers and attendance
- Daily logs
- Budget and cost codes
- Systems events and subscriptions
"""

import sqlite3
import uuid
import datetime
import random
from decimal import Decimal

def generate_uuid():
    return str(uuid.uuid4())

def generate_code(prefix, length=3):
    return f"{prefix}{random.randint(10, 99)}"

def run_seed():
    conn = sqlite3.connect('dev.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = ON")
    
    print("Starting BuildFlow AI database seed...")
    
    # Get or create organizations
    orgs = []
    for org_name, org_slug in [
        ('Test Org', 'test-org'),
        ('BuildFlow Test', 'buildflow-test'),
    ]:
        org_id = generate_uuid()
        c.execute("""
            INSERT OR IGNORE INTO organizations (id, name, slug, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (org_id, org_name, org_slug, 
               datetime.datetime.now(), datetime.datetime.now()))
        orgs.append({'id': org_id, 'name': org_name, 'slug': org_slug})
    
    # Get organizations
    c.execute("SELECT id, name FROM organizations")
    org_map = {row['id']: {'name': row['name'], 'roles': []} for row in c.fetchall()}
    
    # Seed roles for each organization
    role_definitions = [
        ('OWNER', 1000000000000, [
            'users.read', 'users.manage', 'roles.read', 'audit.read',
            'projects.read', 'projects.manage', 'catalog.manage', 'boq.read', 'boq.manage',
            'boq.approve', 'budgets.read', 'budgets.manage', 'budgets.approve',
            'requisitions.create', 'procurement.read', 'procurement.manage', 'procurement.approve',
            'suppliers.approve', 'grn.create', 'inventory.read', 'inventory.manage', 'inventory.issue',
            'inventory.adjust', 'workers.manage', 'attendance.read', 'attendance.submit',
            'attendance.approve', 'labour.read', 'dailylog.read', 'dailylog.submit', 'dailylog.approve',
            'finance.read', 'finance.manage'
        ]),
        ('PROJECT_MANAGER', 50000, [
            'users.read', 'projects.read', 'projects.manage', 'boq.read', 'boq.manage',
            'budgets.read', 'budgets.manage', 'requisitions.create', 'procurement.read',
            'procurement.approve', 'grn.create', 'inventory.read', 'inventory.manage',
            'inventory.issue', 'inventory.adjust', 'dailylog.submit', 'attendance.submit',
            'finance.read', 'workers.manage', 'attendance.read', 'attendance.approve',
            'labour.read', 'dailylog.read', 'dailylog.approve'
        ]),
        ('SITE_ENGINEER', 0, [
            'projects.read', 'boq.read', 'requisitions.create', 'procurement.read',
            'inventory.read', 'inventory.issue', 'dailylog.submit', 'attendance.submit',
            'attendance.read', 'dailylog.read'
        ]),
        ('FOREMAN', 0, [
            'attendance.submit', 'attendance.read', 'dailylog.submit', 'dailylog.read'
        ]),
        ('WORKER', 0, []),
        ('STOREKEEPER', 0, [
            'projects.read', 'requisitions.create', 'procurement.read', 'grn.create',
            'inventory.read', 'inventory.manage', 'inventory.issue'
        ]),
        ('PROCUREMENT_OFFICER', 0, [
            'projects.read', 'boq.read', 'budgets.read', 'requisitions.create',
            'procurement.read', 'procurement.manage', 'inventory.read', 'inventory.manage'
        ]),
        ('ACCOUNTANT', 0, [
            'projects.read', 'boq.read', 'budgets.read', 'procurement.read',
            'inventory.read', 'finance.read', 'finance.manage', 'labour.read',
            'attendance.read'
        ]),
        ('HR_ADMIN', 0, [
            'users.read', 'users.manage', 'attendance.submit', 'attendance.read',
            'workers.manage', 'labour.read'
        ]),
        ('SUBCONTRACTOR', 0, []),
        ('CLIENT', 0, []),
    ]
    
    # Create roles and role_permissions for each org
    role_map = {}
    for role_name, approval_limit, permissions in role_definitions:
        role_id = generate_uuid()
        org_id = list(org_map.keys())[0] if org_map else generate_uuid()
        
        c.execute("""
            INSERT INTO roles (id, organization_id, name, approval_limit, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (role_id, org_id, role_name, approval_limit,
              datetime.datetime.now(), datetime.datetime.now()))
        
        role_map[role_name] = role_id
        org_map[org_id]['roles'][role_name] = role_id
        
        # Add permissions
        for perm in permissions:
            perm_id = generate_uuid()
            c.execute("""
                INSERT OR IGNORE INTO permissions (id, code, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (perm_id, perm, perm, datetime.datetime.now(), datetime.datetime.now()))
            
            # Link role to permission
            c.execute("""
                INSERT INTO role_permissions (role_id, permission_id, created_at)
                VALUES (?, ?, ?)
            """, (role_id, perm_id, datetime.datetime.now()))
    
    # Create clients for organizations
    clients = []
    for org_name, org_id in [(org['name'], org['id']) for org in orgs]:
        client_id = generate_uuid()
        c.execute("""
            INSERT INTO clients (id, organization_id, name, contact_person, phone, email, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_id, org_id, 
               f'{org_name} Main Client',
               'John Doe',
               '+92-300-1234567',
               'contact@example.com',
               datetime.datetime.now(), datetime.datetime.now()))
        clients.append({'id': client_id, 'org_id': org_id, 'name': f'{org_name} Main Client'})
    
    # Create sites
    sites = []
    for org_id in org_map.keys():
        site_id = generate_uuid()
        c.execute("""
            INSERT INTO sites (id, organization_id, project_id, name, address, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (site_id, org_id, None, 'Main Construction Site',
              '123 Main Street, Karachi, Pakistan',
              datetime.datetime.now(), datetime.datetime.now()))
        sites.append({'id': site_id, 'org_id': org_id})
    
    # Create projects for organizations
    projects = []
    for org_id, org_name in [(org['id'], org['name']) for org in orgs]:
        project_id = generate_uuid()
        client_id = next((c['id'] for c in clients if c['org_id'] == org_id), None)
        c.execute("""
            INSERT INTO projects (
                id, organization_id, code, name, client_id, location, contract_value,
                status, start_date, planned_end_date, project_manager_id, engineer_id,
                created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, org_id,
               generate_code('PRJ', 3),
               f'{org_name} - Main Construction Project',
               client_id,
               'Karachi',
               Decimal('150000000.00'),
               'IN_PROGRESS',
               '2026-10-18',
               '2027-06-18',
               list(role_map.values())[1],  # PROJECT_MANAGER role
               list(role_map.values())[2],  # SITE_ENGINEER role
               list(role_map.values())[0],  # OWNER role
               datetime.datetime.now(), datetime.datetime.now()))
        projects.append({'id': project_id, 'org_id': org_id, 'client_id': client_id, 'site_id': sites[0]['id'] if sites else None})
    
    # Create units for inventory
    units = []
    unit_codes = ['BAG', 'KG', 'TON', 'CFT', 'SQFT', 'SQM', 'NOS', 'BRICK', 'LDAY']
    for org_id in org_map.keys():
        for code in unit_codes:
            unit_id = generate_uuid()
            c.execute("""
                INSERT INTO units (id, organization_id, code, name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (unit_id, org_id, code, code, 
                  datetime.datetime.now(), datetime.datetime.now()))
            units.append({'id': unit_id, 'org_id': org_id, 'code': code})
    
    # Create cost codes for budgeting
    cost_categories = ['MATERIAL', 'LABOUR', 'EQUIPMENT', 'SUBCONTRACT', 'OTHER']
    for org_id in org_map.keys():
        for i, category in enumerate(cost_categories):
            cost_id = generate_uuid()
            c.execute("""
                INSERT INTO cost_codes (id, organization_id, code, name, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cost_id, org_id,
                   f"CC-{category[0]}{i+1:02d}",
                   f"{category} Cost Code",
                   category,
                   datetime.datetime.now(), datetime.datetime.now()))
    
    # Create warehouses for projects
    warehouses = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        for i in range(2):
            warehouse_id = generate_uuid()
            c.execute("""
                INSERT INTO warehouses (
                    id, organization_id, name, address, project_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (warehouse_id, org_id,
                   f"{org_id[:8]} Warehouse {i+1}",
                   f"Address {i+1} for {org_id[:8]}",
                   project_id,
                   datetime.datetime.now(), datetime.datetime.now()))
            warehouses.append({'id': warehouse_id, 'org_id': org_id, 'project_id': project_id})
    
    # Create inventory items with relationships
    inventory_items = []
    item_types = [
        ('CEMENT', 'Portland Cement Type I', 'BAG', 'MAT-CEM-01'),
        ('STEEL', 'Deformed Steel Rebar 16mm', 'TON', 'MAT-STL-16'),
        ('AGGREGATE', 'Coarse Aggregate (20mm)', 'CFT', 'MAT-AGG-20'),
        ('SAND', 'Washed Plastering Sand', 'CFT', 'MAT-SND-01'),
        ('BRICKS', 'Red Clay Bricks', 'NOS', 'MAT-BRK-01'),
        ('TIMBER', 'Pine Wood Planks', 'SQM', 'MAT-TIM-01'),
    ]
    
    for org_id in org_map.keys():
        unit_map = {u['id']: u['code'] for u in units if u['org_id'] == org_id}
        cost_code_map = {}
        c.execute(f"SELECT id, code FROM cost_codes WHERE organization_id = ?", (org_id,))
        cost_code_map = {row['id']: row['code'] for row in c.fetchall()}
        
        for type_name, name, unit_code, code_prefix in item_types:
            # Find matching unit and cost code
            unit_id = None
            for u_id, u_code in unit_map.items():
                if u_code == unit_code:
                    unit_id = u_id
                    break
            
            cost_code_id = list(cost_code_map.keys())[0] if cost_code_map else None
            
            item_id = generate_uuid()
            item_code = f"{code_prefix}-{org_id[:4].upper()}"
            
            c.execute("""
                INSERT INTO inventory_items (
                    id, organization_id, code, name, unit_id, cost_code_id,
                    min_stock, max_stock, reorder_level,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, org_id, item_code, name, unit_id, cost_code_id,
                  20, 500, 100,
                  datetime.datetime.now(), datetime.datetime.now()))
            
            inventory_items.append({'id': item_id, 'org_id': org_id, 'code': item_code, 'name': name})
            
            # Create stock balances for this item in warehouses
            for warehouse in warehouses:
                if warehouse['org_id'] == org_id:
                    stock_id = generate_uuid()
                    quantity = random.randint(50, 500)
                    c.execute("""
                        INSERT INTO stock_balances (
                            id, organization_id, warehouse_id, item_id, quantity, avg_cost,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (stock_id, org_id, warehouse['id'], item_id, quantity, 100,
                          datetime.datetime.now(), datetime.datetime.now()))
    
    # Create suppliers
    suppliers = []
    for org_id in org_map.keys():
        for i in range(3):
            supplier_id = generate_uuid()
            c.execute("""
                INSERT INTO suppliers (
                    id, organization_id, name, contact_person, phone, email,
                    is_approved, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (supplier_id, org_id,
                   f"{org_id[:8]} Supplier {i+1}",
                   f"Supplier Contact {i+1}",
                   f"+92-300-{1000+i}",
                   f"supplier{i+1}@example.com",
                   i == 0,  # First supplier approved
                   datetime.datetime.now(), datetime.datetime.now()))
            suppliers.append({'id': supplier_id, 'org_id': org_id, 'name': f"{org_id[:8]} Supplier {i+1}"})
    
    # Create requisitions (purchase requisitions)
    requisitions = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        warehouse = next((w for w in warehouses if w['org_id'] == org_id), None)
        if not warehouse:
            continue
            
        req_id = generate_uuid()
        req_code = f"REQ-{org_id[:4].upper()}-{random.randint(100, 999)}"
        
        c.execute("""
            INSERT INTO purchase_requisitions (
                id, organization_id, code, project_id, warehouse_id, status,
                notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (req_id, org_id, req_code, project_id, warehouse['id'],
               'DRAFT',  # Status
               'Required for ongoing construction work',
               datetime.datetime.now(), datetime.datetime.now()))
        
        requisitions.append({'id': req_id, 'org_id': org_id, 'code': req_code})
        
        # Add requisition lines
        c.execute(f"SELECT id FROM inventory_items WHERE organization_id = ?", (org_id,))
        items = c.fetchall()
        if items:
            item_id = items[0]['id']
            quantity = random.randint(10, 100)
            unit_price = Decimal(random.uniform(100, 1000))
            total = quantity * unit_price
            
            line_id = generate_uuid()
            c.execute("""
                INSERT INTO requisition_lines (
                    id, requisition_id, item_id, quantity, unit_price, total_amount,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (line_id, req_id, item_id, quantity, unit_price, total,
                  datetime.datetime.now(), datetime.datetime.now()))
    
    # Create attendance sheets for workers
    attendance_sheets = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        for date_offset in range(1, 11):  # Last 10 days
            work_date = datetime.date(2026, 10, 18) - datetime.timedelta(days=date_offset)
            
            sheet_id = generate_uuid()
            c.execute("""
                INSERT INTO attendance_sheets (
                    id, organization_id, project_id, work_date, status,
                    created_by, submitted_by, decision_comment,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_id, org_id, project_id, work_date.strftime('%Y-%m-%d'),
                   'SUBMITTED',  # Status
                   list(role_map.values())[0],  # OWNER as created_by
                   list(role_map.values())[1],  # PROJECT_MANAGER as submitted_by
                   'Regular attendance',
                   datetime.datetime.now(), datetime.datetime.now()))
            
            attendance_sheets.append({'id': sheet_id, 'org_id': org_id, 'date': work_date})
            
            # Create attendance entries for this sheet
            c.execute(f"SELECT id, daily_rate FROM workers WHERE organization_id = ?", (org_id,))
            workers_list = c.fetchall()
            if workers_list:
                for worker in workers_list:
                    entry_id = generate_uuid()
                    hours = random.uniform(8, 10)
                    rate = worker['daily_rate']
                    cost = hours * rate
                    
                    c.execute("""
                        INSERT INTO attendance_entries (
                            id, attendance_sheet_id, worker_id, hours_worked, rate, cost,
                            status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (entry_id, sheet_id, worker['id'], hours, rate, cost,
                          'APPROVED', datetime.datetime.now(), datetime.datetime.now()))
    
    # Create daily logs
    daily_logs = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        for date_offset in range(1, 31):  # Last 30 days
            log_date = datetime.date(2026, 10, 18) - datetime.timedelta(days=date_offset)
            
            log_id = generate_uuid()
            c.execute("""
                INSERT INTO daily_logs (
                    id, organization_id, project_id, site_id, log_date, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, org_id, project_id, None, log_date.strftime('%Y-%m-%d'),
                  'SUBMITTED', datetime.datetime.now(), datetime.datetime.now()))
            
            daily_logs.append({'id': log_id, 'org_id': org_id, 'date': log_date, 'project_id': project_id})
            
            # Add daily log progress entries
            progress_id = generate_uuid()
            c.execute("""
                INSERT INTO daily_log_progress (
                    id, daily_log_id, activity_type, description, progress_percent,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (progress_id, log_id, 'CONSTRUCTION', f'Progress update for {log_date}',
                   random.randint(60, 100),
                   datetime.datetime.now(), datetime.datetime.now()))
    
    # Create workers
    workers = []
    for org_id in org_map.keys():
        c.execute(f"SELECT id, code FROM cost_codes WHERE organization_id = ? AND category = 'LABOUR'", (org_id,))
        labour_cost_code = c.fetchone()
        labour_cost_code_id = labour_cost_code['id'] if labour_cost_code else None
        
        for i in range(random.randint(3, 8)):  # 3-8 workers per org
            worker_id = generate_uuid()
            worker_code = f"WRKR-{org_id[:4].upper()}-{i+1:03d}"
            
            c.execute("""
                INSERT INTO workers (
                    id, organization_id, code, name, trade, contractor, phone,
                    daily_rate, overtime_rate, cost_code_id, is_active,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (worker_id, org_id, worker_code,
                   f"Worker {i+1} - {org_id[:8]}",
                   ['Mason', 'Laborer', 'Carpenter', 'Plumber'][i % 4],
                   f"Contractor {i+1}",
                   f"+92-300-{2000+i}",
                   Decimal(random.uniform(1500, 3000)),
                   Decimal(random.uniform(2250, 4500)),
                   labour_cost_code_id,
                   True,
                   datetime.datetime.now(), datetime.datetime.now()))
            
            workers.append({'id': worker_id, 'org_id': org_id, 'name': f"Worker {i+1}"})
    
    # Create BOQs (Bills of Quantities)
    boqs = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        boq_id = generate_uuid()
        boq_code = f"BOQ-{org_id[:4].upper()}-{random.randint(100, 999)}"
        
        c.execute("""
            INSERT INTO boqs (
                id, organization_id, project_id, name, status, overhead_pct,
                contingency_pct, profit_pct, created_by,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (boq_id, org_id, project_id,
               f'{org_id[:8]} - Main BOQ',
               'APPROVED',  # Status
               10.0, 5.0, 5.0,  # Overheads
               list(role_map.values())[1],  # PROJECT_MANAGER as created_by
               datetime.datetime.now(), datetime.datetime.now()))
        
        boqs.append({'id': boq_id, 'org_id': org_id, 'code': boq_code})
        
        # Add BOQ items
        c.execute(f"SELECT id, code FROM cost_codes WHERE organization_id = ?", (org_id,))
        cost_codes = c.fetchall()
        if cost_codes:
            for cost_code in cost_codes[:3]:  # Add first 3 cost codes
                item_id = generate_uuid()
                quantity = random.randint(100, 1000)
                unit = random.choice(['BAG', 'TON', 'CFT', 'NOS'])
                unit_rate = Decimal(random.uniform(100, 5000))
                total = quantity * unit_rate
                
                c.execute("""
                    INSERT INTO boq_items (
                        id, boq_id, cost_code_id, quantity, unit, unit_rate, total_rate,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item_id, boq_id, cost_code['id'], quantity, unit, unit_rate, total,
                      datetime.datetime.now(), datetime.datetime.now()))
    
    # Create budgets
    budgets = []
    for org_id, project_id in [(org['id'], p['id']) for org in orgs for p in projects if p['org_id'] == org['id']]:
        budget_id = generate_uuid()
        budget_code = f"BUD-{org_id[:4].upper()}-{random.randint(100, 999)}"
        
        c.execute("""
            INSERT INTO budgets (
                id, organization_id, project_id, boq_id, status, approved_by,
                approved_at, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (budget_id, org_id, project_id, None,  # No boq_id initially
               'DRAFT', None, None,  # No approval yet
               list(role_map.values())[1],  # PROJECT_MANAGER as created_by
               datetime.datetime.now(), datetime.datetime.now()))
        
        budgets.append({'id': budget_id, 'org_id': org_id, 'code': budget_code})
        
        # Add budget lines
        c.execute(f"SELECT id FROM cost_codes WHERE organization_id = ?", (org_id,))
        cost_codes = c.fetchall()
        if cost_codes:
            for i, cost_code in enumerate(cost_codes[:5]):
                line_id = generate_uuid()
                original_amount = Decimal(random.uniform(50000, 200000))
                revised_amount = original_amount * Decimal(random.uniform(0.9, 1.1))
                committed_amount = original_amount * Decimal(random.uniform(0.3, 0.7))
                actual_amount = original_amount * Decimal(random.uniform(0.1, 0.5))
                paid_amount = original_amount * Decimal(random.uniform(0, 0.4))
                
                c.execute("""
                    INSERT INTO budget_lines (
                        id, budget_id, category, cost_code_id, description,
                        original_amount, revised_amount, committed_amount,
                        actual_amount, paid_amount,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (line_id, budget_id,
                       ['MATERIAL', 'LABOUR', 'EQUIPMENT'][i % 3],
                       cost_code['id'],
                       f'{cost_code["code"]} - Construction material',
                       original_amount, revised_amount, committed_amount,
                       actual_amount, paid_amount,
                       datetime.datetime.now(), datetime.datetime.now()))
    
    # Create system events
    event_types = [
        ('DAILY_LOG_CREATED', 'Daily log submitted successfully', 'system'),
        ('ATTENDANCE_APPROVED', 'Attendance sheet approved', 'finance'),
        ('INVENTORY_UPDATED', 'Stock balance updated', 'inventory'),
        ('REQ_CREATED', 'Purchase requisition created', 'procurement'),
        ('BUDGET_APPROVED', 'Budget approved by accountant', 'finance'),
    ]
    
    for org_id in org_map.keys():
        for event_type, message, source in event_types:
            for _ in range(2):  # 2 events per type per org
                event_id = generate_uuid()
                c.execute("""
                    INSERT INTO system_events (
                        id, organization_id, event_type, severity, message,
                        source, resolved, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (event_id, org_id,
                       event_type, 'INFO',
                       message,
                       source, False, datetime.datetime.now()))
    
    # Create subscriptions
    tiers = ['basic', 'professional', 'enterprise']
    statuses = ['active', 'trialing', 'past_due']
    
    for org_id in org_map.keys():
        sub_id = generate_uuid()
        start_date = datetime.datetime.now() - datetime.timedelta(days=random.randint(30, 365))
        end_date = start_date + datetime.timedelta(days=365)
        current_period_start = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 30))
        current_period_end = current_period_start + datetime.timedelta(days=30)
        
        c.execute("""
            INSERT INTO subscriptions (
                id, organization_id, tier, status, start_date, end_date,
                monthly_limit, current_period_start, current_period_end,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_id, org_id, random.choice(tiers), random.choice(statuses),
               start_date, end_date, random.choice([1000, 5000, 10000, None]),
               current_period_start, current_period_end,
               datetime.datetime.now(), datetime.datetime.now()))
    
    # Create onboarding progress
    for org_id in org_map.keys():
        progress_id = generate_uuid()
        c.execute("""
            INSERT INTO onboarding_progress (
                id, organization_id, steps, completed, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (progress_id, org_id,
               '{"org_setup": true, "users": true, "projects": true, "inventory": true}',
               True,
               datetime.datetime.now(), datetime.datetime.now()))
    
    # Create billing info
    for org_id in org_map.keys():
        billing_id = generate_uuid()
        c.execute("""
            INSERT INTO billing_info (
                id, organization_id, payment_method, billing_email, tax_id,
                card_last4, is_valid, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (billing_id, org_id,
               'credit_card', 'billing@example.com', 'TAX123456',
               '4242', True,
               datetime.datetime.now(), datetime.datetime.now()))
    
    # Create users with different roles
    for org in orgs:
        org_id = org['id']
        org_name = org['name']
        
        # Create users for each role (except OWNER for some orgs)
        roles_to_create = list(org_map[org_id]['roles'].items())
        
        # For first org (Test Org), create a complete set
        if org_name == 'Test Org':
            user_configs = [
                ('test@buildflow.com', 'Test User', 'OWNER'),
                ('demo@buildflow.com', 'Demo User', 'PROJECT_MANAGER'),
                ('ihsanulhaq077@gmail.com', 'Ihsan ul haq', 'ACCOUNTANT'),
            ]
        else:
            # For second org, create minimal set
            user_configs = [
                ('buildflow-admin@example.com', 'BuildFlow Admin', 'OWNER'),
            ]
        
        for email, full_name, role_name in user_configs:
            user_id = generate_uuid()
            
            # Get role_id
            role_id = org_map[org_id].get(role_name)
            if not role_id:
                role_id = list(org_map[org_id]['roles'].values())[0]
            
            # Create user
            c.execute("""
                INSERT INTO users (
                    id, organization_id, email, full_name, password_hash,
                    role_id, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, org_id, email, full_name,
                  '$2b$12$example.hash',  # Mock hash
                  role_id, True,
                  datetime.datetime.now(), datetime.datetime.now()))
    
    # Create dashboards for each role (for role-based testing)
    dashboard_types = ['CUSTOM', 'ROLE_BASED', 'TEMPLATE']
    data_sources = ['project.summary', 'budget.summary', 'procurement.summary',
                   'inventory.summary', 'labour.summary', 'dailylog.summary', 'overall.summary']
    widget_types = ['METRIC', 'CHART', 'TABLE', 'PROGRESS', 'GAUGE']
    chart_types = ['BAR', 'LINE', 'PIE', 'DONUT', 'SCATTER']
    
    for org_id, org_name in [(org['id'], org['name']) for org in orgs]:
        # Create a default dashboard for OWNER role
        owner_dashboard_id = generate_uuid()
        c.execute("""
            INSERT INTO dashboards (
                id, organization_id, name, description, dashboard_type, target_role,
                is_public, is_default, layout_config, refresh_interval,
                created_by, created_at, updated_at, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (owner_dashboard_id, org_id,
               f'{org_name} - Executive Dashboard',
               'Overall business overview for executives',
               'ROLE_BASED', 'OWNER',
               True, True,  # is_public, is_default
               '{"grid": "layout"}',  # layout_config
               60,  # refresh_interval
               list(org_map[org_id]['roles']['OWNER']),  # created_by
               datetime.datetime.now(), datetime.datetime.now(), True))
        
        # Create PROJECT_MANAGER dashboard
        pm_dashboard_id = generate_uuid()
        c.execute("""
            INSERT INTO dashboards (
                id, organization_id, name, description, dashboard_type, target_role,
                is_public, is_default, layout_config, refresh_interval,
                created_by, created_at, updated_at, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pm_dashboard_id, org_id,
               f'{org_name} - Project Manager Dashboard',
               'Project management and team oversight',
               'ROLE_BASED', 'PROJECT_MANAGER',
               True, False,
               '{"grid": "layout"}',
               30,
               list(org_map[org_id]['roles']['PROJECT_MANAGER']),
               datetime.datetime.now(), datetime.datetime.now(), True))
        
        # Add widgets to dashboards
        for dashboard_id, dashboard_name in [(owner_dashboard_id, f'{org_name} - Executive Dashboard'),
                                            (pm_dashboard_id, f'{org_name} - Project Manager Dashboard')]:
            
            # Add 3-5 widgets per dashboard
            for i in range(random.randint(3, 5)):
                widget_id = generate_uuid()
                data_source = random.choice(data_sources)
                widget_type = random.choice(widget_types)
                
                c.execute("""
                    INSERT INTO widgets (
                        id, dashboard_id, title, widget_type, data_source,
                        chart_type, position, width, height, config, filters,
                        refresh_interval, is_visible, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (widget_id, dashboard_id,
                       f'{dashboard_name} Widget {i+1}',
                       widget_type, data_source,
                       random.choice(chart_types) if widget_type == 'CHART' else None,
                       i,  # position
                       random.choice([6, 12]),  # width
                       random.choice([4, 6]),  # height
                       '{"color": "#3b82f6"}',  # config
                       '{"dateRange": "30d"}',  # filters
                       60 if data_source == 'overall.summary' else 30,  # refresh_interval
                       True,
                       datetime.datetime.now()))
    
    # Commit all changes
    conn.commit()
    
    print(f"Successfully seeded BuildFlow AI database!")
    print(f"Created {len(orgs)} organizations")
    print(f"Created {len(role_map)} roles across {len(org_map)} organizations")
    print(f"Created {len(inventory_items)} inventory items")
    print(f"Created {len(workers)} workers")
    print(f"Created {len(projects)} projects")
    print(f"Created {len(requisitions)} purchase requisitions")
    print(f"Created {len(attendance_sheets)} attendance sheets")
    print(f"Created {len(daily_logs)} daily logs")
    print(f"Created {len(boqs)} bills of quantities")
    print(f"Created {len(budgets)} budgets")
    print(f"Created {len(suppliers)} suppliers")
    print(f"Created {len(warehouses)} warehouses")
    print(f"Created {len(projects)} projects")
    print(f"Created {len(sites)} sites")
    print(f"Created {len(clients)} clients")
    print(f"Created {len(users)} users")
    print(f"Created {len(dashboards)} dashboards")
    print(f"Created {len(system_events)} system events")
    print(f"Created {len(subscriptions)} subscriptions")
    print(f"All relationships established!")
    
    conn.close()

if __name__ == '__main__':
    run_seed()
    
    print("\n" + "="*60)
    print("SEEDING COMPLETE - Ready for Frontend Testing")
    print("="*60)
    print("\nDemo Account Credentials:")
    print("Email: test@buildflow.com")
    print("Password: (any 10+ chars)")
    print("Role: OWNER")
    print("\nTest Role Account:")
    print("Email: demo@buildflow.com") 
    print("Password: (any 10+ chars)")
    print("Role: PROJECT_MANAGER")
    print("\nNote: Use the 'switch role' dropdown in Layout to test role-based dashboards!")
    print("="*60)
    
    # List users for reference
    print("\nAll Created Users:")
    conn = sqlite3.connect('dev.db')
    c = conn.cursor()
    c.execute("SELECT u.email, u.full_name, r.name as role, org.name as org FROM users u JOIN roles r ON u.role_id = r.id JOIN organizations org ON u.organization_id = org.id ORDER BY org.name, r.name")
    for row in c.fetchall():
        print(f"  {row[0]} ({row[1]}) - {row[2]} at {row[3]}")
    conn.close()