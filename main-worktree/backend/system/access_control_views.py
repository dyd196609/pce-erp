import hashlib
import json
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from pfm.formal_employee import (
    account_link_employee_queryset,
    employee_archive_queryset,
    formal_employee_queryset,
    organization_complete_employee_queryset,
)
from pfm.models import Employee
from workflow_runtime.models import UserOrganizationRoleAuthority

from .authorization import AuthorizationService, authority_scope_code, user_access_profile
from .enterprise_organization import EnterpriseOrganizationModelService
from .organization_operating import (
    ACTION_PERMISSIONS,
    OrganizationOperatingError,
    OrganizationOperatingService,
    employee_account_association_context,
)
from .organization_import_service import OrganizationImportError, OrganizationImportService
from .organization_code_allocator import ENTITY_ROLE, allocate_code
from .employee_account_provisioning import (
    EmployeeAccountProvisioningError,
    employee_account_provisioning_eligibility,
    employee_account_number,
    provision_employee_account,
)
from .responsibility_catalog import ResponsibilityCatalogService
from .models import (
    Company,
    Department,
    Permission,
    OrganizationOperatingAuditRecord,
    Position,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


def envelope(data=None, *, error=None, http_status=status.HTTP_200_OK):
    return Response({
        "success": error is None,
        "data": data,
        "error": error,
        "meta": {"module": "SYSTEM", "source": "server", "status": http_status},
    }, status=http_status)


def business_hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def organization_import_admin_guard(request):
    if request.user.is_superuser:
        return None
    return envelope(
        error={"code": "ACCESS_CONTROL_ADMIN_REQUIRED", "message": "仅系统管理员可以导入组织基础资料。"},
        http_status=status.HTTP_403_FORBIDDEN,
    )


def organization_import_error(error):
    return envelope(
        error={"code": error.code, "message": error.message, "details": error.details},
        http_status=error.http_status,
    )


class OrganizationImportTemplateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity):
        denied = organization_import_admin_guard(request)
        if denied:
            return denied
        try:
            if request.query_params.get('context') == '1':
                return envelope(OrganizationImportService.target_context(entity,request.user))
            schema = OrganizationImportService.schema(entity)
            content = OrganizationImportService.template_bytes(entity, user=request.user)
        except OrganizationImportError as error:
            return organization_import_error(error)
        filename = f"{schema['label']}导入模板-{OrganizationImportService.VERSION}.xlsx"
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        response["X-PCE-Template-Version"] = OrganizationImportService.VERSION
        return response


class OrganizationImportPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, entity):
        denied = organization_import_admin_guard(request)
        if denied:
            return denied
        uploaded = request.FILES.get("file")
        if not uploaded:
            return envelope(error={"code": "IMPORT_FILE_REQUIRED", "message": "请选择.xlsx导入文件。"}, http_status=status.HTTP_400_BAD_REQUEST)
        try:
            preview, _ = OrganizationImportService.preview(entity, uploaded_file=uploaded, user=request.user)
        except OrganizationImportError as error:
            return organization_import_error(error)
        if request.query_params.get('report') == 'xlsx':
            response=HttpResponse(OrganizationImportService.error_report_bytes(preview),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition']="attachment; filename*=UTF-8''"+quote('导入校验报告.xlsx')
            return response
        return envelope(preview)


class OrganizationImportCommitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, entity):
        denied = organization_import_admin_guard(request)
        if denied:
            return denied
        if str(request.data.get("confirmed") or "").lower() != "true":
            return envelope(error={"code": "IMPORT_CONFIRMATION_REQUIRED", "message": "必须在预览后明确确认导入。"}, http_status=status.HTTP_400_BAD_REQUEST)
        uploaded = request.FILES.get("file")
        if not uploaded:
            return envelope(error={"code": "IMPORT_FILE_REQUIRED", "message": "请选择.xlsx导入文件。"}, http_status=status.HTTP_400_BAD_REQUEST)
        try:
            binding = json.loads(request.data.get("previewActorBinding") or "{}")
            result = OrganizationImportService.commit(
                entity, uploaded_file=uploaded, user=request.user,
                preview_fingerprint=str(request.data.get("previewFingerprint") or ""),
                preview_actor_binding=binding,
                idempotency_key=str(request.data.get("idempotencyKey") or ""),
            )
        except (json.JSONDecodeError, TypeError):
            return envelope(error={"code": "PREVIEW_ACTOR_INVALID", "message": "预览身份绑定无效，请重新预览。"}, http_status=status.HTTP_400_BAD_REQUEST)
        except OrganizationImportError as error:
            return organization_import_error(error)
        return envelope(result)


def employee_row(employee, *, formal_candidate_ids=None, organization_complete_ids=None):
    formal_candidate_ids = formal_candidate_ids or set()
    organization_complete_ids = organization_complete_ids or set()
    formal_department_name = employee.department_ref.name if employee.department_ref else ""
    formal_position_name = employee.position_ref.name if employee.position_ref else ""
    legacy_department_name = employee.department_name or ""
    legacy_position_name = employee.position or ""
    organization_complete = employee.pk in organization_complete_ids
    formal_candidate = employee.pk in formal_candidate_ids
    return {
        "id": employee.pk,
        "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "phone": employee.phone or "",
        "status": employee.status,
        "statusLabel": employee.get_status_display(),
        "departmentId": employee.department_ref_id,
        "departmentCode": employee.department_ref.code if employee.department_ref else "",
        "departmentName": formal_department_name or "未维护",
        "formalDepartmentName": formal_department_name or "未维护",
        "legacyDepartmentName": legacy_department_name or "—",
        "positionId": employee.position_ref_id,
        "positionCode": employee.position_ref.code if employee.position_ref else "",
        "positionName": formal_position_name or "未维护",
        "formalPositionName": formal_position_name or "未维护",
        "legacyPositionName": legacy_position_name or "—",
        "userId": employee.user_id,
        "username": employee.user.username if employee.user else "",
        "suggestedUsername": employee.user.username if employee.user else employee_account_number(employee),
        "credentialState": (
            "ACTIVE" if employee.user and employee.user.has_usable_password()
            else "PENDING_SECURE_INITIALIZATION" if employee.user else "NOT_CREATED"
        ),
        "companyId": employee.department_ref.company_id if employee.department_ref else None,
        "companyName": (
            employee.department_ref.company.name
            if employee.department_ref else "未关联正式公司"
        ),
        "organizationComplete": organization_complete,
        "organizationStatusLabel": (
            "正式组织链完整" if organization_complete else "组织关系待维护"
        ),
        "formalCandidateBaseEligible": formal_candidate,
        "businessCandidateStatusLabel": (
            "基础组织资格通过，仍须业务权限校验"
            if formal_candidate else "不具备正式业务候选基础资格"
        ),
    }


class AccessControlProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return envelope(user_access_profile(request.user))


class ResponsibilityCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        decision = AuthorizationService.decide(
            user=request.user,
            action_code="system.organization.responsibility.manage",
            organization_id=str(request.user.company_id),
        )
        if not decision["allowed"]:
            return envelope(
                data={"authorization": decision},
                error={
                    "code": decision["decisionCode"],
                    "message": decision["reason"],
                },
                http_status=status.HTTP_403_FORBIDDEN,
            )
        responsibility_id = request.query_params.get("id")
        if responsibility_id in (None, ""):
            data = ResponsibilityCatalogService.list()
            if request.query_params.get("assignmentContext") == "1":
                data["assignmentContext"] = (
                    ResponsibilityCatalogService.assignment_context(
                        company_id=request.user.company_id,
                        decision=decision,
                    )
                )
            return envelope(data)
        try:
            responsibility_id = int(responsibility_id)
        except (TypeError, ValueError):
            return envelope(
                error={"code": "INVALID_RESPONSIBILITY_ID", "message": "责任标识无效。"},
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        result = ResponsibilityCatalogService.detail(responsibility_id)
        if result is None:
            return envelope(
                error={"code": "RESPONSIBILITY_NOT_FOUND", "message": "责任不存在。"},
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return envelope(result)


class AccessControlFoundationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _admin_guard(self, request):
        if request.user.is_superuser:
            return None
        return envelope(
            error={"code": "ACCESS_CONTROL_ADMIN_REQUIRED", "message": "仅系统管理员可以维护组织与权限基础。"},
            http_status=status.HTTP_403_FORBIDDEN,
        )

    def get(self, request):
        denied = self._admin_guard(request)
        if denied:
            return denied
        from pde.models import EngineeringSourceRecord
        from sales.models import SalesOrder

        companies = []
        for company in Company.objects.order_by("is_active", "code").reverse():
            company_departments = Department.objects.filter(company=company)
            company_positions = Position.objects.filter(company=company)
            company_employees = Employee.objects.filter(department_ref__company=company)
            companies.append({
                "id": company.pk,
                "code": company.code,
                "name": company.name,
                "address": company.address,
                "contact": company.contact,
                "phone": company.phone,
                "isActive": company.is_active,
                "statusLabel": "有效经营公司" if company.is_active else "历史归档公司",
                "operatingPurpose": "OPERATING" if company.is_active else "HISTORICAL_ARCHIVE",
                "operatingPurposeLabel": "当前经营主体" if company.is_active else "仅供历史追溯",
                "selectableForNewBusiness": company.is_active,
                "departmentCount": company_departments.count(),
                "positionCount": company_positions.count(),
                "employeeCount": company_employees.count(),
                "userCount": User.objects.filter(company_id=company.pk).count(),
                "salesOrderCount": SalesOrder.objects.filter(company=company).count(),
                "engineeringSourceCount": EngineeringSourceRecord.objects.filter(company=company).count(),
            })
        organization_decision = AuthorizationService.decide(
            user=request.user,
            action_code="system.organization_directory.view",
            organization_id=str(request.user.company_id),
        )
        operating_model = EnterpriseOrganizationModelService.project(
            user=request.user, decision=organization_decision,
        )
        departments = operating_model["departments"]
        positions = operating_model["positions"]
        formal_employee_rows = {
            item["id"]: item for item in operating_model["employees"]
        }
        archive_records = list(
            employee_archive_queryset(
                Employee.objects.select_related(
                    "user", "department_ref__company", "position_ref__company",
                    "position_ref__department",
                )
            ).order_by("employee_no", "pk")
        )
        formal_candidate_ids = set(
            formal_employee_queryset().values_list("pk", flat=True)
        )
        organization_complete_ids = set(
            organization_complete_employee_queryset().values_list("pk", flat=True)
        )
        employees = []
        for employee in archive_records:
            item = dict(formal_employee_rows.get(employee.pk) or {})
            item.update(employee_row(
                employee,
                formal_candidate_ids=formal_candidate_ids,
                organization_complete_ids=organization_complete_ids,
            ))
            item.setdefault("directManagerId", None)
            item.setdefault("directManagerName", "待维护")
            item.setdefault("directManagerPositionName", "")
            item.setdefault("directManagerDisplay", "待维护")
            item.setdefault("functionalManagerId", None)
            item.setdefault("functionalManagerDisplay", "待维护")
            item["accountAssociationContext"] = employee_account_association_context(
                employee, company_id=request.user.company_id,
            )
            employees.append(item)
        account_link_records = list(
            account_link_employee_queryset(
                Employee.objects.select_related(
                    "user", "department_ref__company", "position_ref__company",
                    "position_ref__department",
                )
            ).order_by("employee_no", "pk")
        )
        account_link_employees = []
        for employee in account_link_records:
            item = employee_row(
                employee,
                formal_candidate_ids=formal_candidate_ids,
                organization_complete_ids=organization_complete_ids,
            )
            eligibility = employee_account_provisioning_eligibility(
                employee, actor_company_id=request.user.company_id,
            )
            item.update({
                "accountLinkVisible": True,
                "accountLinkStatusLabel": "未建立账号",
                "accountProvisioningEligible": eligibility["eligible"],
                "accountProvisioningCode": eligibility["code"],
                "accountProvisioningStatusLabel": (
                    "可建立待初始化账户"
                    if eligibility["eligible"]
                    else "暂不能建立启用账户"
                ),
                "accountProvisioningMessage": eligibility["message"],
                "accountProvisioningCompanyId": eligibility["companyId"],
            })
            account_link_employees.append(item)
        employee_archive_summary = {
            "employeeArchiveCount": len(archive_records),
            "organizationCompleteCount": len(organization_complete_ids),
            "organizationIncompleteCount": len(archive_records) - len(organization_complete_ids),
            "inactiveHistoryCount": sum(row.status != "active" for row in archive_records),
            "formalCandidateBaseCount": len(formal_candidate_ids),
            "accountLinkCandidateCount": len(account_link_employees),
            "accountLinkQuerySource": "Employee Archive",
            "accountLinkQueryRule": "active Employee + User is null",
        }
        authorities = list(UserRoleScopeAssignment.objects.select_related(
            "user", "role", "organization", "department",
        ).filter(active=True))
        authorities_by_user = {}
        for authority in authorities:
            authorities_by_user.setdefault(authority.user_id, []).append({
                "id": authority.pk,
                "roleCode": authority.role.code,
                "legalEntityId": str(authority.organization_id),
                "departmentId": authority.department_id,
                "scopeCode": authority_scope_code(authority),
                "active": authority.active,
                "version": authority.version,
            })
        formal_user_ids = set(authorities_by_user)
        legacy_authorities = UserOrganizationRoleAuthority.objects.select_related("user").filter(
            active=True,
        ).exclude(user_id__in=formal_user_ids)
        for authority in legacy_authorities:
            authorities_by_user.setdefault(authority.user_id, []).append({
                "id": f"legacy-{authority.pk}",
                "roleCode": authority.role_code,
                "legalEntityId": authority.legal_entity_id,
                "departmentId": (
                    int(authority.department_id)
                    if str(authority.department_id or "").isdigit()
                    else None
                ),
                "scopeCode": authority_scope_code(authority),
                "active": authority.active,
                "version": authority.version,
                "source": "legacy_adapter",
            })
        from pde.models import OrderReviewParticipantGrant
        from pde.review_permission_catalog import REVIEW_PERMISSION_CATALOG

        review_grants = []
        review_grants_by_user = {}
        for grant in OrderReviewParticipantGrant.objects.select_related(
            "review", "company", "employee", "user", "created_by",
        ).order_by("review__review_type", "review_id", "employee__employee_no"):
            catalog = REVIEW_PERMISSION_CATALOG.get(grant.review.review_type) or {}
            actions = catalog.get("actions") or {}
            row = {
                "id": grant.pk,
                "grantCode": f"REVIEW-GRANT-{grant.pk}",
                "moduleName": catalog.get("moduleName") or grant.review.get_review_type_display(),
                "reviewType": grant.review.review_type,
                "reviewId": grant.review_id,
                "reviewVersion": grant.review_version_snapshot,
                "sourceOrderNo": grant.review.source_order_no,
                "sourceVersion": grant.source_version_snapshot,
                "companyId": grant.company_id,
                "companyName": grant.company.name,
                "employeeId": grant.employee_id,
                "employeeNo": grant.employee.employee_no,
                "employeeName": grant.employee.full_name,
                "userId": grant.user_id,
                "username": grant.user.username,
                "active": grant.active,
                "statusLabel": "有效" if grant.active else "已撤销",
                "canView": grant.can_view,
                "canMaintainOwnOpinion": grant.can_maintain_own_opinion,
                "canSignOwnItems": grant.can_sign_own_items,
                "capabilityLabels": [
                    label for enabled, label in (
                        (grant.can_view, "查看本评审"),
                        (grant.can_maintain_own_opinion, "维护本人意见"),
                        (grant.can_sign_own_items, "签认本人项目"),
                    ) if enabled
                ],
                "requiredRoleCode": (catalog.get("role") or {}).get("code", ""),
                "requiredPermissionCodes": [
                    actions[key][0] for key in ("view", "maintainOwnOpinion", "signOwnItems")
                    if key in actions
                ],
                "reason": grant.reason,
                "createdBy": grant.created_by.username,
                "createdAt": grant.created_at.isoformat(),
                "updatedAt": grant.updated_at.isoformat(),
                "scopeLabel": "当前公司 + 当前评审对象 + 当前版本 + 本人负责项目",
            }
            review_grants.append(row)
            review_grants_by_user.setdefault(grant.user_id, []).append(row)

        users = [{
            "id": row.pk,
            "username": row.username,
            "realName": row.real_name,
            "email": row.email or "",
            "mobile": row.mobile or "",
            "companyId": row.company_id,
            "isActive": row.is_active,
            "isStaff": row.is_staff,
            "isSuperuser": row.is_superuser,
            "credentialState": (
                "ACTIVE" if row.has_usable_password() else "PENDING_SECURE_INITIALIZATION"
            ),
            "employee": employee_row(row.employee_profile) if hasattr(row, "employee_profile") else None,
            "authorities": authorities_by_user.get(row.pk, []),
            "reviewGrants": review_grants_by_user.get(row.pk, []),
        } for row in User.objects.order_by("username")]
        roles = [{
            "id": row.pk,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "permissionCodes": list(RolePermission.objects.filter(role=row).values_list(
                "permission__code", flat=True,
            ).order_by("permission__code")),
        } for row in Role.objects.order_by("code")]
        permission_rows = []
        for permission in Permission.objects.order_by("module", "code"):
            assigned_roles = list(
                Role.objects.filter(rolepermission__permission=permission)
                .order_by("code").values("id", "code", "name")
            )
            permission_rows.append({
                "id": permission.pk,
                "code": permission.code,
                "name": permission.name,
                "module": permission.module,
                "permissionGroup": (
                    "PDE_REVIEW_ITEM" if permission.code.startswith("pde.production_feasibility_review.item.")
                    else "PDE_REVIEW_ACTION" if permission.code.startswith("pde.production_feasibility_review.")
                    else "OTHER"
                ),
                "permissionGroupLabel": (
                    "生产可行性评审—评审事项权限" if permission.code.startswith("pde.production_feasibility_review.item.")
                    else "生产可行性评审—操作权限" if permission.code.startswith("pde.production_feasibility_review.")
                    else "其他权限"
                ),
                "itemCode": permission.code.rsplit(".", 1)[-1] if permission.code.startswith("pde.production_feasibility_review.item.") else "",
                "roles": assigned_roles,
                "roleNames": "、".join(row["name"] for row in assigned_roles),
            })
        return envelope({
            "companies": companies,
            "operatingCompany": next((row for row in companies if row["isActive"]), None),
            "companyScopeSummary": {
                "activeOperatingCompanyCount": sum(1 for row in companies if row["isActive"]),
                "historicalInactiveCompanyCount": sum(1 for row in companies if not row["isActive"]),
                "currentCompanyId": request.user.company_id,
            },
            "departments": departments,
            "positions": positions,
            "employees": employees,
            "accountLinkEmployees": account_link_employees,
            "employeeArchiveSummary": employee_archive_summary,
            "users": users,
            "roles": roles,
            "permissions": permission_rows,
            "reviewGrants": review_grants,
            "organizationUnits": operating_model["organizationUnits"],
            "jobFamilies": operating_model["jobFamilies"],
            "jobLevels": operating_model["jobLevels"],
            "responsibilities": operating_model["responsibilities"],
            "workflowResponsibilities": operating_model["workflowResponsibilities"],
            "workflowNodes": operating_model["workflowNodes"],
            "audits": operating_model["audits"],
            "scopeOptions": [
                {"code": "SELF", "name": "本人数据"},
                {"code": "DEPARTMENT", "name": "本部门数据"},
                {"code": "ORGANIZATION", "name": "本组织数据"},
                {"code": "ALL", "name": "全部数据"},
            ],
            "currentUser": user_access_profile(request.user),
            "facts": {
                "source": "server",
                "authorityChain": "Company/Department/Position/Employee/User/UserRoleScopeAssignment/RolePermission/Permission",
                "legacyAuthorityAdapter": "read_only",
                "businessWriteCount": 0,
            },
        })

    @transaction.atomic
    def post(self, request):
        action = str((request.data or {}).get("action") or "").strip()
        payload = (request.data or {}).get("payload") or {}
        expected_actor_id = payload.get("expectedActorId")
        if expected_actor_id not in (None, ""):
            try:
                actor_matches = int(expected_actor_id) == int(request.user.pk)
            except (TypeError, ValueError):
                actor_matches = False
            if not actor_matches:
                return envelope(
                    error={
                        "code": "AUTHENTICATED_ACTOR_CHANGED",
                        "message": "当前登录身份已变化，未执行管理写入；请重新进入管理页面。",
                    },
                    http_status=status.HTTP_409_CONFLICT,
                )
        denied = self._admin_guard(request)
        if denied:
            return denied
        if action in ACTION_PERMISSIONS:
            try:
                result = OrganizationOperatingService.execute(
                    user=request.user, action=action, payload=payload,
                )
            except OrganizationOperatingError as error:
                return envelope(
                    data={"authorization": error.decision} if error.decision else None,
                    error={"code": error.code, "message": error.message},
                    http_status=error.http_status,
                )
            return envelope(result)
        handlers = {
            "SAVE_USER": self._save_user,
            "SAVE_ROLE": self._save_role,
            "SET_ROLE_PERMISSIONS": self._set_role_permissions,
            "SET_USER_AUTHORITIES": self._set_user_authorities,
            "SET_REVIEW_PARTICIPANT_GRANT": self._set_review_participant_grant,
        }
        handler = handlers.get(action)
        if handler is None:
            return envelope(
                error={"code": "ACCESS_CONTROL_ACTION_INVALID", "message": "权限管理动作无效。"},
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if action in {"SAVE_USER", "SAVE_ROLE", "SET_ROLE_PERMISSIONS", "SET_USER_AUTHORITIES", "SET_REVIEW_PARTICIPANT_GRANT"}:
                reason = str(payload.get("reason") or "").strip()
                if action == "SAVE_ROLE" and not reason:
                    reason = "通过角色管理新增或维护角色"
                if len(reason) < 2:
                    raise ValueError("请填写本次修改原因。")
                if not request.user.is_superuser:
                    decision = AuthorizationService.decide(
                        user=request.user,
                        action_code="system.organization.workflow_responsibility.manage",
                        organization_id=str(request.user.company_id),
                    )
                    if not decision["allowed"]:
                        return envelope(
                            data={"authorization": decision},
                            error={"code": decision["decisionCode"], "message": decision["reason"]},
                            http_status=status.HTTP_403_FORBIDDEN,
                        )
                result = handler(payload, actor=request.user, reason=reason)
            else:
                result = handler(payload)
        except (Company.DoesNotExist, Department.DoesNotExist, Position.DoesNotExist,
                Employee.DoesNotExist, User.DoesNotExist, Role.DoesNotExist) as exc:
            # The handler may already have touched a row before discovering a
            # bad relationship.  A handled exception would otherwise allow
            # @transaction.atomic to commit that partial write.
            transaction.set_rollback(True)
            return envelope(
                error={"code": "ACCESS_CONTROL_REFERENCE_INVALID", "message": str(exc)},
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            transaction.set_rollback(True)
            return envelope(
                error={"code": "ACCESS_CONTROL_VALIDATION_FAILED", "message": str(exc)},
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        return envelope({"action": action, "result": result, "businessWriteCount": 1})

    def _save_department(self, payload):
        company = Company.objects.get(pk=int(payload.get("companyId")))
        defaults = {
            "code": str(payload.get("code") or "").strip(),
            "name": str(payload.get("name") or "").strip(),
            "company": company,
            "manager": str(payload.get("manager") or "").strip(),
            "is_active": payload.get("isActive", True) is not False,
            "parent_id": payload.get("parentId") or None,
        }
        if not defaults["code"] or not defaults["name"]:
            raise ValueError("部门编码和名称不能为空。")
        row = Department.objects.filter(pk=payload.get("id")).first() if payload.get("id") else None
        row = row or Department()
        for key, value in defaults.items():
            setattr(row, key, value)
        row.save()
        return {"id": row.pk, "code": row.code, "name": row.name}

    def _save_position(self, payload):
        company = Company.objects.get(pk=int(payload.get("companyId")))
        department = Department.objects.get(pk=int(payload.get("departmentId")))
        if department.company_id != company.pk:
            raise ValueError("岗位所属部门不属于所选公司。")
        row = Position.objects.filter(pk=payload.get("id")).first() if payload.get("id") else None
        row = row or Position()
        row.code = str(payload.get("code") or "").strip()
        row.name = str(payload.get("name") or "").strip()
        row.company = company
        row.department = department
        row.is_active = payload.get("isActive", True) is not False
        if not row.code or not row.name:
            raise ValueError("岗位编码和名称不能为空。")
        row.save()
        return {"id": row.pk, "code": row.code, "name": row.name}

    def _save_employee(self, payload):
        department = Department.objects.get(pk=int(payload.get("departmentId")))
        position = Position.objects.get(pk=int(payload.get("positionId")))
        if position.department_id not in (None, department.pk):
            raise ValueError("岗位不属于所选部门。")
        row = Employee.objects.filter(pk=payload.get("id")).first() if payload.get("id") else None
        row = row or Employee()
        row.employee_no = str(payload.get("employeeNo") or "").strip()
        row.full_name = str(payload.get("fullName") or "").strip()
        row.phone = str(payload.get("phone") or "").strip()
        row.status = str(payload.get("status") or "active")
        row.department_ref = department
        row.position_ref = position
        row.department_id = department.pk
        row.department_name = department.name
        row.position = position.name
        if not row.employee_no or not row.full_name:
            raise ValueError("员工编号和姓名不能为空。")
        row.save()
        return employee_row(row)

    def _save_user(self, payload, *, actor, reason):
        row = User.objects.filter(pk=payload.get("id")).first() if payload.get("id") else None
        is_new = row is None
        if is_new:
            employee_id = payload.get("employeeId")
            if not employee_id:
                raise ValueError("新增账户必须选择一个尚未开户的在职员工。")
            employee = Employee.objects.select_related(
                "user", "department_ref", "position_ref"
            ).get(pk=int(employee_id))
            try:
                result = provision_employee_account(employee=employee, actor=actor, reason=reason)
            except EmployeeAccountProvisioningError as exc:
                raise ValueError(str(exc)) from exc
            account = result["account"]
            return {
                "id": account.pk,
                "username": account.username,
                "realName": account.real_name,
                "employeeId": result["employee"].pk,
                "created": result["created"],
                "idempotentReplay": result["idempotentReplay"],
                "credentialState": "PENDING_SECURE_INITIALIZATION" if not account.has_usable_password() else "ACTIVE",
                "passwordChanged": False,
                "auditId": result["auditId"],
            }
        username = str(payload.get("username") or row.username).strip()
        real_name = str(payload.get("realName") or "").strip()
        if not username or not real_name:
            raise ValueError("登录账号和真实姓名不能为空。")
        before = None if is_new else {
            "username": row.username, "realName": row.real_name,
            "companyId": row.company_id, "isActive": row.is_active,
            "isStaff": row.is_staff,
            "employeeId": getattr(getattr(row, "employee_profile", None), "pk", None),
        }
        row.username = username
        row.real_name = real_name
        row.email = str(payload.get("email") or "").strip() or None
        row.mobile = str(payload.get("mobile") or "").strip() or None
        row.company_id = int(payload.get("companyId"))
        row.is_active = payload.get("isActive", True) is not False
        row.is_staff = payload.get("isStaff", False) is True
        password = str(payload.get("password") or "")
        password_confirm = str(payload.get("passwordConfirm") or "")
        password_change_requested = payload.get("passwordChangeRequested") is True or is_new
        if not is_new and password and not password_change_requested:
            raise ValueError("修改现有账户密码必须明确勾选“重置密码”。")
        if password_change_requested and not password:
            raise ValueError("已选择重置密码，请填写新密码。")
        if password_change_requested and password != password_confirm:
            raise ValueError("两次输入的密码不一致。")
        if password_change_requested:
            row.set_password(password)
        row.save()
        credential_verification = None
        if password_change_requested:
            # Never acknowledge a reset only because set_password() returned.
            # Read the credential back through the same model/backend contract
            # used by normal login and fail the whole transaction if the exact
            # submitted secret cannot be verified after persistence.
            persisted = User.objects.only("password").get(pk=row.pk)
            if not persisted.check_password(password):
                raise ValueError("新密码未能通过持久化凭证回读校验，本次账户修改已撤销。")
            credential_verification = "PERSISTED_AND_VERIFIED"
        employee_id = payload.get("employeeId")
        if employee_id:
            employee = Employee.objects.get(pk=int(employee_id))
            if employee.user_id not in (None, row.pk):
                raise ValueError("该员工已关联其他登录账户。")
            Employee.objects.filter(user=row).exclude(pk=employee.pk).update(user=None)
            employee.user = row
            employee.save(update_fields=["user"])
        after = {
            "username": row.username, "realName": row.real_name,
            "companyId": row.company_id, "isActive": row.is_active,
            "isStaff": row.is_staff, "employeeId": int(employee_id) if employee_id else None,
            "passwordChanged": password_change_requested,
        }
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="CREATE_USER" if is_new else "UPDATE_USER",
            actor=actor,
            organization_id=row.company_id,
            target_type="User",
            target_id=row.pk,
            target_label=f"{row.username} - {row.real_name}",
            reason=reason,
            before_snapshot=before or {},
            after_snapshot=after,
        )
        return {"id": row.pk, "username": row.username, "realName": row.real_name,
            "passwordChanged": password_change_requested,
            "credentialVerification": credential_verification,
            "auditId": audit.pk}

    def _save_role(self, payload, *, actor, reason):
        name = str(payload.get("name") or "").strip()
        description = str(payload.get("description") or "").strip()
        if not name:
            raise ValueError("角色名称不能为空。")
        row = Role.objects.select_for_update().filter(pk=payload.get("id")).first() if payload.get("id") else None
        creating = row is None
        if creating:
            existing = Role.objects.select_for_update().filter(name=name).first()
            if existing:
                if existing.description != description:
                    raise ValueError("同名角色已经存在且说明不同，请从列表打开该角色维护。")
                return {
                    "id": existing.pk, "code": existing.code, "name": existing.name,
                    "created": False, "idempotentReplay": True,
                }
            code = allocate_code(company_id=actor.company_id, entity_type=ENTITY_ROLE)
            row = Role(code=code)
            before = {}
        else:
            code = row.code
            before = {"code": row.code, "name": row.name, "description": row.description}
        row.name = name
        row.description = description
        try:
            row.save()
        except IntegrityError:
            concurrent = Role.objects.filter(name=name, description=description).first()
            if creating and concurrent:
                return {
                    "id": concurrent.pk, "code": concurrent.code, "name": concurrent.name,
                    "created": False, "idempotentReplay": True,
                }
            raise
        after = {"code": row.code, "name": row.name, "description": row.description}
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="CREATE_ROLE" if creating else "UPDATE_ROLE",
            actor=actor,
            organization_id=actor.company_id,
            target_type="Role",
            target_id=row.pk,
            target_label=f"{row.code} - {row.name}",
            reason=reason,
            before_snapshot=before,
            after_snapshot=after,
        )
        return {
            "id": row.pk, "code": code, "name": row.name,
            "created": creating, "idempotentReplay": False, "auditId": audit.pk,
        }

    def _set_role_permissions(self, payload, *, actor, reason):
        role = Role.objects.get(pk=int(payload.get("roleId")))
        before_codes = list(RolePermission.objects.filter(role=role).order_by(
            "permission__code"
        ).values_list("permission__code", flat=True))
        codes = sorted({str(code) for code in payload.get("permissionCodes") or []})
        permissions_by_code = {row.code: row for row in Permission.objects.filter(code__in=codes)}
        if set(codes) != set(permissions_by_code):
            raise ValueError("包含不存在的权限点。")
        RolePermission.objects.filter(role=role).delete()
        RolePermission.objects.bulk_create([
            RolePermission(role=role, permission=permissions_by_code[code]) for code in codes
        ])
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="SET_ROLE_PERMISSIONS",
            actor=actor,
            organization_id=actor.company_id,
            target_type="Role",
            target_id=role.pk,
            target_label=f"{role.code} - {role.name}",
            reason=reason,
            before_snapshot={"permissionCodes": before_codes},
            after_snapshot={"permissionCodes": codes},
        )
        return {"roleCode": role.code, "permissionCodes": codes, "auditId": audit.pk}

    def _set_user_authorities(self, payload, *, actor, reason):
        user = User.objects.get(pk=int(payload.get("userId")))
        if user.is_superuser:
            raise ValueError("超级管理员使用 ALL 内建权限，不需要重复分配业务角色。")
        before = [{
            "roleCode": row.role.code,
            "legalEntityId": str(row.organization_id),
            "departmentId": row.department_id,
            "scopeCode": row.scope_code,
            "active": row.active,
        } for row in UserRoleScopeAssignment.objects.select_related("role").filter(user=user)]
        rows = payload.get("authorities") or []
        role_codes = {str(row.get("roleCode") or "") for row in rows}
        if set(Role.objects.filter(code__in=role_codes).values_list("code", flat=True)) != role_codes:
            raise ValueError("包含不存在的角色。")
        UserRoleScopeAssignment.objects.filter(user=user).delete()
        created = []
        for item in rows:
            scope_code = str(item.get("scopeCode") or "ORGANIZATION").upper()
            if scope_code not in {"SELF", "DEPARTMENT", "ORGANIZATION", "ALL"}:
                raise ValueError("数据权限范围无效。")
            organization = Company.objects.get(
                pk=int(item.get("legalEntityId") or user.company_id)
            )
            department = None
            if scope_code == "DEPARTMENT":
                department_id = str(item.get("departmentId") or "").strip()
                if not department_id:
                    raise ValueError("本部门数据范围必须选择部门。")
                department = Department.objects.get(pk=int(department_id))
                if department.company_id != organization.pk:
                    raise ValueError("授权部门不属于所选组织。")
            role = Role.objects.get(code=item["roleCode"])
            authority_payload = {
                "userId": user.pk,
                "roleCode": role.code,
                "legalEntityId": str(organization.pk),
                "departmentId": department.pk if department else None,
                "scopeCode": scope_code,
                "version": 1,
            }
            created.append(UserRoleScopeAssignment.objects.create(
                user=user,
                role=role,
                organization=organization,
                department=department,
                scope_code=scope_code,
                active=True,
                version=1,
                business_hash=business_hash(authority_payload),
            ))
        after = [{
            "roleCode": row.role.code,
            "legalEntityId": str(row.organization_id),
            "departmentId": row.department_id,
            "scopeCode": row.scope_code,
            "active": row.active,
        } for row in created]
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="SET_USER_AUTHORITIES",
            actor=actor,
            organization_id=actor.company_id,
            target_type="User",
            target_id=user.pk,
            target_label=f"{user.username} - {user.real_name}",
            reason=reason,
            before_snapshot={"authorities": before},
            after_snapshot={"authorities": after},
        )
        return {"userId": user.pk, "authorityCount": len(created), "auditId": audit.pk}

    def _set_review_participant_grant(self, payload, *, actor, reason):
        from pde.models import OrderReviewParticipantGrant

        grant = OrderReviewParticipantGrant.objects.select_related(
            "review", "employee", "user",
        ).get(pk=int(payload.get("grantId")))
        if grant.company_id != actor.company_id:
            raise ValueError("只能维护当前公司的评审对象授权。")
        before = {
            "active": grant.active,
            "canView": grant.can_view,
            "canMaintainOwnOpinion": grant.can_maintain_own_opinion,
            "canSignOwnItems": grant.can_sign_own_items,
            "reason": grant.reason,
        }
        grant.active = payload.get("active", grant.active) is True
        grant.can_view = payload.get("canView", grant.can_view) is True
        grant.can_maintain_own_opinion = payload.get(
            "canMaintainOwnOpinion", grant.can_maintain_own_opinion,
        ) is True
        grant.can_sign_own_items = payload.get(
            "canSignOwnItems", grant.can_sign_own_items,
        ) is True
        if grant.active and not any((
            grant.can_view, grant.can_maintain_own_opinion, grant.can_sign_own_items,
        )):
            raise ValueError("有效对象授权至少保留一项能力；如需全部关闭，请撤销授权。")
        grant.reason = reason
        grant.audit_hash = business_hash({
            "grantId": grant.pk, "actorId": actor.pk, "reason": reason,
            "active": grant.active, "canView": grant.can_view,
            "canMaintainOwnOpinion": grant.can_maintain_own_opinion,
            "canSignOwnItems": grant.can_sign_own_items,
            "version": grant.review_version_snapshot,
        })
        grant.save(update_fields=[
            "active", "can_view", "can_maintain_own_opinion", "can_sign_own_items",
            "reason", "audit_hash", "updated_at",
        ])
        after = {
            "active": grant.active,
            "canView": grant.can_view,
            "canMaintainOwnOpinion": grant.can_maintain_own_opinion,
            "canSignOwnItems": grant.can_sign_own_items,
            "reason": grant.reason,
        }
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="SET_REVIEW_PARTICIPANT_GRANT",
            actor=actor,
            organization_id=grant.company_id,
            target_type="OrderReviewParticipantGrant",
            target_id=grant.pk,
            target_label=(f"{grant.review.get_review_type_display()} #{grant.review_id} / "
                f"{grant.employee.employee_no} / {grant.user.username}"),
            reason=reason,
            before_snapshot=before,
            after_snapshot=after,
        )
        return {"grantId": grant.pk, **after, "auditId": audit.pk}
