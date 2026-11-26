# C5 validation database baseline

This directory contains the authoritative, non-production database baseline for
the existing `verify:pce-formal-import-real-session-actor` Gate.

The baseline is generated from the current Django model contracts by
`backend/scripts/build_c5_validation_baseline.py`. The generator creates a new
SQLite file directly; it does not read or copy another database and does not run
Django migrations. The only initial fact is the active `COMP001` organization.
All users, employees, departments, positions, responsibilities, roles,
permissions, scope assignments, sessions, audit rows, customer rows and
idempotency rows are created only inside the Gate's temporary database copy.

Generate the canonical file from the repository root:

```powershell
$env:PYTHONPATH = 'D:\Dev-PCE\Source\backend\venv\Lib\site-packages'
& 'C:\Users\DAODA\AppData\Local\Python\pythoncore-3.14-64\python.exe' `
  'backend\scripts\build_c5_validation_baseline.py'
```

The output must match `manifest.json`. Install it as the unchanged Gate's fixed
input by copying `c5-validation-baseline.sqlite3` to `backend/db.sqlite3` only in
the C5 integration worktree. Preserve any pre-existing working database before
installation.

This database must not be used as an application, acceptance, production or
formal business database. It must never contain production business facts.
