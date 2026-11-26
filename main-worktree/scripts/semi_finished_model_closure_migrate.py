"""Generate/apply the minimal model-state delta on the isolated database only."""
import json
from semi_finished_model_closure_runtime import bootstrap, ISO, BACKEND, OUT

bootstrap()
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.db.migrations.writer import MigrationWriter
from django.db.migrations.loader import MigrationLoader

after = ProjectState.from_apps(apps)
allowed = {"materialconfiguration", "materialconfigurationattribute", "materialfamilyallowedmaterial",
           "materialconfigurationsourcebinding", "productbom", "bomitem", "templatematerialrequirementslot"}
# Use the canonical migration state for the seven authorized models. Unrelated
# pre-existing model/state drift is intentionally not folded into this migration.
baseline = MigrationLoader(connection).project_state([("pde", "0024_restore_material_contract_state")])
before = after.clone()
for name in allowed:
    key = ("pde", name)
    if key in baseline.models:
        before.models[key] = baseline.models[key].clone()
    else:
        before.models.pop(key, None)
changes = MigrationAutodetector(before, after, NonInteractiveMigrationQuestioner())._detect_changes()
assert set(changes) == {"pde"}, list(changes)
assert len(changes["pde"]) == 1
migration = changes["pde"][0]
migration.name = "0025_material_configuration_applicability_quantity"
migration.dependencies = [("pde", "0024_restore_material_contract_state")]
descriptions = []
for op in migration.operations:
    name = (getattr(op, "model_name", None) or getattr(op, "name", "")).lower()
    assert name in allowed, (type(op).__name__, name)
    descriptions.append({"operation": type(op).__name__, "model": name, "description": op.describe()})
writer = MigrationWriter(migration)
target = BACKEND / "pde/migrations" / writer.filename
if target.exists():
    assert target.read_text(encoding="utf-8").split("\n", 1)[1] == writer.as_string().split("\n", 1)[1], "Candidate migration drift"
else:
    target.write_text(writer.as_string(), encoding="utf-8")
(BACKEND / "static").mkdir(exist_ok=True)
call_command("migrate", "pde", migration.name, interactive=False, verbosity=1)
call_command("check", verbosity=1)
with connection.cursor() as cursor:
    cursor.execute("PRAGMA foreign_key_check")
    violations = cursor.fetchall()
assert not violations, violations
(OUT / "ISOLATED_MIGRATION.json").write_text(json.dumps({"name": migration.name, "status": "PASS",
    "database": str(connection.settings_dict["NAME"]), "productionApplied": False,
    "operations": descriptions, "foreignKeyViolations": violations}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Isolated migration: {len(descriptions)} operations; FK clean; production migration not applied")
