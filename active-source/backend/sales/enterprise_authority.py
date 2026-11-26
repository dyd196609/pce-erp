"""New actions bind both permission and scope to the same formal role."""
from django.db.models import Q

from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, UserRoleScopeAssignment


FOLLOWUP_VIEW = "sales.production_followup.read"
FOLLOWUP_ASSIGN = "sales.production_followup.assign"
CUSTOMER_BIND = "sales.customer_account.bind"
CUSTOMER_PUBLISH = "sales.customer_progress.publish"
RISK_CHECK = "reconciliation.evidence_risk.check"
RISK_RECEIVE = "reconciliation.evidence_risk.receive"
RISK_CLOSE = "reconciliation.evidence_risk.close"
RISK_HANDLERS = {
    "quality": ("reconciliation.evidence_risk.quality", "质检"),
    "inventory": ("reconciliation.evidence_risk.inventory", "仓管"),
    "procurement": ("reconciliation.evidence_risk.procurement", "采购"),
    "payable": ("reconciliation.evidence_risk.payable", "财务"),
}
PERMISSIONS = {
    FOLLOWUP_VIEW: "查看本人负责的生产订单",
    FOLLOWUP_ASSIGN: "分派或移交生产跟单",
    CUSTOMER_BIND: "核实并绑定客户账号",
    CUSTOMER_PUBLISH: "发布客户订单里程碑",
    RISK_CHECK: "读取采购一致性核对",
    RISK_RECEIVE: "受理采购风险并指定处理人",
    RISK_CLOSE: "独立复核并关闭采购风险",
    **{code: f"处理{label}风险" for code, label in RISK_HANDLERS.values()},
}


def scoped_grants(user, code):
    return UserRoleScopeAssignment.objects.filter(
        user=user, active=True, organization_id=user.company_id,
        role__rolepermission__permission__code=code,
    )


def allowed(user, code, departments=(), *, owner_id=None, department_bound=False):
    if not user.is_active:
        return False
    if user.is_superuser and code in {CUSTOMER_BIND, CUSTOMER_PUBLISH, RISK_CHECK}:
        return AuthorizationService.decide(user=user, action_code=code)["allowed"]
    grants = list(scoped_grants(user, code).values_list("scope_code", "department_id"))
    if any(scope in {"ALL", "ORGANIZATION"} for scope, _ in grants):
        return True
    departments = set(departments)
    if department_bound and departments and None not in departments:
        authorized = {department for scope, department in grants if scope == "DEPARTMENT"}
        if departments <= authorized:
            return True
    return owner_id == user.pk and any(scope == "SELF" for scope, _ in grants)


def audit(actor, action, target, label, reason, before, after):
    return OrganizationOperatingAuditRecord.objects.create(
        actor=actor, organization_id=actor.company_id, action_code=action,
        target_type=target.__class__.__name__, target_id=target.pk, target_label=label,
        before_snapshot=before, after_snapshot=after, reason=reason,
    )


def history(actor, target_type, target_id):
    return OrganizationOperatingAuditRecord.objects.filter(
        organization_id=actor.company_id, target_type=target_type, target_id=target_id,
    ).select_related("actor").order_by("pk")


def audit_row(entry):
    return {
        "actionCode": entry.action_code, "actor": entry.actor.real_name,
        "at": entry.created_at.isoformat(), "reason": entry.reason,
        "before": entry.before_snapshot, "after": entry.after_snapshot,
    }
