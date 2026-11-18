"""SIMULATED_FOR_TEST: scoped existing schemes, real saves and native writers.

The parent's reviewed isolated runner must enable the existing contribution
fixture allowlist. No formal database, source proof or native writer is mocked.
"""
from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from system.models import OrganizationOperatingAuditRecord, Permission, Process, RolePermission
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as native
from . import operation_workload_source_service as service
from . import tests_operation_contribution_composition as composition_fixtures
from . import tests_operation_workload_source_service as source_fixtures
from .engineering_rule_foundation import specification_hash
from .manufacturing_configuration_service import ManufacturingConfigurationService
from .manufacturing_rule_configuration import configured_source_candidate
from .manufacturing_routing_context import CONTRACT as ROUTING_CONTRACT
from .models import (EngineeringOperationRequirement, EngineeringRuleDefinition,
    ProductionPlanOperationRequirementAllocation, RoutingStep, RoutingVersion)
from .production_foundation_service import ProductionFoundationService, ProductionFoundationError, _snapshot


SELECTION_CONTRACT_READBACK = []


class OperationSourceSchemeSelectionTests(TestCase):
    def setUp(self):
        class BeforeInitialDemand(composition_fixtures.OperationContributionCompositionTests):
            def generate(inner, fact, rule):
                # Fixture arrangement ends before any EOR exists. The tested
                # generation below calls the real, unpatched native services.
                return None
            def member_rule(inner, fact, component, **kwargs):
                f = inner.f
                original = f.op_area, f.step, f.capacity
                f.op_area, f.step, f.capacity = f.selection_operation, f.selection_step, f.selection_capacity
                try:
                    return super().member_rule(fact, component, **kwargs)
                finally:
                    f.op_area, f.step, f.capacity = original
        original_advance = composition_fixtures.correction.Calc4RoutingCorrectionTests.advance

        def add_unallocated_target_before_release(fixture, obj, target, *, status_field='status'):
            if isinstance(obj, RoutingVersion) and target == 'reviewed':
                if not hasattr(fixture, 'selection_operation'):
                    fixture.selection_operation = Process.objects.create(company=fixture.company,
                        code='SIM-SELECTION-TARGET', name='SIMULATED_FOR_TEST unallocated scheme target',
                        workshop=fixture.workshop, work_center=fixture.center,
                        calculation_basis='area', calculation_uom=fixture.area)
                    fixture.selection_capacity = fixture.make_capacity(fixture.selection_operation,
                        fixture.area, 'SIM-SELECTION-CAPACITY')
                step = RoutingStep.objects.create(routing_version=obj, sequence=2,
                    operation=fixture.selection_operation, operation_parameters={'applicability': {
                        'contractVersion': 'PCE-ROUTING-STEP-APPLICABILITY-V1.0', 'mode': 'MANDATORY'}})
                if obj.routing_version == 'SIM-V1':
                    fixture.selection_step = step
            return original_advance(fixture, obj, target, status_field=status_field)

        self.case = BeforeInitialDemand(methodName='runTest')
        with patch.object(composition_fixtures.correction.Calc4RoutingCorrectionTests,
                'advance', new=add_unallocated_target_before_release):
            self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f = self.case.f
        self.operation = self.f.selection_operation
        self.f.op_area, self.f.step, self.f.capacity = self.operation, self.f.selection_step, self.f.selection_capacity
        self.assertFalse(EngineeringOperationRequirement.objects.filter(operation=self.operation).exists(),
            'The new target has no demand; every original fixture demand remains in place')
        self.declaration = self.case.configure()
        for code in ('production.master_data.resource.maintain', service.RULE_VIEW):
            permission, _ = Permission.objects.get_or_create(code=code,
                defaults={'name': code, 'module': 'PRODUCTION'})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)

    def option(self):
        options = service.source_scheme_options(self.operation)
        return next(row for row in options if row['schemeId'] == f'COMPOSITION:{self.declaration.pk}')

    def intent(self, option=None, revision=0):
        option = option or self.option()
        return {'contractVersion': service.SOURCE_SELECTION_CONTRACT, 'expectedRevision': revision,
            **{key: deepcopy(option[key]) for key in ('scope', 'schemeId', 'schemeHash')}}

    def save(self, *, intent=None, key='sim-source-scheme-save', **fields):
        return ProductionFoundationService.write('operations', user=self.f.user,
            payload={'reason': 'SIMULATED_FOR_TEST explicit existing whole scheme',
                'sourceSchemeSelection': intent if intent is not None else self.intent(), **fields},
            object_id=self.operation.pk, idempotency_key=key, source_identity=None)

    def reject_without_writes(self, call, code):
        before = self.f.full_database_snapshot()
        with self.assertRaises((ProductionFoundationError, native.OperationRequirementError)) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_complete_group_save_readback_and_real_native_generation(self):
        option = self.option()
        self.assertEqual({row['ruleId'] for row in option['ruleRefs']},
            {self.case.rule_a.pk, self.case.rule_b.pk})
        self.assertFalse(any(row['schemeId'] in {f'RULE:{self.case.rule_a.pk}', f'RULE:{self.case.rule_b.pk}'}
            for row in service.source_scheme_options(self.operation)))
        allocation_before = ProductionPlanOperationRequirementAllocation.objects.count()
        audits_before, states_before = OrganizationOperatingAuditRecord.objects.count(), BusinessStateTransition.objects.count()
        saved = self.save()
        self.operation.refresh_from_db()
        readback = service.source_selection_readback(self.operation)
        self.assertEqual(saved['row']['workloadSource']['sourceSelection'], readback)
        self.assertEqual(readback['revision'], 1)
        self.assertEqual(readback['selections'], [option])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count() - audits_before, 1)
        self.assertEqual(BusinessStateTransition.objects.count(), states_before)
        expected = {(rule.pk, fact.pk) for rule in (self.case.rule_a, self.case.rule_b)
            for fact in self.f.source_calc.derived_facts.all()
            if configured_source_candidate(selector=rule.specification['manufacturing']['sourceSelector'], fact=fact)}
        gen_audits, gen_states = OrganizationOperatingAuditRecord.objects.count(), BusinessStateTransition.objects.count()
        generated = ManufacturingConfigurationService.generate_for_calculation(user=self.f.user,
            source_calculation_id=self.f.source_calc.pk, request_key='sim-selected-whole-native',
            reason='SIMULATED_FOR_TEST whole group', rule_ids=[self.case.rule_a.pk, self.case.rule_b.pk])
        self.assertEqual(generated['blockers'], [])
        rows = list(EngineeringOperationRequirement.objects.filter(pk__in=
            [row['id'] for row in generated['requirements']]))
        self.assertEqual({(row.source_detail.rule_id, row.source_fact_id) for row in rows}, expected)
        self.assertEqual({row.source_detail.rule_id for row in rows}, {self.case.rule_a.pk, self.case.rule_b.pk})
        self.assertEqual(generated['businessWriteCount'], 3 * len(expected))
        self.assertEqual(generated['auditWriteCount'], 4 * len(expected))
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count() - gen_audits, 4 * len(expected))
        self.assertEqual(BusinessStateTransition.objects.count() - gen_states, 4 * len(expected))
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), allocation_before)
        frozen = self.f.full_database_snapshot()
        for row in rows:
            native._validate_requirement(row, self.f.company.pk, user=self.f.user)
        self.assertEqual(self.f.full_database_snapshot(), frozen)
        SELECTION_CONTRACT_READBACK.append({'recordedScope': option['scope'], 'schemeId': option['schemeId'],
            'schemeHash': option['schemeHash'], 'ruleRefs': option['ruleRefs'], 'saveAuditId': saved['auditId'],
            'saveAuditDelta': 1, 'saveStateTransitionDelta': 0, 'readback': readback,
            'nativeMemberRuleIds': sorted({row.source_detail.rule_id for row in rows}), 'nativeRequirementCount': len(rows),
            'nativeBusinessWriteCount': generated['businessWriteCount'], 'nativeAuditWriteCount': generated['auditWriteCount'],
            'nativeStateTransitionDelta': BusinessStateTransition.objects.count() - gen_states,
            'allocationCountUnchanged': True, 'frozenReadSnapshotUnchanged': True})

    def test_single_member_and_partial_batch_cannot_bypass_selected_group(self):
        self.save()
        self.reject_without_writes(lambda: native.OperationRequirementService.generate(user=self.f.user,
            source_calculation_id=self.f.source_calc.pk, source_fact_id=self.f.facts[0].pk,
            rule_id=self.case.rule_a.pk, idempotency_key='sim-partial-single', reason='SIMULATED_FOR_TEST'),
            'WORKLOAD_SOURCE_SCHEME_GROUP_REQUIRED')
        self.reject_without_writes(lambda: ManufacturingConfigurationService.generate_for_calculation(user=self.f.user,
            source_calculation_id=self.f.source_calc.pk, request_key='sim-partial-batch', reason='SIMULATED_FOR_TEST',
            rule_ids=[self.case.rule_a.pk]), 'WORKLOAD_SOURCE_SCHEME_GROUP_REQUIRED')

    def test_client_json_members_stale_scope_and_revision_reject_without_writes(self):
        self.reject_without_writes(lambda: ProductionFoundationService.write('operations', user=self.f.user,
            payload={'workload_source_selection': {}, 'reason': 'SIMULATED_FOR_TEST'},
            object_id=self.operation.pk, idempotency_key='sim-raw-json', source_identity=None),
            'WORKLOAD_SOURCE_SELECTION_INTENT_REQUIRED')
        for name, mutate, code in (
            ('members', lambda value: value.update(ruleRefs=[]), 'WORKLOAD_SOURCE_SELECTION_INTENT_INVALID'),
            ('hash', lambda value: value.update(schemeHash='0' * 64), 'WORKLOAD_SOURCE_SELECTION_STALE'),
            ('revision', lambda value: value.update(expectedRevision=1), 'WORKLOAD_SOURCE_SELECTION_REVISION_CONFLICT'),
            ('scope', lambda value: value['scope'].update(companyId=self.f.company.pk + 1000), 'WORKLOAD_SOURCE_SELECTION_STALE'),
        ):
            with self.subTest(name=name):
                value = self.intent(); mutate(value)
                self.reject_without_writes(lambda: self.save(intent=value, key='sim-invalid-' + name), code)
        self.reject_without_writes(lambda: ProductionFoundationService.write('work-centers', user=self.f.user,
            payload={'sourceSchemeSelection': self.intent(), 'reason': 'SIMULATED_FOR_TEST'},
            object_id=self.f.center.pk, idempotency_key='sim-wrong-entity', source_identity=None), 'UNKNOWN_FIELDS')

    def test_current_permissions_required_for_write_and_idempotent_replay(self):
        self.save()
        RolePermission.objects.filter(role=self.f.role, permission__code=service.RELEASE).delete()
        self.reject_without_writes(lambda: self.save(), 'PERMISSION_DENIED')
        self.reject_without_writes(lambda: self.save(intent=self.intent(revision=1), key='sim-denied-new'), 'PERMISSION_DENIED')

    def test_tampered_reference_or_audit_fails_closed_without_list_failure(self):
        self.save()
        self.operation.refresh_from_db()
        state = deepcopy(self.operation.workload_source_selection)
        state['selections'][0]['schemeHash'] = 'e' * 64
        Process.objects.filter(pk=self.operation.pk).update(workload_source_selection=state)
        self.operation.refresh_from_db()
        before = self.f.full_database_snapshot()
        value = service.project_operation_sources([self.operation], self.f.company.pk, include_schemes=True)[self.operation.pk]
        self.assertFalse(value['hasValidSourceConfiguration'])
        self.assertFalse(value['sourceSelection']['valid'])
        self.assertEqual(value['sources'], [])
        self.assertEqual(value['blockers'][-1]['code'], 'WORKLOAD_SOURCE_SELECTION_AUDIT_INVALID')
        with self.assertRaises(service.OperationWorkloadSourceError):
            service.check_source_scheme_generation(user=self.f.user, rule=self.case.rule_a)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_final_operation_unit_edit_cannot_invalidate_applied_scheme(self):
        self.save()
        self.reject_without_writes(lambda: ProductionFoundationService.write('operations', user=self.f.user,
            payload={'calculation_uom_id': self.f.pcs.pk, 'reason': 'SIMULATED_FOR_TEST incompatible final unit'},
            object_id=self.operation.pk, idempotency_key='sim-unit-invalid', source_identity=None),
            'WORKLOAD_SOURCE_SELECTION_STALE')

    def test_new_control_field_preserves_all_old_process_proof_fields(self):
        legacy = _snapshot(self.operation)
        self.assertNotIn('workload_source_selection', legacy)
        self.assertEqual(native._proof_record_hash(self.operation), native._digest(legacy))
        before = native._proof_record_hash(self.operation)
        self.save()
        self.operation.refresh_from_db()
        self.assertEqual(_snapshot(self.operation), legacy)
        self.assertEqual(native._proof_record_hash(self.operation), before)
        full = _snapshot(self.operation, include_workload_source_selection=True)
        self.assertEqual(full.pop('workload_source_selection'), self.operation.workload_source_selection)
        self.assertEqual(full, legacy)

    def test_expired_group_or_member_never_degrades_to_singleton(self):
        EngineeringRuleDefinition.objects.filter(pk=self.declaration.pk).update(effective_to=date.today() - timedelta(days=1))
        EngineeringRuleDefinition.objects.filter(pk=self.case.rule_b.pk).update(effective_to=date.today() - timedelta(days=1))
        options = service.source_scheme_options(self.operation)
        self.assertFalse(any(row['schemeId'] in {f'COMPOSITION:{self.declaration.pk}', f'RULE:{self.case.rule_a.pk}'}
            for row in options))

    def test_existing_frozen_requirement_and_allocation_keep_fixed_proofs_after_future_selection(self):
        generated = native.OperationRequirementService.generate(user=self.f.user,
            source_calculation_id=self.f.source_calc.pk, source_fact_id=self.f.facts[0].pk,
            rule_id=self.case.rule_a.pk, idempotency_key='sim-original-frozen-eor', reason='SIMULATED_FOR_TEST')
        requirement = EngineeringOperationRequirement.objects.get(pk=generated['operationRequirementId'])
        native.OperationRequirementService.allocate(user=self.f.user, production_plan_id=self.case.plan.pk,
            operation_requirement_id=requirement.pk, routing_step_id=self.f.step.pk,
            idempotency_key='sim-original-frozen-load', reason='SIMULATED_FOR_TEST before future selection')
        frozen_requirements = list(EngineeringOperationRequirement.objects.values())
        frozen_allocations = list(ProductionPlanOperationRequirementAllocation.objects.values())
        hashes = {row.pk: native._proof_record_hash(row) for row in EngineeringOperationRequirement.objects.all()}
        original = native.OperationRequirementService.read(user=self.f.user, production_plan_id=self.case.plan.pk)
        self.assertTrue(original['passed'], original)
        self.save()
        self.assertEqual(list(EngineeringOperationRequirement.objects.values()), frozen_requirements)
        self.assertEqual(list(ProductionPlanOperationRequirementAllocation.objects.values()), frozen_allocations)
        self.assertEqual({row.pk: native._proof_record_hash(row) for row in EngineeringOperationRequirement.objects.all()}, hashes)
        before = self.f.full_database_snapshot()
        native._validate_requirement(requirement, self.f.company.pk, user=self.f.user)
        self.assertEqual(native.OperationRequirementService.read(user=self.f.user,
            production_plan_id=self.case.plan.pk), original)
        self.assertEqual(self.f.full_database_snapshot(), before)
        replay = native.OperationRequirementService.generate(user=self.f.user,
            source_calculation_id=self.f.source_calc.pk, source_fact_id=self.f.facts[0].pk,
            rule_id=self.case.rule_a.pk, idempotency_key='sim-original-frozen-eor', reason='SIMULATED_FOR_TEST')
        self.assertTrue(replay['idempotent'])
        self.assertEqual((replay['businessWriteCount'], replay['auditWriteCount']), (0, 0))
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_missing_or_falsey_damaged_marker_never_restores_legacy_generation(self):
        self.save()
        for state, code in ((None, 'WORKLOAD_SOURCE_SELECTION_MISSING'),
                ({}, 'WORKLOAD_SOURCE_SELECTION_MISSING'), ([], 'WORKLOAD_SOURCE_SELECTION_INVALID'),
                ('', 'WORKLOAD_SOURCE_SELECTION_INVALID'), (0, 'WORKLOAD_SOURCE_SELECTION_INVALID')):
            with self.subTest(state=state):
                Process.objects.filter(pk=self.operation.pk).update(workload_source_selection=state)
                self.operation.refresh_from_db()
                before = self.f.full_database_snapshot()
                with self.assertRaises(service.OperationWorkloadSourceError) as caught:
                    service.check_source_scheme_generation(user=self.f.user, rule=self.case.rule_a)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.f.full_database_snapshot(), before)


class OperationSourceSchemeScopeTests(TestCase):
    def setUp(self):
        self.case = source_fixtures.OperationWorkloadSourceTests(methodName='runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f, self.operation = self.case.f, self.case.operation
        for code in ('production.master_data.resource.maintain',):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'module': 'PRODUCTION'})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)

    def test_distinct_route_versions_are_preserved_and_selected_only_for_new_generation(self):
        steps = [self.case.step, self.f.source_other_step]
        for index, step in enumerate(steps):
            context = {'contractVersion': ROUTING_CONTRACT,
                'routingId': step.routing_version.routing_id, 'routingVersionId': step.routing_version_id,
                'routingStepId': step.pk}
            self.case.configure(ruleCode=f'SIM-SCOPE-SCHEME-{index}', routingContext=context)
        options = service.source_scheme_options(self.operation)
        self.assertEqual(len(options), 2)
        for revision, option in enumerate(options):
            intent = {'contractVersion': service.SOURCE_SELECTION_CONTRACT, 'expectedRevision': revision,
                **{key: deepcopy(option[key]) for key in ('scope', 'schemeId', 'schemeHash')}}
            ProductionFoundationService.write('operations', user=self.f.user, object_id=self.operation.pk,
                payload={'sourceSchemeSelection': intent, 'reason': 'SIMULATED_FOR_TEST scoped selection'},
                idempotency_key=f'sim-multi-scope-{revision}', source_identity=None)
        self.operation.refresh_from_db()
        readback = service.source_selection_readback(self.operation)
        self.assertEqual(readback['revision'], 2)
        self.assertEqual({row['schemeHash'] for row in readback['selections']}, {row['schemeHash'] for row in options})
        # The plan reader explicitly retains its fixed-source projection; new
        # Process selections are only a new-generation/current-maintenance gate.
        frozen = self.f.full_database_snapshot()
        self.case.read()
        self.assertEqual(self.f.full_database_snapshot(), frozen)
