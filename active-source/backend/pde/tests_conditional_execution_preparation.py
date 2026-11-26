"""SIMULATED_FOR_TEST: execute only in the parent's isolated test database."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from masterdata.models import MasterDataWriteRequest, CodeRule
from planning.models import Demand, PlanningRequirement, ProductionPlan
from system.models import OrganizationOperatingAuditRecord, Permission, RolePermission
from workflow_runtime.state_transitions import create_business_object_with_initial_state
from . import conditional_execution_preparation as conditional
from . import operation_input_preparation_service as preparation
from . import operation_requirement_service as operation
from .models import OperationInputPreparationDraft, CapacityProductType
from .production_foundation_service import ProductionFoundationError
from .routing_version_successor_service import ROUTING_PERMISSION, RoutingVersionChangeError
from . import tests_engineering_version_handoff_upstream as published_fixtures
from . import tests_operation_requirement as requirement_fixtures
from . import tests_classified_fact_eor as snapshot_fixtures


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=published_fixtures.SCOPE)
class ConditionalExecutionPreparationTests(TestCase):
    def setUp(self):
        # The existing published fixture declares its two upstream document
        # proof stubs. Output generation/release remain native; neither
        # validate_selected_output nor any preparation proof is replaced.
        published = published_fixtures.EngineeringVersionHandoffUpstreamTests(methodName='runTest')
        published.setUp()
        self.addCleanup(published.doCleanups)
        self.user, self.company = published.executor, published.company
        self.step = published.category_routing_version.steps.get()
        self.step.operation.calculation_uom = published.uom
        self.step.operation.save(update_fields=('calculation_uom',))
        for code in (preparation.VIEW, preparation.CREATE, preparation.UPDATE, preparation.CAPACITY,
                operation.VIEW, operation.EXECUTE, operation.PLAN_VIEW, ROUTING_PERMISSION):
            permission, _ = Permission.objects.get_or_create(code=code,
                defaults={'name': code, 'module': 'PDE'})
            RolePermission.objects.get_or_create(role=published.executing_role, permission=permission)
        output, _ = published._generate()
        published._release(output, 'sim-quality-anchor-release')
        demand = create_business_object_with_initial_state(model=Demand, initial_state='draft',
            demand_no='QUALITY-SIM-DEMAND', source_type='sales_order', source_document_type='SalesOrder',
            source_document_id=str(published.order.pk), source_document_no=published.order.order_no,
            sales_order_item=published.order_item, manufacturing_output=output, material=published.finished,
            required_qty=1, required_date=date.today(), department=published.department,
            reason='SIMULATED_FOR_TEST published anchor', created_by=self.user)
        requirement = PlanningRequirement.objects.create(requirement_no='QUALITY-SIM-REQ',
            demand=demand, material=published.finished, demand_qty=1, available_qty=0, net_required_qty=1,
            required_date=date.today(), supply_type='production', status='confirmed', created_by=self.user)
        self.plan = ProductionPlan.objects.create(plan_no='QUALITY-SIM-PLAN', planning_requirement=requirement,
            material=published.finished, planned_qty=1, required_date=date.today(), source_id=str(requirement.pk),
            confirmed_by=self.user, status='confirmed')
        self.product_type = CapacityProductType.objects.create(company=self.company, code='QUALITY-SIM-TYPE',
            name='isolated exact product and process', product_category=published.category,
            manufacturing_process_type=published.process_type)
        self.f = SimpleNamespace(output=output, source_calc=published.calculation, baseline=published.baseline,
            item=published.order_item, area=published.uom, center=SimpleNamespace(pk=999999),
            full_database_snapshot=lambda: snapshot_fixtures.ClassifiedFactEorTests.full_database_snapshot(self))
        self.scope = {'companyId': self.company.pk, 'productionPlanId': self.plan.pk,
            'manufacturingOutputId': output.pk, 'mainCalculationId': published.calculation.pk,
            'salesOrderItemId': published.order_item.pk, 'baselineId': published.baseline.pk,
            'routingVersionId': output.routing_version_id, 'routingStepId': self.step.pk,
            'operationId': self.step.operation_id, 'productTypeId': self.product_type.pk}
        self.role = published.executing_role
        self.pcs, self.rule_counter = published.uom, 0
        self.initial = requirement_fixtures.OperationRequirementTests.initial.__get__(self)
        self.advance = requirement_fixtures.OperationRequirementTests.advance.__get__(self)
        CodeRule.objects.get_or_create(company_id=self.company.pk, entity_type='production_engineering_calculation',
            defaults={'prefix': 'QUALITY-SIM-', 'date_format': '', 'seq_length': 4})
        self.context = conditional.build_conditional_context(user=self.user, exact_scope=self.scope)
        self.basis = conditional.build_conditional_basis(context=self.context,
            reference='SIMULATED_FOR_TEST/quality-policy',
            reference_sha256=sha256(b'SIMULATED_FOR_TEST/quality-policy').hexdigest(),
            exact_statement='品质异常触发时执行，当前待触发；对象部位数量单位未知；触发后产能0且不占定量产能。',
            execution_statement='模拟业务事实：本范围未领料、未开工。')

    def save(self, **changes):
        args = dict(user=self.user, exact_scope=deepcopy(self.scope), business_basis=deepcopy(self.basis),
            expected_context_hash=self.context['context_hash'], expected_revision=None,
            idempotency_key='sim-quality-conditional', reason='SIMULATED_FOR_TEST conditional policy')
        args.update(changes)
        return preparation.save_preparation(**args)

    def read(self):
        return preparation.read_preparation(user=self.user, exact_scope=self.scope)

    def readonly(self, callback):
        before = self.f.full_database_snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = callback()
        self.assertEqual(before, self.f.full_database_snapshot())
        self.assertFalse(any(row['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
            for row in queries))
        return result

    def rejected(self, callback, code=None):
        before = self.f.full_database_snapshot()
        with self.assertRaises((ProductionFoundationError, ValidationError, RoutingVersionChangeError)) as caught:
            callback()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(before, self.f.full_database_snapshot())

    def test_native_save_read_and_replay_keep_unknown_workload_and_independent_zero_policy(self):
        route_before = deepcopy(self.step.routing_version.applicability)
        audits_before = list(OrganizationOperatingAuditRecord.objects.order_by('pk').values())
        saved = self.save()
        row = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        self.assertEqual(row.object_coverage, conditional.COVERAGE)
        self.assertEqual(row.business_basis, self.basis)
        self.assertEqual(self.step.routing_version.applicability, route_before)
        self.assertEqual(list(OrganizationOperatingAuditRecord.objects.filter(
            pk__in=[item['id'] for item in audits_before]).order_by('pk').values()), audits_before)
        result = self.readonly(self.read)
        self.assertTrue(result['formalPolicyValidated'])
        self.assertFalse(result['formalApplicabilityValidated'])
        self.assertEqual((result['result'], result['triggerStatus']), ('PENDING', 'WAITING_TRIGGER'))
        self.assertEqual(result['conditionalCapacityPolicy'], conditional.CAPACITY_POLICY)
        self.assertIsNone(result['capacitySemantics']['meaningCode'])
        for field in ('sourceQuantity', 'inputQuantity', 'quantity', 'uomId', 'capacityBusinessValue'):
            self.assertIsNone(result[field])
        for field in ('readyForGeneration', 'readyForAllocation', 'readyForScheduling'):
            self.assertFalse(result[field])
        resolved = self.readonly(lambda: conditional.resolve_conditional_execution(self.step, self.plan,
            manufacturing_output=self.f.output, engineering_calculation=self.f.source_calc,
            order_engineering_baseline=self.f.baseline, bom_version=self.f.output.bom_version))
        self.assertEqual(resolved, result)
        replay = self.readonly(self.save)
        self.assertTrue(replay['idempotentReplay'])
        self.assertEqual(replay['recordId'], row.pk)
        self.assertEqual(result['statusTransitionCount'], len(result['statusTransitionHistory']))
        self.assertEqual(result['statusTransitionHistory'][0]['auditReference'],
            f"OrganizationOperatingAuditRecord:{saved['auditId']}")
        self.assertIsNone(operation._proof_record_hash(None))

    def test_no_record_returns_none_and_never_grants_or_changes_a_route(self):
        self.assertIsNone(self.readonly(lambda: conditional.resolve_conditional_execution(self.step, self.plan)))
        self.assertFalse(OperationInputPreparationDraft.objects.exists())

    def test_forbidden_trigger_quantity_unit_capacity_types_and_selections_are_rejected_before_writes(self):
        for field, value in (('triggerStatus', 'TRIGGERED'), ('quantity', 0), ('quantity', '1'),
                ('uomId', self.f.area.pk), ('affectedObjects', []), ('affectedParts', ['part'])):
            basis = deepcopy(self.basis)
            basis['conditionalExecution'][field] = value
            with self.subTest(field=field, value=value):
                self.rejected(lambda: self.save(business_basis=basis), 'PREPARATION_CONDITIONAL_INVALID')
        for path, value in (('quantitativeOccupancyAllowed', True), ('quantitativeOccupancyAllowed', 0),
                ('sourceValue', 0), ('sourceValue', None), ('meaningCode', 'QUANTIFIED')):
            basis = deepcopy(self.basis)
            basis['conditionalExecution']['capacityPolicy'][path] = value
            with self.subTest(capacity=path, value=value):
                self.rejected(lambda: self.save(business_basis=basis), 'PREPARATION_CONDITIONAL_INVALID')
        self.rejected(lambda: self.save(work_center_id=self.f.center.pk), 'PREPARATION_CONDITIONAL_INVALID')
        self.rejected(lambda: self.save(draft_selection={'basisQuantity': '1'}), 'PREPARATION_CONDITIONAL_INVALID')

    def test_all_exact_scope_identities_and_actor_company_are_checked(self):
        for key in self.scope:
            changed = deepcopy(self.scope)
            changed[key] += 100000
            with self.subTest(key=key):
                self.rejected(lambda: self.save(exact_scope=changed))
        self.rejected(lambda: self.save(expected_context_hash='0' * 64), 'PREPARATION_CONTEXT_DRIFT')

    def test_ordinary_preparation_cannot_be_converted_or_overwritten(self):
        initial = preparation.read_preparation(user=self.user, exact_scope=self.scope)
        basis = {'contractVersion': preparation.BASIS_CONTRACT, 'entries': [{
            'reference': 'SIMULATED_FOR_TEST/ordinary-preparation',
            'referenceSha256': sha256(b'SIMULATED_FOR_TEST/ordinary-preparation').hexdigest(),
            'exactStatement': '普通投入标准准备，保留精确已证明对象范围。',
            'scope': deepcopy(self.scope), 'objectCoverage': initial['objectCoverage']}]}
        ordinary = preparation.save_preparation(user=self.user, exact_scope=self.scope, business_basis=basis,
            expected_context_hash=initial['contextHash'], idempotency_key='sim-quality-ordinary',
            reason='SIMULATED_FOR_TEST ordinary preparation')
        self.rejected(self.save, 'PREPARATION_CONDITIONAL_CONFLICT')
        result = self.read()
        self.assertEqual(result['recordId'], ordinary['recordId'])
        self.assertNotIn('conditionalExecution', result)

    def test_current_object_drift_remains_a_native_gate_without_inventing_policy_object_coverage(self):
        from .models import OrderEngineeringBaselineItem
        from .routing_object_applicability_service import RoutingObjectApplicabilityService
        obj = OrderEngineeringBaselineItem.objects.filter(baseline=self.f.baseline,
            design_item__sales_order_item=self.f.item).first()
        design = obj.design_item
        design.version += 1
        design.save(update_fields=('version',))
        with self.assertRaises((ProductionFoundationError, ValidationError, RoutingVersionChangeError)):
            RoutingObjectApplicabilityService.build_context(self.plan.pk, self.step.pk, obj.pk)
        self.save()
        result = self.readonly(self.read)
        self.assertEqual(result['objectCoverage'], conditional.COVERAGE)
        self.assertIsNone(result['conditionalExecution']['affectedObjects'])

    def test_ledger_audit_identity_and_initial_state_corruption_never_restores_legacy_decision(self):
        from workflow_runtime.models import BusinessStateTransition
        saved = self.save()
        row = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        for target in ('ledger', 'audit', 'identity', 'state'):
            with self.subTest(target=target), transaction.atomic():
                if target == 'ledger':
                    MasterDataWriteRequest.objects.filter(pk=saved['writeRequestId']).update(status='RESERVED')
                elif target == 'audit':
                    OrganizationOperatingAuditRecord.objects.filter(pk=saved['auditId']).update(after_snapshot={})
                elif target == 'identity':
                    identity = row.creation_write_request.source_identity
                    type(identity).objects.filter(pk=identity.pk).update(source_fingerprint='0' * 64)
                else:
                    BusinessStateTransition.objects.filter(object_type='OperationInputPreparationDraft',
                        object_id=row.pk).delete()
                self.rejected(self.read)
                self.rejected(lambda: conditional.resolve_conditional_execution(self.step, self.plan))
                transaction.set_rollback(True)

    def test_existing_formal_requirement_blocks_save_without_changing_history(self):
        fact = self.f.source_calc.derived_facts.get()
        rule = requirement_fixtures.OperationRequirementTests.make_rule(self, self.step.operation,
            self.pcs, fact.canonical_field, basis='SOURCE_SCOPE_TOTAL', basis_quantity='1')
        operation.OperationRequirementService.generate(user=self.user,
            source_calculation_id=fact.calculation_id, source_fact_id=fact.pk,
            rule_id=rule.pk, idempotency_key='sim-quality-preexisting-eor',
            reason='SIMULATED_FOR_TEST preexisting formal requirement')
        self.rejected(self.save, 'PREPARATION_CONDITIONAL_PERSISTENCE_CONFLICT')

    def test_policy_is_immutable_across_revisions_but_original_basis_can_be_appended(self):
        saved = self.save()
        changed = deepcopy(self.basis)
        changed['conditionalExecution']['executionFact']['statement'] = 'SIMULATED_FOR_TEST changed declaration'
        self.rejected(lambda: self.save(business_basis=changed, expected_revision=saved['revision'],
            idempotency_key='sim-quality-replace-policy'), 'PREPARATION_BASIS_IMMUTABLE')
        appended = deepcopy(self.basis)
        entry = deepcopy(appended['entries'][0])
        entry.update(reference='SIMULATED_FOR_TEST/additional-basis',
            referenceSha256=sha256(b'SIMULATED_FOR_TEST/additional-basis').hexdigest(),
            exactStatement='补充依据，原待触发政策与原答复保持。')
        appended['entries'].append(entry)
        updated = self.save(business_basis=appended, expected_revision=saved['revision'],
            idempotency_key='sim-quality-append-basis')
        self.assertEqual(updated['revision'], 2)
        result = self.readonly(self.read)
        self.assertEqual(result['businessBasis'], appended)
        self.assertEqual(len(result['auditIds']), 2)

    def test_existing_routing_maintain_permission_is_required_for_write_and_replay(self):
        saved = self.save()
        RolePermission.objects.filter(role=self.role, permission__code=ROUTING_PERMISSION).delete()
        self.rejected(self.save, 'PERMISSION_DENIED')
        self.rejected(lambda: self.save(idempotency_key='sim-quality-no-routing'), 'PERMISSION_DENIED')
        row = OperationInputPreparationDraft.objects.get(pk=saved['recordId'])
        self.assertEqual(row.revision, 1)

    def test_readback_preserves_strict_common_preparation_contract_without_changing_saved_proof(self):
        saved = self.save()
        before = OperationInputPreparationDraft.objects.filter(pk=saved['recordId']).values().get()
        result = self.readonly(self.read)
        for field in ('sourceQuantity', 'inputQuantity', 'capacityQuantity'):
            self.assertIn(field, result)
            self.assertIsNone(result[field])
        for field in ('statusLabel', 'inputStandardStatusLabel', 'capacityMeasurementStatusLabel',
                'formalRuleStatusLabel', 'scopeLabel'):
            self.assertIsInstance(result[field], str)
            self.assertTrue(result[field].strip())
        self.assertEqual(result['remainingItems'], [{'code': 'TRIGGER_SCOPE_NOT_YET_DETERMINED',
            'statusLabel': result['pendingScopeLabel']}])
        self.assertEqual(result['businessBasisPresentation'], [{'entryIndex': index,
            'statusLabel': '已确认的条件准备依据', 'exactStatement': entry['exactStatement'],
            'reference': entry['reference'], 'referenceSha256': entry['referenceSha256']}
            for index, entry in enumerate(self.basis['entries'])])
        self.assertEqual(result['businessBasis'], before['business_basis'])
        self.assertEqual(result['contentHash'], before['content_hash'])
        self.assertEqual(result['contextHash'], before['context_hash'])
        self.assertEqual(before, OperationInputPreparationDraft.objects.filter(pk=saved['recordId']).values().get())
