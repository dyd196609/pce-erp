"""RAM-only post-release read projection tests using the native release writer.

The shared fixture explicitly stubs upstream document proof providers. Actual
manufacturing generation/release requests, audits and transitions are persisted
only in the test runner's memory database.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from masterdata.models import MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition

from . import tests_manufacturing_output_release as release_fixture
from .manufacturing_output_release_service import (
    ACTION,
    release_manufacturing_output,
    release_preflight,
)
from .models import BOMItem, ProductManufacturingOutput
from .tests_manufacturing_output_generation import SCOPE


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingOutputReleaseProjectionTests(TestCase):
    def setUp(self):
        release_fixture.ManufacturingOutputReleaseTests.setUp(self)

    def counts(self):
        return (
            MasterDataWriteRequest.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            BusinessStateTransition.objects.count(),
            ProductManufacturingOutput.objects.count(),
        )

    def publish(self):
        source = release_preflight(self.output, self.executor)["sourceFingerprint"]
        result = release_manufacturing_output(
            user=self.executor,
            output_id=self.output.pk,
            payload={"action": ACTION, "reason": "合成发布完成读回", "sourceFingerprint": source},
            idempotency_key="completed-projection-release",
        )
        self.output.refresh_from_db()
        return result

    def test_draft_keeps_existing_publish_gate_and_no_completed_claim(self):
        facts = release_preflight(self.output, self.executor)
        self.assertTrue(facts["releaseAllowed"])
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["manufacturingReleaseExecuted"])
        self.assertEqual(facts["statusLabelForReadiness"], "制造发布准入通过")

    def test_native_complete_release_is_read_only_completion_not_state_denial(self):
        published = self.publish()
        before = self.counts()
        for _ in range(2):
            facts = release_preflight(self.output, self.executor)
            self.assertTrue(facts["releaseCompleted"])
            self.assertTrue(facts["manufacturingReleaseExecuted"])
            self.assertFalse(facts["releaseAllowed"])
            self.assertEqual(facts["statusLabelForReadiness"], "已完成正式制造发布")
            self.assertNotIn("firstBlockerCode", facts)
            self.assertNotIn("firstBlockerMessage", facts)
            self.assertEqual(facts["releaseReadback"]["auditId"], published["auditId"])
            self.assertEqual(facts["releaseReadback"]["actorId"], self.executor.pk)
            self.assertTrue(facts["releaseReadback"]["releasedAt"])
            self.assertEqual(facts["businessWriteCount"], 0)
        self.assertEqual(self.counts(), before)

    def test_status_without_native_release_proof_never_becomes_completed(self):
        ProductManufacturingOutput.objects.filter(pk=self.output.pk).update(
            release_status="released_to_manufacturing",
        )
        self.output.refresh_from_db()
        before = self.counts()
        facts = release_preflight(self.output, self.executor)
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertTrue(facts["firstBlockerCode"])
        self.assertEqual(self.counts(), before)

    def test_missing_committed_release_request_keeps_real_warning(self):
        self.publish()
        MasterDataWriteRequest.objects.filter(action_code=ACTION).delete()
        facts = release_preflight(self.output, self.executor)
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["manufacturingReleaseExecuted"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertEqual(facts["firstBlockerCode"], "MANUFACTURING_RELEASE_FACT_INCOMPLETE")

    def test_changed_current_source_keeps_real_warning_after_published_state(self):
        self.publish()
        BOMItem.objects.filter(bom_version=self.order_bom_version).update(quantity=2)
        facts = release_preflight(self.output, self.executor)
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertEqual(facts["firstBlockerCode"], "MANUFACTURING_RELEASE_CONTENT_CHANGED")

    def test_changed_published_source_fingerprint_is_not_a_success_projection(self):
        result = self.publish()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        audit.after_snapshot = {**audit.after_snapshot, "sourceFingerprint": "changed"}
        audit.save(update_fields=["after_snapshot"])
        facts = release_preflight(self.output, self.executor)
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertEqual(facts["firstBlockerCode"], "MANUFACTURING_RELEASE_CONTENT_CHANGED")

    def test_changed_published_exact_source_snapshot_keeps_warning(self):
        result = self.publish()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        audit.after_snapshot = {
            **audit.after_snapshot,
            "sourceSnapshot": {**audit.after_snapshot["sourceSnapshot"], "bom_version_id": 999},
        }
        audit.save(update_fields=["after_snapshot"])
        facts = release_preflight(self.output, self.executor)
        self.assertFalse(facts["releaseCompleted"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertEqual(facts["firstBlockerCode"], "MANUFACTURING_RELEASE_CONTENT_CHANGED")

    def test_api_five_surfaces_share_same_native_completion_projection(self):
        self.publish()
        client = APIClient()
        client.force_authenticate(self.executor)
        before = self.counts()
        payload = client.get("/api/pde/manufacturing-outputs/").data
        facts = payload["strictFacts"]["manufacturingOutputCandidate"]["manufacturingRelease"]
        self.assertTrue(facts["releaseCompleted"])
        self.assertFalse(facts["releaseAllowed"])
        for surface in ("apiFacts", "pageFacts", "diagnosticFacts", "acceptanceFacts"):
            self.assertEqual(payload[surface]["manufacturingOutputCandidate"]["manufacturingRelease"], facts)
        self.assertEqual(self.counts(), before)
