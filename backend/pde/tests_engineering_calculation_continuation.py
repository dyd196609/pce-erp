"""Synthetic capability tests; no formal source, employee or business admission.

The numeric workbook adapter alone is replaced by a deterministic fixture.
Native legacy adoption, baseline save/confirm, permissions, actor chain, main
calculation persistence, code allocation, continuation ledger/audit/state and
rollback run normally. Design change audit rows are explicit isolated fixtures;
they do not certify any production design or missing production workbook.
"""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from system.models import (Company, OrganizationOperatingAuditRecord, Permission,
    PositionResponsibility, RolePermission, User, UserRoleScopeAssignment)
from workflow_runtime.models import BusinessStateTransition
from . import formal_engineering_continuation_service as native
from .engineering_calculation_continuation_service import (ACTION, OBJECT,
    EngineeringCalculationContinuationService as Service, EngineeringCalculationContinuationError,
    continuation_proof, digest, normal, _protected_snapshot)
from .engineering_calculation_service import EngineeringCalculationError
from .legacy_inflight_order_adoption import (require_active_legacy_adoption,
    LegacyInFlightOrderAdoptionError)
from .models import (EngineeringCalculationContinuation, EngineeringCalculationDetail,
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringRuleDefinition,
    LegacyInFlightOrderAdoption, ManufacturingProcessType, OrderEngineeringBaseline, ProductDesignItem, ProductDesignRevision)
from .product_design_service import ACTION_DESIGN_SAVE
from .product_version_management_service import (product_version_management_facts,
    save_order_engineering_baseline_draft, confirm_order_engineering_baseline)
from .tests_legacy_inflight_order_adoption import LegacyInFlightOrderAdoptionTests as LegacyFixture

CONTRACT_READBACK={}


class EngineeringCalculationContinuationTests(TestCase):
    _adopt=LegacyFixture._adopt

    @classmethod
    def setUpTestData(cls):
        LegacyFixture.setUpTestData.__func__(cls)
        for code in ('production.engineering.calculation.view','production.engineering.calculation.execute',
                     'production.engineering.baseline.save','production.engineering.baseline.confirm'):
            permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code,'module':'production'})
            RolePermission.objects.get_or_create(role=cls.role,permission=permission)
        PositionResponsibility.objects.create(position=cls.position,responsibility=cls.responsibility,active=True)
        CodeRule.objects.create(company_id=cls.company.pk,entity_type='production_engineering_calculation',
            prefix='CONT-FIXTURE-',current_seq=0)
        cls.rules=[]
        cls.process=ManufacturingProcessType.objects.create(company=cls.company,code='FIXTURE-PROCESS',name='isolated process')
        for blueprint in native.formal_rule_blueprints():
            rule=EngineeringRuleDefinition(status='released',**{**blueprint,'company_id':cls.company.pk})
            rule._business_state_initialization_authorized=True;rule.save();cls.rules.append(rule)
        # A real persisted result envelope on the pre-adoption fixed main.
        calc=cls.calculations[0];rule=cls.rules[0]
        detail=EngineeringCalculationDetail.objects.create(calculation=calc,sequence=1,rule=rule,
            rule_code=rule.rule_code,rule_version=rule.version,expression_snapshot='FIXTURE',
            input_snapshot={},dependency_snapshot=[],output_name='fixture_quantity',output_value={'decimal':'1'},
            uom=cls.uom,precision=28,rounding='ROUND_HALF_UP',status='succeeded',
            started_at=calc.started_at,finished_at=calc.finished_at)
        fact=EngineeringDerivedFact.objects.create(calculation=calc,source_detail=detail,rule=rule,
            fact_code='FIXTURE:Q',canonical_field='fixture_quantity',value={'decimal':'1'},uom=cls.uom,
            source_path='isolated.fixture',trace={'unitSnapshot':cls.uom.code})
        graph=[{'id':r.pk,'ruleCode':r.rule_code,'version':r.version,
            'specificationHash':native._hash(r.specification)} for r in cls.rules]
        result=[{'factId':fact.pk,'detailId':detail.pk,'canonicalField':fact.canonical_field,
            'value':fact.value,'unit':cls.uom.code,'ruleCode':rule.rule_code,'ruleVersion':rule.version}]
        old_item=cls.baseline.items.get(design_item=cls.design_items[0])
        objects=[{'designItemId':cls.design_items[0].pk,'contentHash':old_item.content_hash}]
        trace={'baselineReference':{'id':cls.baseline.pk,'baselineNo':cls.baseline.baseline_no},
            'objectInputSnapshot':objects,'ruleGraphSnapshot':graph,'resultSnapshot':result}
        EngineeringCalculationRecord.objects.filter(pk=calc.pk).update(trace=trace,
            result_hash=native._hash(result),rule_graph_hash=native._hash(graph))
        cls.calculations[0].refresh_from_db()

    def setUp(self):
        self.adoption_id=self._adopt()['legacyAdoptionId']
        self.adoption=LegacyInFlightOrderAdoption.objects.get(pk=self.adoption_id)
        self.frozen_adoption=normal(LegacyInFlightOrderAdoption.objects.values().get(pk=self.adoption_id))
        # Native baseline services consume full isolated design snapshots.
        for item in self.design_items:
            ProductDesignItem.objects.filter(pk=item.pk).update(
                existing_design_data={'preserved':True,'routingProcessCode':self.process.code,
                    'provenance':{'sourceSheet':'FIXTURE','sourceRow':item.pk}},
                product_category=self.category,physical_quantity=1,physical_uom=self.uom,
                physical_uom_snapshot=self.uom.code)
        design=self.design_items[0];design.refresh_from_db()
        self.revision=ProductDesignRevision.objects.create(design_item=design,revision=1,
            design_nature='FORMAL',design_length=10,design_width=20,material=self.material,
            design_data={'fixture':'new controlled content'},change_reason='隔离正式修订凭证',created_by=self.actor)
        ProductDesignItem.objects.filter(pk=design.pk).update(version=design.version+1)
        body={'itemIds':[design.pk],'reason':'isolated native-shaped design audit fixture'}
        audit=OrganizationOperatingAuditRecord.objects.create(organization_id=self.company.pk,actor=self.actor,
            action_code=ACTION_DESIGN_SAVE,target_type='ProductDesignItemBatch',target_id=design.pk,
            target_label='isolated design fixture',reason='isolated',before_snapshot=[],after_snapshot={
                'changedRevisionIds':[self.revision.pk],'requestHash':digest(body)})
        identity=ExternalIdentity.objects.create(organization_id=self.company.pk,source_system='FIXTURE',
            source_type='FIXTURE_DESIGN',source_object_type='ProductDesignRevision',external_id='fixture-design',
            target_entity_type='ProductDesignRevision')
        self.design_request=MasterDataWriteRequest.objects.create(organization_id=self.company.pk,
            action_code=ACTION_DESIGN_SAVE,entity_type='ProductDesignRevision',idempotency_key='fixture-design',
            request_hash=digest(body),source_identity=identity,status='COMMITTED',audit_metadata=body,
            result={'changedRevisionIds':[self.revision.pk],'auditId':audit.pk})
        facts=product_version_management_facts(self.company.pk,order_no=self.order.order_no,user=self.actor)
        facts,_=save_order_engineering_baseline_draft(user=self.actor,idempotency_key='fixture-baseline-draft',
            payload={'orderNo':self.order.order_no,'reason':'隔离新版本基线',
                'candidateId':facts['candidateBaseline']['candidateId']})
        baseline=facts['selectedBaseline'];self.new_baseline_id=baseline['baselineId']
        confirm_order_engineering_baseline(user=self.actor,idempotency_key='fixture-baseline-confirm',
            payload={'baselineId':self.new_baseline_id,'expectedVersion':baseline['version'],'reason':'隔离确认'})
        self.adapter=patch.object(native,'run_batch',side_effect=self.numeric_fixture)
        self.adapter.start();self.addCleanup(self.adapter.stop)

    def numeric_fixture(self,keys,*,design_inputs):
        return {'batchFingerprint':'isolated-numeric-adapter','inputRevisionHash':digest(design_inputs),
            'rows':[{'sourceKey':key,'column':'fixture_quantity','project':'fixture quantity',
                'state':'calculated','resultScope':'approved-source-net','value':'2','unit':self.uom.code,
                'matched':True,'inputs':[],'expression':'FIXTURE'} for key in keys]}

    def args(self,**changes):
        result={'user':self.actor,'sales_order_item_id':self.items[0].pk,
            'engineering_instance_id':self.instances[0].pk,'baseline_id':self.new_baseline_id,
            'previous_calculation_id':self.calculations[0].pk}
        result.update(changes);return result

    def execute(self,preview=None,**changes):
        preview=preview or Service.preview(**self.args())
        result={**self.args(),'expected_context_hash':preview['expectedContextHash'],
            'continuation_basis_hash':preview['continuationBasisHash'],
            'idempotency_key':'isolated-main-version-1','reason':'隔离验证正式主核算接续'}
        result.update(changes);return Service.execute(**result)

    def counts(self):
        return [m.objects.count() for m in (EngineeringCalculationContinuation,EngineeringCalculationRecord,
            EngineeringCalculationDetail,EngineeringDerivedFact,MasterDataWriteRequest,ExternalIdentity,
            OrganizationOperatingAuditRecord,BusinessStateTransition)]+[CodeRule.objects.get(
                company_id=self.company.pk,entity_type='production_engineering_calculation').current_seq]

    def error(self,code,call):
        with self.assertRaises((EngineeringCalculationError,LegacyInFlightOrderAdoptionError)) as caught:call()
        self.assertEqual(caught.exception.code,code)

    def test_01_preview_is_read_only_and_exact(self):
        before=self.counts();candidate=Service.preview(**self.args())
        self.assertTrue(candidate['ready']);self.assertEqual(before,self.counts())
        self.assertEqual(candidate['newScope']['baselineReference']['id'],self.new_baseline_id)
        self.assertEqual(len(candidate['continuationBasis']['designRevisions']),1)

    def test_02_native_main_commit_preserves_old_and_admits_both_fixed_versions(self):
        old=_protected_snapshot(self.adoption);result=self.execute()
        row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        self.assertEqual(old,_protected_snapshot(self.adoption,upper=old))
        self.assertEqual(continuation_proof(row)['newCalculationId'],result['newCalculationId'])
        for calc_id in (self.calculations[0].pk,result['newCalculationId']):
            authority=require_active_legacy_adoption(order=self.order,calculation_id=calc_id)
            self.assertEqual(authority.as_dict()['scope']['engineeringCalculationIds'],[c.pk for c in self.calculations])
        self.assertEqual(self.frozen_adoption,normal(LegacyInFlightOrderAdoption.objects.values().get(pk=self.adoption_id)))
        self.assertEqual(row.new_calculation.supersedes_id,self.calculations[0].pk)
        self.assertEqual(row.new_calculation.status,'completed');self.assertEqual(row.previous_calculation.status,'completed')

    def test_03_replay_is_zero_write_and_conflict_rejected(self):
        preview=Service.preview(**self.args());first=self.execute(preview);before=self.counts()
        repeated=self.execute(preview)
        self.assertTrue(repeated['idempotent']);self.assertEqual(repeated['newCalculationId'],first['newCalculationId'])
        self.assertEqual(before,self.counts())
        self.error('IDEMPOTENCY_CONFLICT',lambda:self.execute(preview,reason='changed payload'))

    def test_04_wrong_line_or_instance_is_rejected(self):
        self.error('FORMAL_CONTEXT_MISMATCH',lambda:Service.preview(**self.args(sales_order_item_id=self.items[1].pk)))

    def test_05_cross_company_is_rejected(self):
        other=Company.objects.create(code='OTHER-CONT',name='other')
        self.actor.company_id=other.pk
        UserRoleScopeAssignment.objects.create(user=self.actor,role=self.role,organization=other,
            scope_code='ORGANIZATION',active=True,version=1,business_hash='isolated cross company')
        self.error('FORMAL_CONTEXT_MISMATCH',lambda:Service.preview(**self.args()))

    def test_06_unconfirmed_baseline_is_rejected(self):
        OrderEngineeringBaseline.objects.filter(pk=self.new_baseline_id).update(status='draft')
        self.error('CONFIRMED_BASELINE_REQUIRED',lambda:Service.preview(**self.args()))

    def test_07_wrong_predecessor_is_rejected(self):
        self.error('CONTINUATION_PREVIOUS_SCOPE_INVALID',lambda:Service.preview(**self.args(previous_calculation_id=self.calculations[1].pk)))

    def test_08_missing_revision_authority_is_rejected(self):
        MasterDataWriteRequest.objects.filter(pk=self.design_request.pk).update(status='RESERVED')
        self.error('CONTINUATION_REVISION_AUTHORITY_REQUIRED',lambda:Service.preview(**self.args()))

    def test_09_stale_basis_has_no_effect(self):
        preview=Service.preview(**self.args());before=self.counts()
        self.error('CONTINUATION_CANDIDATE_STALE',lambda:self.execute(preview,expected_context_hash='0'*64))
        self.assertEqual(before,self.counts())

    def test_10_failure_after_native_main_rolls_back_everything(self):
        preview=Service.preview(**self.args());before=self.counts();original=native.FormalEngineeringContinuationService.execute
        def after_native(**kwargs):original(**kwargs);raise RuntimeError('isolated post-native injected failure')
        with patch.object(native.FormalEngineeringContinuationService,'execute',side_effect=after_native):
            with self.assertRaisesRegex(RuntimeError,'post-native'):self.execute(preview)
        self.assertEqual(before,self.counts());self.assertFalse(EngineeringCalculationContinuation.objects.exists())

    def test_11_legacy_data_tamper_is_rejected(self):
        fact=self.calculations[0].derived_facts.get()
        EngineeringDerivedFact.objects.filter(pk=fact.pk).update(value={'decimal':'9'})
        self.error('CONTINUATION_PREVIOUS_FACT_CHANGED',lambda:Service.preview(**self.args()))

    def test_12_unit_mutation_cannot_self_certify(self):
        other=UnitOfMeasure.objects.create(company_id=self.company.pk,code='OTHER-UOM',name='other',dimension='count')
        self.calculations[0].derived_facts.update(uom=other);self.calculations[0].details.update(uom=other)
        self.error('CONTINUATION_PREVIOUS_UNIT_CHANGED',lambda:Service.preview(**self.args()))

    def test_13_missing_initialization_audit_rejects_commit_proof(self):
        result=self.execute();row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        OrganizationOperatingAuditRecord.objects.filter(pk=result['initializationAuditId']).update(action_code='wrong')
        self.error('CONTINUATION_INITIALIZATION_UNPROVEN',lambda:continuation_proof(row))

    def test_14_missing_native_completed_state_rejects_proof(self):
        result=self.execute();row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',object_id=row.new_calculation_id).update(action_code='wrong')
        self.error('CONTINUATION_NATIVE_MAIN_UNPROVEN',lambda:continuation_proof(row))

    def test_15_native_guard_has_no_unbound_bypass(self):
        before=self.counts()
        self.error('LEGACY_MAIN_CALCULATION_CONTINUATION_REQUIRED',lambda:native.FormalEngineeringContinuationService.execute(
            **{k:v for k,v in self.args().items() if k!='previous_calculation_id'},reason='unbound'))
        self.assertEqual(before,self.counts())

    def test_16_scope_frozen_does_not_admit_arbitrary_new_main(self):
        original=self.calculations[0]
        EngineeringCalculationRecord.objects.create(company=self.company,scope='order_engineering',source_record=self.source,
            sales_order_item=self.items[0],engineering_instance=self.instances[0],calculation_no='UNBOUND-FIXTURE',
            revision=2,supersedes=original,status='completed')
        self.error('PDE_LEGACY_IN_FLIGHT_CALCULATION_SCOPE_DRIFT',lambda:require_active_legacy_adoption(order=self.order))

    def test_17_api_preview_execute_true_native_service(self):
        client=APIClient();client.force_authenticate(self.actor)
        body={'salesOrderItemId':self.items[0].pk,'orderEngineeringInstanceId':self.instances[0].pk,
            'orderEngineeringBaselineId':self.new_baseline_id,'predecessorCalculationId':self.calculations[0].pk}
        root='/api/pde/a1-engineering/calculations/version-continuation/'
        before=client.get('/api/pde/a1-engineering/calculations/formal-continuation/',{'orderNo':self.order.order_no})
        self.assertEqual(before.status_code,200,before.data)
        response=client.post(root+'preview/',body,format='json');self.assertEqual(response.status_code,200,response.data)
        preview_response=normal(response.data)
        self.assertEqual([a['actionCode'] for a in response.data['availableActions']],['preview','execute'])
        body.update(expectedContextHash=response.data['expectedContextHash'],continuationBasisHash=response.data['continuationBasisHash'],
            idempotencyKey='api-fixture-main-1',reason='isolated API native execution')
        response=client.post(root+'execute/',body,format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['continuation']['newCalculationId'],response.data['calculation']['id'])
        after=client.get('/api/pde/a1-engineering/calculations/formal-continuation/',{'orderNo':self.order.order_no})
        self.assertEqual(after.status_code,200,after.data)
        line=next(row for row in after.data['lines'] if row['salesOrderItemId']==self.items[0].pk)
        self.assertEqual(line['calculationContinuation']['records'][0]['newCalculationId'],response.data['calculation']['id'])
        CONTRACT_READBACK.update(boundary='ISOLATED SYNTHETIC CAPABILITY ONLY; numeric adapter fixture, no formal source proof',
            factsBefore=normal(before.data),preview=preview_response,execute=normal(response.data),factsAfter=normal(after.data))

    def test_18_missing_workbook_fails_closed_no_new_authority(self):
        before=self.counts()
        with patch.object(native,'run_batch',side_effect=FileNotFoundError('isolated missing registered workbook')):
            self.error('CONTINUATION_SOURCE_READ_FAILED',lambda:Service.preview(**self.args()))
        self.assertEqual(before,self.counts())

    def test_19_missing_required_strings_rejected(self):
        for key in ('reason','idempotency_key'):
            self.error('CONTINUATION_INPUT_REQUIRED',lambda:self.execute(**{key:None}))

    def test_20_request_target_is_part_of_formal_proof(self):
        result=self.execute();row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        MasterDataWriteRequest.objects.filter(pk=row.write_request_id).update(target_entity_id='wrong')
        self.error('CONTINUATION_COMMIT_UNPROVEN',lambda:continuation_proof(row))

    def test_21_source_errors_are_typed_api_read_failures(self):
        client=APIClient();client.force_authenticate(self.actor)
        body={'salesOrderItemId':self.items[0].pk,'orderEngineeringInstanceId':self.instances[0].pk,
            'orderEngineeringBaselineId':self.new_baseline_id,'predecessorCalculationId':self.calculations[0].pk}
        before=self.counts()
        for error in (OSError('fixture source unavailable'),ValueError('fixture source hash mismatch')):
            with patch.object(native,'run_batch',side_effect=error):
                response=client.post('/api/pde/a1-engineering/calculations/version-continuation/preview/',body,format='json')
            self.assertEqual(response.status_code,503,response.data)
            self.assertEqual(response.data['code'],'CONTINUATION_SOURCE_READ_FAILED')
            self.assertNotEqual(response.data.get('readStatus'),'loaded')
        self.assertEqual(before,self.counts())

    def test_22_permission_denied_has_no_writes(self):
        RolePermission.objects.filter(role=self.role,permission__code='production.engineering.calculation.execute').delete()
        preview=Service.preview(**self.args());before=self.counts()
        self.assertFalse(next(a for a in preview['availableActions'] if a['actionCode']=='execute')['allowed'])
        self.error('PERMISSION_DENIED',lambda:self.execute(preview));self.assertEqual(before,self.counts())

    def test_23_current_actor_chain_is_required(self):
        PositionResponsibility.objects.filter(position=self.position).update(active=False)
        preview=Service.preview(**self.args());before=self.counts()
        self.assertFalse(next(a for a in preview['availableActions'] if a['actionCode']=='execute')['allowed'])
        self.error('FORMAL_EXECUTION_CHAIN_REQUIRED',lambda:self.execute(preview));self.assertEqual(before,self.counts())

    def test_24_baseline_confirm_ledger_is_required(self):
        from .product_version_management_service import CONFIRM_ACTION
        MasterDataWriteRequest.objects.filter(action_code=CONFIRM_ACTION,result__baselineId=self.new_baseline_id).update(status='RESERVED')
        self.error('CONTINUATION_BASELINE_AUTHORITY_REQUIRED',lambda:Service.preview(**self.args()))

    def test_25_existing_old_consumption_changed_inside_native_rolls_back(self):
        preview=Service.preview(**self.args());before=self.counts();original=native.FormalEngineeringContinuationService.execute
        old=list(EngineeringCalculationRecord.objects.values().order_by('pk'))
        def mutated(**kwargs):
            result=original(**kwargs)
            EngineeringCalculationRecord.objects.filter(pk=self.calculations[1].pk).update(result_hash='9'*64)
            return result
        with patch.object(native.FormalEngineeringContinuationService,'execute',side_effect=mutated):
            self.error('CONTINUATION_PRESERVATION_FAILED',lambda:self.execute(preview))
        self.assertEqual(before,self.counts());self.assertEqual(old,list(EngineeringCalculationRecord.objects.values().order_by('pk')))

    def test_26_scope_hash_tamper_returns_domain_error_through_old_admission(self):
        result=self.execute();row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        # Deliberate raw corruption fixture bypasses append-only model protection.
        with connection.cursor() as cursor:
            cursor.execute('UPDATE pde_engineering_calculation_continuation SET context_hash=%s WHERE id=%s',['x'*64,row.pk])
        self.error('CONTINUATION_SCOPE_UNPROVEN',lambda:require_active_legacy_adoption(order=self.order))

    def test_27_admission_does_not_rescan_whole_order_and_still_checks_predecessor(self):
        result=self.execute();row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        with patch('pde.engineering_calculation_continuation_service._protected_snapshot',side_effect=AssertionError('whole-order scan forbidden on admission')):
            authority=require_active_legacy_adoption(order=self.order,calculation_id=row.new_calculation_id)
            self.assertEqual(authority.calculation_continuations[0]['continuationId'],row.pk)
            EngineeringDerivedFact.objects.filter(calculation=self.calculations[0]).update(value={'decimal':'99'})
            self.error('CONTINUATION_PREVIOUS_FACT_CHANGED',lambda:require_active_legacy_adoption(order=self.order))
