"""SIMULATED_FOR_TEST: native capacity references over existing saved loads.

Fixture writes use the existing formal services in a disposable test database.
Read/replay phases deny DML and compare the complete isolated database. No
source, budget, object, usage, actor or authorization success is mocked.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from system.models import Permission, RolePermission
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition

from . import operation_input_preparation_service as prep
from . import operation_workload_source_service as workload
from . import daily_capacity_service as daily
from . import tests_step_capacity_scope_conflict as fixtures
from .models import (EngineeringCalculationRecord, OperationInputPreparationDraft,
    OrderEngineeringBaselineItem, ProductDesignItem, StandardCapacity)
from .routing_version_successor_service import ROUTING_PERMISSION


def frozen_source_fixture_initial(self, model, state, **fields):
    """SIMULATED_FOR_TEST: complete input envelopes at initial construction.

    These are the same producer and object values the composed fixture will
    create as Facts. Nothing is patched after publication or allocation.
    Native validators and their return values remain untouched.
    """
    if model is EngineeringCalculationRecord and fields.get('scope') == 'order_engineering':
        from . import operation_requirement_service as native
        from .engineering_rule_foundation import specification_hash
        trace = deepcopy(fields['trace'])
        graph = [{'ruleId': self.producer.pk, 'ruleCode': self.producer.rule_code,
            'ruleVersion': self.producer.version,
            'specificationHash': specification_hash(self.producer.specification),
            'specification': deepcopy(self.producer.specification)}]
        values = self.source.source_payload['objects']
        results = [{'sequence': index, 'designItemId': obj.design_item_id,
            'canonicalField': 'opaque_area', 'value': {'decimal': value}, 'unit': self.area.code,
            'ruleCode': self.producer.rule_code, 'ruleVersion': self.producer.version}
            for index, (obj, value) in enumerate(zip(self.baseline_items, values), 1)]
        trace.update(ruleGraphSnapshot=graph, resultSnapshot=results, resultHash=native._digest(results))
        fields.update(trace=trace, rule_graph_hash=native._digest(graph), result_hash=native._digest(results))
    return fixtures.correction_fixtures.original.OperationRequirementTests.initial(self, model, state, **fields)


def make_capacity_reference_fixture():
    fixture = fixtures.StepCapacityScopeConflictTests(methodName='runTest')
    with patch.object(fixtures.correction_fixtures.Calc4RoutingCorrectionTests, 'initial',
            new=frozen_source_fixture_initial):
        fixture.setUp()
    fixture.source_blank()
    f = fixture.f
    for code in (prep.VIEW, prep.CREATE, prep.UPDATE, prep.CAPACITY, ROUTING_PERMISSION):
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'module': 'PRODUCTION'})
        RolePermission.objects.get_or_create(role=f.role, permission=permission)
    source = workload.read_for_plan(user=f.user, production_plan_id=fixture.plan.pk, routing_step_id=fixture.step.pk)
    context = prep.read_preparation(user=f.user, exact_scope=source['scope'], consumer='ALLOCATED_LOAD_NO_DATE')
    manifest = daily.capacity_source_rules(f.product_type, company_id=f.company.pk, on_date=date.today())['manifest']
    reference = prep.build_capacity_consumption_reference(standard_capacity_id=f.capacity.pk,
        product_type_id=f.product_type.pk, source_sha256=manifest['sourceSha256'],
        source_effective_date=manifest['effectiveDate'], effective_from=date.today().isoformat())
    basis = {'contractVersion': prep.BASIS_CONTRACT, 'entries': [{
        'reference': 'SIMULATED_FOR_TEST explicit formal consumption and unified time decision',
        'referenceSha256': 'a' * 64, 'exactStatement': 'Use the recorded positive daily capacity and formal common DAY standard.',
        'scope': deepcopy(source['scope']), 'objectCoverage': deepcopy(context['objectCoverage']),
        'capacityConsumptionReference': reference}]}
    return SimpleNamespace(fixture=fixture, f=f, user=f.user, plan=fixture.plan, step=fixture.step,
        exact_scope=source['scope'], context=context, basis=basis, manifest=manifest)


def save_capacity_reference(case, *, basis=None, key='sim-native-capacity-reference', revision=0):
    return prep.save_preparation(user=case.user, exact_scope=case.exact_scope,
        business_basis=deepcopy(case.basis if basis is None else basis),
        idempotency_key=key, expected_context_hash=case.context['contextHash'], expected_revision=revision,
        reason='SIMULATED_FOR_TEST maintain a native exact-step capacity/time reference')


class CapacityConsumptionReferenceTests(TestCase):
    def setUp(self):
        self.case = make_capacity_reference_fixture()

    def resolve(self, **kwargs):
        return prep.resolve_capacity_consumption_reference(user=self.case.user,
            exact_scope=self.case.exact_scope, **kwargs)

    def test_native_save_binds_proof_keeps_old_objects_and_replays_with_zero_writes(self):
        c = self.case
        capacity_before = StandardCapacity.objects.filter(pk=c.f.capacity.pk).values().get()
        allocated_before = list(daily.AllocatedLoadCapacityReadinessService.assess(
            user=c.user, production_plan_id=c.plan.pk, routing_step_id=c.step.pk)['allocationRead']['allocations'])
        counts_before = [model.objects.count() for model in (OperationInputPreparationDraft,
            OrganizationOperatingAuditRecord, MasterDataWriteRequest, ExternalIdentity, BusinessStateTransition)]
        saved = save_capacity_reference(c)
        self.assertEqual(saved['statusCode'], 'POSITIVE_CAPACITY_REFERENCE_RECORDED')
        counts_after = [model.objects.count() for model in (OperationInputPreparationDraft,
            OrganizationOperatingAuditRecord, MasterDataWriteRequest, ExternalIdentity, BusinessStateTransition)]
        self.assertEqual([new - old for old, new in zip(counts_before, counts_after)], [1] * 5)
        record = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        self.assertEqual(record.capacity_measurement_status, 'UNMEASURED')
        self.assertIsNone(record.standard_capacity_id)
        self.assertEqual(record.context_hash, c.context['contextHash'])
        self.assertIn('proof', record.business_basis['entries'][-1]['capacityConsumptionReference'])
        view = c.fixture.readonly(lambda: prep.read_preparation(user=c.user, exact_scope=c.exact_scope))
        reference = view['capacityConsumptionReference']
        self.assertEqual(view['statusLabel'], '已保存正产能无日期引用')
        self.assertEqual(view['inputQuantity'], reference['savedLoadReference']['quantity'])
        self.assertTrue(reference['formalConsumptionValidated'])
        self.assertEqual(reference['consumer'], 'ALLOCATED_LOAD_NO_DATE')
        self.assertEqual(record.business_basis['entries'][-1]['capacityConsumptionReference']['consumer'],
            'ALLOCATED_LOAD_NO_DATE')
        self.assertFalse(reference['selectedCapacityFact']['available'])
        self.assertFalse(reference['selectedCapacityFact']['independentApsSchedulingAllowed'])
        self.assertEqual(reference['capacityReference']['standardCapacityId'], c.f.capacity.pk)
        self.assertEqual(reference['sharedTimeSource']['preparationDays'], c.manifest['preparationDays'])
        self.assertEqual(reference['sharedTimeSource']['transferDays'], c.manifest['transferDays'])
        self.assertEqual(reference['sharedTimeSource']['countPolicy'], 'ONCE_PER_STEP')
        self.assertEqual(capacity_before, StandardCapacity.objects.filter(pk=c.f.capacity.pk).values().get())
        after_load = daily.AllocatedLoadCapacityReadinessService.assess(user=c.user,
            production_plan_id=c.plan.pk, routing_step_id=c.step.pk)['allocationRead']['allocations']
        self.assertEqual(allocated_before, after_load)
        replay = c.fixture.readonly(lambda: save_capacity_reference(c))
        self.assertTrue(replay['idempotentReplay'])
        self.assertEqual(replay['capacityConsumptionReference']['referenceHash'], reference['referenceHash'])
        for name in ('businessWriteCount', 'auditWriteCount', 'stateTransitionWriteCount', 'supportWriteCount'):
            self.assertEqual(replay[name], 0)

    def test_bare_saved_reference_is_not_upgraded_and_client_values_are_rejected(self):
        c = self.case
        bad = deepcopy(c.basis)
        bad['entries'][0]['capacityConsumptionReference']['quantity'] = '500'
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(lambda: save_capacity_reference(c, basis=bad))
        scope = prep._scope(c.user, c.exact_scope)
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(lambda: prep._basis(c.basis, scope))
        self.assertEqual(caught.exception.code, 'PREPARATION_CAPACITY_REFERENCE_INVALID')
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_routing_permission_is_fresh_even_before_idempotent_replay(self):
        c = self.case
        save_capacity_reference(c)
        RolePermission.objects.filter(role=c.f.role, permission__code=ROUTING_PERMISSION).delete()
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(lambda: save_capacity_reference(c))
        self.assertEqual(caught.exception.code, 'PERMISSION_DENIED')

    def test_date_scheduling_consumer_is_not_a_no_date_relationship(self):
        c = self.case
        bad = deepcopy(c.basis)
        bad['entries'][0]['capacityConsumptionReference']['consumer'] = 'DATE_SCHEDULING'
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(lambda: save_capacity_reference(c, basis=bad))
        self.assertEqual(caught.exception.code, 'PREPARATION_CAPACITY_REFERENCE_INVALID')
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_actual_saved_capacity_and_scope_cannot_be_replaced(self):
        c = self.case
        bad = deepcopy(c.basis)
        bad['entries'][0]['capacityConsumptionReference']['standardCapacityId'] += 99999
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(lambda: save_capacity_reference(c, basis=bad))
        wrong = deepcopy(c.exact_scope)
        wrong['routingStepId'] += 99999
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(lambda: prep.resolve_capacity_consumption_reference(user=c.user, exact_scope=wrong))
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_capacity_or_unified_header_drift_invalidates_current_reference(self):
        c = self.case
        save_capacity_reference(c)
        StandardCapacity.objects.filter(code='SIM-SCOPE-AUX').update(preparation_days='.2')
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(self.resolve)

    def test_bad_native_preparation_ledger_cannot_supply_consumption_permission(self):
        c = self.case
        saved = save_capacity_reference(c)
        MasterDataWriteRequest.objects.filter(pk=saved['writeRequestId']).update(status='RESERVED')
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(self.resolve)
        self.assertEqual(caught.exception.code, 'PREPARATION_HISTORY_INVALID')

    def test_next_day_reference_hash_is_stable_and_interval_still_gates_reads(self):
        c = self.case
        save_capacity_reference(c)
        current = c.fixture.readonly(self.resolve)
        tomorrow = c.fixture.readonly(lambda: self.resolve(on_date=date.today() + timedelta(days=1)))
        self.assertEqual(current['referenceHash'], tomorrow['referenceHash'])
        self.assertNotIn('assessmentDate', repr(tomorrow))
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(lambda: self.resolve(on_date=date.today() - timedelta(days=1)))
        self.assertEqual(caught.exception.code, 'PREPARATION_CAPACITY_REFERENCE_INACTIVE')

    def test_native_revision_appends_new_reference_and_preserves_old_entry(self):
        c = self.case
        first = save_capacity_reference(c)
        row = OperationInputPreparationDraft.objects.get(pk=first['recordId'])
        old = deepcopy(row.business_basis['entries'])
        basis = deepcopy(row.business_basis)
        entry = deepcopy(c.basis['entries'][0])
        entry['exactStatement'] += ' Additional explicit scope confirmation.'
        basis['entries'].append(entry)
        second = save_capacity_reference(c, basis=basis, key='sim-native-capacity-reference-2', revision=1)
        row.refresh_from_db()
        self.assertEqual(row.revision, 2)
        self.assertEqual(row.business_basis['entries'][:len(old)], old)
        self.assertEqual(second['stateTransitionWriteCount'], 0)
        self.assertEqual(second['capacityConsumptionReference']['revision'], 2)
        self.assertEqual(len(second['capacityConsumptionReference']['auditIds']), 2)

    def test_current_edit_version_does_not_replace_frozen_consumption_scope(self):
        c = self.case
        ids = [row['designItemId'] for row in c.context['objectCoverage']]
        ProductDesignItem.objects.filter(pk__in=ids).update(version=F('version') + 1)
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(lambda: prep.read_preparation(user=c.user, exact_scope=c.exact_scope))
        self.assertEqual(caught.exception.details.get('sourceCode'), 'OBJECT_APPLICABILITY_OBJECT_DRIFT')
        preview = c.fixture.readonly(lambda: prep.read_preparation(user=c.user, exact_scope=c.exact_scope,
            consumer='ALLOCATED_LOAD_NO_DATE'))
        self.assertEqual(preview['contextHash'], c.context['contextHash'])
        self.assertEqual(preview['objectCoverage'], c.context['objectCoverage'])
        saved = save_capacity_reference(c)
        current = c.fixture.readonly(lambda: prep.read_preparation(user=c.user, exact_scope=c.exact_scope))
        self.assertEqual(current['contextHash'], preview['contextHash'])
        self.assertEqual(current['capacityConsumptionReference']['recordId'], saved['recordId'])
        self.assertTrue(c.fixture.readonly(self.resolve)['formalConsumptionValidated'])

    def test_damaged_frozen_snapshot_cannot_be_replaced_by_a_current_design(self):
        c = self.case
        obj = OrderEngineeringBaselineItem.objects.get(pk=c.context['objectCoverage'][0]['baselineItemId'])
        damaged = deepcopy(obj.content_snapshot)
        damaged['SIMULATED_FOR_TEST_corruption'] = True
        OrderEngineeringBaselineItem.objects.filter(pk=obj.pk).update(content_snapshot=damaged)
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(lambda: prep.read_preparation(user=c.user, exact_scope=c.exact_scope,
                consumer='ALLOCATED_LOAD_NO_DATE'))
        with self.assertRaises(prep.OperationInputPreparationError):
            c.fixture.readonly(lambda: save_capacity_reference(c))
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_unconfigured_resolver_is_none_but_removed_marker_is_not_none(self):
        c = self.case
        ProductDesignItem.objects.filter(pk__in=[row['designItemId'] for row in c.context['objectCoverage']]).update(
            version=F('version') + 1)
        self.assertIsNone(c.fixture.readonly(self.resolve))
        saved = save_capacity_reference(c)
        row = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        damaged = deepcopy(row.business_basis)
        del damaged['entries'][-1]['capacityConsumptionReference']
        with self.assertRaises(ValidationError):
            OperationInputPreparationDraft.objects.filter(pk=row.pk).update(business_basis=damaged)
        # SIMULATED_FOR_TEST corruption injection in the guarded disposable DB.
        # Normal ORM tampering is forbidden above; this reaches the independent
        # historical-ledger check without altering its native implementation.
        with connection.cursor() as cursor:
            cursor.execute('UPDATE ' + connection.ops.quote_name(row._meta.db_table)
                + ' SET business_basis=%s WHERE id=%s', (json.dumps(damaged, ensure_ascii=False), row.pk))
            self.assertEqual(cursor.rowcount, 1)
        with self.assertRaises(prep.OperationInputPreparationError) as caught:
            c.fixture.readonly(self.resolve)
        self.assertEqual(caught.exception.code, 'PREPARATION_HISTORY_INVALID')

    def test_existing_get_previews_the_same_context_used_by_existing_post(self):
        from .views import ProductionFoundationA1View
        c = self.case
        ProductDesignItem.objects.filter(pk__in=[row['designItemId'] for row in c.context['objectCoverage']]).update(
            version=F('version') + 1)
        factory = APIRequestFactory()
        request = factory.get('/api/pde/a1-foundation/operations/', {
            'action': 'operationWorkloadSources', 'operationId': c.step.operation_id,
            'productionPlanId': c.plan.pk, 'routingStepId': c.step.pk,
            'preparationConsumer': 'ALLOCATED_LOAD_NO_DATE'})
        force_authenticate(request, user=c.user)
        response = c.fixture.readonly(lambda: ProductionFoundationA1View.as_view()(request, entity='operations'))
        self.assertEqual(response.status_code, 200, response.data)
        preview = response.data['context']['inputPreparation']
        self.assertEqual(preview['contextHash'], c.context['contextHash'])
        self.assertEqual(preview['context']['consumer'], 'ALLOCATED_LOAD_NO_DATE')
        self.assertEqual(Decimal(preview['inputQuantity']), Decimal('4'))
        self.assertNotIn('SAVED_LOAD_UNKNOWN', [row['code'] for row in preview['remainingItems']])
        request = factory.post('/api/pde/a1-foundation/operations/', {
            'action': 'saveOperationInputPreparation', 'exactScope': c.exact_scope,
            'businessBasis': c.basis, 'expectedContextHash': preview['contextHash'],
            'expectedRevision': 0, 'idempotencyKey': 'sim-native-consumption-http',
            'reason': 'SIMULATED_FOR_TEST same existing maintenance context'}, format='json')
        force_authenticate(request, user=c.user)
        response = ProductionFoundationA1View.as_view()(request, entity='operations')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['statusCode'], 'POSITIVE_CAPACITY_REFERENCE_RECORDED')
        reference = c.fixture.readonly(self.resolve)
        self.assertEqual(reference['recordId'], response.data['recordId'])
