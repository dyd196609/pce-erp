"""Isolated binding capability tests, never a formal business admission.

The established output fixture stubs two upstream document proofs. Native
output generation/release, routing successor, permissions, binding ledger,
audit/state and transaction are exercised. Positive binding transaction tests
stub the separate impact assessment explicitly; a real assessment without
source facts is required to block. No fixture is a certificate for old loads.
"""
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import Demand, PlanningRequirement, ProductionPlan
from system.models import OrganizationOperatingAuditRecord, Permission, RolePermission, UserRoleScopeAssignment
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import EngineeringDocumentVersion, PlanStepVersionBinding, RoutingStep, RoutingVersion
from .plan_step_context_service import (CONTRACT, PlanStepContextError, binding_proof, digest,
    resolve_step_context, root_step, route_mapping, version_fact)
from .plan_step_version_handoff_service import ACTIVATE, PlanStepVersionHandoffService as Service
from .routing_version_successor_service import RoutingVersionSuccessorService
from . import tests_engineering_version_handoff_upstream as upstream_fixture
from .tests_manufacturing_output_generation import SCOPE
from . import tests_plan_legal_extension_admission as legal_fixture
from . import tests_classified_fact_eor as classified_fixture


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class PlanStepVersionHandoffTests(TestCase):
    _generate = upstream_fixture.EngineeringVersionHandoffUpstreamTests._generate
    _release = upstream_fixture.EngineeringVersionHandoffUpstreamTests._release
    _successor_sources = upstream_fixture.EngineeringVersionHandoffUpstreamTests._successor_sources

    def setUp(self):
        upstream_fixture.EngineeringVersionHandoffUpstreamTests.setUp(self)
        for code in ('production.engineering.calculation.view', 'production.engineering.calculation.execute',
                     'planning.view', 'production.master_data.routing.maintain'):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={'name':code, 'module':'PDE'})
            RolePermission.objects.get_or_create(role=self.executing_role, permission=permission)
        self.original, _ = self._generate()
        self._release(self.original, 'binding-root-release')
        self.old_step = self.original.routing_version.steps.get()
        baseline, calculation, bom, route, _ = self._successor_sources()
        document = EngineeringDocumentVersion.objects.create(document=self.order_document,
            document_name='隔离精确继任资料', document_version='HANDOFF-BINDING',
            release_subject_type='ORDER_ENGINEERED_PRODUCT', order_engineering_instance=self.instance,
            order_engineering_baseline=baseline, engineering_calculation=calculation,
            related_bom=bom, related_routing=route)
        EngineeringDocumentVersion.objects.filter(pk=document.pk).update(status='released')
        document.refresh_from_db()
        self.successor, _ = self._generate(document, self.original, 'binding-successor-output')
        self._release(self.successor, 'binding-successor-release')
        self.target = route.steps.get()
        demand = create_business_object_with_initial_state(model=Demand, initial_state='draft',
            demand_no='BINDING-DEMAND', source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(self.order.pk), source_document_no=self.order.order_no,
            sales_order_item=self.order_item, manufacturing_output=self.original, material=self.finished,
            required_qty=1, required_date=date.today(), department=self.department,
            reason='隔离固定计划来源', created_by=self.executor)
        requirement = PlanningRequirement.objects.create(requirement_no='BINDING-REQUIREMENT',
            demand=demand, material=self.finished, demand_qty=1, available_qty=0, net_required_qty=1,
            required_date=date.today(), supply_type='production', status='confirmed', created_by=self.executor)
        self.plan = ProductionPlan.objects.create(plan_no='BINDING-PLAN', planning_requirement=requirement,
            material=self.finished, planned_qty=1, required_date=date.today(), source_id=str(requirement.pk),
            confirmed_by=self.executor, status='confirmed')
        self.basis = {'executionFactReference':'isolated human declaration', 'executionStatement':'均未领料、未开工',
            'allMaterialUnissued':True, 'allWorkUnstarted':True}

    def arguments(self):
        return {'user':self.executor, 'production_plan_id':self.plan.pk, 'root_step_id':self.old_step.pk,
            'manufacturing_output_id':self.successor.pk, 'target_step_id':self.target.pk, 'impact_basis':deepcopy(self.basis)}

    def impact(self, *args, **kwargs):
        return {'contractVersion':CONTRACT, 'historicalAllocationCount':0, 'preservedAllocations':[],
            'newVersionReusedAllocationIds':[], 'historicalRowsGrantedFutureExecution':False,
            'blockers':[], 'executionDeclaration':deepcopy(self.basis)}

    def activate(self, **overrides):
        candidate = Service.preview(**self.arguments())
        return Service.activate(**self.arguments(), expected_context_hash=candidate['contextHash'],
            expected_impact_hash=candidate['impactHash'], predecessor_id=candidate['currentBindingId'],
            **{'idempotency_key':'binding-activate', 'reason':'隔离明确新版本承接', **overrides})

    def counts(self):
        return tuple(model.objects.count() for model in (PlanStepVersionBinding, MasterDataWriteRequest,
            ExternalIdentity, OrganizationOperatingAuditRecord, BusinessStateTransition))

    def test_real_impact_does_not_accept_no_start_declaration_as_source_proof(self):
        before = self.counts()
        with self.assertRaises(PlanStepContextError) as caught:
            Service.preview(**self.arguments())
        self.assertEqual(caught.exception.code, 'HANDOFF_SOURCE_MAPPING_UNPROVEN')
        self.assertEqual(before, self.counts())

    def test_binding_native_transaction_and_frozen_plan_identity(self):
        before = ProductionPlan.objects.filter(pk=self.plan.pk).values().get()
        demand_before = Demand.objects.filter(pk=self.plan.planning_requirement.demand_id).values().get()
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            result = self.activate()
        row = PlanStepVersionBinding.objects.get(pk=result['bindingId'])
        self.assertEqual(row.status, 'active')
        self.assertEqual(binding_proof(row)['effectiveRoutingStepId'], self.target.pk)
        context = resolve_step_context(self.plan, self.old_step.pk, user=self.executor)
        self.assertEqual(context['output'].pk, self.successor.pk)
        self.assertEqual(context['root_step'].pk, self.old_step.pk)
        self.assertEqual(version_fact(context)['effectiveRoutingVersionId'], self.target.routing_version_id)
        historical = resolve_step_context(self.plan, self.old_step.pk, historical=True)
        self.assertEqual(historical['output'].pk, self.original.pk)
        self.assertEqual(before, ProductionPlan.objects.filter(pk=self.plan.pk).values().get())
        self.assertEqual(demand_before, Demand.objects.filter(pk=self.plan.planning_requirement.demand_id).values().get())
        self.assertEqual(BusinessStateTransition.objects.filter(object_type='PlanStepVersionBinding', object_id=row.pk).count(), 2)

    def test_replay_is_zero_write_and_conflicting_key_cannot_change_binding(self):
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            candidate = Service.preview(**self.arguments())
            args = {**self.arguments(), 'expected_context_hash':candidate['contextHash'],
                'expected_impact_hash':candidate['impactHash'], 'idempotency_key':'same-key', 'reason':'同一事实'}
            first = Service.activate(**args)
            before = self.counts()
            replay = Service.activate(**args)
            self.assertTrue(replay['idempotentReplay'])
            self.assertEqual((replay['businessWriteCount'], replay['auditWriteCount']), (0,0))
            self.assertEqual(first['bindingId'], replay['bindingId'])
            self.assertEqual(before, self.counts())
            with self.assertRaises(PlanStepContextError):
                Service.activate(**{**args, 'reason':'改变载荷'})
            self.assertEqual(before, self.counts())

    def test_late_state_failure_rolls_back_binding_request_identity_and_audit(self):
        before = self.counts()
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact), patch(
            'pde.plan_step_version_handoff_service.transition_business_object', side_effect=RuntimeError('isolated fault')):
            with self.assertRaises(RuntimeError):
                self.activate()
        self.assertEqual(before, self.counts())

    def test_missing_reason_key_and_wrong_step_are_typed_failures(self):
        before = self.counts()
        for values in ({'idempotency_key':None}, {'reason':None}, {'reason':'  '}, {'idempotency_key':''}):
            with self.subTest(values=values), self.assertRaises(PlanStepContextError) as caught:
                Service.activate(**self.arguments(), expected_context_hash='x', expected_impact_hash='y',
                    **{'reason':'required', 'idempotency_key':'required', **values})
            self.assertEqual(caught.exception.code, 'HANDOFF_INPUT_REQUIRED')
        for key in ('root_step_id', 'target_step_id'):
            with self.assertRaises(PlanStepContextError) as caught:
                Service.preview(**{**self.arguments(), key:999999})
            self.assertEqual(caught.exception.code, 'HANDOFF_STEP_SCOPE_MISMATCH')
        self.assertEqual(before, self.counts())

    def test_scope_mapping_and_predecessor_are_immutable(self):
        self.assertEqual(root_step(self.target).pk, self.old_step.pk)
        self.assertEqual(route_mapping(self.original.routing_version, self.successor.routing_version)[0]['targetStepId'], self.target.pk)
        with self.assertRaises(ValidationError):
            RoutingStep.objects.filter(pk=self.target.pk).update(predecessor_step_id=None)
        other_owner = RoutingVersion.objects.create(product=self.product, product_version=self.product_version,
            routing_version='HANDOFF-OTHER-OWNER', revision=99)
        with self.assertRaises(ValidationError):
            RoutingStep.objects.create(routing_version=other_owner, sequence=1,
                operation=self.old_step.operation, predecessor_step=self.old_step)
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            result = self.activate()
        row = PlanStepVersionBinding.objects.get(pk=result['bindingId'])
        with self.assertRaises(ValidationError):
            PlanStepVersionBinding.objects.filter(pk=row.pk).update(context_hash='x')
        row.reason = 'rewrite'
        with self.assertRaises(ValidationError):
            row.save()
        self.assertEqual(resolve_step_context(self.plan, self.target.pk, frozen_proof=binding_proof(
            PlanStepVersionBinding.objects.get(pk=result['bindingId'])))['step'].pk, self.target.pk)

    def test_http_native_preview_activate_payload_and_typed_failure(self):
        client = APIClient(); client.force_authenticate(self.executor)
        payload = {'action':'preview', 'productionPlanId':self.plan.pk, 'rootRoutingStepId':self.old_step.pk,
            'manufacturingOutputId':self.successor.pk, 'targetRoutingStepId':self.target.pk, 'impactBasis':self.basis}
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            preview = client.post('/api/pde/plan-step-version-handoffs/', payload, format='json')
            self.assertEqual(preview.status_code, 200, preview.data)
            saved = client.post('/api/pde/plan-step-version-handoffs/', {**payload, 'action':'activate',
                'expectedContextHash':preview.data['contextHash'], 'impactHash':preview.data['impactHash'],
                'idempotencyKey':'http-binding', 'reason':'隔离原HTTP合同'}, format='json')
            self.assertEqual(saved.status_code, 200, saved.data)
            self.assertTrue(PlanStepVersionBinding.objects.filter(pk=saved.data['bindingId'], status='active').exists())
        failed = client.post('/api/pde/plan-step-version-handoffs/', {**payload, 'targetRoutingStepId':999999}, format='json')
        self.assertEqual(failed.status_code, 409, failed.data)
        self.assertEqual(failed.data['code'], 'HANDOFF_STEP_SCOPE_MISMATCH')
        UserRoleScopeAssignment.objects.filter(user=self.executor).update(active=False)
        denied = client.post('/api/pde/plan-step-version-handoffs/', payload, format='json')
        self.assertGreaterEqual(denied.status_code, 400)
        self.assertNotIn('businessWriteCount', denied.data)

    def test_historical_frozen_binding_never_grants_current_head_eligibility(self):
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            first = self.activate()
            old = PlanStepVersionBinding.objects.get(pk=first['bindingId'])
            frozen = binding_proof(old)
            made = RoutingVersionSuccessorService.create(source_id=self.successor.routing_version_id,
                user=self.executor, idempotency_key='third-native-route', reason='隔离第三版本')
            route = RoutingVersion.objects.get(pk=made['routingVersionId'])
            RoutingVersion.objects.filter(pk=route.pk).update(status='released')
            route.refresh_from_db()
            document = EngineeringDocumentVersion.objects.create(document=self.order_document,
                document_name='隔离第三版本资料', document_version='HANDOFF-THIRD',
                release_subject_type='ORDER_ENGINEERED_PRODUCT', order_engineering_instance=self.instance,
                order_engineering_baseline=self.successor.order_engineering_baseline,
                engineering_calculation=self.successor.engineering_calculation,
                related_bom=self.successor.bom_version, related_routing=route)
            EngineeringDocumentVersion.objects.filter(pk=document.pk).update(status='released')
            document.refresh_from_db()
            third, _ = self._generate(document, self.successor, 'binding-third-output')
            self._release(third, 'binding-third-release')
            args = {**self.arguments(), 'manufacturing_output_id':third.pk, 'target_step_id':route.steps.get().pk}
            candidate = Service.preview(**args)
            second = Service.activate(**args, expected_context_hash=candidate['contextHash'],
                expected_impact_hash=candidate['impactHash'], predecessor_id=old.pk,
                idempotency_key='binding-third', reason='隔离逐步承接')
        old.refresh_from_db()
        self.assertEqual(old.status, 'superseded')
        self.assertEqual(binding_proof(old), frozen)
        historical = resolve_step_context(self.plan, self.target.pk, historical=True, frozen_proof=frozen)
        self.assertEqual(historical['binding'].pk, old.pk)
        self.assertEqual(resolve_step_context(self.plan, self.old_step.pk)['binding'].pk, second['bindingId'])
        with self.assertRaises(PlanStepContextError):
            resolve_step_context(self.plan, self.target.pk, frozen_proof=frozen)

    def test_binding_audit_action_drift_is_not_a_valid_proof(self):
        with patch('pde.plan_step_version_handoff_service._impact', side_effect=self.impact):
            result = self.activate()
        row = PlanStepVersionBinding.objects.get(pk=result['bindingId'])
        OrganizationOperatingAuditRecord.objects.filter(pk=row.audit_record_id).update(action_code='other.action')
        row.refresh_from_db()
        with self.assertRaises(PlanStepContextError) as caught:
            binding_proof(row)
        self.assertEqual(caught.exception.code, 'STEP_VERSION_BINDING_UNPROVEN')

    def test_cross_company_and_actor_permission_fail_closed(self):
        from system.models import Company, User
        other = Company.objects.create(code='HANDOFF-OTHER', name='隔离其他公司')
        user = User.objects.create_user(username='handoff-other', company_id=other.pk)
        UserRoleScopeAssignment.objects.create(user=user, role=self.executing_role, organization=other,
            scope_code='ORGANIZATION', active=True, business_hash='isolated')
        with self.assertRaises(PlanStepContextError) as caught:
            Service.preview(**{**self.arguments(), 'user':user})
        self.assertEqual(caught.exception.code, 'HANDOFF_PLAN_INVALID')
        before = self.counts()
        UserRoleScopeAssignment.objects.filter(user=self.executor).update(active=False)
        with self.assertRaises(Exception):
            Service.preview(**self.arguments())
        self.assertEqual(before, self.counts())


class PlanStepImpactDependencyTests(TestCase):
    """Native synthetic source/extension/allocations; no assessment stubs."""
    def setUp(self):
        fixture = legal_fixture.PlanLegalExtensionAdmissionTests()
        fixture.setUp()
        self.fixture, self.f = fixture, fixture.f
        self.basis = {'executionFactReference':'isolated original declaration', 'executionStatement':'均未领料、未开工',
            'allMaterialUnissued':True, 'allWorkUnstarted':True}

    def clone_main(self, *, changed_value=False, changed_uom=False, omit_last=False):
        from .models import OrderEngineeringBaseline, OrderEngineeringBaselineItem, EngineeringCalculationRecord
        from .formal_engineering_continuation_service import _baseline_reference, _snapshot_design_input
        from . import operation_requirement_service as native
        f = self.f
        baseline = f.initial(OrderEngineeringBaseline, 'draft', company=f.company, sales_order=f.order,
            baseline_no='IMPACT-NEW-BASELINE', sequence=50, reason='隔离新基线',
            candidate_hash='a'*64, snapshot_hash='b'*64, scope_item_count=len(f.baseline_items)-(1 if omit_last else 0),
            confirmable_item_count=len(f.baseline_items)-(1 if omit_last else 0), blocker_count=0, created_by=f.user)
        items = []
        for old in f.baseline_items[:-1] if omit_last else f.baseline_items:
            values = {field.attname:deepcopy(getattr(old,field.attname))
                for field in OrderEngineeringBaselineItem._meta.concrete_fields
                if not field.primary_key and field.attname != 'baseline_id'}
            items.append(OrderEngineeringBaselineItem.objects.create(baseline=baseline, **values))
        baseline.snapshot_hash = native._digest([item.content_hash for item in items])
        baseline.save(update_fields=['snapshot_hash'])
        f.advance(baseline, 'confirmed')
        reference = _baseline_reference(baseline, items)
        objects = [{'baselineItemId':item.pk, 'designItemId':item.design_item_id,
            'designItemNo':item.item_no_snapshot, 'sourceAttributeId':item.source_attribute_id,
            'sourceKey':f'SIM-SHEET:{index}', 'contentHash':item.content_hash,
            'sourceVersion':f.source.source_version, 'sourceContentHash':f.source.content_hash,
            'input':_snapshot_design_input(item)} for index,item in enumerate(items,1)]
        input_hash = native._digest({'baseline':reference,'objects':objects})
        calc = f.initial(EngineeringCalculationRecord, 'running', company=f.company, scope='order_engineering',
            source_record=f.source, sales_order_item=f.item, engineering_instance=f.instance,
            calculation_no='IMPACT-NEW-MAIN', rule_set_version='SIM-V1', revision=50,
            input_hash=input_hash, trace={'baselineReference':reference, 'objectInputSnapshot':objects,
                'objectInputSnapshotHash':input_hash, 'sourceReference':{'id':f.source.pk,
                    'sourceVersion':f.source.source_version,'contentHash':f.source.content_hash}})
        saved = f.source_calc, f.baseline, f.baseline_items
        f.source_calc, f.baseline, f.baseline_items = calc, baseline, items
        facts = []
        for index,old in enumerate(saved[0].derived_facts.order_by('sequence')[:len(items)],1):
            value = '999' if changed_value and index == 1 else old.value['decimal']
            fact = f.make_fact(value,index)
            if changed_uom and index == 1:
                fact.uom = f.pcs
                fact.save(update_fields=['uom'])
            facts.append(fact)
        classified_fixture.ClassifiedFactEorTests.finish_source_hashes(f,calc,facts)
        f.advance(calc,'completed')
        f.source_calc, f.baseline, f.baseline_items = saved
        from types import SimpleNamespace
        return SimpleNamespace(order_engineering_baseline=baseline, engineering_calculation=calc,
            order_engineering_baseline_id=baseline.pk)

    def identity_extension(self):
        """Real native classification with arbitrary declared identity aliases."""
        from .engineering_fact_extension_service import EngineeringFactExtensionService, CONTRACT as FACT_CONTRACT
        from .models import EngineeringCalculationRecord, EngineeringOperationRequirement
        from . import operation_requirement_service as native
        f=self.f
        spec=deepcopy(self.fixture.extension.derived_facts.first().source_detail.rule.specification)
        config=spec['factExtension']
        config['metadataBindings'] += [{'name':alias,'sourceType':'FORMAL_SOURCE_IDENTITY','valueField':field}
            for alias,field in (('opaque_fact_token','sourceFactId'),('origin_run_token','sourceCalculationId'),
                ('opaque_detail_token','sourceDetailId'))]
        config['groupKeys'].append('opaque_fact_token')
        ids=EngineeringFactExtensionService.configure(user=f.user,reason='SIMULATED_FOR_TEST identity comparison',
            package={'contractVersion':FACT_CONTRACT,'companyId':f.company.pk,'rules':[{
                'ruleCode':'SIM-IMPACT-IDENTITY-ALIASES','ruleName':'Native identity aliases',
                'version':'V1','specification':spec}]})['ruleIds']
        result=EngineeringFactExtensionService.derive(user=f.user,source_calculation_id=f.source_calc.pk,
            rule_ids=ids,idempotency_key='sim-impact-native-identities',reason='SIMULATED_FOR_TEST')
        extension=EngineeringCalculationRecord.objects.get(pk=result['calculationId'])
        facts=list(extension.derived_facts.order_by('sequence'))
        rule=f.make_mapping(facts[0],f.op_area,f.area,mode=f.mode,capacity=f.capacity,
            dynamic_source_basis=True,release=False)
        mapping=deepcopy(rule.specification)
        mapping['manufacturing']['sourceSelector']['traceEquals']={'contractVersion':FACT_CONTRACT}
        mapping['manufacturing']['routingContext']={'contractVersion':legal_fixture.correction.ROUTE_CONTRACT,
            'routingId':f.route.pk,'routingVersionId':f.version.pk,'routingStepId':f.step.pk}
        mapping['sourceEvidence']['formalRouting']=f.route_evidence(f.version,f.step)
        rule.specification=mapping;rule.save(update_fields=['specification'])
        f.advance(rule,'reviewed');f.advance(rule,'released')
        self.fixture.requirements=[]
        for fact in facts:
            generated=native.OperationRequirementService.generate(user=f.user,source_calculation_id=extension.pk,
                source_fact_id=fact.pk,rule_id=rule.pk,idempotency_key=f'sim-impact-identity-eor-{fact.pk}',reason='SIMULATED_FOR_TEST')
            self.fixture.requirements.append(EngineeringOperationRequirement.objects.get(pk=generated['operationRequirementId']))
        return extension,ids,spec

    def test_declared_arbitrary_identity_aliases_have_real_native_equivalence(self):
        from .plan_step_version_handoff_service import _impact, _allocation_rows
        self.identity_extension();self.fixture.allocate()
        output=self.clone_main();before=self.f.full_database_snapshot()
        result=_impact(self.f.user,self.fixture.plan,output,_allocation_rows(self.fixture.plan),self.basis)
        self.assertEqual(result['blockers'],[],result)
        self.assertTrue(result['dependencyComparisons'][0]['equivalent'])
        self.assertEqual(before,self.f.full_database_snapshot())

    def identity_context(self):
        from .engineering_fact_extension_service import EngineeringFactExtensionService
        from .engineering_fact_metadata import REGISTERED_SOURCE_IDENTITIES
        extension,ids,spec=self.identity_extension()
        output=self.clone_main()
        previous=extension.trace['plan']['contexts'][0]
        current=EngineeringFactExtensionService.preview(user=self.f.user,
            source_calculation_id=output.engineering_calculation.pk,rule_ids=ids)['plan']['contexts']
        current=next(c for c in current if c['metadata']['designItemId']==previous['metadata']['designItemId'])
        old_proof=previous['sources'][0]['metadataProof'];new_proof=current['sources'][0]['metadataProof']
        old_record={k:old_proof[k] for k in REGISTERED_SOURCE_IDENTITIES}
        new_record={k:new_proof[k] for k in REGISTERED_SOURCE_IDENTITIES}
        return previous,spec['factExtension']['metadataBindings'],old_record,new_record

    def test_identity_metadata_without_its_declared_binding_is_not_rewritten(self):
        from .plan_step_version_handoff_service import _normalise_declared_metadata
        previous,configurations,old,new=self.identity_context()
        before=self.f.full_database_snapshot()
        configurations=[row for row in configurations if row['name'] not in
            ('opaque_fact_token','origin_run_token','opaque_detail_token')]
        projected={key:deepcopy(previous.get(key)) for key in
            ('ruleId','ruleVersion','specificationHash','group','inputs','result','uomId','metadata')}
        checked=_normalise_declared_metadata(previous,projected,configurations,
            {old['sourceFactId']:old},{new['sourceFactId']:new},{old['sourceFactId']:new['sourceFactId']})
        self.assertEqual(checked['metadata']['opaque_fact_token'],old['sourceFactId'])
        self.assertNotEqual(checked['metadata']['opaque_fact_token'],new['sourceFactId'])
        self.assertEqual(before,self.f.full_database_snapshot())

    def test_declared_identity_requires_exact_proof_and_known_source_field(self):
        from .plan_step_version_handoff_service import _normalise_declared_metadata
        previous,configurations,old,new=self.identity_context()
        before=self.f.full_database_snapshot()
        for mutation in ('wrongSource','missingBinding','unknownField'):
            context=deepcopy(previous);configs=deepcopy(configurations)
            proof=context['sources'][0]['metadataProof']
            if mutation=='wrongSource':proof['sourceFactId']=new['sourceFactId']
            elif mutation=='missingBinding':proof['bindings']=[]
            else:configs[-1]['valueField']='unregistered_identity'
            with self.subTest(mutation=mutation),self.assertRaises(PlanStepContextError) as caught:
                _normalise_declared_metadata(context,deepcopy(context),configs,
                    {old['sourceFactId']:old},{new['sourceFactId']:new},{old['sourceFactId']:new['sourceFactId']})
            self.assertEqual(caught.exception.code,'HANDOFF_SOURCE_IDENTITY_UNPROVEN')
        self.assertEqual(before,self.f.full_database_snapshot())

    def test_real_native_main_and_extension_equivalence_is_read_only(self):
        from .plan_step_version_handoff_service import _impact, _allocation_rows
        self.fixture.allocate()
        output = self.clone_main()
        before = self.f.full_database_snapshot()
        result = _impact(self.f.user,self.fixture.plan,output,_allocation_rows(self.fixture.plan),self.basis)
        self.assertEqual(result['blockers'], [], result)
        self.assertTrue(result['mainComparison']['equivalent'])
        self.assertTrue(all(row['equivalent'] for row in result['dependencyComparisons']))
        self.assertFalse(result['historicalRowsGrantedFutureExecution'])
        self.assertEqual(result['newVersionReusedAllocationIds'], [])
        self.assertEqual(before,self.f.full_database_snapshot())

    def test_real_quantity_difference_blocks(self):
        from .plan_step_version_handoff_service import _impact
        output = self.clone_main(changed_value=True)
        result = _impact(self.f.user,self.fixture.plan,output,[],self.basis)
        self.assertIn('HANDOFF_MAIN_DEPENDENCY_CHANGED',[row['code'] for row in result['blockers']])

    def test_real_unit_difference_blocks(self):
        from .plan_step_version_handoff_service import _impact
        output = self.clone_main(changed_uom=True)
        result = _impact(self.f.user,self.fixture.plan,output,[],self.basis)
        self.assertIn('HANDOFF_MAIN_DEPENDENCY_CHANGED',[row['code'] for row in result['blockers']])

    def test_real_object_omission_blocks_and_actual_allocated_step_cannot_switch(self):
        from .plan_step_version_handoff_service import _impact, _allocation_rows, _assert_unallocated
        output = self.clone_main(omit_last=True)
        result = _impact(self.f.user,self.fixture.plan,output,[],self.basis)
        self.assertIn('HANDOFF_OBJECT_MAPPING_UNPROVEN',[row['code'] for row in result['blockers']])
        self.fixture.allocate()
        before = self.f.full_database_snapshot()
        with self.assertRaises(PlanStepContextError) as caught:
            _assert_unallocated(_allocation_rows(self.fixture.plan),self.f.step)
        self.assertEqual(caught.exception.code,'HANDOFF_ALLOCATED_STEP_BLOCKED')
        self.assertEqual(before,self.f.full_database_snapshot())
