"""SIMULATED_FOR_TEST: native saved material/BOM checks with raw FK preloads.

The borrowed small fixture explicitly supplies its established upstream source
facts and two document stubs. No material/BOM validator is replaced with success.
This module is restricted to the reviewed named disposable database runner.
"""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from . import operation_requirement_service as native
from . import manufacturing_output_generation_service as outputs
from . import tests_engineering_version_handoff_upstream as saved_fixture
from . import tests_plan_legal_extension_admission as legal_fixture
from . import tests_publication_raw_read_cache as raw_fixture  # includes isolated runner guard
from .models import BOMItem, BOMItemSourceRequirement, EngineeringMaterialRequirement, EngineeringRuleDefinition


class SavedOutputRawPreloadTests(raw_fixture.ReadOnlyAssertions, TestCase):
    def readonly(self, action):
        before = raw_fixture.classified_fixture.ClassifiedFactEorTests.full_database_snapshot(self)
        epoch = connection.connection.total_changes
        try:
            with CaptureQueriesContext(connection) as queries:
                value = action()
        finally:
            self.assertEqual(before,
                raw_fixture.classified_fixture.ClassifiedFactEorTests.full_database_snapshot(self))
            self.assertEqual(connection.connection.total_changes, epoch)
            self.assertFalse(any(row['sql'].lstrip().split()[0].upper() in {
                'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'
            } for row in queries), list(queries))
        return value, list(queries)

    def setUp(self):
        self.enterContext(override_settings(
            PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=saved_fixture.SCOPE))
        self.case = saved_fixture.EngineeringVersionHandoffUpstreamTests(methodName='runTest')
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.output, _ = self.case._generate()
        self.user = self.case.executor
        self.requirement = EngineeringMaterialRequirement.objects.select_related(
            'source_detail__rule', 'calculation__sales_order_item', 'material', 'uom',
        ).get(calculation_id=self.output.engineering_calculation_id)

    def test_fk_preload_matches_real_lazy_path_and_keeps_all_native_full_clean_calls(self):
        original_select = QuerySet.select_related
        item_paths = ('bom_version__bom', 'bom_version__product', 'parent_item', 'material', 'uom')
        link_paths = ('material_requirement__source_detail',
            'material_requirement__calculation__sales_order_item',
            'material_requirement__material', 'material_requirement__uom')

        def lazy_path(queryset, *fields):
            if ((queryset.model is BOMItem and fields == item_paths)
                    or (queryset.model is BOMItemSourceRequirement and fields == link_paths)):
                return original_select(queryset, None)
            return original_select(queryset, *fields)

        with patch.object(QuerySet, 'select_related', lazy_path):
            expected, lazy_queries = self.readonly(lambda: outputs._saved_output_content_integrity(self.output))
        full_clean_counts = {BOMItem: 0, BOMItemSourceRequirement: 0, EngineeringMaterialRequirement: 0}

        def checked(model):
            original = model.full_clean
            def validate(row, *args, **kwargs):
                full_clean_counts[model] += 1
                self.assertEqual(row.get_deferred_fields(), set())
                if model is BOMItem:
                    self.assertTrue({'bom_version', 'material', 'uom'} <= row._state.fields_cache.keys())
                    self.assertIn('bom', row.bom_version._state.fields_cache)
                elif model is EngineeringMaterialRequirement:
                    self.assertTrue({'calculation', 'source_detail', 'material', 'uom'}
                        <= row._state.fields_cache.keys())
                    self.assertIn('sales_order_item', row.calculation._state.fields_cache)
                    self.assertIn('rule', row.source_detail._state.fields_cache)
                else:
                    self.assertIn('bom_item', row._state.fields_cache)
                    self.assertIn('bom_version', row.bom_item._state.fields_cache)
                return original(row, *args, **kwargs)
            return validate

        with patch.object(BOMItem, 'full_clean', checked(BOMItem)), \
                patch.object(BOMItemSourceRequirement, 'full_clean', checked(BOMItemSourceRequirement)), \
                patch.object(EngineeringMaterialRequirement, 'full_clean', checked(EngineeringMaterialRequirement)):
            actual, eager_queries = self.readonly(lambda: outputs._saved_output_content_integrity(self.output))
        self.assertIsNone(expected)
        self.assertEqual(actual, expected)
        self.assertLess(len(eager_queries), len(lazy_queries))
        self.assertEqual(full_clean_counts[BOMItem], self.output.bom_version.items.count())
        expected_links = BOMItemSourceRequirement.objects.filter(bom_item__bom_version=self.output.bom_version).count()
        self.assertEqual(full_clean_counts[BOMItemSourceRequirement], expected_links)
        self.assertEqual(full_clean_counts[EngineeringMaterialRequirement], expected_links)
        self.assertGreaterEqual(expected_links, 1)

    def test_mapping_actor_raw_reuse_preserves_every_material_check_and_rejects_changed_mapping(self):
        expected, old_queries = self.readonly(lambda: outputs._saved_requirement_integrity(self.requirement))
        self.assertIsNone(expected)
        with transaction.atomic():
            cache = native._ReadOnlyProofCache(self.user)
            first, initial = self.readonly(lambda: outputs._saved_requirement_integrity(
                self.requirement, read_cache=cache))
            repeated, repeated_queries = self.readonly(lambda: outputs._saved_requirement_integrity(
                self.requirement, read_cache=cache))
            self.assertEqual(first, expected)
            self.assertEqual(repeated, expected)
            self.assertEqual(len(old_queries), len(initial))
            self.assertEqual(len(initial) - len(repeated_queries), 2)
            self.assertTrue(repeated_queries)  # request/audit and each input Fact still checked
            mapping = self.cached_models(cache, EngineeringRuleDefinition)[0]
            cache['dependent-proof'] = True
            mapping.specification['outputs'][0]['materialId'] = -1
            restored, _ = self.readonly(lambda: outputs._saved_requirement_integrity(
                self.requirement, read_cache=cache))
            self.assertEqual(restored, expected)
            self.assertNotIn('dependent-proof', cache)
            mapping = self.cached_models(cache, EngineeringRuleDefinition)[0]
            bad_spec = deepcopy(mapping.specification)
            bad_spec['outputs'][0]['materialId'] = -1
            legal_fixture.PlanLegalExtensionAdmissionTests.raw(self, mapping, 'specification', bad_spec)
            with self.assertRaises(ValidationError):
                self.readonly(lambda: outputs._saved_requirement_integrity(self.requirement, read_cache=cache))
            with self.assertRaises(ValidationError):
                self.readonly(lambda: outputs._saved_requirement_integrity(self.requirement))
