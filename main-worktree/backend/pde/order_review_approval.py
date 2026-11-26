"""Unified final approval integration for submitted itemized reviews."""

from hashlib import sha256
import json

from django.db import transaction
from django.utils import timezone

from system.authorization import AuthorizationService
from system.models import UserRoleScopeAssignment
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    ProcessDefinition,
    SegregationOfDutiesAuthority,
    WorkflowInstance,
    WorkflowNodeDefinition,
)

from .models import OrderCrossFunctionalReview, OrderReviewItemAudit


APPROVAL_CONFIG = {
    "CRM_ORDER_REVIEW": {
        "documentType": "CRMOrderReview",
        "processCode": "CRM_ORDER_REVIEW_FINAL_APPROVAL",
        "processName": "订单评审最终审批",
        "businessDomain": "CRM",
        "permissionCode": "sales.order_review.final_approve",
        "requiredRoleCode": "crm_order_review_final_approver",
    },
    "PDE_PRODUCTION_FEASIBILITY": {
        "documentType": "PDEProductionFeasibilityReview",
        "processCode": "PDE_PRODUCTION_FEASIBILITY_FINAL_APPROVAL",
        "processName": "生产可行性评审最终审批",
        "businessDomain": "PDE",
        "permissionCode": "pde.production_feasibility_review.final_approve",
        # PDE uses the normal permission-role-scope chain.  A custom legitimate
        # role is valid; no account, role code or employee name is hard-coded.
        "requiredRoleCode": "",
    },
}


def _config(review_or_type):
    review_type = getattr(review_or_type, "review_type", review_or_type)
    config = APPROVAL_CONFIG.get(str(review_type or ""))
    if not config:
        raise OrderReviewApprovalError("APPROVAL_POLICY_NOT_APPLICABLE", "当前评审类型未配置最终审批规则。", 409)
    return config


class OrderReviewApprovalError(ValueError):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def ensure_order_review_approval_configuration(review_type="CRM_ORDER_REVIEW"):
    config = _config(review_type)
    process, process_created = ProcessDefinition.objects.update_or_create(
        definition_code=config["processCode"],
        defaults={
            "definition_name": config["processName"],
            "business_domain": config["businessDomain"],
            "description": f"{config['processName']}：意见完成并提交后，由正式权限人作出最终通过或不通过决定。",
            "document_type": config["documentType"],
            "version": 1,
            "active": True,
            "definition_hash": _hash({
                "definitionCode": config["processCode"],
                "documentType": config["documentType"],
                "requiredRoleCode": config["requiredRoleCode"],
                "permissionCode": config["permissionCode"],
                "version": 1,
            }),
        },
    )
    node, node_created = WorkflowNodeDefinition.objects.update_or_create(
        process_definition=process,
        node_code="FINAL_APPROVAL",
        defaults={
            "node_name": "最终审批",
            "sequence": 1,
            "business_action_code": config["permissionCode"],
            "active": True,
            "description": f"针对明确的已提交{config['processName'].removesuffix('最终审批')}版本作出最终决定。",
        },
    )
    return {
        "processDefinitionId": process.pk,
        "processCreated": process_created,
        "nodeDefinitionId": node.pk,
        "nodeCreated": node_created,
        "userAuthorityWrites": 0,
    }


def _workflow(review, *, lock=False):
    config = _config(review)
    queryset = WorkflowInstance.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(document_type=config["documentType"], document_id=review.pk).first()


def _configured_approver_assignments(review):
    config = _config(review)
    queryset = UserRoleScopeAssignment.objects.select_related("user", "role").filter(
        role__rolepermission__permission__code=config["permissionCode"],
        organization_id=review.company_id,
        active=True,
        user__is_active=True,
    ).distinct()
    if config["requiredRoleCode"]:
        queryset = queryset.filter(role__code=config["requiredRoleCode"])
    return queryset


def approval_authorization(user, review):
    config = _config(review)
    decision = AuthorizationService.decide(
        user=user,
        action_code=config["permissionCode"],
        organization_id=review.company_id,
        business_object={"companyId": review.company_id},
    )
    formal_roles = {
        row.role_code
        for row in AuthorizationService.authority_evidence(user, review.company_id)
        if row.source == "system.UserRoleScopeAssignment"
    }
    qualifying_roles = set(_configured_approver_assignments(review).filter(user=user).values_list("role__code", flat=True))
    required_role_ok = not config["requiredRoleCode"] or config["requiredRoleCode"] in formal_roles
    allowed = bool(decision.get("allowed") and qualifying_roles and required_role_ok)
    subject = config["processName"]
    reason = (
        f"{subject}角色、专门权限和组织范围均已通过。"
        if allowed
        else f"当前账号未通过{subject}角色、专门权限和组织范围校验。"
    )
    return {
        **decision,
        "allowed": allowed,
        "reason": reason,
        "decisionCode": "ALLOWED_FINAL_APPROVER" if allowed else "FINAL_APPROVER_ROLE_REQUIRED",
        "facts": {
            "visible": allowed,
            "executable": allowed,
            "disabledReason": "" if allowed else reason,
        },
        "requiredRoleCode": config["requiredRoleCode"],
        "requiredPermissionCode": config["permissionCode"],
        "superuserDoesNotBypass": True,
    }


def _parse_comment(comment):
    try:
        payload = json.loads(comment or "{}")
    except (TypeError, ValueError):
        return {"approvalOpinion": comment or "", "riskHandling": ""}
    if not isinstance(payload, dict):
        return {"approvalOpinion": str(payload), "riskHandling": ""}
    return {
        "approvalOpinion": str(payload.get("approvalOpinion") or ""),
        "riskHandling": str(payload.get("riskHandling") or ""),
    }


def build_approval_facts(*, user, review):
    if not review:
        return {
            "applicable": False,
            "policy": "尚无已提交版本，最终审批关系尚未形成。",
        }
    config = _config(review)
    workflow = _workflow(review)
    task = workflow.tasks.order_by("step_no", "id").first() if workflow else None
    decision_row = task.decisions.select_related("actor").order_by("-decision_sequence", "-id").first() if task else None
    configured = _configured_approver_assignments(review)
    authorization = approval_authorization(user, review)
    final_decision = None
    if decision_row:
        detail = _parse_comment(decision_row.comment)
        final_decision = {
            "decision": "APPROVE" if decision_row.decision == "approved" else "REJECT",
            "decisionLabel": "通过" if decision_row.decision == "approved" else "不通过",
            "approver": {
                "userId": decision_row.actor_id,
                "username": decision_row.actor.username,
                "name": decision_row.actor.real_name,
            },
            "approvedAt": decision_row.completed_at.isoformat(),
            **detail,
        }
    if decision_row:
        status_code = "APPROVED" if decision_row.decision == "approved" else "REJECTED"
        status_label = "已审批通过" if decision_row.decision == "approved" else "已审批不通过"
    elif workflow and workflow.status == WorkflowInstance.Status.PENDING:
        status_code = "PENDING" if configured.exists() else "PENDING_APPROVER_CONFIGURATION"
        status_label = "待审批" if configured.exists() else "待配置审批人／待审批"
    elif review.record_status == "SUBMITTED" and review.conclusion:
        status_code = "LEGACY_SYSTEM_SUMMARY"
        status_label = "旧规则系统汇总，非最终人工审批"
    elif review.record_status == "SUBMITTED":
        status_code = "APPROVAL_RELATION_MISSING"
        status_label = "已提交，待补齐审批关系"
    else:
        status_code = "NOT_SUBMITTED"
        status_label = "尚未送审"
    return {
        "applicable": True,
        "workflowInstanceId": workflow.pk if workflow else None,
        "workflowInstanceNo": workflow.instance_no if workflow else "",
        "taskId": task.pk if task else None,
        "taskNo": task.task_no if task else "",
        "statusCode": status_code,
        "statusLabel": status_label,
        "submittedReviewVersion": review.review_version,
        "sourceVersion": review.source_version,
        "configuredApproverCount": configured.count(),
        "configuredApprovers": [
            {
                "userId": row.user_id,
                "username": row.user.username,
                "name": row.user.real_name,
                "scopeCode": row.scope_code,
            }
            for row in configured
        ],
        "requiredRoleCode": config["requiredRoleCode"],
        "requiredPermissionCode": config["permissionCode"],
        "authorization": authorization,
        "canCurrentUserApprove": bool(
            authorization["allowed"] and task and task.status == ApprovalTask.Status.PENDING
        ),
        "finalDecision": final_decision,
        "legacySystemSummary": (
            {
                "code": review.conclusion,
                "label": review.get_conclusion_display(),
                "provenance": "旧提交逻辑按逐项意见汇总生成；没有ApprovalDecision。",
                "isFinalApproval": False,
            }
            if review.conclusion and not decision_row
            else None
        ),
        "opinionCountsAreReferenceOnly": True,
        "noAutomaticFinalDecision": True,
    }


@transaction.atomic
def create_pending_approval(review):
    config = _config(review)
    process = ProcessDefinition.objects.filter(
        definition_code=config["processCode"],
        active=True,
        document_type=config["documentType"],
    ).first()
    if not process:
        raise OrderReviewApprovalError(
            "ORDER_REVIEW_APPROVAL_CONFIG_MISSING",
            f"{config['processName']}流程尚未配置，不能送审。",
            409,
        )
    workflow, _ = WorkflowInstance.objects.get_or_create(
        document_type=config["documentType"],
        document_id=review.pk,
        defaults={
            "instance_no": f"{config['businessDomain']}-REVIEW-APP-{review.pk:08d}-V{review.review_version}",
            "process_definition": process,
            "status": WorkflowInstance.Status.PENDING,
            "current_step": 1,
            "total_steps": 1,
            "version": 1,
        },
    )
    task, _ = ApprovalTask.objects.get_or_create(
        workflow_instance=workflow,
        step_no=1,
        defaults={
            "task_no": f"{config['businessDomain']}-REVIEW-APP-TASK-{review.pk:08d}-V{review.review_version}-01",
            "required_role_code": config["requiredRoleCode"],
            "minimum_approvals": 1,
            "allow_parallel": False,
            "status": ApprovalTask.Status.PENDING,
            "version": 1,
        },
    )
    return workflow, task


@transaction.atomic
def decide_final_approval(*, user, review_type, review_id, data, idempotency_key):
    config = _config(review_type)
    review = OrderCrossFunctionalReview.objects.select_for_update().filter(
        pk=review_id,
        review_type=review_type,
        record_status="SUBMITTED",
    ).first()
    if not review:
        subject = config["processName"].removesuffix("最终审批")
        raise OrderReviewApprovalError("SUBMITTED_REVIEW_NOT_FOUND", f"未找到可审批的已提交{subject}。", 404)
    if int(data.get("expectedReviewVersion") or 0) != review.review_version:
        raise OrderReviewApprovalError("REVIEW_VERSION_MISMATCH", "审批对象版本已变化，请刷新后重试。", 409)
    if str(data.get("expectedSourceVersion") or "") != review.source_version:
        raise OrderReviewApprovalError("SOURCE_VERSION_MISMATCH", "审批依据版本已变化，请刷新后重试。", 409)
    authorization = approval_authorization(user, review)
    if not authorization["allowed"]:
        raise OrderReviewApprovalError("FINAL_APPROVAL_PERMISSION_DENIED", authorization["reason"], 403)
    workflow = _workflow(review, lock=True)
    task = workflow.tasks.select_for_update().filter(step_no=1).first() if workflow else None
    if not task:
        raise OrderReviewApprovalError("APPROVAL_TASK_NOT_FOUND", "该评审没有正式待审批任务。", 409)
    key = str(idempotency_key or "").strip()
    action_id = str(data.get("actionId") or "").strip()
    if not key or not action_id:
        raise OrderReviewApprovalError("APPROVAL_IDEMPOTENCY_REQUIRED", "审批必须提供动作号和幂等标识。")
    previous = ApprovalDecision.objects.filter(action_id=action_id, idempotency_key=key).first()
    if previous:
        return build_approval_facts(user=user, review=review)
    if task.status != ApprovalTask.Status.PENDING or workflow.status != WorkflowInstance.Status.PENDING:
        raise OrderReviewApprovalError("APPROVAL_ALREADY_COMPLETED", "该评审已经完成审批，不能重复覆盖。", 409)
    decision = str(data.get("decision") or "").upper()
    if decision not in {"APPROVE", "REJECT"}:
        raise OrderReviewApprovalError("FINAL_DECISION_REQUIRED", "请选择最终通过或不通过。")
    opinion = str(data.get("approvalOpinion") or "").strip()
    risk = str(data.get("riskHandling") or "").strip()
    if not opinion:
        raise OrderReviewApprovalError("APPROVAL_OPINION_REQUIRED", "请填写最终审批意见。")
    summary = review.item_summary or {}
    conflicts_with_opinions = bool(
        (decision == "APPROVE" and int(summary.get("disagree") or 0) > 0)
        or (decision == "REJECT" and int(summary.get("disagree") or 0) == 0)
    )
    if conflicts_with_opinions and not risk:
        raise OrderReviewApprovalError(
            "RISK_HANDLING_REQUIRED",
            "最终决定与评审意见不一致时，必须填写风险处理说明。",
        )
    sod = SegregationOfDutiesAuthority.objects.filter(document_type=config["documentType"]).first()
    if sod and sod.applicant_cannot_approve and review.reviewer_id == user.pk:
        raise OrderReviewApprovalError("APPROVAL_SOD_DENIED", "现有职责分离规则禁止提交人审批本人提交的评审。", 403)
    comment = json.dumps(
        {"approvalOpinion": opinion, "riskHandling": risk},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(comment) > 500:
        raise OrderReviewApprovalError("APPROVAL_COMMENT_TOO_LONG", "审批意见与风险说明合计过长。")
    now = timezone.now()
    decision_row = ApprovalDecision.objects.create(
        task=task,
        decision_sequence=task.decisions.count() + 1,
        actor=user,
        decision="approved" if decision == "APPROVE" else "rejected",
        comment=comment,
        action_id=action_id,
        idempotency_key=key,
        decision_hash=_hash({
            "taskId": task.pk,
            "reviewId": review.pk,
            "reviewVersion": review.review_version,
            "sourceVersion": review.source_version,
            "actorId": user.pk,
            "decision": decision,
            "comment": comment,
            "at": now.isoformat(),
        }),
    )
    task.status = ApprovalTask.Status.APPROVED if decision == "APPROVE" else ApprovalTask.Status.REJECTED
    task.completed_at = now
    task.version += 1
    task.save(update_fields=["status", "completed_at", "version"])
    workflow.status = WorkflowInstance.Status.APPROVED if decision == "APPROVE" else WorkflowInstance.Status.REJECTED
    workflow.completed_at = now
    workflow.version += 1
    workflow.save(update_fields=["status", "completed_at", "version"])
    OrderReviewItemAudit.objects.create(
        review=review,
        item=None,
        action="FINAL_APPROVAL",
        actor=user,
        before_snapshot={"approvalStatus": "PENDING"},
        after_snapshot={
            "approvalDecisionId": decision_row.pk,
            "workflowInstanceId": workflow.pk,
            "taskId": task.pk,
            "decision": decision,
            "approvalOpinion": opinion,
            "riskHandling": risk,
            "reviewVersion": review.review_version,
            "sourceVersion": review.source_version,
            "approvedAt": now.isoformat(),
        },
        audit_hash=_hash({
            "reviewId": review.pk,
            "approvalDecisionId": decision_row.pk,
            "actorId": user.pk,
            "at": now.isoformat(),
        }),
    )
    if review_type == "PDE_PRODUCTION_FEASIBILITY" and decision == "APPROVE":
        from .pde_engineering_preparation_admission import (
            PDEEngineeringPreparationAdmissionError,
            create_pde_engineering_preparation_authorization,
        )
        try:
            create_pde_engineering_preparation_authorization(
                pde_review=review,
                workflow_instance=workflow,
                approval_decision=decision_row,
                user=user,
            )
        except PDEEngineeringPreparationAdmissionError as exc:
            raise OrderReviewApprovalError(
                exc.code, exc.message, exc.http_status,
            ) from exc
    return build_approval_facts(user=user, review=review)


@transaction.atomic
def reconcile_legacy_submitted_review(
    *, review, actor, reason, expected_review_type="CRM_ORDER_REVIEW",
    expected_review_version=None, expected_source_order_no=None,
    expected_source_version=None, authorization_audit_id=None,
):
    review = OrderCrossFunctionalReview.objects.select_for_update().get(pk=review.pk)
    if review.review_type != expected_review_type or review.record_status != "SUBMITTED":
        raise OrderReviewApprovalError("LEGACY_REVIEW_NOT_ELIGIBLE", "目标不是精确指定的已提交评审。", 409)
    expected = {
        "reviewVersion": expected_review_version,
        "sourceOrderNo": expected_source_order_no,
        "sourceVersion": expected_source_version,
    }
    actual = {
        "reviewVersion": review.review_version,
        "sourceOrderNo": review.source_order_no,
        "sourceVersion": review.source_version,
    }
    if any(value in (None, "") for value in expected.values()) or actual != expected:
        raise OrderReviewApprovalError(
            "RECONCILIATION_TARGET_MISMATCH",
            "评审版本、来源订单或来源版本与精确授权不一致，停止接通。",
            409,
        )
    latest = OrderCrossFunctionalReview.objects.filter(
        company_id=review.company_id,
        review_type=review.review_type,
        source_order_no=review.source_order_no,
        record_status="SUBMITTED",
    ).order_by("-review_version", "-id").first()
    if not latest or latest.pk != review.pk:
        raise OrderReviewApprovalError(
            "RECONCILIATION_NOT_CURRENT_SUBMISSION",
            "目标不是该来源当前最新的已提交版本，历史版本不得补建待办。",
            409,
        )
    document_type = _config(review)["documentType"]
    if ApprovalDecision.objects.filter(task__workflow_instance__document_type=document_type, task__workflow_instance__document_id=review.pk).exists():
        raise OrderReviewApprovalError("REAL_APPROVAL_EXISTS", "目标已存在真实审批决定，禁止按旧汇总记录处理。", 409)
    if not all(
        item.signature_status == "SIGNED" and item.signature_content_hash
        for item in review.items.filter(is_removed=False)
    ):
        raise OrderReviewApprovalError("SIGNATURE_BASELINE_INCOMPLETE", "原始意见签认不完整，停止历史关系补齐。", 409)
    if review.review_type == "CRM_ORDER_REVIEW":
        from sales.models import SalesOrder
        if SalesOrder.objects.filter(order_no=review.source_order_no).exists():
            raise OrderReviewApprovalError("DOWNSTREAM_SALES_ORDER_EXISTS", "已发现正式销售订单引用，停止历史状态转换。", 409)
    workflow, task = create_pending_approval(review)
    if workflow.status != WorkflowInstance.Status.PENDING or task.status != ApprovalTask.Status.PENDING:
        raise OrderReviewApprovalError("APPROVAL_RELATION_NOT_PENDING", "现有审批关系不是待审批状态，停止覆盖。", 409)
    audit_hash = _hash({
        "action": "APPROVAL_RELATION_CONTINUED",
        "reviewId": review.pk,
        "reviewVersion": review.review_version,
        "sourceVersion": review.source_version,
        "workflowInstanceId": workflow.pk,
        "taskId": task.pk,
        "authorizationAuditId": authorization_audit_id,
    })
    audit, audit_created = OrderReviewItemAudit.objects.get_or_create(
        audit_hash=audit_hash,
        defaults={
            "review": review,
            "item": None,
            "action": "APPROVAL_RELATION_CONTINUED",
            "actor": actor,
            "before_snapshot": {
                "recordStatus": review.record_status,
                "legacyConclusion": review.conclusion,
                "legacySummary": review.item_summary,
                "approvalDecisionCount": 0,
            },
            "after_snapshot": {
                "recordStatus": review.record_status,
                "approvalStatus": "PENDING",
                "workflowInstanceId": workflow.pk,
                "taskId": task.pk,
                "legacyConclusionPreserved": True,
                "legacyConclusionIsFinalApproval": False,
                "executionMode": "AUTHORIZED_TECHNICAL_CONTINUATION",
                "authorizationAuditId": authorization_audit_id,
                "reason": reason,
            },
        },
    )
    return {
        "mode": "CREATED_PENDING_RELATION" if audit_created else "IDEMPOTENT_REUSE",
        "workflowInstanceId": workflow.pk,
        "taskId": task.pk,
        "auditId": audit.pk,
        "legacyConclusion": review.conclusion,
        "legacyConclusionIsFinalApproval": False,
        "userAuthorityWrites": 0,
        "approvalDecisionWrites": 0,
    }
