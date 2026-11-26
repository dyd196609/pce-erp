"""Read-only navigation adapters. Never import or replay admission execution."""
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import SalesOrder
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import ProcessDefinition, WorkflowInstance, BusinessStateTransition
from workflow_runtime.fact_loads import failed_fact_load_facts
from .manufacturing_admission_responsibility_service import (
    PROCESS_CODE, NODE_CODE, DOCUMENT_TYPE, PERMISSION_CODE, ROLE_CODE, RESPONSIBILITY_CODE,
)
from .views import _facts, ProductManufacturingOutputListView


def _read_failure(request, *, status_code, error_code, error_message):
    facts = failed_fact_load_facts(api_url=request.path, http_status=status_code,
        error_code=error_code, error_message=error_message,
        tenant_id=str(getattr(request.user, "company_id", "") or "server-context-unavailable"), request=request)
    surface = {**facts, "factLoadFacts": facts, "passed": False, "recordCount": None,
        "factSource": "server", "businessWriteCount": 0}
    return Response({**surface, "error": {"code": error_code, "message": error_message},
        **{key: dict(surface) for key in ("apiFacts", "pageFacts", "strictFacts", "diagnosticFacts", "acceptanceFacts")}}, status=status_code)


@method_decorator(never_cache, name="dispatch")
class ManufacturingAdmissionHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    page_code = "pde-manufacturing-admissions"

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        return _read_failure(self.request, status_code=response.status_code,
            error_code="MANUFACTURING_ADMISSION_READ_DENIED",
            error_message="制造承接历史读取未获准；本入口不提供确认执行。")

    def get(self, request):
        # Same authenticated-company read boundary as the existing PDE lists.
        # Execute role/action metadata is not a read grant or an execution claim.
        if not request.user.is_active or not request.user.company_id:
            return _read_failure(request, status_code=403, error_code="READ_SCOPE_REQUIRED",
                error_message="需要有效账号及所属公司范围。")
        try:
            definition = ProcessDefinition.objects.get(definition_code=PROCESS_CODE, active=True)
            nodes = list(definition.nodes.filter(active=True))
            if len(nodes) != 1:
                raise ValueError("制造承接正式节点数量不一致。")
            node = nodes[0]
            if definition.document_type != DOCUMENT_TYPE or node.node_code != NODE_CODE or node.business_action_code != PERMISSION_CODE:
                raise ValueError("制造承接正式流程映射不一致。")
            orders = SalesOrder.objects.filter(company_id=request.user.company_id)
            if request.query_params.get("orderId"):
                orders = orders.filter(pk=int(request.query_params["orderId"]))
            if request.query_params.get("q"):
                orders = orders.filter(order_no__icontains=request.query_params["q"].strip())
            order_map = {o.pk: o for o in orders}
            workflows = WorkflowInstance.objects.filter(process_definition=definition,
                document_type=DOCUMENT_TYPE, document_id__in=order_map).order_by("pk")
            rows = [self.project(w, order_map[w.document_id]) for w in workflows]
            payload = _facts(self.page_code, rows, request)
            common = {
                "businessObject": DOCUMENT_TYPE,
                "processBinding": {"processDefinitionId": definition.pk, "processCode": PROCESS_CODE,
                    "workflowNodeId": node.pk, "nodeCode": NODE_CODE,
                    "actionCode": PERMISSION_CODE, "roleCode": ROLE_CODE,
                    "responsibilityType": RESPONSIBILITY_CODE},
                "readOnly": True, "executionEnabled": False, "businessWriteCount": 0,
                "stateMachineConsistent": all(r["stateMachineConsistent"] for r in rows),
                "passed": True,
                "records": rows,
            }
            for key in ("apiFacts", "pageFacts", "strictFacts", "diagnosticFacts", "acceptanceFacts"):
                payload[key].update(common)
            return Response(payload)
        except (ProcessDefinition.DoesNotExist, ValueError, LookupError) as exc:
            return _read_failure(request, status_code=409, error_code="MANUFACTURING_ADMISSION_FACTS_INCONSISTENT",
                error_message=str(exc))
        except DatabaseError:
            return _read_failure(request, status_code=503, error_code="MANUFACTURING_ADMISSION_READ_FAILED",
                error_message="制造承接正式历史读取失败，不能降级为零记录或模拟确认。")

    @staticmethod
    def project(workflow, order):
        tasks = list(workflow.tasks.order_by("pk"))
        if len(tasks) != 1:
            raise ValueError("制造承接流程任务数量不一致。")
        task = tasks[0]
        decisions = list(task.decisions.select_related("actor").order_by("pk"))
        transitions = list(BusinessStateTransition.objects.filter(
            object_type=DOCUMENT_TYPE, object_id=order.pk, workflow_instance=workflow).order_by("pk"))
        if workflow.status != "approved" or task.status != "approved" or len(decisions) != 1 or len(transitions) != 1:
            raise ValueError("制造承接历史尚未形成完整确认事实。")
        decision, transition = decisions[0], transitions[0]
        reference = transition.audit_reference
        prefix = "OrganizationOperatingAuditRecord:"
        audit = OrganizationOperatingAuditRecord.objects.filter(
            pk=int(reference[len(prefix):]) if reference.startswith(prefix) else None).first()
        if not (audit and decision.decision == "approved" and decision.action_id == PERMISSION_CODE
            and transition.source_state == "READY" and transition.target_state == "CONFIRMED"
            and transition.action_code == PERMISSION_CODE
            and audit.action_code == PERMISSION_CODE and audit.target_type == DOCUMENT_TYPE
            and audit.target_id == order.pk and audit.organization_id == order.company_id
            and decision.actor_id == transition.operator_id == audit.actor_id
            and decision.actor_id != order.created_by_id
            and workflow.completed_at and task.completed_at
            and task.required_role_code == ROLE_CODE
            and audit.after_snapshot.get("workflowInstanceId") == workflow.pk
            and audit.after_snapshot.get("approvalTaskId") == task.pk
            and audit.after_snapshot.get("approvalDecisionId") == decision.pk
            and audit.after_snapshot.get("responsibleUserId") == decision.actor_id
            and audit.after_snapshot.get("roleCode") == ROLE_CODE
            and audit.after_snapshot.get("responsibilityCode") == RESPONSIBILITY_CODE
            and audit.after_snapshot.get("processCode") == PROCESS_CODE
            and audit.after_snapshot.get("nodeCode") == NODE_CODE
            and audit.after_snapshot.get("manufacturingAdmissionStatus") == "CONFIRMED"):
            raise ValueError("制造承接决定、转换、责任人与审计证据不一致。")
        employee = getattr(decision.actor, "employee_profile", None)
        return {
            "id": workflow.pk, "orderId": order.pk, "orderNo": order.order_no,
            "statusLabel": "已确认", "salesOrderStatusLabel": order.get_status_display(),
            "workflowInstanceId": workflow.pk, "workflowInstanceNo": workflow.instance_no,
            "workflowStatusLabel": "已完成", "approvalTaskId": task.pk, "taskStatusLabel": "已批准",
            "approvalDecisionId": decision.pk, "decisionLabel": "同意制造承接",
            "businessStateTransitionId": transition.pk, "auditId": audit.pk,
            "responsibleUserId": decision.actor_id,
            "responsibleName": employee.full_name if employee else decision.actor.username,
            "responsibleAccount": decision.actor.username,
            "confirmedAt": decision.completed_at.isoformat(),
            "responsibilityLabel": "制造承接确认责任人", "stateMachineConsistent": True,
            "statusTransitionCount": len(transitions),
            "statusTransitionHistory": [{"id": transition.pk, "statusLabel": "制造承接已确认",
                "actorId": transition.operator_id, "auditReference": reference,
                "occurredAt": transition.timestamp.isoformat()}],
        }


@method_decorator(never_cache, name="dispatch")
class MrpInputSourceReadView(ProductManufacturingOutputListView):
    """Retain the original engineering-source viewing capability, not MRP execution."""
    page_code = "pde-mrp-input-preparation"
    http_method_names = ["get", "head", "options"]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        return _read_failure(self.request, status_code=response.status_code,
            error_code="MRP_INPUT_SOURCE_READ_DENIED", error_message="MRP工程来源入口仅允许正式只读访问。")

    def get(self, request):
        try:
            response = super().get(request)
        except DatabaseError:
            return _read_failure(request, status_code=503, error_code="MRP_INPUT_SOURCE_READ_FAILED",
                error_message="正式工程输入来源读取失败，不降级为空记录。")
        for key in ("apiFacts", "pageFacts", "strictFacts", "diagnosticFacts", "acceptanceFacts"):
            response.data[key].update({"readOnly": True, "executionEnabled": False,
                "businessObject": "PdeMrpInputSource", "sourceBusinessObject": "ProductManufacturingOutput",
                "sourceDataAuthority": "pde.ProductManufacturingOutput", "businessWriteCount": 0,
                "sourcePurpose": "后续计划节点的工程输入来源查看；不执行MRP"})
        return response
