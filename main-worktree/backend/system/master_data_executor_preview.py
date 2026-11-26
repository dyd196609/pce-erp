import re

from django.db.models import Q
from django.utils import timezone

from pfm.models import Employee

from .models import Permission, PositionResponsibility, Responsibility, User


MASTER_DATA_EXECUTOR_PREVIEW_CONTRACT = "PCE-MASTER-DATA-EXECUTOR-PREVIEW-V1"

_TEST_CODE_PREFIXES = (
    "EMP-R",
    "EMP-V1",
    "TEST",
)
_TEST_NAME_MARKERS = (
    "权限测试",
    "系统流程验收",
    "最终验收",
    "测试员工",
)


def _date_is_current(start, end, today):
    return (start is None or start <= today) and (end is None or end >= today)


def _test_reason(employee):
    code = str(employee.employee_no or "").upper()
    name = str(employee.full_name or "")
    if code.startswith(_TEST_CODE_PREFIXES):
        return "员工编号属于已知测试/验收命名空间"
    marker = next((value for value in _TEST_NAME_MARKERS if value in name), "")
    if marker:
        return f"员工姓名包含已知测试标识：{marker}"
    return ""


def _suggested_username(employee, occupied):
    stem = re.sub(r"[^a-z0-9]+", "_", str(employee.employee_no or "").lower()).strip("_")
    base = f"emd_{stem or employee.pk}"
    candidate = base
    suffix = 2
    while candidate in occupied:
        candidate = f"{base}_{suffix}"
        suffix += 1
    occupied.add(candidate)
    return candidate


class MasterDataExecutorPreviewService:
    """Read-only candidate and responsibility projection for one manual decision."""

    @classmethod
    def project(cls, *, user):
        today = timezone.now().date()
        company_id = user.company_id
        technical_admin = User.objects.filter(username="admin").first()
        occupied_usernames = set(User.objects.values_list("username", flat=True))

        employees = list(
            Employee.objects.select_related(
                "department_ref", "department_ref__company", "position_ref", "user"
            )
            .filter(
                status="active",
            )
            .filter(Q(department_ref__company_id=company_id) | Q(department_ref__isnull=True))
            .order_by("department_ref__code", "position_ref__code", "employee_no", "pk")
        )

        eligible = []
        excluded = []
        for employee in employees:
            department = employee.department_ref
            position = employee.position_ref
            reason = _test_reason(employee)
            if not reason and not department:
                reason = "缺少正式部门"
            if not reason and not position:
                reason = "缺少正式岗位"
            if not reason and not department.is_active:
                reason = "正式部门未启用"
            if not reason and (position.company_id != company_id or not position.is_active):
                reason = "正式岗位未启用或不属于当前公司"
            if not reason and position.department_id != department.pk:
                reason = "员工岗位与正式部门不一致"
            if not reason and not _date_is_current(
                department.effective_from, department.effective_to, today
            ):
                reason = "部门当前不在有效期"
            if not reason and not _date_is_current(
                position.effective_from, position.effective_to, today
            ):
                reason = "岗位当前不在有效期"
            if reason:
                excluded.append({
                    "employeeId": employee.pk,
                    "employeeNo": employee.employee_no,
                    "reason": reason,
                })
                continue
            eligible.append(employee)

        position_ids = {employee.position_ref_id for employee in eligible}
        mappings = list(
            PositionResponsibility.objects.select_related("responsibility")
            .filter(
                position_id__in=position_ids,
                active=True,
                responsibility__is_active=True,
                responsibility__status=Responsibility.Status.ACTIVE,
            )
            .order_by("responsibility__code", "pk")
        )
        responsibilities_by_position = {}
        for mapping in mappings:
            responsibility = mapping.responsibility
            if not _date_is_current(
                responsibility.effective_from, responsibility.effective_to, today
            ):
                continue
            responsibilities_by_position.setdefault(mapping.position_id, []).append({
                "code": responsibility.code,
                "name": responsibility.name,
                "isPrimary": mapping.is_primary,
            })

        rows = []
        for employee in eligible:
            account = employee.user
            account_present = account is not None
            account_active = bool(account and account.is_active)
            responsibilities = responsibilities_by_position.get(employee.position_ref_id, [])
            rows.append({
                "id": employee.pk,
                "employeeCode": employee.employee_no,
                "employeeName": employee.full_name,
                "departmentId": employee.department_ref_id,
                "departmentCode": employee.department_ref.code,
                "departmentName": employee.department_ref.name,
                "positionId": employee.position_ref_id,
                "positionCode": employee.position_ref.code,
                "positionName": employee.position_ref.name,
                "employmentStatus": "在职",
                "positionStatus": "启用",
                "businessAccountStatus": (
                    "ACTIVE" if account_active else "INACTIVE" if account_present else "BUSINESS ACCOUNT MISSING"
                ),
                "hasBusinessAccount": account_present,
                "businessUsername": account.username if account else "",
                "businessAccountActive": account_active,
                "businessAccountPreview": (
                    account.username if account else _suggested_username(employee, occupied_usernames)
                ),
                "responsibilities": responsibilities,
                "responsibilityText": "、".join(
                    item["name"] for item in responsibilities
                ) or "尚无正式岗位职责",
                "hasResponsibility": bool(responsibilities),
                "proposedResponsibility": "企业基础资料维护员",
                "selectionStatus": "PENDING USER DECISION",
            })

        master_data_responsibilities = list(
            Responsibility.objects.filter(
                is_active=True,
                status=Responsibility.Status.ACTIVE,
            ).filter(
                Q(code__icontains="MASTER_DATA")
                | Q(name__contains="主数据")
                | Q(name__contains="基础资料")
                | Q(description__contains="主数据")
                | Q(description__contains="基础资料")
            ).values("id", "code", "name")
        )

        requested_action_codes = [
            "production.master_data.view",
            "masterdata.customer.maintain",
            "masterdata.supplier.maintain",
            "production.master_data.unit.maintain",
            "production.master_data.product.maintain",
            "production.master_data.material.maintain",
        ]
        existing_action_codes = set(
            Permission.objects.filter(code__in=requested_action_codes).values_list("code", flat=True)
        )
        action_code_readiness = [
            {
                "code": code,
                "status": "EXISTING / REUSE" if code in existing_action_codes else "MISSING / PREVIEW ONLY",
                "condition": "物料人工验收后" if code == "production.master_data.material.maintain" else "当前职责边界",
            }
            for code in requested_action_codes
        ]

        account_ready_count = sum(
            1 for row in rows if row["businessAccountStatus"] == "ACTIVE"
        )
        account_missing_count = sum(
            1 for row in rows if row["businessAccountStatus"] == "BUSINESS ACCOUNT MISSING"
        )

        return {
            "contractVersion": MASTER_DATA_EXECUTOR_PREVIEW_CONTRACT,
            "status": "MASTER DATA EXECUTOR MANUAL DECISION READY",
            "technicalAdministrator": {
                "username": technical_admin.username if technical_admin else "admin",
                "accountType": "TECHNICAL / SYSTEM ADMINISTRATOR ACCOUNT",
                "employeeLinked": bool(
                    technical_admin and Employee.objects.filter(user=technical_admin).exists()
                ),
                "keptUnlinked": True,
            },
            "summary": {
                "eligibleEmployeeCount": len(rows),
                "activeBusinessAccountCount": account_ready_count,
                "missingBusinessAccountCount": account_missing_count,
                "inactiveBusinessAccountCount": len(rows) - account_ready_count - account_missing_count,
                "excludedTestOrInvalidCount": len(excluded),
                "existingEquivalentResponsibilityCount": len(master_data_responsibilities),
                "recommendedCandidateCount": 0,
            },
            "rows": rows,
            "excludedSummary": excluded,
            "existingEquivalentResponsibilities": master_data_responsibilities,
            "responsibilityPreview": {
                "code": "ENTERPRISE_MASTER_DATA_MAINTAINER",
                "name": "企业基础资料维护员",
                "status": "PREVIEW ONLY / PENDING USER DECISION",
                "bindingModel": "Employee → Position → Responsibility；Application User → exactly one Employee",
                "allowedBusinessObjects": [
                    "客户 / 经销商",
                    "供应商",
                    "UOM Mapping",
                    "Product Category",
                    "用户后续人工确认后的 Material",
                    "后续逐项明确授权的基础资料",
                ],
                "allowedSemantics": [
                    "view",
                    "create",
                    "update",
                    "activate/deactivate",
                    "source mapping",
                    "readback",
                ],
                "actionCodeReadiness": action_code_readiness,
                "existingActionCodesToReuse": [
                    item["code"] for item in action_code_readiness
                    if item["status"] == "EXISTING / REUSE"
                ],
                "missingActionCodesPreview": [
                    item["code"] for item in action_code_readiness
                    if item["status"] == "MISSING / PREVIEW ONLY"
                ],
                "explicitlyDenied": [
                    "delete",
                    "production planning release",
                    "purchase approval",
                    "production order release",
                    "financial approval",
                    "organization administration",
                    "user administration",
                ],
            },
            "recommendation": {
                "status": "MANUAL SELECTION REQUIRED",
                "candidateIds": [],
                "reason": "当前没有员工已具备企业基础资料维护等价正式职责，系统不得自动推荐或选择。",
            },
            "strictFacts": {
                "factSource": "server",
                "readOnly": True,
                "productionBusinessWriteCount": 0,
                "adminEmployeeBindingWriteCount": 0,
                "businessUserWriteCount": 0,
                "positionResponsibilityWriteCount": 0,
                "group1FormalizationWriteCount": 0,
                "productCategoryWriteCount": 0,
            },
        }
