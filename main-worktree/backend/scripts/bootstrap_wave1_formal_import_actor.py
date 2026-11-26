"""Bootstrap or disable Wave 1 formal-import rehearsal actors in an isolated DB."""

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from django.contrib.sessions.models import Session

from pfm.models import Employee
from pde.formal_import_actor_context import bootstrap_rehearsal_actors
from system.models import (
    Company, Position, PositionResponsibility, Responsibility, User,
    UserRoleScopeAssignment,
)


PRODUCTION_DB = (Path(__file__).resolve().parents[1] / "db.sqlite3").resolve()


def isolated_database():
    configured = os.environ.get("PCE_DATABASE_PATH")
    if not configured:
        raise RuntimeError("PCE_DATABASE_PATH must explicitly name the isolated rehearsal DB")
    actual = Path(configured).resolve()
    if actual == PRODUCTION_DB:
        raise RuntimeError("refusing to modify the Production DB")
    return actual


def cleanup(*, run_id, maintenance_username, readonly_username):
    users = User.objects.filter(username__in=(maintenance_username, readonly_username))
    user_ids = list(users.values_list("pk", flat=True))
    UserRoleScopeAssignment.objects.filter(user_id__in=user_ids).update(active=False)
    Employee.objects.filter(user_id__in=user_ids).update(status="inactive")
    for user in users:
        user.is_active = False
        user.set_unusable_password()
        user.save(update_fields=("is_active", "password", "updated_at"))
    responsibilities = Responsibility.objects.filter(description__contains=f"REHEARSAL:{run_id}")
    PositionResponsibility.objects.filter(responsibility__in=responsibilities).update(active=False)
    responsibilities.update(is_active=False, status=Responsibility.Status.SUSPENDED)
    Position.objects.filter(description__contains=f"REHEARSAL:{run_id}").update(is_active=False)
    deleted_sessions, _ = Session.objects.all().delete()
    return {
        "maintenanceUsersDisabled": User.objects.filter(pk__in=user_ids, is_active=False).count(),
        "employeesInactive": Employee.objects.filter(user_id__in=user_ids, status="inactive").count(),
        "positionsDisabled": Position.objects.filter(description__contains=f"REHEARSAL:{run_id}", is_active=False).count(),
        "responsibilitiesDisabled": responsibilities.filter(is_active=False).count(),
        "sessionsDeleted": deleted_sessions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bootstrap", "cleanup"), default="bootstrap")
    parser.add_argument("--run-id", default="W1FIAC-20260911-001")
    parser.add_argument("--acceptance-label", default="A4")
    parser.add_argument("--maintenance-username", default="wave1_import_maintenance_a4")
    parser.add_argument("--readonly-username", default="wave1_import_readonly_a4")
    args = parser.parse_args()
    database = isolated_database()
    if args.mode == "cleanup":
        result = cleanup(
            run_id=args.run_id,
            maintenance_username=args.maintenance_username,
            readonly_username=args.readonly_username,
        )
    else:
        maintenance_password = os.environ.get("PCE_REHEARSAL_MAINTENANCE_PASSWORD")
        readonly_password = os.environ.get("PCE_REHEARSAL_READONLY_PASSWORD")
        company = Company.objects.get(code="COMP001")
        actors = bootstrap_rehearsal_actors(
            company=company,
            run_id=args.run_id,
            maintenance_username=args.maintenance_username,
            maintenance_password=maintenance_password,
            readonly_username=args.readonly_username,
            readonly_password=readonly_password,
            acceptance_label=args.acceptance_label,
            database_binding_id=str(uuid.uuid4()),
        )
        # Stale sessions copied from another isolated database must never select
        # an identity by an obsolete numeric user id.
        deleted_sessions, _ = Session.objects.all().delete()
        result = {
            "maintenanceUserId": actors["maintenance"].pk,
            "readonlyUserId": actors["readonly"].pk,
            "actorContext": actors["context"],
            "sessionsDeleted": deleted_sessions,
        }
    print(json.dumps({
        "gate": "WAVE1_FORMAL_IMPORT_ACTOR_BOOTSTRAP",
        "status": "PASS",
        "mode": args.mode,
        "database": str(database),
        "productionDatabaseUsed": False,
        "runId": args.run_id,
        "result": result,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({
            "gate": "WAVE1_FORMAL_IMPORT_ACTOR_BOOTSTRAP",
            "status": "FAIL", "error": str(exc),
        }, ensure_ascii=False, indent=2))
        raise
