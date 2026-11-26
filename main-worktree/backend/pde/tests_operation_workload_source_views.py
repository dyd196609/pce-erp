"""SIMULATED_FOR_TEST: existing-route integration, no formal database access."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from .views import ProductionFoundationA1View
from .production_foundation_service import ProductionFoundationError


class OperationWorkloadSourceRouteTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(pk=17, company_id=9, is_authenticated=True, is_active=True)
        self.rows = [{'id': 71, 'name': '测试工序', 'workloadSource': {'statusLabel': '已配置正式来源'}}]
        self.catalog = {'productionPlans': [{'id': 81, 'label': '测试计划', 'routingSteps': [
            {'id': 91, 'operationId': 71, 'label': '测试步骤'},
        ]}]}

    def get(self, **params):
        request = self.factory.get('/api/pde/a1-foundation/operations/', {'action': 'operationWorkloadSources', **params})
        force_authenticate(request, user=self.user)
        return ProductionFoundationA1View.as_view()(request, entity='operations')

    def context(self, *, catalog=None):
        return patch.multiple('pde.operation_workload_source_service',
            catalog=Mock(return_value=catalog or self.catalog),
            read_for_plan=Mock(return_value={
                'sourceCandidates': {'quantity': '2.500000'}, 'savedAllocations': {'quantity': None},
            }))

    def test_get_queries_only_unique_formal_step_and_keeps_saved_unknown(self):
        with patch('pde.views.ProductionFoundationService.list', return_value=self.rows), self.context():
            with patch('pde.operation_workload_source_service.read_for_plan', return_value={
                'sourceCandidates': {'quantity': '2.500000'}, 'savedAllocations': {'quantity': None},
            }) as read:
                response = self.get(operationId=71, productionPlanId=81)
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(user=self.user, production_plan_id=81, routing_step_id=91)
        self.assertIsNone(response.data['context']['savedAllocations']['quantity'])

    def test_repeated_operation_requires_explicit_step_instead_of_first(self):
        catalog = {'productionPlans': [{'id': 81, 'routingSteps': [
            {'id': 91, 'operationId': 71}, {'id': 92, 'operationId': 71},
        ]}]}
        with patch('pde.views.ProductionFoundationService.list', return_value=self.rows), self.context(catalog=catalog):
            response = self.get(operationId=71, productionPlanId=81)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['selectionBlocker']['statusCode'], 'STEP_SELECTION_REQUIRED')
        self.assertIsNone(response.data['context'])

    def test_cross_scope_plan_and_step_are_rejected(self):
        with patch('pde.views.ProductionFoundationService.list', return_value=self.rows), self.context():
            self.assertEqual(self.get(operationId=71, productionPlanId=999).status_code, 400)
            self.assertEqual(self.get(operationId=71, productionPlanId=81, routingStepId=999).status_code, 400)
            self.assertEqual(self.get(operationId=999).status_code, 400)

    def test_configure_is_explicit_and_delegates_native_save_without_generation(self):
        request = self.factory.post('/api/pde/a1-foundation/operations/', {
            'action': 'configureOperationWorkloadSource', 'operationId': 71,
            'reason': '测试正式配置', 'producerRuleId': 12, 'modeId': 4,
        }, format='json')
        force_authenticate(request, user=self.user)
        with patch('pde.operation_workload_source_service.configure', return_value={'rules': [{'id': 14}]}) as configure:
            response = ProductionFoundationA1View.as_view()(request, entity='operations')
        self.assertEqual(response.status_code, 200)
        configure.assert_called_once_with(user=self.user, operation_id=71,
            payload={'producerRuleId': 12, 'modeId': 4}, reason='测试正式配置')

    def test_native_employee_chain_denial_is_not_superuser_bypass(self):
        request = self.factory.post('/api/pde/a1-foundation/operations/', {
            'action': 'configureOperationWorkloadSource', 'operationId': 71, 'reason': '测试',
        }, format='json')
        force_authenticate(request, user=self.user)
        with patch('pde.operation_workload_source_service.configure', side_effect=ProductionFoundationError(
            'FORMAL_EXECUTION_CHAIN_REQUIRED', '需要原员工岗位职责链')):
            response = ProductionFoundationA1View.as_view()(request, entity='operations')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'FORMAL_EXECUTION_CHAIN_REQUIRED')

    def test_opt_in_route_overview_uses_one_plan_batch_and_keeps_old_action(self):
        overview = {'scope': {'companyId': 9, 'productionPlanId': 81}, 'rows': [],
            'summary': {'stepCount': 0}, 'businessWriteCount': 0}
        with (patch('pde.operation_workload_source_service.read_route_overview', return_value=overview) as read,
                patch('pde.operation_workload_source_service.catalog', side_effect=AssertionError('no repeated catalog')),
                patch('pde.operation_workload_source_service.read_for_plan', side_effect=AssertionError('no deep step reads')),
                patch('pde.views.ProductionFoundationService.list', side_effect=AssertionError('no repeated projection'))):
            response = self.get(routeOverview=1, productionPlanId=81)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['routeConfiguration'], overview)
        self.assertEqual(response.data['factSource'], 'server')
        read.assert_called_once_with(user=self.user, production_plan_id=81)
        self.assertNotIn('context', response.data)

    def test_route_overview_requires_plan_and_preserves_native_scope_errors(self):
        with patch('pde.operation_workload_source_service.read_route_overview') as read:
            response = self.get(routeOverview=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'PLAN_REQUIRED')
        read.assert_not_called()
        with patch('pde.operation_workload_source_service.read_route_overview', side_effect=ProductionFoundationError(
                'WORKLOAD_SOURCE_PLAN_MISSING', '计划不在当前公司')):
            response = self.get(routeOverview=1, productionPlanId=999)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'WORKLOAD_SOURCE_PLAN_MISSING')

    def preview(self, **data):
        request = self.factory.post('/api/pde/a1-foundation/operations/', {
            'action': 'previewOperationWorkloadSourceConfiguration', 'operationId': 71,
            'configuration': {'expression': 'source_quantity / 2'}, **data,
        }, format='json')
        force_authenticate(request, user=self.user)
        return ProductionFoundationA1View.as_view()(request, entity='operations')

    def test_preview_uses_same_url_read_service_and_cannot_save_or_generate(self):
        result = {'configurationPreview': {'statusLabel': '校验通过'}, 'businessWriteCount': 0}
        with (patch('pde.operation_workload_source_service.preview_configuration', return_value=result) as preview,
                patch('pde.operation_workload_source_service.configure', side_effect=AssertionError('no save')),
                patch('pde.views.ProductionFoundationService.write', side_effect=AssertionError('no fallback write'))):
            response = self.preview(productionPlanId=81, routingStepId=91)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, result)
        preview.assert_called_once_with(user=self.user, company_id=9, operation_id=71,
            payload={'expression': 'source_quantity / 2'}, plan_id=81, routing_step_id=91)

    def test_preview_preserves_permission_company_and_conflict_failures(self):
        for code, expected in [('PERMISSION_DENIED', 403), ('ORGANIZATION_MISMATCH', 403),
                ('WORKLOAD_SOURCE_CONFIGURATION_CONFLICT', 409), ('WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN', 409),
                ('WORKLOAD_SOURCE_UNIT_MISMATCH', 400)]:
            with self.subTest(code=code), patch('pde.operation_workload_source_service.preview_configuration',
                    side_effect=ProductionFoundationError(code, '原生明确原因')):
                response = self.preview(companyId=99)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.data['code'], code)

    def test_preview_invalid_identity_does_not_fall_through_to_business_write(self):
        for identity in ['not-an-id', True, 0, -1, 7.1]:
            with self.subTest(identity=identity), patch('pde.operation_workload_source_service.preview_configuration') as preview, \
                    patch('pde.views.ProductionFoundationService.write', side_effect=AssertionError('no fallback write')):
                response = self.preview(operationId=identity)
                self.assertEqual(response.status_code, 400)
                preview.assert_not_called()


class NativeOperationWorkloadConfigurationRouteTests(TestCase):
    """SIMULATED_FOR_TEST: the existing HTTP action reaches the real writer.

    Only the guarded disposable database may construct these synthetic sources.
    The service, identity, audit and readback are not mocked.
    """

    def setUp(self):
        from .tests_operation_workload_source_service import OperationWorkloadSourceTests
        self.case = OperationWorkloadSourceTests(methodName='runTest')
        self.case.setUp()
        self.factory = APIRequestFactory()

    def request(self, method, payload):
        request = getattr(self.factory, method)('/api/pde/a1-foundation/operations/', payload,
            **({'format': 'json'} if method == 'post' else {}))
        force_authenticate(request, user=self.case.f.user)
        return ProductionFoundationA1View.as_view()(request, entity='operations')

    def test_real_preview_save_and_runtime_read_use_one_formal_contract(self):
        from .models import EngineeringRuleDefinition
        case = self.case
        payload = case.payload(expression='source_quantity / 2')
        before = case.f.full_database_snapshot()
        preview = self.request('post', {'action': 'previewOperationWorkloadSourceConfiguration',
            'companyId': case.f.company.pk, 'operationId': case.operation.pk, 'configuration': payload,
            'productionPlanId': case.plan.pk, 'routingStepId': case.step.pk})
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data['configurationPreview']['passed'], preview.data)
        self.assertEqual(before, case.f.full_database_snapshot())
        response = self.request('post', {'action': 'configureOperationWorkloadSource',
            'operationId': case.operation.pk, 'reason': 'SIMULATED_FOR_TEST HTTP maintenance', **payload})
        self.assertEqual(response.status_code, 200, response.data)
        identity = response.data['nativeResult']['rules'][0]['id']
        row = EngineeringRuleDefinition.objects.get(pk=identity)
        self.assertEqual(row.status, 'released')
        self.assertEqual(row.specification['expression'], 'source_quantity / 2')
        persisted = case.f.full_database_snapshot()
        readback = self.request('get', {'action': 'operationWorkloadSources', 'operationId': case.operation.pk,
            'productionPlanId': case.plan.pk, 'routingStepId': case.step.pk})
        self.assertEqual(readback.status_code, 200, readback.data)
        read = readback.data['context']
        self.assertEqual([source['ruleId'] for source in read['sourceConfiguration']['sources']], [identity])
        self.assertEqual(read['sourceCandidates']['statusCode'], 'AVAILABLE', read)
        self.assertEqual(read['formalRequirements']['items'], [])
        self.assertIsNone(read['savedAllocations']['quantity'])
        self.assertEqual(persisted, case.f.full_database_snapshot())
