from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from masterdata.models import MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord, PositionResponsibility, UserRoleScopeAssignment
from workflow_runtime.models import BusinessStateTransition
from .models import ProductManufacturingOutput, BOMItem, RoutingStep
from .tests_manufacturing_output_generation import build_fixture, SCOPE, MODULE
from .manufacturing_output_generation_service import candidate_projection, generate_manufacturing_output, ManufacturingOutputError
from .manufacturing_output_release_service import ACTION, release_preflight, release_readback, release_manufacturing_output, require_publisher


def fixture(owner):
    build_fixture(owner)
    from system.models import Responsibility
    duty,_ = Responsibility.objects.get_or_create(code="RESP_PROD_PLAN_001",defaults={"name":"生产计划承接","status":"ACTIVE","is_active":True})
    position = owner.executor.employee.position_ref if hasattr(owner.executor,"employee") else None
    if position is None:
        from pfm.models import Employee
        position = Employee.objects.get(user=owner.executor).position_ref
    PositionResponsibility.objects.create(position=position,responsibility=duty,active=True,is_primary=True)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingOutputReleaseTests(TestCase):
    def setUp(self):
        fixture(self)
        self.patches = [patch(f"{MODULE}.release_readback",return_value={"completed":True,"businessStateTransitionId":999}),
            patch(f"{MODULE}.project_release_content_integrity",return_value={"valid":True,"stableCurrentContentHash":"verified-fixture"})]
        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)
        candidate = candidate_projection(self.executor)
        made = generate_manufacturing_output(user=self.executor, payload={"salesOrderItemId":self.order_item.pk,
            "sourceFingerprint":candidate["sourceFingerprint"],"action":"pde.manufacturing_output.generate","reason":"工程来源确认"},idempotency_key="fixture-gen")
        self.output = ProductManufacturingOutput.objects.get(pk=made["row"]["id"])

    def payload(self):
        return {"action":ACTION,"reason":"正式制造发布","sourceFingerprint":release_preflight(self.output,self.executor)["sourceFingerprint"]}

    def release(self,key="release-1",user=None,payload=None):
        return release_manufacturing_output(user=user or self.executor,output_id=self.output.pk,payload=payload or self.payload(),idempotency_key=key)

    def test_preflight_read_only_and_dedicated_release_duty(self):
        counts = (MasterDataWriteRequest.objects.count(),BusinessStateTransition.objects.count())
        result = release_preflight(self.output,self.executor)
        self.assertTrue(result["releaseAllowed"],result)
        self.assertEqual(result["currentPublisher"]["releaseResponsibilityCode"],"RESP_PROD_PLAN_001")
        self.assertEqual(counts,(MasterDataWriteRequest.objects.count(),BusinessStateTransition.objects.count()))
        self.assertFalse(result["resourceObservations"]["releaseGate"])

    def test_release_real_transaction_and_protected_sources_unchanged(self):
        before = (self.order_item.manufacturing_output_id,self.instance.status,RoutingStep.objects.count(),BOMItem.objects.count())
        result = self.release()
        self.output.refresh_from_db()
        self.order_item.refresh_from_db()
        self.instance.refresh_from_db()
        self.assertEqual(self.output.release_status,"released_to_manufacturing")
        self.assertEqual(before,(self.order_item.manufacturing_output_id,self.instance.status,RoutingStep.objects.count(),BOMItem.objects.count()))
        self.assertTrue(release_readback(self.output)["completed"])
        self.assertEqual(result["row"]["statusTransitionCount"],2)
        transition = BusinessStateTransition.objects.get(pk=result["businessStateTransitionId"])
        self.assertEqual((transition.source_state,transition.target_state),("draft","released_to_manufacturing"))
        self.assertEqual(transition.operator,self.executor)

    def test_replay_same_and_new_key_cannot_duplicate_facts(self):
        payload = self.payload()
        first = self.release(payload=payload)
        for key in ("release-1","release-2"):
            self.assertTrue(self.release(key=key,payload=payload)["idempotentReplay"])
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(),1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION).count(),1)
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=ACTION).count(),1)

    def test_reviewer_document_publisher_pmc_admin_denied(self):
        payload=self.payload()
        for actor in self.denied_users:
            with self.subTest(actor=actor.username),self.assertRaises(ManufacturingOutputError) as caught:
                self.release(user=actor,payload=payload)
            self.assertEqual(caught.exception.http_status,403)

    def test_generation_duty_alone_does_not_grant_release(self):
        PositionResponsibility.objects.filter(responsibility__code="RESP_PROD_PLAN_001").update(active=False)
        self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])
        with self.assertRaises(ManufacturingOutputError):
            require_publisher(self.executor,self.company.pk)

    def test_scope_revocation_blocks_even_idempotent_replay(self):
        payload=self.payload()
        self.release(payload=payload)
        UserRoleScopeAssignment.objects.filter(user=self.executor).update(active=False)
        with self.assertRaises(ManufacturingOutputError):
            self.release(payload=payload)

    def test_unreleased_bom_routing_document_each_block(self):
        for obj in (self.order_bom_version,self.category_routing_version,self.order_document_version):
            type(obj).objects.filter(pk=obj.pk).update(status="draft")
            self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])
            type(obj).objects.filter(pk=obj.pk).update(status="released")

    def test_missing_review_or_release_evidence_blocks(self):
        with patch(f"{MODULE}.project_release_content_integrity",return_value={"valid":False}):
            self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])
        with patch(f"{MODULE}.release_readback",return_value={"completed":False}):
            self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])

    def test_source_content_changed_since_generation_blocks(self):
        BOMItem.objects.filter(bom_version=self.order_bom_version).update(quantity=2)
        result=release_preflight(self.output,self.executor)
        self.assertEqual(result["firstBlockerCode"],"MANUFACTURING_RELEASE_CONTENT_CHANGED")

    def test_state_not_draft_and_missing_generation_fact_block(self):
        ProductManufacturingOutput.objects.filter(pk=self.output.pk).update(release_status="engineering_review")
        self.output.refresh_from_db()
        self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])
        ProductManufacturingOutput.objects.filter(pk=self.output.pk).update(release_status="draft")
        self.output.refresh_from_db()
        BusinessStateTransition.objects.filter(object_type="ProductManufacturingOutput",object_id=self.output.pk).delete()
        self.assertFalse(release_preflight(self.output,self.executor)["releaseAllowed"])

    def test_stale_request_foreign_keys_and_missing_reason_rejected(self):
        for payload in ({**self.payload(),"sourceFingerprint":"stale"},{**self.payload(),"release_status":"released_to_manufacturing"},{**self.payload(),"reason":""}):
            with self.assertRaises(ManufacturingOutputError):
                self.release(payload=payload)

    def test_fault_rolls_back_status_audit_and_request(self):
        with patch("pde.manufacturing_output_release_service.transition_business_object",side_effect=RuntimeError("isolated-fault")):
            with self.assertRaises(RuntimeError):
                self.release()
        self.output.refresh_from_db()
        self.assertEqual(self.output.release_status,"draft")
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(),0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION).count(),0)

    def test_http_endpoint_and_five_surface_readback(self):
        client=APIClient()
        client.force_authenticate(self.executor)
        response=client.post(f"/api/pde/manufacturing-outputs/{self.output.pk}/release/",self.payload(),format="json",HTTP_IDEMPOTENCY_KEY="release-http")
        self.assertEqual(response.status_code,200,response.data)
        read=client.get("/api/pde/manufacturing-outputs/").data
        fact=read["strictFacts"]["manufacturingOutputCandidate"]["manufacturingRelease"]
        self.assertTrue(fact["releaseReadback"]["completed"])
        for surface in ("apiFacts","pageFacts","diagnosticFacts","acceptanceFacts"):
            self.assertEqual(read[surface]["manufacturingOutputCandidate"]["manufacturingRelease"],fact)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingOutputConcurrentReleaseTests(TransactionTestCase):
    def test_two_simultaneous_release_requests_one_transition(self):
        fixture(self)
        with patch(f"{MODULE}.release_readback",return_value={"completed":True,"businessStateTransitionId":999}),patch(
            f"{MODULE}.project_release_content_integrity",return_value={"valid":True,"stableCurrentContentHash":"verified-fixture"}):
            candidate=candidate_projection(self.executor)
            made=generate_manufacturing_output(user=self.executor,payload={"salesOrderItemId":self.order_item.pk,
                "sourceFingerprint":candidate["sourceFingerprint"],"action":"pde.manufacturing_output.generate","reason":"来源确认"},idempotency_key="concurrent-gen")
            payload={"action":ACTION,"reason":"并发发布测试","sourceFingerprint":candidate["sourceFingerprint"]}
            barrier=Barrier(2)
            def worker(index):
                try:
                    barrier.wait(timeout=5)
                    return release_manufacturing_output(user=self.executor,output_id=made["row"]["id"],payload=payload,idempotency_key=f"concurrent-release-{index}")
                finally:
                    connections["default"].close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(worker,[1,2]))
            self.assertEqual(len({r["businessStateTransitionId"] for r in results}),1)
            self.assertEqual(BusinessStateTransition.objects.filter(action_code=ACTION).count(),1)
            self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION).count(),1)
            self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(),1)
