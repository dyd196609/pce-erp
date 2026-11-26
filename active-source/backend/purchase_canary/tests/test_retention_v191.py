from django.test import TestCase
from rest_framework.test import APIRequestFactory

from purchase_canary.models import (
    PurchaseCanaryBatch,
    PurchaseCanaryModuleObject,
    PurchaseCanaryScenario,
)
from purchase_canary.retention import (
    CanaryAcceptanceDataProtected,
    assert_canary_cleanup_allowed,
    canary_retention_policy,
)
from purchase_canary.views import CanaryContextView


class CanaryAcceptanceRetentionV191Tests(TestCase):
    def setUp(self):
        self.batch = PurchaseCanaryBatch.objects.create(
            batch_id="V191-ACCEPTANCE",
            tenant_id="tenant-canary-v191",
            purpose="persistent_demonstration",
            version="V1.14.2.8.4.19.1",
        )
        scenario = PurchaseCanaryScenario.objects.create(
            batch=self.batch,
            code="HAPPY_PATH",
            name="持久验收场景",
            expected_outcome="visible_after_refresh",
            scenario_hash="v191",
        )
        PurchaseCanaryModuleObject.objects.create(
            scenario=scenario,
            sequence=1,
            module_code="purchase-request",
            module_name="采购申请",
            route_path="/scm/purchase-request",
            object_no="PR-CANARY-V191",
            object_status="draft",
            evidence_hash="v191-evidence",
        )

    def test_acceptance_canary_is_visible_and_cannot_be_auto_deleted(self):
        policy = canary_retention_policy(self.batch)
        self.assertEqual(policy["dataType"], "canary_acceptance")
        self.assertTrue(policy["visibleOnBusinessPages"])
        self.assertFalse(policy["autoDeleteAllowed"])
        self.assertEqual(policy["cleanupPolicy"], "manual_only")
        with self.assertRaises(CanaryAcceptanceDataProtected):
            assert_canary_cleanup_allowed(self.batch)

    def test_context_refresh_keeps_the_same_canary_data(self):
        factory = APIRequestFactory()
        view = CanaryContextView.as_view()
        url = "/api/pce/purchase-canary/context"
        params = {
            "batchId": self.batch.batch_id,
            "scenarioCode": "HAPPY_PATH",
            "moduleCode": "purchase-request",
        }
        first = view(factory.get(url, params)).data["data"]
        second = view(factory.get(url, params)).data["data"]

        self.assertEqual(first["dataType"], "canary_acceptance")
        self.assertEqual(second["dataType"], "canary_acceptance")
        self.assertEqual(first["current"]["objectNo"], "PR-CANARY-V191")
        self.assertEqual(second["current"]["objectNo"], "PR-CANARY-V191")
        self.assertEqual(PurchaseCanaryBatch.objects.filter(pk=self.batch.pk).count(), 1)
