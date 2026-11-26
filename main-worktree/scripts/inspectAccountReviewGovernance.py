"""Read-only acceptance snapshot for account and review-permission remediation."""
import argparse
import json
import os
import sqlite3
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from django.conf import settings

from pde.models import OrderCrossFunctionalReview, OrderReviewParticipantGrant
from pde.order_review_service import build_review_facts
from system.models import Permission, Role, User, UserRoleScopeAssignment


def semantic_snapshot():
    users = []
    for user in User.objects.order_by("username"):
        employee = getattr(user, "employee_profile", None)
        users.append({
            "id": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "active": user.is_active,
            "usablePassword": user.has_usable_password(),
            "lastLoginAt": user.last_login.isoformat() if user.last_login else None,
            "companyId": user.company_id,
            "employeeId": employee.pk if employee else None,
            "employeeNo": employee.employee_no if employee else None,
            "roles": list(UserRoleScopeAssignment.objects.filter(
                user=user, active=True,
            ).order_by("role__code").values_list("role__code", flat=True)),
        })
    permissions = list(Permission.objects.filter(
        code__in=[
            code
            for prefix in ("sales.order_review.", "pde.production_feasibility_review.")
            for code in (
                f"{prefix}view", f"{prefix}manage_draft",
                f"{prefix}maintain_own_opinion", f"{prefix}sign_own_items",
                f"{prefix}submit",
            )
        ],
    ).order_by("code").values("code", "name", "module"))
    roles = []
    for role in Role.objects.filter(code__in=[
        "crm_order_review_participant",
        "pde_production_feasibility_review_participant",
    ]).order_by("code"):
        roles.append({
            "code": role.code,
            "permissions": list(role.rolepermission_set.order_by(
                "permission__code",
            ).values_list("permission__code", flat=True)),
            "users": list(UserRoleScopeAssignment.objects.filter(
                role=role, active=True,
            ).order_by("user__username").values_list("user__username", flat=True)),
        })
    grants = list(OrderReviewParticipantGrant.objects.select_related(
        "review", "user", "employee",
    ).order_by("pk"))
    grant_rows = [{
        "id": row.pk,
        "reviewType": row.review.review_type,
        "reviewId": row.review_id,
        "reviewVersion": row.review_version_snapshot,
        "sourceVersion": row.source_version_snapshot,
        "username": row.user.username,
        "employeeNo": row.employee.employee_no,
        "active": row.active,
        "capabilities": {
            "view": row.can_view,
            "maintainOwnOpinion": row.can_maintain_own_opinion,
            "signOwnItems": row.can_sign_own_items,
        },
    } for row in grants]
    runtime_access = []
    for grant in grants:
        try:
            facts = build_review_facts(
                user=grant.user,
                review_type=grant.review.review_type,
                source_record_id=grant.review.source_record_id,
            )
            authorization = facts["authorization"]
            runtime_access.append({
                "username": grant.user.username,
                "reviewId": grant.review_id,
                "view": authorization["view"]["executable"],
                "maintainOwnOpinion": authorization["ownOpinion"]["executable"],
                "signOwnItems": authorization["sign"]["executable"],
                "manageFullDraft": authorization["fullDraftEdit"]["executable"],
                "submit": authorization["submit"]["executable"],
                "scopeLabel": authorization["scopeLabel"],
            })
        except Exception as error:
            runtime_access.append({
                "username": grant.user.username,
                "reviewId": grant.review_id,
                "errorType": type(error).__name__,
                "errorCode": getattr(error, "code", "READ_FAILED"),
            })
    review = OrderCrossFunctionalReview.objects.filter(pk=1).first()
    review_row = None
    if review:
        review_row = {
            "id": review.pk,
            "reviewType": review.review_type,
            "recordStatus": review.record_status,
            "reviewVersion": review.review_version,
            "sourceVersion": review.source_version,
            "itemCount": review.items.count(),
            "agreeCount": review.items.filter(decision="AGREE", is_removed=False).count(),
            "disagreeCount": review.items.filter(decision="DISAGREE", is_removed=False).count(),
            "signedCount": review.items.filter(signature_status="SIGNED", is_removed=False).count(),
            "item01": None,
        }
        item = review.items.select_related("responsible_employee").filter(item_code="01").first()
        if item:
            review_row["item01"] = {
                "id": item.pk,
                "decision": item.decision,
                "signatureStatus": item.signature_status,
                "signedEmployeeNo": item.signed_employee_no_snapshot,
                "signedEmployeeName": item.signed_employee_name_snapshot,
                "signedAt": item.signed_at.isoformat() if item.signed_at else None,
                "responsibleEmployeeNo": item.responsible_employee.employee_no if item.responsible_employee else None,
            }
    return {
        "databasePath": str(Path(settings.DATABASES["default"]["NAME"]).resolve()),
        "users": users,
        "reviewPermissions": permissions,
        "reviewRoles": roles,
        "participantGrants": grant_rows,
        "reviewRuntimeAccess": runtime_access,
        "review1": review_row,
    }


def raw_rows(connection, table):
    cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')
    return cursor.fetchall()


def compare_database(before_path, current_path):
    before = sqlite3.connect(before_path)
    current = sqlite3.connect(current_path)
    try:
        before_passwords = dict(before.execute(
            'SELECT id, password FROM "user_system" ORDER BY id'
        ).fetchall())
        current_passwords = dict(current.execute(
            'SELECT id, password FROM "user_system" ORDER BY id'
        ).fetchall())
        review_tables = [
            OrderCrossFunctionalReview._meta.db_table,
            OrderCrossFunctionalReview._meta.get_field("items").related_model._meta.db_table,
            OrderReviewParticipantGrant._meta.db_table,
        ]
        return {
            "userIdSetUnchanged": set(before_passwords) == set(current_passwords),
            "allPasswordHashesUnchanged": before_passwords == current_passwords,
            "changedPasswordUserIds": sorted(
                user_id for user_id in set(before_passwords) | set(current_passwords)
                if before_passwords.get(user_id) != current_passwords.get(user_id)
            ),
            "reviewBusinessTablesUnchanged": {
                table: raw_rows(before, table) == raw_rows(current, table)
                for table in review_tables
            },
        }
    finally:
        before.close()
        current.close()


parser = argparse.ArgumentParser()
parser.add_argument("--compare-db")
args = parser.parse_args()
snapshot = semantic_snapshot()
if args.compare_db:
    snapshot["comparison"] = compare_database(
        str(Path(args.compare_db).resolve()), snapshot["databasePath"],
    )
print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
