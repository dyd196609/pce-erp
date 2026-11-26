from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from masterdata.models import MasterDataWriteRequest
from pfm.models import Employee
from system.models import Department, Position, PositionResponsibility, Responsibility, Role, RolePermission, Permission, User, UserRoleScopeAssignment, Process, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from .models import BOMItem, RoutingStep, ProductManufacturingOutput
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationService, ProductionFoundationError
from . import tests_manufacturing_release_subject_contract as subject_fixture
from .manufacturing_output_generation_service import ACTION, PERMISSION, RESPONSIBILITY, ManufacturingOutputError, candidate_projection, generate_manufacturing_output

MODULE = "pde.manufacturing_output_generation_service"
SCOPE = {"companyCode": "RSC", "orderNo": "SO-RSC-ORDER", "lineNo": 1}


def build_fixture(owner):
    # Reuse the established exact order-engineering model fixture. These are
    # isolated source facts; only upstream already-verified release proofs are
    # stubbed, while generation, permission, transaction and HTTP paths are real.
    subject_fixture.ManufacturingReleaseSubjectContractTests.setUpTestData.__func__(owner)
    owner.order.delivery_information = {"businessPurpose": "FORMAL_SALE"}
    owner.order._business_state_transition_authorized = True
    owner.order.save(update_fields=["delivery_information"])
    operation = Process.objects.create(company=owner.company, code="GEN-OP", name="工序")
    RoutingStep.objects.create(routing_version=owner.category_routing_version, sequence=1, operation=operation)
    BOMItem.objects.create(bom_version=owner.order_bom_version, material=owner.finished, line_no=1, quantity=1, uom=owner.uom)
    for obj in [owner.order_bom_version, owner.category_routing, owner.category_routing_version, owner.order_document_version]:
        type(obj).objects.filter(pk=obj.pk).update(status="released")
    owner.executing_role = Role.objects.create(code="TEST-MFG-EXEC", name="制造生成测试执行人")
    permission, _ = Permission.objects.get_or_create(code=PERMISSION, defaults={"name": "制造业务", "module": "PDE"})
    RolePermission.objects.create(role=owner.executing_role, permission=permission)
    department = Department.objects.create(company=owner.company, code="PROD", name="生产部")
    position = Position.objects.create(company=owner.company, department=department, code="PROD-MGR", name="生产经理")
    duty, _ = Responsibility.objects.get_or_create(code=RESPONSIBILITY, defaults={"name": "生产组织承接", "status": "ACTIVE", "is_active": True})
    PositionResponsibility.objects.create(position=position, responsibility=duty, active=True)
    owner.executor = User.objects.create_user(username="gen-executor", real_name="正式生产执行人", company_id=owner.company.pk)
    Employee.objects.create(user=owner.executor, employee_no="GEN-EXEC", full_name=owner.executor.real_name,
        status="active", department_ref=department, position_ref=position)
    UserRoleScopeAssignment.objects.create(user=owner.executor, role=owner.executing_role, organization=owner.company,
        scope_code="ORGANIZATION", active=True, business_hash="a" * 64)
    owner.denied_users = [owner.user]
    for username in ("gen-reviewer", "gen-document-publisher", "gen-pmc"):
        user = User.objects.create_user(username=username, company_id=owner.company.pk, real_name=username)
        owner.denied_users.append(user)
        if username == "gen-pmc":
            pmc_position = Position.objects.create(company=owner.company, department=department, code="PMC-PLAN", name="计划员")
            pmc_duty = Responsibility.objects.create(code="GEN-PMC-DUTY", name="计划职责", status="ACTIVE")
            PositionResponsibility.objects.create(position=pmc_position, responsibility=pmc_duty, active=True)
            Employee.objects.create(user=user, employee_no="GEN-PMC", full_name=username, status="active", department_ref=department, position_ref=pmc_position)
            UserRoleScopeAssignment.objects.create(user=user, role=owner.executing_role, organization=owner.company,
                scope_code="ORGANIZATION", active=True, business_hash="b" * 64)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingOutputGenerationTests(TestCase):
    def setUp(self):
        build_fixture(self)
        self.release_proof = patch(f"{MODULE}.release_readback", return_value={"completed": True, "businessStateTransitionId": 999})
        self.integrity_proof = patch(f"{MODULE}.project_release_content_integrity", return_value={"valid": True, "stableCurrentContentHash": "verified-fixture"})
        self.release_proof.start()
        self.integrity_proof.start()
        self.addCleanup(self.release_proof.stop)
        self.addCleanup(self.integrity_proof.stop)

    def payload(self, user=None):
        candidate = candidate_projection(user or self.executor)
        return {"salesOrderItemId": candidate.get("salesOrderItemId"), "sourceFingerprint": candidate.get("sourceFingerprint"),
            "action": ACTION, "reason": "确认准确工程来源并生成草稿"}

    def generate(self, key="generate-1", user=None, payload=None):
        return generate_manufacturing_output(user=user or self.executor, payload=payload or self.payload(), idempotency_key=key)

    def test_candidate_only_current_line_and_read_only(self):
        candidate = candidate_projection(self.executor)
        self.assertTrue(candidate["sourceReady"])
        self.assertTrue(candidate["generationAllowed"])
        self.assertEqual(candidate["lineNo"], 1)
        self.assertEqual(candidate["sourceIds"]["routing_version_id"], self.category_routing_version.pk)
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(), 0)

    def test_generation_transaction_persists_exact_draft_and_all_proofs(self):
        item_before = self.order_item.manufacturing_output_id
        result = self.generate()
        output = ProductManufacturingOutput.objects.get(pk=result["row"]["id"])
        self.assertEqual(output.release_status, "draft")
        self.assertEqual(output.order_engineering_instance_id, self.instance.pk)
        self.assertEqual(output.order_engineering_baseline_id, self.baseline.pk)
        self.assertEqual(output.engineering_calculation_id, self.calculation.pk)
        self.assertEqual(output.bom_version_id, self.order_bom_version.pk)
        self.assertEqual(output.routing_version_id, self.category_routing_version.pk)
        self.assertEqual(output.engineering_document_version_id, self.order_document_version.pk)
        self.assertTrue(result["row"]["generationReadback"]["completed"])
        self.assertTrue(result["row"]["stateMachineConsistent"])
        self.assertEqual(result["row"]["statusTransitionCount"], len(result["row"]["statusTransitionHistory"]))
        self.assertEqual(BusinessStateTransition.objects.get(pk=result["initializationTransitionId"]).source_state, "")
        self.assertEqual(MasterDataWriteRequest.objects.get(pk=result["writeRequestId"]).status, "COMMITTED")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"]).actor_id, self.executor.pk)
        self.order_item.refresh_from_db()
        self.assertEqual(self.order_item.manufacturing_output_id, item_before)

    def test_replay_same_and_different_keys_preserves_one_fact_set(self):
        first = self.generate()
        second = self.generate()
        third = self.generate(key="different-key")
        self.assertEqual(first["row"]["id"], second["row"]["id"])
        self.assertEqual(first["row"]["id"], third["row"]["id"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(ProductManufacturingOutput.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(), 1)
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=ACTION).count(), 1)

    def test_reviewer_publisher_pmc_admin_all_denied(self):
        payload = self.payload()
        for user in self.denied_users:
            with self.subTest(username=user.username), self.assertRaises(ManufacturingOutputError) as caught:
                self.generate(user=user, payload=payload)
            self.assertEqual(caught.exception.http_status, 403)
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)

    def test_lines_2_3_4_cannot_enter_write_scope(self):
        payload = self.payload()
        for line in (2, 3, 4):
            with self.assertRaises(ManufacturingOutputError) as caught:
                self.generate(payload={**payload, "salesOrderItemId": self.order_item.pk + line})
            self.assertEqual(caught.exception.code, "MANUFACTURING_OUTPUT_SCOPE_DENIED")

    def test_missing_unreleased_each_source_blocks_generation(self):
        for obj in (self.order_bom_version, self.category_routing_version, self.order_document_version):
            with self.subTest(source=type(obj).__name__):
                type(obj).objects.filter(pk=obj.pk).update(status="draft")
                candidate = candidate_projection(self.executor)
                self.assertFalse(candidate["generationAllowed"])
                self.assertFalse(candidate["sourceReady"])
                with self.assertRaises(ManufacturingOutputError):
                    self.generate(payload={"salesOrderItemId": self.order_item.pk, "sourceFingerprint": "bad", "action": ACTION, "reason": "源版本缺失"})
                type(obj).objects.filter(pk=obj.pk).update(status="released")
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)

    def test_changed_fingerprint_refuses_stale_submission(self):
        payload = self.payload()
        BOMItem.objects.filter(bom_version=self.order_bom_version).update(quantity=2)
        with self.assertRaises(ManufacturingOutputError) as caught:
            self.generate(payload=payload)
        self.assertEqual(caught.exception.code, "MANUFACTURING_OUTPUT_CANDIDATE_STALE")

    def test_client_cannot_override_status_or_source_foreign_keys(self):
        with self.assertRaises(ManufacturingOutputError) as caught:
            self.generate(payload={**self.payload(), "release_status": "released_to_manufacturing"})
        self.assertEqual(caught.exception.code, "MANUFACTURING_OUTPUT_FIELDS_DENIED")

    def test_five_fact_surfaces_share_one_candidate(self):
        client = APIClient()
        client.force_authenticate(self.executor)
        response = client.get("/api/pde/manufacturing-outputs/")
        candidate = response.data["strictFacts"]["manufacturingOutputCandidate"]
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "acceptanceFacts"):
            self.assertEqual(response.data[key]["manufacturingOutputCandidate"], candidate)
        self.assertEqual(candidate["actionContract"]["initialState"], "draft")

    def test_baseline_calculation_and_published_content_gates(self):
        for obj, bad in ((self.baseline, "draft"), (self.calculation, "failed")):
            previous = obj.status
            type(obj).objects.filter(pk=obj.pk).update(status=bad)
            self.assertFalse(candidate_projection(self.executor)["generationAllowed"])
            type(obj).objects.filter(pk=obj.pk).update(status=previous)
        with patch(f"{MODULE}.release_readback", return_value={"completed": False}):
            self.assertFalse(candidate_projection(self.executor)["generationAllowed"])
        with patch(f"{MODULE}.project_release_content_integrity", return_value={"valid": False}):
            self.assertFalse(candidate_projection(self.executor)["generationAllowed"])

    def test_authority_revocation_prevents_replay(self):
        payload = self.payload()
        self.generate(payload=payload)
        UserRoleScopeAssignment.objects.filter(user=self.executor).update(active=False)
        with self.assertRaises(ManufacturingOutputError):
            self.generate(payload=payload)

    def test_initialization_failure_rolls_back_output_audit_ledger(self):
        with patch(f"{MODULE}.transition_business_object", side_effect=RuntimeError("isolated-fault")):
            with self.assertRaises(RuntimeError):
                self.generate()
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION).count(), 0)

    def test_dedicated_http_endpoint_and_formal_readback(self):
        client = APIClient()
        client.force_authenticate(self.executor)
        response = client.post("/api/pde/manufacturing-outputs/generate/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="http-generate")
        self.assertEqual(response.status_code, 200, response.data)
        readback = client.get("/api/pde/manufacturing-outputs/")
        self.assertEqual(len(readback.data["rows"]), 1)
        self.assertEqual(readback.data["rows"][0]["orderNo"], self.order.order_no)
        self.assertEqual(readback.data["strictFacts"]["manufacturingOutputCandidate"]["outputCount"], 1)

    def test_legacy_create_update_and_release_cannot_bypass_control(self):
        fields = candidate_projection(self.executor)["sourceIds"]
        with self.assertRaises(ProductionFoundationError):
            ProductionFoundationService.save("manufacturing-outputs", user=self.denied_users[-1], payload=fields)
        generated = self.generate()
        with self.assertRaises(ProductionFoundationError):
            ProductionFoundationService.save("manufacturing-outputs", user=self.executor, object_id=generated["row"]["id"], payload={"engineering_status": "incomplete"})
        with self.assertRaises(ProductionFoundationError) as caught:
            EngineeringLifecycleService.transition("manufacturing-outputs", object_id=generated["row"]["id"], target_status="released_to_manufacturing", user=self.executor)
        self.assertEqual(caught.exception.code, "MANUFACTURING_OUTPUT_RELEASE_NOT_OPEN")


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingOutputConcurrentTests(TransactionTestCase):
    def test_two_simultaneous_generation_requests_have_one_output_and_audit(self):
        build_fixture(self)
        with patch(f"{MODULE}.release_readback", return_value={"completed": True, "businessStateTransitionId": 999}), patch(
            f"{MODULE}.project_release_content_integrity", return_value={"valid": True, "stableCurrentContentHash": "verified-fixture"}):
            candidate = candidate_projection(self.executor)
            payload = {"salesOrderItemId": candidate["salesOrderItemId"], "sourceFingerprint": candidate["sourceFingerprint"], "action": ACTION, "reason": "并发受控生成"}
            barrier = Barrier(2)
            def worker(index):
                try:
                    barrier.wait(timeout=5)
                    return generate_manufacturing_output(user=self.executor, payload=payload, idempotency_key=f"concurrent-{index}")
                finally:
                    connections["default"].close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, [1, 2]))
            self.assertEqual(len({r["row"]["id"] for r in results}), 1)
            self.assertEqual(ProductManufacturingOutput.objects.count(), 1)
            self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION).count(), 1)
            self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION).count(), 1)
