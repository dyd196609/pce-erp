"""Isolated regression evidence for the two Demand engineering identities.

Run with pce_backend.supply_admission_regression_test_settings (:memory:).
The reused PDE fixture creates synthetic source data; only upstream document
release proofs are mocked. Output generation/release, persisted output audits,
state transitions and Demand input references use real services. MAKE/BUY and
the sales workflow actor are stubbed exclusively for consumer tests, not as
proof of formal production authorization. No existing/formal database is used.
Negative QuerySet updates below inject corruption only in the isolated fixture.
"""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from masterdata.models import MasterDataWriteRequest
from pde.models import (
    BOMItem, EngineeringDocumentVersion, ManufacturingInputReference,
    ProductManufacturingOutput,
)
from pde.tests_manufacturing_output_generation import MODULE, SCOPE
from pde.tests_manufacturing_output_release import fixture
from pde import tests_manufacturing_release_subject_contract as subject_fixture
from pde.manufacturing_output_generation_service import (
    ACTION as GENERATE_OUTPUT, candidate_projection, generate_manufacturing_output,
)
from pde.manufacturing_output_release_service import (
    ACTION as RELEASE_OUTPUT, release_manufacturing_output, release_preflight,
)
from planning.models import Demand, PlanningRequirement
from sales.manufacturing_input import (
    ManufacturingInputError, resolve_demand_manufacturing_input,
    resolve_order_engineered_input,
)
from sales.models import SalesOrderItem
from sales.services import SalesBusinessError, engineering_readiness_facts, generate_demand
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime import state_transitions


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class OrderEngineeredDemandCompatibilityTests(TestCase):
    def setUp(self):
        fixture(self)
        # Freeze non-unit BOM consumption to prove Demand remains five products,
        # not five times the material/component consumption quantity.
        SalesOrderItem.objects.filter(pk=self.order_item.pk).update(quantity=Decimal("5"))
        BOMItem.objects.filter(bom_version=self.order_bom_version).update(quantity=Decimal("3"))
        self.order_item.refresh_from_db()
        self.document_proof = patch(
            f"{MODULE}.release_readback",
            return_value={"completed": True, "businessStateTransitionId": 999},
        )
        self.document_integrity = patch(
            f"{MODULE}.project_release_content_integrity",
            return_value={"valid": True, "stableCurrentContentHash": "verified-fixture"},
        )
        self.supply = patch(
            "sales.supply_admission_service.supply_admission_facts",
            return_value={"supplyBranch": "MAKE", "status": "CONFIRMED",
                          "sourceAuthority": "SIMULATED_FOR_TEST"},
        )
        for stub in (self.document_proof, self.document_integrity, self.supply):
            stub.start()
            self.addCleanup(stub.stop)
        candidate = candidate_projection(self.executor)
        made = generate_manufacturing_output(
            user=self.executor,
            payload={"salesOrderItemId": self.order_item.pk,
                     "sourceFingerprint": candidate["sourceFingerprint"],
                     "action": GENERATE_OUTPUT, "reason": "隔离订单工程消费回归来源"},
            idempotency_key="demand-consumer-generation",
        )
        self.output = ProductManufacturingOutput.objects.get(pk=made["row"]["id"])
        released = release_manufacturing_output(
            user=self.executor, output_id=self.output.pk,
            payload={"action": RELEASE_OUTPUT, "reason": "隔离订单工程消费回归发布",
                     "sourceFingerprint": release_preflight(self.output, self.executor)["sourceFingerprint"]},
            idempotency_key="demand-consumer-release",
        )
        self.output.refresh_from_db()
        self.generation_audit_id = made["auditId"]
        self.release_audit_id = released["auditId"]
        self.release_transition_id = released["businessStateTransitionId"]

    def _line(self):
        return engineering_readiness_facts(self.order)["lines"][0]

    def _protected_counts(self):
        return (
            Demand.objects.count(), PlanningRequirement.objects.count(),
            ManufacturingInputReference.objects.count(), MasterDataWriteRequest.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(), BusinessStateTransition.objects.count(),
        )

    def _assert_blocked(self, expected_code=None):
        before = self._protected_counts()
        self.order_item.refresh_from_db()
        with self.assertRaises(ManufacturingInputError) as caught:
            resolve_order_engineered_input(self.order_item)
        if expected_code:
            self.assertEqual(caught.exception.code, expected_code)
        line = self._line()
        self.assertFalse(line["ready"], line)
        self.assertEqual(line["engineeringBlockerCode"], caught.exception.code)
        self.assertTrue(line["blockers"])
        self.assertEqual(before, self._protected_counts())

    def _generate_demand(self):
        # This stub isolates the consumer; it does not grant permissions or
        # substitute an authorization result in any formal database/API.
        with patch("sales.services._workflow_actor") as sales_actor:
            result = generate_demand(
                user=self.executor, order_id=self.order.pk,
                authorization={"evidenceSource": "SIMULATED_FOR_TEST"}, return_all=True,
            )
            sales_actor.assert_called_once_with(self.executor, "sales.order.generate_demand")
            return result

    def _long_term_output(self):
        # Established legacy fixture only; not a fabricated order-engineering
        # product identity. Its actual model clean contract remains exercised.
        for obj, status_field in (
            (self.product_version, "version_status"),
            (self.standard_bom_version, "status"),
            (self.standard_routing_version, "status"),
            (self.standard_document_version, "status"),
        ):
            type(obj).objects.filter(pk=obj.pk).update(**{status_field: "released"})
            obj.refresh_from_db()
        output = subject_fixture.ManufacturingReleaseSubjectContractTests._long_term_output(
            self, release_status="released_to_manufacturing",
        )
        output.full_clean()
        output.save()
        return output

    def test_missing_item_output_fk_uses_formal_oei_release_and_is_read_only(self):
        before = self._protected_counts()
        self.assertIsNone(self.order_item.manufacturing_output_id)
        self.assertIsNone(self.order_item.product_definition_id)
        self.assertIsNone(self.order_item.product_version_id)
        self.assertEqual(self.instance.status, "calculated")
        line = self._line()
        self.assertTrue(line["ready"], line)
        self.assertEqual(line["definitionMode"], "ORDER_ENGINEERED_PRODUCT")
        self.assertEqual(line["supplyBranch"], "MAKE")
        self.assertEqual(line["manufacturingOutputId"], self.output.pk)
        source = line["manufacturingInput"]
        self.assertTrue(source["sourceConsistent"])
        self.assertTrue(source["generationReadback"]["completed"])
        self.assertTrue(source["releaseReadback"]["completed"])
        self.assertEqual(source["orderEngineeringBaselineId"], self.baseline.pk)
        self.assertEqual(source["engineeringCalculationId"], self.calculation.pk)
        self.assertEqual(source["engineeringDocumentVersionId"], self.order_document_version.pk)
        self.assertEqual(source["businessWriteCount"], 0)
        self.assertEqual(before, self._protected_counts())
        self.order_item.refresh_from_db()
        self.instance.refresh_from_db()
        self.assertIsNone(self.order_item.manufacturing_output_id)
        self.assertEqual(self.instance.status, "calculated")

    def test_absent_oei_blocks_before_demand(self):
        type(self.instance).objects.filter(pk=self.instance.pk).update(status="inactive")
        self._assert_blocked("MANUFACTURING_OUTPUT_OEI_REQUIRED")

    def test_required_source_lifecycle_each_fails_closed(self):
        for obj, invalid, restore in (
            (self.baseline, "draft", "confirmed"),
            (self.calculation, "failed", "completed"),
            (self.order_document_version, "draft", "released"),
            (self.order_bom_version, "draft", "released"),
            (self.category_routing_version, "draft", "released"),
        ):
            with self.subTest(source=type(obj).__name__):
                type(obj).objects.filter(pk=obj.pk).update(status=invalid)
                self._assert_blocked()
                type(obj).objects.filter(pk=obj.pk).update(status=restore)

    def test_unreleased_output_blocks(self):
        ProductManufacturingOutput.objects.filter(pk=self.output.pk).update(release_status="draft")
        self._assert_blocked("ORDER_ENGINEERING_OUTPUT_NOT_RELEASED")

    def test_absent_output_blocks(self):
        self.output.delete()
        self._assert_blocked("ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE")

    def test_ambiguous_output_reader_fails_closed_without_bypassing_unique_constraint(self):
        # The real schema disallows duplicate OEI outputs. Reader fault injection
        # tests defense-in-depth without removing/altering a database constraint.
        with patch("sales.manufacturing_input.ProductManufacturingOutput.objects.filter") as query:
            query.return_value.select_related.return_value = [self.output, self.output]
            self._assert_blocked("ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE")

    def test_output_frozen_source_fk_conflict_blocks(self):
        ProductManufacturingOutput.objects.filter(pk=self.output.pk).update(
            routing_version=self.standard_routing_version,
        )
        self._assert_blocked("ORDER_ENGINEERING_SOURCE_CONFLICT")

    def test_wrong_item_direct_output_fk_is_not_used_as_a_fallback(self):
        legacy = self._long_term_output()
        SalesOrderItem.objects.filter(pk=self.order_item.pk).update(manufacturing_output=legacy)
        self._assert_blocked("ORDER_ENGINEERING_INPUT_INVALID")

    def test_wrong_item_document_fk_blocks(self):
        SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
            engineering_document_version=self.standard_document_version,
        )
        self._assert_blocked("ORDER_ENGINEERING_ITEM_DOCUMENT_CONFLICT")

    def test_other_document_does_not_replace_fixed_output_document(self):
        copy = EngineeringDocumentVersion.objects.get(pk=self.order_document_version.pk)
        copy.pk = None
        copy.document_version = "R2"
        copy.save()
        before = self._protected_counts()
        resolved = resolve_order_engineered_input(self.order_item, output_id=self.output.pk)
        self.assertEqual(resolved['output'].pk, self.output.pk)
        self.assertEqual(self.output.engineering_document_version_id, self.order_document_version.pk)
        self.assertEqual(before, self._protected_counts())

    def test_obsolete_output_document_cannot_be_replaced_by_a_new_current_version(self):
        current = EngineeringDocumentVersion.objects.get(pk=self.order_document_version.pk)
        current.pk = None
        current.document_version = "R2"
        current.save()
        EngineeringDocumentVersion.objects.filter(pk=self.order_document_version.pk).update(status="obsolete")
        self._assert_blocked("MANUFACTURING_OUTPUT_RELEASED_DOCUMENT_REQUIRED")

    def test_changed_frozen_bom_content_blocks(self):
        BOMItem.objects.filter(bom_version=self.order_bom_version).update(quantity=Decimal("4"))
        self._assert_blocked("ORDER_ENGINEERING_FROZEN_CONTENT_CHANGED")

    def test_changed_generation_or_release_fingerprint_blocks(self):
        for audit_id in (self.generation_audit_id, self.release_audit_id):
            audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
            original = deepcopy(audit.after_snapshot)
            changed = {**original, "sourceFingerprint": "stale-fingerprint"}
            with self.subTest(audit_id=audit_id):
                OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(after_snapshot=changed)
                self._assert_blocked("ORDER_ENGINEERING_FROZEN_CONTENT_CHANGED")
                OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(after_snapshot=original)

    def test_release_source_snapshot_conflict_blocks(self):
        audit = OrganizationOperatingAuditRecord.objects.get(pk=self.release_audit_id)
        changed = deepcopy(audit.after_snapshot)
        changed["sourceSnapshot"]["bom_version_id"] = self.standard_bom_version.pk
        OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=changed)
        self._assert_blocked("ORDER_ENGINEERING_RELEASE_SOURCE_CONFLICT")

    def test_missing_formal_generation_or_release_audit_blocks(self):
        for audit_id in (self.generation_audit_id, self.release_audit_id):
            audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
            original = audit.action_code
            with self.subTest(audit_id=audit_id):
                OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(action_code="test.corrupt.audit")
                self._assert_blocked("ORDER_ENGINEERING_RELEASE_FACT_INCOMPLETE")
                OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(action_code=original)

    def test_cross_company_audit_and_write_request_each_block(self):
        other = Company.objects.create(code="RSC-OTHER", name="隔离证据范围冲突公司")
        for model, object_id in (
            (OrganizationOperatingAuditRecord, self.release_audit_id),
            (MasterDataWriteRequest, resolve_order_engineered_input(self.order_item)["facts"]["releaseReadback"]["writeRequestId"]),
        ):
            with self.subTest(proof=model.__name__):
                model.objects.filter(pk=object_id).update(organization_id=other.pk)
                self._assert_blocked("ORDER_ENGINEERING_RELEASE_SCOPE_CONFLICT")
                model.objects.filter(pk=object_id).update(organization_id=self.company.pk)

    def test_nonconsecutive_release_transition_version_blocks(self):
        BusinessStateTransition.objects.filter(pk=self.release_transition_id).update(version=9)
        self._assert_blocked("ORDER_ENGINEERING_RELEASE_FACT_INCOMPLETE")

    def test_invalid_audit_reference_format_is_a_blocker_not_a_fake_empty_fact(self):
        BusinessStateTransition.objects.filter(pk=self.release_transition_id).update(
            audit_reference="OrganizationOperatingAuditRecord:not-an-integer",
        )
        self._assert_blocked("ORDER_ENGINEERING_RELEASE_FACT_INVALID")

    def test_upstream_document_proof_and_content_integrity_remain_required(self):
        with patch(f"{MODULE}.release_readback", return_value={"completed": False}):
            self._assert_blocked("MANUFACTURING_OUTPUT_RELEASE_FACT_REQUIRED")
        with patch(f"{MODULE}.project_release_content_integrity", return_value={"valid": False}):
            self._assert_blocked("MANUFACTURING_OUTPUT_RELEASE_FACT_REQUIRED")

    def test_explicit_isolated_demand_retains_output_empty_products_and_quantity(self):
        # The upstream fixture releases source versions with QuerySet updates;
        # compare persisted facts, never its stale pre-release Python objects.
        self.order_bom_version.refresh_from_db()
        self.category_routing_version.refresh_from_db()
        protected = (self.instance.status, self.order_item.manufacturing_output_id,
                     self.order_bom_version.status, self.category_routing_version.status)
        demands, audits = self._generate_demand()
        self.assertEqual(len(demands), 1)
        demand = demands[0]
        self.assertEqual(demand.status, "confirmed")
        history = list(BusinessStateTransition.objects.filter(
            object_type="Demand", object_id=demand.pk,
        ).order_by("version"))
        self.assertEqual([(row.source_state, row.target_state, row.version) for row in history],
                         [("", "draft", 1), ("draft", "confirmed", 2)])
        self.assertEqual(len({row.audit_reference for row in history}), 2)
        self.assertEqual(history[1].audit_reference,
                         f"OrganizationOperatingAuditRecord:{audits[0].pk}")
        self.assertEqual(demand.manufacturing_output_id, self.output.pk)
        self.assertIsNone(demand.product_definition_id)
        self.assertIsNone(demand.product_version_id)
        self.assertEqual(demand.required_qty, Decimal("5"))
        self.assertEqual(demand.required_date, self.order_item.required_date)
        reference = ManufacturingInputReference.objects.get(target_demand=demand)
        self.assertEqual(reference.source_manufacturing_output_id, self.output.pk)
        self.assertEqual(reference.reference_status, "active")
        state = audits[0].after_snapshot["state"]
        self.assertEqual(state["manufacturingInput"]["definitionMode"], "ORDER_ENGINEERED_PRODUCT")
        self.assertEqual(state["manufacturingOutputId"], self.output.pk)
        self.assertEqual(state["requiredQty"], "5.0000")
        self.assertEqual(PlanningRequirement.objects.count(), 0)
        self.order_item.refresh_from_db()
        self.instance.refresh_from_db()
        self.order_bom_version.refresh_from_db()
        self.category_routing_version.refresh_from_db()
        self.assertEqual(protected, (self.instance.status, self.order_item.manufacturing_output_id,
                                     self.order_bom_version.status, self.category_routing_version.status))
        replay_before = self._protected_counts()
        replay, replay_audits = self._generate_demand()
        self.assertEqual(replay[0].pk, demand.pk)
        self.assertEqual(replay_audits, [])
        self.assertEqual(Demand.objects.count(), 1)
        self.assertEqual(ManufacturingInputReference.objects.count(), 1)
        self.assertEqual(replay_before, self._protected_counts())

    def test_demand_confirmation_failure_rolls_back_output_reference_audits_and_history(self):
        before = self._protected_counts()
        output_before = ProductManufacturingOutput.objects.values().get(pk=self.output.pk)

        def confirm_then_fail(**kwargs):
            state_transitions.transition_business_object(**kwargs)
            demand = kwargs["business_object"]
            self.assertEqual(demand.status, "confirmed")
            self.assertEqual(ManufacturingInputReference.objects.filter(
                target_demand=demand, source_manufacturing_output=self.output,
            ).count(), 1)
            self.assertEqual(BusinessStateTransition.objects.filter(
                object_type="Demand", object_id=demand.pk,
            ).count(), 2)
            raise RuntimeError("isolated Demand confirmation failure")

        with patch("sales.services.transition_business_object", side_effect=confirm_then_fail):
            with self.assertRaisesRegex(RuntimeError, "Demand confirmation failure"):
                self._generate_demand()
        self.assertEqual(before, self._protected_counts())
        self.assertEqual(Demand.objects.count(), 0)
        self.assertEqual(ManufacturingInputReference.objects.count(), 0)
        self.assertEqual(output_before, ProductManufacturingOutput.objects.values().get(pk=self.output.pk))

    def test_other_blocked_line_prevents_partial_demand_creation(self):
        second = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=2, material=self.finished,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="未形成工程输入订单行",
            quantity=Decimal("2"), uom=self.uom, required_date=self.order_item.required_date,
        )
        before = self._protected_counts()
        with self.assertRaises(SalesBusinessError) as caught:
            self._generate_demand()
        self.assertEqual(caught.exception.code, "ORDER_DEMAND_MANUFACTURING_NOT_READY")
        self.assertEqual([line["salesOrderItemId"] for line in caught.exception.data["blockedLines"]], [second.pk])
        self.assertEqual(before, self._protected_counts())

    def test_buy_order_engineered_line_does_not_require_manufacturing_output(self):
        second = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=2, material=self.finished,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="外购订单专属产品",
            quantity=Decimal("2"), uom=self.uom, required_date=self.order_item.required_date,
        )
        with patch("sales.supply_admission_service.supply_admission_facts", return_value={"supplyBranch": "BUY"}):
            readiness = engineering_readiness_facts(self.order)
            self.assertTrue(readiness["ready"], readiness)
            resolved = resolve_demand_manufacturing_input(second, supply_branch="BUY")
            self.assertIsNone(resolved["output"])
            self.assertEqual(resolved["facts"]["definitionMode"], "NOT_APPLICABLE")
            demands, _ = self._generate_demand()
        self.assertEqual(len(demands), 2)
        self.assertTrue(all(demand.manufacturing_output_id is None for demand in demands))
        self.assertEqual(ManufacturingInputReference.objects.count(), 0)
        self.assertEqual(PlanningRequirement.objects.count(), 0)

    def test_long_term_product_existing_identity_and_input_reference_preserved(self):
        legacy = self._long_term_output()
        SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
            engineering_mode="STANDARD", product_definition=self.product,
            product_version=self.product_version, manufacturing_output=legacy,
        )
        self.order_item.refresh_from_db()
        line = self._line()
        self.assertTrue(line["ready"], line)
        self.assertEqual(line["definitionMode"], "LONG_TERM_PRODUCT")
        self.assertEqual(line["manufacturingOutputId"], legacy.pk)
        with patch("sales.manufacturing_input.resolve_order_engineered_input", side_effect=AssertionError("legacy path must remain independent")):
            demands, _ = self._generate_demand()
        self.assertEqual(demands[0].product_definition_id, self.product.pk)
        self.assertEqual(demands[0].product_version_id, self.product_version.pk)
        self.assertEqual(demands[0].manufacturing_output_id, legacy.pk)
        self.assertEqual(ManufacturingInputReference.objects.get(target_demand=demands[0]).source_manufacturing_output_id, legacy.pk)

    def test_long_term_missing_product_version_or_output_still_blocks(self):
        legacy = self._long_term_output()
        SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
            engineering_mode="STANDARD", product_definition=self.product,
            product_version=self.product_version, manufacturing_output=legacy,
        )
        for field in ("product_version", "manufacturing_output"):
            with self.subTest(field=field):
                SalesOrderItem.objects.filter(pk=self.order_item.pk).update(**{field: None})
                self.assertFalse(self._line()["ready"])
                with self.assertRaises(SalesBusinessError) as caught:
                    self._generate_demand()
                self.assertEqual(caught.exception.code, "ORDER_DEMAND_MANUFACTURING_NOT_READY")
                SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
                    product_version=self.product_version, manufacturing_output=legacy,
                )
        self.assertEqual(Demand.objects.count(), 0)

    def test_demand_clean_rejects_other_order_line_source(self):
        second = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=2, material=self.finished,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="不同工程订单行",
            quantity=Decimal("2"), uom=self.uom, required_date=self.order_item.required_date,
        )
        demand = Demand(
            demand_no="DM-ISOLATED-WRONG-LINE", source_type="sales_order",
            source_document_type="SalesOrderItem", source_document_id=str(second.pk),
            source_document_no=self.order.order_no, sales_order_item=second,
            manufacturing_output=self.output, material=self.finished,
            required_qty=Decimal("2"), required_date=second.required_date,
            department=self.department, reason="隔离不同来源拒绝回归", created_by=self.executor,
        )
        with self.assertRaises(ValidationError) as caught:
            demand.clean()
        self.assertIn("manufacturing_output", caught.exception.message_dict)
        self.assertEqual(Demand.objects.count(), 0)

