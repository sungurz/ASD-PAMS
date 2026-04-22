================================================================================
  PARAGON APARTMENT MANAGEMENT SYSTEM (PAMS)
  Advanced Software Development — UFCF8S-30-2
  UWE Bristol — April 2026

  Authors:
    Ahmet Sungur  (24034408) — Full-Stack Development, Database, RBAC
    Efe Genc      (23001693) — UI/UX Design, QA and Testing
    Dan McNamara  (23037788) — UML Diagrams, System Design Documentation

  GitHub: https://github.com/sungurz/ASD-PAMS
================================================================================

HOW TO RUN
----------
All commands must be run from the backend/ directory.

  Step 1 — python -m app.db.seed_data
  Step 2 — python -m app.db.create_tables
  Step 3 — python -m app.db.migrate_audit_table
  Step 4 — python -m app.db.seed_demo_data
  Step 5 — python -m app.main

DATABASE SETUP
--------------
Create a .env file inside backend/ with:

  DB_HOST=your_host
  DB_PORT=3306
  DB_NAME=paragon_db
  DB_USER=your_username
  DB_PASSWORD=your_password

LOGIN CREDENTIALS
-----------------
System Admin:     admin / admin123
Bristol Admin:    bristol_admin / Bristol123
London Admin:     london_admin / London123
Cardiff Admin:    cardiff_admin / Cardiff123
Manchester Admin: manchester_admin / Manchester123
Finance Manager:  bristol_finance / Bristol123
Front Desk:       bristol_desk / Bristol123
Maintenance:      bristol_maint1 / Bristol123
================================================================================
