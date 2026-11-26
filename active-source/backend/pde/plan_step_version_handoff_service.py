"""Controlled activation of an already published engineering successor.

Preparing/publishing upstream objects is separate. This service writes only its
binding, normal request/identity, audit and shared state facts.
"""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import ProductionPlan
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)

from .models import (EngineeringDerivedFact, EngineeringRuleDefinition, PlanStepVersionBinding,
    ProductDesignRevision, ProductManufacturingOutput, ProductionPlanOperationRequirementAllocation, RoutingStep)
from .plan_step_context_service import (CONTRACT, OBJECT, PlanStepContextError, digest,
    root_step, route_mapping, binding_proof, resolve_step_context, version_fact, calculation_source)

ACTIVATE = 'pde.plan_step.activate_engineering_version'
_UNSELECTED = object()


class PlanStepVersionHandoffError(PlanStepContextError):
    pass


def fail(code, message, **details):
    raise PlanStepVersionHandoffError(code, message, details)


def _authority(user, *, write=False):
    from . import operation_requirement_service as native
    decisions = [native._authorize(user, native.VIEW), native._authorize(user, native.PLAN_VIEW)]
    chain = None
    if write:
        decisions.append(native._authorize(user, native.EXECUTE))
        chain = native._allocation_executor(user)
    return decisions, chain


def _allocation_rows(plan):
    return list(ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=plan)
        .select_related('routing_step__routing_version__routing', 'operation_requirement__source_calculation',
            'operation_requirement__source_fact', 'operation_requirement__source_detail__rule').order_by('pk'))


def _row_fingerprint(rows):
    return [{'allocationId': row.pk, 'inputHash': row.input_hash, 'sourceHash': row.source_hash,
        'snapshotHash': digest(row.source_snapshot), 'auditId': row.audit_record_id,
        'allocationHash':digest({f.attname:getattr(row,f.attname) for f in row._meta.concrete_fields})} for row in rows]


def _assert_unallocated(rows, root):
    if any(root_step(row.routing_step).pk == root_step(root).pk for row in rows):
        fail('HANDOFF_ALLOCATED_STEP_BLOCKED', '目标逻辑步骤已有历史分配，本版禁止替换或撤销')


def _normalise_identity(value, baseline_map, item_map):
    if isinstance(value, list):
        return [_normalise_identity(v, baseline_map, item_map) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == 'baselineId':
            result[key] = baseline_map.get(item, item)
        elif key == 'baselineItemId':
            result[key] = item_map.get(item, item)
        else:
            result[key] = _normalise_identity(item, baseline_map, item_map)
    return result


def _normalise_declared_metadata(context, projected, configurations, records, targets, pairs):
    """Map only configured native FK identities with proved source correspondence."""
    declarations = [row for row in configurations if row.get('sourceType') == 'FORMAL_SOURCE_IDENTITY']
    if not declarations:
        return projected
    changes = {}
    for source in context.get('sources', []):
        snapshot, proof = source.get('source', {}), source.get('metadataProof', {})
        record = records.get(snapshot.get('sourceFactId'))
        bindings = proof.get('bindings', [])
        if (not record or not isinstance(bindings, list)
            or any(snapshot.get(key) != record[key] or proof.get(key) != record[key]
                for key in ('sourceFactId', 'sourceCalculationId', 'sourceDetailId'))):
            fail('HANDOFF_SOURCE_IDENTITY_UNPROVEN', '分类身份缺少同一真实来源Fact及成功明细证明')
        target = targets.get(pairs.get(record['sourceFactId']))
        for configuration in declarations:
            name, field = configuration.get('name'), configuration.get('valueField')
            matches = [row for row in bindings if row.get('configuration') == configuration]
            value = record.get(field)
            if (len(matches) != 1 or type(value) is not int or value <= 0
                or matches[0].get('inputValue') != value
                or matches[0].get('sourceIdentity') != {'valueField':field, 'value':value}
                or proof.get(field) != value or source.get('metadata', {}).get(name) != value
                or context.get('metadata', {}).get(name) != value
                or name in context.get('group', {}) and context['group'][name] != value):
                fail('HANDOFF_SOURCE_IDENTITY_UNPROVEN', '分类身份配置、固定证明与真实来源外键不一致')
            if target is not None:
                replacement = target.get(field)
                if (type(replacement) is not int or replacement <= 0
                    or name in changes and changes[name] != replacement):
                    fail('HANDOFF_SOURCE_IDENTITY_UNPROVEN', '分类身份没有唯一、同义的正式目标外键')
                changes[name] = replacement
    for name, value in changes.items():
        projected['metadata'][name] = value
        if name in projected.get('group', {}):
            projected['group'][name] = value
    return projected


def _impact(user, plan, output, rows, basis, *, base=None, baseline=None):
    """Compare native dependencies; human no-start evidence alone never passes."""
    from . import operation_requirement_service as native
    from .engineering_fact_extension_service import EngineeringFactExtensionService
    original = plan.planning_requirement.demand.manufacturing_output
    old = original.engineering_calculation
    new = base if base is not None else output.engineering_calculation
    target_baseline = baseline if baseline is not None else output.order_engineering_baseline
    result = {'contractVersion': CONTRACT, 'historicalAllocationCount': len(rows),
        'preservedAllocations': _row_fingerprint(rows), 'newVersionReusedAllocationIds': [],
        'historicalRowsGrantedFutureExecution': False, 'blockers': [], 'dependencyComparisons': []}
    if (not isinstance(basis, dict) or set(basis) != {'executionFactReference', 'executionStatement',
        'allMaterialUnissued', 'allWorkUnstarted'} or not str(basis.get('executionFactReference', '')).strip()
        or not str(basis.get('executionStatement', '')).strip()
        or basis.get('allMaterialUnissued') is not True or basis.get('allWorkUnstarted') is not True):
        result['blockers'].append({'code': 'HANDOFF_EXECUTION_FACT_REQUIRED',
            'statusLabel': '缺少办理人对未领料、未开工事实的原文引用及责任声明；它不替代影响证明'})
    result['executionDeclaration'] = deepcopy(basis)
    if rows:
        verified = native.OperationRequirementService.read(user=user, production_plan_id=plan.pk)
        if not verified['passed'] or verified['resultCount'] != len(rows):
            result['blockers'].append({'code': 'HANDOFF_HISTORICAL_FACT_UNPROVEN',
                'statusLabel': '既有分配完整原生校验未通过', 'details': verified['blockers']})
        result['historicalNativeProofHash'] = digest(verified)
    old_items = list(original.order_engineering_baseline.items.filter(design_item__sales_order_item=old.sales_order_item))
    new_items = list(target_baseline.items.filter(design_item__sales_order_item=new.sales_order_item))
    old_by_design, new_by_design = {r.design_item_id:r for r in old_items}, {r.design_item_id:r for r in new_items}
    if old_by_design.keys() != new_by_design.keys() or len(old_by_design) != len(old_items) or not old_items:
        result['blockers'].append({'code': 'HANDOFF_OBJECT_MAPPING_UNPROVEN', 'statusLabel': '新旧完整对象范围不能一对一证明'})
        return result
    mapping = {old_by_design[k].pk:new_by_design[k].pk for k in old_by_design}
    result['objectMapping'] = [{'designItemId': k, 'originalBaselineItemId': old_by_design[k].pk,
        'targetBaselineItemId': new_by_design[k].pk, 'originalContentHash': old_by_design[k].content_hash,
        'targetContentHash': new_by_design[k].content_hash} for k in sorted(old_by_design)]
    for item in new_items:
        latest = ProductDesignRevision.objects.filter(design_item_id=item.design_item_id).order_by('-revision', '-pk').first()
        if (not latest or latest.pk != item.design_revision_id
            or item.design_item_version != item.design_item.version
            or digest(item.content_snapshot) != item.content_hash):
            result['blockers'].append({'code':'HANDOFF_CURRENT_REVISION_UNPROVEN',
                'statusLabel':'目标基线未固定当前正式设计修订及完整Hash', 'designItemId':item.design_item_id})
    # Every direct source is a real active Fact from each completed main run.
    fact_records = {}
    def facts(calc):
        values = {}
        records = {}
        for fact in EngineeringDerivedFact.objects.filter(calculation=calc, status='active').select_related('source_detail__rule'):
            detail, trace = fact.source_detail, fact.trace or {}
            native._source_output_proof(calc, fact, detail, user.company_id)
            identity = trace.get('designItemId')
            if identity is None:
                identity = next((d for d,r in (old_by_design if calc.pk == old.pk else new_by_design).items()
                    if r.pk == trace.get('baselineItemId')), None)
            key = (fact.canonical_field, identity)
            if identity is None or key in values:
                fail('HANDOFF_SOURCE_MAPPING_UNPROVEN', '真实主核算Fact缺少唯一对象及数量用途身份')
            values[key] = {'ruleId': detail.rule_id, 'ruleVersion':detail.rule_version,
                'specificationHash': digest(detail.rule.specification), 'value':fact.value, 'uomId':fact.uom_id}
            item = (old_by_design if calc.pk == old.pk else new_by_design)[identity]
            records[key] = {'sourceFactId':fact.pk, 'sourceCalculationId':calc.pk, 'sourceDetailId':detail.pk,
                'baselineId':item.baseline_id, 'baselineItemId':item.pk, 'designItemId':identity,
                'sourceAttributeId':item.source_attribute_id, 'sourceRecordId':item.source_record_id}
        fact_records[calc.pk] = records
        return values
    a, b = facts(old), facts(new)
    old_records, new_records = fact_records[old.pk], fact_records[new.pk]
    fact_pairs = {old_records[key]['sourceFactId']:new_records[key]['sourceFactId']
        for key in a.keys() & b.keys() if a[key] == b[key]}
    old_by_fact = {row['sourceFactId']:row for row in old_records.values()}
    new_by_fact = {row['sourceFactId']:row for row in new_records.values()}
    if not a or a != b:
        result['blockers'].append({'code':'HANDOFF_MAIN_DEPENDENCY_CHANGED',
            'statusLabel':'新旧主核算的对象、生产规则、数量或单位不能证明等价；须正式影响评估'})
    result['mainComparison'] = {'originalCalculationId':old.pk, 'targetCalculationId':new.pk,
        'originalFactCount':len(a), 'targetFactCount':len(b), 'equivalent':bool(a) and a == b,
        'originalHash':digest(sorted((str(k),v) for k,v in a.items())),
        'targetHash':digest(sorted((str(k),v) for k,v in b.items()))}
    origins = {r.operation_requirement.source_calculation_id:r.operation_requirement.source_calculation for r in rows}
    for origin in origins.values():
        if origin.pk == old.pk:
            continue
        if origin.scope != 'fact_extension' or origin.origin_calculation_id != old.pk:
            result['blockers'].append({'code':'HANDOFF_EXTENSION_ORIGIN_UNPROVEN',
                'statusLabel':'既有来源不属于固定原主核算及合法扩展', 'calculationId':origin.pk})
            continue
        ids = origin.trace.get('ruleIds', [])
        fresh = EngineeringFactExtensionService.preview(user=user, source_calculation_id=new.pk, rule_ids=ids)['plan']
        previous = origin.trace.get('plan') or {}
        rules = {rule.pk:rule for rule in EngineeringRuleDefinition.objects.filter(pk__in=ids,company_id=user.company_id)}
        def semantic_contexts(contexts, old_identity):
            projected = []
            for c in contexts:
                p = {key:deepcopy(c.get(key)) for key in ('ruleId','ruleVersion','specificationHash','group','inputs','result','uomId','metadata')}
                if old_identity:
                    p = _normalise_identity(p, {original.order_engineering_baseline_id:target_baseline.pk}, mapping)
                if isinstance(c.get('metadata'), dict):
                    # Numeric/text metadata remains business content unless its
                    # exact rule binding declares a formal source identity.
                    p['metadata'] = deepcopy(c['metadata'])
                    for name in c.get('group', {}).keys() & c['metadata'].keys():
                        p['group'][name] = deepcopy(c['group'][name])
                    rule = rules.get(c.get('ruleId'))
                    configurations = (rule.specification.get('factExtension', {}).get('metadataBindings', [])
                        if rule else [])
                    p = _normalise_declared_metadata(c, p, configurations,
                        old_by_fact if old_identity else new_by_fact, new_by_fact,
                        fact_pairs if old_identity else {pk:pk for pk in new_by_fact})
                projected.append(p)
            return sorted(projected, key=digest)
        previous_semantic = semantic_contexts(previous.get('contexts', []), True)
        fresh_semantic = semantic_contexts(fresh['contexts'], False)
        equivalent = bool(previous_semantic) and previous_semantic == fresh_semantic
        result['dependencyComparisons'].append({'originalCalculationId':origin.pk,
            'ruleIds':ids, 'originalHash':digest(previous_semantic), 'targetPreviewHash':digest(fresh_semantic),
            'equivalent':equivalent, 'targetNativePreviewHash':digest(fresh), 'factSource':'server'})
        if not equivalent:
            result['blockers'].append({'code':'HANDOFF_EXTENSION_DEPENDENCY_CHANGED',
                'statusLabel':'既有派生数量、对象分类或规则条件与新主核算只读预览不一致', 'calculationId':origin.pk})
    result['statusLabel'] = '既有负荷保持原历史组合；本次未授予新版本复用资格'
    return result


class PlanStepVersionHandoffService:
    @classmethod
    @transaction.atomic
    def preview(cls, *, user, production_plan_id, root_step_id, manufacturing_output_id=None, target_step_id,
                impact_basis, main_calculation_id=_UNSELECTED):
        _authority(user)
        from .manufacturing_output_generation_service import validate_selected_output
        plan = ProductionPlan.objects.select_related('planning_requirement__demand__sales_order_item__sales_order',
            'planning_requirement__demand__manufacturing_output__routing_version').filter(pk=production_plan_id,
            planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).first()
        if not plan or plan.status != 'confirmed' or plan.planned_qty != plan.planning_requirement.net_required_qty:
            fail('HANDOFF_PLAN_INVALID', '承接计划不存在、未确认或正式净需求数量不一致')
        original = plan.planning_requirement.demand.manufacturing_output
        source_context = None
        if main_calculation_id is not _UNSELECTED:
            if type(main_calculation_id) is not int or main_calculation_id <= 0:
                fail('HANDOFF_SOURCE_SELECTION_INVALID', '必须明确选择有效的已保存正式主核算编号')
            if (not original or manufacturing_output_id is not None
                    and (type(manufacturing_output_id) is not int or manufacturing_output_id != original.pk)):
                fail('HANDOFF_OUTPUT_SCOPE_INVALID', '主核算来源接续必须保留原计划真实制造输出锚点')
            output = original
            source_context = calculation_source(plan, main_calculation_id, user=user)
        else:
            output = ProductManufacturingOutput.objects.select_related('order_engineering_instance', 'routing_version',
                'engineering_calculation', 'order_engineering_baseline').filter(pk=manufacturing_output_id).first()
            if not original or not output or output.pk == original.pk or output.order_engineering_instance_id != original.order_engineering_instance_id:
                fail('HANDOFF_OUTPUT_SCOPE_INVALID', '目标必须是原实例的独立完整新制造发布组合')
        selected = validate_selected_output(output, user=user)
        root = RoutingStep.objects.filter(pk=root_step_id, routing_version_id=original.routing_version_id).first()
        target = RoutingStep.objects.filter(pk=target_step_id, routing_version_id=output.routing_version_id).first()
        if root is None or target is None:
            fail('HANDOFF_STEP_SCOPE_MISMATCH', '原计划步骤或目标发布版本步骤不存在或不属于指定正式范围')
        if source_context is not None and target.applies_to_item_id is not None:
            fail('HANDOFF_SOURCE_BOM_DEPENDENCY_REQUIRED',
                '目标步骤显式依赖BOM组件，必须沿完整制造发布组合办理，不能只承接主核算来源')
        if root_step(root).pk != root_step(target).pk:
            fail('HANDOFF_STEP_MAPPING_INVALID', '目标步骤不属于原计划逻辑步骤的正式继任链')
        mapping = route_mapping(original.routing_version, output.routing_version)
        rows = _allocation_rows(plan)
        _assert_unallocated(rows, root)
        bindings = list(PlanStepVersionBinding.objects.filter(production_plan=plan,root_step=root))
        previous_ids = {row.predecessor_id for row in bindings if row.predecessor_id}
        heads = [row for row in bindings if row.pk not in previous_ids]
        if len(heads) > 1 or bindings and not heads:
            fail('HANDOFF_BINDING_AMBIGUOUS', '步骤承接前驱链没有唯一正式链头')
        previous = heads[0] if heads else None
        if previous and previous.status == 'draft':
            fail('HANDOFF_BINDING_PENDING', '既有承接草稿尚未完成，禁止越过处理')
        if source_context is not None:
            if previous:
                previous_main = binding_proof(previous, user=user)['mainCalculationId']
                predecessors = {p['predecessorCalculationId'] for p in source_context['sourceProof']['continuationProofs']}
                if previous_main not in predecessors:
                    fail('HANDOFF_SOURCE_PREDECESSOR_INVALID', '所选主核算必须正式继任当前步骤已冻结的主核算，禁止回退或重绑同一来源')
            impact = _impact(user,plan,output,rows,impact_basis,
                base=source_context['base'],baseline=source_context['baseline'])
        else:
            impact = _impact(user,plan,output,rows,impact_basis)
        snapshot = {'contractVersion':CONTRACT, 'companyId':user.company_id, 'productionPlanId':plan.pk,
            'planUpdatedAt':plan.updated_at.isoformat(), 'planQuantity':str(plan.planned_qty),
            'originalManufacturingOutputId':original.pk, 'manufacturingOutputId':output.pk,
            'rootStepId':root.pk, 'targetStepId':target.pk, 'predecessorId':previous.pk if previous else None,
            'sourceFields':selected['sourceFields'], 'sourceFingerprint':selected['sourceFingerprint'],
            'stepMapping':mapping, 'stepMappingHash':digest(mapping)}
        if source_context is not None:
            snapshot['sourceSelection'] = deepcopy(source_context['sourceProof'])
        return {'contractVersion':CONTRACT,'factSource':'server','ready':not impact['blockers'],
            'contextHash':digest(snapshot),'impactHash':digest(impact),'sourceSnapshot':snapshot,
            'impactSnapshot':impact,'currentBindingId':previous.pk if previous else None,
            'blockers':impact['blockers'],'businessWriteCount':0,'auditWriteCount':0}

    @classmethod
    @transaction.atomic
    def activate(cls, *, user, production_plan_id, root_step_id, manufacturing_output_id=None, target_step_id,
                 impact_basis, expected_context_hash, expected_impact_hash, predecessor_id=None, idempotency_key,
                 reason, main_calculation_id=_UNSELECTED):
        decisions, chain = _authority(user,write=True)
        if (not isinstance(reason, str) or not reason.strip()
            or not isinstance(idempotency_key, str) or not idempotency_key.strip()):
            fail('HANDOFF_INPUT_REQUIRED','正式承接必须提供原因和幂等键')
        Company.objects.select_for_update().get(pk=user.company_id)
        list(ProductionPlan.objects.select_for_update().filter(pk=production_plan_id))
        list(PlanStepVersionBinding.objects.select_for_update().filter(production_plan_id=production_plan_id,root_step_id=root_step_id))
        source_arguments = {}
        if main_calculation_id is not _UNSELECTED:
            if type(main_calculation_id) is not int or main_calculation_id <= 0:
                fail('HANDOFF_SOURCE_SELECTION_INVALID', '必须明确选择有效的已保存正式主核算编号')
            plan = ProductionPlan.objects.select_related('planning_requirement__demand').filter(pk=production_plan_id,
                planning_requirement__demand__sales_order_item__sales_order__company_id=user.company_id).first()
            anchor_id = plan.planning_requirement.demand.manufacturing_output_id if plan else None
            if (not anchor_id or manufacturing_output_id is not None
                    and (type(manufacturing_output_id) is not int or manufacturing_output_id != anchor_id)):
                fail('HANDOFF_OUTPUT_SCOPE_INVALID', '主核算来源接续必须保留原计划真实制造输出锚点')
            manufacturing_output_id = anchor_id
            source_arguments['main_calculation_id'] = main_calculation_id
        request_body = {'companyId':user.company_id,'actorId':user.pk,'productionPlanId':production_plan_id,
            'rootStepId':root_step_id,'outputId':manufacturing_output_id,'targetStepId':target_step_id,
            'predecessorId':predecessor_id,'contextHash':expected_context_hash,'impactHash':expected_impact_hash,
            'impactBasis':impact_basis,'reason':reason}
        if source_arguments:
            request_body['mainCalculationId'] = main_calculation_id
        request_hash = digest(request_body)
        ledger = MasterDataWriteRequest.objects.select_for_update().filter(organization_id=user.company_id,
            action_code=ACTIVATE,idempotency_key=idempotency_key).first()
        if ledger:
            if ledger.request_hash != request_hash:
                fail('IDEMPOTENCY_CONFLICT','同一幂等键已绑定其他承接内容')
            if ledger.status == 'COMMITTED':
                row = PlanStepVersionBinding.objects.get(pk=ledger.result['bindingId'])
                binding_proof(row,user=user)
                return {**ledger.result,'idempotentReplay':True,'businessWriteCount':0,'auditWriteCount':0}
        fresh = cls.preview(user=user,production_plan_id=production_plan_id,root_step_id=root_step_id,
            manufacturing_output_id=manufacturing_output_id,target_step_id=target_step_id,impact_basis=impact_basis,
            **source_arguments)
        if not fresh['ready']:
            fail('HANDOFF_IMPACT_UNPROVEN','新工程版本的完整影响证明未通过',blockers=fresh['blockers'])
        if (fresh['contextHash'] != expected_context_hash or fresh['impactHash'] != expected_impact_hash
            or fresh['currentBindingId'] != predecessor_id):
            fail('HANDOFF_CANDIDATE_STALE','承接来源、影响或前驱已变化，请重新读取')
        identity,_ = ExternalIdentity.objects.get_or_create(organization_id=user.company_id,source_system='PCE',
            source_type='PLAN_STEP_ENGINEERING_VERSION',source_object_type=OBJECT,
            external_id=f'{production_plan_id}:{root_step_id}:{expected_context_hash}',defaults={
                'target_entity_type':OBJECT,'mapping_status':'REVIEW','source_fingerprint':expected_context_hash})
        ledger = ledger or MasterDataWriteRequest.objects.create(organization_id=user.company_id,action_code=ACTIVATE,
            entity_type=OBJECT,idempotency_key=idempotency_key,request_hash=request_hash,source_identity=identity,
            audit_metadata={'request':request_body,'executionChain':chain,'executionDeclarationIsHumanFact':True})
        previous = PlanStepVersionBinding.objects.get(pk=predecessor_id) if predecessor_id else None
        row = create_business_object_with_initial_state(model=PlanStepVersionBinding,initial_state='draft',
            company_id=user.company_id,production_plan_id=production_plan_id,root_step_id=root_step_id,
            target_step_id=target_step_id,manufacturing_output_id=manufacturing_output_id,predecessor=previous,
            revision=previous.revision+1 if previous else 1,context_hash=fresh['contextHash'],impact_hash=fresh['impactHash'],
            source_snapshot=fresh['sourceSnapshot'],impact_snapshot=fresh['impactSnapshot'],write_request=ledger,created_by=user,reason=reason)
        initial_audit = OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id,action_code=ACTIVATE,
            actor=user,target_type=OBJECT,target_id=row.pk,target_label=f'步骤版本绑定{row.pk}初始化',
            reason=reason,before_snapshot={},after_snapshot={'status':'draft','contextHash':row.context_hash,
                'impactHash':row.impact_hash,'writeRequestId':ledger.pk,'authorization':decisions,'executionChain':chain})
        initial_transition = record_projected_business_transition(object_type=OBJECT,object_id=row.pk,
            source_state='',target_state='draft',action_code=ACTIVATE,operator=user,reason=reason,
            audit_reference=f'OrganizationOperatingAuditRecord:{initial_audit.pk}',allowed_transitions={('', 'draft')})
        audit = OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id,action_code=ACTIVATE,
            actor=user,target_type=OBJECT,target_id=row.pk,target_label=f'计划{production_plan_id}步骤{root_step_id}工程承接',
            reason=reason,before_snapshot={'predecessorId':predecessor_id},after_snapshot={
                'contextHash':row.context_hash,'impactHash':row.impact_hash,'sourceSnapshot':row.source_snapshot,
                'impactSnapshot':row.impact_snapshot,'authorization':decisions,'executionChain':chain})
        row.audit_record=audit;row._binding_write_authorized=True;row.save(update_fields=['audit_record'])
        reference=f'OrganizationOperatingAuditRecord:{audit.pk}'
        if previous and previous.status == 'active':
            supersede_audit = OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id,action_code=ACTIVATE,
                actor=user,target_type=OBJECT,target_id=previous.pk,target_label=f'步骤版本绑定{previous.pk}继任',
                reason=reason,before_snapshot={'status':'active','contextHash':previous.context_hash},
                after_snapshot={'status':'superseded','successorBindingId':row.pk,'contextHash':previous.context_hash,
                    'writeRequestId':ledger.pk,'authorization':decisions,'executionChain':chain})
            transition_business_object(business_object=previous,object_type=OBJECT,source_state='active',target_state='superseded',
                action_code=ACTIVATE,operator=user,reason=reason,
                audit_reference=f'OrganizationOperatingAuditRecord:{supersede_audit.pk}',allowed_transitions={('active','superseded')})
        transition_business_object(business_object=row,object_type=OBJECT,source_state='draft',target_state='active',
            action_code=ACTIVATE,operator=user,reason=reason,audit_reference=reference,allowed_transitions={('draft','active')})
        result={'bindingId':row.pk,'contextHash':row.context_hash,'impactHash':row.impact_hash,
            'statusLabel':'新工程版本已正式承接','auditId':audit.pk,'writeRequestId':ledger.pk,
            'initializationAuditId':initial_audit.pk,'initializationTransitionId':initial_transition.pk,
            'idempotentReplay':False,'businessWriteCount':1,'auditWriteCount':3 if previous else 2,
            'productionPlanWriteCount':0}
        ledger.status='COMMITTED';ledger.target_entity_id=str(row.pk);ledger.result=result
        ledger.save(update_fields=['status','target_entity_id','result','updated_at'])
        binding_proof(row,user=user)
        return result

