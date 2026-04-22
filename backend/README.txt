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
-----------------
BRISTOL
-------
Role: Location Admin      | Username: bristol_admin    | Password: Bristol123
Role: Finance Manager     | Username: bristol_finance  | Password: Bristol123
Role: Front Desk          | Username: bristol_desk     | Password: Bristol123
Role: Maintenance Staff   | Username: bristol_maint1   | Password: Bristol123
Role: Maintenance Staff   | Username: bristol_maint2   | Password: Bristol123
 
LONDON
------
Role: Location Admin      | Username: london_admin     | Password: London123
Role: Finance Manager     | Username: london_finance   | Password: London123
Role: Front Desk          | Username: london_desk      | Password: London123
Role: Maintenance Staff   | Username: london_maint1    | Password: London123
 
CARDIFF
-------
Role: Location Admin      | Username: cardiff_admin    | Password: Cardiff123
Role: Front Desk          | Username: cardiff_desk     | Password: Cardiff123
Role: Maintenance Staff   | Username: cardiff_maint1   | Password: Cardiff123
 
MANCHESTER
----------
Role: Location Admin      | Username: manchester_admin    | Password: Manchester123
Role: Front Desk          | Username: manchester_desk     | Password: Manchester123
Role: Maintenance Staff   | Username: manchester_maint1   | Password: Manchester123
================================================================================
