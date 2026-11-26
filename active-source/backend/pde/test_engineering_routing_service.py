"""Pinned, immutable TEST_BUSINESS engineering references; no production release."""
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import BOMVersion, RoutingVersion, TestEngineeringRoutingBinding
from .test_business_bom_service import authorize, validate_source
from .design_revision_approval_service import digest
from .production_foundation_service import _snapshot


class TestRoutingError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def fail(code, message):
    raise TestRoutingError(code, message)


def source(user, bom_id, *, write=False):
    bom = BOMVersion.objects.select_related('bom__source_calculation', 'order_engineering_instance').get(pk=bom_id)
    authorize(user, 'production.master_data.routing.maintain' if write else 'production.master_data.view', bom.bom.company_id)
    if bom.usage_purpose != 'TEST_BUSINESS' or bom.bom.usage_purpose != 'TEST_BUSINESS' or bom.status != 'draft':
        fail('TEST_DRAFT_BOM_REQUIRED', '仅接受来源完整的测试业务BOM草稿。')
    record = bom.bom.source_calculation
    if not record or bom.order_engineering_instance_id != record.engineering_instance_id:
        fail('TEST_ROUTING_SOURCE_MISMATCH', '测试BOM与根核算、工程实例不一致。')
    if bom.source_calculation_id != record.pk and not bom.origin_version_id:
        fail('TEST_ROUTING_SOURCE_MISMATCH', '派生测试BOM缺少根来源沿革。')
    validate_source(record, user)
    from .product_bom_detail_projection import project_product_bom_material_detail
    project_product_bom_material_detail(bom=bom.bom, bom_version=bom, order_item=record.sales_order_item)
    return bom, record


def route_snapshot(version, instance):
    route = version.routing
    today = date.today()
    from .models import _routing_matches_order_engineering_instance
    test_draft = (version.usage_purpose == 'TEST_BUSINESS' and version.status == 'draft'
        and version.origin_version_id and version.test_origin_bom_id
        and version.test_origin_bom.usage_purpose == 'TEST_BUSINESS'
        and version.test_origin_bom.order_engineering_instance_id == instance.pk
        and version.origin_version.routing_id == version.routing_id)
    if (not route or route.company_id != instance.company_id or not route.is_active
            or route.status != 'released' or not (version.status == 'released' and version.usage_purpose != 'TEST_BUSINESS' or test_draft)
            or not _routing_matches_order_engineering_instance(route, instance)
            or any(start and start > today for start in [route.effective_from, version.effective_date])
            or any(end and end < today for end in [route.effective_to, version.expire_date])):
        fail('TEST_ROUTE_SCOPE_INVALID', '路线及精确版本须在同公司有效发布并匹配当前工程范围。')
    from .manufacturing_structure_service import _matches_applicability
    if not _matches_applicability(version.applicability, {}):
        fail('TEST_ROUTE_APPLICABILITY_UNRESOLVED', '版本存在附加适用条件，须先按原契约核定，不能静默放行。')
    steps = []
    for step in version.steps.select_related('operation__work_center', 'operation__workshop', 'work_center', 'workshop').order_by('sequence'):
        op = step.operation
        if not step.is_active or not op.is_active or op.company_id != instance.company_id:
            fail('TEST_ROUTE_OPERATION_INVALID', '路线包含停用或越公司工序。')
        wc = step.work_center or op.work_center
        shop = step.workshop or op.workshop
        if wc and (wc.company_id != instance.company_id or not wc.is_active):
            fail('TEST_ROUTE_RESOURCE_INVALID', '工序资源停用或越公司。')
        steps.append({'stepId': step.pk, 'sequence': step.sequence, 'operationId': op.pk,
            'operationCode': op.code, 'operationName': op.name, 'predecessors': step.predecessor_sequences,
            'workCenterId': wc.pk if wc else None, 'workCenterCode': wc.code if wc else None,
            'workCenterName': wc.name if wc else '待维护', 'workshopId': shop.pk if shop else None,
            'workshopName': shop.name if shop else '待维护',
            'resourceBasis': '步骤直接引用' if step.work_center_id else '正式工序默认工作中心' if op.work_center_id else '未维护工作中心',
            'stepProof': _snapshot(step), 'operationProof': _snapshot(op),
            'resourceProof': {key:getattr(wc,key) for key in ('id','code','name','company_id','workshop_id','is_active')} if wc else None})
    if not steps:
        fail('TEST_ROUTE_EMPTY', '完整路线不能没有工序。')
    version_proof = _snapshot(version)
    if version.usage_purpose != 'TEST_BUSINESS':
        # Legacy immutable bindings predate the additive purpose fields.
        for field in ('usage_purpose','origin_version_id','test_origin_bom_id'):
            version_proof.pop(field, None)
    return {'route': _snapshot(route), 'version': version_proof, 'steps': steps}


def preview(*, user, bom_version_id, routing_version_id, decisions):
    bom, record = source(user, bom_version_id)
    version = RoutingVersion.objects.select_related('routing').get(pk=routing_version_id)
    if version.usage_purpose == 'TEST_BUSINESS':
        _, origin_record = source(user, version.test_origin_bom_id)
        if origin_record.pk != record.pk:
            fail('TEST_ROUTE_SOURCE_MISMATCH', '测试路线与绑定物料清单的根核算来源不一致。')
    route = route_snapshot(version, record.engineering_instance)
    if not isinstance(decisions, list) or len(decisions) != len(route['steps']):
        fail('TEST_FULL_ROUTE_REQUIRED', '须逐项说明完整路线所有工序，包含未触发或待核定工序。')
    by_id = {x.get('stepId'): x for x in decisions if isinstance(x, dict)}
    if len(by_id) != len(decisions) or set(by_id) != {x['stepId'] for x in route['steps']}:
        fail('TEST_FULL_ROUTE_REQUIRED', '工序必须完整且唯一对应当前固定版本。')
    rows = []
    for step in route['steps']:
        decision = by_id[step['stepId']]
        configured = (step['stepProof'].get('operation_parameters') or {}).get('applicability') or {}
        if configured.get('mode') == 'MANDATORY' and decision.get('decision') != 'REQUIRED':
            fail('CONFIGURED_MANDATORY_STEP_REQUIRED', '该固定版本步骤已配置为必经，不能以测试假设、材料空值或条件未触发改为不执行。')
        user_confirmed = decision.get('evidenceClass') == 'USER_CONFIRMED'
        required_fields = {'stepId', 'stage', 'decision', 'basis', 'evidenceClass'} | ({'evidenceAuditId'} if user_confirmed else set())
        if (set(decision) != required_fields
                or decision['decision'] not in {'REQUIRED', 'NOT_APPLICABLE', 'PENDING'}
                or decision['evidenceClass'] not in {'TEST_ASSUMPTION', 'UNRESOLVED', 'USER_CONFIRMED'}
                or not str(decision['stage']).strip() or not str(decision['basis']).strip()):
            fail('TEST_ROUTE_DECISION_REQUIRED', '每道工序须明确阶段、执行条件和依据；本测试方案只接受补拟假设或待核定，不冒充正式来源裁决。')
        if user_confirmed:
            from system.models import OrganizationOperatingAuditRecord
            audit = OrganizationOperatingAuditRecord.objects.filter(pk=decision['evidenceAuditId'],
                organization_id=record.company_id, target_type='RoutingStep', target_id=step['stepId'],
                action_code='pde.routing_step.maintain_applicability').first()
            after = (audit.after_snapshot.get('state') or {}) if audit else {}
            parameters = after.get('operation_parameters') or {}
            if (decision['decision'] != 'REQUIRED' or not audit or not audit.reason.strip()
                    or after.get('routing_version_id') != version.pk
                    or after.get('operation_id') != step['operationId']
                    or (parameters.get('applicability') or {}).get('mode') != 'MANDATORY'):
                fail('USER_REQUIRED_EVIDENCE_INVALID', '用户必经依据须对应当前版本步骤的真实必经配置及审计。')
        rows.append({**step, **decision,
            'decisionLabel':{'REQUIRED':'用户明确必经' if user_confirmed else '补拟必经（本测试方案要求经过，依据为补拟假设）','NOT_APPLICABLE':'本单不执行（未满足已声明的执行条件）','PENDING':'待核定（尚无足够依据决定是否执行）'}[decision['decision']],
            'evidenceLabel':{'USER_CONFIRMED':'用户明确工艺依据及必经配置审计','SOURCE':'来源事实','TEST_ASSUMPTION':'补拟测试假设','UNRESOLVED':'依据不足'}[decision['evidenceClass']]})
    proof = {'bomVersion': _snapshot(bom), 'bomHeader': _snapshot(bom.bom),
        'calculationId': record.pk, 'calculationResultHash': record.result_hash,
        'calculationInputHash': record.input_hash, 'baselineSnapshotHash': record.baseline.snapshot_hash,
        'sourceContentHash': record.source_record.content_hash,
        'baselineId': record.baseline_id, 'revisionId': record.design_revision_id,
        'sourceId': record.source_record_id, 'sourceVersion': record.source_record.source_version,
        'oei': _snapshot(record.engineering_instance), 'bomItems': [_snapshot(x) for x in bom.items.order_by('pk')],
        'route': route, 'decisions': decisions}
    return {'previewHash': digest(proof), 'proof': proof, 'steps': rows,
        'bomVersionId': bom.pk, 'routingVersionId': version.pk, 'routingId': version.routing_id,
        'purposeLabel': '测试业务：固定路线版本；禁止正式制造', 'formalManufacturingEligible': False,
        'sourceQualification': '获准来源工艺/颜色未明时仍需业务核定；测试假设不得冒充正式确认',
        'databaseBusinessWriteCount': 0}


@transaction.atomic
def bind(*, user, bom_version_id, routing_version_id, decisions, preview_hash, reason, key):
    bom, record = source(user, bom_version_id, write=True)
    BOMVersion.objects.select_for_update().get(pk=bom.pk)
    if not isinstance(reason, str) or not reason.strip() or not isinstance(key, str) or not key.strip():
        fail('TEST_ROUTING_REASON_KEY_REQUIRED', '保存测试路线须填写依据和幂等键。')
    current = preview(user=user, bom_version_id=bom.pk, routing_version_id=routing_version_id, decisions=decisions)
    if current['previewHash'] != preview_hash:
        fail('TEST_ROUTE_PREVIEW_CHANGED', '来源、路线版本或工序资源已变化，请重新预览；不会切换最新版。')
    old = TestEngineeringRoutingBinding.objects.filter(bom_version=bom).first()
    if old:
        if old.preview_hash != preview_hash:
            fail('TEST_ROUTE_ALREADY_PINNED', '此物料清单版本已有旧机制固定引用，历史保持；新的固定引用或执行调整请到订单工序执行安排办理，不因此新增物料清单版本。')
        return {'id': old.pk, 'idempotent': True}
    fail('ORDER_EXECUTION_ARRANGEMENT_REQUIRED','旧测试固定绑定仅保留历史；新引用和执行安排请从订单工序执行安排办理，无需新增物料清单版本。')


def read(*, user, bom_version_id):
    bom, record = source(user, bom_version_id)
    obj = TestEngineeringRoutingBinding.objects.filter(bom_version=bom).first()
    if not obj:
        return {'bound': False, 'bomVersionId': bom.pk, 'databaseBusinessWriteCount': 0}
    from system.models import OrganizationOperatingAuditRecord
    audit = OrganizationOperatingAuditRecord.objects.filter(target_type='TestEngineeringRoutingBinding',
        target_id=obj.pk, actor_id=obj.created_by_id, organization_id=obj.company_id,
        action_code='production.master_data.routing.maintain').first()
    if not audit or audit.after_snapshot.get('previewHash') != obj.preview_hash:
        fail('TEST_ROUTE_AUDIT_REQUIRED', '固定路线绑定缺少匹配的权威审计，不能作为有效承接。')
    decisions = obj.source_proof['decisions']
    current = preview(user=user, bom_version_id=bom.pk, routing_version_id=obj.routing_version_id, decisions=decisions)
    fixed = obj.source_proof['route']
    identity = {'orderId':record.sales_order_item.sales_order_id,
        'orderNo':record.sales_order_item.sales_order.order_no,
        'bomVersionId':bom.pk, 'bomVersionName':bom.bom_version,
        'routingCode':fixed['route']['routing_code'], 'routingName':fixed['route']['name'],
        'routingVersionName':fixed['version']['routing_version'],
        'routingVersionRevision':fixed['version']['revision'],
        'routingVersionRecordId':obj.routing_version_id}
    return {'bound': True, 'id': obj.pk, 'auditId': audit.pk, 'bomVersionId': bom.pk, 'routingVersionId': obj.routing_version_id,
        'usagePurpose': obj.usage_purpose, 'purposeLabel': '测试业务（禁止正式制造）',
        'sourceUnchanged': current['previewHash'] == obj.preview_hash,
        'displayIdentity': identity,
        'statusLabel': '固定版本已保存' if current['previewHash'] == obj.preview_hash else '来源或固定版本已变化，须重新核定',
        'steps': [{**row,
            'decisionLabel': ('用户明确必经' if row['evidenceClass']=='USER_CONFIRMED' else '补拟必经（本测试方案要求经过，依据为补拟假设）') if row['decision']=='REQUIRED' else '本单不执行（未满足已声明的执行条件）' if row['decision']=='NOT_APPLICABLE' else '待核定（尚无足够依据决定是否执行）',
            'quantityLabel': '经过但无定量数据' if row['decision']=='REQUIRED' else '是否执行尚待核定' if row['decision']=='PENDING' else '本单不执行',
            'quantity': None} for row in obj.step_plan],
        'historicalPlan': True, 'legacyContractLabel':'旧机制固定绑定（保留历史；不作为新订单执行安排）',
        'routeVersionPurposeLabel': obj.routing_version.get_usage_purpose_display(),
        'originRoutingVersionId': obj.routing_version.origin_version_id,
        'versionNameExplanation': '系统初始版本（历史名称保留）' if fixed['version']['routing_version'] == 'SYSTEM_INITIAL_VERSION' else '后继测试草稿版本' if obj.routing_version.usage_purpose == 'TEST_BUSINESS' else '既有版本标识（原文保留）',
        'stepsCount':len(obj.step_plan), 'proof': obj.source_proof, 'formalManufacturingEligible': False,
        'databaseBusinessWriteCount': 0}


def company_facts(user):
    """Separate test references from the existing formal handoff count."""
    rows = []
    from .engineering_calculation_service import EngineeringCalculationError
    for obj in TestEngineeringRoutingBinding.objects.filter(company_id=user.company_id).order_by('-pk'):
        try:
            rows.append(read(user=user, bom_version_id=obj.bom_version_id))
        except (TestRoutingError, EngineeringCalculationError) as exc:
            rows.append({'id':obj.pk, 'bomVersionId':obj.bom_version_id,
                'factLoadStatus':'read_failed','statusLabel':str(exc),
                'formalManufacturingEligible':False,'databaseBusinessWriteCount':0})
    return rows
