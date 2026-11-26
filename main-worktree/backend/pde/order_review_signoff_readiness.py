"""Controlled preparation of exact-object sign-off participants for review #1.

The service creates no review decision, signature or submission.  It creates or
reuses one-to-one employee login identities and grants only review-object
capabilities; it never adds ``sales.order.update`` or changes shared roles.
"""

from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pce_backend.identity_context import database_identity
from pde.acceptance_isolation import verify_acceptance_connections
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, User

from .models import OrderCrossFunctionalReview, OrderReviewParticipantGrant
from .order_review_service import _audit, summarize_items


EXPECTED_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
EXPECTED_DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
EXPECTED_COMPANY_ID = 1
EXPECTED_COMPANY_CODE = "COMP001"
EXPECTED_REVIEW_ID = 1
EXPECTED_REVIEW_TYPE = "CRM_ORDER_REVIEW"
VERSION = "PCE-REVIEW-SIGNOFF-READINESS-V1"
NEW_ACCOUNT_USERNAMES = {
    "EMP111": "pce_review_emp111",
    "EMP096": "pce_review_emp096",
    "EMP110": "pce_review_emp110",
    "EMP009": "pce_review_emp009",
}
EXPECTED_EXISTING_ACCOUNTS = {
    "EMP003": "pce_finance_r14",
    "EMP-R12-PLAN": "pce_plan_r12",
    "EMP-R13-SALES": "pce_sales_r13",
}


class SignoffReadinessError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _hash(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _review_snapshot(review):
    items = list(review.items.select_related("responsible_employee", "signed_by_user", "review").filter(is_removed=False))
    return {
        "id": review.pk, "companyId": review.company_id, "reviewType": review.review_type,
        "reviewVersion": review.review_version, "sourceRecordId": review.source_record_id,
        "sourceOrderNo": review.source_order_no, "sourceVersion": review.source_version,
        "recordStatus": review.record_status, "conclusion": review.conclusion,
        "summary": summarize_items(items),
        "items": [{"id": row.pk, "itemCode": row.item_code, "decision": row.decision,
            "reasonCode": row.disagreement_reason_code, "reasonText": row.disagreement_reason_text,
            "responsibleEmployeeId": row.responsible_employee_id,
            "responsibleEmployeeNo": row.responsible_employee.employee_no if row.responsible_employee else "",
            "responsibleEmployeeName": row.responsible_employee.full_name if row.responsible_employee else "",
            "signatureStatus": row.signature_status, "signedByUserId": row.signed_by_user_id}
            for row in items],
    }


def _employee_snapshot(employee):
    account = employee.user
    return {
        "employeeId": employee.pk, "employeeNo": employee.employee_no, "name": employee.full_name,
        "status": employee.status, "departmentId": employee.department_ref_id,
        "department": employee.department_ref.name if employee.department_ref else employee.department_name,
        "positionId": employee.position_ref_id,
        "position": employee.position_ref.name if employee.position_ref else employee.position,
        "account": ({"userId": account.pk, "username": account.username, "active": account.is_active,
            "realName": account.real_name, "companyId": account.company_id,
            "usablePassword": account.has_usable_password(),
            "lastLogin": account.last_login.isoformat() if account.last_login else None} if account else None),
    }


def _assert_environment():
    actual = Path(settings.DATABASES["default"]["NAME"]).resolve()
    try:
        verified = verify_acceptance_connections(settings.DATABASES)
    except ValueError as exc:
        raise SignoffReadinessError("DATABASE_MISMATCH", "仅允许在指定非生产B库执行签认准备。") from exc
    if actual != EXPECTED_DATABASE.resolve() or verified["databaseIdentity"] != EXPECTED_IDENTITY:
        raise SignoffReadinessError("DATABASE_MISMATCH", "仅允许在指定非生产B库执行签认准备。")


def _load_review(lock=False):
    query = OrderCrossFunctionalReview.objects.select_related("company", "source_record", "reviewer")
    if lock:
        query = query.select_for_update()
    review = query.filter(pk=EXPECTED_REVIEW_ID).first()
    if not review or review.company_id != EXPECTED_COMPANY_ID or review.company.code != EXPECTED_COMPANY_CODE:
        raise SignoffReadinessError("REVIEW_IDENTITY_DRIFT", "评审#1或COMP001身份不符合已批准范围。")
    if review.review_type != EXPECTED_REVIEW_TYPE or review.record_status != "DRAFT":
        raise SignoffReadinessError("REVIEW_STATE_DRIFT", "评审#1已不再是当前订单评审草稿，停止配置。")
    return review


def readback():
    _assert_environment()
    review = _load_review()
    employees = list(Employee.objects.select_related("user", "department_ref", "position_ref")
        .filter(pk__in=review.items.filter(is_removed=False).values_list("responsible_employee_id", flat=True).distinct())
        .order_by("employee_no"))
    grants = {row.employee_id: row for row in OrderReviewParticipantGrant.objects.filter(review=review).select_related("user")}
    participant_rows = []
    for employee in employees:
        account = employee.user
        generic_view = AuthorizationService.decide(user=account, action_code="sales.order.view",
            organization_id=review.company_id, business_object={"companyId": review.company_id}) if account else None
        generic_update = AuthorizationService.decide(user=account, action_code="sales.order.update",
            organization_id=review.company_id, business_object={"companyId": review.company_id}) if account else None
        participant_rows.append({**_employee_snapshot(employee), "genericPermissions": {
            "sales.order.view": bool(generic_view and generic_view["allowed"]),
            "sales.order.update": bool(generic_update and generic_update["allowed"]),
        }, "grant": ({
            "id": grants[employee.pk].pk, "reviewId": grants[employee.pk].review_id,
            "reviewVersion": grants[employee.pk].review_version_snapshot,
            "sourceVersion": grants[employee.pk].source_version_snapshot,
            "canView": grants[employee.pk].can_view,
            "canMaintainOwnOpinion": grants[employee.pk].can_maintain_own_opinion,
            "canSignOwnItems": grants[employee.pk].can_sign_own_items,
            "active": grants[employee.pk].active,
        } if employee.pk in grants else None)})
    organization_audits = list(OrganizationOperatingAuditRecord.objects.filter(
        organization_id=review.company_id,
        reason="用户已批准订单评审#1责任人签认阻断最小处理",
    ).order_by("id").values("id", "action_code", "target_type", "target_id", "created_at"))
    review_audits = list(review.item_audits.filter(action="SIGNOFF_GRANT_CREATED")
        .order_by("id").values("id", "action", "actor_id", "created_at"))
    return {
        "contractVersion": VERSION,
        "database": {"identity": EXPECTED_IDENTITY, "binding": database_identity(),
            "path": str(Path(settings.DATABASES["default"]["NAME"]).resolve()), "nonProduction": True},
        "review": _review_snapshot(review),
        "participants": participant_rows,
        "audits": {"organization": organization_audits, "reviewGrant": review_audits},
    }


@transaction.atomic
def apply(*, actor_username="admin"):
    _assert_environment()
    actor = User.objects.select_for_update().filter(username=actor_username, company_id=EXPECTED_COMPANY_ID, is_active=True, is_superuser=True).first()
    if not actor:
        raise SignoffReadinessError("TECHNICAL_ACTOR_REQUIRED", "未找到COMP001当前有效技术管理员，不能执行受控配置。")
    review = _load_review(lock=True)
    before = readback()
    before_review_hash = _hash(before["review"])
    participants = list(Employee.objects.select_for_update().select_related("user", "department_ref", "position_ref")
        .filter(pk__in=review.items.filter(is_removed=False).values_list("responsible_employee_id", flat=True).distinct())
        .order_by("employee_no"))
    if len(participants) != 7 or any(row.status != "active" for row in participants):
        raise SignoffReadinessError("PARTICIPANT_SET_DRIFT", "责任人集合不再是7名有效员工，停止配置并保留新事实。")

    changes = {"accountsCreated": [], "accountsReused": [], "employeeLinksCreated": [], "grantsCreated": [], "grantsReused": []}
    reason = "用户已批准订单评审#1责任人签认阻断最小处理"
    for employee in participants:
        expected_existing = EXPECTED_EXISTING_ACCOUNTS.get(employee.employee_no)
        new_username = NEW_ACCOUNT_USERNAMES.get(employee.employee_no)
        if not expected_existing and not new_username:
            raise SignoffReadinessError("PARTICIPANT_IDENTITY_UNEXPECTED", f"{employee.employee_no}不在已批准账号对象中。")
        account = employee.user
        expected_username = expected_existing or new_username
        username_owner = User.objects.select_for_update().filter(username=expected_username).first()
        if account and account.username != expected_username:
            raise SignoffReadinessError("EMPLOYEE_ACCOUNT_CONFLICT", f"{employee.employee_no}已绑定非预期账号。")
        if username_owner and (not account or username_owner.pk != account.pk):
            raise SignoffReadinessError("USERNAME_COLLISION", f"账号{expected_username}已属于其他身份。")
        if not account:
            account = User(username=expected_username, real_name=employee.full_name,
                company_id=review.company_id, is_active=True, is_staff=False)
            account.set_unusable_password()
            account.full_clean(); account.save()
            changes["accountsCreated"].append(account.pk)
            OrganizationOperatingAuditRecord.objects.create(
                action_code="CREATE_REVIEW_PARTICIPANT_USER", actor=actor, organization_id=review.company_id,
                target_type="User", target_id=account.pk, target_label=f"{account.username} - {account.real_name}",
                reason=reason, before_snapshot={"formalizationVersion": VERSION},
                after_snapshot={"username": account.username, "realName": account.real_name,
                    "companyId": account.company_id, "active": True,
                    "credentialState": "PENDING_SECURE_INITIALIZATION", "formalizationVersion": VERSION})
            employee.user = account; employee.full_clean(); employee.save(update_fields=["user", "updated_at"])
            changes["employeeLinksCreated"].append(employee.pk)
            OrganizationOperatingAuditRecord.objects.create(
                action_code="SAVE_EMPLOYEE_ACCOUNT", actor=actor, organization_id=review.company_id,
                target_type="EmployeeAccount", target_id=employee.pk,
                target_label=f"{employee.employee_no} {employee.full_name}", reason=reason,
                before_snapshot={"userId": None, "formalizationVersion": VERSION},
                after_snapshot={"userId": account.pk, "username": account.username, "formalizationVersion": VERSION})
        else:
            if not account.is_active or account.company_id != review.company_id:
                raise SignoffReadinessError("EMPLOYEE_ACCOUNT_INVALID", f"{employee.employee_no}既有账号状态或公司不匹配。")
            changes["accountsReused"].append(account.pk)

        grant = OrderReviewParticipantGrant.objects.select_for_update().filter(review=review, employee=employee, user=account).first()
        grant_payload = {"reviewId": review.pk, "companyId": review.company_id,
            "employeeId": employee.pk, "userId": account.pk, "reviewVersion": review.review_version,
            "sourceVersion": review.source_version, "capabilities": ["VIEW_REVIEW", "MAINTAIN_OWN_OPINION", "SIGN_OWN_ITEMS"],
            "scope": "CURRENT_REVIEW_CURRENT_VERSION_OWN_ASSIGNED_ITEMS", "reason": reason}
        if not grant:
            grant = OrderReviewParticipantGrant.objects.create(
                review=review, company_id=review.company_id, employee=employee, user=account,
                review_version_snapshot=review.review_version, source_version_snapshot=review.source_version,
                can_view=True, can_maintain_own_opinion=True, can_sign_own_items=True,
                active=True, reason=reason, created_by=actor,
                audit_hash=_hash({**grant_payload, "at": timezone.now().isoformat()}),
            )
            changes["grantsCreated"].append(grant.pk)
            _audit(review, actor, "SIGNOFF_GRANT_CREATED", None, {}, {**grant_payload, "grantId": grant.pk})
        else:
            expected = (grant.company_id == review.company_id and grant.review_version_snapshot == review.review_version
                and grant.source_version_snapshot == review.source_version and grant.can_view
                and grant.can_maintain_own_opinion and grant.can_sign_own_items and grant.active)
            if not expected:
                raise SignoffReadinessError("EXISTING_GRANT_DRIFT", f"{employee.employee_no}既有评审授权与批准范围不一致。")
            changes["grantsReused"].append(grant.pk)

    after = readback()
    if _hash(after["review"]) != before_review_hash:
        raise SignoffReadinessError("REVIEW_CONTENT_CHANGED", "配置过程意外改变评审#1业务内容，事务已回滚。")
    return {"before": before, "after": after, "changes": changes,
        "proof": {"sharedRolesChanged": False, "genericSalesOrderUpdateGranted": False,
            "reviewSignaturesCreated": False, "reviewSubmitted": False}}
