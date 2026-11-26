from django.test import SimpleTestCase, override_settings

from workflow_runtime.fact_loads import (
    FACT_LOAD_CONTRACT_VERSION,
    FactLoadContractError,
    failed_fact_load_facts,
    successful_fact_load_facts,
)


@override_settings(
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
)
class FactLoadContractV5813Tests(SimpleTestCase):
    def test_success_with_rows_is_loaded(self):
        facts = successful_fact_load_facts(
            result_count=8,
            api_url="/api/finance/bank-send-prepares/",
        )
        self.assertEqual(
            facts["factLoadContractVersion"],
            FACT_LOAD_CONTRACT_VERSION,
        )
        self.assertEqual(facts["factLoadStatus"], "loaded")
        self.assertEqual(facts["httpStatus"], 200)
        self.assertEqual(facts["tenantId"], "tenant-canary-demo")
        self.assertEqual(facts["batchId"], "PURCHASE-FLOW-DEMO-V1")
        self.assertEqual(facts["errorCode"], "")
        self.assertEqual(facts["errorMessage"], "")

    def test_success_without_rows_is_empty_valid(self):
        facts = successful_fact_load_facts(
            result_count=0,
            api_url="/api/finance/bank-send-prepares/",
        )
        self.assertEqual(facts["factLoadStatus"], "empty_valid")
        self.assertEqual(facts["httpStatus"], 200)

    def test_read_failure_preserves_http_and_error(self):
        facts = failed_fact_load_facts(
            api_url="/api/finance/bank-send-preparations/",
            http_status=404,
            error_code="API_NOT_FOUND",
            error_message="API route not found",
        )
        self.assertEqual(facts["factLoadStatus"], "read_failed")
        self.assertEqual(facts["httpStatus"], 404)
        self.assertEqual(facts["errorCode"], "API_NOT_FOUND")
        self.assertEqual(facts["errorMessage"], "API route not found")

    def test_read_failure_cannot_omit_error_code(self):
        with self.assertRaises(FactLoadContractError):
            failed_fact_load_facts(
                api_url="/api/finance/bank-send-preparations/",
                http_status=404,
                error_code="",
                error_message="API route not found",
            )
