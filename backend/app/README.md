# Paragon Apartment Management System (PAMS)

> Systems Development Group Project — UWE Bristol, 2025–26

PAMS is a desktop application that replaces Paragon's manual, paper-based property management processes with a consolidated, secure, and multi-city software solution. Built for property offices across Bristol, Cardiff, London, and Manchester.

---

## Team

| Name | Role |
|------|------|
| Ahmet Sungur | Project Manager & Full-Stack Developer |
| Efe Genc | UI/UX Designer & QA Lead |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11 |
| UI Framework | ttkbootstrap (tkinter) |
| ORM | SQLAlchemy |
| Database | MySQL (cloud-hosted) |
| DB Driver | pymysql |
| Auth | bcrypt password hashing |

---

## Prerequisites

- Python 3.11 (required — not 3.12/3.13 due to dependency compatibility)
- MySQL database (local or cloud)
- Git

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/sungurz/paragon-app.git
cd paragon-app/backend
```

### 2. Create and activate virtual environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the `backend/` directory:
```
DB_HOST=your_host
DB_PORT=3306
DB_NAME=paragon_db
DB_USER=your_username
DB_PASSWORD=your_password
```

### 5. Initialise the database
Run these commands in order:
```bash
python -m app.db.seed_data           # Creates roles, cities, system admin
python -m app.db.create_tables       # Creates all tables
python -m app.db.migrate_audit_table # Adds audit log columns
python -m app.db.seed_demo_data      # Loads demo data across all 4 cities
```

### 6. Launch the application
```bash
python -m app.main
```

---

## Demo Login Credentials

### System Administrator
| Username | Password |
|----------|----------|
| `admin` | `admin123` |

### Location Admins
| Username | Password | City |
|----------|----------|------|
| `bristol_admin` | `Bristol123` | Bristol |
| `london_admin` | `London123` | London |
| `cardiff_admin` | `Cardiff123` | Cardiff |
| `manchester_admin` | `Manchester123` | Manchester |

### Other Staff (Bristol)
| Username | Password | Role |
|----------|----------|------|
| `bristol_finance` | `Bristol123` | Finance Manager |
| `bristol_desk` | `Bristol123` | Front Desk |
| `bristol_maint1` | `Bristol123` | Maintenance Staff |

> Tenant accounts can be created via **Tenants → Edit → 🔑 Create Login**

---

## Features

### Account & User Management
- Six role types: Manager, Location Admin, Finance Manager, Front Desk, Maintenance Staff, Tenant
- Role-based access control (RBAC) — each role sees only what they need
- City-scoped access — Location Admins are restricted to their assigned city
- User deactivation and reactivation (preserves all history)
- Session timeout — auto-logout after 30 minutes of inactivity
- Change password from Settings page

### Tenant Management
- Full tenant registration — NI number (masked), personal details, employment, references, apartment preferences
- Lease creation, management, and early termination workflow
- Early termination — tenant submits a request (1 month notice, 5% penalty), management approves or rejects
- Tenant archiving and reactivation
- Tenant portal login — create a login directly from the tenant edit dialog

### Apartment Management
- Property and apartment registration with full attributes (location, type, rooms, rent)
- Apartment status tracking — Available, Occupied, Maintenance, Inactive
- City-scoped apartment and property creation

### Payment & Billing
- Invoice generation (monthly, bulk, and manual)
- Partial payments and outstanding balance tracking
- Receipt generation on every payment
- Late payment detection and overdue alerts
- Payment emulation with card validation (no real gateway)

### Maintenance
- Full ticket lifecycle: New → Triaged → Scheduled → In Progress → Waiting Parts → Resolved → Closed
- Priority levels: Low, Medium, High, Urgent
- Assign tickets to maintenance staff (city-scoped)
- Log material cost, time spent, and scheduled date per ticket
- Tenant notifications on status updates
- Update history timeline per ticket

### Complaints
- Six complaint categories: Noise, Maintenance, Neighbour, Billing, Staff Conduct, Other
- Full status workflow with assignment to relevant staff
- Resolution notes recorded on close

### Reporting
- Occupancy report — overall and per-city breakdown (Manager only)
- Finance report — monthly revenue, collected vs outstanding vs overdue
- Maintenance report — open tickets by status, total material costs, hours spent, most expensive jobs

### Tenant Dashboard
- Personal lease details with days remaining
- Own payment records with Total / Paid / Remaining breakdown
- Late payment alerts
- Make payments — card validation and receipt generation
- Submit maintenance repair requests
- View repair request progress timeline
- Submit complaints
- Payment history bar chart (monthly)
- Payment comparison vs neighbours in same property
- Late payments chart grouped by property
- Request early lease termination

### Audit Log
- Every key action is recorded — logins, lease creation, payments, ticket updates, complaints
- Filterable by action type
- Visible to Manager and Location Admin roles

### Business Expansion
- Manager can add new cities from the Settings page
- Newly created cities are immediately available for properties and staff assignments

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                  # Entry point, login handler, UserContext
│   ├── auth/
│   │   ├── permissions.py       # RBAC permission checks, sidebar modules
│   │   └── security.py          # bcrypt hashing
│   ├── db/
│   │   ├── models.py            # 19 SQLAlchemy models
│   │   ├── database.py          # Engine and session setup
│   │   ├── seed_data.py         # Roles, cities, admin user
│   │   ├── seed_demo_data.py    # Demo data across all 4 cities
│   │   ├── create_tables.py     # Table creation
│   │   └── migrate_audit_table.py  # Audit log migration
│   ├── services/
│   │   ├── lease_service.py
│   │   ├── tenant_service.py
│   │   ├── invoice_service.py
│   │   ├── payment_service.py
│   │   ├── receipt_service.py
│   │   ├── maintenance_service.py
│   │   ├── complaint_service.py
│   │   ├── notification_service.py
│   │   ├── late_payment_service.py
│   │   ├── reports_service.py
│   │   └── audit_service.py
│   └── ui/
│       ├── main_window.py
│       ├── login_window.py
│       ├── home_page.py
│       ├── users_page.py
│       ├── tenants_page.py
│       ├── apartments_page.py
│       ├── finance_page.py
│       ├── maintenance_page.py
│       ├── complaints_page.py
│       ├── reports_page.py
│       ├── tenant_dashboard.py
│       ├── session_manager.py
│       ├── city_management_page.py
│       ├── pending_terminations_panel.py
│       └── ... (dialogs)
├── requirements.txt
├── .env                         # Not committed — see setup instructions
└── README.md
```

---

## Database Schema

19 tables across the following domains:

| Domain | Tables |
|--------|--------|
| Auth | `users`, `roles` |
| Location | `cities`, `properties`, `apartments` |
| Tenants | `tenants`, `tenant_references` |
| Leases | `lease_agreements`, `lease_termination_requests` |
| Finance | `invoices`, `payments`, `payment_receipts`, `late_payment_alerts` |
| Maintenance | `maintenance_tickets`, `maintenance_updates` |
| Complaints | `complaints` |
| System | `notifications`, `audit_logs` |

---



## Case Study Reference

Built against the **Paragon Apartment Management System** case study specification (SDGP 2025–26), covering all required components:
- Account / User Management ✓
- Tenant Management ✓
- Apartment Management ✓
- Payment & Billing ✓
- Report Generation ✓
- Maintenance ✓
- Tenant Electronic Dashboard ✓ (SDGP additional requirement)