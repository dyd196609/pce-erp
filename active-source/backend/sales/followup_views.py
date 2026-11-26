from datetime import date

from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pde.routing_read_context import routing_read_request
from pfm.models import Employee
from planning.work_order_models import ProductionWorkOrder
from system.models import OrganizationOperatingAuditRecord, User, UserRoleScopeAssignment
from workflow_runtime.fact_loads import successful_fact_load_facts
from workflow_runtime.models import BusinessStateTransition, UserOrganizationRoleAuthority

from .enterprise_authority import (
    CUSTOMER_BIND, CUSTOMER_PUBLISH, FOLLOWUP_ASSIGN, FOLLOWUP_VIEW,
    allowed, audit, audit_row, history, scoped_grants,
)
from .followup_models import CustomerAccountBinding, CustomerProgressPublication, ProductionFollowupAssignment
from .models import Customer, SalesOrder
from .views import SalesOrderDetailView


class AssignmentInput(serializers.Serializer):
    ownerId = serializers.IntegerField(min_value=1)
    expectedVersion = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=300)


class BindingInput(serializers.Serializer):
    accountId = serializers.IntegerField(min_value=1)
    customerId = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300)


class PublicationInput(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


def validated(serializer_type, request):
    serializer = serializer_type(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def response(request, data, count=1):
    facts = successful_fact_load_facts(result_count=count, api_url=request.path,
        tenant_id=str(request.user.company_id), request=request)
    return Response({"success": True, "data": {**data, "factLoadFacts": facts},
        "error": None, "meta": {"module": "EnterpriseEvidence", "source": "server"}})


def read_failure(request):
    from workflow_runtime.fact_loads import build_fact_load_facts
    message = "正式事实读取失败，结果待核。"
    facts = build_fact_load_facts(fact_load_status="read_failed", api_url=request.path,
        http_status=503, error_code="ENTERPRISE_FACT_READ_FAILED", error_message=message,
        tenant_id=str(request.user.company_id), batch_id="enterprise-evidence")
    return Response({"success": False, "error": {"code": facts["errorCode"],
        "message": message}, "data": {"factLoadFacts": facts}}, status=503)


def conflict(message):
    return Response({"success": False, "error": {"code": "VERSION_CONFLICT", "message": message}}, status=409)


def order_department_ids(order):
    orders = ProductionWorkOrder.objects.filter(company_id=order.company_id, status="released",
        usage_purpose="PRODUCTION_USE",
        production_plan__planning_requirement__demand__sales_order_item__sales_order=order)
    return set(orders.values_list("operations__work_center__department_id", flat=True))


def manager_can_assign(user, order):
    if allowed(user, FOLLOWUP_ASSIGN):
        return True
    if not scoped_grants(user, FOLLOWUP_ASSIGN).filter(scope_code="DEPARTMENT").exists():
        return False
    return allowed(user, FOLLOWUP_ASSIGN, order_department_ids(order), department_bound=True)


def follower_can_read(user, order):
    return (ProductionFollowupAssignment.objects.filter(order=order, owner=user).exists()
            and allowed(user, FOLLOWUP_VIEW, owner_id=user.pk))


def order_for_actor(user, order_no, lock=False):
    orders = SalesOrder.objects.filter(company_id=user.company_id, order_no=order_no)
    return (orders.select_for_update() if lock else orders).first()


def assignment_facts(assignment):
    return {
        "ownerId": assignment.owner_id if assignment else None,
        "owner": assignment.owner.real_name if assignment else None,
        "effectiveAt": assignment.effective_at.isoformat() if assignment else None,
        "version": assignment.version if assignment else 0,
    }


class EnterpriseView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        result = super().handle_exception(exc)
        messages = result.data
        if isinstance(messages, dict) and "detail" in messages:
            message = str(messages["detail"])
        elif isinstance(messages, dict):
            message = "；".join(str(item) for value in messages.values()
                for item in (value if isinstance(value, list) else [value]))
        else:
            message = "；".join(map(str, messages))
        result.data = {"success": False, "data": None,
            "error": {"code": f"HTTP_{result.status_code}", "message": message}}
        return result


class FollowupDirectoryView(EnterpriseView):
    def get(self, request):
        actor = request.user
        manage = allowed(actor, FOLLOWUP_ASSIGN) or scoped_grants(actor, FOLLOWUP_ASSIGN).filter(scope_code="DEPARTMENT").exists()
        if not manage and not allowed(actor, FOLLOWUP_VIEW, owner_id=actor.pk):
            raise PermissionDenied("当前岗位没有生产跟单入口权限。")
        orders = SalesOrder.objects.filter(company_id=actor.company_id)
        order_no = request.query_params.get("orderNo", "").strip()
        if order_no:
            orders = orders.filter(order_no=order_no)
        if not manage or not order_no:
            orders = orders.filter(productionfollowupassignment__owner=actor)
        rows = [
            {"orderNo": order.order_no, "approvalLabel": order.get_status_display()}
            for order in orders.order_by("order_no")
            if follower_can_read(actor, order) or (manage and manager_can_assign(actor, order))
        ]
        candidates = []
        if manage:
            users = User.objects.filter(company_id=actor.company_id, is_active=True, is_superuser=False,
                role_scope_assignments__active=True,
                role_scope_assignments__role__rolepermission__permission__code=FOLLOWUP_VIEW).distinct()
            candidates = [{"id": candidate.pk, "name": candidate.real_name} for candidate in users
                if allowed(candidate, FOLLOWUP_VIEW, owner_id=candidate.pk)]
        return response(request, {"orders": rows, "candidates": candidates,
            "searchByOrderNo": manage}, len(rows))


class FollowupOrderView(EnterpriseView):
    @routing_read_request
    def get(self, request, order_no):
        actor = request.user
        try:
            order = order_for_actor(actor, order_no)
            can_assign = bool(order and manager_can_assign(actor, order))
            if not order or not (can_assign or follower_can_read(actor, order)):
                raise NotFound("当前范围没有可查看的生产跟单订单。")
            assignment = ProductionFollowupAssignment.objects.filter(order=order).select_related("owner").first()
            result = {"orderNo": order.order_no, "approvalLabel": order.get_status_display(),
                "assignment": assignment_facts(assignment),
                "actions": [{"code": FOLLOWUP_ASSIGN, "label": "移交跟单" if assignment else "分派跟单"}]
                if can_assign else []}
            if can_assign:
                result["history"] = [audit_row(row) for row in history(actor,
                    "ProductionFollowupAssignment", assignment.pk)] if assignment else []
            if request.query_params.get("includeProgress") == "1":
                task_query = request.query_params.get("progressTaskId")
                if task_query is not None and (
                    not task_query.isascii() or not task_query.isdecimal() or len(task_query) > 18 or int(task_query) <= 0
                ):
                    raise ValidationError("请从订单生产进度选择工序。")
                task_id = int(task_query) if task_query is not None else None
                completion, progress = SalesOrderDetailView()._read_production_facts(
                    order, include_progress=True, selected_task_id=task_id)
                if progress is None or progress["factStatus"] == "READ_FAILED":
                    return read_failure(request)
                if task_id is not None:
                    selected = [task for line in progress["lines"] for wo in line["workOrders"]
                        for task in wo.get("tasks") or [] if task["taskId"] == task_id]
                    if len(selected) != 1:
                        raise NotFound("当前订单已核实范围没有该工序。")
                    progress["selectedTask"] = selected[0]
                result.update(completion=completion, progress=progress, order={
                    "id": order.pk, "orderNo": order.order_no, "version": order.version, "progressFacts": progress,
                })
            return response(request, result)
        except DatabaseError:
            return read_failure(request)

    @transaction.atomic
    def post(self, request, order_no):
        values = validated(AssignmentInput, request)
        actor = request.user
        order = order_for_actor(actor, order_no, lock=True)
        if not order or not manager_can_assign(actor, order):
            raise PermissionDenied("当前岗位不可分派此订单。")
        owner = User.objects.filter(pk=values["ownerId"], company_id=actor.company_id,
            is_active=True, is_superuser=False).first()
        if not owner or not allowed(owner, FOLLOWUP_VIEW, owner_id=owner.pk):
            raise ValidationError({"ownerId": "此账号没有生效的生产跟单岗位授权。"})
        assignment = ProductionFollowupAssignment.objects.select_for_update().filter(order=order).first()
        before = assignment_facts(assignment)
        if before["version"] != values["expectedVersion"]:
            return conflict("跟单责任已变化，请读取最新记录。")
        if assignment and assignment.owner_id == owner.pk:
            return conflict("该账号已经负责这张订单。")
        now = timezone.now()
        if assignment:
            assignment.owner = owner
            assignment.effective_at = now
            assignment.version += 1
            assignment.save(update_fields=["owner", "effective_at", "version"])
        else:
            assignment = ProductionFollowupAssignment.objects.create(order=order, owner=owner, effective_at=now)
        after = assignment_facts(assignment)
        audit(actor, FOLLOWUP_ASSIGN, assignment, order.order_no, values["reason"], before, after)
        return response(request, {"assignment": after})


def dedicated_account(account):
    return (account.is_active and not account.is_staff and not account.is_superuser
        and not account.groups.exists() and not account.user_permissions.exists()
        and not Employee.objects.filter(user=account).exists()
        and not UserRoleScopeAssignment.objects.filter(user=account, active=True).exists()
        and not UserOrganizationRoleAuthority.objects.filter(user=account, active=True).exists())


class CustomerBindingView(EnterpriseView):
    @transaction.atomic
    def post(self, request):
        actor = request.user
        if not allowed(actor, CUSTOMER_BIND):
            raise PermissionDenied("当前岗位没有客户身份核实与绑定权限。")
        data = validated(BindingInput, request)
        account = User.objects.select_for_update().filter(pk=data["accountId"], company_id=actor.company_id).first()
        customer = Customer.objects.filter(pk=data["customerId"], company_id=actor.company_id, is_active=True).first()
        if not account or not customer or not dedicated_account(account):
            raise ValidationError("请选择本企业有效客户和经过身份核实的独立客户账号。")
        if CustomerAccountBinding.objects.filter(account=account).exists():
            return conflict("此客户账号已有生效绑定。")
        binding = CustomerAccountBinding.objects.create(account=account, customer=customer, effective_at=timezone.now())
        audit(actor, CUSTOMER_BIND, binding, customer.code, data["reason"], {},
              {"accountId": account.pk, "customerId": customer.pk, "effectiveAt": binding.effective_at.isoformat()})
        return response(request, {"customerCode": customer.code, "bound": True})

    def get(self, request):
        actor = request.user
        if not allowed(actor, CUSTOMER_BIND):
            raise PermissionDenied("当前岗位没有客户身份核实与绑定权限。")
        customers = Customer.objects.filter(company_id=actor.company_id, is_active=True)
        accounts = User.objects.filter(company_id=actor.company_id, is_active=True,
                                       is_staff=False, is_superuser=False)
        available = [{"id": row.pk, "username": row.username, "name": row.real_name}
            for row in accounts if dedicated_account(row) and not CustomerAccountBinding.objects.filter(account=row).exists()]
        return response(request, {"accounts": available,
            "customers": list(customers.values("id", "code", "name"))}, len(available))


PUBLIC_MILESTONE_ACTIONS = {"sales.order.approve": ("approved", "订单已批准")}


def committed_delivery(order):
    info = order.delivery_information
    value = info.get("committedDeliveryDate") if isinstance(info, dict) else None
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def valid_publication_source(source):
    prefix, _, raw_id = source.audit_reference.partition(":")
    return prefix == "OrganizationOperatingAuditRecord" and raw_id.isascii() and raw_id.isdecimal() and len(raw_id) <= 18 and (
        OrganizationOperatingAuditRecord.objects.filter(pk=int(raw_id), target_type="SalesOrder",
            target_id=source.object_id, actor_id=source.operator_id, action_code=source.action_code).exists()
    )


def public_order(order):
    milestones = []
    for publication in CustomerProgressPublication.objects.filter(order=order,
            source__object_type="SalesOrder", source__object_id=order.pk).select_related("source").order_by("published_at"):
        definition = PUBLIC_MILESTONE_ACTIONS.get(publication.source.action_code)
        if definition and publication.source.target_state == definition[0] and valid_publication_source(publication.source):
            milestones.append({"label": definition[1], "publishedAt": publication.published_at.isoformat()})
    return {"orderNo": order.order_no, "milestones": milestones,
            "committedDeliveryDate": committed_delivery(order),
            "shipmentStatus": None, "receiptStatus": None}


class CustomerOrderProgressView(EnterpriseView):
    def get(self, request, order_no=None):
        actor = request.user
        binding = CustomerAccountBinding.objects.filter(account=actor,
            customer__company_id=actor.company_id, customer__is_active=True).first()
        if not binding or not dedicated_account(actor):
            raise PermissionDenied("当前账号未关联有效客户档案。")
        orders = SalesOrder.objects.filter(company_id=actor.company_id, customer_id=binding.customer_id,
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE).exclude(status__in=["draft", "submitted"])
        if order_no is not None:
            order = orders.filter(order_no=order_no).first()
            if not order:
                raise NotFound("当前账号没有可查询的该订单。")
            return Response({"order": public_order(order)})
        return Response({"orders": [public_order(order) for order in orders.order_by("order_no")]})


class CustomerProgressPublicationView(EnterpriseView):
    @transaction.atomic
    def post(self, request, order_no):
        actor = request.user
        if not allowed(actor, CUSTOMER_PUBLISH):
            raise PermissionDenied("当前岗位没有客户里程碑发布权限。")
        data = validated(PublicationInput, request)
        order = order_for_actor(actor, order_no, lock=True)
        if not order or order.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE:
            raise NotFound("未找到可发布的正式销售订单。")
        source = BusinessStateTransition.objects.filter(object_type="SalesOrder", object_id=order.pk,
            action_code="sales.order.approve", target_state="approved").exclude(audit_reference="").order_by("-version").first()
        if not source or order.status in {"draft", "submitted", "cancelled"} or not valid_publication_source(source):
            raise ValidationError("正式审批依据尚未核实，当前不能发布。")
        publication, created = CustomerProgressPublication.objects.get_or_create(
            order=order, source=source, defaults={"published_at": timezone.now()})
        if created:
            audit(actor, CUSTOMER_PUBLISH, publication, order.order_no, data["reason"], {},
                  {"sourceTransitionId": source.pk, "publishedAt": publication.published_at.isoformat()})
        return response(request, {"published": True})
