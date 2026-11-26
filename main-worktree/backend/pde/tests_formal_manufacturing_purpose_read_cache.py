"""SIMULATED_FOR_TEST: persisted purpose reads reuse raw facts, never a decision.

The imported route fixture keeps its named isolated-runner guard. Successful
database reads, source traversal and purpose qualification are native. The one
DatabaseError is an explicit negative injection; it cannot become a cached
success. Fixture raw writes occur only before/between guarded reads.
"""
from unittest.mock import patch

from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from sales.models import SalesOrder, SalesOrderItem
from system.models import User
from . import operation_requirement_service as native
from . import tests_plan_legal_extension_admission as legal
from . import tests_route_workload_final_read as fixtures
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService as service


class FormalManufacturingPurposeReadCacheTests(TestCase):
    def setUp(self):
        self.case = fixtures.RouteWorkloadFinalNativeTests(methodName='runTest')
        self.case.setUp()
        self.f, self.user = self.case.f, self.case.f.user
        # Explicit disposable setup: use the existing compatibility column and
        # native order fields, without schema alteration or a published object.
        for field, value in (('business_purpose', 'FORMAL_SALE'),
                ('delivery_information', {'businessPurpose': 'FORMAL_SALE'}),
                ('acceptance_marker', ''), ('contract_reference', 'SIMULATED_FOR_TEST purpose')):
            legal.PlanLegalExtensionAdmissionTests.raw(self, self.f.order, field, value)
        self.order = SalesOrder.objects.get(pk=self.f.order.pk)
        self.source = SalesOrderItem.objects.select_related('sales_order').get(pk=self.f.item.pk)

    def readonly(self, callback):
        before = self.f.full_database_snapshot()
        epoch = connection.connection.total_changes

        def no_write(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if verb not in {'SELECT', 'PRAGMA', 'BEGIN', 'COMMIT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK'}:
                raise AssertionError('Purpose read attempted a write')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(no_write), CaptureQueriesContext(connection) as queries:
            try:
                return callback(), list(queries)
            finally:
                self.assertEqual(connection.connection.total_changes, epoch)
                self.assertEqual(self.f.full_database_snapshot(), before)

    def read(self, cache=None):
        return service.resolve(self.source, read_cache=cache) if cache is not None else service.resolve(self.source)

    @staticmethod
    def purpose_keys(cache):
        return [key for key in cache if isinstance(key, tuple) and str(key[0]).startswith('formal_manufacturing_')]

    def test_only_successful_raw_reads_reused_while_source_and_current_fields_requalify(self):
        expected, _ = self.readonly(self.read)
        self.assertEqual(expected['decisionCode'], 'FORMAL_MANUFACTURING_ELIGIBLE')
        cache = native._ReadOnlyProofCache(self.user)
        describe = connection.introspection.get_table_description
        with patch.object(connection.introspection, 'get_table_description', wraps=describe) as descriptions:
            first, queries = self.readonly(lambda: self.read(cache))
            second, repeated = self.readonly(lambda: self.read(cache))
            self.assertEqual(first, expected)
            self.assertEqual(second, expected)
            self.assertTrue(queries)
            self.assertEqual(repeated, [])
            self.assertEqual(descriptions.call_count, 1)
            # Only column metadata may be shared across distinct order PKs.
            missing_order = SalesOrder(pk=self.order.pk + 1000000, company_id=self.user.company_id)
            missing, missing_queries = self.readonly(lambda: service._database_purpose(missing_order, read_cache=cache))
            self.assertEqual(missing, {'available': True, 'value': None, 'error': None})
            self.assertEqual(descriptions.call_count, 1)
            self.assertEqual(len(missing_queries), 1)
            first['evidence']['databaseBusinessPurpose']['value'] = 'DEVELOPMENT_VALIDATION'
            first['formalManufacturingEligible'] = False
            clean, copied = self.readonly(lambda: self.read(cache))
            self.assertEqual(clean, expected)
            self.assertEqual(copied, [])

        # Mutating current source/order objects changes qualification even
        # though the persisted scalar remains the same cached raw fact.
        self.source.sales_order.delivery_information = {'businessPurpose': 'DEVELOPMENT_VALIDATION'}
        conflict, _ = self.readonly(lambda: self.read(cache))
        uncached_conflict, _ = self.readonly(self.read)
        self.assertEqual(conflict, uncached_conflict)
        self.assertEqual(conflict['decisionCode'], 'BUSINESS_PURPOSE_EVIDENCE_CONFLICT')
        self.assertFalse(conflict['formalManufacturingEligible'])
        self.source.sales_order = SalesOrder(pk=None, company_id=self.user.company_id,
            order_no='SIMULATED_FOR_TEST changed unsaved source relation', acceptance_marker='',
            contract_reference='', delivery_information={})
        changed, _ = self.readonly(lambda: self.read(cache))
        self.assertIsNone(changed['orderId'])
        self.assertEqual(changed['orderNo'], self.source.sales_order.order_no)
        self.assertEqual(changed['decisionCode'], 'BUSINESS_PURPOSE_EVIDENCE_MISSING')
        self.assertFalse(changed['formalManufacturingEligible'])

    def test_foreign_actor_expired_and_plain_caches_never_reuse_and_epoch_reloads_persisted_value(self):
        expected, _ = self.readonly(self.read)

        def unshared(cache):
            before = dict(cache)
            for _ in range(2):
                actual, queries = self.readonly(lambda: self.read(cache))
                self.assertEqual(actual, expected)
                self.assertTrue(queries)
            self.assertEqual(dict(cache), before)

        unshared({'SIMULATED_WRITE_CACHE': True})
        unshared(native._ReadOnlyProofCache(User(pk=self.user.pk,
            company_id=self.user.company_id + 10000)))
        actor_changed = native._ReadOnlyProofCache(self.user)
        native._bind_current_actor(actor_changed, User(pk=self.user.pk + 10000,
            company_id=self.user.company_id))
        unshared(actor_changed)
        with transaction.atomic():
            expired = native._ReadOnlyProofCache(self.user)
            self.readonly(lambda: self.read(expired))
        unshared(expired)

        cache = native._ReadOnlyProofCache(self.user)
        first, _ = self.readonly(lambda: self.read(cache))
        first_keys = set(self.purpose_keys(cache))
        self.assertTrue(first_keys)
        cache['SIMULATED_DEPENDENT_APPROVAL'] = True
        epoch = connection.connection.total_changes
        # Explicit isolated fixture change, not a production write or a fake
        # approval: the native raw column must be queried again after DML.
        legal.PlanLegalExtensionAdmissionTests.raw(self, self.order, 'business_purpose', 'DEVELOPMENT_VALIDATION')
        self.assertGreater(connection.connection.total_changes, epoch)
        changed, queries = self.readonly(lambda: self.read(cache))
        self.assertTrue(queries)
        self.assertEqual(changed['evidence']['databaseBusinessPurpose']['value'], 'DEVELOPMENT_VALIDATION')
        self.assertEqual(changed['decisionCode'], 'BUSINESS_PURPOSE_EVIDENCE_CONFLICT')
        self.assertFalse(changed['formalManufacturingEligible'])
        self.assertNotIn('SIMULATED_DEPENDENT_APPROVAL', cache)
        self.assertTrue(first_keys.isdisjoint(self.purpose_keys(cache)))
        self.assertEqual(first['evidence']['databaseBusinessPurpose']['value'], 'FORMAL_SALE')

    def test_database_error_never_enters_raw_or_metadata_cache_and_native_retry_is_not_suppressed(self):
        cache = native._ReadOnlyProofCache(self.user)
        # A negative adapter fault only; every successful result below is a
        # real introspection/SELECT against the disposable runner database.
        with patch.object(connection.introspection, 'get_table_description',
                side_effect=DatabaseError('SIMULATED_FOR_TEST introspection unavailable')):
            failed, _ = self.readonly(lambda: service._database_purpose(self.order, read_cache=cache))
        self.assertEqual(failed, {'available': None, 'value': None, 'error': 'DatabaseError'})
        self.assertEqual(self.purpose_keys(cache), [])
        recovered, queries = self.readonly(lambda: service._database_purpose(self.order, read_cache=cache))
        self.assertTrue(queries)
        self.assertEqual(recovered, {'available': True, 'value': 'FORMAL_SALE', 'error': None})
        repeated, hit_queries = self.readonly(lambda: service._database_purpose(self.order, read_cache=cache))
        self.assertEqual(repeated, recovered)
        self.assertEqual(hit_queries, [])
