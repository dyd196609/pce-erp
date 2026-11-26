"""The maintenance preview shares server normalization and never saves."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .views import ProductionFoundationA1View
from .source_format_mapping_service import SourceFormatMappingError


class SourceFormatPreviewTests(SimpleTestCase):
    def preview(self, payload):
        request = APIRequestFactory().post('/api/pde/a1-foundation/engineering-source-records/',
            {'action': 'sourceFormatPreview', 'sourcePayload': payload}, format='json')
        force_authenticate(request, user=SimpleNamespace(company_id=7, is_authenticated=True))
        return ProductionFoundationA1View.as_view()(request, entity='engineering-source-records')

    @patch('pde.source_format_mapping_service.normalize_source_payload')
    @patch('pde.views.ProductionFoundationService.maintenance_authorization')
    def test_preview_returns_the_formal_server_result_without_database_access(self, auth, normalize):
        auth.return_value = {'allowed': True}
        normalize.return_value = {'normalization': {'selectedRow': 0},
            'canonicalInputs': {'amount': {'value': '0'}}}
        payload = {'sourceFormatReference': {'ruleId': 12}, 'rawContent': 'amount\n0'}
        result = self.preview(payload)
        self.assertEqual(result.status_code, 200)
        normalize.assert_called_once_with(payload, company_id=7)
        self.assertEqual(result.data['canonicalInputs'], normalize.return_value['canonicalInputs'])
        self.assertEqual((result.data['businessWriteCount'], result.data['auditWriteCount']), (0, 0))

    @patch('pde.source_format_mapping_service.normalize_source_payload')
    @patch('pde.views.ProductionFoundationService.maintenance_authorization')
    def test_formal_maintenance_chain_is_required_before_normalization(self, auth, normalize):
        auth.return_value = {'allowed': False, 'decisionCode': 'FORMAL_EXECUTION_CHAIN_REQUIRED',
            'reason': '正式维护身份未完成'}
        result = self.preview({})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.data['code'], 'FORMAL_EXECUTION_CHAIN_REQUIRED')
        normalize.assert_not_called()

    @patch('pde.source_format_mapping_service.normalize_source_payload')
    @patch('pde.views.ProductionFoundationService.maintenance_authorization')
    def test_native_mapping_rejection_is_preserved(self, auth, normalize):
        auth.return_value = {'allowed': True}
        normalize.side_effect = SourceFormatMappingError('SOURCE_FORMAT_REFERENCE_REQUIRED', '缺少引用')
        result = self.preview({'sourceFormatReference': {'ruleId': 12}})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.data['code'], 'SOURCE_FORMAT_REFERENCE_REQUIRED')

    @patch('pde.source_format_mapping_service.normalize_source_payload')
    @patch('pde.views.ProductionFoundationService.maintenance_authorization')
    def test_legacy_payload_cannot_be_reported_as_a_successful_mapping_preview(self, auth, normalize):
        auth.return_value = {'allowed': True}
        result = self.preview({'canonicalInputs': {'amount': {'value': '1'}}})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.data['code'], 'SOURCE_FORMAT_REFERENCE_REQUIRED')
        normalize.assert_not_called()
