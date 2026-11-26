"""Boundary contracts; persistence and rollback use separately pinned copies."""
from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from django.test import override_settings

from . import saved_fact_material_requirement_service as kernel
from . import system_test_material_handoff as controlled


class SystemTestMaterialHandoffContractTests(TestCase):
    def test_v1_limit_is_not_expanded_by_predecessor_declarations(self):
        record = SimpleNamespace(material_requirements=SimpleNamespace(
            values_list=lambda *args, **kwargs: [10, 11]))
        with self.assertRaises(kernel.SavedFactMaterialRequirementError) as caught:
            controlled._validate_requirement_limits(
                {"scope": controlled.SCOPE, "preservedRequirements": [{"requirementId": 10}]},
                record, None, None,
            )
        self.assertEqual(caught.exception.code, "SYSTEM_TEST_HANDOFF_REQUIREMENT_LIMIT")

    def test_continuation_requires_actual_predecessor_declarations(self):
        record = SimpleNamespace(material_requirements=SimpleNamespace(
            values_list=lambda *args, **kwargs: []))
        with self.assertRaises(kernel.SavedFactMaterialRequirementError) as caught:
            controlled._validate_requirement_limits(
                {"scope": controlled.CONTINUATION_SCOPE}, record, None, None,
            )
        self.assertEqual(caught.exception.code, "SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID")

    def test_continuation_predecessor_ids_cannot_be_duplicated(self):
        record = SimpleNamespace(material_requirements=SimpleNamespace(
            values_list=lambda *args, **kwargs: [10]))
        with self.assertRaises(kernel.SavedFactMaterialRequirementError) as caught:
            controlled._validate_requirement_limits(
                {"scope": controlled.CONTINUATION_SCOPE,
                 "preservedRequirements": [{"requirementId": 10}, {"requirementId": 10}]},
                record, None, None,
            )
        self.assertEqual(caught.exception.code, "SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID")

    def test_ordinary_apply_does_not_forward_development_context(self):
        with patch.object(kernel, "_apply_saved_fact_material_requirement", return_value="formal") as call:
            self.assertEqual(kernel.apply_saved_fact_material_requirement(user="actor", contract="contract"), "formal")
            call.assert_called_once_with(user="actor", contract="contract")

    def test_public_ordinary_entry_has_no_frontend_context_switch(self):
        for method in (kernel.apply_saved_fact_material_requirement,
                       kernel.preview_saved_fact_material_requirement,
                       kernel.readback_saved_fact_material_requirement):
            with self.assertRaises(TypeError):
                method(user=None, contract=None, _development_context=True)

    @override_settings(PCE_SYSTEM_TEST_MATERIAL_HANDOFF=None)
    def test_controlled_entry_requires_server_activation(self):
        for method in (controlled.preview, controlled.apply, controlled.readback):
            with self.assertRaises(kernel.SavedFactMaterialRequirementError) as caught:
                method(user=None, contract=None)
            self.assertEqual(caught.exception.code, "SYSTEM_TEST_HANDOFF_NOT_ACTIVATED")

    def test_unvalidated_context_is_rejected(self):
        with self.assertRaises(kernel.SavedFactMaterialRequirementError) as caught:
            controlled.verify_admission(object(), user=None, contract=None)
        self.assertEqual(caught.exception.code, "SYSTEM_TEST_HANDOFF_CONTEXT_INVALID")

    def test_controlled_path_reuses_the_same_atomic_save_kernel(self):
        admission = object()
        with (patch.object(controlled, "_validate", return_value=admission) as validate,
              patch.object(kernel, "_apply_saved_fact_material_requirement", return_value="saved") as save):
            self.assertEqual(controlled.apply(user="actor", contract="contract"), "saved")
            validate.assert_called_once_with(user="actor", contract="contract", operation="apply")
            save.assert_called_once_with(user="actor", contract="contract", _development_context=admission)
