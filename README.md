# BMSIT Library Management System

A Streamlit and SQLite application for managing the BMSIT Engineering College library catalog, member register, book circulation, and inventory reports.

## Features

- Catalog search and book creation, editing, copy tracking, archive, and restore.
- Member registration and maintenance with archive and restore controls.
- Checkouts with due dates, return processing, and overdue tracking.
- Dashboard metrics for catalog size, availability, active loans, members, and overdue books.
- Category and popular-title charts, plus CSV exports for inventory and loan history.
- SQLite transaction and constraint checks to prevent over-issuing copies or returning a loan twice.

## Run locally

From PowerShell in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r req.txt
streamlit run app.py
```

The app creates `library.db` in the project folder on first run. To store it elsewhere, set `LIBRARY_DB_PATH` before starting Streamlit:

```powershell
$env:LIBRARY_DB_PATH = "D:\\library-data\\library.db"
streamlit run app.py
```

## Operational notes

This version is a local library operations tool and does not include sign-in or role-based permissions. Before deploying it for campus-wide use, add institutional authentication and authorization, choose managed persistent storage, and establish an automated database backup and restore procedure. Avoid placing student contact details in an instance accessible to unauthorized users.