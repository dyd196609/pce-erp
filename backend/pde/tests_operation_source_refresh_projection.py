"""SIMULATED_FOR_TEST: original GET, native whole schemes, bounded projection.

Run only with the existing two-file isolated runner. No source proof, candidate
builder, authorization decision or view result is replaced with a success mock.
"""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from system.models import Process, RolePermission
from . import operation_workload_source_service as sources
from . import tests_operation_source_scheme_selection as fixtures
from .production_foundation_service import ProductionFoundationService
from .views import ProductionFoundationA1View


class OperationSourceRefreshProjectionTests(TestCase):
    def setUp(self):
        self.case = fixtures.OperationSourceSchemeSelectionTests(methodName='runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f, self.operation = self.case.f, self.case.operation

    def get_sources(self, **params):
        request = APIRequestFactory().get('/api/pde/a1-foundation/operations/',
            {'action': 'operationWorkloadSources', **params})
        force_authenticate(request, user=self.f.user)
        return ProductionFoundationA1View.as_view()(request, entity='operations')

    def test_plain_list_and_catalog_do_not_build_optional_schemes(self):
        before = self.f.full_database_snapshot()
        with patch.object(sources, 'source_scheme_options', wraps=sources.source_scheme_options) as options, \
                patch.object(sources, '_selection_entries', wraps=sources._selection_entries) as selections:
            rows = ProductionFoundationService.list('operations', organization_id=self.f.company.pk)
            response = self.get_sources()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(options.call_count, 0)
        self.assertGreater(selections.call_count, 0, 'Empty-marker/tombstone verification remains active')
        self.assertIsNone(response.data['configuration'])
        self.assertIsNone(response.data['context'])
        self.assertEqual(response.data['operations'], rows)
        self.assertTrue(rows)
        self.assertTrue(all('sourceSchemes' not in row['workloadSource']
            and 'sourceSelection' not in row['workloadSource'] for row in rows))
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_explicit_operation_get_returns_complete_group_once_and_reuses_configuration(self):
        expected = deepcopy(self.case.option())
        before = self.f.full_database_snapshot()
        with patch.object(sources, 'source_scheme_options', wraps=sources.source_scheme_options) as options:
            response = self.get_sources(operationId=self.operation.pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(options.call_count, 1)
        self.assertEqual(sources._operation_id(options.call_args.args[0]), self.operation.pk)
        configuration = response.data['configuration']
        lookup = next(row for row in response.data['operations'] if row['id'] == self.operation.pk)
        self.assertIs(configuration, lookup['workloadSource'])
        self.assertIn(expected, configuration['sourceSchemes'])
        selected = next(row for row in configuration['sourceSchemes'] if row['schemeId'] == expected['schemeId'])
        self.assertEqual({row['ruleId'] for row in selected['ruleRefs']},
            {self.case.case.rule_a.pk, self.case.case.rule_b.pk})
        self.assertEqual(configuration['sourceSelection'], sources.source_selection_readback(self.operation))
        self.assertTrue(all('sourceSchemes' not in row['workloadSource']
            for row in response.data['operations'] if row['id'] != self.operation.pk))
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_unknown_operation_is_rejected_without_candidates_or_writes(self):
        before = self.f.full_database_snapshot()
        with patch.object(sources, 'source_scheme_options', wraps=sources.source_scheme_options) as options:
            response = self.get_sources(operationId=1000000 + self.operation.pk)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['code'], 'OPERATION_SCOPE_MISMATCH')
        self.assertEqual(options.call_count, 0)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_original_rule_view_permission_still_precedes_candidate_read(self):
        RolePermission.objects.filter(role=self.f.role, permission__code=sources.RULE_VIEW).delete()
        before = self.f.full_database_snapshot()
        with patch.object(sources, 'source_scheme_options', wraps=sources.source_scheme_options) as options:
            response = self.get_sources(operationId=self.operation.pk)
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')
        self.assertEqual(options.call_count, 0)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_plain_list_keeps_missing_selected_marker_fail_closed(self):
        self.case.save()
        Process.objects.filter(pk=self.operation.pk).update(workload_source_selection=None)
        before = self.f.full_database_snapshot()
        rows = ProductionFoundationService.list('operations', organization_id=self.f.company.pk)
        value = next(row['workloadSource'] for row in rows if row['id'] == self.operation.pk)
        self.assertFalse(value['hasValidSourceConfiguration'])
        self.assertEqual(value['sources'], [])
        self.assertIn('WORKLOAD_SOURCE_SELECTION_MISSING', {row['code'] for row in value['blockers']})
        self.assertEqual(self.f.full_database_snapshot(), before)
