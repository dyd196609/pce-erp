from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from purchase_canary.operation_data import (
    CONTRACT_VERSION,
    ensure_payable_check_operation_pool,
    payable_check_operation_facts,
    payable_check_operation_rows,
)
from purchase_canary.views import CanaryOperationDataView
from workflow_runtime.action_permissions import BusinessObjectFactProvider


@override_settings(
    PCE_CANARY_OPERATION_DATA_ENABLED=True,
    PCE_CANARY_OPERATION_BATCH_ID="PCE-CANARY-OPERATION-DATA-V1-TEST",
    PCE_CANARY_OPERATION_LEGAL_ENTITY_ID="LEGAL-V45",
)
class CanaryOperationDataV571Tests(TestCase):
    def setUp(self):
        self.batch = ensure_payable_check_operation_pool()

    def test_payable_check_pool_has_eight_rows_per_state(self):
        rows = payable_check_operation_rows(self.batch)
        facts = payable_check_operation_facts(rows)
        self.assertEqual(len(rows), 16)
        self.assertEqual(facts["pendingCheckCount"], 8)
        self.assertEqual(facts["checkedCount"], 8)
        self.assertTrue(facts["mixedSelectionSupported"])
        self.assertTrue(facts["operationPoolConsistent"])
        required = {
            "moduleCode", "scenarioCode", "objectState",
            "availableActions", "expectedAction", "preservePurpose",
        }
        self.assertTrue(all(required.issubset(row) for row in rows))

    def test_api_and_strict_facts_share_the_same_rows(self):
        request = APIRequestFactory().get(
            "/api/pce/purchase-canary/operation-data",
            {"moduleCode": "payable-check"},
        )
        response = CanaryOperationDataView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = response.data["data"]
        self.assertEqual(payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(payload["count"], 16)
        self.assertEqual(
            payload["strictFacts"]["objectCount"],
            len(payload["results"]),
        )
        self.assertEqual(payload["businessWriteRequestCount"], 0)
        self.assertFalse(payload["productionUserDataWritten"])

    def test_permission_fact_provider_reads_canary_operation_rows(self):
        rows = payable_check_operation_rows(self.batch)
        pending = next(row for row in rows if row["objectState"] == "pending_check")
        checked = next(row for row in rows if row["objectState"] == "checked")
        facts = BusinessObjectFactProvider().read(
            "payable-check", [pending["id"], checked["id"]],
        )
        self.assertTrue(facts["found"])
        self.assertEqual(facts["statuses"], ["draft", "checked"])
        self.assertEqual(facts["legalEntityIds"], ["LEGAL-V45"])
