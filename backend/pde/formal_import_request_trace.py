"""Sanitized trace captured from a real formal-import HTTP request."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from django.contrib.sessions.models import Session

from pfm.models import Employee
from pce_backend.identity_context import database_identity


def build_actor_request_trace(request, *, entity, phase):
    user = request.user
    database = database_identity()
    employee = Employee.objects.select_related(
        "department_ref", "position_ref", "position_ref__default_role"
    ).filter(user=user).first()
    auth = getattr(request, "pce_auth_context", {}) or {}
    session_user_id = request.session.get("_auth_user_id") if hasattr(request, "session") else None
    return {
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "source": "ACTUAL_HTTP_REQUEST",
        "phase": phase,
        "entity": entity,
        "requestUserId": user.pk,
        "requestUsername": user.username,
        "stableIdentity": f"system.User:{user.username}",
        "authenticationBackend": auth.get("backend") or "django-session-or-test-auth",
        "jwtSubject": auth.get("jwtSubject"),
        "jwtUserId": auth.get("jwtUserId"),
        "jwtUsername": auth.get("jwtUsername"),
        "jwtStableIdentity": auth.get("jwtStableIdentity"),
        "sessionUserId": session_user_id,
        "sessionExists": bool(session_user_id and Session.objects.filter(session_key=request.session.session_key).exists()),
        "databaseAlias": database["databaseAlias"],
        "databasePath": database["databasePath"],
        "databaseContext": database["databaseContext"],
        "organizationId": user.company_id,
        "companyId": user.company_id,
        "employeeInputUserId": user.pk,
        "resolvedEmployeeId": employee.pk if employee else None,
        "resolvedEmployeeNo": employee.employee_no if employee else None,
        "employmentStatus": employee.status if employee else None,
        "positionId": employee.position_ref_id if employee else None,
        "positionCode": employee.position_ref.code if employee and employee.position_ref else None,
        "roleId": employee.position_ref.default_role_id if employee and employee.position_ref else None,
    }


def append_rehearsal_trace(trace, *, outcome, error_code=None):
    """Append only when an explicit isolated-rehearsal trace path is configured."""
    configured = os.environ.get("PCE_FORMAL_IMPORT_ACTOR_TRACE_PATH", "").strip()
    if not configured:
        return
    target = Path(configured).resolve()
    production = (Path(__file__).resolve().parents[1] / "db.sqlite3").resolve()
    if Path(trace["databasePath"]).resolve() == production:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {**trace, "outcome": outcome, "errorCode": error_code}
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
