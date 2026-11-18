"""Atomic, authorized successor-version and draft-step applicability writes."""
from __future__ import annotations

from hashlib import sha256
import json

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.authorization import AuthorizationService

from .models import RoutingStep, RoutingVersion
from .production_foundation_service import _actor_chain, _audit, _snapshot
from .routing_step_applicability_service import (
    CONTRACT_VERSION,
    normalized_contract,
    successor_contract,
    explicit_contract,
    legacy_exact_contract,
)


ROUTING_PERMISSION = "production.master_data.routing.maintain"
SUCCESSOR_ACTION = "pde.routing_version.create_successor"
APPLICABILITY_ACTION = "pde.routing_step.maintain_applicability"
SUCCESSOR_SOURCE_STATUSES = {"reviewed", "released", "obsolete"}


class RoutingVersionChangeError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _canonical_hash(value):
    return sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def _organization_id(version):
    if version.routing_id:
        return version.routing.company_id
    return version.product.company_id


def _authorize(user, version):
    organization_id = _organization_id(version)
    if user.company_id != organization_id:
        raise RoutingVersionChangeError("ORGANIZATION_SCOPE_DENIED", "目标路线版本不属于当前登录组织。")
    decision = AuthorizationService.decide(
        user=user,
        action_code=ROUTING_PERMISSION,
        organization_id=organization_id,
        business_object={"organizationId": organization_id},
    )
    if not decision.get("allowed"):
        raise RoutingVersionChangeError(
            decision.get("decisionCode") or "PERMISSION_DENIED",
            decision.get("reason") or "当前账号没有工艺路线正式维护权限。",
            {"authorization": decision},
        )
    try:
        from .master_data_actor import maintenance_actor
        execution_chain = maintenance_actor(user,action_code=ROUTING_PERMISSION,organization_id=organization_id)
    except Exception as exc:
        raise RoutingVersionChangeError(
            "FORMAL_EXECUTION_CHAIN_REQUIRED",
            "工艺路线维护必须由具备在职员工、启用岗位和有效职责链的正式业务账号执行。",
        ) from exc
    return organization_id, decision, execution_chain


def _identity(*, organization_id, object_type, external_id, target_type, fingerprint_payload):
    fingerprint = _canonical_hash(fingerprint_payload)
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=organization_id,
        source_system="PCE_SYSTEM",
        source_type="ROUTING_VERSION_CONTROLLED_CHANGE",
        source_object_type=object_type,
        external_id=external_id,
        defaults={
            "target_entity_type": target_type,
            "mapping_status": ExternalIdentity.MappingStatus.CREATE,
            "source_fingerprint": fingerprint,
            "audit_metadata": {
                "contractVersion": CONTRACT_VERSION,
                "fingerprintPayload": fingerprint_payload,
            },
        },
    )
    if identity.target_entity_type != target_type:
        raise RoutingVersionChangeError("SOURCE_IDENTITY_TARGET_CONFLICT", "正式来源身份的目标类型冲突。")
    return identity, fingerprint


def _ledger(*, organization_id, action_code, entity_type, idempotency_key, request_hash, identity, user):
    row = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=organization_id,
        action_code=action_code,
        idempotency_key=idempotency_key,
    ).first()
    if row:
        if row.request_hash != request_hash:
            raise RoutingVersionChangeError("IDEMPOTENCY_PAYLOAD_CONFLICT", "相同幂等键的业务内容不一致。")
        if row.source_identity_id != identity.pk:
            raise RoutingVersionChangeError("IDEMPOTENCY_SOURCE_CONFLICT", "相同幂等键的来源对象不一致。")
        return row
    return MasterDataWriteRequest.objects.create(
        organization_id=organization_id,
        action_code=action_code,
        entity_type=entity_type,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        source_identity=identity,
        audit_metadata={"operatorId": user.pk, "contractVersion": CONTRACT_VERSION},
    )


class RoutingVersionSuccessorService:
    @classmethod
    @transaction.atomic
    def create(cls, *, source_id, user, idempotency_key, reason, test_bom_version_id=None):
        if not str(idempotency_key or "").strip():
            raise RoutingVersionChangeError("IDEMPOTENCY_KEY_REQUIRED", "创建后续版本必须提供幂等键。")
        if not str(reason or "").strip():
            raise RoutingVersionChangeError("CHANGE_REASON_REQUIRED", "创建后续版本必须填写原因。")
        source = RoutingVersion.objects.select_for_update().select_related(
            "routing", "product", "product_version",
        ).filter(pk=source_id).first()
        if source is None:
            raise RoutingVersionChangeError("ROUTING_VERSION_NOT_FOUND", "来源工艺路线版本不存在。")
        organization_id, authorization, execution_chain = _authorize(user, source)
        if source.usage_purpose == 'TEST_BUSINESS':
            from .models import TestEngineeringRoutingBinding
            if TestEngineeringRoutingBinding.objects.filter(routing_version=source).exists():
                raise RoutingVersionChangeError('LEGACY_TEST_ROUTING_HISTORY','旧订单安排混入的测试版本仅保留历史；请在企业基础资料从通用标准源办理结构补正。')
            from .order_routing_models import OrderRoutingExecutionArrangement
            if source.status=='draft' and not OrderRoutingExecutionArrangement.objects.filter(routing_version=source,status='confirmed').exists():
                raise RoutingVersionChangeError('STANDARD_DRAFT_EDIT_DIRECTLY','标准草稿可正常维护；订单执行选择不构成标准新版本。已被确认安排引用时才需受控结构后继。')
        test_bom = None
        if test_bom_version_id is not None:
            from .test_engineering_routing_service import source as test_source, route_snapshot, TestRoutingError
            from .engineering_calculation_service import EngineeringCalculationError
            try:
                test_bom, record = test_source(user, test_bom_version_id, write=True)
                route_snapshot(source, record.engineering_instance)
            except (TestRoutingError, EngineeringCalculationError) as exc:
                raise RoutingVersionChangeError(exc.code, str(exc)) from exc
            except (ObjectDoesNotExist, ValueError, TypeError) as exc:
                raise RoutingVersionChangeError('TEST_ROUTE_SOURCE_NOT_FOUND', '测试来源或其精确版本不存在。') from exc
        if source.usage_purpose == 'TEST_BUSINESS' and test_bom is None:
            raise RoutingVersionChangeError('TEST_ROUTE_SOURCE_REQUIRED', '测试路线后继必须保留可信测试来源。')
        if source.status not in SUCCESSOR_SOURCE_STATUSES and not (source.usage_purpose == 'TEST_BUSINESS' and test_bom):
            raise RoutingVersionChangeError(
                "SUCCESSOR_SOURCE_STATUS_INVALID",
                "只有已评审、已发布或已失效的路线版本可以创建后续草稿版本。",
            )

        payload = {
            "sourceId": source.pk,
            "sourceUpdatedAt": source.updated_at.isoformat() if source.updated_at else "",
            "reason": str(reason).strip(),
        }
        if test_bom:
            payload['testBomVersionId'] = test_bom.pk
        identity, fingerprint = _identity(
            organization_id=organization_id,
            object_type="ROUTING_VERSION_SUCCESSOR_SOURCE",
            external_id=f"RoutingVersion:{source.pk}:successor" + (f":test:{test_bom.pk}" if test_bom else ""),
            target_type="routing-versions",
            fingerprint_payload={"sourceId": source.pk, "sourceRevision": source.revision},
        )
        request_hash = _canonical_hash(payload)
        ledger = _ledger(
            organization_id=organization_id,
            action_code=SUCCESSOR_ACTION,
            entity_type="routing-versions",
            idempotency_key=str(idempotency_key).strip(),
            request_hash=request_hash,
            identity=identity,
            user=user,
        )
        if ledger.status == MasterDataWriteRequest.Status.COMMITTED:
            target = RoutingVersion.objects.filter(
                pk=ledger.target_entity_id, routing_id=source.routing_id, status="draft",
            ).first()
            if target is None:
                raise RoutingVersionChangeError("IDEMPOTENT_RESULT_DRIFT", "幂等账本与后续草稿版本回读不一致。")
            return {**ledger.result, "idempotentReplay": True}
        if identity.mapping_status == ExternalIdentity.MappingStatus.MATCH and identity.target_entity_id:
            target = RoutingVersion.objects.filter(
                pk=identity.target_entity_id, routing_id=source.routing_id, status="draft",
            ).first()
            if target is None:
                raise RoutingVersionChangeError(
                    "SUCCESSOR_IDENTITY_DRIFT",
                    "正式来源身份与既有后续草稿版本回读不一致。",
                )
            raise RoutingVersionChangeError(
                "SUCCESSOR_ALREADY_CREATED",
                "该终态路线版本已经创建后续草稿版本，禁止使用新的幂等键重复创建。",
                {"routingVersionId": target.pk, "routingVersionNo": target.routing_version},
            )

        siblings = RoutingVersion.objects.select_for_update().filter(routing_id=source.routing_id)
        next_revision = max(siblings.values_list("revision", flat=True) or [0]) + 1
        version_no = f"V{next_revision}.0"
        while siblings.filter(routing_version=version_no).exists():
            next_revision += 1
            version_no = f"V{next_revision}.0"

        target = RoutingVersion(
            usage_purpose=('TEST_BUSINESS' if test_bom else
                'SHARED_DEFINITION' if source.usage_purpose=='SHARED_DEFINITION' else 'UNCLASSIFIED'),
            origin_version=source,
            test_origin_bom=test_bom,
            product=source.product,
            product_version=source.product_version,
            routing=source.routing,
            routing_version=version_no,
            revision=next_revision,
            effective_date=source.effective_date,
            expire_date=source.expire_date,
            approval_state="not_submitted",
            applicability=source.applicability,
            status="draft",
        )
        target.full_clean()
        from workflow_runtime.state_transitions import create_business_object_with_initial_state
        fields={f.attname:getattr(target,f.attname) for f in target._meta.concrete_fields if f.name not in ('id','status','created_at','updated_at')}
        target=create_business_object_with_initial_state(model=RoutingVersion, initial_state='draft', **fields)

        copied_steps = []
        for step in source.steps.select_related("operation", "routing_version__routing").order_by("sequence", "pk"):
            parameters = dict(step.operation_parameters or {})
            # A test engineering plan keeps unresolved operations unresolved.
            # Preserve genuine explicit/validated rules without importing the
            # production successor's blanket legacy-mandatory compatibility.
            contract = (explicit_contract(step) or legacy_exact_contract(step)) if test_bom else successor_contract(step)
            if contract:
                parameters["applicability"] = contract
            copied = RoutingStep(
                predecessor_step=step,
                routing_version=target,
                sequence=step.sequence,
                operation=step.operation,
                workshop=step.workshop,
                work_center=step.work_center,
                applies_to_item=step.applies_to_item,
                standard_hours=step.standard_hours,
                setup_hours=step.setup_hours,
                transfer_hours=step.transfer_hours,
                preparation_days=step.preparation_days,
                transfer_days=step.transfer_days,
                quality_checkpoint=step.quality_checkpoint,
                instruction=step.instruction,
                operation_parameters=parameters,
                predecessor_sequences=step.predecessor_sequences,
                effective_transition_mode=step.effective_transition_mode,
                resource_selection_rule=step.resource_selection_rule,
                is_active=step.is_active,
            )
            copied.full_clean()
            copied.save()
            copied_steps.append(copied)

        after = _snapshot(target)
        after.update({
            "sourceRoutingVersionId": source.pk,
            "copiedStepCount": len(copied_steps),
            "applicabilityContractVersion": CONTRACT_VERSION,
            "stepPredecessorMapping": [{"predecessorStepId": step.predecessor_step_id,
                "routingStepId": step.pk} for step in sorted(copied_steps, key=lambda row: row.pk)],
        })
        after["stepPredecessorMappingHash"] = _canonical_hash(after["stepPredecessorMapping"])
        audit = _audit(
            user=user,
            organization_id=organization_id,
            action_code=SUCCESSOR_ACTION,
            instance=target,
            before={"source": _snapshot(source), "sourceStepCount": source.steps.count()},
            after=after,
            reason=str(reason).strip(),
            authorization=authorization,
            execution_chain=execution_chain,
            audit_context={"sourceFingerprint": fingerprint},
        )
        from workflow_runtime.state_transitions import record_projected_business_transition
        record_projected_business_transition(object_type='RoutingVersion', object_id=target.pk,
            source_state='', target_state='draft', action_code=SUCCESSOR_ACTION, operator=user,
            reason=str(reason).strip(), audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions={('','draft')})
        identity.target_entity_id = str(target.pk)
        identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
        identity.source_fingerprint = fingerprint
        identity.full_clean()
        identity.save()
        result = {
            "sourceRoutingVersionId": source.pk,
            "sourceStatusLabel": source.get_status_display(),
            "routingVersionId": target.pk,
            "routingVersionNo": target.routing_version,
            "revision": target.revision,
            "statusLabel": target.get_status_display(),
            "copiedStepCount": len(copied_steps),
            "auditId": audit.pk,
            "writeRequestId": ledger.pk,
            "sourceIdentityId": identity.pk,
            "idempotentReplay": False,
        }
        ledger.status = MasterDataWriteRequest.Status.COMMITTED
        ledger.target_entity_id = str(target.pk)
        ledger.result = result
        ledger.save(update_fields=("status", "target_entity_id", "result", "updated_at"))
        return result


class RoutingStepApplicabilityMaintenanceService:
    @classmethod
    @transaction.atomic
    def update(cls, *, step_id, user, idempotency_key, mode, condition_code="", reason=""):
        if not str(idempotency_key or "").strip():
            raise RoutingVersionChangeError("IDEMPOTENCY_KEY_REQUIRED", "维护工序适用性必须提供幂等键。")
        if not str(reason or "").strip():
            raise RoutingVersionChangeError("CHANGE_REASON_REQUIRED", "维护工序适用性必须填写原因。")
        step = RoutingStep.objects.select_for_update().select_related(
            "routing_version__routing", "routing_version__product", "operation",
        ).filter(pk=step_id).first()
        if step is None:
            raise RoutingVersionChangeError("ROUTING_STEP_NOT_FOUND", "工艺路线步骤不存在。")
        version = step.routing_version
        organization_id, authorization, execution_chain = _authorize(user, version)
        if version.status != "draft":
            raise RoutingVersionChangeError(
                "ROUTING_VERSION_IMMUTABLE",
                "只有草稿路线版本允许维护步骤适用性；请先创建后续路线版本。",
            )
        try:
            contract = normalized_contract({"mode": mode, "conditionCode": condition_code})
        except ValidationError as exc:
            raise RoutingVersionChangeError("APPLICABILITY_CONTRACT_INVALID", "；".join(exc.messages)) from exc

        payload = {"stepId": step.pk, "contract": contract, "reason": str(reason).strip()}
        identity, fingerprint = _identity(
            organization_id=organization_id,
            object_type="ROUTING_STEP_APPLICABILITY",
            external_id=f"RoutingStep:{step.pk}:applicability",
            target_type="routing-steps",
            fingerprint_payload={"stepId": step.pk, "routingVersionId": version.pk},
        )
        ledger = _ledger(
            organization_id=organization_id,
            action_code=APPLICABILITY_ACTION,
            entity_type="routing-steps",
            idempotency_key=str(idempotency_key).strip(),
            request_hash=_canonical_hash(payload),
            identity=identity,
            user=user,
        )
        if ledger.status == MasterDataWriteRequest.Status.COMMITTED:
            return {**ledger.result, "idempotentReplay": True}

        before = _snapshot(step)
        parameters = dict(step.operation_parameters or {})
        parameters["applicability"] = contract
        step.operation_parameters = parameters
        step.full_clean()
        step.save(update_fields=("operation_parameters", "updated_at"))
        after = _snapshot(step)
        audit = _audit(
            user=user,
            organization_id=organization_id,
            action_code=APPLICABILITY_ACTION,
            instance=step,
            before=before,
            after=after,
            reason=str(reason).strip(),
            authorization=authorization,
            execution_chain=execution_chain,
            audit_context={"sourceFingerprint": fingerprint, "contractVersion": CONTRACT_VERSION},
        )
        identity.target_entity_id = str(step.pk)
        identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
        identity.source_fingerprint = fingerprint
        identity.full_clean()
        identity.save()
        result = {
            "routingStepId": step.pk,
            "routingVersionId": version.pk,
            "modeLabel": "必经工序" if mode == "MANDATORY" else "条件执行工序",
            "auditId": audit.pk,
            "writeRequestId": ledger.pk,
            "sourceIdentityId": identity.pk,
            "idempotentReplay": False,
        }
        ledger.status = MasterDataWriteRequest.Status.COMMITTED
        ledger.target_entity_id = str(step.pk)
        ledger.result = result
        ledger.save(update_fields=("status", "target_entity_id", "result", "updated_at"))
        return result
