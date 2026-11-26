from django.db.models import Count, Prefetch

from pfm.formal_employee import formal_employee_queryset
from pfm.models import (
    Employee,
    EmployeeReportingRelation,
    OrganizationLeadershipAssignment,
)
from workflow_runtime.models import WorkflowNodeDefinition

from .models import (
    Company,
    Department,
    JobFamily,
    JobLevel,
    OrganizationOperatingAuditRecord,
    OrganizationUnit,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
)


ENTERPRISE_ORGANIZATION_MODEL_CONTRACT = "PCE-ENTERPRISE-ORGANIZATION-MODEL-V1"


def _date(value):
    return value.isoformat() if value else None


def _status_label(active):
    return "启用" if active else "停用"


class EnterpriseOrganizationModelService:
    """Read-only projection of canonical organization operating facts."""

    @classmethod
    def project(cls, *, user, decision):
        company_id = user.company_id
        scope_codes = set(decision.get("scope", {}).get("codes") or [])
        visible_department_ids = cls._visible_department_ids(
            user=user,
            company_id=company_id,
            scope_codes=scope_codes,
            decision=decision,
        )

        departments = list(
            Department.objects.select_related(
                "company", "parent", "organization_unit", "responsible_position"
            )
            .filter(company_id=company_id, pk__in=visible_department_ids)
            .order_by("code", "pk")
        )
        department_ids = [row.pk for row in departments]
        department_by_unit = {
            row.organization_unit_id: row for row in departments if row.organization_unit_id
        }

        units_query = OrganizationUnit.objects.select_related(
            "company", "parent"
        ).filter(company_id=company_id)
        if not ({"ALL", "ORGANIZATION"} & scope_codes):
            unit_ids = set(department_by_unit)
            unit_ids.update(
                units_query.filter(unit_type=OrganizationUnit.UnitType.COMPANY).values_list(
                    "pk", flat=True
                )
            )
            units_query = units_query.filter(pk__in=unit_ids)
        units = list(units_query.order_by("unit_type", "code", "pk"))

        positions = list(
            Position.objects.select_related(
                "company", "department", "job_family", "job_level",
                "parent_position", "default_role",
            )
            .prefetch_related(
                Prefetch(
                    "responsibility_mappings",
                    queryset=PositionResponsibility.objects.select_related(
                        "responsibility"
                    ).filter(active=True),
                ),
                Prefetch(
                    "workflow_responsibilities",
                    queryset=PositionWorkflowResponsibility.objects.select_related(
                        "responsibility", "workflow_node__process_definition"
                    ).filter(active=True),
                ),
            )
            .filter(company_id=company_id, department_id__in=department_ids)
            .order_by("department__code", "code", "pk")
        )
        position_ids = [row.pk for row in positions]

        employees = list(
            formal_employee_queryset(
                Employee.objects.select_related(
                    "department_ref", "department_ref__company", "position_ref", "user"
                ),
                company_id=company_id,
            ).filter(department_ref_id__in=department_ids)
            .order_by("employee_no", "pk")
        )
        employee_ids = [row.pk for row in employees]

        leaderships = list(
            OrganizationLeadershipAssignment.objects.select_related("employee").filter(
                active=True
            ).filter(
                models_q_for_leadership(
                    unit_ids=[row.pk for row in units], department_ids=department_ids
                )
            )
        )
        unit_leaders = {
            row.organization_unit_id: row.employee for row in leaderships if row.organization_unit_id
        }
        department_leaders = {
            row.department_id: row.employee for row in leaderships if row.department_id
        }

        reporting = list(
            EmployeeReportingRelation.objects.select_related(
                "employee", "manager", "employee__department_ref",
                "manager__department_ref", "manager__position_ref",
            )
            .filter(active=True, is_primary=True, employee_id__in=employee_ids)
            .order_by("employee__employee_no", "relation_type", "pk")
        )
        reporting_by_employee = {}
        for row in reporting:
            reporting_by_employee.setdefault(row.employee_id, []).append(row)

        employee_counts = {
            row["department_ref_id"]: row["count"]
            for row in formal_employee_queryset(company_id=company_id)
            .filter(department_ref_id__in=department_ids)
            .values("department_ref_id")
            .annotate(count=Count("id"))
        }
        position_counts = {
            row["department_id"]: row["count"]
            for row in Position.objects.filter(department_id__in=department_ids)
            .values("department_id")
            .annotate(count=Count("id"))
        }

        unit_rows = cls._unit_rows(units, department_by_unit, unit_leaders)
        department_rows = [
            {
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "companyId": row.company_id,
                "companyName": row.company.name,
                "parentId": row.parent_id,
                "parentName": row.parent.name if row.parent_id in department_ids else "",
                "departmentType": row.department_type,
                "departmentTypeLabel": row.get_department_type_display(),
                "organizationUnitId": row.organization_unit_id,
                "organizationUnitName": row.organization_unit.name if row.organization_unit else "待维护",
                "responsiblePositionId": row.responsible_position_id,
                "responsiblePositionCode": row.responsible_position.code if row.responsible_position else "",
                "responsiblePositionName": row.responsible_position.name if row.responsible_position else "待维护",
                "leaderEmployeeId": department_leaders.get(row.pk).pk if department_leaders.get(row.pk) else None,
                "leaderEmployeeNo": department_leaders.get(row.pk).employee_no if department_leaders.get(row.pk) else "",
                "leaderEmployeeName": department_leaders.get(row.pk).full_name if department_leaders.get(row.pk) else "待维护",
                "legacyManagerText": row.manager,
                "effectiveFrom": _date(row.effective_from),
                "effectiveTo": _date(row.effective_to),
                "employeeCount": employee_counts.get(row.pk, 0),
                "positionCount": position_counts.get(row.pk, 0),
                "statusLabel": _status_label(row.is_active),
                "isActive": row.is_active,
            }
            for row in departments
        ]

        position_rows = []
        workflow_rows = []
        for row in positions:
            responsibility_mappings = list(row.responsibility_mappings.all())
            workflow_mappings = list(row.workflow_responsibilities.all())
            responsibility_names = [item.responsibility.name for item in responsibility_mappings]
            workflow_labels = [
                f"{item.workflow_code}/{item.node_code}（{item.get_ownership_type_display()}）"
                for item in workflow_mappings
            ]
            position_rows.append({
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "companyId": row.company_id,
                "departmentId": row.department_id,
                "departmentName": row.department.name if row.department else "待维护",
                "jobFamilyId": row.job_family_id,
                "jobFamilyName": row.job_family.name if row.job_family else "待维护",
                "jobLevelId": row.job_level_id,
                "jobLevelName": row.job_level.name if row.job_level else "待维护",
                "jobLevelRank": row.job_level.rank if row.job_level else None,
                "parentPositionId": row.parent_position_id,
                "parentPositionName": row.parent_position.name if row.parent_position else "",
                "defaultRoleId": row.default_role_id,
                "defaultRoleCode": row.default_role.code if row.default_role else "",
                "defaultRoleName": row.default_role.name if row.default_role else "待维护",
                "description": row.description,
                "responsibilitySummary": row.responsibility_summary,
                "effectiveFrom": _date(row.effective_from),
                "effectiveTo": _date(row.effective_to),
                "responsibilityNames": responsibility_names,
                "responsibilityText": "、".join(responsibility_names) or row.responsibility_summary or "待维护",
                "workflowResponsibilityText": "；".join(workflow_labels) or "待维护",
                "employeeCount": sum(1 for item in employees if item.position_ref_id == row.pk),
                "statusLabel": _status_label(row.is_active),
                "isActive": row.is_active,
            })
            for mapping in workflow_mappings:
                workflow_rows.append({
                    "id": mapping.pk,
                    "positionId": row.pk,
                    "positionCode": row.code,
                    "positionName": row.name,
                    "workflowNodeId": mapping.workflow_node_id,
                    "workflowCode": mapping.workflow_code,
                    "nodeCode": mapping.node_code,
                    "businessActionCode": (
                        mapping.workflow_node.business_action_code
                        if mapping.workflow_node else ""
                    ),
                    "ownershipType": mapping.ownership_type,
                    "ownershipTypeLabel": mapping.get_ownership_type_display(),
                    "responsibilityCode": mapping.responsibility.code if mapping.responsibility else "",
                    "responsibilityName": mapping.responsibility.name if mapping.responsibility else "",
                    "effectiveFrom": _date(mapping.effective_from),
                    "effectiveTo": _date(mapping.effective_to),
                    "statusLabel": _status_label(mapping.active),
                })

        employee_rows = []
        visible_employee_ids = set(employee_ids)
        for row in employees:
            relations = reporting_by_employee.get(row.pk, [])
            direct_relation = next(
                (
                    item for item in relations
                    if item.relation_type == EmployeeReportingRelation.RelationType.DIRECT
                ),
                None,
            )
            functional_relation = next(
                (
                    item for item in relations
                    if item.relation_type == EmployeeReportingRelation.RelationType.FUNCTIONAL
                ),
                None,
            )
            manager_names = []
            relation_labels = []
            for relation in relations:
                manager_visible = relation.manager_id in visible_employee_ids or bool(
                    {"ALL", "ORGANIZATION"} & scope_codes
                )
                manager_names.append(
                    relation.manager.full_name if manager_visible else "跨部门主管（受权限保护）"
                )
                relation_labels.append(relation.get_relation_type_display())
            employee_rows.append({
                "id": row.pk,
                "employeeNo": row.employee_no,
                "fullName": row.full_name,
                "departmentId": row.department_ref_id,
                "departmentName": row.department_ref.name if row.department_ref else "待维护",
                "positionId": row.position_ref_id,
                "positionName": row.position_ref.name if row.position_ref else "待维护",
                "userId": row.user_id,
                "username": row.user.username if row.user else "",
                "directManagerId": direct_relation.manager_id if direct_relation else None,
                "directManagerName": (
                    direct_relation.manager.full_name
                    if direct_relation and (
                        direct_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    ) else "跨部门主管（受权限保护）" if direct_relation else "待维护"
                ),
                "directManagerPositionName": (
                    direct_relation.manager.position_ref.name
                    if direct_relation
                    and direct_relation.manager.position_ref
                    and (
                        direct_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    )
                    else ""
                ),
                "directManagerDisplay": (
                    f"{direct_relation.manager.full_name}（{direct_relation.manager.position_ref.name}）"
                    if direct_relation
                    and direct_relation.manager.position_ref
                    and (
                        direct_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    )
                    else direct_relation.manager.full_name
                    if direct_relation and (
                        direct_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    )
                    else "跨部门主管（受权限保护）" if direct_relation else "待维护"
                ),
                "directManagerEffectiveFrom": _date(direct_relation.effective_from) if direct_relation else None,
                "directManagerEffectiveTo": _date(direct_relation.effective_to) if direct_relation else None,
                "functionalManagerId": functional_relation.manager_id if functional_relation else None,
                "functionalManagerDisplay": (
                    f"{functional_relation.manager.full_name}（{functional_relation.manager.position_ref.name}）"
                    if functional_relation
                    and functional_relation.manager.position_ref
                    and (
                        functional_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    )
                    else functional_relation.manager.full_name
                    if functional_relation and (
                        functional_relation.manager_id in visible_employee_ids
                        or bool({"ALL", "ORGANIZATION"} & scope_codes)
                    )
                    else "跨部门主管（受权限保护）" if functional_relation else "待维护"
                ),
                "managerNames": manager_names,
                "managerText": "、".join(manager_names) or "待维护",
                "reportingTypeText": "、".join(relation_labels) or "待维护",
                "statusLabel": row.get_status_display(),
                "status": row.status,
                "phone": row.phone or "",
                "companyId": row.department_ref.company_id if row.department_ref else None,
                "companyName": row.department_ref.company.name if row.department_ref else "",
            })

        job_families = [
            {
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "companyId": row.company_id,
                "description": row.description,
                "statusLabel": _status_label(row.is_active),
                "isActive": row.is_active,
            }
            for row in JobFamily.objects.filter(company_id=company_id).order_by("code", "pk")
        ]
        job_levels = [
            {
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "companyId": row.company_id,
                "rank": row.rank,
                "description": row.description,
                "statusLabel": _status_label(row.is_active),
                "isActive": row.is_active,
            }
            for row in JobLevel.objects.filter(company_id=company_id).order_by("rank", "code", "pk")
        ]
        responsibilities = [
            {
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "category": row.category,
                "businessDomain": row.category,
                "status": row.status,
                "statusLabel": row.get_status_display(),
                "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
                "effectiveTo": row.effective_to.isoformat() if row.effective_to else None,
                "isActive": row.is_active,
            }
            for row in Responsibility.objects.order_by("code", "pk")
        ]
        roles = [
            {"id": row.pk, "code": row.code, "name": row.name}
            for row in Role.objects.order_by("code", "pk")
        ]
        workflow_nodes = [
            {
                "id": row.pk,
                "processDefinitionId": row.process_definition_id,
                "workflowCode": row.process_definition.definition_code,
                "workflowName": row.process_definition.definition_name,
                "nodeCode": row.node_code,
                "nodeName": row.node_name,
                "sequence": row.sequence,
                "businessActionCode": row.business_action_code,
                "active": row.active and row.process_definition.active,
            }
            for row in WorkflowNodeDefinition.objects.select_related("process_definition")
            .filter(active=True, process_definition__active=True)
            .order_by("process_definition__definition_code", "sequence", "node_code")
        ]
        audits = [
            {
                "id": row.pk,
                "actionCode": row.action_code,
                "actorName": row.actor.real_name or row.actor.username,
                "targetType": row.target_type,
                "targetId": row.target_id,
                "targetLabel": row.target_label,
                "reason": row.reason,
                "before": row.before_snapshot,
                "after": row.after_snapshot,
                "createdAt": row.created_at.isoformat(),
            }
            for row in OrganizationOperatingAuditRecord.objects.select_related("actor")
            .filter(organization_id=company_id)[:30]
        ]

        return {
            "contractVersion": ENTERPRISE_ORGANIZATION_MODEL_CONTRACT,
            "authorization": decision,
            "company": cls._company_row(company_id),
            "organizationUnits": unit_rows,
            "departments": department_rows,
            "positions": position_rows,
            "employees": employee_rows,
            "workflowResponsibilities": workflow_rows,
            "jobFamilies": job_families,
            "jobLevels": job_levels,
            "responsibilities": responsibilities,
            "roles": roles,
            "workflowNodes": workflow_nodes,
            "audits": audits,
            "strictFacts": {
                "factSource": "server",
                "factLoadStatus": "success",
                "organizationUnitCount": len(unit_rows),
                "departmentCount": len(department_rows),
                "positionCount": len(position_rows),
                "employeeCount": len(employee_rows),
                "workflowResponsibilityCount": len(workflow_rows),
                "jobFamilyCount": len(job_families),
                "jobLevelCount": len(job_levels),
                "responsibilityCount": len(responsibilities),
                "auditCount": len(audits),
                "authorizedBusinessWriteCount": 0,
                "unauthorizedBusinessWriteCount": 0,
                "workflowExecutionCount": 0,
            },
        }

    @staticmethod
    def _company_row(company_id):
        row = Company.objects.get(pk=company_id)
        return {
            "id": row.pk,
            "code": row.code,
            "name": row.name,
            "statusLabel": _status_label(row.is_active),
        }

    @staticmethod
    def _visible_department_ids(*, user, company_id, scope_codes, decision):
        query = Department.objects.filter(company_id=company_id)
        if {"ALL", "ORGANIZATION"} & scope_codes:
            return set(query.values_list("pk", flat=True))
        visible = set(decision.get("scope", {}).get("departmentIds") or [])
        if "SELF" in scope_codes:
            try:
                if user.employee_profile.department_ref_id:
                    visible.add(user.employee_profile.department_ref_id)
            except Exception:
                pass
        return set(query.filter(pk__in=visible).values_list("pk", flat=True))

    @staticmethod
    def _unit_rows(units, department_by_unit, unit_leaders):
        unit_by_id = {row.pk: row for row in units}

        def lineage(row):
            names = [row.name]
            seen = {row.pk}
            current = row
            while current.parent_id in unit_by_id and current.parent_id not in seen:
                current = unit_by_id[current.parent_id]
                names.append(current.name)
                seen.add(current.pk)
            return list(reversed(names))

        rows = []
        for row in units:
            names = lineage(row)
            leader = unit_leaders.get(row.pk)
            source_department = department_by_unit.get(row.pk)
            rows.append({
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "unitType": row.unit_type,
                "unitTypeLabel": row.get_unit_type_display(),
                "parentId": row.parent_id if row.parent_id in unit_by_id else None,
                "parentName": row.parent.name if row.parent_id in unit_by_id else "",
                "companyId": row.company_id,
                "companyName": row.company.name,
                "leaderEmployeeId": leader.pk if leader else None,
                "leaderEmployeeNo": leader.employee_no if leader else "",
                "leaderEmployeeName": leader.full_name if leader else "待维护",
                "sourceDepartmentId": source_department.pk if source_department else None,
                "depth": max(len(names) - 1, 0),
                "pathText": " / ".join(names),
                "effectiveFrom": _date(row.effective_from),
                "effectiveTo": _date(row.effective_to),
                "statusLabel": _status_label(row.is_active),
            })
        return sorted(rows, key=lambda item: (item["pathText"], item["code"]))


def models_q_for_leadership(*, unit_ids, department_ids):
    from django.db.models import Q

    return Q(organization_unit_id__in=unit_ids) | Q(department_id__in=department_ids)
