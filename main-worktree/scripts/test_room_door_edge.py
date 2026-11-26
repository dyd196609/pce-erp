"""Scoped isolated non-regression and explicit simulated loss boundaries."""
import copy
import json
import sys
import unittest
from decimal import Decimal as D
from room_door_edge import ROOT,OUT,OLD,ISO,bootstrap,read,save
bootstrap()
# Reuse prior tests against the NEW isolated database; do not run its entrypoint or write its evidence.
import semi_finished_role_layer as previous_context
previous_context.bootstrap=lambda *a,**k:ISO/'isolated.sqlite3'
import test_semi_finished_role_layer as legacy
from django.core.exceptions import ValidationError
from django.db import transaction,IntegrityError
from pde.models import ComponentMaterialRequirement as Requirement,MaterialLossPolicy
from pde.material_loss_policy_service import MaterialLossPolicyService as Loss
from pde.material_configuration_service import MaterialConfigurationService

class FrozenModelTests(legacy.Tests):
    def test_requirement_owner_is_component(self):
        self.assertEqual(Requirement.objects.filter(component=None,breakdown_item__isnull=False).count(),75)
        self.assertEqual(Requirement.objects.filter(requirement_source_mode='STRUCTURE_CALCULATED').count(),59)

class LossTests(unittest.TestCase):
    def seg(self,*lengths,qty=1):return [{'netSegmentLengthMm':str(v),'quantityMultiplier':qty} for v in lengths]
    def test_zero_edges_zero_allowance(self):self.assertEqual(Loss.per_edge_preview(0,[],0)['grossLengthM'],'0')
    def test_zero_edges_missing_not_zero(self):self.assertIsNone(Loss.per_edge_preview(0,[],None)['grossLengthM'])
    def test_one_edge_20(self):self.assertEqual(D(Loss.per_edge_preview(1,self.seg(1000),20)['grossLengthM']),D('1.02'))
    def test_different_lengths_multiple_quantity(self):self.assertEqual(D(Loss.per_edge_preview('3.6',self.seg(1000,800,qty=2),20)['grossLengthM']),D('3.68'))
    def test_explicit_zero_parameter(self):self.assertEqual(D(Loss.per_edge_preview(1,self.seg(1000),0)['grossLengthM']),1)
    def test_missing_parameter(self):self.assertIsNone(Loss.per_edge_preview(1,self.seg(1000),None)['grossLengthM'])
    def test_missing_segments(self):self.assertEqual(Loss.per_edge_preview(1,None,20)['status'],'BLOCKED_NET_OR_SEGMENTS')
    def test_missing_net(self):self.assertIsNone(Loss.per_edge_preview(None,[],20)['grossLengthM'])
    def test_negative_parameter(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(1,self.seg(1000),-1)
    def test_negative_length(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(1,self.seg(-1000),20)
    def test_fractional_edges(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(1,self.seg(2000,qty=.5),20)
    def test_boolean_rejected(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(1,self.seg(1000),False)
    def test_nan_rejected(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(1,self.seg(1000),'NaN')
    def test_net_mismatch_blocks_before_loss(self):
        with self.assertRaises(ValidationError):Loss.per_edge_preview(2,self.seg(1000),20)
    def test_16_source_results_with_simulated_0_and_20(self):
        tests=[]
        for edge in read('ROOM_DOOR_EDGE_SEGMENT_TRACE.json')['rows']:
            for allowance in (0,20):
                result=Loss.per_edge_preview(edge['netLengthM'],edge['segments'],allowance)
                self.assertEqual(D(result['grossLengthM']),D(edge['netLengthM'])+D(edge['edgeCount'])*allowance/1000)
                tests.append({'sourceRow':edge['row'],'sourceType':edge['sourceType'],'provenance':'SIMULATED_FOR_TEST',
                    'allowanceMm':allowance,'result':result,'realParameterWrite':0})
        save('SIMULATED_LOSS_BOUNDARIES.json',tests)

class ConstraintTests(unittest.TestCase):
    def setUp(self):
        self.tx=transaction.atomic();self.tx.__enter__()
        self.req=Requirement.objects.filter(requirement_source_mode='DIRECT_CALCULATED').first()
    def tearDown(self):transaction.set_rollback(True);self.tx.__exit__(None,None,None)
    def invalid(self,**fields):
        for k,v in fields.items():setattr(self.req,k,v)
        with self.assertRaises(ValidationError):self.req.full_clean()
    def test_direct_mode_does_not_need_edge_mode(self):
        self.assertIsNone(self.req.breakdown_item.attributes['edgePreview'])
        self.assertEqual(MaterialConfigurationService.component_edge_preview(self.req)['requirementSourceMode'],'DIRECT_CALCULATED')
    def test_unresolved_material_keeps_net(self):
        self.assertIsNone(self.req.material_id);self.assertGreater(self.req.net_quantity,0)
    def test_true_zero_net_preserved(self):self.assertEqual(Requirement.objects.filter(requirement_source_mode='DIRECT_CALCULATED',net_quantity=0).count(),3)
    def test_source_modes(self):
        for mode in ('STRUCTURE_CALCULATED','DIRECT_CALCULATED','FIXED','MANUAL_ENGINEERING','AD_HOC','CUSTOMER_SPECIFIC'):
            self.req.requirement_source_mode=mode;self.req.full_clean()
    def test_bad_source_mode(self):self.invalid(requirement_source_mode='DOOR_V2')
    def test_bad_net(self):self.invalid(net_quantity=-1)
    def test_gross_cannot_copy_net(self):self.invalid(gross_quantity=self.req.net_quantity,total_allowance=0)
    def test_zero_gross_not_unknown(self):self.invalid(gross_quantity=0,total_allowance=0)
    def test_unknown_trace_not_empty_list(self):self.invalid(edge_trace_status='UNKNOWN',edge_segment_trace=[])
    def test_unknown_trace_null(self):self.req.edge_trace_status='UNKNOWN';self.req.edge_segment_trace=None;self.req.full_clean()
    def test_bad_unit(self):self.req.uom.code='m2';self.invalid()
    def test_25_50_parameter_not_same_identity(self):
        self.req.loss_policy=MaterialLossPolicy.objects.get(source_material_identity='EDGE_BANDING_50_SOURCE');self.invalid()
    def test_trace_sum_integrity(self):self.invalid(edge_segment_trace=[])
    def test_db_gross_guard(self):
        with self.assertRaises(IntegrityError),transaction.atomic():Requirement.objects.filter(pk=self.req.pk).update(gross_quantity=self.req.net_quantity,total_allowance=0)
    def test_db_net_guard(self):
        with self.assertRaises(IntegrityError),transaction.atomic():Requirement.objects.filter(pk=self.req.pk).update(net_quantity=-1)
    def test_policy_negative(self):
        p=self.req.loss_policy;p.suggested_allowance_mm=-1
        with self.assertRaises(ValidationError):p.full_clean()
    def test_policy_cannot_default_zero(self):
        p=self.req.loss_policy;p.allowance_mm=0
        with self.assertRaises(ValidationError):p.full_clean()
    def test_policy_confirm_requires_user_decision(self):
        p=self.req.loss_policy;p.allowance_mm=20;p.parameter_status='CONFIRMED'
        with self.assertRaises(ValidationError):p.full_clean()
    def test_all_real_parameters_null(self):self.assertEqual(MaterialLossPolicy.objects.exclude(allowance_mm=None).count(),0)

suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (FrozenModelTests,LossTests,ConstraintTests))
result=unittest.TextTestRunner(verbosity=1).run(suite)
save('ISOLATED_TEST_RESULTS.json',{'testsRun':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'status':'PASS' if result.wasSuccessful() else 'FAIL','simulatedLossParametersOnly':True,'productionBusinessWrite':0})
assert result.wasSuccessful()
