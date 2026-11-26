import copy
import unittest
from unittest.mock import patch
from django.test import override_settings
from . import oei_calculated_transition_repair_service as repair
from .engineering_calculation_service import EngineeringCalculationError


class OEIRepairEvidenceTests(unittest.TestCase):
    """Run on an explicitly selected permanent-readonly verification copy."""
    @classmethod
    def setUpClass(cls):
        from system.models import User
        cls.actor=User.objects.defer('password').get(pk=10)

    def inspect(self):
        return repair.inspect_calculated_transition(user=self.actor,source_audit_id=11749,calculation_id=1334)

    def error(self,code,fn):
        with self.assertRaises(EngineeringCalculationError) as caught:fn()
        self.assertEqual(caught.exception.code,code)

    def test_repeated_evidence_read_has_same_proof_and_existing_fact(self):
        first=self.inspect();self.assertEqual(first,self.inspect());self.assertIsNotNone(first['existingTransitionId'])

    def test_disabled_pin_refuses_before_business_read(self):
        with override_settings(PCE_OEI_CALCULATED_TRANSITION_REPAIR={}):
            self.error('OEI_REPAIR_COPY_PIN_REQUIRED',self.inspect)

    def test_wrong_audit_or_calculation_outside_pin_refused(self):
        for args in ((11748,1334),(11749,1333)):
            with self.subTest(args=args):
                self.error('OEI_REPAIR_COPY_PIN_MISMATCH',lambda:repair.inspect_calculated_transition(
                    user=self.actor,source_audit_id=args[0],calculation_id=args[1]))

    def test_changed_evidence_hash_refuses_without_writes(self):
        self.error('OEI_REPAIR_EVIDENCE_CHANGED',lambda:repair.repair_calculated_transition(user=self.actor,
            source_audit_id=11749,calculation_id=1334,expected_evidence_hash='0'*64,reason='negative test'))

    def test_cross_company_even_with_stubbed_permission_is_refused(self):
        actor=copy.copy(self.actor);actor.company_id=2
        with patch.object(repair.EngineeringCalculationService,'_authorize',return_value={'allowed':True}):
            self.error('OEI_REPAIR_SCOPE_MISMATCH',lambda:repair.inspect_calculated_transition(
                user=actor,source_audit_id=11749,calculation_id=1334))

    def test_missing_original_authorization_not_inferred(self):
        from system.models import OrganizationOperatingAuditRecord
        original_filter=OrganizationOperatingAuditRecord.objects.filter
        audit=copy.copy(original_filter(pk=11749).get())
        audit.before_snapshot=copy.deepcopy(audit.before_snapshot)
        audit.before_snapshot['authorization']['allowed']=False
        class Query:
            def first(self):return audit
        def read(*args,**kwargs):return Query() if kwargs=={'pk':11749} else original_filter(*args,**kwargs)
        with patch.object(OrganizationOperatingAuditRecord.objects,'filter',side_effect=read):
            self.error('OEI_REPAIR_ORIGINAL_AUTHORIZATION_UNPROVEN',self.inspect)

    def test_state_fact_projection_uses_persisted_history(self):
        from .models import OrderEngineeringInstance
        fact=repair.calculated_state_facts(instance=OrderEngineeringInstance.objects.get(pk=7),company_id=1)
        self.assertTrue(fact['stateMachineConsistent'])
        self.assertEqual(fact['statusTransitionCount'],len(fact['statusTransitionHistory']))
        self.assertEqual(fact['statusTransitionHistory'][-1]['target_state'],'calculated')
