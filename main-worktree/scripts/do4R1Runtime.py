"""DO4-R1 local startup/read-only evidence. No migrations or business requests."""
import argparse
from datetime import datetime
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "frontend/test-results/pce-order-delivery-planning-do4-r1-runtime-20260913"
DATABASES = {"A": BACKEND / "db.sqlite3", "B": Path("D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3")}
ENVIRONMENT = {
    "PCE_DATABASE_PATH": str(DATABASES["B"]),
    "PCE_NON_PRODUCTION_ACCEPTANCE": "1",
    "PCE_DATABASE_IDENTITY": "PDE-OPERABLE-ACCEPTANCE-20260912",
    "PCE_ENVIRONMENT_LABEL": "PDE original page isolated acceptance",
    "DJANGO_SETTINGS_MODULE": "pce_backend.settings",
}
ROUTES = [
    "/api/sales/previews/whole-house-order/",
    "/api/sales/orders/source-intake/whole-house/",
    "/api/sales/orders/source-intake/whole-house/actions/save-mapping/",
    "/api/sales/orders/source-intake/whole-house/actions/confirm-source/",
    "/api/sales/orders/source-intake/whole-house/actions/confirm-mapping/",
    "/api/sales/orders/", "/api/sales/facts/", "/api/planning/facts/", "/api/auth/login/",
]


def now():
    return datetime.now().astimezone().isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(OUT / name), "recordedAt": now()}, ensure_ascii=False), flush=True)


def protect_reads(db):
    db.execute("PRAGMA query_only=ON")
    def authorizer(action, arg1, arg2, *_):
        if action == sqlite3.SQLITE_READ and (arg2 or "").lower() in {
            "password", "password_hash", "session_key", "session_data", "token", "access_token", "refresh_token", "secret_key"
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    db.set_authorizer(authorizer)


def snapshot(label):
    result = {"recordedAt": now(), "mode": "SQLite mode=ro; query_only; sensitive-column deny", "databases": {}}
    names = ["sales_customer", "material", "unit_of_measure", "pde_product_definition", "sales_order", "sales_order_item",
             "planning_demand", "planning_requirement", "planning_purchase_plan", "planning_production_plan",
             "masterdata_external_identity", "masterdata_write_request", "system_organization_operating_audits",
             "django_migrations", "django_session", "user_system", "system_user_role_scope_assignments", "workflow_instances"]
    for key, path in DATABASES.items():
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        protect_reads(db)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {name: db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in names if name in tables}
        result["databases"][key] = {
            "path": str(path.resolve()), "sha256": sha(path), "size": path.stat().st_size,
            "databaseList": db.execute("PRAGMA database_list").fetchall(), "counts": counts,
            "relatedAuditCounts": db.execute("SELECT action_code,count(*) FROM system_organization_operating_audits WHERE action_code LIKE '%SOURCE%' OR action_code LIKE '%LOGIN%' OR action_code LIKE 'sales.%' GROUP BY action_code").fetchall(),
            "lastLoginSummary": db.execute("SELECT count(last_login),max(last_login) FROM user_system").fetchone(),
            "planningMigrations": db.execute("SELECT name FROM django_migrations WHERE app='planning' ORDER BY id").fetchall(),
            "sidecars": {suffix: {"exists": Path(str(path)+suffix).exists(), "size": Path(str(path)+suffix).stat().st_size if Path(str(path)+suffix).exists() else None} for suffix in ("-wal", "-journal", "-shm")},
        }
        db.close()
    save(f"DATABASE_{label}.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def setup(read_only):
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    os.environ.update(ENVIRONMENT)
    sys.dont_write_bytecode = True
    from django.conf import settings
    # Keep existing allowed origins and extend only this process to the original 5176 origin.
    for key in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        values = list(getattr(settings, key))
        if "http://127.0.0.1:5176" not in values:
            values.append("http://127.0.0.1:5176")
        setattr(settings, key, values)
    for alias, config in settings.DATABASES.items():
        if config["ENGINE"] != "django.db.backends.sqlite3" or Path(config["NAME"]).resolve() != DATABASES["B"].resolve():
            raise RuntimeError(f"Unexpected database target for alias {alias}; refusing startup")
        if read_only:
            config["NAME"] = DATABASES["B"].as_uri() + "?mode=ro"
            config["OPTIONS"] = {**config.get("OPTIONS", {}), "uri": True}
    import django
    django.setup()
    from django.db import connections
    if read_only:
        for connection in connections.all():
            connection.ensure_connection()
            protect_reads(connection.connection)
    return settings


def runtime(read_only):
    settings = setup(read_only)
    from django.db import connections
    from django.urls import resolve
    from django.core.management import execute_from_command_line
    from django.apps import apps
    from planning.schema import order_planning_schema_status
    from sales.source_review import ACTIONS
    result = {"recordedAt": now(), "pid": os.getpid(), "parentPid": os.getppid(), "executable": sys.executable,
              "cwd": str(Path.cwd()), "environment": ENVIRONMENT, "readOnlyPrecheck": read_only,
              "managementCommand": ["manage.py", "runserver", "127.0.0.1:8075", "--noreload", "--settings=pce_backend.settings"],
              "connections": {}, "routes": [], "sourceActions": ACTIONS,
              "allowedOrigins": {k: getattr(settings, k) for k in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS")},
              "databaseRouters": settings.DATABASE_ROUTERS}
    for alias in connections:
        with connections[alias].cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            actual = cursor.fetchall()
        if not actual or any(name != "temp" and Path(path).resolve() != DATABASES["B"].resolve() for _, name, path in actual):
            raise RuntimeError("Actual SQLite connection does not match B")
        result["connections"][alias] = {"configuredName": str(connections[alias].settings_dict["NAME"]), "databaseList": actual}
    for path in ROUTES:
        match = resolve(path)
        target = getattr(match.func, "view_class", match.func)
        file = Path(inspect.getsourcefile(inspect.unwrap(target))).resolve()
        result["routes"].append({"path": path, "handler": f"{target.__module__}.{target.__name__}",
                                 "kwargs": match.kwargs, "implementedMethods": [m.upper() for m in ("get", "post", "patch", "put", "delete") if hasattr(target, m)],
                                 "sourceFile": str(file), "sourceSha256": sha(file),
                                 "functionMethodContract": "POST (@require_http_methods)" if path == "/api/auth/login/" else None})
    result["planningSchema"] = order_planning_schema_status()
    required = ["sales.Customer", "sales.SalesOrder", "sales.SalesOrderItem", "masterdata.ExternalIdentity",
                "masterdata.MasterDataWriteRequest", "system.OrganizationOperatingAuditRecord", "planning.Demand", "planning.PlanningRequirement"]
    result["requiredModelColumns"] = {}
    for label in required:
        model = apps.get_model(label)
        with connections["default"].cursor() as cursor:
            cursor.execute(f'PRAGMA table_info("{model._meta.db_table}")')
            present = {r[1] for r in cursor.fetchall()}
        missing = sorted({f.column for f in model._meta.concrete_fields} - present)
        result["requiredModelColumns"][label] = {"table": model._meta.db_table, "missing": missing}
        if missing:
            raise RuntimeError(f"Required existing schema missing: {label}: {missing}")
    result["loadedDo4Sources"] = {str(Path(sys.modules[name].__file__).relative_to(ROOT)): sha(sys.modules[name].__file__)
        for name in ("sales.source_intake", "sales.source_review", "sales.source_semantics", "sales.whole_house_preview", "sales.views", "sales.urls")}
    execute_from_command_line(["manage.py", "check", "--settings=pce_backend.settings"])
    save("PRECHECK_LOADED.json" if read_only else "STARTUP_LOADED.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    connections.close_all()
    if not read_only:
        execute_from_command_line(result["managementCommand"])


def identities():
    setup(True)
    from system.models import User, UserRoleScopeAssignment
    from system.authorization import AuthorizationService
    from sales.source_review import source_actor, ACTIONS
    from sales.services import _workflow_actor, SalesBusinessError
    rows = []
    for user in User.objects.filter(company_id=1).only("id", "username", "company_id", "is_active", "is_superuser"):
        row = {"username": user.username, "organizationId": user.company_id, "active": user.is_active, "actions": {}}
        if user.username == "pce_sales_r13":
            employee = user.employee_profile
            row["roleBindingEvidence"] = {
                "positionCode": employee.position_ref.code,
                "positionDefaultRoleId": employee.position_ref.default_role_id,
                "positionDefaultRoleCode": employee.position_ref.default_role.code if employee.position_ref.default_role_id else None,
                "activeRoleAssignments": list(UserRoleScopeAssignment.objects.filter(user=user, organization_id=1, active=True)
                    .values("role_id", "role__code", "scope_code", "department_id")),
            }
        for code in ("sales.order.view", "sales.order.update", "sales.order.confirm", "sales.order.create"):
            decision = AuthorizationService.decide(user=user, action_code=code, organization_id=1,
                business_object={"organizationId": 1}, context={"businessWrite": code != "sales.order.view"})
            row["actions"][code] = {k: decision[k] for k in ("allowed", "decisionCode", "reason", "scope")}
        row["sourceSteps"] = {}
        departments = [None] + list(UserRoleScopeAssignment.objects.filter(user=user, organization_id=1, active=True,
            scope_code="DEPARTMENT").exclude(department_id=None).values_list("department_id", flat=True).distinct())
        for action in ACTIONS:
            checks = []
            for department in departments:
                try:
                    actor, decision = source_actor(user, action, department)
                    evidence = {k: actor[k] for k in ("organizationId", "positionCode", "responsibilityCode", "roleCode", "scopeCode", "permissionCode")}
                    checks.append({"departmentId": department, "allowed": True, "evidence": evidence})
                except SalesBusinessError as error:
                    checks.append({"departmentId": department, "allowed": False, "code": error.code, "reason": error.message})
            row["sourceSteps"][action] = checks
        try:
            employee, position, node, mapping = _workflow_actor(user, "sales.order.create")
            row["createWorkflow"] = {"allowed": True, "positionCode": position.code,
                "responsibilityCode": mapping.responsibility.code, "processCode": node.process_definition.definition_code,
                "nodeId": node.pk, "businessActionCode": node.business_action_code}
        except SalesBusinessError as error:
            row["createWorkflow"] = {"allowed": False, "code": error.code, "reason": error.message}
        rows.append(row)
    wrong_org = User.objects.filter(username="pde_acceptance").values("username", "company_id", "is_active").first()
    result = {"recordedAt": now(), "database": str(DATABASES["B"]), "mode": "SQLite mode=ro; sensitive columns denied; no authentication performed",
              "targetOrganization": 1, "accounts": rows, "historicalAccount": wrong_org,
              "note": "Eligibility checks only. No login, source action, or order creation was executed. Department scope is not proof of the historical source department."}
    save("SALES_IDENTITY_READONLY.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["before", "after", "precheck", "serve", "identities"])
    args = parser.parse_args()
    if args.mode in ("before", "after"):
        snapshot(args.mode.upper())
    elif args.mode == "identities":
        identities()
    else:
        runtime(args.mode == "precheck")
