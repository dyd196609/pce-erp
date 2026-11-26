"""DB-free pollution checks for call-owned capacity raw-value guards."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from .daily_capacity_service import (
    _capacity_guard_bytes, _capacity_guard_matches, _capacity_guard_snapshot,
)


class _Row:
    def __init__(self, label, **values):
        self._meta = SimpleNamespace(label_lower=label,
            concrete_fields=[SimpleNamespace(attname=name) for name in values])
        for name, value in values.items():
            setattr(self, name, value)


class DailyCapacityRawGuardTests(SimpleTestCase):
    def setUp(self):
        self.capacity = _Row('pde.standardcapacity', id=9, company_id=1,
            work_center_id=2, quantity=Decimal('500.000'), effective_from=date(2026, 10, 1),
            conditions={'manifest': {'steps': [1, 2], 'days': 0.1}}, is_active=True)
        self.center = _Row('pde.workcenter', id=2, company_id=1,
            resource_capabilities={'scope': ['length']}, is_active=True)

    def groups(self):
        return [(self.capacity, self.center, None)]

    def legacy(self):
        return tuple(tuple(None if row is None else (row._meta.label_lower,
            tuple((field.attname, getattr(row, field.attname)) for field in row._meta.concrete_fields))
            for row in group) for group in self.groups())

    def snapshot(self):
        return _capacity_guard_snapshot(self.groups(), self.legacy)

    def matches(self, snapshot):
        return _capacity_guard_matches(snapshot, self.groups(), self.legacy)

    def test_complete_unchanged_values_match(self):
        saved = self.snapshot()
        self.assertIsInstance(saved.get('bytes'), bytes)
        self.assertTrue(self.matches(saved))
        self.assertEqual(saved['bytes'], _capacity_guard_bytes(self.groups()))

    def test_extra_aliases_to_unchanged_json_do_not_invalidate_the_read(self):
        saved = self.snapshot()
        manifest_alias = self.capacity.conditions['manifest']
        self.assertTrue(self.matches(saved))
        list_alias = manifest_alias['steps']
        self.assertTrue(self.matches(saved))
        aliases = [manifest_alias, list_alias, self.center.resource_capabilities]
        self.assertTrue(self.matches(saved))
        self.assertEqual(aliases[1], [1, 2])

    def test_equal_numeric_values_keep_exact_outer_types(self):
        for old, changed in ((1, True), (True, 1), (1, 1.0), (1.0, True)):
            with self.subTest(oldType=type(old), changedType=type(changed)):
                self.capacity.quantity = old
                saved = self.snapshot()
                self.capacity.quantity = changed
                self.assertFalse(self.matches(saved))

    def test_nested_json_equal_numeric_type_change_is_pollution(self):
        for changed in (True, 1.0):
            with self.subTest(changedType=type(changed)):
                self.capacity.conditions = {'manifest': {'steps': [1, 2]}}
                saved = self.snapshot()
                self.capacity.conditions['manifest']['steps'][0] = changed
                self.assertFalse(self.matches(saved))

    def test_nested_json_mutation_cannot_change_its_saved_guard(self):
        saved = self.snapshot()
        before = saved['bytes']
        self.capacity.conditions['manifest']['steps'].append(3)
        self.assertFalse(self.matches(saved))
        self.assertEqual(saved['bytes'], before)

    def test_related_model_json_and_identity_are_guarded(self):
        for field, value in (('id', 7), ('company_id', 3), ('is_active', False),
                ('resource_capabilities', {'scope': ['area']})):
            with self.subTest(field=field):
                original = getattr(self.center, field)
                saved = self.snapshot()
                setattr(self.center, field, value)
                self.assertFalse(self.matches(saved))
                setattr(self.center, field, original)

    def test_date_datetime_decimal_types_remain_distinct(self):
        saved = self.snapshot()
        self.capacity.effective_from = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.assertFalse(self.matches(saved))
        self.capacity.effective_from = date(2026, 10, 1)
        self.capacity.quantity = 500.0
        self.assertFalse(self.matches(saved))

    def test_unknown_value_uses_independent_legacy_snapshot(self):
        self.capacity.conditions = {'unsupported': {'length'}}
        self.assertIsNone(_capacity_guard_bytes(self.groups()))
        saved = self.snapshot()
        self.assertIn('legacy', saved)
        self.assertTrue(self.matches(saved))
        self.capacity.conditions['unsupported'].add('area')
        self.assertFalse(self.matches(saved))

    def test_nonfinite_float_keeps_native_strict_semantics(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=str(value)):
                self.capacity.conditions = {'nested': [value]}
                self.assertIsNone(_capacity_guard_bytes(self.groups()))
                saved = self.snapshot()
                self.assertIn('legacy', saved)
                # NaN is never equal even to itself; infinity remains equal.
                self.assertEqual(self.matches(saved), value == value)

    def test_supported_guard_becoming_unsupported_does_not_reuse(self):
        saved = self.snapshot()
        self.capacity.conditions['manifest']['steps'] = {1, 2}
        self.assertFalse(self.matches(saved))
