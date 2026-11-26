from types import SimpleNamespace

from django.test import SimpleTestCase

from formal_payment_order.services import (
    ALLOWED_STATE_TRANSITIONS,
    APPROVAL_ROLES,
    CANONICAL_NAME,
    PROCESS_DEFINITION_CODE,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    source_gate,
)
from formal_payment_order.models import (
    FormalPaymentOrder,
    FormalPaymentOrderFreezeSnapshot,
)
from formal_payment_order.facts import EXPECTED_STATE_TRANSITIONS
from workflow_runtime.facts import (
    StateTransitionFactError,
    assert_status_transition_count_matches_history,
    status_transition_facts,
)


def valid_source():
    return SimpleNamespace(
        pk=1,
        status="passed",
        risk_result="passed",
        risk_level="low",
        version=2,
        review_version=3,
    )


def valid_authority():
    return {
        "source": {
            "version": 2,
            "reviewVersion": 3,
            "ruleVersion": "payment-risk-review-rules-v1",
            "resultHash": "a" * 64,
            "eligibility": {
                "eligible": True,
                "nextStepReadiness": "ready_for_formal_payment_order",
            },
        },
        "evidence": {
            "funds": {"available": True},
            "bankInterface": {"available": True},
            "account": {"payer": {"active": True}, "payee": {"active": True}},
            "riskReview": {"status": "passed"},
            "segregation": {"valid": True},
        },
    }


class FormalPaymentOrderContractTests(SimpleTestCase):
    def test_identity_contract(self):
        self.assertEqual(VERSION, "V1.14.2.8.4.7.54.3")
        self.assertEqual(CANONICAL_NAME, "正式付款单")
        self.assertEqual(SOURCE_DOCUMENT_TYPE, "paymentRiskReview")

    def test_execution_gate_state_machine_contract(self):
        self.assertEqual(
            list(FormalPaymentOrder.Status.values),
            ["prepared", "submitted", "approved", "frozen_for_execution"],
        )
        self.assertEqual(PROCESS_DEFINITION_CODE, "FORMAL_PAYMENT_ORDER_APPROVAL")
        self.assertEqual(APPROVAL_ROLES, ("payment_checker", "payment_authorizer"))
        self.assertEqual(
            ALLOWED_STATE_TRANSITIONS,
            (
                ("prepared", "submitted"),
                ("submitted", "approved"),
                ("approved", "frozen_for_execution"),
            ),
        )
        self.assertEqual(
            EXPECTED_STATE_TRANSITIONS["frozen_for_execution"],
            (
                ("prepared", "submitted", "submit-formal-payment-order"),
                ("submitted", "approved", "approve-formal-payment-order"),
                (
                    "approved",
                    "frozen_for_execution",
                    "freeze-formal-payment-order",
                ),
            ),
        )
        self.assertEqual(
            FormalPaymentOrderFreezeSnapshot._meta.db_table,
            "formal_payment_order_freezes",
        )

    def test_transition_fact_contract_is_audit_complete(self):
        from workflow_runtime.models import BusinessStateTransition

        field_names = {
            field.name for field in BusinessStateTransition._meta.get_fields()
        }
        self.assertTrue(
            {
                "object_type",
                "object_id",
                "source_state",
                "target_state",
                "operator",
                "timestamp",
                "reason",
                "version",
                "audit_reference",
            }.issubset(field_names)
        )

    def test_transition_count_is_server_derived_and_matches_history(self):
        history = [
            {"sourceState": "prepared", "targetState": "submitted"},
            {"sourceState": "submitted", "targetState": "approved"},
            {"sourceState": "approved", "targetState": "frozen_for_execution"},
        ]
        payload = status_transition_facts(
            history=history,
            state_machine_consistent=True,
        )
        self.assertEqual(payload["statusTransitionCount"], 3)
        self.assertEqual(payload["statusTransitionHistory"], history)
        self.assertTrue(payload["stateMachineConsistent"])
        self.assertIs(
            assert_status_transition_count_matches_history(payload),
            payload,
        )

    def test_transition_count_mismatch_is_rejected(self):
        with self.assertRaises(StateTransitionFactError):
            assert_status_transition_count_matches_history({
                "statusTransitionHistory": [{}, {}, {}],
                "statusTransitionCount": 0,
            })

    def test_valid_source_passes_server_gate(self):
        self.assertEqual(source_gate(valid_source(), valid_authority(), check_existing=False), [])

    def test_source_and_evidence_failures_are_blocked(self):
        scenarios = {
            "RISK_NOT_PASSED": ("status", "blocked"),
            "RISK_RESULT_NOT_PASSED": ("risk_result", "blocked"),
            "RISK_LEVEL_NOT_LOW": ("risk_level", "high"),
        }
        for expected, (field, value) in scenarios.items():
            source = valid_source()
            setattr(source, field, value)
            self.assertIn(expected, source_gate(source, valid_authority(), check_existing=False))
        evidence_fields = {
            "FUNDS_EVIDENCE_MISSING": "funds",
            "BANK_INTERFACE_EVIDENCE_MISSING": "bankInterface",
            "RISK_REVIEW_EVIDENCE_MISSING": "riskReview",
            "SEGREGATION_EVIDENCE_MISSING": "segregation",
        }
        for expected, field in evidence_fields.items():
            authority = valid_authority()
            authority["evidence"][field] = {}
            self.assertIn(expected, source_gate(valid_source(), authority, check_existing=False))

    def test_client_eligibility_cannot_override_server_source(self):
        authority = valid_authority()
        authority["source"]["eligibility"] = {
            "eligible": False,
            "nextStepReadiness": "blocked",
        }
        reasons = source_gate(valid_source(), authority, check_existing=False)
        self.assertIn("SOURCE_NOT_ELIGIBLE", reasons)
        self.assertIn("READINESS_NOT_RELEASED", reasons)
