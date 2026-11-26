"""Continue a complete saved material contract set to a proven main version.

There is no parallel material writer here.  Every result is created by the
existing saved-fact service, with its permissions, identity, ledger and audits.
"""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .engineering_calculation_continuation_service import continuation_proof, digest
from .engineering_fact_extension_service import _source_snapshot
from .engineering_rule_foundation import evaluate_specification, specification_hash
from .manufacturing_output_generation_service import _saved_requirement_integrity
from .models import (EngineeringCalculationContinuation, EngineeringDerivedFact,
    EngineeringMaterialRequirement, EngineeringRuleDefinition)
from .saved_fact_material_requirement_service import (
    SERVICE_CODE as SAVED_FACT_SERVICE, SavedFactInputBinding,
    SavedFactMaterialRequirementContract, SavedFactMaterialRequirementError,
    apply_saved_fact_material_requirement, preview_saved_fact_material_requirement,
)

CONTRACT = 'PCE-MATERIAL-REQUIREMENT-VERSION-CONTINUATION-V1'


def _fail(code, message, **details):
    raise SavedFactMaterialRequirementError(code, message, details)


def _bind_fact_pairs(*, previous, current, design_item_id, design_item_no, inputs):
    """Join by immutable business identity; values and ordering are not keys."""
    pairs = []
    for declared in inputs:
        variable = declared['canonicalName']
        old_rows = [f for f in previous if f.canonical_field == variable
            and f.trace.get('designItemId') == design_item_id
            and f.fact_code == f'{design_item_no}:{variable}']
        new_rows = [f for f in current if f.canonical_field == variable
            and f.trace.get('designItemId') == design_item_id
            and f.fact_code == f'{design_item_no}:{variable}']
        if len(old_rows) != 1 or len(new_rows) != 1:
            _fail('MATERIAL_CONTINUATION_FACT_NOT_UNIQUE',
                '新旧材料输入必须按设计对象身份和规范字段唯一对应。',
                designItemId=design_item_id, canonicalField=variable,
                previousCount=len(old_rows), currentCount=len(new_rows))
        old, new = old_rows[0], new_rows[0]
        old_unit = old.uom.code if old.uom_id else None
        new_unit = new.uom.code if new.uom_id else None
        if (old.uom_id != new.uom_id or old_unit != new_unit
            or declared.get('unit') is not None and declared['unit'] != old_unit
            or old.trace.get('designItemNo') != design_item_no
            or new.trace.get('designItemNo') != design_item_no):
            _fail('MATERIAL_CONTINUATION_FACT_MISMATCH',
                '新旧材料输入的设计身份或正式计量单位不一致。',
                previousFactId=old.pk, newFactId=new.pk, canonicalField=variable)
        pairs.append((declared, old, new))
    return pairs


def _material_contract(requirement, rule, material):
    """Reject changed identities/specifications instead of copying a label."""
    spec = rule.specification
    outputs = spec.get('outputs', [])
    if (len(outputs) != 1 or outputs[0].get('resultDomain') != 'MATERIAL_REQUIREMENT'
        or requirement.trace.get('serviceCode') != SAVED_FACT_SERVICE
        or requirement.trace.get('mappingSpecificationHash') != specification_hash(spec)):
        _fail('MATERIAL_CONTINUATION_MAPPING_UNPROVEN', '旧材料需求不是完整可追溯的正式Mapping合同。')
    output = outputs[0]
    if not material.base_uom_id:
        _fail('MATERIAL_CONTINUATION_MATERIAL_MISMATCH', '材料缺少正式基本单位，不能承接。')
    expected = {'materialId': material.pk, 'materialCode': material.code,
        'outputUom': material.base_uom.code, 'quantityBasis': requirement.quantity_basis,
        'itemRole': requirement.item_role, 'requirementType': requirement.requirement_type,
        'supplyType': requirement.supply_type, 'orderSpecification': requirement.order_specification}
    if (material.pk != requirement.material_id or not material.is_active
        or not material.base_uom_id or material.base_uom_id != requirement.uom_id
        or not material.base_uom.is_active
        or requirement.order_specification.get('materialCode') != material.code
        or requirement.order_specification.get('materialSpecification') != material.specification
        or any(output.get(key) != value for key, value in expected.items())):
        _fail('MATERIAL_CONTINUATION_MATERIAL_MISMATCH',
            '材料身份、编码、规格、单位或原用途合同不一致，禁止自动承接。', requirementId=requirement.pk)
    return output


def _contract_for(*, requirement, rule, output, pairs, continuation, proof,
                  authorization_reference, idempotency_key):
    bindings = tuple(SavedFactInputBinding(
        variable=row['canonicalName'], fact_code=new.canonical_field,
        expected_uom_code=row.get('unit'), unit_dimension=row.get('unitDimension'),
        unit_required=row.get('unitRequired', True),
        integer_required=row.get('unitDimension') in ('count', 'dimensionless'),
    ) for row, old, new in pairs)
    values = {row['canonicalName']: {'value': new.value['decimal'],
        'unit': new.uom.code if new.uom_id else None, 'unitDimension': row.get('unitDimension')}
        for row, old, new in pairs}
    quantity = Decimal(str(evaluate_specification(rule.specification, values)['value'])).quantize(Decimal('.000001'))
    identity = requirement.trace.get('sourceMaterialExternalIdentity') or {}
    specification = deepcopy(requirement.order_specification)
    missing_revision_policy = 'designRevisionReference' in specification
    # An explicitly frozen structural-material policy is the only exemption
    # from the current primary-design-material check.
    structural_policy = (rule.specification.get('provenance') or {}).get('designMaterialReferencePolicy')
    if structural_policy not in (None,
        'STRUCTURE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL',
        'EDGE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL'):
        _fail('MATERIAL_CONTINUATION_POLICY_UNSUPPORTED', '旧材料设计引用策略未受支持，不能猜测。')
    evidence = {'contractVersion': CONTRACT, 'continuation': proof,
        'previousRequirementId': requirement.pk,
        'previousRequirementHash': digest({f.attname: getattr(requirement, f.attname)
            for f in requirement._meta.concrete_fields}),
        'previousMappingId': rule.pk, 'previousMappingVersion': rule.version,
        'previousMappingHash': specification_hash(rule.specification),
        'scope': {'companyId': continuation.company_id,
            'salesOrderItemId': continuation.sales_order_item_id,
            'engineeringInstanceId': continuation.engineering_instance_id,
            'previousCalculationId': continuation.previous_calculation_id,
            'newCalculationId': continuation.new_calculation_id,
            'baselineId': continuation.baseline_id,
            'designItemId': requirement.trace['designItemId'],
            'designItemNo': requirement.trace['designItemNo']},
        'factCorrespondence': [{'variable': declared['canonicalName'],
            'previous': _source_snapshot(old, continuation.previous_calculation),
            'current': _source_snapshot(new, continuation.new_calculation)}
            for declared, old, new in pairs]}
    version = f'{rule.version}.C{continuation.new_calculation_id}'
    if len(version) > EngineeringRuleDefinition._meta.get_field('version').max_length:
        _fail('MATERIAL_CONTINUATION_VERSION_TOO_LONG', '来源版本身份超过正式字段长度，禁止截断。')
    return SavedFactMaterialRequirementContract(
        mapping_no=requirement.trace['mappingNo'], mapping_rule_code=rule.rule_code,
        mapping_version=version, rule_name=rule.rule_name,
        order_no=continuation.sales_order_item.sales_order.order_no,
        calculation_id=continuation.new_calculation_id,
        design_item_no=requirement.trace['designItemNo'], material_id=requirement.material_id,
        material_code=requirement.material.code, output_uom_code=requirement.uom.code,
        output_name=output['canonicalName'], expression=rule.specification['expression'],
        inputs=bindings, primary_source_fact_code=output['sourceFactCode'],
        expected_quantity=quantity, authorization_reference=authorization_reference,
        idempotency_key=f'{idempotency_key}:R{requirement.pk}',
        purpose_code=output['structureRole'], quantity_basis=requirement.quantity_basis,
        item_role=requirement.item_role, requirement_type=requirement.requirement_type,
        supply_type=requirement.supply_type, scrap_rate=requirement.scrap_rate,
        order_specification=specification, output_unit_dimension=output.get('unitDimension'),
        provenance={**deepcopy(rule.specification.get('provenance', {})),
            'materialVersionContinuation': evidence,
            'previousProvenance': deepcopy(rule.specification.get('provenance', {}))},
        require_design_material_reference=not structural_policy and not missing_revision_policy,
        source_external_identity_id=identity.get('id'),
        allow_missing_design_revision_when_source_identity_confirmed=missing_revision_policy)


def _prepare(*, user, continuation_id, authorization_reference, idempotency_key, lock=False):
    if not str(authorization_reference or '').strip() or not str(idempotency_key or '').strip():
        _fail('MATERIAL_CONTINUATION_AUTHORITY_REQUIRED', '必须提供本次来源承接授权依据和幂等键。')
    query = EngineeringCalculationContinuation.objects.select_related(
        'previous_calculation', 'new_calculation', 'sales_order_item__sales_order',
        'adoption', 'write_request', 'audit_record')
    if lock:
        query = query.select_for_update()
    row = query.filter(pk=continuation_id, company_id=user.company_id).first()
    if not row:
        _fail('MATERIAL_CONTINUATION_NOT_FOUND', '正式主核算接续不存在或跨公司。')
    proof = continuation_proof(row)
    old, new = row.previous_calculation, row.new_calculation
    if (old.source_record_id != new.source_record_id or old.sales_order_item_id != new.sales_order_item_id
        or old.engineering_instance_id != new.engineering_instance_id):
        _fail('MATERIAL_CONTINUATION_SCOPE_MISMATCH', '新旧主核算来源、订单行或工程实例不一致。')
    old_objects = {v['designItemId']: v for v in old.trace.get('objectInputSnapshot', [])}
    new_objects = {v['designItemId']: v for v in new.trace.get('objectInputSnapshot', [])}
    if not old_objects or old_objects.keys() != new_objects.keys() or any(
        old_objects[k]['designItemNo'] != new_objects[k]['designItemNo'] for k in old_objects):
        _fail('MATERIAL_CONTINUATION_OBJECT_SCOPE_MISMATCH', '新旧来源必须具有相同完整设计对象身份集合。')
    requirements = EngineeringMaterialRequirement.objects.select_related(
        'material__base_uom', 'uom', 'calculation__sales_order_item', 'source_detail__rule').filter(
        calculation_id=old.pk).order_by('pk')
    if lock:
        requirements = requirements.select_for_update()
    requirements = list(requirements)
    if not requirements or {r.trace.get('designItemId') for r in requirements} != set(old_objects):
        _fail('MATERIAL_CONTINUATION_REQUIREMENT_SCOPE_INCOMPLETE', '前驱材料需求未完整覆盖正式设计对象，不能部分承接。')
    facts = EngineeringDerivedFact.objects.select_related('uom', 'source_detail__rule', 'calculation').filter(
        calculation_id__in=(old.pk, new.pk), status='active')
    if lock:
        facts = facts.select_for_update()
    facts = list(facts)
    previous, current = [f for f in facts if f.calculation_id == old.pk], [f for f in facts if f.calculation_id == new.pk]
    contracts = []
    for requirement in requirements:
        try:
            _saved_requirement_integrity(requirement)
        except ValidationError as error:
            _fail('MATERIAL_CONTINUATION_REQUIREMENT_UNPROVEN', '旧材料需求原生证明不完整。',
                requirementId=requirement.pk, validation=str(error))
        rule_query = EngineeringRuleDefinition.objects.filter(pk=requirement.trace.get('mappingRuleId'),
            company_id=user.company_id, status='released')
        if lock:
            rule_query = rule_query.select_for_update()
        rule = rule_query.first()
        if not rule:
            _fail('MATERIAL_CONTINUATION_MAPPING_UNPROVEN', '旧材料需求缺少已发布Mapping。')
        output = _material_contract(requirement, rule, requirement.material)
        applicability = rule.specification.get('applicability', {})
        if (applicability.get('salesOrderItemId') != row.sales_order_item_id
            or applicability.get('designItemNo') != requirement.trace.get('designItemNo')
            or requirement.trace.get('calculationId') != old.pk
            or rule.specification.get('sourceEvidence', {}).get('calculationId') != old.pk):
            _fail('MATERIAL_CONTINUATION_MAPPING_SCOPE_MISMATCH', '旧Mapping范围与原核算、订单行及设计对象不一致。')
        pairs = _bind_fact_pairs(previous=previous, current=current,
            design_item_id=requirement.trace['designItemId'],
            design_item_no=requirement.trace['designItemNo'], inputs=rule.specification['inputs'])
        frozen = {f['factCode']: f['factId'] for f in requirement.trace['sourceFacts']}
        if frozen != {declared['canonicalName']: old_fact.pk for declared, old_fact, new_fact in pairs}:
            _fail('MATERIAL_CONTINUATION_MAPPING_FACT_MISMATCH', '旧材料需求输入集合与Mapping精确字段不一致。')
        contracts.append(_contract_for(requirement=requirement, rule=rule, output=output,
            pairs=pairs, continuation=row, proof=proof, authorization_reference=authorization_reference,
            idempotency_key=idempotency_key))
    previews = [preview_saved_fact_material_requirement(user=user, contract=contract) for contract in contracts]
    frozen_set = {'contractVersion': CONTRACT, 'continuation': proof,
        'previousRequirementIds': [r.pk for r in requirements],
        'contracts': [{'mappingCode': c.mapping_rule_code, 'version': c.mapping_version,
            'quantity': str(c.expected_quantity), 'provenance': c.provenance} for c in contracts]}
    return contracts, {'contractVersion': CONTRACT, 'continuation': proof,
        'contextHash': digest(frozen_set), 'previousRequirementIds': [r.pk for r in requirements],
        'requirementCount': len(contracts), 'designItemIds': sorted(old_objects),
        'previews': previews, 'businessWriteCount': 0}


class MaterialRequirementVersionContinuationService:
    @staticmethod
    def preview(*, user, continuation_id, authorization_reference, idempotency_key):
        return _prepare(user=user, continuation_id=continuation_id,
            authorization_reference=authorization_reference, idempotency_key=idempotency_key)[1]

    @staticmethod
    @transaction.atomic
    def apply(*, user, continuation_id, authorization_reference, idempotency_key, expected_context_hash):
        contracts, preview = _prepare(user=user, continuation_id=continuation_id,
            authorization_reference=authorization_reference, idempotency_key=idempotency_key, lock=True)
        if not expected_context_hash or preview['contextHash'] != expected_context_hash:
            _fail('MATERIAL_CONTINUATION_STALE_PREVIEW', '材料来源承接范围或证据已变化，请重新预览。')
        results = [apply_saved_fact_material_requirement(user=user, contract=contract) for contract in contracts]
        return {**preview, 'results': results,
            'businessWriteCount': sum(r.get('businessWriteCount', r.get('directWriteCount', 0)) for r in results),
            'idempotentReplay': all(r.get('idempotent', False) for r in results)}
