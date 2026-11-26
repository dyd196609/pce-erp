from datetime import date

from django.utils import timezone

from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    Permission,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
)

from .definition_service import WorkflowDefinitionCatalogService, WorkflowDefinitionError
from .models import ProcessDefinition


EXECUTION_RESOLUTION_CONTRACT = "PCE-WORKFLOW-EXECUTOR-RESOLUTION-V1.0"


def _effective(row, today):
    return (
        row.active
        and (row.effective_from is None or row.effective_from <= today)
        and (row.effective_to is None or row.effective_to >= today)
    )


class WorkflowExecutionResolutionService:
    """Resolve the existing permission, responsibility, position and account facts for a definition."""

    @classmethod
    def resolve(cls, *, user, definition_id):
        authorization = WorkflowDefinitionCatalogService.authorize(user)
        definition = ProcessDefinition.objects.prefetch_related("nodes").filter(pk=definition_id).first()
        if not definition:
            raise WorkflowDefinitionError("OBJECT_NOT_FOUND", "流程定义不存在。", http_status=404)
        today = date.today()
        node_results = [
            cls._resolve_node(node=node, definition=definition, today=today)
            for node in definition.nodes.order_by("sequence", "node_code")
        ]
        return {
            "contractVersion": EXECUTION_RESOLUTION_CONTRACT,
            "definition": {
                "id": definition.pk,
                "definitionCode": definition.definition_code,
                "definitionName": definition.definition_name,
                "active": definition.active,
            },
            "nodes": node_results,
            "metrics": {
                "formalNodeCount": len(node_results),
                "configuredNodeCount": sum(bool(row["assignments"]) for row in node_results),
                "resolvedPositionNodeCount": sum(bool(row["positions"]) for row in node_results),
                "resolvedEmployeeNodeCount": sum(bool(row["employees"]) for row in node_results),
                "resolvedAccountNodeCount": sum(bool(row["accounts"]) for row in node_results),
                "permissionMatchedNodeCount": sum(row["permission"]["exists"] for row in node_results),
                "executableNodeCount": sum(row["executable"] for row in node_results),
                "rolePermissionGapCount": sum("ROLE_PERMISSION_MISSING" in row["issueCodes"] for row in node_results),
                "positionResponsibilityGapCount": sum("POSITION_RESPONSIBILITY_MISSING" in row["issueCodes"] for row in node_results),
                "positionIncumbencyGapCount": sum("POSITION_EMPLOYEE_MISSING" in row["issueCodes"] for row in node_results),
                "accountGapCount": sum("EMPLOYEE_ACCOUNT_MISSING" in row["issueCodes"] for row in node_results),
                "pendingConfirmationCount": sum(not row["executable"] for row in node_results),
            },
            "authorization": authorization,
            "resolvedAt": timezone.now().isoformat(),
        }

    @staticmethod
    def _resolve_node(*, node, definition, today):
        permission = Permission.objects.filter(code=node.business_action_code).first()
        roles = list(
            Role.objects.filter(rolepermission__permission=permission).order_by("code").distinct()
        ) if permission else []
        role_codes = {role.code for role in roles}
        mappings = list(
            PositionWorkflowResponsibility.objects.select_related(
                "position__department", "position__job_level", "position__default_role",
                "responsibility", "workflow_node"
            ).filter(workflow_node=node).order_by("position__code", "ownership_type")
        )
        assignments = []
        all_positions = []
        all_employees = []
        all_accounts = []
        issue_codes = []
        if not definition.active:
            issue_codes.append("PROCESS_INACTIVE")
        if not node.active:
            issue_codes.append("NODE_INACTIVE")
        if not permission:
            issue_codes.append("PERMISSION_MISSING")
        if not mappings:
            issue_codes.append("WORKFLOW_RESPONSIBILITY_MISSING")

        for mapping in mappings:
            position = mapping.position
            responsibility = mapping.responsibility
            mapping_effective = _effective(mapping, today)
            responsibility_valid = bool(
                responsibility
                and responsibility.is_active
                and responsibility.status == Responsibility.Status.ACTIVE
            )
            position_responsibility_valid = bool(
                responsibility_valid
                and position.responsibility_mappings.filter(
                    responsibility=responsibility, active=True,
                ).exists()
            )
            position_valid = position.is_active
            if not position_responsibility_valid:
                issue_codes.append("POSITION_RESPONSIBILITY_MISSING")
            employee_rows = []
            employees = list(
                formal_employee_queryset(
                    Employee.objects.select_related("user", "department_ref", "position_ref"),
                    company_id=position.company_id,
                ).filter(position_ref=position).order_by("employee_no")
            ) if position_valid and mapping_effective and position_responsibility_valid else []
            if not employees:
                issue_codes.append("POSITION_EMPLOYEE_MISSING")
            for employee in employees:
                user_row = employee.user
                account_exists = bool(user_row and user_row.is_active)
                authority_role_codes = set()
                matched_role_codes = set()
                decision = None
                executable = False
                if account_exists:
                    evidence = AuthorizationService.authority_evidence(
                        user_row, str(position.company_id)
                    )
                    authority_role_codes = {row.role_code for row in evidence}
                    matched_role_codes = role_codes & authority_role_codes
                    decision = AuthorizationService.decide(
                        user=user_row,
                        action_code=node.business_action_code,
                        organization_id=str(position.company_id),
                        business_object={
                            "departmentId": position.department_id,
                            "ownerUserId": user_row.pk,
                        },
                    )
                    executable = bool(
                        definition.active
                        and node.active
                        and permission
                        and mapping_effective
                        and position_valid
                        and responsibility_valid
                        and position_responsibility_valid
                        and decision["allowed"]
                        and (user_row.is_superuser or matched_role_codes)
                    )
                    all_accounts.append({
                        "id": user_row.pk,
                        "username": user_row.username,
                        "realName": user_row.real_name,
                        "active": user_row.is_active,
                        "roleCodes": sorted(authority_role_codes),
                        "matchedRoleCodes": sorted(matched_role_codes),
                        "authorizationDecision": decision["decisionCode"],
                        "executable": executable,
                    })
                else:
                    pass
                employee_payload = {
                    "id": employee.pk,
                    "employeeNo": employee.employee_no,
                    "fullName": employee.full_name,
                    "status": employee.status,
                    "departmentId": employee.department_ref_id,
                    "departmentName": employee.department_ref.name if employee.department_ref else "",
                    "accountId": user_row.pk if user_row else None,
                    "username": user_row.username if user_row else "",
                    "accountActive": user_row.is_active if user_row else False,
                    "roleCodes": sorted(authority_role_codes),
                    "matchedRoleCodes": sorted(matched_role_codes),
                    "executable": executable,
                }
                employee_rows.append(employee_payload)
                all_employees.append(employee_payload)
            position_payload = {
                "id": position.pk,
                "code": position.code,
                "name": position.name,
                "active": position.is_active,
                "departmentId": position.department_id,
                "departmentName": position.department.name if position.department else "",
                "jobLevelCode": position.job_level.code if position.job_level else "",
                "defaultRoleCode": position.default_role.code if position.default_role else "",
            }
            all_positions.append(position_payload)
            assignments.append({
                "id": mapping.pk,
                "workflowNodeId": mapping.workflow_node_id,
                "ownershipType": mapping.ownership_type,
                "active": mapping.active,
                "effective": mapping_effective,
                "position": position_payload,
                "responsibility": {
                    "id": responsibility.pk if responsibility else None,
                    "code": responsibility.code if responsibility else "",
                    "name": responsibility.name if responsibility else "",
                    "status": responsibility.status if responsibility else "",
                    "active": responsibility.is_active if responsibility else False,
                },
                "positionResponsibilityValid": position_responsibility_valid,
                "employees": employee_rows,
            })

        executable = any(account["executable"] for account in all_accounts)
        if mappings and not all_accounts:
            issue_codes.append("EMPLOYEE_ACCOUNT_MISSING")
        if mappings and all_accounts and not executable:
            issue_codes.append("ROLE_PERMISSION_MISSING")
        issue_codes = sorted(set(issue_codes))
        return {
            "nodeId": node.pk,
            "nodeCode": node.node_code,
            "nodeName": node.node_name,
            "sequence": node.sequence,
            "active": node.active,
            "businessActionCode": node.business_action_code,
            "permission": {
                "exists": bool(permission),
                "id": permission.pk if permission else None,
                "code": permission.code if permission else node.business_action_code,
                "name": permission.name if permission else "",
            },
            "roles": [{"id": role.pk, "code": role.code, "name": role.name} for role in roles],
            "assignments": assignments,
            "positions": all_positions,
            "employees": all_employees,
            "accounts": all_accounts,
            "executable": executable,
            "issueCodes": issue_codes,
            "reason": "至少一个在职员工账户通过正式角色权限校验。" if executable else "；".join(issue_codes) or "无可执行账户。",
        }
