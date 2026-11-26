"""SIMULATED_FOR_TEST: formal scope and existing capacity use stay independent.

Native fixtures, publications, saved loads, object decisions and capacity scope
ledgers are real. Only draft fixture capacity construction is specialized.
Execute exclusively in the parent's guarded disposable test database.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from system.models import Permission, Process, RolePermission
from . import daily_capacity_service as capacity
from . import operation_requirement_service as native
from . import operation_workload_source_service as workload
from . import routing_object_applicability_service as objects
from . import tests_calc4_routing_correction as correction_fixtures
from . import tests_no_date_allocated_capacity as saved_fixtures
from . import tests_routing_object_applicability_service as object_fixtures
from . import tests_no_date_read_context as context_fixtures
from .manufacturing_capacity_scope import capacity_usage_scope_proof, CONTRACT as SCOPE_CONTRACT
from .models import StandardCapacity
from .production_foundation_service import ProductionFoundationService


def create_eor_capacity(f, operation, uom, code, **overrides):
    for name in ('production.master_data.create', 'production.master_data.capacity.maintain'):
        permission, _ = Permission.objects.get_or_create(code=name, defaults={'name': name, 'module': 'PRODUCTION'})
        RolePermission.objects.get_or_create(role=f.role, permission=permission)
    scope = {'contractVersion': SCOPE_CONTRACT, 'usageScope': 'ENGINEERING_EOR_ONLY', 'version': 'V1',
        'businessFactReference': 'SIMULATED_FOR_TEST explicit capacity use fixture',
        'sourceFingerprint': sha256(code.encode()).hexdigest()}
    payload = {'company_id': f.company.pk, 'code': code, 'name': 'Abstract positive declared capacity',
        'resource_scope': 'work_center', 'work_center_id': f.center.pk, 'operation_id': operation.pk,
        'product_type_id': f.product_type.pk, 'measurement_status': 'measured', 'quantity': '500',
        'uom_id': uom.pk, 'time_basis': 'day', 'time_basis_quantity': '1', 'time_unit': 'DAY',
        'effective_from': (date.today() - timedelta(days=1)).isoformat(),
        'conditions': {'capacityUsageScope': scope}, 'is_active': True,
        'reason': 'SIMULATED_FOR_TEST preserve positive quantity and audited use scope'}
    payload.update(overrides)
    result = ProductionFoundationService.write('standard-capacities', user=f.user, payload=payload,
        idempotency_key=f'sim-scope-{code}', source_identity={'sourceSystem': 'PCE', 'sourceType': 'FORMAL_CONFIG',
            'sourceObjectType': 'SIMULATED_FOR_TEST_CAPACITY_SCOPE', 'externalId': code,
            'sourceFingerprint': scope['sourceFingerprint'], 'auditMetadata': {'capacityUsageScope': scope}})
    row = StandardCapacity.objects.get(pk=result['row']['id'])
    assert capacity_usage_scope_proof(row) is not None
    return row


class StepCapacityScopeConflictTests(TestCase):
    def setUp(self):
        self.saved = saved_fixtures.NoDateAllocatedCapacityPersistenceTests(methodName='runTest')
        # Declare EOR use before original rule/calculation/allocation snapshots.
        # No saved capacity, hash or source is amended to construct the fixture.
        with patch.object(correction_fixtures.Calc4RoutingCorrectionTests, 'make_capacity', create_eor_capacity):
            self.saved.setUp()
        self.f, self.plan = self.saved.f, self.saved.plan
        self.step, self.user = self.f.step, self.f.user
        for name in (native.VIEW, workload.RULE_VIEW):
            permission, _ = Permission.objects.get_or_create(code=name, defaults={'name': name, 'module': 'PRODUCTION'})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.saved.save_contributions()

    def readonly(self, callback):
        before = self.f.full_database_snapshot()
        changes = connection.connection.total_changes

        def no_writes(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if verb not in {'SELECT', 'PRAGMA', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'BEGIN', 'COMMIT'}:
                raise AssertionError('Capacity assessment attempted ' + verb)
            return execute(sql, params, many, context)

        with ExitStack() as stack:
            for target in ('pde.daily_capacity_service.working_date_window',
                    'pde.daily_capacity_views.production_plan_date_preview',
                    'pde.operation_requirement_service.OperationRequirementService.generate',
                    'pde.operation_requirement_service.OperationRequirementService.allocate'):
                stack.enter_context(patch(target, side_effect=AssertionError('No-date scope check cannot write or book')))
            stack.enter_context(connection.execute_wrapper(no_writes))
            try:
                return callback()
            finally:
                self.assertEqual(connection.connection.total_changes, changes)
                self.assertEqual(self.f.full_database_snapshot(), before)

    def read(self):
        return capacity.AllocatedLoadCapacityReadinessService.assess(user=self.user,
            production_plan_id=self.plan.pk, routing_step_id=self.step.pk)

    def lower_read(self):
        output = self.f.output
        return capacity.DailyCapacityReadinessService.assess(output.routing_version,
            bom_version=output.bom_version, engineering_calculation=self.f.source_calc,
            engineering_document_version=output.engineering_document_version,
            order_engineering_instance=self.f.instance, order_engineering_baseline=self.f.baseline,
            production_plan=self.plan, manufacturing_output=output,
            routing_step_id=self.step.pk, user=self.user)

    def source_blank(self):
        other = Process.objects.create(company=self.f.company, code='SIM-SCOPE-OTHER',
            name='Abstract auxiliary source operation', calculation_basis='area', calculation_uom=self.f.area)
        manifest = {'contractVersion': capacity.SOURCE_RULES_CONTRACT, 'sourceSha256': 'e' * 64,
            'productTypeCode': self.f.product_type.code, 'effectiveDate': date.today().isoformat(),
            'applicableOperationIds': [other.pk], 'nonApplicableOperationIds': [self.step.operation_id],
            'auxiliaryOperationIds': [other.pk], 'preparationDays': '0.1', 'transferDays': '0.1',
            'businessFactReference': 'SIMULATED_FOR_TEST contradictory declared source scope'}
        StandardCapacity.objects.create(company=self.f.company, code='SIM-SCOPE-AUX', name='Abstract source zero',
            resource_scope='work_center', work_center=self.f.center, operation=other,
            product_type=self.f.product_type, uom=self.f.area, measurement_status='zero_capacity', quantity=0,
            time_basis='day', time_basis_quantity=1, time_unit='DAY', effective_from=date.today(),
            preparation_days=Decimal('.1'), transfer_days=Decimal('.1'), conditions={
                'apsSourceRules': manifest, 'sourceSha256': manifest['sourceSha256'],
                'sourceProductTypeCode': self.f.product_type.code})
        proof = capacity.capacity_source_rules(self.f.product_type, company_id=self.f.company.pk, on_date=date.today())
        self.assertEqual(proof['status'], 'VALID', proof)

    def confirm_objects(self, *, required, partial=False):
        fixture = object_fixtures.make_object_applicability_fixture(f=self.f, plan=self.plan)
        rows = deepcopy(fixture.contributions[:1] if partial else fixture.contributions)
        for row in rows:
            row['decision'] = 'REQUIRED' if required else 'NOT_APPLICABLE'
        objects.confirm_group(self.user, self.plan.pk, self.step.pk, rows,
            'SIMULATED_FOR_TEST preserve independently confirmed object applicability')

    def assert_scope_blocked(self, result):
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        self.assertTrue(result['allocationRead']['passed'])
        self.assertEqual(result['allocationRead']['resultCount'], 3)
        self.assertEqual(result['allocationRead']['blockers'], [])
        self.assertFalse(result['scopeNoDateReady'])
        self.assertFalse(result['planningReady'])
        self.assertIn('CAPACITY_OBJECT_SCOPE_CONFLICT', {b['code'] for b in result['blockers']})
        row, = result['steps']
        self.assertEqual(row['applicability']['result'], 'REQUIRED')
        self.assertIn('CAPACITY_OBJECT_SCOPE_CONFLICT', {b['code'] for b in row['blockers']})
        self.assertEqual(row['capacityMatches'], [])
        self.assertNotIn('durationDays', row)
        self.assertIsNotNone(row['processDemand'])
        self.assertEqual(Decimal(row['processDemand']['quantity']), Decimal('4'))
        for name in ('businessWriteCount', 'dateOccupationCount', 'productionScheduleCreatedCount'):
            self.assertEqual(result[name], 0)

    def test_explicit_required_survives_valid_source_blank_and_reaches_top_blockers(self):
        self.source_blank()
        result = self.readonly(self.read)
        self.assert_scope_blocked(result)
        native_row, = result['readiness']['steps']
        self.assertEqual(native_row['routingApplicability']['result'], 'REQUIRED')
        self.assertEqual(native_row['applicability'], native_row['routingApplicability'])
        self.assertNotEqual(native_row['capacityDateMode'], 'NOT_APPLICABLE')

    def test_complete_required_objects_survive_source_blank_without_becoming_pending(self):
        self.confirm_objects(required=True)
        self.source_blank()
        result = self.readonly(self.read)
        self.assert_scope_blocked(result)
        self.assertTrue(result['steps'][0]['applicability']['objectApplicability']['complete'])

    def test_true_formal_object_exclusion_stays_not_applicable_without_false_conflict(self):
        self.confirm_objects(required=False)
        self.source_blank()
        result = self.readonly(self.lower_read)
        row, = result['steps']
        self.assertEqual(row['applicability']['result'], 'NOT_APPLICABLE')
        self.assertEqual(row['capacityDateMode'], 'NOT_APPLICABLE')
        self.assertTrue(row['capacitySemantics']['valid'])
        self.assertEqual(row['capacitySemantics']['meaningCode'], 'NOT_APPLICABLE')
        self.assertNotIn('SOURCE_OBJECT_APPLICABILITY_CONFLICT', row['blockerCodes'])
        self.assertNotIn('CAPACITY_OBJECT_SCOPE_CONFLICT', row['blockerCodes'])

    def test_actual_saved_eor_capacity_has_explicit_use_blocker_without_erasing_positive_fact(self):
        before = StandardCapacity.objects.filter(pk=self.f.capacity.pk).values().get()
        result = self.readonly(self.read)
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        self.assertFalse(result['scopeNoDateReady'])
        blockers = [b for b in result['blockers'] if b['code'] == 'ALLOCATED_STANDARD_CAPACITY_UNMATCHED']
        self.assertTrue(any(b.get('standardCapacityId') == self.f.capacity.pk for b in blockers))
        row, = result['steps']
        self.assertTrue(any(b.get('standardCapacityId') == self.f.capacity.pk for b in row['blockers']))
        self.assertEqual(row['capacityMatches'], [])
        self.assertEqual(before, StandardCapacity.objects.filter(pk=self.f.capacity.pk).values().get())
        self.assertEqual(before['quantity'], Decimal('500'))
        self.assertEqual(before['time_basis_quantity'], Decimal('1'))
        self.assertNotIn('durationDays', row)

    def test_incomplete_object_scope_is_never_resolved_by_blank_or_zero(self):
        self.confirm_objects(required=True, partial=True)
        self.source_blank()
        result = self.readonly(self.lower_read)
        row, = result['steps']
        self.assertEqual(row['applicability']['result'], 'PENDING')
        self.assertIn('ROUTING_STEP_APPLICABILITY_PENDING', row['blockerCodes'])
        self.assertFalse(row['capacitySemantics']['valid'])
        self.assertIsNone(row['capacitySemantics']['meaningCode'])
        self.assertNotIn('durationDays', row)


class StepCapacityScopeIsolationTests(TestCase):
    def test_unrelated_eor_candidate_does_not_pollute_real_saved_aps_capacity(self):
        fixture = saved_fixtures.NoDateAllocatedCapacityPersistenceTests(methodName='runTest')
        fixture.setUp()
        f = fixture.f
        fixture.save_contributions()
        permission, _ = Permission.objects.get_or_create(code=workload.RULE_VIEW,
            defaults={'name': workload.RULE_VIEW, 'module': 'PRODUCTION'})
        RolePermission.objects.get_or_create(role=f.role, permission=permission)
        extra = create_eor_capacity(f, f.op_area, f.area, 'SIM-SCOPE-UNUSED-EOR')
        before = f.full_database_snapshot()
        result = capacity.AllocatedLoadCapacityReadinessService.assess(user=f.user,
            production_plan_id=fixture.plan.pk, routing_step_id=f.step.pk)
        self.assertTrue(result['scopeNoDateReady'], result)
        self.assertFalse(any(b.get('standardCapacityId') == extra.pk for b in result['blockers']))
        self.assertEqual(result['steps'][0]['capacityMatches'][0]['standardCapacityId'], f.capacity.pk)
        self.assertEqual(Decimal(result['steps'][0]['capacityMatches'][0]['durationDays']), Decimal('.208'))
        self.assertEqual(before, f.full_database_snapshot())

    def test_existing_nonquantified_preparation_keeps_qualitative_zero_without_duration(self):
        fixture = context_fixtures.NoDateReadContextTests(methodName='runTest')
        fixture.setUp()
        result = fixture.readonly(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(
            user=fixture.user, production_plan_id=fixture.plan.pk, routing_step_id=fixture.nq_step.pk))
        self.assertTrue(result['allocatedLoadReadPassed'], result)
        row, = result['steps']
        self.assertEqual(row['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(row['capacitySemantics']['sourceValue'], '0')
        self.assertFalse(result['scopeNoDateReady'])
        self.assertEqual(row['capacityMatches'], [])
        self.assertNotIn('durationDays', row)
