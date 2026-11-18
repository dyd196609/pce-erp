"""Shared authorization and audit control for the formal PR -> PO workflow."""

from system.authorization import AuthorizationService
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import WorkflowNodeDefinition


PROCESS_CODE = "PROCUREMENT_PURCHASE_REQUEST_TO_ORDER"


def authorize_action(*, user, action_code, organization_id, business_object=None, context=None):
    return AuthorizationService.decide(
        user=user,
        action_code=action_code,
        organization_id=organization_id,
        business_object=business_object or {},
        context=context or {},
    )


def _actor_facts(user):
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    return {
        "account": {
            "userId": user.pk,
            "username": user.get_username(),
            "realName": str(getattr(user, "real_name", "") or ""),
        },
        "employee": {
            "id": employee.pk if employee else None,
            "employeeNo": employee.employee_no if employee else "",
            "name": employee.full_name if employee else "",
        },
        "position": {
            "id": position.pk if position else None,
            "code": position.code if position else "",
            "name": position.name if position else "",
        },
    }


def _workflow_node(action_code):
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        process_definition__definition_code=PROCESS_CODE,
        process_definition__active=True,
        business_action_code=action_code,
        active=True,
    ).order_by("sequence", "pk").first()
    if not node:
        return {"processCode": PROCESS_CODE, "nodeId": None, "nodeCode": "", "nodeName": ""}
    return {
        "processCode": node.process_definition.definition_code,
        "nodeId": node.pk,
        "nodeCode": node.node_code,
        "nodeName": node.node_name,
        "sequence": node.sequence,
    }


def record_action_audit(
    *, user, action_code, organization_id, target_type, target_id, target_no,
    before, after, authorization, reason="系统流程验收数据",
):
    organization = Company.objects.get(pk=organization_id)
    common = {
        **_actor_facts(user),
        "workflowNode": _workflow_node(action_code),
        "document": {"type": target_type, "id": target_id, "no": target_no},
        "authorization": {
            "allowed": bool(authorization.get("allowed")),
            "decisionCode": authorization.get("decisionCode", ""),
            "scope": authorization.get("scope", {}),
            "roleCodes": authorization.get("roleCodes", []),
            "permissionCodes": authorization.get("permissionCodes", []),
            "authoritySource": authorization.get("authoritySource", ""),
        },
    }
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code,
        actor=user,
        organization=organization,
        target_type=target_type,
        target_id=target_id,
        target_label=str(target_no)[:200],
        reason=str(reason)[:300],
        before_snapshot={**common, "state": before, "result": "committed"},
        after_snapshot={**common, "state": after, "result": "committed"},
    )
