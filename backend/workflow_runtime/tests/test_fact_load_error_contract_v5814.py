from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from rest_framework.exceptions import APIException, NotFound

from workflow_runtime.exception_handler import pce_exception_handler
from workflow_runtime.fact_loads import (
    FACT_LOAD_CONTEXT_UNAVAILABLE,
    FACT_LOAD_ERROR_REQUIRED_FIELDS,
    FactLoadContractError,
    build_fact_load_facts,
    failed_fact_load_facts,
)


@override_settings(
    PCE_CANARY_TENANT_ID="tenant-canary-demo",
    PCE_CANARY_BATCH_ID="PURCHASE-FLOW-DEMO-V1",
)
class FactLoadErrorContractV5814Tests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def assert_complete_read_failure(self, facts):
        self.assertEqual(facts["factLoadStatus"], "read_failed")
        for field in FACT_LOAD_ERROR_REQUIRED_FIELDS:
            self.assertIn(field, facts)
            if field != "httpStatus":
                self.assertTrue(str(facts[field]).strip(), field)

    def test_request_context_is_preserved_on_read_failure(self):
        request = self.factory.get("/api/finance/bank-send-prepares/")
        request.pce_tenant_id = "tenant-request-context"
        request.pce_batch_id = "BATCH-REQUEST-CONTEXT"
        facts = failed_fact_load_facts(
            api_url=request.path,
            http_status=500,
            error_code="FACT_READ_FAILED",
            error_message="Read failed during server evaluation",
            request=request,
        )
        self.assert_complete_read_failure(facts)
        self.assertEqual(facts["tenantId"], "tenant-request-context")
        self.assertEqual(facts["batchId"], "BATCH-REQUEST-CONTEXT")

    def test_server_context_fallback_is_non_empty_and_auditable(self):
        with override_settings(
            PCE_CANARY_TENANT_ID="",
            PCE_CANARY_BATCH_ID="",
        ):
            facts = failed_fact_load_facts(
                api_url="/api/finance/bank-send-prepares/",
                http_status=500,
                error_code="FACT_READ_FAILED",
                error_message="Read failed before tenant resolution",
            )
        self.assert_complete_read_failure(facts)
        self.assertEqual(
            facts["tenantId"],
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        )
        self.assertEqual(
            facts["batchId"],
            FACT_LOAD_CONTEXT_UNAVAILABLE,
        )

    def test_read_failure_rejects_empty_audit_fields(self):
        for field in ("api_url", "error_code", "error_message"):
            values = {
                "api_url": "/api/finance/bank-send-prepares/",
                "http_status": 500,
                "error_code": "FACT_READ_FAILED",
                "error_message": "Server read failed",
            }
            values[field] = ""
            with self.subTest(field=field):
                with self.assertRaises(FactLoadContractError):
                    build_fact_load_facts(
                        fact_load_status="read_failed",
                        **values,
                    )

    def test_drf_404_and_500_are_complete_read_failed_facts(self):
        cases = (
            (NotFound("Missing facts"), 404),
            (APIException("Server facts unavailable"), 500),
        )
        for exception, expected_status in cases:
            request = self.factory.get(
                "/api/finance/bank-send-prepares/missing/"
            )
            with self.subTest(status=expected_status):
                response = pce_exception_handler(
                    exception,
                    {"request": request},
                )
                self.assertEqual(response.status_code, expected_status)
                self.assert_complete_read_failure(
                    response.data["factLoadFacts"]
                )
                self.assertEqual(
                    response.data["factLoadFacts"]["tenantId"],
                    "tenant-canary-demo",
                )
                self.assertEqual(
                    response.data["factLoadFacts"]["batchId"],
                    "PURCHASE-FLOW-DEMO-V1",
                )
                self.assertFalse(response.data.get("passed", False))

    @override_settings(
        DEBUG=False,
        ROOT_URLCONF="pce_backend.urls",
    )
    def test_unmatched_api_route_returns_complete_contract(self):
        response = Client().get(
            "/api/finance/bank-send-preparations/"
        )
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assert_complete_read_failure(payload["factLoadFacts"])
        self.assertEqual(
            payload["factLoadFacts"]["apiUrl"],
            "/api/finance/bank-send-preparations/",
        )
        self.assertEqual(
            payload["factLoadFacts"]["errorCode"],
            "API_NOT_FOUND",
        )

    @override_settings(
        DEBUG=True,
        ROOT_URLCONF="pce_backend.urls",
    )
    def test_unmatched_api_route_is_structured_when_debug_enabled(self):
        response = Client().get(
            "/api/finance/not-a-real-fact-route/"
        )
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assert_complete_read_failure(payload["factLoadFacts"])
        self.assertEqual(
            payload["factLoadFacts"]["errorCode"],
            "API_NOT_FOUND",
        )
