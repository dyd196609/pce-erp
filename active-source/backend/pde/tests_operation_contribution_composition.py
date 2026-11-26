"""SIMULATED_FOR_TEST: audited non-executable composition over real native EORs.

Only the reviewed two-file isolated runner may import this module. Sources are
created while their main calculation is running; no successful proof is mocked.
"""
from copy import deepcopy
from decimal import Decimal
import os
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from system.models import Company, OrganizationOperatingAuditRecord, Permission, Process, RolePermission
from masterdata.models import UnitOfMeasure
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as native
from . import operation_workload_source_service as sources
from . import tests_calc4_routing_correction as correction
from . import tests_classified_fact_eor as classified
from . import tests_plan_legal_extension_admission as legal
from . import tests_engineering_fact_extension as extension_fixture
from .engineering_fact_extension_service import EngineeringFactExtensionService, CONTRACT as EXTENSION_CONTRACT
from .engineering_rule_foundation import EngineeringRuleError, evaluate_specification, specification_hash
from .manufacturing_configuration_service import ManufacturingConfigurationService, CREATE, RELEASE
from .manufacturing_rule_configuration import CONTRACT as MANUFACTURING_CONTRACT
from .operation_contribution_composition import (OperationContributionCompositionError,
    composition_for_requirement, validate_composition_specification)
from .models import (EngineeringCalculationDetail, EngineeringCalculationRecord, EngineeringDerivedFact,
    EngineeringOperationRequirement, EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation, WorkCenter)

if os.environ.get('PCE_CONTRIBUTION_COMPOSITION_ISOLATED_TESTS') != '1':
    raise RuntimeError('Composition tests require the reviewed named isolated runner')
_allowed = {Path(os.environ[k]).resolve() for k in ('PCE_DATABASE_PATH','PCE_ISOLATED_TEST_DATABASE')}
if Path(settings.DATABASES['default']['NAME']).resolve() not in _allowed:
    raise RuntimeError('Composition tests are outside the exact isolated database allowlist')

ROLE = 'OPERATION_ALLOCATION_COMPOSITION'
CONTRACT = 'PCE-OPERATION-ALLOCATION-COMPOSITION-V1'


class OperationContributionCompositionTests(TestCase):
    def setUp(self):
        class Fixture(correction.Calc4RoutingCorrectionTests):
            def advance(inner, obj, target, *, status_field='status'):
                if isinstance(obj,EngineeringCalculationRecord) and obj.scope == 'order_engineering' and target == 'completed':
                    classified.ClassifiedFactEorTests.finish_source_hashes(inner,obj,list(obj.derived_facts.order_by('sequence','pk')))
                return super().advance(obj,target,status_field=status_field)

            def leaf(inner, producer, canonical, value, sequence, object_index):
                item = inner.baseline_items[object_index]
                detail = inner.initial(EngineeringCalculationDetail,'running',calculation=inner.source_calc,
                    sequence=sequence,rule=producer,rule_code=producer.rule_code,rule_version=producer.version,
                    expression_snapshot=producer.specification['expression'],
                    input_snapshot={f'raw_{canonical}':str(value),'object':deepcopy(inner.source_calc.trace['objectInputSnapshot'][object_index]['input'])},
                    dependency_snapshot=[],output_name=canonical,output_value={'decimal':str(value)},uom=inner.area,
                    precision=18,rounding='ROUND_HALF_UP',started_at=timezone.now(),finished_at=timezone.now())
                inner.advance(detail,'succeeded')
                return inner.initial(EngineeringDerivedFact,'active',calculation=inner.source_calc,rule=producer,
                    source_detail=detail,fact_code=canonical,canonical_field=canonical,sequence=sequence,
                    value={'decimal':str(value)},value_type='decimal',source_type='ENGINEERING_DERIVED',uom=inner.area,
                    source_path=f'SIMULATED_FOR_TEST.component[{sequence}]',trace=dict(sourceKind='SIMULATED_FOR_TEST',
                        resultDomain='DERIVED_FACT',detailId=detail.pk,ruleCode=producer.rule_code,ruleVersion=producer.version,
                        specificationHash=specification_hash(producer.specification),baselineId=inner.baseline.pk,
                        baselineItemId=item.pk,designItemId=item.design_item_id,sourceAttributeId=item.source_attribute_id,
                        baselineContentHash=item.content_hash,ProductPaintingProcessCode='SIM-FULL/CTX'))

            def make_fact(inner,value,sequence):
                primary = super().make_fact(value,sequence)
                if not hasattr(inner,'component_producer'):
                    inner.component_producer = inner.make_rule(inner.op_area,inner.area,'opaque_component_b',output_domain='DERIVED_FACT')
                    inner.component_b_facts = []
                inner.component_b_facts.append(inner.leaf(inner.component_producer,'opaque_component_b',
                    Decimal(value)*Decimal(2),100+sequence,sequence-1))
                if sequence == 1:
                    # A second real leaf for the same object and same component
                    # must not become a second contribution merely by a new ID.
                    inner.component_a_alias = inner.leaf(inner.producer,'opaque_area',value,201,0)
                return primary

        self.f = Fixture(methodName='runTest')
        self.f.setUp()
        f = self.f
        for code in (native.PLAN_VIEW,CREATE,RELEASE):
            permission,_ = Permission.objects.get_or_create(code=code,defaults={'name':code,'module':'PRODUCTION'})
            RolePermission.objects.get_or_create(role=f.role,permission=permission)
        plan_fixture = legal.PlanLegalExtensionAdmissionTests(methodName='runTest')
        plan_fixture.f = f
        self.plan = plan_fixture.make_plan()
        self.rule_a = self.member_rule(f.facts[0],'COMPONENT_A')
        self.rule_b = self.member_rule(f.component_b_facts[0],'COMPONENT_B')
        self.req_a = self.generate(f.facts[0],self.rule_a)
        self.req_b = self.generate(f.component_b_facts[0],self.rule_b)
        self.serial = 0

    def member_rule(self,fact,component,*,center=None,capacity=None):
        f = self.f
        rule = f.make_mapping(fact,f.op_area,f.area,mode=f.mode,capacity=capacity or f.capacity,
            manufacturing_overrides={'workCenterId':(center or f.center).pk},dynamic_source_basis=True,release=False)
        spec = deepcopy(rule.specification)
        spec['rulePackage'] = {'code':'SIM-COMMON-WORKLOAD','version':'V1'}
        spec['inputs'][0]['canonicalName'] = 'component_quantity'
        spec['expression'] = 'component_quantity'
        spec['outputs'][0]['canonicalName'] = 'formal_operation_workload'
        spec['applicability']['sourceSemantic'] = component
        spec['manufacturing']['routingContext'] = dict(contractVersion=correction.ROUTE_CONTRACT,
            routingId=f.route.pk,routingVersionId=f.version.pk,routingStepId=f.step.pk)
        spec['sourceEvidence']['formalRouting'] = f.route_evidence(f.version,f.step)
        if fact.calculation_id != f.source_calc.pk:
            spec['manufacturing']['sourceSelector']['traceEquals'] = {'contractVersion':EXTENSION_CONTRACT}
        rule.specification = spec
        rule.save(update_fields=('specification',))
        f.advance(rule,'reviewed');f.advance(rule,'released')
        return rule

    def generate(self,fact,rule):
        value = native.OperationRequirementService.generate(user=self.f.user,source_calculation_id=fact.calculation_id,
            source_fact_id=fact.pk,rule_id=rule.pk,idempotency_key=f'sim-composition-eor-{fact.pk}-{rule.pk}',reason='SIMULATED_FOR_TEST')
        return EngineeringOperationRequirement.objects.get(pk=value['operationRequirementId'])

    def declaration_spec(self,rules=None):
        f = self.f
        return dict(ruleRole=ROLE,rulePackage={'code':'SIM-COMPOSITION','version':'V1'},
            sourceEvidence={'reference':'SIMULATED_FOR_TEST: formally declared sum of independent measured components'},
            allocationComposition=dict(contractVersion=CONTRACT,operator='SUM',quantityPurpose='formal_operation_workload',
                memberRules=[dict(ruleCode=r.rule_code,ruleVersion=r.version,specificationHash=specification_hash(r.specification),
                    componentCode=r.specification['applicability']['sourceSemantic']) for r in (rules or [self.rule_a,self.rule_b])],
                resourceScope=dict(companyId=f.company.pk,productTypeId=f.product_type.pk,operationId=f.op_area.pk,
                    manufacturingModeId=f.mode.pk,workCenterId=f.center.pk,standardCapacityId=f.capacity.pk,uomId=f.area.pk,
                    quantityBasis='SOURCE_SCOPE_TOTAL',basisUomId=f.pcs.pk),allowSameObjectAcrossComponents=True,inputOverlap='FORBID'))

    def configure(self,spec=None,*,code='SIM-COMPOSITION'):
        spec = deepcopy(spec or self.declaration_spec())
        spec['rulePackage']['code'] = code
        value = ManufacturingConfigurationService.configure(user=self.f.user,reason='SIMULATED_FOR_TEST',package={
            'contractVersion':MANUFACTURING_CONTRACT,'companyId':self.f.company.pk,'modes':[],
            'rules':[dict(ruleCode=code,ruleName='SIMULATED_FOR_TEST non-executable composition',version=spec['rulePackage']['version'],
                ruleKind='decision',specification=spec)]})
        return EngineeringRuleDefinition.objects.get(pk=value['rules'][0]['id'])

    def contributions(self,requirements=None):
        return [dict(operationRequirementId=req.pk,routingStepId=self.f.step.pk,
            idempotencyKey=f'sim-composition-allocation-{req.pk}') for req in (requirements or [self.req_a,self.req_b])]

    def preview(self,requirements=None):
        return native.OperationRequirementService.allocation_group_readiness(user=self.f.user,
            production_plan_id=self.plan.pk,contributions=self.contributions(requirements))

    def save_group(self,requirements=None):
        return native.OperationRequirementService.allocate_group(user=self.f.user,production_plan_id=self.plan.pk,
            contributions=self.contributions(requirements),reason='SIMULATED_FOR_TEST')

    def reject_group(self,requirements=None):
        before = self.f.full_database_snapshot()
        try:
            preview = self.preview(requirements)
        except native.OperationRequirementError as error:
            code = error.code
        else:
            self.assertFalse(preview['canSave'],preview)
            self.assertEqual(preview['businessWriteCount'],0)
            self.assertEqual(preview['auditWriteCount'],0)
            code = preview['blockers'][0]['code']
        with self.assertRaises(native.OperationRequirementError) as caught:
            self.save_group(requirements)
        self.assertEqual(caught.exception.code,code)
        self.assertEqual(self.f.full_database_snapshot(),before)

    def test_configure_publishes_exactly_three_authoritative_audits_and_transitions(self):
        before = OrganizationOperatingAuditRecord.objects.count()
        declaration = self.configure()
        self.assertEqual(declaration.status,'released')
        self.assertEqual(declaration.rule_kind,'decision')
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count()-before,3)
        audits = list(OrganizationOperatingAuditRecord.objects.filter(target_type='EngineeringRuleDefinition',
            target_id=declaration.pk).order_by('pk'))
        self.assertEqual(len(audits),3)
        self.assertTrue(all(a.actor_id == self.f.user.pk and a.organization_id == self.f.company.pk for a in audits))
        states = list(BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition',
            object_id=declaration.pk).order_by('version'))
        self.assertEqual([(s.source_state,s.target_state) for s in states],[('','draft'),('draft','reviewed'),('reviewed','released')])
        self.assertEqual({int(s.audit_reference.rsplit(':',1)[1]) for s in states},{a.pk for a in audits})
        with transaction.atomic():
            proof = composition_for_requirement(self.req_a,self.f.company.pk)
        self.assertEqual(proof['declarationId'],declaration.pk)
        self.assertEqual(proof['componentCode'],'COMPONENT_A')
        self.assertTrue(proof['auditProof'])

    def test_same_object_distinct_real_leaf_components_save_and_read_native_quantity_once(self):
        self.configure()
        before = self.f.full_database_snapshot()
        ready = self.preview()
        self.assertTrue(ready['canSave'],ready)
        self.assertEqual(self.f.full_database_snapshot(),before)
        target = next(s for s in ready['steps'] if s['routingStepId'] == self.f.step.pk)
        self.assertEqual(Decimal(target['allocatedQuantity']),Decimal('4.5'))
        saved = self.save_group()
        self.assertEqual((saved['businessWriteCount'],saved['auditWriteCount']),(2,2))
        read = native.OperationRequirementService.read(user=self.f.user,production_plan_id=self.plan.pk)
        self.assertTrue(read['passed'],read)
        self.assertEqual({r['operationRequirementId'] for r in read['allocations']},{self.req_a.pk,self.req_b.pk})
        demand = native.process_demand_for_plan(self.plan,self.f.output,self.f.item,
            {'stepId':self.f.step.pk,'operationId':self.f.op_area.pk},company_id=self.f.company.pk,user=self.f.user)
        self.assertEqual(demand['quantity'],Decimal('4.5'))
        self.assertEqual(native._scope_budget(self.req_a,self.f.company.pk),{self.plan.pk:Decimal(37)})
        snapshot = self.f.full_database_snapshot()
        replay = self.save_group()
        self.assertTrue(replay['idempotent'])
        self.assertEqual((replay['businessWriteCount'],replay['auditWriteCount']),(0,0))
        self.assertEqual(self.f.full_database_snapshot(),snapshot)

    def test_matching_package_output_alias_without_explicit_declaration_still_blocks(self):
        self.reject_group()

    def test_same_component_new_leaf_and_new_eor_cannot_repeat_the_same_object(self):
        self.configure()
        alias = self.generate(self.f.component_a_alias,self.rule_a)
        self.assertNotEqual(alias.source_fact_id,self.req_a.source_fact_id)
        self.reject_group([self.req_a,alias])

    def test_same_source_leaf_cannot_be_declared_twice_as_total_plus_part(self):
        duplicate_rule = self.member_rule(self.f.facts[0],'COMPONENT_B')
        duplicate = self.generate(self.f.facts[0],duplicate_rule)
        self.configure(self.declaration_spec([self.rule_a,duplicate_rule]))
        self.assertEqual(duplicate.source_fact_id,self.req_a.source_fact_id)
        self.reject_group([self.req_a,duplicate])

    def test_ancestor_and_real_derived_fact_overlap_remains_rejected(self):
        f = self.f
        names = ('baselineId','baselineItemId','designItemId','sourceAttributeId')
        config = dict(strategy='GROUP_SUM',groupKeys=list(names),metadataBindings=[
            dict(name=k,sourceType='FORMAL_SOURCE_IDENTITY',valueField=k) for k in names],bindings=[
            extension_fixture.EngineeringFactExtensionTests.binding(f,'a','opaque_area',f.producer,f.area,f.area)])
        spec = extension_fixture.EngineeringFactExtensionTests.spec(f,[dict(canonicalName='a',valueType='decimal',
            unit=f.area.code,unitDimension='area',sourceType='AGGREGATED',required=True,unitRequired=True)],'opaque_derived_component','a',config)
        rules = EngineeringFactExtensionService.configure(user=f.user,reason='SIMULATED_FOR_TEST',package=dict(
            contractVersion=EXTENSION_CONTRACT,companyId=f.company.pk,rules=[dict(ruleCode='SIM-COMPOSITION-DERIVED',
                ruleName='SIMULATED_FOR_TEST ancestor overlap',version='V1',specification=spec)]))['ruleIds']
        value = EngineeringFactExtensionService.derive(user=f.user,source_calculation_id=f.source_calc.pk,
            rule_ids=rules,idempotency_key='sim-composition-derived',reason='SIMULATED_FOR_TEST')
        source_identity = self.req_a.source_fact.trace
        matches = []
        for candidate in EngineeringDerivedFact.objects.filter(calculation_id=value['calculationId']).order_by('pk'):
            identity = candidate.trace.get('group') or candidate.trace
            if (identity.get('baselineItemId') == source_identity['baselineItemId']
                    and identity.get('designItemId') == source_identity['designItemId']):
                matches.append(candidate)
        self.assertEqual(len(matches),1,'The real derived fact must cover the same exact formal object as its ancestor')
        fact = matches[0]
        rule = self.member_rule(fact,'COMPONENT_B')
        req = self.generate(fact,rule)
        self.configure(self.declaration_spec([self.rule_a,rule]))
        with transaction.atomic():
            cache = native._source_read_cache(f.user,None)
            identities = []
            for requirement in (self.req_a,req):
                context = native._validate_requirement(requirement,f.company.pk,read_cache=cache,user=f.user)
                proof = native._plan_source_consistency(f.company.pk,self.plan,requirement,
                    native_context=context,routing_step=f.step,read_cache=cache)
                identities.append(native._contribution_identity(dict(req=requirement,plan=self.plan,sourceProof=proof),
                    f.company.pk,cache))
            self.assertEqual(identities[0]['baselineItemIds'],identities[1]['baselineItemIds'])
            self.assertEqual(identities[0]['designItemIds'],identities[1]['designItemIds'])
            overlap = identities[0]['inputFactIds'] & identities[1]['inputFactIds']
            self.assertIn(self.req_a.source_fact_id,overlap,'This fixture must prove actual ancestor/input reuse')
        self.reject_group([self.req_a,req])

    def test_wrong_member_hash_is_not_a_formal_composition(self):
        spec = self.declaration_spec()
        spec['allocationComposition']['memberRules'][0]['specificationHash'] = '0'*64
        before = self.f.full_database_snapshot()
        with self.assertRaises((OperationContributionCompositionError,native.OperationRequirementError)):
            self.configure(spec)
        self.assertEqual(self.f.full_database_snapshot(),before)

    def test_two_current_declarations_for_the_same_members_are_ambiguous(self):
        self.configure()
        self.configure(code='SIM-COMPOSITION-SECOND')
        self.reject_group()

    def test_scope_unit_basis_and_resource_contract_conflicts_are_rejected(self):
        f = self.f
        center = WorkCenter.objects.create(company=f.company,workshop=f.workshop,department=f.department,
            code='SIM-COMPOSITION-OTHER-CENTER',name='SIMULATED_FOR_TEST resource')
        operation = Process.objects.create(company=f.company,code='SIM-COMPOSITION-OTHER-OP',
            name='SIMULATED_FOR_TEST operation',calculation_basis='area',calculation_uom=f.area)
        foreign = Company.objects.create(code='SIM-COMPOSITION-FOREIGN',name='SIMULATED_FOR_TEST foreign')
        for field,value in (('companyId',foreign.pk),('operationId',operation.pk),('workCenterId',center.pk),
                ('uomId',f.pcs.pk),('quantityBasis','PER_BASIS_QUANTITY')):
            with self.subTest(field=field):
                spec = self.declaration_spec();spec['allocationComposition']['resourceScope'][field] = value
                before = self.f.full_database_snapshot()
                with self.assertRaises((OperationContributionCompositionError,native.OperationRequirementError)):
                    self.configure(spec,code='SIM-COMPOSITION-CONFLICT-'+field)
                self.assertEqual(self.f.full_database_snapshot(),before)

    def test_other_valid_dynamic_basis_declaration_does_not_match_current_requirements(self):
        spec = self.declaration_spec()
        spec['allocationComposition']['resourceScope']['basisUomId'] = self.f.area.pk
        declaration = self.configure(spec)
        self.assertEqual(declaration.status,'released')
        before = self.f.full_database_snapshot()
        with transaction.atomic():
            self.assertIsNone(composition_for_requirement(self.req_a,self.f.company.pk))
            self.assertIsNone(composition_for_requirement(self.req_b,self.f.company.pk))
        self.assertEqual(self.f.full_database_snapshot(),before)
        self.reject_group()

    def test_non_executable_declaration_is_not_a_source_producer_or_eor_candidate(self):
        declaration = self.configure()
        with self.assertRaises(EngineeringRuleError):
            evaluate_specification(declaration.specification,{})
        self.assertIsNone(sources._numeric_producer(declaration,list(UnitOfMeasure.objects.filter(company_id=self.f.company.pk))))
        projection = sources.operation_source_configuration(self.f.op_area,self.f.product_type.pk,
            routing_context=dict(routingId=self.f.route.pk,routingVersionId=self.f.version.pk,routingStepId=self.f.step.pk))
        self.assertNotIn(declaration.pk,{r['ruleId'] for r in projection['sources']})
        self.assertNotIn(declaration.pk,{r.get('ruleId') for r in projection['blockers']})

    def test_old_normal_snapshot_and_original_key_survive_declaration_publication(self):
        saved = self.save_group([self.req_a])
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=saved['allocations'][0]['allocationId'])
        original = dict(snapshot=deepcopy(row.source_snapshot),inputHash=row.input_hash,auditId=row.audit_record_id)
        self.configure()
        before = self.f.full_database_snapshot()
        read = native.OperationRequirementService.read(user=self.f.user,production_plan_id=self.plan.pk)
        self.assertTrue(read['passed'],read)
        replay = self.save_group([self.req_a])
        self.assertEqual((replay['businessWriteCount'],replay['auditWriteCount']),(0,0))
        row.refresh_from_db()
        self.assertEqual(dict(snapshot=row.source_snapshot,inputHash=row.input_hash,auditId=row.audit_record_id),original)
        self.assertEqual(self.f.full_database_snapshot(),before)

    def test_missing_publication_audit_proof_cannot_grant_composition(self):
        declaration = self.configure()
        audit = OrganizationOperatingAuditRecord.objects.filter(target_type='EngineeringRuleDefinition',
            target_id=declaration.pk).order_by('pk').last()
        legal.PlanLegalExtensionAdmissionTests.raw(self,audit,'after_snapshot',{})
        self.reject_group()

    def test_typed_contract_rejects_unknown_fields_boolean_ids_and_duplicate_components(self):
        for edit in (lambda s:s.update(unrecognized=True),
                lambda s:s['allocationComposition']['resourceScope'].update(operationId=True),
                lambda s:s['allocationComposition']['memberRules'][1].update(componentCode='COMPONENT_A'),
                lambda s:s['allocationComposition'].update(inputOverlap='ALLOW'),
                lambda s:s['allocationComposition'].update(allowSameObjectAcrossComponents=False)):
            with self.subTest(edit=edit):
                spec = self.declaration_spec();edit(spec)
                with self.assertRaises(OperationContributionCompositionError):
                    validate_composition_specification(spec)
