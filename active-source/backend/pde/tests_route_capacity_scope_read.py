"""SIMULATED_FOR_TEST: exact route-key narrowing preserves raw bad candidates.

Borrow construction only from the guarded native route fixture. No original
database is a target, no successful authorization/proof is mocked, and no
schema/validator is disabled. Deliberate legacy faults use the existing fixture
raw helper outside guarded reads; the raw reader must retain them for native
qualification rather than silently filtering them into success.
"""
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from system.models import User
from . import daily_capacity_service as capacity
from . import operation_requirement_service as native
from . import tests_plan_legal_extension_admission as legal
from . import tests_route_workload_final_read as fixtures
from .models import CapacityProductType, ManufacturingProcessType, ProductCategory, StandardCapacity


class RouteCapacityScopeReadTests(TestCase):
    def setUp(self):
        # Only reuse fixture construction, never inherit/discover its tests.
        self.case = fixtures.RouteWorkloadFinalNativeTests(methodName='runTest')
        self.case.setUp()
        self.f, self.user = self.case.f, self.case.f.user
        self.operation_ids = [self.f.op_area.pk]
        self.kind = self.f.product_type
        self.key = self.route_key(self.kind)

    @staticmethod
    def route_key(kind):
        return (kind.code, kind.product_category_id, kind.manufacturing_process_type_id)

    @staticmethod
    def concrete(rows):
        return [(row.pk, {field.attname: getattr(row, field.attname)
                         for field in row._meta.concrete_fields}) for row in rows]

    def readonly(self, callback):
        before = self.f.full_database_snapshot()
        epoch = connection.connection.total_changes

        def no_write(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if verb not in {'SELECT', 'PRAGMA', 'BEGIN', 'COMMIT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK'}:
                raise AssertionError('Route raw capacity read attempted a write')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(no_write), CaptureQueriesContext(connection) as queries:
            try:
                return callback(), list(queries)
            finally:
                self.assertEqual(connection.connection.total_changes, epoch)
                self.assertEqual(self.f.full_database_snapshot(), before)

    def raw(self, cache, keys):
        return capacity._no_date_raw_read(user=self.user, operation_ids=self.operation_ids,
            read_cache=cache, routing_keys=keys)

    def make_capacity(self, code, *, kind=None, uom=None):
        # New, schema-valid disposable fixture rows; native qualification is
        # deliberately not substituted for by this construction helper.
        row = StandardCapacity(company=self.f.company, code=code,
            name='SIMULATED_FOR_TEST route raw scope', resource_scope='work_center',
            work_center=self.f.center, operation=self.f.op_area,
            product_type=kind or self.kind, measurement_status='measured', quantity=500,
            uom=uom or self.f.area, time_basis='day', time_basis_quantity=1,
            time_unit='DAY', is_active=True)
        row.full_clean()
        row.save()
        return row

    def test_exact_key_union_none_empty_keep_inactive_duplicate_bad_and_wrong_unit_rows(self):
        category = ProductCategory.objects.create(company=self.f.company,
            code='SIM-RAW-CAT-NEAR', name=self.f.category.name)
        process = ManufacturingProcessType.objects.create(company=self.f.company,
            code='SIM-RAW-PROC-NEAR', name='SIMULATED_FOR_TEST distinct raw process')
        near = CapacityProductType(company=self.f.company, code='SIM-RAW-TYPE-NEAR',
            name=self.kind.name, product_category=category,
            manufacturing_process_type=process, is_active=False)
        near.full_clean()
        near.save()
        outside = CapacityProductType(company=self.f.company, code='SIM-RAW-TYPE-OTHER',
            name=self.kind.name, product_category=self.f.category,
            manufacturing_process_type=self.f.kind)
        outside.full_clean()
        outside.save()
        # Same-company duplicate codes cannot exist under the real schema;
        # use distinct valid codes instead of inventing an impossible fixture.
        unique = next(rule for rule in CapacityProductType._meta.constraints
            if rule.name == 'pde_capacity_product_type_company_code_unique')
        self.assertEqual(tuple(unique.fields), ('company', 'code'))
        near_capacity = self.make_capacity('SIM-RAW-CAP-NEAR', kind=near)
        outside_capacity = self.make_capacity('SIM-RAW-CAP-OTHER', kind=outside)
        duplicate = self.make_capacity('SIM-RAW-CAP-DUPLICATE')
        wrong_unit = self.make_capacity('SIM-RAW-CAP-WRONG-UOM', uom=self.f.pcs)
        bad = self.make_capacity('SIM-RAW-CAP-BAD-LEGACY')
        # Explicit isolated fault: equipment scope without equipment violates
        # the existing Model.clean contract but not a DB constraint. It must
        # remain in this raw set for the unchanged native consumer to reject.
        legal.PlanLegalExtensionAdmissionTests.raw(self, bad, 'resource_scope', 'equipment')
        bad.refresh_from_db()
        with self.assertRaises(ValidationError):
            bad.full_clean()

        expected_types = list(CapacityProductType.objects.filter(company=self.f.company))
        expected_capacities = list(StandardCapacity.objects.filter(company=self.f.company,
            operation_id__in=self.operation_ids, time_basis='day', time_basis_quantity=1))
        cache = native._ReadOnlyProofCache(self.user)
        full, _ = self.readonly(lambda: self.raw(cache, None))
        self.assertEqual(self.concrete(full['types']), self.concrete(expected_types))
        self.assertEqual(self.concrete(full['capacities']), self.concrete(expected_capacities))
        empty, _ = self.readonly(lambda: self.raw(cache, []))
        self.assertEqual(empty['types'], [])
        self.assertEqual(empty['capacities'], [])
        self.assertEqual([row.pk for row in empty['capabilities']],
            [row.pk for row in full['capabilities']])

        scoped, _ = self.readonly(lambda: self.raw(cache, [self.key, self.route_key(near), self.key]))
        expected_type_ids = {self.kind.pk, near.pk}
        self.assertEqual({row.pk for row in scoped['types']}, expected_type_ids)
        self.assertFalse(next(row for row in scoped['types'] if row.pk == near.pk).is_active)
        self.assertEqual(self.concrete(scoped['capacities']),
            self.concrete([row for row in expected_capacities if row.product_type_id in expected_type_ids]))
        ids = {row.pk for row in scoped['capacities']}
        self.assertTrue({self.f.capacity.pk, near_capacity.pk, duplicate.pk, wrong_unit.pk, bad.pk} <= ids)
        self.assertNotIn(outside_capacity.pk, ids)
        kept = {row.pk: row for row in scoped['capacities']}
        self.assertEqual(kept[wrong_unit.pk].uom_id, self.f.pcs.pk)
        self.assertEqual(kept[bad.pk].resource_scope, 'equipment')
        self.assertEqual(kept[duplicate.pk].product_type_id, self.kind.pk)
        for wrong_key in ((self.kind.code, category.pk, self.kind.manufacturing_process_type_id),
                          (self.kind.code, self.kind.product_category_id, process.pk)):
            with self.subTest(wrong_exact_triple=wrong_key):
                rejected, _ = self.readonly(lambda: self.raw(cache, [wrong_key]))
                self.assertEqual(rejected['types'], [])
                self.assertEqual(rejected['capacities'], [])

    def test_raw_scope_requires_actual_typed_actor_and_invalidates_on_write_epoch(self):
        def denied(cache):
            with self.assertRaises(capacity.DailyCapacityError) as caught:
                self.readonly(lambda: self.raw(cache, [self.key]))
            self.assertEqual(caught.exception.code, 'READ_CONTEXT_REQUIRED')

        denied({})
        denied(native._ReadOnlyProofCache(User(pk=self.user.pk,
            company_id=self.user.company_id + 10000)))
        denied(native._ReadOnlyProofCache(User(pk=self.user.pk + 10000,
            company_id=self.user.company_id)))
        actor_changed = native._ReadOnlyProofCache(self.user)
        native._bind_current_actor(actor_changed, User(pk=self.user.pk + 10000,
            company_id=self.user.company_id))
        denied(actor_changed)
        with transaction.atomic():
            expired = native._ReadOnlyProofCache(self.user)
            self.readonly(lambda: self.raw(expired, [self.key]))
        denied(expired)

        cache = native._ReadOnlyProofCache(self.user)
        first, _ = self.readonly(lambda: self.raw(cache, [self.key]))
        original = next(row for row in first['capacities'] if row.pk == self.f.capacity.pk)
        cache['SIMULATED_DEPENDENT_APPROVAL'] = True
        cache.allocation_validation_cache['SIMULATED'] = True
        cache.budget_proofs['SIMULATED'] = True
        before_epoch = connection.connection.total_changes
        # Explicit isolated fixture DML between read guards: a same-connection
        # write must invalidate every dependent proof, even when still a raw
        # candidate. Inactive records must not disappear before qualification.
        legal.PlanLegalExtensionAdmissionTests.raw(self, self.f.capacity, 'is_active', False)
        self.assertGreater(connection.connection.total_changes, before_epoch)
        second, _ = self.readonly(lambda: self.raw(cache, [self.key]))
        changed = next(row for row in second['capacities'] if row.pk == self.f.capacity.pk)
        self.assertIsNot(changed, original)
        self.assertFalse(changed.is_active)
        self.assertNotIn('SIMULATED_DEPENDENT_APPROVAL', cache)
        self.assertFalse(cache.allocation_validation_cache)
        self.assertFalse(cache.budget_proofs)
