"""SIMULATED_FOR_TEST: call-owned publication rows, never cached approvals.

Only the reviewed named isolated runner may import this module. Existing
fixtures retain their declared upstream stubs; release/readback/ledger/audit
and state-transition readers under test are native. Deliberate corruption is
confined to that disposable fixture database.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from masterdata.models import MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as native
from . import tests_route_workload_final_read as isolated_guard  # retain named-runner guard
from . import tests_manufacturing_output_release as manufacturing_fixture
from . import manufacturing_output_release_service as manufacturing
from . import engineering_document_version_release_service as document
from . import tests_classified_fact_eor as classified_fixture
from . import tests_plan_legal_extension_admission as legal_fixture


class ReadOnlyAssertions:
    def readonly(self, action):
        before = classified_fixture.ClassifiedFactEorTests.full_database_snapshot(self)
        epoch = connection.connection.total_changes
        with CaptureQueriesContext(connection) as queries:
            value = action()
        self.assertEqual(before, classified_fixture.ClassifiedFactEorTests.full_database_snapshot(self))
        self.assertEqual(connection.connection.total_changes, epoch)
        self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
            'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
        } for row in queries), list(queries))
        return value, list(queries)

    def cached_models(self, cache, model):
        result = []
        for key, entry in cache.items():
            if not isinstance(key, tuple) or key[0] != 'guarded_raw_rows':
                continue
            rows = entry[0]
            for row in rows if isinstance(rows, (tuple, list)) else [rows]:
                if isinstance(row, model):
                    result.append(row)
        return result


class GuardedPublicationRowsTests(ReadOnlyAssertions, TestCase):
    def setUp(self):
        self.company = Company.objects.create(code='RAW-PUB', name='Raw publication test company')
        self.user = User.objects.create_user(username='raw-pub', password=None,
            company_id=self.company.pk, real_name='Raw fixture actor')
        self.audit = OrganizationOperatingAuditRecord.objects.create(
            action_code='SIMULATED_FOR_TEST', actor=self.user, organization=self.company,
            target_type='SIMULATED_FOR_TEST', target_id=1, target_label='Raw row fixture',
            reason='SIMULATED_FOR_TEST', before_snapshot={},
            after_snapshot={'nested': {'values': [True, 1, 1.0]},
                'left': {'values': [True, 1, 1.0]}, 'right': {'values': [True, 1, 1.0]}})

    def read_audit(self, cache, *, related=False):
        def load():
            query = OrganizationOperatingAuditRecord.objects
            if related:
                query = query.select_related('actor').only(
                    *(field.attname for field in OrganizationOperatingAuditRecord._meta.concrete_fields),
                    'actor__id', 'actor__username', 'actor__real_name')
            return query.get(pk=self.audit.pk)
        return native._read_guarded_raw(cache, ('test-audit', self.audit.pk, related), load)

    def test_full_raw_rows_repeat_without_sql_and_equal_json_aliases_remain_valid(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first, initial = self.readonly(lambda: self.read_audit(cache))
            self.assertEqual(len(initial), 1)
            cache['unrelated-proof'] = 'retained'
            shared = first.after_snapshot['nested']
            first.after_snapshot = {'nested': deepcopy(shared)}
            first.after_snapshot['left'] = deepcopy(self.audit.after_snapshot['left'])
            first.after_snapshot['right'] = first.after_snapshot['left']
            second, repeated = self.readonly(lambda: self.read_audit(cache))
            self.assertIs(second, first)
            self.assertEqual(repeated, [])
            self.assertEqual(cache['unrelated-proof'], 'retained')
            self.assertEqual(first.after_snapshot, self.audit.after_snapshot)

    def test_nested_type_and_related_model_pollution_refetch_and_clear_proofs(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            for index, replacement in ((0, 1), (1, 1.0), (2, True)):
                with self.subTest(index=index, replacement=type(replacement).__name__):
                    first = self.read_audit(cache, related=True)
                    cache['dependent-proof'] = 'must disappear'
                    first.after_snapshot['nested']['values'][index] = replacement
                    repaired, queries = self.readonly(lambda: self.read_audit(cache, related=True))
                    self.assertEqual(len(queries), 1)
                    self.assertIsNot(repaired, first)
                    self.assertEqual(repaired.after_snapshot, self.audit.after_snapshot)
                    self.assertNotIn('dependent-proof', cache)
            first = self.read_audit(cache, related=True)
            cache['dependent-proof'] = True
            first.actor.real_name = 'polluted loaded relationship'
            repaired, queries = self.readonly(lambda: self.read_audit(cache, related=True))
            self.assertEqual(len(queries), 1)
            self.assertEqual(repaired.actor.real_name, self.user.real_name)
            self.assertNotIn('dependent-proof', cache)

    def test_deferred_fields_and_lazy_relationship_growth_are_conservatively_refetched(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first, initial = self.readonly(lambda: self.read_audit(cache, related=True))
            self.assertEqual(len(initial), 1)
            self.assertIn('password', first.actor.get_deferred_fields())
            _, repeated = self.readonly(lambda: self.read_audit(cache, related=True))
            self.assertEqual(repeated, [])
            self.assertIn('password', first.actor.get_deferred_fields())
            # A newly loaded concrete value is a graph change. The guard must
            # refetch, never ignore new fields or trigger credential reads.
            self.assertEqual(first.actor.is_active, self.user.is_active)
            cache['dependent-proof'] = True
            second, queries = self.readonly(lambda: self.read_audit(cache, related=True))
            self.assertEqual(len(queries), 1)
            self.assertIsNot(second, first)
            self.assertIn('is_active', second.actor.get_deferred_fields())
            self.assertIn('password', second.actor.get_deferred_fields())
            self.assertNotIn('dependent-proof', cache)
            _, repeated = self.readonly(lambda: self.read_audit(cache, related=True))
            self.assertEqual(repeated, [])
            bare = self.read_audit(cache)
            self.assertNotIn('actor', bare._state.fields_cache)
            self.assertEqual(bare.actor.pk, self.user.pk)
            replacement, queries = self.readonly(lambda: self.read_audit(cache))
            self.assertEqual(len(queries), 1)
            self.assertIsNot(replacement, bare)
            self.assertNotIn('actor', replacement._state.fields_cache)

    def test_typed_date_decimal_values_and_unsupported_values_keep_native_behavior(self):
        stamp = datetime(2026, 10, 21, 2, 3, tzinfo=timezone.utc)
        expected = {'day': date(2026, 10, 21), 'at': stamp, 'quantity': Decimal('1.000')}
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            loader = lambda: deepcopy(expected)
            first = native._read_guarded_raw(cache, 'values', loader)
            self.assertEqual(first, expected)
            self.assertIs(native._read_guarded_raw(cache, 'values', loader), first)
            cache['dependent-proof'] = True
            first['quantity'] = 1.0
            restored = native._read_guarded_raw(cache, 'values', loader)
            self.assertIs(type(restored['quantity']), Decimal)
            self.assertIs(type(restored['day']), date)
            self.assertIs(type(restored['at']), datetime)
            self.assertNotIn('dependent-proof', cache)
            with patch.object(native, '_read_once', wraps=native._read_once) as read_once:
                cache['unrelated-proof'] = True
                unknown1 = native._read_guarded_raw(cache, 'unknown', object)
                unknown2 = native._read_guarded_raw(cache, 'unknown', object)
            self.assertEqual(read_once.call_count, 2)
            self.assertIsNot(unknown1, unknown2)
            self.assertTrue(cache['unrelated-proof'])
            self.assertFalse(any(isinstance(key, tuple) and key[-1] == 'unknown' for key in cache))
            class UnknownIsoformat:
                def isoformat(self):
                    raise AssertionError('Unsupported type must not be converted or shared')
            unknown1 = native._read_guarded_raw(cache, 'unknown-isoformat', UnknownIsoformat)
            unknown2 = native._read_guarded_raw(cache, 'unknown-isoformat', UnknownIsoformat)
            self.assertIsNot(unknown1, unknown2)
            self.assertTrue(cache['unrelated-proof'])
            self.assertFalse(any(isinstance(key, tuple) and key[-1] == 'unknown-isoformat' for key in cache))
            class CustomDict(dict):
                pass
            class CustomList(list):
                pass
            for custom in (CustomDict, CustomList):
                with self.subTest(custom=custom.__name__):
                    first = native._read_guarded_raw(cache, custom.__name__, custom)
                    first.extra_state = 'mutated unsupported state'
                    second = native._read_guarded_raw(cache, custom.__name__, custom)
                    self.assertIsNot(first, second)
                    self.assertFalse(hasattr(second, 'extra_state'))
                    self.assertTrue(cache['unrelated-proof'])
                    self.assertFalse(any(isinstance(key, tuple) and key[-1] == custom.__name__ for key in cache))
            first = self.read_audit(cache)
            first.after_snapshot = CustomDict(first.after_snapshot)
            first.after_snapshot.extra_state = 'unsupported direct model value'
            second, queries = self.readonly(lambda: self.read_audit(cache))
            self.assertEqual(len(queries), 1)
            self.assertIsNot(first, second)
            self.assertIs(type(second.after_snapshot), dict)

    def test_plain_foreign_actor_company_and_expired_transactions_never_share(self):
        for cache in (None, {}):
            with self.subTest(kind=type(cache).__name__):
                first, _ = self.readonly(lambda: self.read_audit(cache))
                second, queries = self.readonly(lambda: self.read_audit(cache))
                self.assertEqual(len(queries), 1)
                self.assertIsNot(second, first)
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first = self.read_audit(cache)
            for actor in (User(pk=self.user.pk + 1, company_id=self.company.pk),
                          User(pk=self.user.pk, company_id=self.company.pk + 1)):
                native._bind_current_actor(cache, actor)
                second, queries = self.readonly(lambda: self.read_audit(cache))
                self.assertEqual(len(queries), 1)
                self.assertIsNot(second, first)
            native._bind_current_actor(cache, self.user)
        second, queries = self.readonly(lambda: self.read_audit(cache))
        self.assertEqual(len(queries), 1)
        self.assertIsNot(second, first)

    def test_same_connection_write_invalidates_raw_and_dependent_proofs(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first = self.read_audit(cache)
            cache['dependent-proof'] = True
            OrganizationOperatingAuditRecord.objects.filter(pk=self.audit.pk).update(
                after_snapshot={'new': 'native database value'})
            second, queries = self.readonly(lambda: self.read_audit(cache))
            self.assertEqual(len(queries), 1)
            self.assertIsNot(second, first)
            self.assertEqual(second.after_snapshot, {'new': 'native database value'})
            self.assertNotIn('dependent-proof', cache)


class ManufacturingPublicationRawReadbackTests(ReadOnlyAssertions, TestCase):
    def setUp(self):
        self.enterContext(override_settings(
            PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=manufacturing_fixture.SCOPE))
        self.case = manufacturing_fixture.ManufacturingOutputReleaseTests(methodName='runTest')
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.case.release()
        self.case.output.refresh_from_db()
        self.output, self.user = self.case.output, self.case.executor

    def test_cached_and_uncached_readback_equal_with_no_repeated_ledger_sql(self):
        expected, old_queries = self.readonly(lambda: manufacturing.release_readback(self.output))
        self.assertTrue(expected['completed'])
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first, initial = self.readonly(lambda: manufacturing.release_readback(self.output, read_cache=cache))
            second, repeated = self.readonly(lambda: manufacturing.release_readback(self.output, read_cache=cache))
            self.assertEqual(first, expected)
            self.assertEqual(second, expected)
            self.assertGreaterEqual(len(old_queries), 4)
            self.assertGreaterEqual(len(initial), 4)
            self.assertEqual(repeated, [])
            self.output.release_status = 'draft'
            rejected, _ = self.readonly(lambda: manufacturing.release_readback(self.output, read_cache=cache))
            self.assertFalse(rejected['completed'])
            self.output.release_status = 'released_to_manufacturing'
            self.assertEqual(manufacturing.release_readback(self.output, read_cache=cache), expected)

    def test_cached_publication_models_are_guarded_and_native_bad_ledger_is_rejected(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            expected = manufacturing.release_readback(self.output, read_cache=cache)
            request = self.cached_models(cache, MasterDataWriteRequest)[0]
            cache['dependent-proof'] = True
            request.result['auditId'] = -1
            restored, _ = self.readonly(lambda: manufacturing.release_readback(self.output, read_cache=cache))
            self.assertEqual(restored, expected)
            self.assertNotIn('dependent-proof', cache)
            request = self.cached_models(cache, MasterDataWriteRequest)[0]
            bad_result = deepcopy(request.result)
            bad_result['businessStateTransitionId'] = -1
            legal_fixture.PlanLegalExtensionAdmissionTests.raw(self, request, 'result', bad_result)
            rejected, _ = self.readonly(lambda: manufacturing.release_readback(self.output, read_cache=cache))
            self.assertFalse(rejected['completed'])
            self.assertEqual(rejected, manufacturing.release_readback(self.output))


class EngineeringDocumentPublicationRawReadbackTests(ReadOnlyAssertions, TestCase):
    def setUp(self):
        from .tests_engineering_document_version_release import EngineeringDocumentVersionReleaseTests
        self.case = EngineeringDocumentVersionReleaseTests(methodName='runTest')
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.case.release()
        self.case.version.refresh_from_db()
        self.version, self.user = self.case.version, self.case.publisher

    def test_complete_native_review_still_runs_on_every_equal_cached_readback(self):
        expected, old_queries = self.readonly(lambda: document.release_readback(self.version))
        self.assertTrue(expected['completed'])
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            with patch.object(document, 'review_readback', wraps=document.review_readback) as review:
                first, initial = self.readonly(lambda: document.release_readback(self.version, read_cache=cache))
                second, repeated = self.readonly(lambda: document.release_readback(self.version, read_cache=cache))
            self.assertEqual(review.call_count, 2)
            self.assertEqual(first, expected)
            self.assertEqual(second, expected)
            def publication_queries(rows):
                return [row for row in rows if document.RELEASE_ACTION in row['sql']]
            self.assertEqual(len(publication_queries(old_queries)), 3)
            self.assertEqual(len(publication_queries(initial)), 3)
            self.assertEqual(publication_queries(repeated), [])
            self.assertEqual(len(initial) - len(repeated), 3)
            self.assertTrue(repeated)  # workflow, decisions and review transition remain fresh
            transitions = self.cached_models(cache, BusinessStateTransition)
            self.assertEqual(len(transitions), 1)
            self.assertIn('password', transitions[0].operator.get_deferred_fields())
            self.version.status = 'reviewed'
            rejected, _ = self.readonly(lambda: document.release_readback(self.version, read_cache=cache))
            self.assertFalse(rejected['completed'])
            self.assertEqual(rejected['statusCode'], 'reviewed')

    def test_review_transition_write_and_cached_actor_pollution_cannot_approve(self):
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            expected = document.release_readback(self.version, read_cache=cache)
            transition = self.cached_models(cache, BusinessStateTransition)[0]
            transition.operator.real_name = 'polluted publication actor'
            restored, _ = self.readonly(lambda: document.release_readback(self.version, read_cache=cache))
            self.assertEqual(restored, expected)
            review = document.review_readback(self.version)
            review_transition = BusinessStateTransition.objects.get(pk=review['businessStateTransitionId'])
            legal_fixture.PlanLegalExtensionAdmissionTests.raw(self, review_transition, 'target_state', 'draft')
            rejected, _ = self.readonly(lambda: document.release_readback(self.version, read_cache=cache))
            self.assertFalse(rejected['completed'])
            self.assertEqual(rejected, document.release_readback(self.version))
