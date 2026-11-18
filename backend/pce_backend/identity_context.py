"""Stable authentication identity bound to the active database runtime."""

from hashlib import sha256
import hmac
import json
from pathlib import Path

from django.conf import settings
from django.db import connections


AUTH_CONTEXT_VERSION = "PCE-AUTH-DB-CONTEXT-V1"


def database_identity(alias="default"):
    configured = settings.DATABASES[alias]["NAME"]
    resolved = str(Path(configured).resolve())
    instance_id = None
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT after_snapshot FROM system_organization_operating_audits "
                "WHERE action_code = %s ORDER BY id DESC LIMIT 1",
                ["BOOTSTRAP_FORMAL_IMPORT_REHEARSAL_ACTOR"],
            )
            row = cursor.fetchone()
        snapshot = json.loads(row[0]) if row and isinstance(row[0], str) else (row[0] if row else {})
        instance_id = (snapshot or {}).get("databaseBindingId")
    except Exception:
        instance_id = None
    binding = instance_id or f"PATH:{resolved}"
    digest = sha256(f"{alias}\0{resolved}\0{binding}".encode("utf-8")).hexdigest()
    return {
        "version": AUTH_CONTEXT_VERSION,
        "databaseAlias": alias,
        "databasePath": resolved,
        "databaseContext": digest,
        "databaseInstanceId": instance_id,
    }


def jwt_identity_claims(user):
    database = database_identity()
    return {
        "username": user.username,
        "stable_identity": f"system.User:{user.username}",
        "database_context": database["databaseContext"],
        "database_alias": database["databaseAlias"],
        "auth_context_version": AUTH_CONTEXT_VERSION,
        # Bind an issued JWT to the current credential without exposing the
        # password hash itself.  A controlled password reset therefore
        # invalidates every older browser-tab token immediately.
        "credential_context": hmac.new(
            str(settings.JWT_SECRET_KEY).encode("utf-8"),
            str(user.password or "").encode("utf-8"),
            sha256,
        ).hexdigest(),
    }


def credential_context_matches(user, claimed):
    expected = jwt_identity_claims(user)["credential_context"]
    return bool(claimed) and hmac.compare_digest(str(claimed), expected)
