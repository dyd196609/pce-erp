"""SIMULATED_FOR_TEST: native plan policy, published anchor and formal references.

Only an isolated Django test database may execute this module. The established
published fixture retains its declared upstream document stubs; no quantity
policy, output validator, configuration proof or preparation proof is mocked.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings

from masterdata.models import CodeRule, MasterDataWriteRequest, UnitOfMeasure
from planning.models import Demand, PlanningRequirement, ProductionPlan
from system.models import Permission, Process, RolePermission, Workshop
from workflow_runtime.state_transitions import create_business_object_with_initial_state
from . import conditional_execution_preparation as policy
from . import operation_input_preparation_service as preparation
from . import operation_requirement_service as operation
from . import operation_workload_source_service as sources
from . import tests_conditional_execution_preparation as conditional_fixtures
from . import tests_engineering_version_handoff_upstream as published_fixtures
from . import tests_operation_requirement as requirement_fixtures
from .daily_capacity_service import SOURCE_RULES_CONTRACT
from .manufacturing_configuration_service import RELEASE
from .manufacturing_routing_context import CONTRACT as ROUTING_CONTEXT_CONTRACT
from .models import (CapacityProductType, OperationInputPreparationDraft, RoutingStep,
                     StandardCapacity, WorkCenter)
from .routing_version_successor_service import ROUTING_PERMISSION


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=published_fixtures.SCOPE)
class OperationQuantityPolicyTests(TestCase):
    initial = requirement_fixtures.OperationRequirementTests.initial
    advance = requirement_fixtures.OperationRequirementTests.advance
    readonly = conditional_fixtures.ConditionalExecutionPreparationTests.readonly
    rejected = conditional_fixtures.ConditionalExecutionPreparationTests.rejected

    def setUp(self):
        published = published_fixtures.EngineeringVersionHandoffUpstreamTests(methodName='runTest')
        native_create = RoutingStep.objects.create

        def draft_steps(**fields):
            # Both abstract steps are built while the established route fixture
            # is still draft. Published route content is never amended.
            first = native_create(**fields)
            self.reference_uom = UnitOfMeasure.objects.create(company_id=first.operation.company_id,
                code='SIM-QP-M', name='Abstract length unit', dimension='length')
            reference_operation = Process.objects.create(company=first.operation.company,
                code='SIM-QP-REFERENCE', name='Abstract measured operation', calculation_uom=self.reference_uom)
            self.reference_step = native_create(routing_version=first.routing_version, sequence=2,
                operation=reference_operation, predecessor_sequences=[1])
            return first

        with patch.object(RoutingStep.objects, 'create', side_effect=draft_steps):
            published.setUp()
        self.addCleanup(published.doCleanups)
        self.user, self.company, self.role = published.executor, published.company, published.executing_role
        self.step = published.category_routing_version.steps.get(sequence=1)
        self.step.operation.calculation_uom = published.uom
        self.step.operation.save(update_fields=('calculation_uom',))
        for code in (preparation.VIEW, preparation.CREATE, preparation.UPDATE, preparation.CAPACITY,
                operation.VIEW, operation.EXECUTE, operation.PLAN_VIEW, ROUTING_PERMISSION, RELEASE):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'module': 'PDE'})
            RolePermission.objects.get_or_create(role=self.role, permission=permission)
        output, _ = published._generate()
        published._release(output, 'sim-quantity-policy-anchor')
        demand = create_business_object_with_initial_state(model=Demand, initial_state='draft',
            demand_no='SIM-QP-DEMAND', source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(published.order.pk), source_document_no=published.order.order_no,
            sales_order_item=published.order_item, manufacturing_output=output, material=published.finished,
            required_qty=1, required_date=date.today(), department=published.department,
            reason='SIMULATED_FOR_TEST quantity policy anchor', created_by=self.user)
        requirement = PlanningRequirement.objects.create(requirement_no='SIM-QP-REQ', demand=demand,
            material=published.finished, demand_qty=1, available_qty=0, net_required_qty=1,
            required_date=date.today(), supply_type='production', status='confirmed', created_by=self.user)
        self.plan = ProductionPlan.objects.create(plan_no='SIM-QP-PLAN', planning_requirement=requirement,
            material=published.finished, planned_qty=1, required_date=date.today(), source_id=str(requirement.pk),
            confirmed_by=self.user, status='confirmed')
        self.product_type = CapacityProductType.objects.create(company=self.company, code='SIM-QP-TYPE',
            name='Abstract policy product type', product_category=published.category,
            manufacturing_process_type=published.process_type)
        self.pcs, self.rule_counter = published.uom, 0
        self.f = SimpleNamespace(output=output, source_calc=published.calculation, baseline=published.baseline,
            item=published.order_item, area=published.uom,
            full_database_snapshot=lambda: conditional_fixtures.snapshot_fixtures.ClassifiedFactEorTests.full_database_snapshot(self))
        self.scope = {'companyId': self.company.pk, 'productionPlanId': self.plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': published.calculation.pk,
            'salesOrderItemId': published.order_item.pk, 'baselineId': published.baseline.pk,
            'routingVersionId': output.routing_version_id, 'routingStepId': self.step.pk,
            'operationId': self.step.operation_id, 'productTypeId': self.product_type.pk}
        CodeRule.objects.get_or_create(company_id=self.company.pk, entity_type='production_engineering_calculation',
            defaults={'prefix': 'SIM-QP-', 'date_format': '', 'seq_length': 4})
        workshop = Workshop.objects.create(company=self.company, department=published.department,
            code='SIM-QP-WS', name='Abstract policy workshop')
        self.center = WorkCenter.objects.create(company=self.company, workshop=workshop,
            department=published.department, code='SIM-QP-WC', name='Abstract policy resource')
        manifest = {'contractVersion': SOURCE_RULES_CONTRACT, 'sourceSha256': sha256(b'SIMULATED_FOR_TEST').hexdigest(),
            'productTypeCode': self.product_type.code, 'effectiveDate': date.today().isoformat(),
            'businessFactReference': 'SIMULATED_FOR_TEST explicit complete applicability',
            'applicableOperationIds': sorted([self.step.operation_id, self.reference_step.operation_id]),
            'nonApplicableOperationIds': [], 'auxiliaryOperationIds': [self.step.operation_id],
            'preparationDays': '0.1', 'transferDays': '0.1'}
        capacities = []
        for step, uom, amount, status in ((self.step, self.pcs, 0, 'zero_capacity'),
                (self.reference_step, self.reference_uom, 500, 'measured')):
            capacities.append(StandardCapacity.objects.create(company=self.company, code=f'SIM-QP-CAP-{step.pk}',
                name='Abstract formally declared capacity', resource_scope='work_center', work_center=self.center,
                operation=step.operation, product_type=self.product_type, uom=uom,
                measurement_status=status, quantity=Decimal(amount), time_basis='day', time_basis_quantity=1,
                time_unit='DAY', preparation_days=Decimal('0.1'), transfer_days=Decimal('0.1'),
                effective_from=date.today(), conditions={'apsSourceRules': deepcopy(manifest),
                    'sourceSha256': manifest['sourceSha256'], 'sourceProductTypeCode': self.product_type.code}))
        self.capacity, reference_capacity = capacities
        producer = requirement_fixtures.OperationRequirementTests.make_rule(self,
            self.reference_step.operation, self.reference_uom, 'abstract_reference_length', output_domain='DERIVED_FACT')
        from .models import ManufacturingMode
        mode = self.initial(ManufacturingMode, 'draft', company=self.company, code='SIM-QP-MODE',
            name='Abstract length mode', version='V1', uom=self.reference_uom, effective_from=date.today())
        self.advance(mode, 'reviewed')
        self.advance(mode, 'released')
        configured = sources.configure(user=self.user, operation_id=self.reference_step.operation_id,
            payload={'producerRuleId': producer.pk, 'modeId': mode.pk, 'productTypeId': self.product_type.pk,
                'workCenterId': self.center.pk, 'standardCapacityId': reference_capacity.pk,
                'ruleCode': 'SIM-QP-SOURCE', 'ruleName': 'Abstract statistical source', 'version': 'V1',
                'effectiveFrom': date.today().isoformat(), 'traceEquals': {},
                'routingContext': {'contractVersion': ROUTING_CONTEXT_CONTRACT,
                    'routingId': output.routing_version.routing_id,
                    'routingVersionId': output.routing_version_id, 'routingStepId': self.reference_step.pk}},
            reason='SIMULATED_FOR_TEST native source publication without any quantity copying')
        self.source_rule_id = configured['configuration']['sources'][0]['ruleId']
        self.context = self.build_context()
        self.basis = policy.build_quantity_policy_basis(context=self.context,
            reference='SIMULATED_FOR_TEST/quantity-policy', reference_sha256=sha256(b'quantity-policy').hexdigest(),
            exact_statement='常规必经配套；图纸和现场决定范围；不单独统计计划投产量或实际产量；统计单位引用同路线正式配置。')

    def build_context(self, **changes):
        args = dict(user=self.user, exact_scope=self.scope, statistical_routing_step_id=self.reference_step.pk,
            standard_capacity_id=self.capacity.pk)
        args.update(changes)
        return policy.build_quantity_policy_context(**args)

    def save(self, **changes):
        args = dict(user=self.user, exact_scope=deepcopy(self.scope), business_basis=deepcopy(self.basis),
            expected_context_hash=self.context['context_hash'], expected_revision=None,
            idempotency_key='sim-quantity-policy', reason='SIMULATED_FOR_TEST native quantity policy')
        args.update(changes)
        return preparation.save_preparation(**args)

    def read(self):
        return preparation.read_preparation(user=self.user, exact_scope=self.scope)

    def test_native_save_read_replay_preserve_null_quantities_and_formal_capacity(self):
        before_capacity = StandardCapacity.objects.filter(pk=self.capacity.pk).values().get()
        saved = self.save()
        result = self.readonly(self.read)
        quantity = result['quantityPolicy']
        self.assertEqual(result['statusCode'], policy.QUANTITY_MODE)
        self.assertEqual(result['context']['contractVersion'], policy.QUANTITY_CONTRACT)
        self.assertEqual(quantity['exactScope'], self.scope)
        self.assertTrue(quantity['formalPolicyValidated'])
        self.assertEqual(quantity['nullReason'], policy.QUANTITY_MODE)
        self.assertEqual(quantity['statisticalUomReference']['uomId'], self.reference_uom.pk)
        self.assertNotEqual(quantity['statisticalUomReference']['uomId'], self.capacity.uom_id)
        self.assertRegex(quantity['statisticalUomReference']['proofHash'], r'^[0-9a-f]{64}$')
        for field in ('plannedQuantity', 'actualQuantity', 'sourceQuantity', 'inputQuantity', 'capacityQuantity'):
            self.assertIsNone(result[field])
        self.assertEqual(result['capacityBusinessValue'], 0)
        self.assertEqual(result['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(result['capacityResolution']['code'], 'FORMAL_AUXILIARY_ZERO_REFERENCE')
        self.assertEqual(before_capacity, StandardCapacity.objects.filter(pk=self.capacity.pk).values().get())
        self.assertEqual(result['remainingItems'], [])
        self.assertEqual(result['objectCoverage'], policy.QUANTITY_COVERAGE)
        self.assertEqual(result['businessBasis'], self.basis)
        self.assertEqual(result['statusTransitionCount'], len(result['statusTransitionHistory']))
        self.assertTrue(result['auditIds'])
        for field in ('readyForGeneration', 'readyForAllocation', 'readyForScheduling', 'formalRulePublished'):
            self.assertFalse(result[field])
        replay = self.readonly(self.save)
        self.assertTrue(replay['idempotentReplay'])
        self.assertEqual(replay['recordId'], saved['recordId'])
        resolved = self.readonly(lambda: policy.resolve_quantity_policy(self.step, self.plan,
            manufacturing_output=self.f.output, engineering_calculation=self.f.source_calc,
            order_engineering_baseline=self.f.baseline, bom_version=self.f.output.bom_version))
        self.assertEqual(resolved, quantity)
        self.assertIsNone(policy.resolve_conditional_execution(self.step, self.plan))

    def test_quantities_client_units_scope_claims_and_selections_are_rejected_without_writes(self):
        for key, value in (('plannedQuantity', 0), ('actualQuantity', '1'), ('nullReason', None),
                ('measurementMode', 'UNKNOWN'), ('scopeDetermination', 'OBJECTS'),
                ('objectCoverageClaimed', True), ('objectCoverageClaimed', 0), ('uomId', self.reference_uom.pk)):
            changed = deepcopy(self.basis)
            changed['quantityPolicy'][key] = value
            with self.subTest(key=key, value=value):
                self.rejected(lambda: self.save(business_basis=changed), 'PREPARATION_QUANTITY_POLICY_INVALID')
        self.rejected(lambda: self.save(work_center_id=self.center.pk), 'PREPARATION_CONDITIONAL_INVALID')
        self.rejected(lambda: self.save(draft_selection={'basisQuantity': '0'}), 'PREPARATION_CONDITIONAL_INVALID')

    def test_current_formal_reference_and_capacity_corruption_fail_closed(self):
        self.save()
        from .models import EngineeringRuleDefinition
        for model, pk, values in ((UnitOfMeasure, self.reference_uom.pk, {'is_active': False}),
                (EngineeringRuleDefinition, self.source_rule_id, {'status': 'obsolete'}),
                (StandardCapacity, self.capacity.pk, {'quantity': 1, 'measurement_status': 'measured'}),
                (StandardCapacity, self.capacity.pk, {'uom_id': self.reference_uom.pk})):
            with self.subTest(model=model.__name__, values=values), transaction.atomic():
                model.objects.filter(pk=pk).update(**values)
                self.rejected(self.read)
                transaction.set_rollback(True)
        self.rejected(lambda: self.build_context(statistical_routing_step_id=self.step.pk),
            'PREPARATION_QUANTITY_POLICY_INVALID')
        self.rejected(lambda: self.build_context(standard_capacity_id=self.capacity.pk + 99999),
            'PREPARATION_QUANTITY_POLICY_CAPACITY_INVALID')

    def test_existing_conditional_policy_is_not_converted_or_overwritten(self):
        context = policy.build_conditional_context(user=self.user, exact_scope=self.scope)
        basis = policy.build_conditional_basis(context=context, reference='SIMULATED_FOR_TEST/conditional',
            reference_sha256=sha256(b'conditional').hexdigest(), exact_statement='原待触发政策保留',
            execution_statement='模拟未领料未开工')
        preparation.save_preparation(user=self.user, exact_scope=self.scope, business_basis=basis,
            expected_context_hash=context['context_hash'], idempotency_key='sim-previous-conditional',
            reason='SIMULATED_FOR_TEST protect existing policy')
        self.rejected(self.save, 'PREPARATION_CONDITIONAL_CONFLICT')
        self.assertEqual(self.read()['businessBasis'], basis)

    def test_ledger_or_audit_corruption_cannot_restore_an_unrecorded_or_legacy_state(self):
        saved = self.save()
        from system.models import OrganizationOperatingAuditRecord
        for model, pk, values in ((MasterDataWriteRequest, saved['writeRequestId'], {'status': 'RESERVED'}),
                (OrganizationOperatingAuditRecord, saved['auditId'], {'after_snapshot': {}})):
            with self.subTest(model=model.__name__), transaction.atomic():
                model.objects.filter(pk=pk).update(**values)
                self.rejected(self.read)
                self.rejected(lambda: policy.resolve_quantity_policy(self.step, self.plan))
                transaction.set_rollback(True)

    def test_existing_requirement_blocks_policy_without_hiding_saved_quantities(self):
        fact = self.f.source_calc.derived_facts.get()
        rule = requirement_fixtures.OperationRequirementTests.make_rule(self, self.step.operation,
            self.pcs, fact.canonical_field, basis='SOURCE_SCOPE_TOTAL')
        operation.OperationRequirementService.generate(user=self.user, source_calculation_id=fact.calculation_id,
            source_fact_id=fact.pk, rule_id=rule.pk, idempotency_key='sim-quantity-existing-eor',
            reason='SIMULATED_FOR_TEST preserve existing EOR')
        self.rejected(self.save, 'PREPARATION_CONDITIONAL_PERSISTENCE_CONFLICT')

    def test_routing_permission_remains_required_for_write_and_replay(self):
        saved = self.save()
        RolePermission.objects.filter(role=self.role, permission__code=ROUTING_PERMISSION).delete()
        self.rejected(self.save, 'PERMISSION_DENIED')
        self.rejected(lambda: self.save(idempotency_key='sim-quantity-no-routing'), 'PERMISSION_DENIED')
        self.assertEqual(OperationInputPreparationDraft.objects.get(pk=saved['recordId']).revision, 1)

    def test_quantity_policy_is_immutable_but_original_basis_entries_are_append_only(self):
        saved = self.save()
        changed = deepcopy(self.basis)
        changed['quantityPolicy']['capacityReference']['standardCapacityId'] += 99999
        self.rejected(lambda: self.save(business_basis=changed, expected_revision=saved['revision'],
            idempotency_key='sim-quantity-replace-policy'))
        appended = deepcopy(self.basis)
        entry = deepcopy(appended['entries'][0])
        entry.update(reference='SIMULATED_FOR_TEST/additional-policy-basis',
            referenceSha256=sha256(b'additional').hexdigest(), exactStatement='补充原文，不改写正式数量政策。')
        appended['entries'].append(entry)
        updated = self.save(business_basis=appended, expected_revision=saved['revision'],
            idempotency_key='sim-quantity-append-basis')
        self.assertEqual(updated['revision'], 2)
        self.assertEqual(self.read()['businessBasis'], appended)
