"""Existing OEI choices remain authoritative during read-only fact handoff."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from . import formal_engineering_continuation_service as service
from .engineering_calculation_service import EngineeringCalculationError


class ExistingInstanceFactHandoffTests(SimpleTestCase):
    def setUp(self):
        self.item = SimpleNamespace(pk=8, sales_order=SimpleNamespace(company_id=1))
        self.design = SimpleNamespace(
            source_record_id=14, product_category_id=1, existing_design_data={},
            design_revisions=SimpleNamespace(all=lambda: []),
        )
        self.instance = SimpleNamespace(
            pk=7, company_id=1, sales_order_item_id=8,
            source_record_id=14, product_category_id=1, selected_process_type_id=12,
            source_record=SimpleNamespace(company_id=1),
            product_category=SimpleNamespace(company_id=1),
            selected_process_type=SimpleNamespace(company_id=1),
        )
        manager = self.enterContext(patch.object(service.ProductDesignItem, 'objects'))
        self.rows = manager.select_related.return_value.prefetch_related.return_value.filter.return_value.order_by
        self.rows.return_value = [self.design]
        self.process_lookup = self.enterContext(patch.object(service.ManufacturingProcessType.objects, 'filter'))

    def assert_error(self, code, instance=None):
        with self.assertRaises(EngineeringCalculationError) as caught:
            service._resolve_instance_identity(self.item, instance=instance)
        self.assertEqual(caught.exception.code, code)

    def test_complete_instance_is_readable_without_optional_design_process(self):
        result = service._resolve_instance_identity(self.item, instance=self.instance)
        self.assertEqual(
            (result['sourceRecordId'], result['productCategoryId'], result['selectedProcessTypeId']),
            (14, 1, 12),
        )
        self.process_lookup.assert_not_called()

    def test_optional_raw_or_revision_process_cannot_replace_saved_selection(self):
        for raw, revision in (({'routingProcessCode': 'OTHER'}, []), ({}, [SimpleNamespace(revision=1, material_process_type_id=99)])):
            with self.subTest(raw=raw, revision=bool(revision)):
                self.design.existing_design_data = raw
                self.design.design_revisions = SimpleNamespace(all=lambda: revision)
                result = service._resolve_instance_identity(self.item, instance=self.instance)
                self.assertEqual(result['selectedProcessTypeId'], 12)
        self.process_lookup.assert_not_called()

    def test_saved_identity_or_related_company_conflicts_are_rejected(self):
        for field, value in (
            ('company_id', 2), ('sales_order_item_id', 9),
            ('source_record_id', 13), ('product_category_id', 2),
        ):
            with self.subTest(field=field):
                original = getattr(self.instance, field)
                setattr(self.instance, field, value)
                self.assert_error('INSTANCE_IDENTITY_MISMATCH', self.instance)
                setattr(self.instance, field, original)
        for field in ('source_record', 'product_category', 'selected_process_type'):
            with self.subTest(relation=field):
                related = getattr(self.instance, field)
                related.company_id = 2
                self.assert_error('INSTANCE_IDENTITY_MISMATCH', self.instance)
                related.company_id = 1
        self.process_lookup.assert_not_called()

    def test_ambiguous_source_or_category_is_not_hidden_by_existing_instance(self):
        for field in ('source_record_id', 'product_category_id'):
            with self.subTest(field=field):
                other = SimpleNamespace(**vars(self.design))
                setattr(other, field, 2)
                self.rows.return_value = [self.design, other]
                self.assert_error('INSTANCE_IDENTITY_NOT_UNIQUE', self.instance)

    def test_missing_design_scope_is_not_filled_from_instance(self):
        self.rows.return_value = []
        self.assert_error('DESIGN_OBJECT_SCOPE_EMPTY', self.instance)

    def test_new_intake_does_not_borrow_an_existing_instance_implicitly(self):
        self.assert_error('INSTANCE_PROCESS_NOT_UNIQUE')
        self.process_lookup.assert_not_called()

    def test_incomplete_legacy_instance_keeps_existing_process_derivation(self):
        self.instance.selected_process_type_id = None
        self.design.existing_design_data = {'routingProcessCode': 'LEGACY/旧配置'}
        self.process_lookup.return_value.first.return_value = SimpleNamespace(pk=19)
        result = service._resolve_instance_identity(self.item, instance=self.instance)
        self.assertEqual(result['selectedProcessTypeId'], 19)
        self.process_lookup.assert_called_once_with(company_id=1, code='LEGACY')

    def test_incomplete_legacy_instance_still_rejects_unknown_process(self):
        self.instance.selected_process_type_id = None
        self.assert_error('INSTANCE_PROCESS_NOT_UNIQUE', self.instance)

