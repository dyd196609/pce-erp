"""Isolated saved-main step continuation; never formal business admission.

The established 0046 fixture supplies real legacy adoption, baseline confirmation,
main execution and its ledger/audit/state. Only its numeric workbook adapter is
synthetic. The original output is generated/released by the native services;
the same two upstream document-proof stubs used by the established output
fixture remain explicit. No continuation proof, fixed-input resolver, impact
comparison, binding persistence or consumer context is replaced.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import sqlite3
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import Demand, PlanningRequirement, ProductionPlan
from system.models import (
    Company, OrganizationOperatingAuditRecord, Permission, PositionResponsibility,
    Process, Responsibility, RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from . import tests_engineering_calculation_continuation as main_fixture
from .tests_engineering_version_handoff_upstream import finalize_runtime_fixture
from . import tests_plan_legal_extension_admission as legal_fixture
from . import tests_operation_requirement as requirement_fixture
from . import tests_engineering_document_version_release as document_release_fixture
from . import operation_requirement_service as requirement_service
from . import operation_workload_source_service as workload_service
from . import operation_input_preparation_service as preparation_service
from . import routing_object_applicability_service as object_service
from . import plan_step_context_service as step_context_service
from .engineering_rule_foundation import specification_hash
from .engineering_calculation_continuation_service import continuation_proof
from .manufacturing_output_generation_service import ACTION as GENERATE
from . import manufacturing_output_generation_service as output_service
from .manufacturing_output_release_service import (
    ACTION as RELEASE, release_manufacturing_output, release_preflight,
)
from .models import (
    BOMItem, BOMVersion, CapacityProductType, EngineeringCalculationContinuation,
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringDocument,
    EngineeringDocumentVersion, EngineeringOperationRequirement,
    OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    PlanStepVersionBinding, ProductBOM, ProductManufacturingOutput,
    ProductionPlanOperationRequirementAllocation, Routing, RoutingStep, RoutingVersion,
)
from .plan_step_context_service import (
    CALCULATION_CONTINUATION, PlanStepContextError, binding_proof, bind_plan_context,
    calculation_source, digest, effective_baseline, effective_calculation,
    effective_routing_version, resolve_step_context, source_selection, version_fact,
)
from .plan_step_version_handoff_service import (
    PlanStepVersionHandoffService as Service, _allocation_rows, _assert_unallocated, _impact,
)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE={
    'companyCode': 'LIA', 'orderNo': 'SO-LIA-001', 'lineNo': 1,
})
class PlanStepSourceContinuationTests(TestCase):
    _adopt = main_fixture.EngineeringCalculationContinuationTests._adopt
    args = main_fixture.EngineeringCalculationContinuationTests.args
    execute_main = main_fixture.EngineeringCalculationContinuationTests.execute

    @classmethod
    def setUpTestData(cls):
        main_fixture.EngineeringCalculationContinuationTests.setUpTestData.__func__(cls)
        # Complete this isolated old Fact's object identity before native adoption
        # freezes it; do not rewrite an already adopted or consumed Fact.
        item = cls.baseline.items.get(design_item=cls.design_items[0])
        fact = cls.calculations[0].derived_facts.get()
        fact.trace = {**fact.trace, 'baselineId': cls.baseline.pk,
            'baselineItemId': item.pk, 'designItemId': item.design_item_id,
            'sourceAttributeId': item.source_attribute_id}
        fact.save(update_fields=['trace'])
        type(cls.instances[0]).objects.filter(pk=cls.instances[0].pk).update(
            product_category=cls.category, selected_process_type=cls.process)
        cls.instances[0].refresh_from_db()
        finalize_runtime_fixture(cls,cls.calculations[0],cls.baseline)

    def numeric_fixture(self, keys, *, design_inputs):
        result = main_fixture.EngineeringCalculationContinuationTests.numeric_fixture(
            self, keys, design_inputs=design_inputs)
        for row in result['rows']:
            # The negative comparison is created by native main execution, with
            # all persisted detail/result hashes intact; never re-sign a Fact.
            row['value'] = ('2' if self._testMethodName ==
                'test_16_real_impact_uses_selected_main_not_anchor_self_comparison' else '1')
        return result

    def setUp(self):
        main_fixture.EngineeringCalculationContinuationTests.setUp(self)
        for code in ('planning.view', 'production.master_data.routing.maintain',
                     output_service.PERMISSION):
            permission, _ = Permission.objects.get_or_create(code=code,
                defaults={'name': code, 'module': 'PDE'})
            RolePermission.objects.get_or_create(role=self.role, permission=permission)
        for code, primary in ((output_service.RESPONSIBILITY, False), ('RESP_PROD_PLAN_001', True)):
            duty, _ = Responsibility.objects.get_or_create(code=code,
                defaults={'name': code, 'status': 'ACTIVE', 'is_active': True})
            PositionResponsibility.objects.get_or_create(position=self.position,
                responsibility=duty, defaults={'active': True, 'is_primary': primary})
        for stub in (
            patch('pde.manufacturing_output_generation_service.release_readback',
                return_value={'completed': True, 'businessStateTransitionId': 999}),
            patch('pde.manufacturing_output_generation_service.project_release_content_integrity',
                return_value={'valid': True, 'stableCurrentContentHash': 'verified-fixture'}),
        ):
            stub.start()
            self.addCleanup(stub.stop)
        self._make_original_output_and_plan(component_dependent=
            self._testMethodName == 'test_15_actual_bom_component_dependency_keeps_full_output_gate')
        self.original_plan = ProductionPlan.objects.values().get(pk=self.plan.pk)
        self.original_demand = Demand.objects.values().get(pk=self.plan.planning_requirement.demand_id)
        result = self.execute_main()
        self.continuation = EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        self.main = self.continuation.new_calculation
        self.new_baseline = self.continuation.baseline
        self.basis = {'executionFactReference': 'isolated user execution fact',
            'executionStatement': '均未领料、未开工',
            'allMaterialUnissued': True, 'allWorkUnstarted': True}

    def _make_original_output_and_plan(self, *, component_dependent=False):
        instance, old = self.instances[0], self.calculations[0]
        bom = ProductBOM.objects.create(company=self.company, applicability_scope='ORDER_ENGINEERING',
            order_engineering_instance=instance, bom_code='SOURCE-ANCHOR-BOM', name='isolated original BOM')
        bom_version = BOMVersion.objects.create(bom=bom, bom_version='SOURCE-ANCHOR-1',
            bom_scope='order_specific', order_engineering_instance=instance, source_calculation=old)
        component = BOMItem.objects.create(bom_version=bom_version, material=self.material,
            line_no=1, quantity=1, uom=self.uom)
        finalize_runtime_fixture(self,old,self.baseline,bom_version)
        route = Routing.objects.create(company=self.company, applicability_scope='PRODUCT_CATEGORY',
            product_category=self.category, manufacturing_process_type=self.process,
            routing_code='SOURCE-ANCHOR-ROUTE', name='isolated original route')
        route_version = RoutingVersion.objects.create(routing=route, routing_version='SOURCE-ANCHOR-1')
        operation = Process.objects.create(company=self.company, code='SOURCE-ANCHOR-OP',
            name='isolated operation', calculation_uom=self.uom)
        self.step = RoutingStep.objects.create(routing_version=route_version, sequence=1,
            operation=operation, operation_parameters={'applicability': {
                'contractVersion': 'PCE-ROUTING-STEP-APPLICABILITY-V1.0', 'mode': 'MANDATORY'}},
            applies_to_item=component if component_dependent else None)
        document = EngineeringDocument.objects.create(document_no='SOURCE-ANCHOR-DOC',
            document_name='isolated original document', document_type='technical',
            release_subject_type='ORDER_ENGINEERED_PRODUCT', order_engineering_instance=instance,
            product_bom=bom, routing=route)
        document_version = EngineeringDocumentVersion.objects.create(document=document,
            document_name='isolated original document', document_version='SOURCE-ANCHOR-1',
            release_subject_type='ORDER_ENGINEERED_PRODUCT', order_engineering_instance=instance,
            order_engineering_baseline=self.baseline, engineering_calculation=old,
            related_bom=bom_version, related_routing=route_version)
        for obj in (bom_version, route, route_version, document_version):
            type(obj).objects.filter(pk=obj.pk).update(status='released')
        candidate = output_service.candidate_projection(self.actor, sales_order_item_id=self.items[0].pk,
            document_version_id=document_version.pk)
        self.assertTrue(candidate['sourceReady'], candidate)
        result = output_service.generate_manufacturing_output(user=self.actor,
            idempotency_key='source-anchor-generate', payload={'action': GENERATE,
                'salesOrderItemId': self.items[0].pk, 'engineeringDocumentVersionId': document_version.pk,
                'sourceFingerprint': candidate['sourceFingerprint'], 'reason': 'isolated existing original anchor'})
        self.anchor = ProductManufacturingOutput.objects.get(pk=result['row']['id'])
        preflight = release_preflight(self.anchor, self.actor)
        self.assertTrue(preflight['releaseAllowed'], preflight)
        release_manufacturing_output(user=self.actor, output_id=self.anchor.pk,
            idempotency_key='source-anchor-release', payload={'action': RELEASE,
                'reason': 'isolated original release', 'sourceFingerprint': preflight['sourceFingerprint']})
        self.anchor.refresh_from_db()
        demand = create_business_object_with_initial_state(model=Demand, initial_state='draft',
            demand_no='SOURCE-PLAN-DEMAND', source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(self.order.pk), source_document_no=self.order.order_no,
            sales_order_item=self.items[0], manufacturing_output=self.anchor, material=self.material,
            required_qty=1, required_date=date.today(), department=self.department,
            reason='isolated fixed original plan', created_by=self.actor)
        requirement = PlanningRequirement.objects.create(requirement_no='SOURCE-PLAN-REQUIREMENT',
            demand=demand, material=self.material, demand_qty=1, available_qty=0, net_required_qty=1,
            required_date=date.today(), supply_type='production', status='confirmed', created_by=self.actor)
        self.plan = ProductionPlan.objects.create(plan_no='SOURCE-PLAN', planning_requirement=requirement,
            material=self.material, planned_qty=1, required_date=date.today(), source_id=str(requirement.pk),
            confirmed_by=self.actor, status='confirmed')

    def handoff_arguments(self, **changes):
        values = {'user': self.actor, 'production_plan_id': self.plan.pk,
            'root_step_id': self.step.pk, 'target_step_id': self.step.pk,
            'main_calculation_id': self.main.pk, 'impact_basis': deepcopy(self.basis)}
        values.update(changes)
        return values

    def activate(self, candidate=None, **changes):
        candidate = candidate or Service.preview(**self.handoff_arguments())
        values = {**self.handoff_arguments(), 'expected_context_hash': candidate['contextHash'],
            'expected_impact_hash': candidate['impactHash'], 'predecessor_id': candidate['currentBindingId'],
            'idempotency_key': 'source-step-activate', 'reason': 'isolated exact saved-main selection'}
        values.update(changes)
        return Service.activate(**values)

    def counts(self):
        return tuple(model.objects.count() for model in (PlanStepVersionBinding, MasterDataWriteRequest,
            ExternalIdentity, OrganizationOperatingAuditRecord, BusinessStateTransition,
            EngineeringCalculationRecord, EngineeringDerivedFact, ProductManufacturingOutput))

    def test_01_real_saved_continuation_preview_compares_distinct_mains_without_writes(self):
        before = self.counts()
        candidate = Service.preview(**self.handoff_arguments())
        self.assertTrue(candidate['ready'], candidate)
        selection = candidate['sourceSnapshot']['sourceSelection']
        self.assertEqual(selection['selectionType'], CALCULATION_CONTINUATION)
        self.assertEqual(selection['mainCalculationId'], self.main.pk)
        self.assertEqual(selection['baselineId'], self.new_baseline.pk)
        self.assertEqual(selection['anchorManufacturingOutputId'], self.anchor.pk)
        comparison = candidate['impactSnapshot']['mainComparison']
        self.assertEqual(comparison['originalCalculationId'], self.calculations[0].pk)
        self.assertEqual(comparison['targetCalculationId'], self.main.pk)
        self.assertNotEqual(comparison['originalCalculationId'], comparison['targetCalculationId'])
        self.assertTrue(comparison['equivalent'])
        self.assertEqual(before, self.counts())

    def test_02_native_binding_and_all_context_helpers_keep_real_anchor(self):
        saved = self.activate()
        binding = PlanStepVersionBinding.objects.get(pk=saved['bindingId'])
        proof = binding_proof(binding)
        ctx = resolve_step_context(self.plan, self.step.pk, user=self.actor)
        bound_plan = bind_plan_context(self.plan, ctx)
        self.assertEqual(ctx['base'].pk, self.main.pk)
        self.assertEqual(ctx['baseline'].pk, self.new_baseline.pk)
        self.assertEqual(ctx['output'].pk, self.anchor.pk)
        self.assertEqual(effective_calculation(bound_plan).pk, self.main.pk)
        self.assertEqual(effective_baseline(bound_plan).pk, self.new_baseline.pk)
        self.assertEqual(effective_routing_version(bound_plan).pk, self.step.routing_version_id)
        self.assertEqual(bound_plan.planning_requirement.demand.manufacturing_output_id, self.anchor.pk)
        self.assertEqual(source_selection(bound_plan), ctx['sourceProof'])
        self.assertEqual(source_selection(ctx), ctx['sourceProof'])
        self.assertEqual(proof['sourceSelection'], ctx['sourceProof'])
        self.assertIn(str(self.main.pk), version_fact(ctx)['versionLabel'])
        self.assertEqual(self.original_plan, ProductionPlan.objects.values().get(pk=self.plan.pk))
        self.assertEqual(self.original_demand, Demand.objects.values().get(pk=self.plan.planning_requirement.demand_id))
        self.assertEqual(continuation_proof(self.continuation)['newCalculationId'], self.main.pk)

    def test_03_replay_is_zero_write_and_conflicting_payload_is_rejected(self):
        candidate = Service.preview(**self.handoff_arguments())
        first = self.activate(candidate)
        before = self.counts()
        again = self.activate(candidate)
        self.assertEqual(again['bindingId'], first['bindingId'])
        self.assertTrue(again['idempotentReplay'])
        self.assertEqual((again['businessWriteCount'], again['auditWriteCount']), (0, 0))
        self.assertEqual(before, self.counts())
        with self.assertRaises(PlanStepContextError):
            self.activate(candidate, reason='changed request')
        self.assertEqual(before, self.counts())

    def test_04_late_transition_failure_rolls_back_all_binding_effects(self):
        candidate = Service.preview(**self.handoff_arguments())
        before = self.counts()
        with patch('pde.plan_step_version_handoff_service.transition_business_object',
                   side_effect=RuntimeError('isolated binding transition failure')):
            with self.assertRaisesRegex(RuntimeError, 'isolated binding'):
                self.activate(candidate)
        self.assertEqual(before, self.counts())
        self.assertEqual(self.original_plan, ProductionPlan.objects.values().get(pk=self.plan.pk))

    def test_05_explicit_invalid_selectors_never_fall_back_to_old_output(self):
        before = self.counts()
        for value in (None, 0, True, False, '1', -1):
            with self.subTest(value=value), self.assertRaises(PlanStepContextError):
                Service.preview(**self.handoff_arguments(main_calculation_id=value))
        self.assertEqual(before, self.counts())

    def test_06_original_or_wrong_order_main_cannot_be_selected(self):
        for calc in (self.calculations[0], self.calculations[1]):
            with self.subTest(calc=calc.pk), self.assertRaises(PlanStepContextError):
                calculation_source(self.plan, calc.pk, user=self.actor)

    def test_07_cross_company_selector_is_rejected(self):
        company = Company.objects.create(code='SOURCE-OTHER', name='isolated other company')
        other = User.objects.create_user(username='source-other', company_id=company.pk)
        with self.assertRaises(PlanStepContextError) as caught:
            calculation_source(self.plan, self.main.pk, user=other)
        self.assertEqual(caught.exception.code, 'STEP_VERSION_SOURCE_INVALID')

    def corrupt(self, model, pk, column, value):
        # Deliberate isolated negative fixture, bypassing immutable model guards;
        # this is not a production repair or a write performed by the service.
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {model._meta.db_table} SET {column}=%s WHERE id=%s', [value, pk])

    def test_08_unconfirmed_baseline_is_not_source_authority(self):
        self.corrupt(OrderEngineeringBaseline, self.new_baseline.pk, 'status', 'draft')
        with self.assertRaises(PlanStepContextError):
            calculation_source(self.plan, self.main.pk, user=self.actor)

    def test_09_wrong_0046_predecessor_is_rejected_without_new_records(self):
        self.corrupt(EngineeringCalculationContinuation, self.continuation.pk,
            'previous_calculation_id', self.calculations[1].pk)
        before = self.counts()
        with self.assertRaises(PlanStepContextError):
            calculation_source(self.plan, self.main.pk, user=self.actor)
        self.assertEqual(before, self.counts())

    def test_10_baseline_object_content_hash_cannot_self_certify(self):
        item = self.new_baseline.items.get(design_item=self.design_items[0])
        self.corrupt(OrderEngineeringBaselineItem, item.pk, 'content_hash', 'f' * 64)
        with self.assertRaises(PlanStepContextError):
            calculation_source(self.plan, self.main.pk, user=self.actor)

    def test_11_saved_main_hash_tamper_is_rejected(self):
        EngineeringCalculationRecord.objects.filter(pk=self.main.pk).update(result_hash='f' * 64)
        with self.assertRaises(PlanStepContextError):
            calculation_source(self.plan, self.main.pk, user=self.actor)

    def test_12_stale_context_and_impact_hashes_do_not_create_binding(self):
        candidate = Service.preview(**self.handoff_arguments())
        before = self.counts()
        for key in ('expected_context_hash', 'expected_impact_hash'):
            with self.subTest(key=key), self.assertRaises(PlanStepContextError):
                self.activate(candidate, **{key: '0' * 64})
        self.assertEqual(before, self.counts())

    def test_13_missing_native_continuation_audit_is_not_accepted(self):
        OrganizationOperatingAuditRecord.objects.filter(pk=self.continuation.audit_record_id).update(
            action_code='isolated.wrong')
        with self.assertRaises(PlanStepContextError):
            calculation_source(self.plan, self.main.pk, user=self.actor)

    def test_14_actual_http_selector_uses_same_native_source_and_null_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.actor)
        payload = {'action': 'preview', 'productionPlanId': self.plan.pk,
            'rootRoutingStepId': self.step.pk, 'targetRoutingStepId': self.step.pk,
            'mainCalculationId': self.main.pk, 'impactBasis': self.basis}
        response = client.post('/api/pde/plan-step-version-handoffs/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['sourceSnapshot']['sourceSelection']['mainCalculationId'], self.main.pk)
        for value in (None, 0, True):
            bad = client.post('/api/pde/plan-step-version-handoffs/',
                {**payload, 'mainCalculationId': value}, format='json')
            self.assertGreaterEqual(bad.status_code, 400, bad.data)

    def test_15_actual_bom_component_dependency_keeps_full_output_gate(self):
        before = self.counts()
        with self.assertRaises(PlanStepContextError) as caught:
            Service.preview(**self.handoff_arguments())
        self.assertEqual(caught.exception.code, 'HANDOFF_SOURCE_BOM_DEPENDENCY_REQUIRED')
        self.assertEqual(before, self.counts())

    def test_16_real_impact_uses_selected_main_not_anchor_self_comparison(self):
        before = self.counts()
        result = _impact(self.actor, self.plan, self.anchor, [], self.basis,
            base=self.main, baseline=self.new_baseline)
        self.assertEqual(result['mainComparison']['targetCalculationId'], self.main.pk)
        self.assertNotEqual(result['mainComparison']['originalCalculationId'], self.main.pk)
        self.assertFalse(result['mainComparison']['equivalent'])
        self.assertIn('HANDOFF_MAIN_DEPENDENCY_CHANGED', [row['code'] for row in result['blockers']])
        self.assertEqual(before, self.counts())

    def _consumer_type(self):
        kind = CapacityProductType.objects.create(company=self.company, code='SOURCE-CONSUMER-TYPE',
            name='isolated exact category and process', product_category=self.category,
            manufacturing_process_type=self.process)
        permission, _ = Permission.objects.get_or_create(code=preparation_service.VIEW,
            defaults={'name': preparation_service.VIEW, 'module': 'PDE'})
        RolePermission.objects.get_or_create(role=self.role, permission=permission)
        return kind

    def _direct_requirement(self):
        """Native legacy EOR rule contract, without fabricating producer units.

        This is disposable fixture configuration. The saved main's real generic
        producer declaration and all its frozen Facts remain unchanged.
        """
        kind = self._consumer_type()
        self.user, self.product_type, self.pcs = self.actor, kind, self.uom
        self.rule_counter = 0
        self.initial = requirement_fixture.OperationRequirementTests.initial.__get__(self)
        self.advance = requirement_fixture.OperationRequirementTests.advance.__get__(self)
        fact = self.main.derived_facts.get()
        rule = requirement_fixture.OperationRequirementTests.make_rule(self, self.step.operation,
            self.uom, fact.canonical_field, basis='SOURCE_SCOPE_TOTAL',
            basis_quantity=str(self.items[0].quantity))
        result = requirement_service.OperationRequirementService.generate(user=self.actor,
            source_calculation_id=self.main.pk, source_fact_id=fact.pk, rule_id=rule.pk,
            idempotency_key='isolated-source-direct-generation', reason='isolated native DIRECT source')
        return kind, fact, rule, EngineeringOperationRequirement.objects.get(pk=result['operationRequirementId'])

    def test_18_real_consumers_read_selected_main_and_complete_baseline_without_writes(self):
        self.activate()
        kind = self._consumer_type()
        exact = {'companyId': self.company.pk, 'productionPlanId': self.plan.pk,
            'manufacturingOutputId': self.anchor.pk, 'mainCalculationId': self.main.pk,
            'salesOrderItemId': self.items[0].pk, 'baselineId': self.new_baseline.pk,
            'routingVersionId': self.step.routing_version_id, 'routingStepId': self.step.pk,
            'operationId': self.step.operation_id, 'productTypeId': kind.pk}
        before = self.counts()
        with CaptureQueriesContext(connection) as queries:
            plan, output, item, base, step, actual_kind, applicability = workload_service._scope_context(
                self.actor, self.plan.pk, self.step.pk)
            native = object_service._load_scope(self.plan.pk, self.step.pk)
            prepared = preparation_service._scope_impl(self.actor, exact)
            preparation = preparation_service.read_preparation(user=self.actor, exact_scope=exact)
            detail = workload_service.read_for_plan(user=self.actor,
                production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
            route = workload_service.read_route_overview(user=self.actor,
                production_plan_id=self.plan.pk, include_workloads=True)
        self.assertEqual((base.pk, effective_baseline(plan).pk, output.pk),
            (self.main.pk, self.new_baseline.pk, self.anchor.pk))
        self.assertEqual((native['base'].pk, native['baseline'].pk, native['output'].pk),
            (self.main.pk, self.new_baseline.pk, self.anchor.pk))
        expected_objects = set(self.new_baseline.items.filter(
            design_item__sales_order_item=self.items[0]).values_list('pk', flat=True))
        self.assertEqual({obj.pk for obj in native['objects']}, expected_objects)
        self.assertEqual(prepared['scope'], exact)
        self.assertEqual(prepared['context']['sourceSelection']['mainCalculationId'], self.main.pk)
        self.assertEqual(preparation['exactScope'], exact)
        self.assertEqual(preparation['recordStatus'], 'NOT_RECORDED')
        self.assertEqual(detail['scope'], exact)
        self.assertEqual(detail['effectiveVersion']['mainCalculationId'], self.main.pk)
        self.assertEqual(len(route['rows']), 1)
        self.assertEqual(route['rows'][0]['scope'], exact)
        self.assertEqual(route['rows'][0]['effectiveVersion']['mainCalculationId'], self.main.pk)
        self.assertEqual(applicability['result'], 'REQUIRED')
        self.assertEqual((item.pk, step.pk, actual_kind.pk), (self.items[0].pk, self.step.pk, kind.pk))
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(
            ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP')) for query in queries))
        self.assertEqual(self.counts(), before)

    def test_19_native_direct_eor_allocate_and_read_preserve_original_plan_and_main(self):
        self.activate()
        old_main = EngineeringCalculationRecord.objects.values().get(pk=self.main.pk)
        old_facts = list(EngineeringDerivedFact.objects.filter(calculation=self.main).order_by('pk').values())
        kind, fact, rule, req = self._direct_requirement()
        ready = requirement_service.OperationRequirementService.allocation_readiness(user=self.actor,
            production_plan_id=self.plan.pk, operation_requirement_id=req.pk, routing_step_id=self.step.pk)
        self.assertTrue(ready['canSave'], ready)
        result = requirement_service.OperationRequirementService.allocate(user=self.actor,
            production_plan_id=self.plan.pk, operation_requirement_id=req.pk, routing_step_id=self.step.pk,
            idempotency_key='isolated-source-direct-allocation', reason='isolated native exact source')
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=result['allocationId'])
        self.assertEqual((row.source_quantity, row.allocated_quantity, row.uom_id),
            (Decimal('1'), Decimal('1'), self.uom.pk))
        self.assertEqual(row.source_snapshot['planStepVersionBinding']['sourceSelection']['mainCalculationId'], self.main.pk)
        self.assertEqual(row.operation_requirement.source_calculation_id, self.main.pk)
        readback = requirement_service.OperationRequirementService.read(user=self.actor, production_plan_id=self.plan.pk)
        self.assertTrue(readback['passed'], readback)
        detail = workload_service.read_for_plan(user=self.actor,
            production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        self.assertEqual([item['operationRequirementId'] for item in detail['formalRequirements']['items']], [req.pk])
        self.assertEqual([item['allocationId'] for item in detail['savedAllocations']['items']], [row.pk])
        self.assertEqual(self.original_plan, ProductionPlan.objects.values().get(pk=self.plan.pk))
        self.assertEqual(self.original_demand, Demand.objects.values().get(pk=self.plan.planning_requirement.demand_id))
        self.assertEqual(old_main, EngineeringCalculationRecord.objects.values().get(pk=self.main.pk))
        self.assertEqual(old_facts, list(EngineeringDerivedFact.objects.filter(calculation=self.main).order_by('pk').values()))

    def test_20_native_object_exclusion_blocks_new_direct_allocation_without_writes(self):
        self.activate()
        kind, fact, rule, req = self._direct_requirement()
        obj = self.new_baseline.items.get(design_item=self.design_items[0])
        candidate = object_service.build_context(self.plan.pk, self.step.pk, obj.pk)
        proof = next(row for row in candidate['sourceProofs'] if row['id'] == fact.pk)
        basis = {'contractVersion': object_service.BASIS_CONTRACT_VERSION,
            'decisionReference': {'code': 'ISOLATED-EXCLUSION', 'statement': 'isolated object excluded',
                'reference': 'disposable test fixture', 'referenceSha256': 'a' * 64},
            'sourceFact': {'id': fact.pk, 'sourceSnapshotHash': proof['sourceSnapshotHash']},
            'rules': [{'id': fact.rule_id, 'version': fact.rule.version,
                'specificationHash': specification_hash(fact.rule.specification)}],
            'execution': {'mode': 'AUTHORIZED_CODEX_AGENT', 'humanBusinessAcceptanceClaimed': False}}
        saved = object_service.confirm_group(self.actor, self.plan.pk, self.step.pk, [{
            'baselineItemId': obj.pk, 'decision': 'NOT_APPLICABLE', 'basis': basis,
            'contextHash': candidate['contextHash'], 'idempotencyKey': 'isolated-source-object-excluded'}],
            'isolated exact exclusion after source binding')
        self.assertEqual(saved['objectApplicability']['result'], 'NOT_APPLICABLE')
        before, allocations = self.counts(), ProductionPlanOperationRequirementAllocation.objects.count()
        ready = requirement_service.OperationRequirementService.allocation_readiness(user=self.actor,
            production_plan_id=self.plan.pk, operation_requirement_id=req.pk, routing_step_id=self.step.pk)
        self.assertFalse(ready['canSave'], ready)
        self.assertIn('ALLOCATION_STEP_NOT_REQUIRED', [row['code'] for row in ready['blockers']])
        with self.assertRaises(requirement_service.OperationRequirementError) as caught:
            requirement_service.OperationRequirementService.allocate(user=self.actor,
                production_plan_id=self.plan.pk, operation_requirement_id=req.pk, routing_step_id=self.step.pk,
                idempotency_key='isolated-excluded-direct-allocation', reason='must reject exclusion')
        self.assertEqual(caught.exception.code, 'ALLOCATION_STEP_NOT_REQUIRED')
        self.assertEqual((self.counts(), ProductionPlanOperationRequirementAllocation.objects.count()), (before, allocations))

    def test_21_mutated_call_owned_context_rejects_helpers_and_cache_restores_database_values(self):
        self.activate()
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        context = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache=cache)
        correct_hash = self.main.result_hash
        bound = bind_plan_context(self.plan, context)
        context['base'].result_hash = 'f' * 64
        for reader in (source_selection, effective_calculation, effective_baseline, effective_routing_version):
            with self.subTest(reader=reader.__name__), self.assertRaises(PlanStepContextError) as caught:
                reader(bound)
            self.assertEqual(caught.exception.code, 'STEP_VERSION_SOURCE_CHANGED')
        restored = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache=cache)
        self.assertEqual(restored['base'].result_hash, correct_hash)
        self.assertEqual(source_selection(restored)['mainCalculationId'], self.main.pk)
        mutated = bind_plan_context(self.plan, restored)
        mutated._native_step_version_context['sourceProof']['mainCalculationId'] = self.calculations[0].pk
        with self.assertRaises(PlanStepContextError) as caught:
            source_selection(mutated)
        self.assertEqual(caught.exception.code, 'STEP_VERSION_SOURCE_CHANGED')
        current = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache=cache)
        self.assertEqual(source_selection(current)['mainCalculationId'], self.main.pk)
        self.assertEqual(EngineeringCalculationRecord.objects.get(pk=self.main.pk).result_hash, correct_hash)

    def test_22_one_binding_proof_is_shared_across_current_history_and_preparation_reads(self):
        self.activate();kind=self._consumer_type()
        cache=requirement_service._ReadOnlyProofCache(self.actor)
        before=self.counts();changes=connection.connection.total_changes
        with patch.object(output_service,'validate_selected_output',wraps=output_service.validate_selected_output) as proof, \
                patch.object(output_service, '_saved_output_content_integrity',
                    wraps=output_service._saved_output_content_integrity) as content, \
                patch.object(step_context_service, 'binding_proof', wraps=binding_proof) as binding, \
                patch.object(step_context_service, 'calculation_source', wraps=calculation_source) as source, \
                patch.object(ProductManufacturingOutput, 'full_clean', autospec=True,
                    side_effect=ProductManufacturingOutput.full_clean) as clean:
            current=resolve_step_context(self.plan,self.step.pk,user=self.actor,read_cache=cache)
            plan,output,item,base,step,actual_kind,_=workload_service._scope_context(
                self.actor,self.plan.pk,self.step.pk,_read_cache=cache)
            exact={'companyId':self.company.pk,'productionPlanId':self.plan.pk,'manufacturingOutputId':output.pk,
                'mainCalculationId':base.pk,'salesOrderItemId':item.pk,'baselineId':effective_baseline(plan).pk,
                'routingVersionId':step.routing_version_id,'routingStepId':step.pk,
                'operationId':step.operation_id,'productTypeId':actual_kind.pk}
            preparation=preparation_service.read_preparation(user=self.actor,exact_scope=exact,read_cache=cache)
            historical=resolve_step_context(self.plan,self.step.pk,user=self.actor,historical=True,
                frozen_proof=current['bindingProof'],read_cache=cache)
            self.assertEqual(historical['bindingProof'],current['bindingProof'])
            self.assertIsNot(current['_sourceIntegrityGuard'], historical['_sourceIntegrityGuard'])
            self.assertEqual(proof.call_count,2)
            self.assertEqual((binding.call_count, source.call_count, clean.call_count, content.call_count), (2, 2, 2, 1))
            wrong={**current['bindingProof'],'impactHash':'f'*64}
            with self.assertRaises(PlanStepContextError) as caught:
                resolve_step_context(self.plan,self.step.pk,user=self.actor,historical=True,
                    frozen_proof=wrong,read_cache=cache)
            self.assertEqual(caught.exception.code,'STEP_VERSION_BINDING_CHANGED')
            self.assertEqual(proof.call_count,3)
            self.assertEqual((binding.call_count, source.call_count, clean.call_count, content.call_count), (3, 3, 3, 1))
        self.assertEqual(preparation['exactScope'],exact)
        self.assertEqual((self.counts(),connection.connection.total_changes),(before,changes))

    def test_23_full_value_fast_guard_rejects_nested_type_and_concrete_field_mutations(self):
        self.activate()
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        context = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache=cache)
        before, changes = self.counts(), connection.connection.total_changes
        cases = {
            'model_nested_json': lambda ctx: ctx['base'].trace.update(guardProbe={'nested': [1, 2]}),
            'proof_nested_json': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(number=2),
            'list_append': lambda ctx: ctx['sourceProof']['guardProbe']['list'].append(3),
            'list_remove': lambda ctx: ctx['sourceProof']['guardProbe']['list'].pop(),
            'list_nested_value': lambda ctx: ctx['sourceProof']['guardProbe']['list'][1].update(value='changed'),
            'int_to_bool': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(number=True),
            'int_to_float': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(number=1.0),
            'bool_to_int': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(flag=1),
            'float_to_int': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(decimal=1),
            'signed_float_zero': lambda ctx: ctx['sourceProof']['guardProbe']['nested'].update(zero=0.0),
            'dict_key_remove': lambda ctx: ctx['sourceProof']['guardProbe']['keys'].pop('remove'),
            'unsupported_value': lambda ctx: ctx['sourceProof']['guardProbe'].update(unsupported=Decimal('2')),
            'output_concrete_field': lambda ctx: setattr(ctx['output'], 'engineering_status', 'changed'),
            'step_concrete_field': lambda ctx: setattr(ctx['step'], 'sequence', ctx['step'].sequence + 1),
            'base_concrete_field': lambda ctx: setattr(ctx['base'], 'input_hash', None),
        }
        for name, edit in cases.items():
            with self.subTest(case=name):
                fixture = deepcopy(context)
                fixture['sourceProof']['guardProbe'] = {
                    'nested': {'number': 1, 'flag': True, 'decimal': 1.0, 'zero': -0.0},
                    'list': [1, {'value': 'unchanged'}], 'keys': {'keep': 'value', 'remove': 'value'}}
                fixture['_sourceIntegrity'] = step_context_service._source_context_fingerprint(fixture)
                fixture['_sourceIntegrityGuard'] = step_context_service._SourceIntegrityFastGuard(fixture)
                with patch.object(step_context_service, '_source_context_fingerprint',
                        wraps=step_context_service._source_context_fingerprint) as canonical:
                    self.assertEqual(source_selection(fixture), fixture['sourceProof'])
                    self.assertEqual(canonical.call_count, 0)
                    edit(fixture)
                    with self.assertRaises(PlanStepContextError) as caught:
                        source_selection(fixture)
                    self.assertEqual(caught.exception.code, 'STEP_VERSION_SOURCE_CHANGED')
                    self.assertEqual(canonical.call_count, 1)
        self.assertEqual(source_selection(context)['mainCalculationId'], self.main.pk)
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def test_24_full_value_fast_guard_preserves_canonical_order_alias_and_copy_semantics(self):
        self.activate()
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        context = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache=cache)
        before, changes = self.counts(), connection.connection.total_changes
        guard = context['_sourceIntegrityGuard']
        self.assertIs(deepcopy(guard), guard)
        with self.assertRaises(AttributeError):
            guard._bytes = b''
        copied = deepcopy(context)
        self.assertIs(copied['_sourceIntegrityGuard'], guard)
        with CaptureQueriesContext(connection) as queries, patch.object(step_context_service,
                '_source_context_fingerprint', wraps=step_context_service._source_context_fingerprint) as canonical:
            self.assertEqual(source_selection(copied), context['sourceProof'])
            self.assertEqual(canonical.call_count, 0)
        self.assertEqual(len(queries), 0)
        for name in ('dict_order', 'alias_change', 'canonical_container'):
            with self.subTest(case=name):
                fixture = deepcopy(context)
                shared = {'items': [1, 2, 3]}
                fixture['sourceProof']['guardProbe'] = [shared, shared]
                fixture['_sourceIntegrity'] = step_context_service._source_context_fingerprint(fixture)
                fixture['_sourceIntegrityGuard'] = step_context_service._SourceIntegrityFastGuard(fixture)
                if name == 'dict_order':
                    fixture['base'].trace = dict(reversed(list(fixture['base'].trace.items())))
                    fixture['sourceProof'] = dict(reversed(list(fixture['sourceProof'].items())))
                elif name == 'alias_change':
                    fixture['sourceProof']['guardProbe'][1] = deepcopy(shared)
                else:
                    fixture['sourceProof']['guardProbe'] = tuple(fixture['sourceProof']['guardProbe'])
                with patch.object(step_context_service, '_source_context_fingerprint',
                        wraps=step_context_service._source_context_fingerprint) as canonical:
                    self.assertEqual(source_selection(fixture), fixture['sourceProof'])
                    self.assertEqual(canonical.call_count, 0 if name == 'alias_change' else 1)
        corrupted = deepcopy(context)
        corrupted['_sourceIntegrity'] = 'f' * 64
        with self.assertRaises(PlanStepContextError):
            source_selection(corrupted)
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def test_25_plain_read_retains_original_canonical_guard_without_fast_snapshot(self):
        self.activate()
        before, changes = self.counts(), connection.connection.total_changes
        with patch.object(step_context_service, '_source_context_bytes',
                side_effect=AssertionError('Plain/write caches must not create a fast snapshot')):
            context = resolve_step_context(self.plan, self.step.pk, user=self.actor, read_cache={})
            self.assertNotIn('_sourceIntegrityGuard', context)
            with patch.object(step_context_service, '_source_context_fingerprint',
                    wraps=step_context_service._source_context_fingerprint) as canonical:
                self.assertEqual(source_selection(context)['mainCalculationId'], self.main.pk)
                self.assertEqual(canonical.call_count, 1)
                context['base'].result_hash = 'f' * 64
                with self.assertRaises(PlanStepContextError) as caught:
                    source_selection(context)
                self.assertEqual(caught.exception.code, 'STEP_VERSION_SOURCE_CHANGED')
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def _content_anchor(self):
        return ProductManufacturingOutput.objects.select_related(
            'order_engineering_baseline__sales_order', 'engineering_calculation__source_record',
            'engineering_calculation__sales_order_item__sales_order', 'engineering_calculation__engineering_instance',
            'bom_version__bom', 'order_engineering_instance__sales_order_item__sales_order').get(pk=self.anchor.pk)

    def _read_anchor_content(self, row, cache, **changes):
        args = {'user': self.actor, 'lock': False, 'read_cache': cache, 'plan_id': self.plan.pk}
        args.update(changes)
        return output_service._saved_output_content_read_proof(row, **args)

    def test_26_identical_fixed_anchor_content_shares_only_inside_the_same_plan(self):
        first, independent = self._content_anchor(), self._content_anchor()
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        before, changes = self.counts(), connection.connection.total_changes
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            self._read_anchor_content(first, cache)
            with CaptureQueriesContext(connection) as queries:
                self._read_anchor_content(independent, cache)
            self.assertEqual(content.call_count, 1)
            self.assertEqual(len(queries), 0)
            # This private content proof grants no plan or binding eligibility.
            self._read_anchor_content(independent, cache, plan_id=self.plan.pk + 1)
            self.assertEqual(content.call_count, 2)
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def test_27_all_explicit_anchor_fields_and_nested_values_rerun_native_content_validation(self):
        from .engineering_calculation_service import EngineeringCalculationError
        from .product_bom_detail_projection import ProductBomDetailProjectionError
        cases = {
            'output': lambda row: setattr(row, 'engineering_status', 'changed'),
            'baseline': lambda row: setattr(row.order_engineering_baseline, 'scope_item_count', 999),
            'baseline_order': lambda row: setattr(row.order_engineering_baseline.sales_order, 'order_no', 'changed'),
            'main': lambda row: setattr(row.engineering_calculation, 'input_hash', 'f' * 64),
            'main_source': lambda row: setattr(row.engineering_calculation.source_record, 'content_hash', 'f' * 64),
            'main_item': lambda row: setattr(row.engineering_calculation.sales_order_item, 'id', 999999),
            'main_order': lambda row: setattr(row.engineering_calculation.sales_order_item.sales_order, 'order_no', 'changed'),
            'main_instance': lambda row: setattr(row.engineering_calculation.engineering_instance, 'status', 'inactive'),
            'bom_version': lambda row: setattr(row.bom_version, 'source_calculation_id', 999999),
            'bom': lambda row: setattr(row.bom_version.bom, 'company_id', self.company.pk + 1),
            'output_instance': lambda row: setattr(row.order_engineering_instance, 'status', 'inactive'),
            'output_item': lambda row: setattr(row.order_engineering_instance.sales_order_item, 'quantity', Decimal('9')),
            'output_order': lambda row: setattr(row.order_engineering_instance.sales_order_item.sales_order, 'status', 'closed'),
            'nested_main_trace': lambda row: row.engineering_calculation.trace.update(probe={'nested': [True, -0.0]}),
            'nested_source_payload': lambda row: row.engineering_calculation.source_record.source_payload.update(probe={'nested': [1, 2]}),
        }
        native_errors = (ValidationError, EngineeringCalculationError, ProductBomDetailProjectionError)
        before, changes = self.counts(), connection.connection.total_changes
        for name, edit in cases.items():
            with self.subTest(anchor=name):
                row = self._content_anchor()
                cache = requirement_service._ReadOnlyProofCache(self.actor)
                self._read_anchor_content(row, cache)
                edit(row)
                try:
                    output_service._saved_output_content_integrity(deepcopy(row))
                except native_errors as expected:
                    with patch.object(output_service, '_saved_output_content_integrity',
                            wraps=output_service._saved_output_content_integrity) as content:
                        with self.assertRaises(type(expected)):
                            self._read_anchor_content(row, cache)
                        self.assertEqual(content.call_count, 1)
                else:
                    with patch.object(output_service, '_saved_output_content_integrity',
                            wraps=output_service._saved_output_content_integrity) as content:
                        self._read_anchor_content(row, cache)
                        self.assertEqual(content.call_count, 1)
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def test_28_plain_lock_actor_company_atomic_and_date_boundaries_do_not_reuse_content_success(self):
        row = self._content_anchor()
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        self._read_anchor_content(row, cache)
        foreign_actor = User(pk=self.actor.pk + 1, company_id=self.company.pk)
        foreign_company = User(pk=self.actor.pk, company_id=self.company.pk + 1)
        before, changes = self.counts(), connection.connection.total_changes
        for name, supplied, args in (
                ('default', None, {}), ('plain', {}, {}), ('lock', cache, {'lock': True}),
                ('no_user', cache, {'user': None}), ('no_plan', cache, {'plan_id': None}),
                ('foreign_actor', cache, {'user': foreign_actor}), ('foreign_company', cache, {'user': foreign_company})):
            with self.subTest(scope=name), patch.object(output_service, '_saved_output_content_integrity',
                    wraps=output_service._saved_output_content_integrity) as content:
                self._read_anchor_content(row, supplied, **args)
                self._read_anchor_content(row, supplied, **args)
                self.assertEqual(content.call_count, 2)
        with transaction.atomic():
            ended = requirement_service._ReadOnlyProofCache(self.actor)
            self._read_anchor_content(row, ended)
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            self._read_anchor_content(row, ended)
            self.assertEqual(content.call_count, 1)
        detached = requirement_service._ReadOnlyProofCache(self.actor)
        self._read_anchor_content(row, detached)
        detached._connection = object()
        changed_actor = requirement_service._ReadOnlyProofCache(self.actor)
        self._read_anchor_content(row, changed_actor)
        requirement_service._bind_current_actor(changed_actor, foreign_actor)
        for invalid_cache in (detached, changed_actor):
            with patch.object(output_service, '_saved_output_content_integrity',
                    wraps=output_service._saved_output_content_integrity) as content:
                self._read_anchor_content(row, invalid_cache)
                self._read_anchor_content(row, invalid_cache)
                self.assertEqual(content.call_count, 2)
        dated = requirement_service._ReadOnlyProofCache(self.actor)
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            for today in (date(2026, 10, 1), date(2026, 10, 2)):
                with patch.object(requirement_service, '_today', return_value=today):
                    self._read_anchor_content(row, dated)
            self.assertEqual(content.call_count, 2)
        self.assertEqual((self.counts(), connection.connection.total_changes), (before, changes))

    def test_29_database_write_failed_proof_and_unsupported_guard_never_reuse_content_success(self):
        from .product_bom_detail_projection import ProductBomDetailProjectionError
        row = self._content_anchor()
        unsupported = deepcopy(row)
        unsupported.bom_version.bom.name = object()  # Unconsumed by the native content proof.
        cache = requirement_service._ReadOnlyProofCache(self.actor)
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            self._read_anchor_content(unsupported, cache)
            self._read_anchor_content(unsupported, cache)
            self.assertEqual(content.call_count, 2)
        self.assertFalse(any(isinstance(key, tuple) and key and key[0] == 'fixed_saved_output_content' for key in cache))
        invalid = self._content_anchor()
        invalid.engineering_calculation.input_hash = 'f' * 64
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            for _ in range(2):
                with self.assertRaises(ValidationError):
                    self._read_anchor_content(invalid, cache)
            self.assertEqual(content.call_count, 2)
        self.assertFalse(any(isinstance(key, tuple) and key and key[0] == 'fixed_saved_output_content' for key in cache))
        self._read_anchor_content(row, cache)
        # Isolated fixture only: a same-connection write in the same atomic block.
        BOMItem.objects.filter(bom_version_id=row.bom_version_id).update(quantity=Decimal('9'))
        with patch.object(output_service, '_saved_output_content_integrity',
                wraps=output_service._saved_output_content_integrity) as content:
            for _ in range(2):
                with self.assertRaises(ProductBomDetailProjectionError):
                    self._read_anchor_content(row, cache)
            self.assertEqual(content.call_count, 2)
        self.assertFalse(any(isinstance(key, tuple) and key and key[0] == 'fixed_saved_output_content' for key in cache))



@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE={
    'companyCode': 'LIA', 'orderNo': 'SO-LIA-001', 'lineNo': 1,
})
class FixedOutputContentOutsideAtomicTests(TransactionTestCase):
    def test_explicit_plan_with_none_or_plain_cache_retains_real_native_output_validation(self):
        # Reuse the established real fixture without invoking TestCase's atomic
        # setup. Its native writers create only this disposable test database.
        fixture_type = type('OutsideAtomicNativeOutputFixture', (PlanStepSourceContinuationTests,), {})
        fixture = fixture_type(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        with transaction.atomic():
            fixture_type.setUpTestData()
            fixture.setUp()
        self.assertFalse(connection.in_atomic_block)
        output = fixture._content_anchor()
        before, changes = fixture.counts(), connection.connection.total_changes
        with patch.object(requirement_service._ReadOnlyProofCache, '__init__',
                side_effect=AssertionError('An ordinary validator must not construct a read cache')):
            for supplied in (None, {}):
                with self.subTest(cache=type(supplied).__name__), patch.object(output_service,
                        '_saved_output_content_integrity', wraps=output_service._saved_output_content_integrity) as content:
                    for _ in range(2):
                        result = output_service.validate_selected_output(output, user=fixture.actor,
                            read_cache=supplied, _content_plan_id=fixture.plan.pk)
                        self.assertEqual(result['instance'].pk, fixture.instances[0].pk)
                    self.assertEqual(content.call_count, 2)
        self.assertFalse(connection.in_atomic_block)
        self.assertEqual((fixture.counts(), connection.connection.total_changes), (before, changes))


class ExistingAllocatedStepRefusalTests(TestCase):
    """Existing legal fixture allocates through native services, no fake rows."""
    def test_real_saved_allocation_forbids_switch_and_preserves_complete_snapshot(self):
        fixture = legal_fixture.PlanLegalExtensionAdmissionTests()
        fixture.setUp()
        fixture.allocate()
        before = fixture.f.full_database_snapshot()
        with self.assertRaises(PlanStepContextError) as caught:
            _assert_unallocated(_allocation_rows(fixture.plan), fixture.f.step)
        self.assertEqual(caught.exception.code, 'HANDOFF_ALLOCATED_STEP_BLOCKED')
        self.assertEqual(before, fixture.f.full_database_snapshot())


class EngineeringDocumentSourceProofPrivacyTests(TestCase):
    """Actual review/release ledgers under a read-only SQLite column guard.

    The established release fixture stubs only upstream source completeness
    while creating its native review. Review/release persistence, workflow,
    transition and all readback queries here are real; none is replaced.
    """

    def test_source_proof_readbacks_project_only_public_actor_fields_without_writes(self):
        from .engineering_document_version_release_service import release_readback
        from .engineering_document_version_review_service import review_readback, workflow_projection
        fixture = document_release_fixture.EngineeringDocumentVersionReleaseTests()
        fixture.setUp()
        fixture.release()
        fixture.version.refresh_from_db()
        expected_review = review_readback(fixture.version)
        expected_release = release_readback(fixture.version)
        self.assertTrue(expected_review['completed'])
        self.assertTrue(expected_release['completed'])
        self.assertEqual((expected_review['actorId'], expected_review['actorUsername'], expected_review['actorRealName']),
            (fixture.reviewer.pk, fixture.reviewer.username, fixture.reviewer.real_name))
        self.assertEqual((expected_release['actorId'], expected_release['actorUsername'], expected_release['actorRealName']),
            (fixture.publisher.pk, fixture.publisher.username, fixture.publisher.real_name))
        raw = connection.connection
        before_changes = raw.total_changes
        public_user_columns = {'id', 'username', 'real_name'}
        denied, selected = [], set()
        writes = {getattr(sqlite3, name) for name in (
            'SQLITE_INSERT', 'SQLITE_UPDATE', 'SQLITE_DELETE', 'SQLITE_CREATE_TABLE',
            'SQLITE_DROP_TABLE', 'SQLITE_ALTER_TABLE', 'SQLITE_CREATE_INDEX',
            'SQLITE_DROP_INDEX', 'SQLITE_CREATE_TRIGGER', 'SQLITE_DROP_TRIGGER')}

        def authorize(action, table, column, database, trigger):
            if action in writes:
                denied.append(('write', table, column))
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and table == User._meta.db_table:
                if column not in public_user_columns:
                    denied.append(('user-column', table, column))
                    return sqlite3.SQLITE_DENY
                selected.add(column)
            return sqlite3.SQLITE_OK

        raw.execute('PRAGMA query_only=ON')
        raw.set_authorizer(authorize)
        try:
            # Prove this guard really denies the credential column before any
            # value can be read, rather than passing because no guard ran.
            with self.assertRaises(sqlite3.DatabaseError):
                raw.execute('SELECT password FROM "' + User._meta.db_table + '" LIMIT 1').fetchone()
            self.assertEqual(denied, [('user-column', User._meta.db_table, 'password')])
            denied.clear()
            with CaptureQueriesContext(connection) as queries:
                review = review_readback(fixture.version)
                release = release_readback(fixture.version)
                projection = workflow_projection(fixture.version)
                decision = projection['decisions'][0]
                self.assertEqual(decision.get_deferred_fields(), set())
                self.assertEqual(decision.task.get_deferred_fields(), set())
                self.assertEqual(decision.actor.username, fixture.reviewer.username)
                self.assertEqual(decision.actor.real_name, fixture.reviewer.real_name)
            self.assertEqual(review, expected_review)
            self.assertEqual(release, expected_release)
            self.assertEqual(denied, [])
            self.assertEqual(selected, public_user_columns)
            self.assertTrue(queries.captured_queries)
            self.assertFalse(any('"password"' in query['sql'] for query in queries))
            self.assertEqual(raw.total_changes, before_changes)
        finally:
            raw.set_authorizer(None)
            raw.execute('PRAGMA query_only=OFF')
