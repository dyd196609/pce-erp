"""Isolated-only Django bootstrap and baseline state adoption tooling."""
from pathlib import Path
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
ISO = ROOT / ".runtime/semi-finished-model-closure-20260909"
BACKEND = ISO / "backend"
OUT = ROOT / "docs/evidence/semi_finished_model_closure_20260909"


def bootstrap(database="isolated.sqlite3"):
    target = (ISO / database).resolve()
    if target.parent != ISO.resolve() or target == (ROOT / "backend/db.sqlite3").resolve():
        raise RuntimeError("ISOLATION_PATH_GUARD")
    sys.path.insert(0, str(ROOT / "backend/venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["DJANGO_SETTINGS_MODULE"] = "pce_backend.settings"
    from django.conf import settings
    # Overwrite all aliases BEFORE setup; no connection may point to production.
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(target)}}
    settings.PCE_CONFIGURATION_ISOLATED_REPLAY = True
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    import django
    django.setup()
    from django.db import connection
    assert Path(connection.settings_dict["NAME"]).resolve() == target
    return target


def adopt():
    from semi_finished_model_closure_prepare import RECOVER
    from django.apps import apps
    from django.db import connection, migrations
    from django.db.migrations.state import ModelState
    from django.db.migrations.writer import MigrationWriter
    from django.core.management import call_command
    import pickle

    db = Path(connection.settings_dict["NAME"])
    if db.exists():
        raise RuntimeError("Refusing to overwrite isolated DB")
    shutil.copy2(ROOT / "backend/db.sqlite3", db)
    checks, operations = [], []
    with connection.cursor() as cursor:
        for name in RECOVER:
            model = apps.get_model("pde", name)
            state = ModelState.from_model(model)
            cursor.execute(f'PRAGMA table_info("{model._meta.db_table}")')
            columns = {r[1]: r for r in cursor.fetchall()}
            expected = {f.column for f in model._meta.local_fields}
            if set(columns) != expected:
                raise RuntimeError((name, "HISTORICAL_SCHEMA_MISMATCH", sorted(expected-set(columns)), sorted(set(columns)-expected)))
            cursor.execute(f'SELECT count(*) FROM "{model._meta.db_table}"')
            checks.append({"model": name, "columnsExact": True, "count": cursor.fetchone()[0], "table": model._meta.db_table})
            options = dict(state.options)
            operations.append(migrations.CreateModel(name=state.name, fields=list(state.fields.items()), options=options, bases=state.bases, managers=state.managers))
    migration = migrations.Migration("0024_restore_material_contract_state", "pde")
    migration.dependencies = [("pde", "0022_manufacturing_definition_applicability")]
    migration.operations = [migrations.SeparateDatabaseAndState(database_operations=[], state_operations=operations)]
    writer = MigrationWriter(migration)
    path = BACKEND / "pde/migrations" / writer.filename
    path.write_text(writer.as_string(), encoding="utf-8")
    # Runtime model state before minimal changes lets the next diff exclude unrelated historical drift.
    from django.db.migrations.state import ProjectState
    (ISO / "before_model_state.pickle").write_bytes(pickle.dumps(ProjectState.from_apps(apps)))
    call_command("migrate", "pde", migration.name, interactive=False, verbosity=1)
    call_command("check", verbosity=1)
    (OUT / "STATE_ADOPTION.json").write_text(json.dumps({"models": checks, "databaseOperations": 0,
        "isolatedDatabase": str(db), "productionApplied": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    bootstrap()
    adopt()
