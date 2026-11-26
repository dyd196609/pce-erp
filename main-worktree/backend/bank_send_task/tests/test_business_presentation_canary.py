import io

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bank_send_preparation.models import BankSendPreparation
from bank_send_preparation.services import generate_bank_message_preview
from bank_send_task.canary import (
    BLOCKED_SCENARIOS,
    bank_send_task_canary_facts,
    replenish_bank_send_task_canary_pool,
    seed_bank_send_task_canary_pool,
)
from bank_send_task.models import BankSendTaskCanaryPoolEntry
from bank_send_task.services import (
    BankSendTaskFactError,
    bank_send_task_status_label,
    create_bank_send_task,
    serialize_task,
)
from bank_send_task.views import (
    BankSendTaskCanaryPoolReplenishView,
    BankSendTaskListView,
)
from system.models import User


CANARY_SETTINGS = {
    "PCE_CANARY_DEMO_MODE": True,
    "PCE_CANARY_TENANT_ID": "tenant-canary-demo",
    "PCE_CANARY_BATCH_ID": "PURCHASE-FLOW-DEMO-V1",
    "PCE_BANK_SEND_PREPARATION_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_PREPARATION_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_PREPARATION_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_BANK_SEND_TASK_FEATURE_ENABLED": True,
    "PCE_BANK_SEND_TASK_PRODUCTION_ROLLOUT_ENABLED": False,
    "PCE_BANK_SEND_TASK_TEST_TENANTS": {"tenant-canary-demo"},
    "PCE_ACTION_PERMISSION_ENFORCED": True,
}


@override_settings(**CANARY_SETTINGS)
class BankSendTaskBusinessPresentationCanaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        output = io.StringIO()
        for command in (
            "ensure_purchase_canary_formal_domain",
            "ensure_payable_confirmation_prepare_canary",
            "ensure_payment_request_prepare_canary",
            "ensure_payment_request_canary",
            "ensure_payment_instruction_prepare_canary",
            "ensure_payment_order_prepare_canary",
            "ensure_payment_order_draft_canary",
            "ensure_payment_risk_review_canary",
            "ensure_formal_payment_order_canary",
            "ensure_formal_payment_order_send_gate_v54",
            "ensure_bank_send_preparation_canary",
            "ensure_business_action_permission_canary_v552",
        ):
            call_command(command, stdout=output)
        cls.preparations = list(
            BankSendPreparation.objects.order_by("prepare_no")[:8]
        )
        cls.operator = User.objects.get(username="v552-operator")
        cls.viewer = User.objects.get(username="v552-viewer")
        seed_bank_send_task_canary_pool(cls.preparations)

    def setUp(self):
        self.factory = APIRequestFactory()

    def create_one(self):
        preparation = BankSendPreparation.objects.get(
            pk=self.preparations[0].pk
        )
        if not hasattr(preparation, "message_preview"):
            generate_bank_message_preview(
                user=self.operator,
                preparation=preparation,
                idempotency_key="V591-TEST-PREVIEW",
                expected_version=preparation.version,
                explicit_user_action=True,
            )
            preparation.refresh_from_db()
        return create_bank_send_task(
            user=self.operator,
            preparation=preparation,
            idempotency_key="V591-TEST-TASK",
            expected_source_version=preparation.version,
            explicit_user_action=True,
        )

    def test_01_prepared_label(self):
        self.assertEqual(bank_send_task_status_label("prepared"), "已准备")

    def test_02_queued_label(self):
        self.assertEqual(
            bank_send_task_status_label("queued"),
            "已进入发送队列",
        )

    def test_03_ready_to_send_label(self):
        self.assertEqual(
            bank_send_task_status_label("ready_to_send"),
            "发送前就绪",
        )

    def test_04_sent_label_is_forbidden(self):
        with self.assertRaises(BankSendTaskFactError):
            bank_send_task_status_label("sent")

    def test_05_unknown_label_is_rejected(self):
        with self.assertRaises(BankSendTaskFactError):
            bank_send_task_status_label("unknown")

    def test_06_serialized_status_code_is_preserved(self):
        task = self.create_one()["data"]
        self.assertEqual(task["statusCode"], "ready_to_send")
        self.assertEqual(task["status"], task["statusCode"])

    def test_07_serialized_status_label_is_server_derived(self):
        task = self.create_one()["data"]
        self.assertEqual(task["statusLabel"], "发送前就绪")
        self.assertEqual(task["currentStateSource"], "server")

    def test_08_normal_pool_has_eight_entries(self):
        self.assertEqual(bank_send_task_canary_facts()["normalPoolCount"], 8)

    def test_09_blocked_pool_has_five_entries(self):
        self.assertEqual(bank_send_task_canary_facts()["blockedPoolCount"], 5)

    def test_10_reserve_pool_has_twenty_entries(self):
        self.assertEqual(bank_send_task_canary_facts()["reservePoolCount"], 20)

    def test_11_all_blocked_scenarios_are_present(self):
        reasons = set(
            BankSendTaskCanaryPoolEntry.objects.filter(
                pool_type="blocked"
            ).values_list("blocking_reason", flat=True)
        )
        self.assertEqual(reasons, {reason for _, reason in BLOCKED_SCENARIOS})

    def test_12_blocked_pool_is_not_eligible(self):
        self.assertTrue(
            all(
                row.eligibility_snapshot["eligible"] is False
                for row in BankSendTaskCanaryPoolEntry.objects.filter(
                    pool_type="blocked"
                )
            )
        )

    def test_13_reserve_pool_is_template_only(self):
        self.assertTrue(
            all(
                row.eligibility_snapshot["templateOnly"] is True
                for row in BankSendTaskCanaryPoolEntry.objects.filter(
                    pool_type="reserve"
                )
            )
        )

    def test_14_pool_model_has_no_business_status_field(self):
        names = {
            field.name
            for field in BankSendTaskCanaryPoolEntry._meta.get_fields()
        }
        self.assertNotIn("status", names)
        self.assertNotIn("task_status", names)

    def test_15_canary_facts_are_server_sourced(self):
        facts = bank_send_task_canary_facts()
        self.assertEqual(facts["factType"], "BankSendTaskCanaryFacts")
        self.assertEqual(facts["currentStateSource"], "server")

    def test_16_pool_sufficiency_requires_all_three_classes(self):
        self.assertTrue(bank_send_task_canary_facts()["poolSufficient"])

    def test_17_initial_available_pool_is_eight(self):
        self.assertEqual(bank_send_task_canary_facts()["availablePoolCount"], 8)

    def test_18_task_creation_consumes_one_normal_candidate(self):
        self.create_one()
        facts = bank_send_task_canary_facts()
        self.assertEqual(facts["createdTaskCount"], 1)
        self.assertEqual(facts["availablePoolCount"], 7)

    def test_19_replenishment_activates_eight_reserve_candidates(self):
        outcome = replenish_bank_send_task_canary_pool(8)
        self.assertEqual(outcome["replenishedCount"], 8)
        self.assertEqual(
            outcome["canaryPoolFacts"]["availablePoolCount"],
            16,
        )

    def test_20_replenishment_is_bounded_by_reserve_pool(self):
        first = replenish_bank_send_task_canary_pool(20)
        second = replenish_bank_send_task_canary_pool(20)
        self.assertEqual(first["replenishedCount"], 20)
        self.assertEqual(second["replenishedCount"], 0)

    def test_21_production_write_fact_is_false(self):
        self.assertFalse(
            bank_send_task_canary_facts()["productionUserDataWritten"]
        )

    def test_22_list_exposes_canary_facts_and_status_label(self):
        self.create_one()
        request = self.factory.get("/api/finance/bank-send-tasks/")
        force_authenticate(request, user=self.viewer)
        response = BankSendTaskListView.as_view()(request)
        data = response.data["data"]
        self.assertEqual(
            data["canaryPoolFacts"],
            bank_send_task_canary_facts(),
        )
        self.assertEqual(data["results"][0]["statusLabel"], "发送前就绪")

    def test_23_replenishment_endpoint_requires_test_role(self):
        request = self.factory.post(
            "/api/finance/bank-send-tasks/canary-pool/replenish",
            {"count": 8},
            format="json",
        )
        force_authenticate(request, user=self.viewer)
        response = BankSendTaskCanaryPoolReplenishView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_24_replenishment_endpoint_allows_operator(self):
        request = self.factory.post(
            "/api/finance/bank-send-tasks/canary-pool/replenish",
            {"count": 8},
            format="json",
        )
        force_authenticate(request, user=self.operator)
        response = BankSendTaskCanaryPoolReplenishView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["replenishedCount"], 8)

    @override_settings(PCE_CANARY_DEMO_MODE=False)
    def test_25_replenishment_is_forbidden_outside_canary_mode(self):
        with self.assertRaises(RuntimeError):
            replenish_bank_send_task_canary_pool(8)
