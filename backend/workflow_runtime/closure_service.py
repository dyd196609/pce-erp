"""Explicit applicant withdrawal, with no invented approval decision.

The business owner validates its action/position/scope and holds its stable
document lock before calling this service. This service closes the shared
pending work and records a separate, verifiable closure fact in that same
transaction. A closure is neither approval nor rejection.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re

from django.db import connection
from django.utils import timezone
from system.models import OrganizationOperatingAuditRecord
from .models import ApprovalTask, BusinessStateTransition, WorkflowClosure, WorkflowInstance
from .state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)

CONTRACT = "PCE-SHARED-APPLICANT-WORKFLOW-CLOSURE-V1"
KIND = "applicant_withdrawn_superseded"


class WorkflowClosureError(ValueError):
    pass


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str).encode()).hexdigest()


def _fail(message):
    raise WorkflowClosureError(message)


def _audit(*, obj, name, actor, action, reason, authorization, state, before):
    row = OrganizationOperatingAuditRecord.objects.create(action_code=action,
        actor=actor, organization_id=actor.company_id, target_type=name,
        target_id=obj.pk, target_label=f"{name}:{obj.pk}", reason=reason,
        before_snapshot={"authorization":deepcopy(authorization), "state":before},
        after_snapshot={"authorization":deepcopy(authorization), "state":state})
    return f"OrganizationOperatingAuditRecord:{row.pk}"


def _original_request(workflow,approval_task,applicant_id,company_id,reference):
    match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',reference or '')
    row=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
    after=row.after_snapshot if row and isinstance(row.after_snapshot,dict) else {}
    state=after.get('state') if isinstance(after.get('state'),dict) else {}
    original=BusinessStateTransition.objects.filter(object_type='WorkflowInstance',object_id=workflow.pk,version=1).first()
    if (not row or row.actor_id!=applicant_id or row.organization_id!=company_id
            or row.target_type!=workflow.document_type or row.target_id!=workflow.document_id
            or state.get('workflowInstanceId')!=workflow.pk or state.get('approvalTaskId')!=approval_task.pk
            or state.get('status') not in ('pending','pending_review')
            or not original or original.source_state!='' or original.target_state!='pending'
            or original.operator_id!=applicant_id or original.action_code!=row.action_code
            or original.workflow_instance_id not in (None,workflow.pk)):
        _fail('原申请审计、真实申请人及准确共享对象未完整核实，不能关闭。')
    for name,obj in (('WorkflowInstance',workflow),('ApprovalTask',approval_task)):
        event=BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk,version=1).first()
        ref=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '') if event else None
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(ref[1])).first() if ref else None
        before=audit.before_snapshot if audit and isinstance(audit.before_snapshot,dict) else {}
        after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
        initial=after.get('state') if isinstance(after.get('state'),dict) else {}
        if (not event or (event.source_state,event.target_state)!=('','pending')
                or event.operator_id!=applicant_id or event.action_code!=row.action_code
                or event.workflow_instance_id not in (None,workflow.pk)
                or not audit or audit.organization_id!=company_id or audit.actor_id!=applicant_id
                or audit.target_type!=name or audit.target_id!=obj.pk or audit.action_code!=event.action_code
                or audit.reason!=event.reason or before.get('state')!={'status':''} or initial.get('status')!='pending'):
            _fail('原共享初始化缺少真实对象、申请人、公司、动作及审计，不能伪造关闭来源。')


def close_pending_workflow(*, workflow, approval_task, actor, applicant_id,
        expected_workflow_version, expected_approval_version, action_code,
        reason, authorization, source_object_type, source_object_id,
        replacement_object_type, replacement_object_id, original_request_reference,
        request_hash, request_key_hash):
    if not connection.in_atomic_block:
        _fail("共享撤回关闭必须处于业务所有者的原子事务中。")
    if actor.pk != applicant_id or not actor.is_active or actor.is_superuser or not actor.company_id:
        _fail("仅原申请人本人可以撤回尚未审核的申请。")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not 2 <= len(reason) <= 240 or not action_code:
        _fail("请明确本次撤回及替代原因。")
    if (not isinstance(authorization, dict) or authorization.get("allowed") is not True
            or not isinstance(authorization.get("permissionCodes"),list)
            or not isinstance(authorization.get("roleCodes"),list)
            or action_code not in authorization.get("permissionCodes", [])
            or not authorization.get("roleCodes")):
        _fail("撤回关闭缺少本动作真实权限及范围证据。")
    if any(type(value) is not int or value <= 0 for value in
            (source_object_id, replacement_object_id, expected_workflow_version, expected_approval_version)):
        _fail("共享关闭对象及原版本无效。")
    if (not source_object_type or not replacement_object_type
            or not re.fullmatch(r"OrganizationOperatingAuditRecord:[1-9][0-9]*", original_request_reference or "")
            or any(not isinstance(h, str) or not re.fullmatch("[a-f0-9]{64}", h) for h in (request_hash, request_key_hash))):
        _fail("共享关闭缺少准确原申请、替代对象及原请求绑定。")
    workflow = WorkflowInstance.objects.select_for_update().get(pk=workflow.pk)
    approval_task = ApprovalTask.objects.select_for_update().get(pk=approval_task.pk)
    if (workflow.status != WorkflowInstance.Status.PENDING
            or approval_task.status != ApprovalTask.Status.PENDING
            or workflow.version != expected_workflow_version
            or approval_task.version != expected_approval_version
            or approval_task.workflow_instance_id != workflow.pk
            or workflow.tasks.count() != 1 or approval_task.decisions.exists()
            or WorkflowClosure.objects.filter(workflow_instance=workflow).exists()):
        _fail("仅准确版本、没有审核决策的共享待审申请可以撤回关闭。")
    first = BusinessStateTransition.objects.filter(object_type="WorkflowInstance", object_id=workflow.pk).order_by("version", "pk").first()
    if not first or first.source_state != "" or first.target_state != "pending" or first.operator_id != applicant_id:
        _fail("共享原申请人与申请初始化历史未核实。")
    _original_request(workflow,approval_task,applicant_id,actor.company_id,original_request_reference)
    snapshot = {"contractVersion":CONTRACT, "kind":KIND,
        "companyId":actor.company_id, "actorId":actor.pk, "applicantId":applicant_id,
        "workflowInstanceId":workflow.pk, "approvalTaskId":approval_task.pk,
        "sourceObjectType":source_object_type, "sourceObjectId":source_object_id,
        "replacementObjectType":replacement_object_type, "replacementObjectId":replacement_object_id,
        "originalRequestReference":original_request_reference, "actionCode":action_code,
        "reason":reason, "requestHash":request_hash, "requestKeyHash":request_key_hash}
    closure = create_business_object_with_initial_state(model=WorkflowClosure, initial_state="closed",
        workflow_instance=workflow, approval_task=approval_task, kind=KIND, actor=actor,
        company_id=actor.company_id, reason=reason, source_object_type=source_object_type,
        source_object_id=source_object_id, replacement_object_type=replacement_object_type,
        replacement_object_id=replacement_object_id, original_request_reference=original_request_reference,
        action_code=action_code, request_hash=request_hash, request_key_hash=request_key_hash,
        snapshot=deepcopy(snapshot), snapshot_hash=_hash(snapshot), version=1)
    state = {"contractVersion":CONTRACT, "status":"closed", "closureId":closure.pk,
        "closureHash":closure.snapshot_hash, **snapshot}
    reference = _audit(obj=closure, name="WorkflowClosure", actor=actor, action=action_code,
        reason=reason, authorization=authorization, before={"status":""}, state=state)
    closure.audit_reference=reference; closure.save(update_fields=["audit_reference"])
    record_projected_business_transition(object_type="WorkflowClosure", object_id=closure.pk,
        source_state="", target_state="closed", action_code=action_code, operator=actor,
        reason=reason, audit_reference=reference, workflow_instance=workflow, allowed_transitions={("", "closed")})
    for obj, name in ((approval_task, "ApprovalTask"), (workflow, "WorkflowInstance")):
        reference = _audit(obj=obj, name=name, actor=actor, action=action_code, reason=reason,
            authorization=authorization, before={"status":"pending"}, state=state)
        obj.completed_at=timezone.now(); obj.save(update_fields=["completed_at"])
        transition_business_object(business_object=obj, object_type=name, source_state="pending",
            target_state="closed", action_code=action_code, operator=actor, reason=reason,
            audit_reference=reference, workflow_instance=workflow,
            allowed_transitions={("pending", "closed")}, updated_at_field=None)
    return closure


def closure_facts(closure):
    """All readers use this fact, never label closed work as a rejection."""
    closure = WorkflowClosure.objects.select_related("workflow_instance", "approval_task", "actor").defer("actor__password").get(pk=closure.pk)
    snapshot=closure.snapshot
    expected={"contractVersion":CONTRACT,"kind":KIND,"companyId":closure.company_id,
        "actorId":closure.actor_id,"applicantId":closure.actor_id,
        "workflowInstanceId":closure.workflow_instance_id,"approvalTaskId":closure.approval_task_id,
        "sourceObjectType":closure.source_object_type,"sourceObjectId":closure.source_object_id,
        "replacementObjectType":closure.replacement_object_type,"replacementObjectId":closure.replacement_object_id,
        "originalRequestReference":closure.original_request_reference,"actionCode":closure.action_code,
        "reason":closure.reason,"requestHash":closure.request_hash,"requestKeyHash":closure.request_key_hash}
    if (snapshot != expected or _hash(snapshot) != closure.snapshot_hash or closure.status != "closed"
            or closure.version != 1 or closure.kind != KIND or closure.actor.company_id != closure.company_id
            or closure.workflow_instance.status != "closed" or closure.approval_task.status != "closed"
            or closure.approval_task.workflow_instance_id != closure.workflow_instance_id
            or closure.workflow_instance.tasks.count()!=1
            or not closure.workflow_instance.completed_at or not closure.approval_task.completed_at
            or closure.approval_task.decisions.exists()):
        _fail("共享撤回关闭事实、原对象或审核决策存在冲突。")
    _original_request(closure.workflow_instance,closure.approval_task,closure.actor_id,
        closure.company_id,closure.original_request_reference)
    result=[]
    for name, obj, initial in (("WorkflowClosure",closure,True),
            ("WorkflowInstance",closure.workflow_instance,False), ("ApprovalTask",closure.approval_task,False)):
        rows=list(BusinessStateTransition.objects.filter(object_type=name,object_id=obj.pk).order_by("version","pk"))
        if len(rows) != (1 if initial else 2) or obj.version != len(rows):
            _fail("共享撤回关闭的真实状态历史或版本不完整。")
        if not initial and (rows[0].source_state != "" or rows[0].target_state != "pending"
                or rows[0].operator_id != closure.actor_id or rows[0].version!=1
                or rows[0].workflow_instance_id not in (None,closure.workflow_instance_id)):
            _fail("共享关闭不属于原申请人创建的待审对象。")
        event=rows[-1]
        match=re.fullmatch(r"OrganizationOperatingAuditRecord:([1-9][0-9]*)",event.audit_reference or "")
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        state={"status":"closed","closureId":closure.pk,"closureHash":closure.snapshot_hash,**snapshot}
        after=audit.after_snapshot if audit and isinstance(audit.after_snapshot,dict) else {}
        before=audit.before_snapshot if audit and isinstance(audit.before_snapshot,dict) else {}
        authorization=after.get('authorization') if isinstance(after.get('authorization'),dict) else {}
        if (event.source_state != ("" if initial else "pending") or event.target_state != "closed"
                or event.version!=(1 if initial else 2)
                or event.action_code != closure.action_code or event.operator_id != closure.actor_id
                or event.reason != closure.reason or event.workflow_instance_id != closure.workflow_instance_id
                or not audit or audit.organization_id != closure.company_id or audit.actor_id != closure.actor_id
                or audit.target_type != name or audit.target_id != obj.pk or audit.action_code != event.action_code
                or audit.reason != event.reason or after.get("state") != state
                or before.get("state") != {"status":"" if initial else "pending"}
                or not isinstance(authorization.get('permissionCodes'),list)
                or not isinstance(authorization.get('roleCodes'),list) or not authorization.get('roleCodes')
                or authorization.get("allowed") is not True
                or closure.action_code not in authorization.get("permissionCodes",[])
                or before.get('authorization')!=authorization
                or initial and closure.audit_reference != event.audit_reference):
            _fail("共享关闭缺少真实同对象、同动作和同申请人的审计证明。")
        result.append({"objectType":name,"objectId":obj.pk,"statusTransitionCount":len(rows),
            "statusTransitionHistory":[{"id":row.pk,"version":row.version,"sourceState":row.source_state,
                "targetState":row.target_state,"actionCode":row.action_code,"operatorId":row.operator_id,
                "reason":row.reason,"auditReference":row.audit_reference} for row in rows]})
    return {"contractVersion":CONTRACT,"closureId":closure.pk,"kind":KIND,
        "statusLabel":"因生产事实变化由申请人撤回待审","closedById":closure.actor_id,
        "closedByLabel":closure.actor.real_name or closure.actor.username,
        "closedAt":closure.created_at.isoformat(),"reason":closure.reason,
        "sourceObjectType":closure.source_object_type,"sourceObjectId":closure.source_object_id,
        "replacementObjectType":closure.replacement_object_type,"replacementObjectId":closure.replacement_object_id,
        "originalRequestReference":closure.original_request_reference,"actionCode":closure.action_code,"requestHash":closure.request_hash,
        "requestKeyHash":closure.request_key_hash,"proofHash":closure.snapshot_hash,
        "auditReference":closure.audit_reference,"reviewerId":None,"approvalDecisionId":None,
        "reviewed":False,"rejected":False,"pendingCount":0,"approvedCount":0,"rejectedCount":0,
        "closedCount":1,"stateMachineConsistent":True,"sharedHistory":result,
        "statusTransitionCount":result[0]["statusTransitionCount"],
        "statusTransitionHistory":result[0]["statusTransitionHistory"]}


def pending_approval_tasks(queryset=None):
    """A reusable pending-work predicate: closed tasks cannot remain work."""
    return (queryset if queryset is not None else ApprovalTask.objects.all()).filter(
        status="pending", workflow_instance__status="pending")
