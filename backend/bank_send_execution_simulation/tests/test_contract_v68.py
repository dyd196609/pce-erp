from django.core.exceptions import ValidationError
from django.test import override_settings

from workflow_runtime.state_transitions import transition_business_object

from bank_send_execution_simulation.bank_connector import BankConnectorAdapter
from bank_send_execution_simulation.models import (
    BankSendExecutionFailure,
    BankSendExecutionFramework,
    BankSendExecutionIdempotency,
    BankSendRequestSignature,
    BankSendResponseReceipt,
)
from bank_send_execution_simulation.v68 import (
    FRAMEWORK_TRANSITIONS,
    adapter_facts,
    create_execution_framework,
    create_simulated_artifacts,
    evaluate_safety,
    framework_facts,
    perform_safety_review,
    protection_counts,
    serialize_adapter_review,
    serialize_framework,
)

from .test_contract_v65 import V65_SETTINGS
from .test_contract_v67 import BankSendProductionReleaseV67Tests


@override_settings(**V65_SETTINGS)
class BankSendExecutionFrameworkV68Tests(
    BankSendProductionReleaseV67Tests
):
    def _framework(self):
        review = self._lock_review()
        return create_execution_framework(
            source_review=review,
            user=self.operator,
            environment="simulation",
        )

    def _complete(self):
        framework = self._framework()
        request = (
            self.review.trace.source_simulation.source_request
        )
        artifacts = create_simulated_artifacts(
            request=request,
            user=self.operator,
            execution_version=1,
        )
        framework, safety = perform_safety_review(
            framework=framework,
            user=self.operator,
        )
        return framework, safety, artifacts

    def test_71_production_environment_forbidden(self):
        with self.assertRaises(ValueError):
            BankConnectorAdapter(environment="production")

    def test_72_adapter_prepare_is_simulated(self):
        result = BankConnectorAdapter().prepareRequest({"requestNo": "R1"})
        self.assertEqual(result["result"], "simulated")
        self.assertFalse(result["networkCallPerformed"])

    def test_73_adapter_sign_has_no_certificate(self):
        adapter = BankConnectorAdapter()
        result = adapter.signRequest(adapter.prepareRequest({"a": 1}))
        self.assertFalse(result["productionCertificateUsed"])

    def test_74_adapter_send_does_not_send(self):
        adapter = BankConnectorAdapter()
        prepared = adapter.prepareRequest({"a": 1})
        result = adapter.sendRequest(adapter.signRequest(prepared))
        self.assertFalse(result["realBankMessageSent"])
        self.assertFalse(result["networkCallPerformed"])

    def test_75_framework_starts_designed(self):
        self.assertEqual(self._framework().status, "designed")

    def test_76_framework_environment_is_nonproduction(self):
        row = self._framework()
        self.assertIn(row.environment, {"simulation", "sandbox"})
        self.assertFalse(row.production_connection_enabled)

    def test_77_framework_is_idempotent(self):
        first = self._framework()
        second = create_execution_framework(
            source_review=self.review,
            user=self.operator,
        )
        self.assertEqual(first.pk, second.pk)

    def test_78_safety_checks_pass(self):
        checks = evaluate_safety(self._framework())
        self.assertTrue(checks["passed"])
        self.assertTrue(all(
            checks[f"FRAMEWORK-{index:03d}"] for index in range(1, 9)
        ))

    def test_79_safety_review_completes_state(self):
        framework, safety, _ = self._complete()
        self.assertEqual(framework.status, "security_reviewed")
        self.assertEqual(safety.result, "passed")

    def test_80_signature_is_simulation_only(self):
        _, _, result = self._complete()
        self.assertEqual(
            result["signature"].certificate_mode, "simulation_only"
        )
        self.assertEqual(
            result["signature"].algorithm, "SHA256_SIMULATION"
        )

    def test_81_idempotency_returns_existing(self):
        _, _, first = self._complete()
        request = self.review.trace.source_simulation.source_request
        second = create_simulated_artifacts(
            request=request,
            user=self.operator,
            execution_version=1,
        )
        self.assertEqual(
            first["idempotency"].pk, second["idempotency"].pk
        )
        self.assertEqual(BankSendExecutionIdempotency.objects.count(), 1)

    def test_82_failure_is_simulated_no_retry(self):
        _, _, result = self._complete()
        self.assertTrue(result["failure"].simulated)
        self.assertFalse(result["failure"].retry_allowed)

    def test_83_receipt_is_simulated(self):
        _, _, result = self._complete()
        self.assertTrue(result["receipt"].simulated)
        self.assertEqual(result["receipt"].response_status, "accepted")

    def test_84_direct_status_save_blocked(self):
        framework = self._framework()
        framework.status = "security_reviewed"
        with self.assertRaises(ValidationError):
            framework.save()

    def test_85_bulk_status_update_blocked(self):
        framework = self._framework()
        with self.assertRaises(ValidationError):
            BankSendExecutionFramework.objects.filter(
                pk=framework.pk
            ).update(status="security_reviewed")

    def test_86_state_jump_blocked(self):
        framework = self._framework()
        with self.assertRaises(ValueError):
            transition_business_object(
                business_object=framework,
                object_type="bank_send_execution_framework",
                source_state="designed",
                target_state="sent",
                action_code="invalid",
                operator=self.operator,
                reason="invalid",
                audit_reference="invalid",
                allowed_transitions=FRAMEWORK_TRANSITIONS,
            )

    def test_87_transition_history_consistent(self):
        framework, _, _ = self._complete()
        row = serialize_framework(framework)
        self.assertTrue(row["stateMachineConsistent"])
        self.assertEqual(row["statusTransitionCount"], 2)

    def test_88_adapter_serialization_has_all_models(self):
        framework, _, _ = self._complete()
        row = serialize_adapter_review(framework)
        self.assertTrue(row["signature"])
        self.assertTrue(row["idempotency"])
        self.assertTrue(row["failure"])
        self.assertTrue(row["receipt"])
        self.assertFalse(row["networkCallPerformed"])

    def test_89_facts_and_protection(self):
        framework, _, _ = self._complete()
        framework_row = serialize_framework(framework)
        adapter_row = serialize_adapter_review(framework)
        first = framework_facts(
            [framework_row], tenant_id="t", batch_id="b"
        )
        second = adapter_facts(
            [adapter_row], tenant_id="t", batch_id="b"
        )
        self.assertEqual(first["recordCount"], 1)
        self.assertEqual(second["signatureCount"], 1)
        self.assertEqual(second["networkCallCount"], 0)

    def test_90_zero_real_writes(self):
        self._complete()
        facts = protection_counts()
        self.assertEqual(facts["bankMessageSendWriteCount"], 0)
        self.assertEqual(facts["paymentExecutionWriteCount"], 0)
        self.assertEqual(facts["financialImpactWriteCount"], 0)
        self.assertEqual(facts["businessProgressWriteCount"], 0)
        self.assertEqual(facts["productionSendRecordCount"], 0)

    def test_91_artifact_counts(self):
        self._complete()
        self.assertEqual(BankSendRequestSignature.objects.count(), 1)
        self.assertEqual(BankSendExecutionIdempotency.objects.count(), 1)
        self.assertEqual(BankSendExecutionFailure.objects.count(), 1)
        self.assertEqual(BankSendResponseReceipt.objects.count(), 1)

    def test_92_api_five_surfaces(self):
        self._complete()
        for url, key in (
            (
                "/api/finance/bank-send-execution-framework-reviews/",
                "frameworkFacts",
            ),
            (
                "/api/finance/bank-connector-adapter-reviews/",
                "adapterFacts",
            ),
        ):
            data = self.client.get(url).json()["data"]
            count = data[key]["recordCount"]
            self.assertEqual(data["diagnosticFacts"]["recordCount"], count)
            self.assertEqual(data["strictFacts"]["recordCount"], count)
            self.assertEqual(data["acceptanceFacts"]["recordCount"], count)
            self.assertEqual(
                data["acceptanceFacts"]["acceptanceStatus"], "PASS"
            )
