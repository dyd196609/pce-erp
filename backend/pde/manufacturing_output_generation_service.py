"""One formal, draft-only handoff from an exact order-engineering source set.

Activation scope is explicit acceptance configuration, not an industry model or
version-number rule. Authority is resolved from existing permission and duties.
"""
from copy import deepcopy
import json
import time
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.db.models import Q

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from sales.models import SalesOrderItem
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, PositionResponsibility, RolePermission, UserRoleScopeAssignment
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object
from .models import EngineeringDocumentVersion, OrderEngineeringInstance, ProductManufacturingOutput
from .engineering_document_version_release_service import release_readback, project_release_content_integrity, project_release_source_completeness
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService

CONTRACT = "PCE-ORDER-MANUFACTURING-OUTPUT-GENERATE-V1.0"
ACTION = "pde.manufacturing_output.generate"
PERMISSION = "production.engineering.release"
RESPONSIBILITY = "RESP_PROD_COORD_006"
OBJECT = "ProductManufacturingOutput"
DEFAULT_SCOPE = {"companyCode": "COMP001", "orderNo": "SO202609180003", "lineNo": 1}
ACTION_CONTRACT = {"actionCode": ACTION, "displayName": "生成制造输出", "moduleCode": "PDE",
    "requiredPermission": PERMISSION, "requiredResponsibility": RESPONSIBILITY,
    "roleAuthority": "system.UserRoleScopeAssignment", "organizationScope": "ORGANIZATION",
    "serverValidator": "pde.manufacturing_output_generation_service.generate_manufacturing_output",
    "initialState": "draft", "manufacturingReleaseAllowed": False}


class ManufacturingOutputError(Exception):
    def __init__(self, code, message, http_status=409, details=None):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status
        self.details = details or {}


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _optional_id(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_VERSION_ID_INVALID", f"{label}必须是有效正整数。", 400)
    return int(value)


def _scope():
    return dict(getattr(settings, "PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE", DEFAULT_SCOPE))


def scoped_item(company_id, *, lock=False, item_id=None):
    scope = _scope()
    qs = SalesOrderItem.objects.select_related("sales_order__company", "uom")
    if lock:
        qs = qs.select_for_update()
    if item_id is not None:
        item = qs.filter(pk=item_id, sales_order__company_id=company_id).first()
    else:
        item = qs.filter(sales_order__company_id=company_id, sales_order__company__code=scope["companyCode"],
                         sales_order__order_no=scope["orderNo"], line_no=scope["lineNo"]).first()
    if not item:
        if item_id is not None:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SCOPE_DENIED", "所选订单行不存在或不属于当前公司。", 403)
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SCOPE_NOT_FOUND", "当前公司没有本轮已授权的订单行制造承接范围。", 404)
    return item


def eligible_executors(company_id):
    now = timezone.now()
    today = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
    grants = list(UserRoleScopeAssignment.objects.filter(
        organization_id=company_id, active=True, scope_code="ORGANIZATION",
        user__is_active=True, user__is_superuser=False,
        role__rolepermission__permission__code=PERMISSION,
    ).select_related("role").distinct())
    result = []
    employees = formal_employee_queryset(company_id=company_id).filter(
        user_id__in=[a.user_id for a in grants]
    ).select_related("user", "position_ref", "department_ref").only(
        "id", "employee_no", "user_id", "position_ref_id", "department_ref_id",
        "user__id", "user__username", "user__real_name", "user__company_id",
        "user__is_active", "user__is_superuser",
        "position_ref__id", "position_ref__code", "position_ref__name",
        "department_ref__id", "department_ref__code",
    )
    for employee in employees:
        duties = PositionResponsibility.objects.filter(position=employee.position_ref, active=True,
            responsibility__code=RESPONSIBILITY, responsibility__is_active=True, responsibility__status="ACTIVE"
        ).filter(Q(responsibility__effective_from__isnull=True) | Q(responsibility__effective_from__lte=today)
        ).filter(Q(responsibility__effective_to__isnull=True) | Q(responsibility__effective_to__gte=today))
        duty = duties.first()
        if not duty:
            continue
        decision = AuthorizationService.decide(user=employee.user, action_code=PERMISSION,
            organization_id=company_id, business_object={"organizationId": company_id},
            context={"moduleCode": "PDE", "businessWrite": True})
        if not decision.get("allowed"):
            continue
        assignments = [a for a in grants if a.user_id == employee.user_id]
        result.append({"userId": employee.user_id, "username": employee.user.username,
            "realName": employee.user.real_name, "employeeId": employee.pk, "employeeNo": employee.employee_no,
            "positionId": employee.position_ref_id, "positionCode": employee.position_ref.code,
            "positionName": employee.position_ref.name, "departmentCode": employee.department_ref.code,
            "roleIds": [a.role_id for a in assignments], "roleCodes": [a.role.code for a in assignments],
            "rolePermissionIds": list(RolePermission.objects.filter(role_id__in=[a.role_id for a in assignments], permission__code=PERMISSION).values_list("pk", flat=True)),
            "assignmentIds": [a.pk for a in assignments], "scopeCode": "ORGANIZATION", "companyId": company_id,
            "positionResponsibilityId": duty.pk, "responsibilityId": duty.responsibility_id,
            "responsibilityCode": duty.responsibility.code})
    return sorted(result, key=lambda row: row["userId"])


def require_executor(user, company_id):
    if not user.is_active or user.is_superuser or user.company_id != company_id:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_EXECUTOR_DENIED", "当前账号不能绕过正式制造输出执行链。", 403)
    actors = eligible_executors(company_id)
    if len(actors) != 1:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_EXECUTOR_NOT_UNIQUE", "制造输出生成执行人未能唯一解析，请核实正式授权。", 403)
    actor = actors[0]
    if actor["userId"] != user.pk:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_EXECUTOR_DENIED", "当前登录人员不是正式制造输出生成执行人。", 403)
    return actor


def resolve_sources(item, *, lock=False, document_version_id=None):
    qs = OrderEngineeringInstance.objects.filter(sales_order_item=item).exclude(status="inactive")
    if lock:
        qs = qs.select_for_update()
    instances = list(qs[:2])
    if len(instances) != 1 or instances[0].status not in {"calculated", "released"}:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_OEI_REQUIRED", "当前订单行必须唯一关联已完成工程转换的有效工程实例。")
    instance = instances[0]
    purpose = FormalManufacturingEligibilityService.resolve(instance)
    if not purpose["formalManufacturingEligible"]:
        raise ManufacturingOutputError(purpose["decisionCode"], purpose["message"])
    if item.sales_order.status in {"cancelled", "canceled", "closed"} or item.quantity <= 0:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_ORDER_LINE_INVALID", "订单行已关闭、撤销或数量无效。")
    documents = EngineeringDocumentVersion.objects.filter(order_engineering_instance=instance,
        release_subject_type="ORDER_ENGINEERED_PRODUCT").exclude(status="obsolete").select_related(
        "document", "related_bom__bom", "related_routing__routing", "order_engineering_baseline", "engineering_calculation")
    if lock:
        documents = documents.select_for_update()
    if document_version_id is not None:
        documents = documents.filter(pk=document_version_id)
    versions = list(documents[:2])
    if len(versions) != 1 or versions[0].status != "released":
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_RELEASED_DOCUMENT_REQUIRED", "当前订单工程实例必须唯一关联正式已发布的工程资料版本。")
    doc = versions[0]
    if doc.order_engineering_baseline_id:
        from .baseline_usage_service import validate_baseline
        from .product_design_service import ProductDesignError
        try:validate_baseline(doc.order_engineering_baseline)
        except ProductDesignError as exc:raise ManufacturingOutputError(exc.code,exc.message,exc.http_status) from exc
    completeness = project_release_source_completeness(doc)
    if not completeness["complete"]:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SOURCE_INCOMPLETE", "基线、核算、BOM或工艺版本尚未通过准确来源合同。", details={"gates": completeness["gates"]})
    release = release_readback(doc)
    integrity = project_release_content_integrity(doc)
    if not release["completed"] or not integrity["valid"]:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_RELEASE_FACT_REQUIRED", "工程资料必须具有完整发布事实，且当前内容与正式评审冻结内容一致。")
    fields = {"release_subject_type": "ORDER_ENGINEERED_PRODUCT", "definition_mode": "order_specific",
        "order_engineering_instance_id": instance.pk, "order_engineering_baseline_id": doc.order_engineering_baseline_id,
        "engineering_calculation_id": doc.engineering_calculation_id, "bom_version_id": doc.related_bom_id,
        "routing_version_id": doc.related_routing_id, "engineering_document_version_id": doc.pk,
        "engineering_status": "ready"}
    probe = ProductManufacturingOutput(**fields, release_status="draft")
    try:
        probe.clean()
    except ValidationError as exc:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_RELATION_INVALID", "制造输出准确来源关系不一致。", details=exc.message_dict) from exc
    identity = {**fields, "salesOrderItemId": item.pk,
        "baselineSnapshotHash": doc.order_engineering_baseline.snapshot_hash,
        "calculationResultHash": doc.engineering_calculation.result_hash,
        "bomContentHash": _hash(list(doc.related_bom.items.values())),
        # A new navigation FK is not part of the historical content contract.
        # Its own successor proof is validated separately; old hashes stay exact.
        "routingContentHash": _hash(list(doc.related_routing.steps.values(*[
            field.attname for field in doc.related_routing.steps.model._meta.concrete_fields
            if field.attname != "predecessor_step_id"
        ]))),
        "documentReviewContentHash": integrity["stableCurrentContentHash"],
        "documentReleaseTransitionId": release["businessStateTransitionId"]}
    return instance, doc, fields, _hash(identity)


def _versioned_sources(output, fields, fingerprint):
    if output.revision == 1 and output.predecessor_id is None:
        return fields, fingerprint
    fields = {**fields, "revision": output.revision, "predecessor_id": output.predecessor_id}
    mapping = [{"routingStepId": step_id, "predecessorStepId": predecessor_id}
        for step_id, predecessor_id in output.routing_version.steps.order_by("pk").values_list(
            "pk", "predecessor_step_id")]
    mapping_hash = sha256(json.dumps(mapping, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str).encode()).hexdigest()
    return fields, _hash({"sourceFingerprint": fingerprint,
        "revision": output.revision, "predecessorOutputId": output.predecessor_id,
        "stepPredecessorMapping": mapping, "stepPredecessorMappingHash": mapping_hash})


def _saved_requirement_integrity(requirement, *, read_cache=None):
    """Prove persisted material values from their existing native authority."""
    from decimal import Decimal
    from .engineering_rule_foundation import specification_hash
    from .saved_fact_material_requirement_service import (
        SERVICE_CODE, REQUIREMENT_ACTION_CODE, _hash as material_hash,
    )
    trace = requirement.trace if isinstance(requirement.trace, dict) else {}
    if trace.get('serviceCode') != SERVICE_CODE:
        # Native calculation outputs retain their exact successful output and
        # explicit quantity basis; this does not execute their rule again.
        detail = requirement.source_detail
        outputs = detail.rule.specification.get('outputs', [])
        output = outputs[0] if len(outputs) == 1 else {}
        expected = (requirement.calculated_quantity * requirement.order_quantity
            if requirement.quantity_basis == 'PER_SALES_ITEM_UNIT' else requirement.calculated_quantity)
        expected = expected.quantize(Decimal('0.000001'))
        scrap = output.get('scrapRate')
        scrap = Decimal(str(scrap)) if scrap is not None else None
        gross = (expected / (Decimal(1) - scrap)).quantize(Decimal('0.000001')) if scrap is not None else None
        if (len(outputs) != 1 or outputs[0].get('resultDomain') != 'MATERIAL_REQUIREMENT'
            or detail.status != 'succeeded' or detail.calculation_id != requirement.calculation_id
            or detail.uom_id != requirement.uom_id
            or output.get('materialId') != requirement.material_id
            or output.get('quantityBasis') != requirement.quantity_basis
            or requirement.order_quantity != requirement.calculation.sales_order_item.quantity
            or (output.get('itemRole') or 'material') != requirement.item_role
            or (output.get('requirementType') or 'manufacturing') != requirement.requirement_type
            or (output.get('supplyType') or 'BUY') != requirement.supply_type
            or (output.get('orderSpecification') or {}) != requirement.order_specification
            or requirement.scrap_rate != scrap or requirement.gross_quantity != gross
            or requirement.scrap_rate_status != ('maintained' if scrap is not None else 'not_maintained')
            or Decimal(str(detail.output_value.get('decimal'))) != requirement.calculated_quantity
            or requirement.net_quantity != expected):
            raise ValidationError('材料需求缺少一致的已保存原生数量输出。')
        return
    requests = list(MasterDataWriteRequest.objects.filter(
        organization_id=requirement.calculation.company_id, action_code=REQUIREMENT_ACTION_CODE,
        entity_type='EngineeringMaterialRequirement', target_entity_id=str(requirement.pk), status='COMMITTED')[:2])
    if len(requests) != 1:
        raise ValidationError('已保存材料需求缺少唯一原生提交账本。')
    request = requests[0]
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('auditId'),
        organization_id=requirement.calculation.company_id, action_code=REQUIREMENT_ACTION_CODE,
        target_type='EngineeringMaterialRequirement', target_id=requirement.pk).first()
    body = audit.after_snapshot.get('request') if audit and isinstance(audit.after_snapshot, dict) else None
    from .models import EngineeringRuleDefinition
    from system.models import User
    from .operation_requirement_service import _requirement_read_cache, _read_guarded_raw
    company_id = requirement.calculation.company_id
    cache = _requirement_read_cache(read_cache, company_id)
    mapping = _read_guarded_raw(cache,
        ('saved_material_mapping', company_id, trace.get('mappingRuleId'), 'released'), lambda:
        EngineeringRuleDefinition.objects.filter(pk=trace.get('mappingRuleId'),
            company_id=company_id, status='released').first())
    if (not isinstance(body, dict) or material_hash(body) != request.request_hash or not mapping
        or body.get('mappingRuleId') != mapping.pk or body.get('mappingSpecificationHash') != specification_hash(mapping.specification)
        or trace.get('mappingSpecificationHash') != body['mappingSpecificationHash']
        or body.get('calculationId') != requirement.calculation_id
        or body.get('calculationResultHash') != requirement.calculation.result_hash
        or body.get('materialId') != requirement.material_id
        or Decimal(str(body.get('quantity'))) != requirement.net_quantity
        or requirement.calculated_quantity != requirement.net_quantity
        or body.get('uom') != requirement.uom.code
        or request.result.get('requirementId') != requirement.pk
        or request.result.get('mappingRuleId') != mapping.pk
        or Decimal(str(request.result.get('quantity'))) != requirement.net_quantity
        or request.result.get('uom') != requirement.uom.code
        or not isinstance(request.audit_metadata, dict)
        or request.audit_metadata.get('actor',{}).get('accountId') != audit.actor_id
        or not _read_guarded_raw(cache, ('saved_material_actor_exists', company_id, audit.actor_id), lambda:
            User.objects.filter(pk=audit.actor_id, company_id=company_id).exists())
        or audit.actor_id != trace.get('operatorId')):
        raise ValidationError('材料需求数量、单位、规则或原生审计账本不一致。')
    if audit.after_snapshot.get('sourceFacts') != trace.get('sourceFacts'):
        raise ValidationError('材料需求保存的来源事实与原生审计不一致。')
    from .models import EngineeringDerivedFact
    for frozen in trace.get('sourceFacts') or []:
        fact = EngineeringDerivedFact.objects.select_related('uom').filter(pk=frozen.get('factId'),
            calculation_id=requirement.calculation_id, status='active').first()
        if (not fact or frozen.get('sourceDetailId') != fact.source_detail_id
            or Decimal(str(frozen.get('value'))) != Decimal(str(fact.value.get('decimal')))
            or frozen.get('uom') != (fact.uom.code if fact.uom_id else None)):
            raise ValidationError('材料需求保存的输入事实、值或单位已变化。')
    output = mapping.specification['outputs'][0]
    if any(output.get(key) != expected for key, expected in {
        'materialId':requirement.material_id, 'quantityBasis':requirement.quantity_basis,
        'itemRole':requirement.item_role, 'requirementType':requirement.requirement_type,
        'supplyType':requirement.supply_type, 'orderSpecification':requirement.order_specification,
        'scrapRate':str(requirement.scrap_rate) if requirement.scrap_rate is not None else None,
    }.items()):
        raise ValidationError('材料需求与已发布内部用途、规格或损耗合同不一致。')


def _saved_output_content_integrity(output, *, read_cache=None):
    """Validate saved internal business facts, not an import representation."""
    from .engineering_calculation_continuation_service import _main_proof
    from .formal_engineering_continuation_service import _baseline_reference, _hash as fact_hash
    from .product_bom_detail_projection import project_product_bom_material_detail
    from .engineering_calculation_service import _bom_item_role, _bom_requirement_type, _bom_supply_type
    from .engineering_fact_metadata import _prepare_origin
    from .operation_requirement_service import OperationRequirementError, _requirement_read_cache
    from .models import BOMItemSourceRequirement
    from django.db.models import Prefetch
    baseline, main = output.order_engineering_baseline, output.engineering_calculation
    cache = _requirement_read_cache(read_cache, main.company_id)
    items = list(baseline.items.select_related('design_item').filter(
        design_item__sales_order_item_id=main.sales_order_item_id).order_by('source_attribute_id','design_item_id','pk'))
    if not items or any(fact_hash(row.content_snapshot) != row.content_hash for row in items):
        raise ValidationError('固定工程基线明细的保存内容与Hash不一致。')
    if main.trace.get('baselineReference') != _baseline_reference(baseline, items, read_cache=read_cache):
        raise ValidationError('固定主核算的已保存基线范围与内部工程基线不一致。')
    try:
        _prepare_origin(main, read_cache=read_cache)
    except OperationRequirementError as exc:
        raise ValidationError(f'固定主核算输入或内部基线证明不一致：{exc.code}') from exc
    _main_proof(main, read_cache=read_cache)
    transitions = list(BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',
        object_id=main.pk).order_by('version'))
    action = 'production.engineering.calculation.execute'
    if (len(transitions) != 1 or transitions[0].version != 1
        or (transitions[0].source_state, transitions[0].target_state, transitions[0].action_code)
            != ('running', 'completed', action)):
        raise ValidationError('固定主核算缺少唯一原生完成状态事实。')
    transition = transitions[0]
    prefix = 'OrganizationOperatingAuditRecord:'
    reference = transition.audit_reference
    audit = None
    if isinstance(reference, str) and reference.startswith(prefix) and reference[len(prefix):].isdigit():
        audit = OrganizationOperatingAuditRecord.objects.select_related('actor').only(
            'id', 'organization_id', 'actor_id', 'action_code', 'target_type', 'target_id', 'after_snapshot',
            'actor__id', 'actor__username', 'actor__company_id').filter(pk=int(reference[len(prefix):])).first()
    after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
    state = after.get('state', {})
    if (not audit or audit.organization_id != main.company_id or audit.actor.company_id != main.company_id
        or audit.actor_id != transition.operator_id or audit.action_code != action
        or audit.target_type != 'EngineeringCalculationRecord' or audit.target_id != main.pk
        or not isinstance(state, dict) or state.get('status') != 'completed'
        or after.get('authorization', {}).get('allowed') is not True
        or after.get('executionChain', {}).get('account') != audit.actor.username
        or any(state.get(key) != getattr(main,key) for key in ('company_id', 'scope', 'source_record_id',
            'sales_order_item_id', 'engineering_instance_id', 'input_hash', 'rule_graph_hash', 'result_hash', 'trace'))):
        raise ValidationError('固定主核算与其原生完成审计的结果或输入Hash不一致。')
    bom = output.bom_version
    rows = project_product_bom_material_detail(bom=bom.bom, bom_version=bom,
        order_item=main.sales_order_item)
    if not rows or any(not row['sourceRequirements'] for row in rows):
        raise ValidationError('已定稿订单BOM缺少完整的已保存来源需求关系。')
    seen = set()
    links_query = BOMItemSourceRequirement.objects.select_related(
        'material_requirement__source_detail',
        'material_requirement__calculation__sales_order_item',
        'material_requirement__material', 'material_requirement__uom',
    ).prefetch_related('material_requirement__source_detail__rule')
    for item in bom.items.select_related('bom_version__bom', 'bom_version__product',
            'parent_item', 'material', 'uom').prefetch_related(
                Prefetch('source_requirements', queryset=links_query)):
        item.full_clean()
        links = sorted(item.source_requirements.all(), key=lambda link:(link.material_requirement.sequence,link.pk))
        specifications, design_nos = [], []
        for link in links:
            requirement = link.material_requirement
            requirement.full_clean(); link.full_clean()
            if cache is None:
                _saved_requirement_integrity(requirement)
            else:
                _saved_requirement_integrity(requirement, read_cache=cache)
            expected = requirement.gross_quantity if requirement.scrap_rate_status == 'maintained' else requirement.net_quantity
            if (link.contributed_quantity != expected or requirement.pk in seen
                or item.item_role != _bom_item_role(requirement.item_role)
                or item.requirement_type != _bom_requirement_type(requirement.requirement_type)
                or item.supply_type != _bom_supply_type(requirement.supply_type)
                or item.scrap_rate_status != requirement.scrap_rate_status or item.scrap_rate != requirement.scrap_rate):
                raise ValidationError('BOM来源贡献量、用途或损耗合同与正式需求不一致。')
            seen.add(requirement.pk)
            spec = dict(requirement.order_specification or {})
            number = spec.pop('designItemNo', None)
            if number and number not in design_nos:design_nos.append(number)
            specifications.append(spec)
        if any(spec != specifications[0] for spec in specifications):
            raise ValidationError('BOM聚合来源的正式规格不兼容。')
        expected_spec = ({**specifications[0], 'sourceDesignItemNos':design_nos,
            'aggregationMode':'EXACT_COMPATIBLE_REQUIREMENTS'} if len(links) > 1
            else links[0].material_requirement.order_specification)
        if item.order_specification != expected_spec:
            raise ValidationError('BOM已保存规格与原生来源关系不一致。')
    if seen != set(main.material_requirements.values_list('pk', flat=True)):
        raise ValidationError('已定稿BOM的完整来源需求集合发生变化。')


def _saved_output_content_read_proof(output, *, user, lock, read_cache, plan_id):
    """Reuse only this exact fixed anchor's content proof in one plan read."""
    from . import operation_requirement_service as native
    cache = (native._requirement_read_cache(read_cache, user.company_id)
        if user is not None and not lock and type(plan_id) is int and plan_id > 0 else None)
    if cache is not None and cache.user_id != user.pk:
        cache = None
    epoch = cache._write_epoch if cache is not None else None
    key = None
    if cache is not None:
        try:
            baseline, main, bom = (output.order_engineering_baseline,
                output.engineering_calculation, output.bom_version)
            instance = output.order_engineering_instance
            anchors = (output, baseline, baseline.sales_order, main, main.source_record,
                main.sales_order_item, main.sales_order_item.sales_order, main.engineering_instance,
                bom, bom.bom, instance, instance.sales_order_item, instance.sales_order_item.sales_order)
            key = ('fixed_saved_output_content', user.company_id, user.pk, plan_id, native._today(),
                *((row._meta.label_lower, native._proof_record_hash(row, read_cache=cache)) for row in anchors))
        except (AttributeError, KeyError, TypeError, ValueError, ObjectDoesNotExist):
            pass  # Unsupported guard values retain the original validator.
    if key is None or key not in cache:
        _saved_output_content_integrity(output, read_cache=cache)
        if key is not None and cache.is_current(user.company_id) and cache._write_epoch == epoch:
            cache[key] = True


def validate_selected_output(output, *, user=None, lock=False, read_cache=None, _content_plan_id=None):
    from .bom_usage_contract import is_test_source
    if is_test_source(output):
        raise ManufacturingOutputError('TEST_BUSINESS_PRODUCTION_DENIED','测试BOM禁止生产消费者选择。',403)
    """Validate a pinned published combination, never an implicit latest one."""
    from .manufacturing_output_release_service import release_readback as output_release_readback
    from .engineering_calculation_service import EngineeringCalculationError
    from .product_bom_detail_projection import ProductBomDetailProjectionError
    if output.release_subject_type != "ORDER_ENGINEERED_PRODUCT" or not output.order_engineering_instance_id:
        raise ManufacturingOutputError("ORDER_ENGINEERING_IDENTITY_CONFLICT", "所选输出不是订单工程发布组合。")
    if output.order_engineering_baseline_id:
        from .baseline_usage_service import validate_baseline
        from .product_design_service import ProductDesignError
        try:validate_baseline(output.order_engineering_baseline)
        except ProductDesignError as exc:raise ManufacturingOutputError(exc.code,exc.message,exc.http_status) from exc
    item = output.order_engineering_instance.sales_order_item
    company_id = item.sales_order.company_id
    if user is not None and user.company_id != company_id:
        raise ManufacturingOutputError("ORDER_ENGINEERING_RELEASE_SCOPE_CONFLICT", "所选制造输出不属于当前公司。", 403)
    instance = output.order_engineering_instance
    from .operation_requirement_service import _requirement_read_cache, _read_guarded_raw
    cache = _requirement_read_cache(None if lock else read_cache, company_id)
    if cache is not None and user is not None and cache.user_id != user.pk:
        cache = None
    def raw(key, loader):
        return _read_guarded_raw(cache, ('manufacturing_output_validation_raw', company_id,
            output.pk, *key), loader)
    from .order_lifecycle_source_projection import terminal_read_allowed
    terminal_read = not lock and item.sales_order.status == 'closed' and terminal_read_allowed(item.sales_order)
    if (instance.status not in {'calculated','released'} or item.sales_order.status in {'cancelled','canceled'}
        or (item.sales_order.status == 'closed' and not terminal_read)
        or item.quantity <= 0):
        raise ManufacturingOutputError('ORDER_ENGINEERING_SOURCE_CONFLICT', '固定订单行或工程实例已不满足内部正式业务身份。')
    purpose = (FormalManufacturingEligibilityService.resolve(instance, read_cache=cache)
        if cache is not None else FormalManufacturingEligibilityService.resolve(instance))
    if not purpose['formalManufacturingEligible']:
        raise ManufacturingOutputError(purpose['decisionCode'], purpose['message'])
    documents = EngineeringDocumentVersion.objects.select_related('document','related_bom__bom',
        'related_routing__routing','order_engineering_baseline','engineering_calculation')
    if lock:documents = documents.select_for_update()
    document = documents.filter(pk=output.engineering_document_version_id).first()
    if not document or document.status != 'released':
        raise ManufacturingOutputError('ORDER_ENGINEERING_SOURCE_CONFLICT', '所固定的正式工程资料不存在或未发布。')
    completeness, integrity = project_release_source_completeness(document), project_release_content_integrity(document)
    document_release = (release_readback(document, read_cache=cache) if cache is not None else release_readback(document))
    if not completeness['complete'] or not integrity['valid'] or not document_release['completed']:
        raise ManufacturingOutputError('ORDER_ENGINEERING_FROZEN_CONTENT_CHANGED', '内部工程资料关联、稳定业务内容或正式发布证明不一致。')
    fields = {'release_subject_type':'ORDER_ENGINEERED_PRODUCT','definition_mode':'order_specific',
        'order_engineering_instance_id':document.order_engineering_instance_id,
        'order_engineering_baseline_id':document.order_engineering_baseline_id,
        'engineering_calculation_id':document.engineering_calculation_id,'bom_version_id':document.related_bom_id,
        'routing_version_id':document.related_routing_id,'engineering_document_version_id':document.pk,'engineering_status':'ready'}
    if output.revision != 1 or output.predecessor_id is not None:
        fields.update(revision=output.revision, predecessor_id=output.predecessor_id)
    if any(getattr(output, name) != value for name, value in fields.items()):
        raise ManufacturingOutputError("ORDER_ENGINEERING_SOURCE_CONFLICT", "所选输出与自身冻结工程来源不一致。")
    if output.release_status != "released_to_manufacturing":
        raise ManufacturingOutputError("ORDER_ENGINEERING_OUTPUT_NOT_RELEASED", "订单工程制造输出尚未正式发布至制造。")
    try:
        output.full_clean()
        _saved_output_content_read_proof(output, user=user, lock=lock,
            read_cache=read_cache, plan_id=_content_plan_id)
        # An independent publication consumes its own frozen source set. The
        # complete old/new step bijection belongs to an existing plan's explicit
        # version handoff, whose preview and binding proof still require it.
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError,
            EngineeringCalculationError, ProductBomDetailProjectionError) as exc:
        raise ManufacturingOutputError("ORDER_ENGINEERING_INPUT_INVALID", "所选制造输出精确关系或已保存内部来源无效。",
            details=getattr(exc,'message_dict',{'errors':str(exc)})) from exc
    generation = generation_readback(output, read_cache=cache) if cache is not None else generation_readback(output)
    release = (output_release_readback(output, read_cache=cache) if cache is not None else output_release_readback(output))
    history = (output_snapshot(output, read_cache=cache) if cache is not None else output_snapshot(output))["statusTransitionHistory"]
    expected = [("", "draft", ACTION), ("draft", "released_to_manufacturing", "pde.manufacturing_output.release")]
    if (not generation["completed"] or not release["completed"] or len(history) != 2
            or any((entry["source_state"], entry["target_state"], entry["action_code"]) != states
                or entry["version"] != index
                for index, (entry, states) in enumerate(zip(history, expected), 1))):
        raise ManufacturingOutputError("ORDER_ENGINEERING_RELEASE_FACT_INCOMPLETE", "制造输出生成、发布及状态转换证据不完整。")
    proofs = (generation, release)
    for proof in proofs:
        if not raw(('request_company_exists', proof['writeRequestId']), lambda:
                MasterDataWriteRequest.objects.filter(pk=proof["writeRequestId"], organization_id=company_id).exists()):
            raise ManufacturingOutputError("ORDER_ENGINEERING_RELEASE_SCOPE_CONFLICT", "制造输出提交证据不属于订单公司。")
    audit_ids = tuple(proof['auditId'] for proof in proofs)
    audits = {row.pk: row for row in raw(('audits', audit_ids), lambda: list(
        OrganizationOperatingAuditRecord.objects.filter(pk__in=audit_ids, organization_id=company_id)))}
    if len(audits) != 2:
        raise ManufacturingOutputError("ORDER_ENGINEERING_RELEASE_SCOPE_CONFLICT", "制造输出审计不属于订单公司。")
    if any(audits[generation['auditId']].after_snapshot.get(name) != value for name,value in fields.items()):
        raise ManufacturingOutputError('ORDER_ENGINEERING_SOURCE_CONFLICT', '制造生成审计的冻结内部来源与当前精确关联不一致。')
    frozen = [audits[proof['auditId']].after_snapshot.get('sourceFingerprint') for proof in proofs]
    if any(not isinstance(value, str) or len(value) != 64 for value in frozen) or frozen[0] != frozen[1]:
        raise ManufacturingOutputError("ORDER_ENGINEERING_FROZEN_CONTENT_CHANGED", "工程来源与正式生成或发布冻结指纹不一致。")
    fingerprint = frozen[0]
    if audits[release["auditId"]].after_snapshot.get("sourceSnapshot") != fields:
        raise ManufacturingOutputError("ORDER_ENGINEERING_RELEASE_SOURCE_CONFLICT", "制造发布审计冻结来源与所选输出不一致。")
    return {"instance": instance, "document": document, "sourceFields": fields,
        "sourceFingerprint": fingerprint, "generationReadback": generation, "releaseReadback": release}


def _version_candidate(instance, fields, fingerprint, *, predecessor_output_id=None, lock=False):
    outputs = ProductManufacturingOutput.objects.filter(order_engineering_instance=instance,
        release_subject_type="ORDER_ENGINEERED_PRODUCT")
    if lock:
        outputs = outputs.select_for_update()
    exact = outputs.filter(**fields).first()
    if exact:
        if predecessor_output_id is not None and exact.predecessor_id != predecessor_output_id:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_PREDECESSOR_CONFLICT", "精确组合已绑定其他前驱，禁止改写。")
        version_fields, version_fingerprint = _versioned_sources(exact, fields, fingerprint)
        proof = generation_readback(exact)
        if not proof["completed"]:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_EXISTING_CONFLICT", "精确组合缺少完整生成提交事实。")
        if not OrganizationOperatingAuditRecord.objects.filter(pk=proof["auditId"],
                after_snapshot__sourceFingerprint=version_fingerprint).exists():
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_FROZEN_CONTENT_CHANGED", "精确组合来源已偏离生成冻结指纹。")
        return exact, version_fields, version_fingerprint
    if not outputs.exists():
        if predecessor_output_id is not None:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_PREDECESSOR_CONFLICT", "首个制造输出不得指定其他实例前驱。")
        return None, fields, fingerprint
    if predecessor_output_id is None:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_PREDECESSOR_REQUIRED", "已有历史输出；新组合必须明确选择已发布前驱。")
    predecessor = outputs.filter(pk=predecessor_output_id).first()
    if not predecessor:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_PREDECESSOR_CONFLICT", "前驱必须属于同一订单工程实例。")
    validate_selected_output(predecessor, lock=lock)
    if outputs.filter(predecessor_id=predecessor.pk).exists():
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SUCCESSOR_EXISTS", "该前驱已有继任输出，禁止分叉。")
    probe = ProductManufacturingOutput(**fields, revision=predecessor.revision + 1, predecessor=predecessor)
    return None, *_versioned_sources(probe, fields, fingerprint)


def _output_read_cache(output, read_cache):
    from .operation_requirement_service import _requirement_read_cache
    company_id = (output.order_engineering_instance.company_id
        if output.order_engineering_instance_id else None)
    return _requirement_read_cache(read_cache, company_id)


def generation_readback(output, *, read_cache=None):
    from .operation_requirement_service import _read_guarded_raw
    cache = _output_read_cache(output, read_cache) if read_cache is not None else None
    def raw(key, loader):
        return _read_guarded_raw(cache, ('manufacturing_generation_readback_raw',
            cache.company_id if cache is not None else None, output.pk, *key), loader)
    transition = raw(('transition', OBJECT, ACTION, '', 'draft'), lambda:
        BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=output.pk,
        action_code=ACTION, source_state="", target_state="draft").first())
    request = raw(('request', OBJECT, ACTION, 'COMMITTED', str(output.pk)), lambda:
        MasterDataWriteRequest.objects.filter(entity_type=OBJECT, target_entity_id=str(output.pk),
        action_code=ACTION, status="COMMITTED").first())
    audit = None
    if transition:
        reference = transition.audit_reference.rsplit(':', 1)[-1]
        audit = raw(('audit', reference, OBJECT, ACTION, transition.operator_id), lambda:
            OrganizationOperatingAuditRecord.objects.filter(pk=reference,
            target_type=OBJECT, target_id=output.pk, action_code=ACTION, actor_id=transition.operator_id).first())
    completed = bool(transition and request and audit and request.result.get("row", {}).get("id") == output.pk
        and request.result.get("auditId") == audit.pk
        and request.result.get("initializationTransitionId") == transition.pk
        and request.audit_metadata.get("operatorId") == transition.operator_id)
    return {"completed": completed, "auditId": audit.pk if audit else None,
        "writeRequestId": request.pk if request else None, "initializationTransitionId": transition.pk if transition else None,
        "actorId": transition.operator_id if transition else None,
        "actorUsername": (raw(('actor_username', transition.pk), lambda:
            BusinessStateTransition.objects.filter(pk=transition.pk).values_list(
            "operator__username", flat=True).first()) or "") if transition else "",
        "createdAt": transition.timestamp.isoformat() if transition else ""}


def output_snapshot(output, *, read_cache=None):
    from .operation_requirement_service import _read_guarded_raw
    cache = _output_read_cache(output, read_cache) if read_cache is not None else None
    item = output.order_engineering_instance.sales_order_item if output.order_engineering_instance_id else None
    history = deepcopy(_read_guarded_raw(cache, ('manufacturing_output_raw_history',
        cache.company_id if cache is not None else None, output.pk, OBJECT), lambda: list(
        BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=output.pk).order_by("version", "pk").values(
        "id", "source_state", "target_state", "action_code", "operator_id", "audit_reference", "version"))))
    proof = generation_readback(output, read_cache=cache) if cache is not None else generation_readback(output)
    return {"id": output.pk, "statusCode": output.release_status, "statusLabel": output.get_release_status_display(),
        "releaseSubjectType": output.release_subject_type, "orderNo": item.sales_order.order_no if item else "",
        "orderLineNo": item.line_no if item else None, "salesOrderItemId": item.pk if item else None,
        "orderEngineeringInstanceId": output.order_engineering_instance_id,
        "orderEngineeringBaselineId": output.order_engineering_baseline_id,
        "engineeringCalculationId": output.engineering_calculation_id,
        "bomVersionId": output.bom_version_id, "routingVersionId": output.routing_version_id,
        "engineeringDocumentVersionId": output.engineering_document_version_id,
        "revision": output.revision, "predecessorOutputId": output.predecessor_id,
        "generationReadback": proof, "statusTransitionHistory": history, "statusTransitionCount": len(history),
        "stateMachineConsistent": bool(proof["completed"] and history and history[-1]["target_state"] == output.release_status),
        "manufacturingReleaseExecuted": output.release_status == "released_to_manufacturing"}


def candidate_projection(user, *, sales_order_item_id=None, document_version_id=None, predecessor_output_id=None):
    base = {"contractVersion": CONTRACT, **_scope(), "statusLabel": "制造输出候选尚未通过准入",
        "actionCode": ACTION, "actionLabel": ACTION_CONTRACT["displayName"], "actionContract": ACTION_CONTRACT, "permissionCode": PERMISSION,
        "currentUser": {"id": user.pk, "username": user.username, "realName": user.real_name},
        "generationAllowed": False, "sourceReady": False, "output": None, "outputCount": 0,
        "eligibleExecutors": eligible_executors(user.company_id), "businessWriteCount": 0}
    try:
        sales_order_item_id = _optional_id(sales_order_item_id, "订单行")
        document_version_id = _optional_id(document_version_id, "工程资料版本")
        predecessor_output_id = _optional_id(predecessor_output_id, "前驱制造输出")
        item = scoped_item(user.company_id, item_id=sales_order_item_id)
        instance, doc, fields, fingerprint = resolve_sources(item, document_version_id=document_version_id)
        existing, fields, fingerprint = _version_candidate(instance, fields, fingerprint,
            predecessor_output_id=predecessor_output_id)
        base.update({"salesOrderItemId": item.pk, "orderEngineeringInstanceNo": instance.instance_no,
            "orderNo": item.sales_order.order_no, "lineNo": item.line_no,
            "companyCode": item.sales_order.company.code,
            "engineeringBaselineNo": doc.order_engineering_baseline.baseline_no,
            "engineeringCalculationNo": doc.engineering_calculation.calculation_no,
            "bomVersionLabel": f"{doc.related_bom.bom_version} / Rev{doc.related_bom.revision}",
            "bomStatusLabel": doc.related_bom.get_status_display(),
            "routingVersionLabel": f"{doc.related_routing.routing.routing_code} / {doc.related_routing.routing_version} / Rev{doc.related_routing.revision}",
            "routingStatusLabel": doc.related_routing.get_status_display(),
            "documentVersionLabel": doc.document_version, "documentStatusLabel": doc.get_status_display(),
            "sourceIds": fields, "sourceFingerprint": fingerprint, "sourceReady": True})
        base["outputCount"] = ProductManufacturingOutput.objects.filter(order_engineering_instance=instance).count()
        if existing:
            base.update(output=output_snapshot(existing), statusLabel="所选版本制造输出已形成")
            return base
        actor = require_executor(user, user.company_id)
        base.update(generationAllowed=True, currentActor=actor, statusLabel="可生成制造输出")
    except ManufacturingOutputError as exc:
        base.update(firstBlockerCode=exc.code, firstBlockerMessage=exc.message, blockerDetails=exc.details)
    return base


def _generate_atomic(user, payload, key):
    with transaction.atomic():
        item = scoped_item(user.company_id, lock=True, item_id=payload.get("salesOrderItemId"))
        actor = require_executor(user, user.company_id)
        if payload.get("salesOrderItemId") != item.pk:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SCOPE_DENIED", "请求不属于本轮已授权的准确订单行。", 403)
        instance, doc, fields, fingerprint = resolve_sources(item, lock=True,
            document_version_id=payload.get("engineeringDocumentVersionId"))
        existing, fields, fingerprint = _version_candidate(instance, fields, fingerprint,
            predecessor_output_id=payload.get("predecessorOutputId"), lock=True)
        if payload.get("sourceFingerprint") != fingerprint:
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_CANDIDATE_STALE", "工程来源组合已变化，请刷新候选后重新确认。")
        request_hash = _hash({"actorId": user.pk, "payload": payload})
        ledger = MasterDataWriteRequest.objects.select_for_update().filter(organization_id=user.company_id,
            action_code=ACTION, idempotency_key=key).first()
        if ledger:
            if ledger.request_hash != request_hash:
                raise ManufacturingOutputError("IDEMPOTENCY_PAYLOAD_CONFLICT", "同一幂等键不得提交不同人员或不同内容。")
            if ledger.status == "COMMITTED":
                return {**ledger.result, "idempotentReplay": True}
        if existing:
            if any(getattr(existing, name) != value for name, value in fields.items()) or not generation_readback(existing)["completed"]:
                raise ManufacturingOutputError("MANUFACTURING_OUTPUT_EXISTING_CONFLICT", "已有制造输出的来源或正式生成事实与本候选不一致。")
            return {"contractVersion": CONTRACT, "row": output_snapshot(existing), "idempotentReplay": True,
                "auditId": generation_readback(existing)["auditId"], "writeRequestId": generation_readback(existing)["writeRequestId"],
                "initializationTransitionId": generation_readback(existing)["initializationTransitionId"], "manufacturingReleaseExecuted": False}
        external_id = (f"OEI:{instance.pk}:MANUFACTURING_OUTPUT" if fields.get("revision", 1) == 1 else
            f"OEI:{instance.pk}:MANUFACTURING_OUTPUT:R{fields['revision']}:{fingerprint}")
        identity, _ = ExternalIdentity.objects.get_or_create(organization_id=user.company_id, source_system="PCE",
            source_type="FORMAL_ORDER_ENGINEERING", source_object_type=OBJECT,
            external_id=external_id, defaults={"target_entity_type": OBJECT,
                "mapping_status": "CREATE", "source_fingerprint": fingerprint, "audit_metadata": {"contractVersion": CONTRACT}})
        if identity.target_entity_type != OBJECT or (identity.source_fingerprint and identity.source_fingerprint != fingerprint):
            raise ManufacturingOutputError("MANUFACTURING_OUTPUT_SOURCE_IDENTITY_CONFLICT", "正式来源身份与制造候选不一致。")
        ledger = ledger or MasterDataWriteRequest.objects.create(organization_id=user.company_id, action_code=ACTION,
            entity_type=OBJECT, idempotency_key=key, request_hash=request_hash, source_identity=identity,
            audit_metadata={"operatorId": user.pk, "executionChain": actor})
        # Empty state is transaction-internal only. The shared initializer and
        # transition service persist the single real initialization -> draft fact.
        output = create_business_object_with_initial_state(model=ProductManufacturingOutput,
            initial_state="", status_field="release_status", **fields)
        audit = OrganizationOperatingAuditRecord.objects.create(action_code=ACTION, actor=user,
            organization_id=user.company_id, target_type=OBJECT, target_id=output.pk,
            target_label=f"{item.sales_order.order_no} / 行{item.line_no} / 制造输出{output.pk}", reason=payload["reason"],
            before_snapshot={}, after_snapshot={**fields, "release_status": "draft", "sourceFingerprint": fingerprint,
                "executionChain": actor, "writeRequestId": ledger.pk, "manufacturingReleaseExecuted": False})
        initial = transition_business_object(business_object=output, object_type=OBJECT, source_state="", target_state="draft",
            action_code=ACTION, operator=user, reason=payload["reason"], audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={("", "draft")}, status_field="release_status", version_field=None)
        output.full_clean()
        identity.target_entity_id = str(output.pk)
        identity.mapping_status = "MATCH"
        identity.save(update_fields=["target_entity_id", "mapping_status", "last_seen"])
        result = {"contractVersion": CONTRACT, "row": output_snapshot(output), "auditId": audit.pk,
            "writeRequestId": ledger.pk, "initializationTransitionId": initial.pk,
            "idempotentReplay": False, "manufacturingReleaseExecuted": False}
        ledger.target_entity_id, ledger.status, ledger.result = str(output.pk), "COMMITTED", result
        ledger.save(update_fields=["target_entity_id", "status", "result", "updated_at"])
        result["row"] = output_snapshot(output)
        ledger.result = result
        ledger.save(update_fields=["result", "updated_at"])
        return result


def generate_manufacturing_output(*, user, payload, idempotency_key):
    if set(payload) - {"salesOrderItemId", "sourceFingerprint", "reason", "action",
                       "engineeringDocumentVersionId", "predecessorOutputId"}:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_FIELDS_DENIED", "生成请求不得自行指定来源外键或最终状态。", 400)
    payload = dict(payload)
    for name, label in (("salesOrderItemId", "订单行"), ("engineeringDocumentVersionId", "工程资料版本"),
                        ("predecessorOutputId", "前驱制造输出")):
        if name in payload:
            payload[name] = _optional_id(payload[name], label)
    reason = str(payload.get("reason") or "").strip()
    key = str(idempotency_key or "").strip()
    if not reason or len(reason) > 300 or not key or len(key) > 150:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_INPUT_REQUIRED", "必须提供生成确认说明和有效幂等键。", 400)
    if payload.get("action") != ACTION:
        raise ManufacturingOutputError("MANUFACTURING_OUTPUT_ACTION_DENIED", "请求动作与正式制造输出生成合同不一致。", 400)
    from .models import ProductBOM
    if ProductBOM.objects.filter(company_id=user.company_id,usage_purpose='TEST_BUSINESS',order_engineering_instance__sales_order_item_id=payload.get('salesOrderItemId')).exists():
        raise ManufacturingOutputError('TEST_BUSINESS_PRODUCTION_DENIED','测试业务BOM禁止生成制造输出。',403)
    payload["reason"] = reason
    for attempt in range(5):
        try:
            return _generate_atomic(user, payload, key)
        except (OperationalError, IntegrityError) as exc:
            retryable = isinstance(exc, IntegrityError) or "locked" in str(exc).lower()
            if not retryable or attempt == 4:
                raise ManufacturingOutputError("MANUFACTURING_OUTPUT_CONCURRENT_CONFLICT", "制造输出并发请求未完成；请刷新并回读已有结果。") from exc
            time.sleep(0.03 * (attempt + 1))
