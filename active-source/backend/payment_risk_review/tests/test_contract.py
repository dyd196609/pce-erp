from inspect import signature

from django.test import SimpleTestCase

from payment_risk_review.services import (
    CANONICAL_NAME,
    RULES,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    ensure_review_for_source,
)


class PaymentRiskReviewContractTests(SimpleTestCase):
    def test_v52_contract_is_server_owned_and_complete(self):
        self.assertEqual(VERSION, "V1.14.2.8.4.7.52")
        self.assertEqual(CANONICAL_NAME, "真实付款风险评审")
        self.assertEqual(SOURCE_DOCUMENT_TYPE, "paymentOrderDraft")
        self.assertGreater(len(RULES), 0)
        self.assertEqual(len(RULES), len({row[0] for row in RULES}))
        self.assertTrue(all(row[0].startswith("PRR_") for row in RULES))

    def test_scenario_code_is_a_required_server_argument(self):
        parameter = signature(ensure_review_for_source).parameters["scenario_code"]
        self.assertTrue(parameter.kind.name.startswith("KEYWORD"))
        self.assertTrue(parameter.default is parameter.empty)
