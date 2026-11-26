import json

from django.test import RequestFactory, SimpleTestCase, override_settings

from workflow_runtime.exception_handler import (
    pce_not_found_handler,
    pce_server_error_handler,
)
from workflow_runtime.fact_loads import (
    FACT_LOAD_CONTRACT_VERSION,
    FACT_LOAD_CONTEXT_UNAVAILABLE,
    FactLoadContractError,
    build_fact_load_facts,
    failed_fact_load_facts,
)


API_URL = "/api/finance/bank-send-tasks/"
TENANT_ID = "tenant-canary-demo"
BATCH_ID = "PURCHASE-FLOW-DEMO-V1"


@override_settings(
    PCE_CANARY_TENANT_ID=TENANT_ID,
    PCE_CANARY_BATCH_ID=BATCH_ID,
)
class BankSendTaskFactLoadContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def success(self, **overrides):
        values = {
            "fact_load_status": "success",
            "api_url": API_URL,
            "http_status": 200,
            "tenant_id": TENANT_ID,
            "batch_id": BATCH_ID,
        }
        values.update(overrides)
        return build_fact_load_facts(**values)

    def test_01_success_status_is_supported(self):
        self.assertEqual(self.success()["factLoadStatus"], "success")

    def test_02_contract_version_is_v1(self):
        self.assertEqual(
            self.success()["factLoadContractVersion"],
            FACT_LOAD_CONTRACT_VERSION,
        )

    def test_03_api_url_is_complete(self):
        self.assertEqual(self.success()["apiUrl"], API_URL)

    def test_04_http_status_is_complete(self):
        self.assertEqual(self.success()["httpStatus"], 200)

    def test_05_loaded_at_is_non_empty(self):
        self.assertTrue(self.success()["loadedAt"])

    def test_06_tenant_is_server_context(self):
        self.assertEqual(self.success()["tenantId"], TENANT_ID)

    def test_07_batch_is_server_context(self):
        self.assertEqual(self.success()["batchId"], BATCH_ID)

    def test_08_missing_tenant_never_becomes_empty(self):
        with override_settings(PCE_CANARY_TENANT_ID=""):
            facts = self.success(tenant_id="")
        self.assertEqual(
            facts["tenantId"],
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        )

    def test_09_missing_batch_never_becomes_empty(self):
        with override_settings(PCE_CANARY_BATCH_ID=""):
            facts = self.success(batch_id="")
        self.assertEqual(
            facts["batchId"],
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        )

    def test_10_404_is_read_failed(self):
        facts = failed_fact_load_facts(
            api_url=API_URL,
            http_status=404,
            error_code="API_NOT_FOUND",
            error_message="not found",
            tenant_id=TENANT_ID,
            batch_id=BATCH_ID,
        )
        self.assertEqual(facts["factLoadStatus"], "read_failed")
        self.assertEqual(facts["httpStatus"], 404)

    def test_11_500_is_read_failed(self):
        facts = failed_fact_load_facts(
            api_url=API_URL,
            http_status=500,
            error_code="INTERNAL_SERVER_ERROR",
            error_message="server failed",
            tenant_id=TENANT_ID,
            batch_id=BATCH_ID,
        )
        self.assertEqual(facts["factLoadStatus"], "read_failed")
        self.assertEqual(facts["httpStatus"], 500)

    def test_12_read_failed_requires_error_code(self):
        with self.assertRaises(FactLoadContractError):
            failed_fact_load_facts(
                api_url=API_URL,
                http_status=500,
                error_code="",
                error_message="server failed",
            )

    def test_13_read_failed_requires_error_message(self):
        with self.assertRaises(FactLoadContractError):
            failed_fact_load_facts(
                api_url=API_URL,
                http_status=500,
                error_code="INTERNAL_SERVER_ERROR",
                error_message="",
            )

    def test_14_success_cannot_carry_error_fields(self):
        with self.assertRaises(FactLoadContractError):
            self.success(error_code="SHOULD_NOT_EXIST")

    def test_15_empty_api_response_contract_is_rejected(self):
        with self.assertRaises(FactLoadContractError):
            self.success(api_url="")

    def test_16_unknown_status_is_rejected(self):
        with self.assertRaises(FactLoadContractError):
            self.success(fact_load_status="")

    def test_17_api_404_handler_returns_complete_contract(self):
        response = pce_not_found_handler(
            self.factory.get("/api/finance/missing/"),
            exception=None,
        )
        payload = json.loads(response.content)
        self.assertEqual(payload["factLoadStatus"], "read_failed")
        self.assertEqual(payload["httpStatus"], 404)
        self.assertTrue(payload["tenantId"])
        self.assertTrue(payload["batchId"])

    def test_18_api_500_handler_returns_complete_contract(self):
        response = pce_server_error_handler(
            self.factory.get(API_URL)
        )
        payload = json.loads(response.content)
        self.assertEqual(payload["factLoadStatus"], "read_failed")
        self.assertEqual(payload["httpStatus"], 500)
        self.assertTrue(payload["errorCode"])
        self.assertTrue(payload["errorMessage"])
