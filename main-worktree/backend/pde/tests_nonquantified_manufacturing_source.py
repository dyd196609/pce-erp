"""SIMULATED_FOR_TEST: structured non-quantified manufacturing, real native chain.

Only the named, pre-Django guarded disposable SQLite runner may execute this
module. Existing fixtures are composed, never inherited as additional suites.
No successful source, preparation, generation or read result is mocked.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json

from django.db import connection, IntegrityError, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from masterdata.models import CodeRule
from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import SalesOrderItem
from system.models import Company, OrganizationOperatingAuditRecord, RolePermission, User
from workflow_runtime.models import BusinessStateTransition
from . import operation_input_preparation_service as preparation
from . import operation_requirement_service as native
from . import operation_workload_source_service as workload
from . import tests_manufacturing_eor_configuration as quantitative_fixtures
from . import tests_operation_requirement as legacy_fixtures
from . import tests_preparation_ruling_capacity_consumption as ruling_fixtures
from .models import (EngineeringOperationRequirement, EngineeringRuleDefinition,
    OperationInputPreparationDraft, ProductionPlanOperationRequirementAllocation, StandardCapacity)


MODE = 'PREPARATION_NON_QUANTIFIED'
DEFAULT = object()


class NonQuantifiedManufacturingSourceTests(TestCase):
    def setUp(self):
        self.fixture = ruling_fixtures.PreparationRulingCapacityConsumptionTests(methodName='runTest')
        self.fixture.setUp()
        self.prep_case = self.fixture.case
        self.source_case = self.prep_case.case
        self.f, self.plan = self.fixture.f, self.fixture.plan
        self.user, self.step, self.operation = self.fixture.user, self.fixture.step, self.fixture.operation
        self.origin = self.source_case.fixture.fixture.extension
        self.facts = list(self.origin.derived_facts.select_related('source_detail__rule', 'uom').order_by('sequence'))
        self.context = {'productionPlanId': self.plan.pk, 'routingStepId': self.step.pk}
        self.routing = {'contractVersion': 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1',
            'routingId': self.f.route.pk, 'routingVersionId': self.f.version.pk, 'routingStepId': self.step.pk}
        self.rule = None

    def snapshot(self):
        return self.f.full_database_snapshot()

    def confirm_zero(self):
        return self.fixture.confirm_zero()

    def payload(self, **changes):
        value = self.source_case.payload(ruleCode='SIM-NONQUANT-SOURCE',
            ruleName='Simulated structured non-quantified operation input',
            capacityMode=MODE, standardCapacityId=None)
        value.update(changes)
        return value

    def configure(self, *, context=DEFAULT, user=None, **changes):
        saved = workload.configure(user=user or self.user, operation_id=self.operation.pk,
            payload=self.payload(**changes), reason='SIMULATED_FOR_TEST configured source and precise zero ruling',
            generation_context=self.context if context is DEFAULT else context)
        self.rule = EngineeringRuleDefinition.objects.get(pk=saved['nativeResult']['rules'][0]['id'])
        return saved

    def ready(self, fact=None, *, context=DEFAULT, user=None):
        return native.OperationRequirementService.generate_readiness(user=user or self.user,
            source_calculation_id=self.origin.pk, source_fact_id=(fact or self.facts[0]).pk,
            rule_id=self.rule.pk, generation_context=self.context if context is DEFAULT else context)

    def generate(self, fact=None, *, context=DEFAULT, key=None):
        fact = fact or self.facts[0]
        return native.OperationRequirementService.generate(user=self.user,
            source_calculation_id=self.origin.pk, source_fact_id=fact.pk, rule_id=self.rule.pk,
            generation_context=self.context if context is DEFAULT else context,
            idempotency_key=key or f'sim-nonquant-generated-{fact.pk}', reason='SIMULATED_FOR_TEST native generation')

    def source_read(self, *, plan=None, step=None):
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            value = workload.read_for_plan(user=self.user, production_plan_id=(plan or self.plan).pk,
                routing_step_id=(step or self.step).pk)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(row['sql'].lstrip().upper().startswith(
            ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP')) for row in queries))
        return value

    def assert_ready_rejected(self, *, context=DEFAULT, user=None, expected=None):
        before = self.snapshot()
        try:
            result = self.ready(context=context, user=user)
        except native.OperationRequirementError as error:
            code = error.code
        else:
            self.assertFalse(result['ready'], result)
            self.assertEqual(result['businessWriteCount'], 0)
            code = result['blockers'][0]['code']
        self.assertEqual(before, self.snapshot())
        if expected is not None:
            self.assertEqual(code, expected)
        return code

    def assert_configuration_rejected(self, *, context=DEFAULT, expected=None, **changes):
        before = self.snapshot()
        with self.assertRaises(workload.OperationWorkloadSourceError) as caught:
            self.configure(context=context, **changes)
        self.assertEqual(before, self.snapshot())
        if expected is not None:
            self.assertEqual(caught.exception.code, expected)
        return caught.exception.code

    def raw(self, obj, **fields):
        names, values = [], []
        for field, value in fields.items():
            names.append(connection.ops.quote_name(obj._meta.get_field(field).column) + '=%s')
            values.append(json.dumps(value) if isinstance(value, (dict, list)) else value)
        table = connection.ops.quote_name(obj._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {table} SET {", ".join(names)} WHERE id=%s', [*values, obj.pk])

    def other_plan(self):
        item = SalesOrderItem.objects.create(sales_order=self.f.order, line_no=2,
            material=self.f.item.material, quantity=self.plan.planned_qty, uom=self.f.pcs,
            required_date=date.today(), engineering_mode='ORDER_ENGINEERED')
        demand = self.f.initial(Demand, 'draft', demand_no='SIM-NONQUANT-OTHER-DEMAND',
            source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(self.f.order.pk), source_document_no=self.f.order.order_no,
            sales_order_item=item, material=self.f.item.material, required_qty=self.plan.planned_qty,
            required_date=self.plan.required_date, department=self.f.department,
            reason='SIMULATED_FOR_TEST separate legitimate plan, no preparation context reuse',
            acceptance_marker='SIMULATED_FOR_TEST', created_by=self.user)
        self.f.advance(demand, 'confirmed')
        requirement = self.f.initial(PlanningRequirement, 'draft',
            requirement_no='SIM-NONQUANT-OTHER-REQ', demand=demand, material=self.plan.material,
            demand_qty=self.plan.planned_qty, available_qty=0, net_required_qty=self.plan.planned_qty,
            required_date=self.plan.required_date, supply_type='production',
            calculation_facts={'sourceKind': 'SIMULATED_FOR_TEST'}, created_by=self.user)
        self.f.advance(requirement, 'calculated')
        self.f.advance(requirement, 'confirmed')
        value = self.f.initial(ProductionPlan, 'draft', plan_no='SIM-NONQUANT-OTHER-PLAN',
            planning_requirement=requirement, material=self.plan.material,
            planned_qty=self.plan.planned_qty, required_date=self.plan.required_date,
            source_id=str(requirement.pk), confirmed_by=self.user)
        self.f.advance(value, 'confirmed')
        return value

    def test_real_configuration_publication_three_native_generations_and_readback(self):
        current = self.confirm_zero()
        self.assertNotEqual(self.step.pk, 804)
        self.assertCountEqual([Decimal(row.value['decimal']) for row in self.facts],
            [Decimal('1.5'), Decimal('.5'), Decimal('2')])
        expected_by_object = {row.trace['baselineItemId']: Decimal(row.value['decimal'])
            for row in self.f.facts}
        self.assertEqual({row.trace['baselineItemId']: Decimal(row.value['decimal'])
            for row in self.facts}, expected_by_object)
        self.assertEqual(len({row.pk for row in self.facts}), 3)
        self.assertFalse(StandardCapacity.objects.filter(company=self.f.company,
            product_type=self.f.product_type, operation=self.operation).exists())
        old_requirements = list(EngineeringOperationRequirement.objects.order_by('pk').values())
        counts = tuple(model.objects.count() for model in
            (EngineeringRuleDefinition, OrganizationOperatingAuditRecord, BusinessStateTransition))
        codes = list(CodeRule.objects.order_by('pk').values())
        self.configure()
        self.assertEqual(tuple(model.objects.count() for model in
            (EngineeringRuleDefinition, OrganizationOperatingAuditRecord, BusinessStateTransition)),
            (counts[0] + 1, counts[1] + 3, counts[2] + 3))
        self.assertEqual(list(CodeRule.objects.order_by('pk').values()), codes)
        self.assertEqual(self.rule.status, 'released')
        manufacturing = self.rule.specification['manufacturing']
        self.assertEqual(manufacturing['capacityMode'], MODE)
        self.assertIsNone(manufacturing['standardCapacityId'])
        self.assertNotIn('productionPlanId', manufacturing)
        self.assertNotIn('recordId', manufacturing)
        self.assertNotIn('generationContext', manufacturing)
        self.assertEqual(list(BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition',
            object_id=self.rule.pk).order_by('version').values_list('source_state', 'target_state')),
            [('', 'draft'), ('draft', 'reviewed'), ('reviewed', 'released')])
        before = self.snapshot()
        self.configure()
        self.assertEqual(before, self.snapshot())
        generated, keys = [], []
        for fact in self.facts:
            before_ready = self.snapshot()
            ready = self.ready(fact)
            self.assertTrue(ready['ready'], ready)
            self.assertEqual(Decimal(ready['evaluatedOutput']['value']), Decimal(fact.value['decimal']))
            self.assertEqual(before_ready, self.snapshot())
            keys.append(ready['generationKey'])
            saved = self.generate(fact)
            obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
            obj.refresh_from_db()
            self.assertEqual(obj.manufacturing_mode_id, self.f.mode.pk)
            self.assertEqual(obj.work_center_id, self.f.center.pk)
            self.assertIsNone(obj.standard_capacity_id)
            self.assertEqual(obj.trace['manufacturingReferenceType'], MODE)
            proof = obj.trace['manufacturingPreparationContext']
            self.assertEqual(proof['recordId'], current['recordId'])
            self.assertEqual(proof['revision'], current['revision'])
            self.assertEqual(proof['exactScope'], self.prep_case.scope)
            self.assertEqual(obj.generation_key, ready['generationKey'])
            self.assertEqual(obj.workload_quantity, Decimal(fact.value['decimal']))
            self.assertEqual((obj.source_calculation_id, obj.source_fact_id), (self.origin.pk, fact.pk))
            generated.append(obj)
            before_replay = self.snapshot()
            self.assertEqual(self.generate(fact)['operationRequirementId'], obj.pk)
            self.assertEqual(before_replay, self.snapshot())
        self.assertEqual(len(set(keys)), 3)
        read = self.source_read()
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
        self.assertEqual({row['id'] for row in read['formalRequirements']['items']}, {row.pk for row in generated})
        self.assertIsNone(read['savedAllocations']['quantity'])
        self.assertEqual(list(EngineeringOperationRequirement.objects.filter(
            pk__in=[row['id'] for row in old_requirements]).order_by('pk').values()), old_requirements)

    def test_exact_routing_scope_uses_explicit_plan_and_persisted_native_context(self):
        self.confirm_zero()
        self.configure(ruleCode='SIM-NONQUANT-EXACT-STEP', routingContext=deepcopy(self.routing))
        self.assertEqual(self.rule.specification['manufacturing']['routingContext'], self.routing)
        ready = self.ready()
        self.assertTrue(ready['ready'], ready)
        saved = self.generate()
        obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
        native_routing = obj.calculation.trace['sourceSnapshot']['manufacturing']['routingContext']
        self.assertEqual({key: native_routing[key] for key in self.routing}, self.routing)
        self.assertEqual(native_routing, ready['sourceSnapshot']['manufacturing']['routingContext'])
        self.assertEqual((native_routing['sourceEngineeringCalculationId'], native_routing['sourceFactCalculationId'],
            native_routing['sourceFactId'], native_routing['manufacturingOutputId']),
            (self.f.source_calc.pk, self.origin.pk, self.facts[0].pk, self.f.output.pk))
        self.assertEqual(native_routing['stepApplicability']['result'], 'REQUIRED')
        self.assertEqual(native_routing['formalSourceHashes']['engineeringCalculationInputHash'], self.f.source_calc.input_hash)
        self.assertEqual(native_routing['formalSourceHashes']['engineeringCalculationResultHash'], self.f.source_calc.result_hash)
        self.assertEqual(obj.trace['manufacturingPreparationContext']['exactScope'], self.prep_case.scope)
        self.assertIn(obj.pk, [row['id'] for row in self.source_read()['formalRequirements']['items']])
        for context in ({'productionPlanId': self.plan.pk, 'routingStepId': self.f.source_other_step.pk},
                {'productionPlanId': self.other_plan().pk, 'routingStepId': self.step.pk}):
            with self.subTest(context=context):
                self.assert_ready_rejected(context=context)

    def test_native_single_and_group_allocation_readiness_preserve_nonquantified_proof(self):
        self.confirm_zero()
        self.configure()
        ids = [self.generate(fact)['operationRequirementId'] for fact in self.facts]
        contributions = [{'operationRequirementId': ident, 'routingStepId': self.step.pk,
            'idempotencyKey': f'sim-nonquant-readonly-allocation-{ident}'} for ident in ids]
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            singles = [native.OperationRequirementService.allocation_readiness(user=self.user,
                production_plan_id=self.plan.pk, operation_requirement_id=ident,
                routing_step_id=self.step.pk) for ident in ids]
            group = native.OperationRequirementService.allocation_group_readiness(user=self.user,
                production_plan_id=self.plan.pk, contributions=contributions)
        for result in singles:
            self.assertTrue(result['dataReady'], result)
            self.assertTrue(result['canSave'], result)
        self.assertTrue(group['ready'], group)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(row['sql'].lstrip().upper().startswith(
            ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP')) for row in queries))
        other = self.other_plan()
        before = self.snapshot()
        wrong = native.OperationRequirementService.allocation_group_readiness(user=self.user,
            production_plan_id=other.pk, contributions=contributions)
        self.assertFalse(wrong['ready'], wrong)
        self.assertIn('ALLOCATION_SOURCE_MISMATCH', {row['code'] for row in wrong['blockers']}, wrong)
        # The public group rejects this different line's plan at its original
        # fixed-output gate. Separately exercise the new exact-scope guard on
        # the real saved requirement and the real confirmed other plan. The
        # OneToOne planning model cannot create two valid plans for one line;
        # this is not described as that unsupported fixture configuration.
        req = EngineeringOperationRequirement.objects.get(pk=ids[0])
        context = native._validate_requirement(req, self.f.company.pk, user=self.user)
        self.assertEqual(req.trace['manufacturingPreparationContext']['exactScope']['productionPlanId'], self.plan.pk)
        self.assertEqual(other.status, 'confirmed')
        self.assertNotEqual(other.pk, self.plan.pk)
        with self.assertRaises(native.OperationRequirementError) as caught:
            native._plan_source_consistency(self.f.company.pk, other, req,
                native_context=context, routing_step=self.step)
        self.assertEqual(caught.exception.code, 'NON_QUANTIFIED_CONTEXT_MISMATCH')
        self.assertEqual(before, self.snapshot())

    def test_real_native_allocation_save_and_independent_formal_load_readback(self):
        self.confirm_zero()
        self.configure()
        ids = [self.generate(fact)['operationRequirementId'] for fact in self.facts]
        requirements_before = list(EngineeringOperationRequirement.objects.filter(pk__in=ids).order_by('pk').values())
        plan_before = list(ProductionPlan.objects.filter(pk=self.plan.pk).values())
        contributions = [{'operationRequirementId': ident, 'routingStepId': self.step.pk,
            'idempotencyKey': f'sim-nonquant-actual-allocation-{ident}'} for ident in ids]
        saved = native.OperationRequirementService.allocate_group(user=self.user,
            production_plan_id=self.plan.pk, contributions=contributions,
            reason='SIMULATED_FOR_TEST real non-quantified allocation persistence and independent readback')
        self.assertTrue(saved['atomic'])
        self.assertEqual(saved['businessWriteCount'], 3)
        allocation_ids = {row['allocationId'] for row in saved['allocations']}
        self.assertEqual(len(allocation_ids), 3)
        for row in ProductionPlanOperationRequirementAllocation.objects.filter(pk__in=allocation_ids):
            self.assertEqual((row.production_plan_id, row.routing_step_id), (self.plan.pk, self.step.pk))
            self.assertIn(row.operation_requirement_id, ids)
            req = row.operation_requirement
            self.assertEqual((req.manufacturing_mode_id, req.work_center_id, req.standard_capacity_id),
                (self.f.mode.pk, self.f.center.pk, None))
            self.assertEqual(row.allocated_quantity, req.workload_quantity)
            self.assertEqual(row.source_snapshot['generationKey'], req.generation_key)
            self.assertEqual(row.source_snapshot['sourceFactId'], req.source_fact_id)
            self.assertEqual(row.source_snapshot['planEngineeringSource']['sourceEngineeringCalculationId'],
                self.f.source_calc.pk)
        before = self.snapshot()
        read = native.OperationRequirementService.read(user=self.user, production_plan_id=self.plan.pk)
        self.assertTrue(read['passed'], read)
        self.assertEqual({row['allocationId'] for row in read['allocations']}, allocation_ids)
        source_read = self.source_read()
        self.assertEqual(source_read['savedAllocations']['statusCode'], 'SAVED', source_read['savedAllocations'])
        self.assertEqual(source_read['savedAllocations']['blockers'], [], source_read['savedAllocations'])
        self.assertEqual({row['allocationId'] for row in source_read['savedAllocations']['items']}, allocation_ids)
        self.assertEqual(Decimal(source_read['savedAllocations']['quantity']), Decimal('4'))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list(EngineeringOperationRequirement.objects.filter(pk__in=ids).order_by('pk').values()),
            requirements_before)
        self.assertEqual(list(ProductionPlan.objects.filter(pk=self.plan.pk).values()), plan_before)

    def test_missing_partial_and_malformed_context_cannot_publish_or_generate(self):
        self.confirm_zero()
        for context in (None, {}, {'productionPlanId': self.plan.pk}, {'routingStepId': self.step.pk},
                {'productionPlanId': True, 'routingStepId': self.step.pk},
                {'productionPlanId': self.plan.pk, 'routingStepId': str(self.step.pk)}):
            with self.subTest(context=context):
                self.assert_configuration_rejected(context=context)
        self.configure()
        for context in (None, {}, {'productionPlanId': self.plan.pk}, {'routingStepId': self.step.pk}):
            with self.subTest(generationContext=context):
                self.assert_ready_rejected(context=context, expected='NON_QUANTIFIED_CONTEXT_REQUIRED')
                before = self.snapshot()
                with self.assertRaises(native.OperationRequirementError):
                    self.generate(context=context)
                self.assertEqual(before, self.snapshot())

    def test_existing_http_configuration_rejects_malformed_context_without_any_write(self):
        self.confirm_zero()
        client = APIClient()
        client.force_authenticate(user=self.user)
        for context in ({'productionPlanId': self.plan.pk},
                {'productionPlanId': True, 'routingStepId': self.step.pk},
                {'productionPlanId': self.plan.pk, 'routingStepId': str(self.step.pk)}):
            with self.subTest(generationContext=context):
                before = self.snapshot()
                with CaptureQueriesContext(connection) as queries:
                    response = client.post('/api/pde/a1-foundation/operations/', {'action': 'configureOperationWorkloadSource',
                        'operationId': self.operation.pk, 'reason': 'SIMULATED_FOR_TEST invalid explicit context',
                        **self.payload(), 'generationContext': context}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data['code'], 'NON_QUANTIFIED_CONTEXT_REQUIRED')
                self.assertEqual(before, self.snapshot())
                self.assertFalse(any(row['sql'].lstrip().upper().startswith(
                    ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP')) for row in queries))

    def test_missing_unconfirmed_and_withdrawn_rulings_do_not_authorize_source(self):
        self.f.source_capacity.delete()
        self.assert_configuration_rejected()
        self.prep_case.save()
        self.assert_configuration_rejected()
        self.prep_case.correct_capacity()
        self.configure()
        self.prep_case.correct_capacity(confirmed_zero=False, revision=2, key='sim-nonquant-withdraw')
        self.assert_ready_rejected(expected='NON_QUANTIFIED_PREPARATION_INVALID')

    def test_foreign_company_wrong_version_step_and_other_plan_are_rejected(self):
        self.confirm_zero()
        self.configure()
        for context in ({'productionPlanId': self.plan.pk, 'routingStepId': self.f.source_other_step.pk},
                {'productionPlanId': self.plan.pk, 'routingStepId': self.f.step.pk},
                {'productionPlanId': self.other_plan().pk, 'routingStepId': self.step.pk}):
            with self.subTest(context=context):
                self.assert_ready_rejected(context=context)
        company = Company.objects.create(code='SIM-NQ-FOREIGN', name='SIMULATED_FOR_TEST nonquant foreign company')
        outsider = User.objects.create_user(username='sim_nonquant_foreign', company_id=company.pk)
        self.assert_ready_rejected(user=outsider)

    def test_saved_object_version_and_revision_damage_are_not_accepted(self):
        self.confirm_zero()
        self.configure()
        record = OperationInputPreparationDraft.objects.get(production_plan=self.plan, routing_step=self.step)
        cases = ({'routing_version_id': self.f.wrong_version.pk},
            {'object_coverage': record.object_coverage[:-1]}, {'revision': record.revision + 1})
        for fields in cases:
            with self.subTest(fields=list(fields)), transaction.atomic():
                self.raw(record, **fields)
                self.assert_ready_rejected()
                transaction.set_rollback(True)

    def test_later_positive_capacity_invalidates_zero_ruling(self):
        self.confirm_zero()
        self.configure()
        self.f.make_capacity(self.operation, self.f.area, 'SIM-NQ-LATER-POSITIVE',
            measurement_status='measured', quantity=Decimal('7'))
        self.assert_ready_rejected(expected='NON_QUANTIFIED_PREPARATION_INVALID')

    def test_saved_proof_does_not_silently_rebind_after_real_preparation_revision(self):
        self.confirm_zero()
        self.configure()
        saved = self.generate()
        obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
        frozen = deepcopy(obj.trace)
        template = self.prep_case.ruling_basis()
        basis = preparation.build_capacity_ruling_basis(current_preparation=self.prep_case.read(),
            reference='SIMULATED_FOR_TEST/later-zero-confirmation', reference_sha256='e' * 64,
            exact_statement='Confirm the same precise zero with a new explicit preparation revision',
            reason='SIMULATED_FOR_TEST preserved history, real appended revision',
            source_proof=template['entries'][-1]['capacityRuling']['sourceProof'])
        self.prep_case.correct_capacity(basis=basis, revision=2, key='sim-nonquant-new-ruling-revision')
        current = self.prep_case.read()
        self.assertGreater(current['revision'], frozen['manufacturingPreparationContext']['revision'])
        obj.refresh_from_db()
        self.assertEqual(obj.trace, frozen)
        before = self.snapshot()
        with self.assertRaises(native.OperationRequirementError) as caught:
            native._validate_requirement(obj, self.f.company.pk, user=self.user)
        self.assertEqual(caught.exception.code, 'NON_QUANTIFIED_PREPARATION_CHANGED')
        self.assertEqual(before, self.snapshot())

    def test_standard_capacity_mode_never_gains_automatic_preparation_exemption(self):
        self.confirm_zero()
        self.assert_configuration_rejected(capacityMode='STANDARD_CAPACITY', standardCapacityId=None)
        self.assert_configuration_rejected(capacityMode='STANDARD_CAPACITY', standardCapacityId=0)
        self.assert_configuration_rejected(capacityMode='unsupported-mode', standardCapacityId=None)

    def test_existing_publication_permissions_cannot_be_bypassed(self):
        self.confirm_zero()
        for code in ('production.engineering.rule.create', 'production.engineering.rule.release'):
            with self.subTest(permission=code), transaction.atomic():
                RolePermission.objects.filter(role=self.f.role, permission__code=code).delete()
                self.assert_configuration_rejected()
                transaction.set_rollback(True)
        self.configure()
        with transaction.atomic():
            RolePermission.objects.filter(role=self.f.role, permission__code=native.VIEW).delete()
            self.assert_ready_rejected(expected='PERMISSION_DENIED')
            transaction.set_rollback(True)

    def test_native_database_check_rejects_missing_null_wrong_types_and_fk_shapes(self):
        self.confirm_zero()
        self.configure()
        saved = self.generate()
        obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
        trace = deepcopy(obj.trace)
        mutations = []

        def add(label, path, value=DEFAULT):
            candidate = deepcopy(trace)
            parent = candidate
            for key in path[:-1]:
                parent = parent[key]
            if value is DEFAULT:
                parent.pop(path[-1])
            else:
                parent[path[-1]] = value
            mutations.append((label, {'trace': candidate}))

        for value in (DEFAULT, None, 1, 'unsupported'):
            add('reference-type-' + repr(value), ['manufacturingReferenceType'], value)
        for value in (DEFAULT, None, [], 'invalid'):
            add('proof-' + repr(value), ['manufacturingPreparationContext'], value)
        for name in ('contractVersion', 'exactScope', 'recordId', 'revision',
                'contextHash', 'objectsHash', 'contentHash', 'capacityRuling', 'sourceObjectCoverage'):
            add('missing-proof-field-' + name, ['manufacturingPreparationContext', name])
            add('null-proof-field-' + name, ['manufacturingPreparationContext', name], None)
        for name in trace['manufacturingPreparationContext']['exactScope']:
            for value in (DEFAULT, None, True, '1', 0):
                add('scope-' + name + '-' + repr(value), ['manufacturingPreparationContext', 'exactScope', name], value)
        for name in ('recordId', 'revision'):
            for value in (True, '1', 0):
                add('proof-integer-' + name + '-' + repr(value), ['manufacturingPreparationContext', name], value)
        for name in ('contextHash', 'objectsHash', 'contentHash'):
            for value in ('short', 'z' * 64, 123):
                add('proof-hash-' + name + '-' + repr(value), ['manufacturingPreparationContext', name], value)
        for name, value in (('code', 'INVALID'), ('meaningCode', 'QUANTIFIED'), ('sourceValue', 0)):
            add('ruling-' + name, ['manufacturingPreparationContext', 'capacityRuling', name], value)
        for value in (True, 1, 'unsupported-contract'):
            add('contract-version-' + repr(value), ['manufacturingPreparationContext', 'contractVersion'], value)
        for name in ('designItemIds', 'baselineItemIds', 'inputFactIds'):
            for value in (DEFAULT, None, [], 'invalid'):
                add('coverage-' + name + '-' + repr(value),
                    ['manufacturingPreparationContext', 'sourceObjectCoverage', name], value)
        mutations.extend([('nonquant-with-SC', {'standard_capacity_id': self.f.capacity.pk}),
            ('nonquant-without-mode', {'manufacturing_mode_id': None}),
            ('nonquant-without-center', {'work_center_id': None}),
            ('nonquant-with-all-three-null', {'manufacturing_mode_id': None, 'work_center_id': None})])
        for label, fields in mutations:
            with self.subTest(invalidCombination=label):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        self.raw(obj, **fields)
        obj.refresh_from_db()
        self.assertEqual(obj.trace, trace)
        self.assertEqual((obj.manufacturing_mode_id, obj.work_center_id, obj.standard_capacity_id),
            (self.f.mode.pk, self.f.center.pk, None))


class ExistingAuxiliaryCapacityCompatibilityTests(TestCase):
    def test_real_all_null_legacy_generation_and_replay_keep_original_contract(self):
        case = legacy_fixtures.OperationRequirementTests(methodName='runTest')
        case.setUp()
        source_before = list(case.source_calc.derived_facts.order_by('pk').values())
        saved = case.generate()
        obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
        self.assertEqual((obj.manufacturing_mode_id, obj.work_center_id, obj.standard_capacity_id),
            (None, None, None))
        self.assertNotIn('manufacturingReferenceType', obj.trace)
        self.assertNotIn('manufacturingPreparationContext', obj.trace)
        original = list(EngineeringOperationRequirement.objects.filter(pk=obj.pk).values())
        counts = tuple(model.objects.count() for model in
            (EngineeringOperationRequirement, OrganizationOperatingAuditRecord, BusinessStateTransition))
        replay = case.generate()
        self.assertEqual(replay['operationRequirementId'], obj.pk)
        native._validate_requirement(obj, case.company.pk, user=case.user)
        self.assertEqual(list(EngineeringOperationRequirement.objects.filter(pk=obj.pk).values()), original)
        self.assertEqual(tuple(model.objects.count() for model in
            (EngineeringOperationRequirement, OrganizationOperatingAuditRecord, BusinessStateTransition)), counts)
        self.assertEqual(list(case.source_calc.derived_facts.order_by('pk').values()), source_before)

    def test_real_sc_zero_manifest_keeps_original_complete_manufacturing_references(self):
        case = quantitative_fixtures.ManufacturingEorConfigurationTests(methodName='runTest')
        case.setUp()
        capacity = case.capacity
        effective = capacity.effective_from
        manifest = {'contractVersion': 'PCE-APS-CAPACITY-SOURCE-RULES-V1', 'sourceSha256': 'a' * 64,
            'productTypeCode': case.product_type.code, 'effectiveDate': effective.isoformat(),
            'applicableOperationIds': [case.op_area.pk], 'nonApplicableOperationIds': [],
            'auxiliaryOperationIds': [case.op_area.pk], 'preparationDays': None, 'transferDays': None,
            'businessFactReference': 'SIMULATED_FOR_TEST formally declared auxiliary zero source'}
        capacity.quantity = Decimal('0')
        capacity.measurement_status = 'zero_capacity'
        capacity.preparation_days = capacity.transfer_days = None
        capacity.conditions = {'sourceSha256': 'a' * 64, 'sourceProductTypeCode': case.product_type.code,
            'apsSourceRules': manifest}
        capacity.save()
        before = list(case.source_calc.derived_facts.order_by('pk').values())
        ready = native.OperationRequirementService.generate_readiness(user=case.user,
            source_calculation_id=case.source_calc.pk, source_fact_id=case.fact_area.pk, rule_id=case.mapping.pk)
        self.assertTrue(ready['ready'], ready)
        saved = case.generate(rule=case.mapping)
        obj = EngineeringOperationRequirement.objects.get(pk=saved['operationRequirementId'])
        self.assertEqual((obj.manufacturing_mode_id, obj.work_center_id, obj.standard_capacity_id),
            (case.mode.pk, case.center.pk, capacity.pk))
        self.assertNotIn('manufacturingReferenceType', obj.trace)
        self.assertNotIn('manufacturingPreparationContext', obj.trace)
        native._validate_requirement(obj, case.company.pk)
        self.assertEqual(list(case.source_calc.derived_facts.order_by('pk').values()), before)
