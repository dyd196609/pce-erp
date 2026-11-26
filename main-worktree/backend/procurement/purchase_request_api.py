from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from masterdata.material_master_runtime import MaterialMasterRuntimeAdapter
from masterdata.models import BudgetCategory, CostCenter, ExpenseCategory, ProjectMaster
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.models import Department

from .models import PurchaseRequest, PurchaseRequestApprovalRecord, Supplier
from .serializers import PurchaseRequestSerializer
from .business_action_control import authorize_action, record_action_audit


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseRequestSerializer
    queryset = PurchaseRequest.objects.all().order_by("-id")
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        query = str(self.request.query_params.get("search") or "").strip()
        status_code = str(self.request.query_params.get("status") or "").strip()
        if query:
            queryset = queryset.filter(request_no__icontains=query)
        if status_code:
            queryset = queryset.filter(status=status_code)
        return queryset

    @staticmethod
    def _next_request_no(request_date=None):
        numbering_date = request_date or timezone.localdate()
        prefix = f"PR{numbering_date:%Y%m%d}"
        latest = PurchaseRequest.objects.filter(request_no__startswith=prefix).order_by("-request_no").first()
        suffix = str(latest.request_no)[len(prefix):] if latest else ""
        sequence = int(suffix) + 1 if suffix.isdigit() else 1
        return f"{prefix}{sequence:04d}"

    @transaction.atomic
    def perform_create(self, serializer):
        department = serializer.validated_data["department_master"]
        employee_id = serializer.validated_data["requester_employee_id"]
        owner_user_id = formal_employee_queryset(company_id=department.company_id).filter(
            pk=employee_id
        ).values_list("user_id", flat=True).first()
        decision = authorize_action(
            user=self.request.user,
            action_code="procurement.purchase_request.create",
            organization_id=department.company_id,
            business_object={
                "organizationId": department.company_id,
                "departmentId": department.pk,
                "ownerUserId": owner_user_id,
            },
        )
        if not decision["allowed"]:
            raise PermissionDenied(decision["reason"], code=decision["decisionCode"])
        value = serializer.save(
            request_no=self._next_request_no(serializer.validated_data.get("request_date")),
            status="draft",
        )
        record_action_audit(
            user=self.request.user,
            action_code="procurement.purchase_request.create",
            organization_id=department.company_id,
            target_type="PurchaseRequest",
            target_id=value.pk,
            target_no=value.request_no,
            before={"exists": False, "status": None},
            after={"exists": True, "status": value.status, "approvalStatus": value.approval_status},
            authorization=decision,
        )

    def destroy(self, request, *args, **kwargs):
        value = self.get_object()
        if value.status != "draft":
            return Response({"error": "只有草稿采购申请允许删除"}, status=status.HTTP_409_CONFLICT)
        value.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _transition(self, request, expected, target, error_message):
        with transaction.atomic():
            value = PurchaseRequest.objects.select_for_update().get(pk=self.get_object().pk)
            action_code = {
                "submitted": "purchase_request.submit",
                "approved": "purchase_request.approve",
            }.get(target)
            organization_id = (
                value.department_master.company_id if value.department_master_id
                else getattr(request.user, "company_id", None)
            )
            employee = formal_employee_queryset(company_id=organization_id).filter(
                pk=value.requester_employee_id
            ).first()
            decision = None
            if action_code:
                decision = authorize_action(
                    user=request.user,
                    action_code=action_code,
                    organization_id=organization_id,
                    business_object={
                        "organizationId": organization_id,
                        "departmentId": value.department_master_id,
                        "ownerUserId": employee.user_id if employee else None,
                    },
                )
                if not decision["allowed"]:
                    raise PermissionDenied(decision["reason"], code=decision["decisionCode"])
            if value.status != expected:
                return Response({"error": error_message}, status=status.HTTP_409_CONFLICT)
            from_status = value.status
            actor = request.user.get_username() if request.user and request.user.is_authenticated else value.requester
            value.status = target
            update_fields = ["status", "updated_at"]
            if target == "submitted":
                value.approval_status = "pending"
                value.approval_current_node = "采购经理审批"
                value.approval_current_approver = "采购经理"
                value.approval_result = ""
                update_fields.extend(["approval_status", "approval_current_node", "approval_current_approver", "approval_result"])
            elif target == "approved":
                value.approval_status = "completed"
                value.approval_current_node = "审批完成"
                value.approval_current_approver = actor or "采购经理"
                value.approval_result = "通过"
                update_fields.extend(["approval_status", "approval_current_node", "approval_current_approver", "approval_result"])
            value.save(update_fields=update_fields)
            if target in {"submitted", "approved"}:
                PurchaseRequestApprovalRecord.objects.create(
                    purchase_request=value,
                    action="submit" if target == "submitted" else "approve",
                    from_status=from_status,
                    to_status=target,
                    node_name=value.approval_current_node,
                    actor=actor,
                    comment="提交审批" if target == "submitted" else "审批通过",
                )
            if action_code:
                record_action_audit(
                    user=request.user,
                    action_code=action_code,
                    organization_id=organization_id,
                    target_type="PurchaseRequest",
                    target_id=value.pk,
                    target_no=value.request_no,
                    before={"status": from_status},
                    after={
                        "status": value.status,
                        "approvalStatus": value.approval_status,
                        "approvalCurrentNode": value.approval_current_node,
                        "approvalResult": value.approval_result,
                    },
                    authorization=decision,
                )
        return Response(self.get_serializer(value).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._transition(request, "draft", "submitted", "只有草稿采购申请允许提交审批")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, "submitted", "approved", "只有已提交采购申请允许审批")

    @action(detail=True, methods=["get"], url_path="inquiry-eligibility")
    def inquiry_eligibility(self, request, pk=None):
        value = self.get_object()
        payload = self.get_serializer(value).data["inquiryEligibility"]
        return Response({"success": True, "data": payload, "productionUserDataWritten": False})

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        value = self.get_object()
        if value.status == "converted":
            return Response({"error": "已转询价采购申请不能直接关闭"}, status=status.HTTP_409_CONFLICT)
        return self._transition(request, value.status, "closed", "采购申请状态不允许关闭")


class PurchaseRequestReferenceView(APIView):
    """采购申请智能表单的有界、只读主数据搜索。"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reference_type):
        query = str(request.query_params.get("q") or "").strip()
        try:
            limit = min(max(int(request.query_params.get("limit") or 20), 1), 200)
        except (TypeError, ValueError):
            limit = 20
        fetch_limit = limit + 1
        if reference_type == "organization-tree":
            values = list(Department.objects.select_related("company", "parent").filter(is_active=True).order_by("company_id", "parent_id", "code", "id")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name,
                        "parentId": value.parent_id, "companyId": value.company_id,
                        "companyName": value.company.name} for value in values[:limit]]
        elif reference_type == "employees":
            values = list(formal_employee_queryset(
                Employee.objects.select_related("department_ref", "position_ref"),
                company_id=request.user.company_id,
            ).filter(
                Q(employee_no__icontains=query) | Q(full_name__icontains=query)
                | Q(department_ref__name__icontains=query)
            ).order_by("employee_no")[:fetch_limit])
            results = [{"id": value.pk, "employeeNo": value.employee_no, "name": value.full_name,
                        "departmentId": value.department_ref_id,
                        "departmentName": value.department_ref.name}
                       for value in values[:limit]]
        elif reference_type in {"departments", "purchase-organizations"}:
            queryset = Department.objects.filter(is_active=True).filter(Q(name__icontains=query) | Q(code__icontains=query))
            if reference_type == "purchase-organizations":
                queryset = queryset.filter(name__icontains="采购")
            values = list(queryset.order_by("code", "id")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name} for value in values[:limit]]
        elif reference_type == "materials":
            values = MaterialMasterRuntimeAdapter.list_runtime_models(query, limit=fetch_limit)
            results = [value.to_reference_dict() for value in values[:limit]]
        elif reference_type == "projects":
            values = list(ProjectMaster.objects.filter(is_active=True).filter(
                Q(code__icontains=query) | Q(name__icontains=query) | Q(stage__icontains=query)
            ).order_by("code")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name, "stage": value.stage,
                        "owner": value.owner, "status": "启用" if value.is_active else "停用",
                        "recommendedCostCenterId": value.recommended_cost_center_id}
                       for value in values[:limit]]
        elif reference_type == "cost-centers":
            values = list(CostCenter.objects.filter(is_active=True).filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            ).order_by("code")[:fetch_limit])
            department_names = dict(Department.objects.filter(id__in=[value.department_id for value in values if value.department_id]).values_list("id", "name"))
            results = [{"id": value.pk, "code": value.code, "name": value.name, "departmentId": value.department_id,
                        "departmentName": department_names.get(value.department_id, "")} for value in values[:limit]]
        elif reference_type == "expense-categories":
            values = list(ExpenseCategory.objects.filter(is_active=True).filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            ).order_by("code")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name} for value in values[:limit]]
        elif reference_type == "budget-categories":
            values = list(BudgetCategory.objects.filter(is_active=True).filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            ).order_by("code")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name} for value in values[:limit]]
        elif reference_type == "suppliers":
            values = list(Supplier.objects.filter(is_active=True).filter(
                Q(code__icontains=query) | Q(name__icontains=query) | Q(short_name__icontains=query)
            ).order_by("code")[:fetch_limit])
            results = [{"id": value.pk, "code": value.code, "name": value.name} for value in values[:limit]]
        else:
            return Response({"success": False, "error": {"message": "未知基础资料类型"}}, status=status.HTTP_404_NOT_FOUND)

        return Response({"success": True, "data": {"results": results, "hasMore": len(values) > limit, "limit": limit},
                         "meta": {"source": "server", "readOnly": True, "productionUserDataWritten": False}})
