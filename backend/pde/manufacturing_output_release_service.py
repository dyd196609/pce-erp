"""Dedicated manual release of a formally generated order manufacturing draft.

Reuses engineering review/release evidence, organization permissions and shared
state transitions. Never rewrites the order/OEI or creates downstream objects.
The legacy lifecycle of other manufacturing outputs remains unchanged.
"""
import time
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord, PositionResponsibility
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import transition_business_object
from .models import ProductManufacturingOutput, StandardCapacity
from .manufacturing_output_generation_service import (
    OBJECT, PERMISSION, ManufacturingOutputError, _hash, eligible_executors,
    generation_readback, output_snapshot, resolve_sources, scoped_item, _versioned_sources,
)

CONTRACT = "PCE-ORDER-MANUFACTURING-OUTPUT-RELEASE-V1.0"
ACTION = "pde.manufacturing_output.release"
RELEASE_RESPONSIBILITY = "RESP_PROD_PLAN_001"
ACTION_CONTRACT = {"actionCode": ACTION, "displayName": "正式发布至制造", "moduleCode": "PDE",
    "requiredPermission": PERMISSION, "requiredResponsibility": RELEASE_RESPONSIBILITY,
    "roleAuthority": "system.UserRoleScopeAssignment", "organizationScope": "ORGANIZATION",
    "serverValidator": "pde.manufacturing_output_release_service.release_manufacturing_output",
    "sourceState": "draft", "targetState": "released_to_manufacturing",
    "engineeringReviewAuthority": "EngineeringDocumentVersion formal review and released source set",
    "downstreamCreationAllowed": False}


def eligible_publishers(company_id):
    # Distinct release duty, not inheritance of generation or PMC authority.
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    actors = []
    for actor in eligible_executors(company_id):
        duty = PositionResponsibility.objects.filter(position_id=actor["positionId"], active=True,
            is_primary=True, responsibility__code=RELEASE_RESPONSIBILITY,
            responsibility__is_active=True, responsibility__status="ACTIVE"
        ).filter(Q(responsibility__effective_from__isnull=True) | Q(responsibility__effective_from__lte=today)
        ).filter(Q(responsibility__effective_to__isnull=True) | Q(responsibility__effective_to__gte=today)).first()
        if duty:
            actors.append({**actor, "releasePositionResponsibilityId": duty.pk,
                "releaseResponsibilityId": duty.responsibility_id, "releaseResponsibilityCode": duty.responsibility.code})
    return actors


def require_publisher(user, company_id):
    actors = eligible_publishers(company_id)
    if user.is_superuser or not user.is_active or user.company_id != company_id:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_PUBLISHER_DENIED", "管理员或无效账号不能绕过正式制造发布责任链。", 403)
    if len(actors) != 1:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_RESPONSIBILITY_REQUIRED", "正式制造发布责任人未能唯一解析。", 403)
    if actors[0]["userId"] != user.pk:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_PUBLISHER_DENIED", "当前登录人员不是正式制造发布责任人。", 403)
    return actors[0]


def release_readback(output, *, read_cache=None):
    from .operation_requirement_service import _ReadOnlyProofCache, _requirement_read_cache, _read_guarded_raw
    cache = None
    if isinstance(read_cache, _ReadOnlyProofCache):
        company_id = (output.order_engineering_instance.company_id if output.order_engineering_instance_id
            else output.product.company_id if output.product_id else None)
        cache = _requirement_read_cache(read_cache, company_id)

    def raw(key, loader):
        return _read_guarded_raw(cache, ('manufacturing_release_readback', output.pk, *key), loader)

    transitions = raw(('transitions', OBJECT, ACTION, 'draft', 'released_to_manufacturing', 2), lambda:
        list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=output.pk,
        action_code=ACTION, source_state="draft", target_state="released_to_manufacturing")[:2]))
    transition = transitions[0] if len(transitions) == 1 else None
    request = raw(('request', ACTION, OBJECT, str(output.pk), 'COMMITTED'), lambda:
        MasterDataWriteRequest.objects.filter(action_code=ACTION, entity_type=OBJECT,
        target_entity_id=str(output.pk), status="COMMITTED").first())
    audit = None
    if transition:
        audit_id = transition.audit_reference.rsplit(":",1)[-1]
        audit = raw(('audit', audit_id, OBJECT, output.pk, ACTION, transition.operator_id), lambda:
            OrganizationOperatingAuditRecord.objects.filter(pk=audit_id,
            target_type=OBJECT, target_id=output.pk, action_code=ACTION, actor_id=transition.operator_id).first())
    complete = bool(transition and request and audit and output.release_status == "released_to_manufacturing"
        and request.result.get("businessStateTransitionId") == transition.pk
        and request.result.get("auditId") == audit.pk and request.result.get("row",{}).get("id") == output.pk
        and request.audit_metadata.get("operatorId") == transition.operator_id
        and audit.after_snapshot.get("sourceFingerprint") and audit.after_snapshot.get("sourceSnapshot"))
    return {"completed":complete, "businessStateTransitionId":transition.pk if transition else None,
        "writeRequestId":request.pk if request else None, "auditId":audit.pk if audit else None,
        "actorId":transition.operator_id if transition else None,
        "actorUsername":(raw(('actor_username', transition.pk), lambda:
            BusinessStateTransition.objects.filter(pk=transition.pk).values_list(
            "operator__username", flat=True).first()) or "") if transition else "",
        "releasedAt":transition.timestamp.isoformat() if transition else ""}


def _validated_sources(output, user, lock=False):
    from .bom_usage_contract import is_test_source
    if is_test_source(output):
        raise ManufacturingOutputError('TEST_BUSINESS_PRODUCTION_DENIED','测试BOM禁止制造发布。',403)
    if not output.order_engineering_instance_id or output.order_engineering_instance.company_id != user.company_id:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_SOURCE_IDENTITY_CONFLICT", "制造输出不属于当前公司订单工程实例。", 403)
    item = scoped_item(user.company_id, lock=lock,
        item_id=output.order_engineering_instance.sales_order_item_id)
    instance, doc, fields, fingerprint = resolve_sources(item, lock=lock,
        document_version_id=output.engineering_document_version_id)
    fields, fingerprint = _versioned_sources(output, fields, fingerprint)
    if output.order_engineering_instance_id != instance.pk or any(getattr(output,key) != value for key,value in fields.items()):
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_SOURCE_IDENTITY_CONFLICT", "制造输出与当前准确工程来源组合不一致。")
    proof = generation_readback(output)
    snapshot = output_snapshot(output)
    if not proof["completed"] or not snapshot["stateMachineConsistent"]:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_GENERATION_FACT_REQUIRED", "制造输出生成请求、初始化状态转换和审计事实不完整。")
    audit = OrganizationOperatingAuditRecord.objects.get(pk=proof["auditId"])
    if audit.after_snapshot.get("sourceFingerprint") != fingerprint:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_CONTENT_CHANGED", "当前来源内容与正式生成时的冻结指纹不一致，禁止发布。")
    try:
        output.full_clean()
    except ValidationError as exc:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_RELATION_INVALID", "制造输出精确来源或字段合同未通过。", details=exc.message_dict) from exc
    return fields, fingerprint, doc


def release_preflight(output, user):
    result = {"contractVersion":CONTRACT, "actionContract":ACTION_CONTRACT,
        "outputId":output.pk, "statusCode":output.release_status, "statusLabel":output.get_release_status_display(),
        "currentUser":{"id":user.pk,"username":user.username,"realName":user.real_name},
        "eligiblePublishers":eligible_publishers(user.company_id), "releaseAllowed":False,
        "sourceReady":False, "statusLabelForReadiness":"制造发布准入阻断", "gates":[],
        "releaseCompleted":False, "completionMessage":"",
        "manufacturingReleaseExecuted":False, "businessWriteCount":0}
    def gate(code, label, passed, evidence):
        result["gates"].append({"code":code,"label":label,"passed":bool(passed),
            "statusLabel":"通过" if passed else "阻断","evidence":evidence})
    try:
        fields, fingerprint, doc = _validated_sources(output, user)
        result.update(sourceReady=True, sourceFingerprint=fingerprint, sourceSnapshot=fields,
            releaseReadback=release_readback(output))
        gate("MANUFACTURING_RELEASE_SOURCE_VALID", "来源、上游评审发布及冻结内容", True, "正式来源链与生成冻结指纹一致。")
        steps = doc.related_routing.steps.all()
        result["resourceObservations"] = {"releaseGate":False, "routingStepCount":steps.count(),
            "missingStandardHoursCount":steps.filter(standard_hours__isnull=True).count(),
            "missingWorkCenterCount":steps.filter(work_center_id__isnull=True).count(),
            "standardCapacityCount":StandardCapacity.objects.filter(company_id=user.company_id).count(),
            "standardCapacityAssessment":"本制造发布合同不以StandardCapacity作为门禁；资源齐套留待独立计划准入。"}
        if output.release_status == "released_to_manufacturing":
            proof = result["releaseReadback"]
            if not proof["completed"]:
                raise ManufacturingOutputError("MANUFACTURING_RELEASE_FACT_INCOMPLETE",
                    "制造输出显示已发布，但原生发布请求、状态转换或审计证明不完整，不能确认发布完成。")
            published = OrganizationOperatingAuditRecord.objects.filter(pk=proof["auditId"],
                organization_id=user.company_id, action_code=ACTION,
                target_type=OBJECT, target_id=output.pk).values("after_snapshot").first()
            frozen = published["after_snapshot"] if published else {}
            if frozen.get("sourceSnapshot") != fields or frozen.get("sourceFingerprint") != fingerprint:
                raise ManufacturingOutputError("MANUFACTURING_RELEASE_CONTENT_CHANGED",
                    "正式发布审计的冻结来源与当前准确来源不一致，不能确认发布完成。")
            gate("MANUFACTURING_RELEASE_COMPLETED", "正式制造发布已完成", True,
                f"原生审计 {proof['auditId']}；发布人 {proof['actorUsername']}；发布时间 {proof['releasedAt']}。")
            result.update(releaseCompleted=True, manufacturingReleaseExecuted=True,
                statusLabelForReadiness="已完成正式制造发布",
                completionMessage="正式制造发布已完成，无需重复办理；未自动创建生产计划、MRP或工单。")
            return result
        if output.release_status != "draft":
            raise ManufacturingOutputError("MANUFACTURING_RELEASE_STATE_DENIED", "当前制造输出不是待发布草稿，不得重复发布。")
        if BusinessStateTransition.objects.filter(object_type=OBJECT,object_id=output.pk,target_state="released_to_manufacturing").exists():
            raise ManufacturingOutputError("MANUFACTURING_RELEASE_DUPLICATE_FACT", "已存在制造发布事实，禁止重复执行。")
        gate("MANUFACTURING_RELEASE_DRAFT_AND_NO_RELEASE", "草稿身份且尚未发布", True, f"ProductManufacturingOutput {output.pk}，无发布转换。")
        actor = require_publisher(user, user.company_id)
        gate("MANUFACTURING_RELEASE_PUBLISHER_VALID", "当前人员发布权限、Scope及正式职责", True, f"{actor['username']} / ORGANIZATION / {RELEASE_RESPONSIBILITY}")
        result.update(releaseAllowed=True, currentPublisher=actor, statusLabelForReadiness="制造发布准入通过")
    except (ManufacturingOutputError, ValidationError) as exc:
        code = getattr(exc,"code","MANUFACTURING_RELEASE_RELATION_INVALID")
        gate(code,"当前首个真实阻断",False,str(exc))
        result.update(firstBlockerCode=code, firstBlockerMessage=str(exc))
    return result


def _release_atomic(user, output_id, payload, key):
    with transaction.atomic():
        output = ProductManufacturingOutput.objects.select_for_update().filter(pk=output_id).first()
        if not output:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_NOT_FOUND", "制造输出不存在。",404)
        actor = require_publisher(user,user.company_id)
        fields, fingerprint, doc = _validated_sources(output,user,lock=True)
        if payload.get("sourceFingerprint") != fingerprint:
            raise ManufacturingOutputError("MANUFACTURING_RELEASE_CANDIDATE_STALE", "发布准入来源已变化，请刷新后重新确认。")
        request_hash = _hash({"outputId":output_id,"actorId":user.pk,"payload":payload})
        ledger = MasterDataWriteRequest.objects.select_for_update().filter(organization_id=user.company_id,
            action_code=ACTION,idempotency_key=key).first()
        if ledger and ledger.request_hash != request_hash:
            raise ManufacturingOutputError("IDEMPOTENCY_PAYLOAD_CONFLICT", "同一幂等键不得更换对象、操作人或内容。")
        if output.release_status == "released_to_manufacturing":
            proof = release_readback(output)
            if not proof["completed"]:
                raise ManufacturingOutputError("MANUFACTURING_RELEASE_FACT_INCOMPLETE", "制造发布状态缺少完整提交事实。")
            committed = MasterDataWriteRequest.objects.get(pk=proof["writeRequestId"])
            return {**committed.result,"row":output_snapshot(output),"idempotentReplay":True}
        preflight = release_preflight(output,user)
        if not preflight["releaseAllowed"]:
            raise ManufacturingOutputError(preflight["firstBlockerCode"],preflight["firstBlockerMessage"])
        before = output_snapshot(output)
        generation_request = MasterDataWriteRequest.objects.get(pk=generation_readback(output)["writeRequestId"])
        ledger = ledger or MasterDataWriteRequest.objects.create(organization_id=user.company_id,
            action_code=ACTION,entity_type=OBJECT,idempotency_key=key,request_hash=request_hash,
            source_identity_id=generation_request.source_identity_id,
            audit_metadata={"operatorId":user.pk,"releaseChain":actor})
        audit = OrganizationOperatingAuditRecord.objects.create(action_code=ACTION,actor=user,
            organization_id=user.company_id,target_type=OBJECT,target_id=output.pk,
            target_label=f"{before['orderNo']} / 行{before['orderLineNo']} / 制造输出{output.pk}",
            reason=payload["reason"],before_snapshot=before,
            after_snapshot={"release_status":"released_to_manufacturing","sourceSnapshot":fields,
                "sourceFingerprint":fingerprint,"releaseChain":actor,"writeRequestId":ledger.pk})
        transition = transition_business_object(business_object=output,object_type=OBJECT,
            source_state="draft",target_state="released_to_manufacturing",action_code=ACTION,
            operator=user,reason=payload["reason"],audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={("draft","released_to_manufacturing")},status_field="release_status",version_field=None)
        result = {"contractVersion":CONTRACT,"row":output_snapshot(output),"auditId":audit.pk,
            "writeRequestId":ledger.pk,"businessStateTransitionId":transition.pk,"idempotentReplay":False}
        ledger.target_entity_id,ledger.status,ledger.result = str(output.pk),"COMMITTED",result
        ledger.save(update_fields=["target_entity_id","status","result","updated_at"])
        result["releaseReadback"] = release_readback(output)
        ledger.result = result
        ledger.save(update_fields=["result","updated_at"])
        return result


def release_manufacturing_output(*, user, output_id, payload, idempotency_key):
    if set(payload) - {"action","sourceFingerprint","reason"} or payload.get("action") != ACTION:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_ACTION_REQUIRED", "请求必须使用独立制造发布动作，不得指定状态或来源外键。",400)
    payload = dict(payload)
    payload["reason"] = str(payload.get("reason") or "").strip()
    key = str(idempotency_key or "").strip()
    if not payload["reason"] or len(payload["reason"]) > 300 or not key or len(key) > 150:
        raise ManufacturingOutputError("MANUFACTURING_RELEASE_INPUT_REQUIRED", "必须填写发布理由及有效幂等键。",400)
    for attempt in range(5):
        try:
            return _release_atomic(user,output_id,payload,key)
        except (OperationalError,IntegrityError) as exc:
            if (not isinstance(exc,IntegrityError) and "locked" not in str(exc).lower()) or attempt == 4:
                raise ManufacturingOutputError("MANUFACTURING_RELEASE_CONCURRENT_CONFLICT", "发布并发请求未完成，请刷新回读正式结果，勿重复操作。") from exc
            time.sleep(0.03 * (attempt + 1))
