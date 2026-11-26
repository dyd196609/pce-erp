"""SIMULATED_FOR_TEST: native saved consumption, not blanket EOR availability.

Only the guarded disposable runner may execute this module. Formal capacity
scope, published rules, object coverage, allocations and preparation references
are built through existing native fixtures/services before measured reads.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from unittest.mock import patch

from django.test import TestCase

from masterdata.models import MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord, Permission, RolePermission
from . import daily_capacity_service as capacity
from . import operation_input_preparation_service as preparation
from . import tests_step_capacity_scope_conflict as scope_fixtures
from .tests_capacity_consumption_reference import frozen_source_fixture_initial
from .models import OperationInputPreparationDraft, StandardCapacity
from .production_foundation_service import ProductionFoundationError
from .routing_version_successor_service import ROUTING_PERMISSION


class CapacityConsumptionNoDateTests(TestCase):
    def setUp(self):
        original = scope_fixtures.create_eor_capacity
        conflicting_time = self._testMethodName == 'test_existing_nonempty_capacity_time_cannot_be_overridden'

        def declared_capacity(f, operation, uom, code, **fields):
            fields.update(preparation_days=Decimal('.2') if conflicting_time else None, transfer_days=None)
            return original(f, operation, uom, code, **fields)

        self.case = scope_fixtures.StepCapacityScopeConflictTests(methodName='runTest')
        with patch.object(scope_fixtures, 'create_eor_capacity', side_effect=declared_capacity), \
                patch.object(scope_fixtures.correction_fixtures.Calc4RoutingCorrectionTests,
                    'initial', new=frozen_source_fixture_initial):
            self.case.setUp()
        self.f, self.plan, self.user, self.step = self.case.f, self.case.plan, self.case.user, self.case.step
        self.case.source_blank()
        for code in (preparation.VIEW, preparation.CREATE, preparation.UPDATE, preparation.CAPACITY, ROUTING_PERMISSION):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'module': 'PRODUCTION'})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.scope = {'companyId': self.f.company.pk, 'productionPlanId': self.plan.pk,
            'manufacturingOutputId': self.f.output.pk, 'mainCalculationId': self.f.source_calc.pk,
            'salesOrderItemId': self.f.item.pk, 'baselineId': self.f.baseline.pk,
            'routingVersionId': self.f.version.pk, 'routingStepId': self.step.pk,
            'operationId': self.step.operation_id, 'productTypeId': self.f.product_type.pk}

    def save_reference(self, *, capacity_id=None, effective_to=None, key='sim-capacity-consumption'):
        context = preparation.read_preparation(user=self.user, exact_scope=self.scope,
            consumer='ALLOCATED_LOAD_NO_DATE')
        source = capacity.capacity_source_rules(self.f.product_type, company_id=self.f.company.pk, on_date=date.today())
        self.assertEqual(source['status'], 'VALID', source)
        manifest = source['manifest']
        reference = preparation.build_capacity_consumption_reference(
            standard_capacity_id=self.f.capacity.pk if capacity_id is None else capacity_id,
            product_type_id=self.f.product_type.pk, source_sha256=manifest['sourceSha256'],
            source_effective_date=manifest['effectiveDate'], effective_from=date.today().isoformat(),
            effective_to=effective_to)
        basis = {'contractVersion': preparation.BASIS_CONTRACT, 'entries': [{
            'reference': 'SIMULATED_FOR_TEST/exact-no-date-reference',
            'referenceSha256': sha256(b'exact-no-date-reference').hexdigest(),
            'exactStatement': '对本计划本步骤实际保存对象及负荷，引用现有正式正产能和系统统一准备、转运DAY；整工序各计一次。',
            'scope': deepcopy(self.scope), 'objectCoverage': deepcopy(context['objectCoverage']),
            'capacityConsumptionReference': reference}]}
        return preparation.save_preparation(user=self.user, exact_scope=self.scope, business_basis=basis,
            expected_context_hash=context['contextHash'], expected_revision=0,
            idempotency_key=key, reason='SIMULATED_FOR_TEST maintain exact no-date capacity consumption')

    def read(self, *, on_date=None):
        return self.case.readonly(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(user=self.user,
            production_plan_id=self.plan.pk, routing_step_id=self.step.pk, on_date=on_date))

    def test_eor_without_saved_exact_relation_remains_blocked(self):
        result = self.read()
        self.assertTrue(result['allocatedLoadReadPassed'])
        self.assertFalse(result['scopeNoDateReady'])
        self.assertNotIn('capacityConsumptionReference', result)
        self.assertTrue(any(b['code'] == 'ALLOCATED_STANDARD_CAPACITY_UNMATCHED' for b in result['blockers']))
        self.assertFalse(result['allocationRead']['sourceRead']['standardCapacityFacts'][0]['available'])

    def test_native_saved_reference_consumes_aggregate_load_and_shared_times_once(self):
        saved = self.save_reference()
        before = self.f.full_database_snapshot()
        original_capacity = StandardCapacity.objects.filter(pk=self.f.capacity.pk).values().get()
        result = self.read()
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertTrue(result['scopeNoDateReady'], result)
        self.assertTrue(result['evaluatedRequiredStepsCovered'])
        self.assertTrue(result['allocatedLoadReadPassed'])
        self.assertFalse(result['planningReady'])
        self.assertFalse(result['noDateReady'])
        self.assertEqual(result['blockers'], [])
        self.assertTrue(result['originalReadiness']['blockers'])
        self.assertTrue(result['originalSourceCapacityBlockers'])
        self.assertTrue(result['resolvedSourceCapacityBlockers'])
        self.assertTrue(result['readiness']['noDateConsumptionProjected'])
        self.assertEqual(result['capacityConsumptionReference']['recordId'], saved['recordId'])
        self.assertEqual(result['capacityConsumptionReference']['consumer'], 'ALLOCATED_LOAD_NO_DATE')
        row, = result['steps']
        match, = row['capacityMatches']
        self.assertEqual(result['matchedAllocationCount'], 3)
        self.assertEqual(Decimal(row['processDemand']['quantity']), Decimal('4'))
        self.assertEqual(Decimal(match['capacityFact']['capacityQuantity']), Decimal('500'))
        self.assertFalse(match['capacityFact']['available'])
        self.assertEqual((Decimal(match['productionDays']), Decimal(match['preparationDays']),
            Decimal(match['transferDays']), Decimal(match['durationDays'])),
            (Decimal('.008'), Decimal('.1'), Decimal('.1'), Decimal('.208')))
        self.assertEqual(match['preparationIncludedCount'], 1)
        self.assertEqual(match['transferIncludedCount'], 1)
        for name in ('preparation', 'transfer'):
            selected = match['timeSelection'][name]
            self.assertIsNone(selected['stepDays'])
            self.assertEqual(selected['standardCapacityDays'], [{'standardCapacityId': self.f.capacity.pk, 'days': None}])
            self.assertEqual(selected['source'], 'CAPACITY_SOURCE_RULES_HEADER')
            self.assertEqual(selected['sourceId'], self.f.product_type.pk)
            self.assertRegex(selected['referenceHash'], r'^[0-9a-f]{64}$')
            self.assertEqual(Decimal(selected['selectedDays']), Decimal('.1'))
        self.assertEqual(original_capacity, StandardCapacity.objects.filter(pk=self.f.capacity.pk).values().get())
        self.assertIsNone(original_capacity['preparation_days'])
        self.assertIsNone(original_capacity['transfer_days'])
        row = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        self.assertIsNone(row.standard_capacity_id)
        self.assertEqual(row.capacity_measurement_status, 'UNMEASURED')
        for key in ('businessWriteCount', 'dateOccupationCount', 'productionScheduleCreatedCount'):
            self.assertEqual(result[key], 0)
        with self.assertRaises(capacity.DailyCapacityError) as caught:
            capacity._current_plan_capacity(match['capacityFact'], date.today())
        self.assertEqual(caught.exception.code, 'CAPACITY_FACT_CHANGED')
        wrong_consumer = deepcopy(result['capacityConsumptionReference'])
        wrong_consumer['consumer'] = 'DATE_PREVIEW'
        with self.assertRaises(capacity.DailyCapacityError) as caught:
            capacity._no_date_consumption_projection(result['originalReadiness'],
                result['allocationRead']['sourceRead'], wrong_consumer, date.today())
        self.assertEqual(caught.exception.code, 'CAPACITY_OBJECT_SCOPE_CONFLICT')

    def test_different_unreferenced_positive_capacity_cannot_be_saved_as_this_load_relation(self):
        other = scope_fixtures.create_eor_capacity(self.f, self.f.op_area, self.f.area, 'SIM-CONSUME-UNUSED')
        before = self.f.full_database_snapshot()
        with self.assertRaises((ProductionFoundationError, capacity.DailyCapacityError)):
            self.save_reference(capacity_id=other.pk)
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertFalse(self.read()['scopeNoDateReady'])

    def test_expired_relation_does_not_open_a_future_assessment(self):
        self.save_reference(effective_to=date.today().isoformat())
        with self.assertRaises((ProductionFoundationError, capacity.DailyCapacityError)):
            self.read(on_date=date.today() + timedelta(days=1))

    def test_bad_native_reference_ledger_never_falls_back_to_a_previous_approval(self):
        saved = self.save_reference()
        MasterDataWriteRequest.objects.filter(pk=saved['writeRequestId']).update(status='RESERVED')
        with self.assertRaises((ProductionFoundationError, capacity.DailyCapacityError)):
            self.read()

    def test_damaged_original_capacity_use_audit_is_not_hidden_by_saved_reference(self):
        saved = self.save_reference()
        saved_basis = deepcopy(OperationInputPreparationDraft.objects.get(pk=saved['recordId']).business_basis)
        original = scope_fixtures.capacity_usage_scope_proof(self.f.capacity)
        self.assertNotEqual(original['writeRequestId'], saved['writeRequestId'])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=original['auditId'])
        self.assertEqual(audit.action_code, 'production.master_data.capacity.maintain')
        self.assertEqual(audit.target_id, self.f.capacity.pk)
        damaged = deepcopy(audit.after_snapshot)
        damaged['state']['quantity'] = '501'
        OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=damaged)
        with self.assertRaises((ProductionFoundationError, capacity.DailyCapacityError)) as caught:
            self.read()
        self.assertEqual(caught.exception.code, 'PREPARATION_CONTEXT_DRIFT')
        self.assertEqual(caught.exception.details['sourceCode'], 'MANUFACTURING_CAPACITY_SCOPE_INVALID')
        self.assertEqual(OperationInputPreparationDraft.objects.get(pk=saved['recordId']).business_basis,
            saved_basis)

    def test_current_rule_view_permission_remains_required_after_reference_save(self):
        self.save_reference()
        RolePermission.objects.filter(role=self.f.role, permission__code=preparation.VIEW).delete()
        with self.assertRaises((ProductionFoundationError, capacity.DailyCapacityError)) as caught:
            self.read()
        self.assertEqual(caught.exception.code, 'PERMISSION_DENIED')

    def test_existing_nonempty_capacity_time_cannot_be_overridden(self):
        before = self.f.full_database_snapshot()
        try:
            self.save_reference()
        except (ProductionFoundationError, capacity.DailyCapacityError):
            self.assertEqual(before, self.f.full_database_snapshot())
        else:
            with self.assertRaises(capacity.DailyCapacityError) as caught:
                self.read()
            self.assertEqual(caught.exception.code, 'APS_SOURCE_RULES_INVALID')
