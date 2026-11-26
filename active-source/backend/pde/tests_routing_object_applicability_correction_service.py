"""SIMULATED_FOR_TEST: real native append-only correction in isolated DBs.

No production connection, date/duration evaluation or formal business write.
Faults bypass immutable guards only inside Django's disposable test database.
"""
from copy import deepcopy
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ModelState
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, RolePermission
from . import production_foundation_service as foundation
from . import routing_object_applicability_service as original
from . import routing_object_applicability_correction_service as service
from .models import RoutingStepObjectApplicability, RoutingStepObjectApplicabilityCorrection
from .routing_version_successor_service import ROUTING_PERMISSION, RoutingVersionChangeError
from .operation_requirement_service import OperationRequirementError
from .tests_routing_object_applicability_service import make_object_applicability_fixture

REASON = 'SIMULATED_FOR_TEST formal correction'


def make_correction_fixture(*, f=None, plan=None):
    fixture = make_object_applicability_fixture(f=f, plan=plan)
    fixture.root_result = original.confirm_group(fixture.f.user, fixture.plan.pk, fixture.f.step.pk,
        fixture.contributions, 'SIMULATED_FOR_TEST object applicability')
    fixture.roots = list(RoutingStepObjectApplicability.objects.filter(
        pk__in=[row['recordId'] for row in fixture.root_result['objects']]).order_by('baseline_item_id'))
    return fixture


def build_correction_contributions(fixture, *, decision=original.REQUIRED):
    prepared = service.prepare_group(fixture.f.user, fixture.plan.pk, fixture.f.step.pk,
        [row.pk for row in fixture.roots])
    by_id = {row.pk: row for row in fixture.roots}
    contributions = []
    for row in prepared['objects']:
        root = by_id[row['rootRecordId']]
        basis = deepcopy(root.basis)
        basis['decisionReference'] = {'code': 'SIMULATED_CORRECTED_DECISION',
            'statement': 'Synthetic authorized corrected requirement',
            'reference': 'SIMULATED_FOR_TEST correction', 'referenceSha256': 'b' * 64}
        contributions.append({key: row[key] for key in ('rootRecordId', 'baselineItemId', 'contextHash',
            'expectedCurrentCorrectionId', 'expectedCurrentRecordHash')})
        contributions[-1].update(decision=decision, basis=basis, idempotencyKey=row['suggestedIdempotencyKey'])
    return contributions


class RoutingObjectApplicabilityCorrectionTests(TestCase):
    def setUp(self):
        self.fixture = make_correction_fixture()
        self.f, self.plan, self.roots = self.fixture.f, self.fixture.plan, self.fixture.roots
        self.contributions = build_correction_contributions(self.fixture)

    def save(self, contributions=None, *, reason=REASON):
        return service.correct_group(self.f.user, self.plan.pk, self.f.step.pk,
            self.contributions if contributions is None else contributions, reason)

    def read(self):
        return original.resolve_for_step(self.f.step, production_plan=self.plan,
            manufacturing_output=self.f.output, engineering_calculation=self.f.source_calc,
            order_engineering_instance=self.f.instance, order_engineering_baseline=self.f.baseline,
            bom_version=self.f.bom_version)

    def snapshot(self):
        return self.f.full_database_snapshot()

    def raw(self, obj, field, value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        column = obj._meta.get_field(field).column
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {connection.ops.quote_name(obj._meta.db_table)} '
                f'SET {connection.ops.quote_name(column)}=%s WHERE id=%s', [value, obj.pk])

    def readonly(self, action):
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = action()
        self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in
            {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER'} for row in queries))
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        self.assertEqual(self.snapshot(), before)
        return result

    def test_three_native_corrections_exact_four_tables_and_new_audits_keep_v1_history(self):
        before = self.snapshot()
        old_rows = list(RoutingStepObjectApplicability.objects.order_by('pk').values())
        with CaptureQueriesContext(connection) as queries:
            result = self.save()
        self.assertEqual((result['createdCount'], result['replayedCount']), (3, 0))
        self.assertFalse(any('password' in row['sql'].lower() for row in queries))
        after = self.snapshot()
        self.assertEqual({table for table in before if before[table] != after[table]},
            {'pde_routing_object_applicability_correction', 'masterdata_external_identity',
             'masterdata_write_request', 'system_organization_operating_audits'})
        self.assertEqual(old_rows, list(RoutingStepObjectApplicability.objects.order_by('pk').values()))
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=service.ACTION).count(), 3)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=service.ACTION,
            status=MasterDataWriteRequest.Status.COMMITTED).count(), 3)
        self.assertEqual(ExternalIdentity.objects.filter(source_object_type=service.SOURCE_OBJECT_TYPE).count(), 3)
        for proof in result['objects']:
            row = RoutingStepObjectApplicabilityCorrection.objects.get(pk=proof['recordId'])
            audit = OrganizationOperatingAuditRecord.objects.get(pk=proof['auditId'])
            self.assertEqual((audit.target_type, int(audit.target_id)), (type(row).__name__, row.pk))
            self.assertEqual(audit.after_snapshot['state']['previousDecision'], original.NOT_APPLICABLE)
            self.assertEqual(audit.after_snapshot['state']['newDecision'], original.REQUIRED)
        read = self.readonly(self.read)
        self.assertEqual((read['result'], read['complete']), (original.REQUIRED, True))
        self.assertEqual(read['requiredBaselineItemIds'], sorted(row.baseline_item_id for row in self.roots))
        self.assertEqual(read['excludedBaselineItemIds'], [])
        self.assertEqual(read['unknownBaselineItemIds'], [])
        for proof in read['objects']:
            self.assertEqual(proof['effectiveDecision'], original.REQUIRED)
            self.assertEqual(proof['rootRecordProof']['decision'], original.NOT_APPLICABLE)
            self.assertEqual(proof['currentCorrectionProof']['recordType'], 'RoutingStepObjectApplicabilityCorrection')

    def test_native_prepare_and_exact_replay_are_readonly(self):
        self.readonly(lambda: service.prepare_group(self.f.user, self.plan.pk, self.f.step.pk,
            [row.pk for row in self.roots]))
        first = self.save()
        replay = self.readonly(self.save)
        self.assertEqual((replay['createdCount'], replay['replayedCount']), (0, 3))
        self.assertEqual([row['recordId'] for row in replay['objects']], [row['recordId'] for row in first['objects']])
        self.assertTrue(all(row['idempotentReplay'] for row in replay['objects']))

    def test_second_generation_and_historical_replay_do_not_restore_old_leaf(self):
        first = self.save()
        second_payload = build_correction_contributions(self.fixture, decision=original.PENDING)
        second = self.save(second_payload, reason=REASON + ' subsequent')
        self.assertEqual(second['createdCount'], 3)
        self.assertEqual(self.readonly(self.read)['result'], original.PENDING)
        replay = self.readonly(self.save)
        self.assertEqual(replay['createdCount'], 0)
        self.assertEqual([row['recordId'] for row in replay['objects']], [row['recordId'] for row in first['objects']])
        scope = original._load_scope(self.plan.pk, self.f.step.pk)
        for root in self.roots:
            chain = self.readonly(lambda: service.read_chain(root, scope))
            self.assertEqual(len(chain['history']), 2)
            self.assertEqual(chain['current'].decision, original.PENDING)
            audit = OrganizationOperatingAuditRecord.objects.get(pk=chain['history'][-1]['proof']['auditId'])
            self.assertEqual(audit.after_snapshot['state']['previousDecision'], original.REQUIRED)
            self.assertEqual(audit.after_snapshot['state']['newDecision'], original.PENDING)

    def test_changed_key_payload_stale_predecessor_and_partial_recovery(self):
        self.save(self.contributions[:1])
        recovered = self.save()
        self.assertEqual((recovered['createdCount'], recovered['replayedCount']), (2, 1))
        for field, value in (('idempotencyKey', 'SIM-NEW-ALIAS'), ('decision', original.PENDING),
                             ('contextHash', '0' * 64), ('expectedCurrentRecordHash', '0' * 64),
                             ('expectedCurrentCorrectionId', True)):
            with self.subTest(field=field):
                payload = deepcopy(self.contributions)
                payload[0][field] = value
                before = self.snapshot()
                with self.assertRaises(RoutingVersionChangeError):
                    self.save(payload)
                self.assertEqual(self.snapshot(), before)
        before = self.snapshot()
        with self.assertRaises(RoutingVersionChangeError):
            self.save(reason=REASON + ' changed')
        self.assertEqual(self.snapshot(), before)

    def test_second_audit_failure_rolls_back_every_new_business_and_support_row(self):
        native_audit, calls = foundation._audit, []
        def fail_second(**kwargs):
            if kwargs['action_code'] == service.ACTION:
                calls.append(kwargs['instance'].root_record_id)
                if len(calls) == 2:
                    raise RuntimeError('SIMULATED_FOR_TEST second audit failure')
            return native_audit(**kwargs)
        before = self.snapshot()
        with patch.object(foundation, '_audit', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(RoutingStepObjectApplicabilityCorrection.objects.count(), 0)

    def test_second_committed_proof_failure_rolls_back_whole_group(self):
        native_commit, calls = service._committed, []
        def fail_second(row, *args, **kwargs):
            calls.append(row.root_record_id)
            if len(calls) == 2:
                raise RoutingVersionChangeError('SIMULATED_COMMIT_FAILURE', 'Synthetic failure')
            return native_commit(row, *args, **kwargs)
        before = self.snapshot()
        with patch.object(service, '_committed', side_effect=fail_second):
            with self.assertRaises(RoutingVersionChangeError):
                self.save()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)

    def test_node_and_source_hash_drift_new_reads_and_writes_fail_closed(self):
        saved = self.save()
        row = RoutingStepObjectApplicabilityCorrection.objects.get(pk=saved['objects'][0]['recordId'])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=saved['objects'][0]['auditId'])
        wrong_audit = deepcopy(audit.after_snapshot)
        wrong_audit['executionChain']['account'] = 'SIM-OTHER-ACTOR'
        foreign = Company.objects.create(name='SIM_CORRECTION_FOREIGN_COMPANY')
        faults = [(row, 'context_hash', '0' * 64), (row, 'root_record_hash', '0' * 64),
            (row, 'predecessor_hash', '0' * 64), (row, 'company', foreign.pk),
            (audit, 'after_snapshot', wrong_audit), (self.f.facts[0], 'status', 'inactive')]
        for target, field, value in faults:
            with self.subTest(field=field):
                old = deepcopy(getattr(target, target._meta.get_field(field).attname))
                self.raw(target, field, value)
                try:
                    result = self.readonly(self.read)
                    self.assertEqual(result['result'], original.PENDING)
                    self.assertFalse(result['complete'])
                    self.assertIn(row.root_record.baseline_item_id, result['unknownBaselineItemIds'])
                    before = self.snapshot()
                    with self.assertRaises((RoutingVersionChangeError, OperationRequirementError)):
                        self.save()
                    self.assertEqual(self.snapshot(), before)
                finally:
                    self.raw(target, field, old)
        self.assertEqual(self.readonly(self.read)['result'], original.REQUIRED)

    def test_typed_chain_cycle_and_moved_node_are_not_hidden_by_old_root(self):
        self.save()
        self.save(build_correction_contributions(self.fixture, decision=original.PENDING), reason=REASON + ' second')
        rows = list(RoutingStepObjectApplicabilityCorrection.objects.filter(root_record=self.roots[0]).order_by('pk'))
        first, second = rows
        self.raw(first, 'predecessor', second.pk)
        self.assertEqual(self.readonly(self.read)['result'], original.PENDING)
        self.raw(first, 'predecessor', None)
        self.raw(second, 'root_record', self.roots[1].pk)
        result = self.readonly(self.read)
        self.assertEqual(result['result'], original.PENDING)
        self.assertTrue(any(reason['code'] == 'OBJECT_CORRECTION_AUDIT_SET_MISMATCH' for reason in result['reasons']))
        self.raw(second, 'root_record', self.roots[0].pk)

    def test_immutable_model_and_database_first_predecessor_uniqueness(self):
        self.save()
        row = RoutingStepObjectApplicabilityCorrection.objects.first()
        for action in (lambda: row.save(), lambda: row.delete(),
            lambda: RoutingStepObjectApplicabilityCorrection.objects.all().update(reason='bad'),
            lambda: RoutingStepObjectApplicabilityCorrection.objects.all().delete(),
            lambda: RoutingStepObjectApplicabilityCorrection.objects.bulk_create([]),
            lambda: RoutingStepObjectApplicabilityCorrection.objects.bulk_update([row], ['reason'])):
            with self.assertRaises(ValidationError):
                action()
        clone = deepcopy(row)
        clone.pk = None
        clone.write_request = row.root_record.write_request
        with self.assertRaises(IntegrityError), transaction.atomic():
            clone.save_base(force_insert=True, raw=True)
        self.save(build_correction_contributions(self.fixture, decision=original.PENDING), reason=REASON + ' next')
        child = RoutingStepObjectApplicabilityCorrection.objects.get(predecessor=row)
        clone = deepcopy(child)
        clone.pk = None
        clone.write_request = row.root_record.write_request
        with self.assertRaises(IntegrityError), transaction.atomic():
            clone.save_base(force_insert=True, raw=True)

    def test_permission_and_wrong_consumer_scope_remain_native(self):
        RolePermission.objects.filter(role=self.f.role, permission__code=ROUTING_PERMISSION).delete()
        before = self.snapshot()
        with self.assertRaises(RoutingVersionChangeError):
            self.save()
        self.assertEqual(self.snapshot(), before)
        result = original.resolve_for_step(self.f.step, production_plan=self.plan,
            manufacturing_output=self.f.output.pk + 999)
        self.assertEqual(result['result'], original.PENDING)


class CorrectionStructureMissingTests(TransactionTestCase):
    def test_registered_but_missing_table_is_domain_blocked_without_reading_missing_rows(self):
        with transaction.atomic():
            fixture = make_correction_fixture()
        with connection.schema_editor() as editor:
            editor.delete_model(RoutingStepObjectApplicabilityCorrection)
        try:
            with self.assertRaises(RoutingVersionChangeError) as caught:
                service.prepare_group(fixture.f.user, fixture.plan.pk, fixture.f.step.pk,
                    [row.pk for row in fixture.roots])
            self.assertEqual(caught.exception.code, 'OBJECT_CORRECTION_STRUCTURE_REQUIRED')
            result = original.resolve_for_step(fixture.f.step, production_plan=fixture.plan)
            self.assertEqual(result['result'], original.PENDING)
            self.assertEqual(result['excludedBaselineItemIds'], [])
        finally:
            with connection.schema_editor() as editor:
                editor.create_model(RoutingStepObjectApplicabilityCorrection)


class CorrectionMigrationContractTests(SimpleTestCase):
    @override_settings(MIGRATION_MODULES={})
    def test_single_create_model_dependency_and_exact_current_model_state(self):
        module = importlib.import_module('pde.migrations.0042_routing_step_object_applicability_correction')
        migration = module.Migration('0042_routing_step_object_applicability_correction', 'pde')
        self.assertEqual(migration.dependencies, [('pde', '0041_routing_step_object_applicability')])
        self.assertEqual(len(migration.operations), 1)
        self.assertEqual(type(migration.operations[0]).__name__, 'CreateModel')
        loader = MigrationLoader(None)
        state = loader.project_state([('pde', '0041_routing_step_object_applicability')])
        migration.operations[0].state_forwards('pde', state)
        actual = ModelState.from_model(RoutingStepObjectApplicabilityCorrection)
        expected = state.models[('pde', 'routingstepobjectapplicabilitycorrection')]
        self.assertEqual(expected.options, actual.options)
        self.assertEqual({name: field.deconstruct()[1:] for name, field in expected.fields.items()},
            {name: field.deconstruct()[1:] for name, field in actual.fields.items()})
