"""RAM-only continuation contract tests; no formal publication is simulated.

The existing registration fixture supplies the actual ORM/PFS writer.  Upstream
0046/release proof providers are explicit component stubs; their rejection is
tested, and these fixtures are not evidence that a business release occurred.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord, Permission, Process, Role, RolePermission, UserRoleScopeAssignment

from .models import (BOMVersion, EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDocument, EngineeringDocumentVersion, EngineeringMaterialRequirement,
    EngineeringRuleDefinition, OrderEngineeringBaseline, OrderEngineeringBaselineItem, RoutingVersion, RoutingStep)
from .order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationError, OrderEngineeringDocumentRegistrationService as Service)
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService
from .tests_order_engineering_document_registration import OrderEngineeringDocumentRegistrationTests


class EngineeringDocumentVersionContinuationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        OrderEngineeringDocumentRegistrationTests.setUpTestData.__func__(cls)
        cls.user.is_superuser = False
        cls.user.save(update_fields=["is_superuser"])
        permission, _ = Permission.objects.get_or_create(code=Service.PERMISSION,
            defaults={"name": "资料维护", "module": "PDE"})
        role = Role.objects.create(code="DOC-CONT-FIXTURE", name="资料维护夹具")
        cls.permission_row = RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="fixture")

    def setUp(self):
        OrderEngineeringDocumentRegistrationTests.setUp(self)
        registered = Service.register(user=self.user, order_no=self.order.order_no, line_no=1,
            document_no="DOCUMENT-CONTINUATION-001", document_name="已确认资料名称", document_type="technical",
            idempotency_key="fixture-first-document", reason="合成首版夹具")
        self.previous = EngineeringDocumentVersion.objects.get(pk=registered["readback"]["engineeringDocumentVersion"]["id"])
        # Explicit synthetic state only. Native proof providers below are stubs,
        # never a claim that review/release services ran for these old objects.
        EngineeringDocumentVersion.objects.filter(pk=self.previous.pk).update(status="released")
        EngineeringDocument.objects.filter(pk=self.previous.document_id).update(version="V1.0")
        self.previous.refresh_from_db()
        self.new_baseline = OrderEngineeringBaseline(
            company=self.company, sales_order=self.order, baseline_no="DOC-CONT-BASELINE-2",
            sequence=2, reason="合成新基线", candidate_hash="a" * 64, snapshot_hash="b" * 64,
            scope_item_count=1, confirmable_item_count=1, blocker_count=0, created_by=self.user)
        self.new_baseline._business_state_initialization_authorized = True
        self.new_baseline.save()
        for old in self.baseline.items.all():
            values = {field.attname: getattr(old, field.attname) for field in old._meta.concrete_fields
                if not field.primary_key and field.attname != "baseline_id"}
            OrderEngineeringBaselineItem.objects.create(baseline=self.new_baseline, **values)
        OrderEngineeringBaseline.objects.filter(pk=self.new_baseline.pk).update(status="confirmed")
        self.new_baseline.refresh_from_db()
        self.current = EngineeringCalculationRecord.objects.create(company=self.company, source_record=self.source,
            sales_order_item=self.order_item, engineering_instance=self.instance, scope="order_engineering",
            calculation_no="DOC-CONT-MAIN-2", rule_set_version="FIXTURE", revision=2,
            supersedes=self.calculation, status="completed", trace={"baselineReference": {
                "id": self.new_baseline.pk, "snapshotHash": self.new_baseline.snapshot_hash}})
        self.new_bom = BOMVersion.objects.create(bom=self.bom, bom_version="CALC-CONT-2", revision=2,
            bom_scope="order_specific", order_engineering_instance=self.instance,
            source_calculation=self.current, status="released")
        rule = EngineeringRuleDefinition(company=self.company, rule_code="DOC-CONT-MATERIAL", rule_name="夹具",
            version="V1", rule_kind="formula", specification={}, status="released")
        rule._business_state_initialization_authorized = True
        rule.save()
        detail = EngineeringCalculationDetail.objects.create(calculation=self.current, sequence=1, rule=rule,
            rule_code=rule.rule_code, rule_version=rule.version, expression_snapshot="1", output_name="quantity",
            output_value={"decimal": "1"}, status="succeeded", uom=self.uom,
            precision=28, rounding="ROUND_HALF_UP", started_at=timezone.now(), finished_at=timezone.now())
        self.requirement = EngineeringMaterialRequirement.objects.create(calculation=self.current,
            source_detail=detail, sequence=1, material=self.finished, quantity_basis="ORDER_TOTAL",
            calculated_quantity=1, order_quantity=1, net_quantity=1, uom=self.uom,
            item_role="material", requirement_type="manufacturing", supply_type="MAKE")
        self.patches = {}
        defaults = {
            "pde.engineering_document_version_release_service.release_readback": {"completed": True, "auditId": 1},
            "pde.engineering_document_version_review_service.review_readback": {"completed": True, "projectionConsistent": True},
            "pde.engineering_document_version_release_service.project_release_content_integrity": {
                "valid": True, "stableCurrentContentHash": "c" * 64},
            "pde.engineering_document_version_release_service.project_release_source_completeness": {"complete": True},
            "pde.bom_version_control_service.release_readback": {"released": True},
            "pde.bom_version_control_service._assert_upstream_gates": {},
            "pde.manufacturing_output_generation_service._saved_requirement_integrity": None,
            "pde.engineering_calculation_continuation_service.continuation_proof": {
                "continuationId": 1, "newCalculationId": self.current.pk,
                "predecessorCalculationId": self.calculation.pk, "baselineId": self.new_baseline.pk},
        }
        for target, value in defaults.items():
            handle = patch(target, return_value=value)
            self.patches[target.rsplit(".", 1)[-1]] = handle.start()
            self.addCleanup(handle.stop)
        manager = patch("pde.models.EngineeringCalculationContinuation.objects")
        self.continuations = manager.start()
        self.addCleanup(manager.stop)
        self.continuations.select_related.return_value.filter.return_value.first.return_value = NS(
            sales_order_item_id=self.order_item.pk, engineering_instance_id=self.instance.pk,
            previous_calculation=self.calculation)

    def args(self, **changes):
        values = dict(user=self.user, predecessor_version_id=self.previous.pk,
            order_no=self.order.order_no, line_no=1, baseline_id=self.new_baseline.pk,
            calculation_id=self.current.pk, bom_version_id=self.new_bom.pk,
            routing_version_id=self.routing_version.pk, authorization_reference="用户授权的隔离来源版本闭环")
        values.update(changes)
        return values

    def apply(self, *, key="fixture-continue-one", preview=None, **changes):
        args = self.args(**changes)
        preview = preview or Service.preview_version_continuation(**args)
        return Service.apply_version_continuation(**args, expected_context_hash=preview["contextHash"],
            idempotency_key=key, reason="原资料同头准确新来源草稿接续")

    def rejected(self, call, code):
        with self.assertRaises(OrderEngineeringDocumentRegistrationError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def counts(self):
        return (EngineeringDocumentVersion.objects.count(), OrganizationOperatingAuditRecord.objects.count(),
            ExternalIdentity.objects.count(), MasterDataWriteRequest.objects.count())

    def test_preview_is_read_only_and_server_allocates_same_head_v2(self):
        before = self.counts()
        preview = Service.preview_version_continuation(**self.args())
        self.assertEqual(preview["documentVersion"], "V2.0")
        self.assertEqual(preview["chain"]["bomVersion"]["id"], self.new_bom.pk)
        self.assertEqual(preview["businessWriteCount"], 0)
        self.assertEqual(self.counts(), before)

    def test_apply_preserves_old_header_version_and_creates_native_audit(self):
        before_header = Service._saved_row(self.previous.document)
        before_previous = Service._saved_row(self.previous)
        result = self.apply()
        row = result["readback"]["engineeringDocumentVersion"]
        self.assertEqual((row["documentId"], row["documentVersion"], row["status"]),
            (self.previous.document_id, "V2.0", "draft"))
        self.assertEqual(row["documentName"], self.previous.document_name)
        self.assertEqual(row["engineeringCalculationId"], self.current.pk)
        self.previous.refresh_from_db(); self.previous.document.refresh_from_db()
        self.assertEqual(Service._saved_row(self.previous), before_previous)
        self.assertEqual(Service._saved_row(self.previous.document), before_header)
        self.assertTrue(result["creationProof"]["auditId"])

    def test_same_and_different_keys_replay_without_new_version_or_audit(self):
        preview = Service.preview_version_continuation(**self.args())
        first = self.apply(preview=preview)
        after = self.counts()
        same = self.apply(preview=preview)
        alternate = self.apply(key="fixture-alias", preview=preview)
        self.assertEqual(self.counts()[:3], after[:3])
        self.assertEqual(self.counts()[3], after[3] + 1)  # native alias ledger only
        self.assertEqual(first["readback"], same["readback"])
        self.assertTrue(alternate["idempotentReplay"])

    def test_reviewed_and_released_replay_returns_existing_state(self):
        created = self.apply()
        identity = created["readback"]["engineeringDocumentVersion"]["id"]
        for state in ("reviewed", "released"):
            EngineeringDocumentVersion.objects.filter(pk=identity).update(status=state)
            replay = self.apply(key="fixture-replay-" + state)
            self.assertEqual(replay["readback"]["engineeringDocumentVersion"]["status"], state)
            self.assertTrue(replay["idempotentReplay"])
            self.assertEqual(EngineeringDocumentVersion.objects.count(), 2)

    def test_false_review_or_release_projection_is_rejected_on_replay(self):
        created = self.apply()
        identity = created["readback"]["engineeringDocumentVersion"]["id"]
        EngineeringDocumentVersion.objects.filter(pk=identity).update(status="reviewed")
        self.patches["review_readback"].side_effect = lambda version: {
            "completed": version.pk == self.previous.pk, "projectionConsistent": True}
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN")

    def test_predecessor_or_new_source_change_after_preview_is_stale(self):
        preview = Service.preview_version_continuation(**self.args())
        EngineeringMaterialRequirement.objects.filter(pk=self.requirement.pk).update(net_quantity=2)
        self.rejected(lambda: self.apply(preview=preview), "DOCUMENT_CONTINUATION_STALE_PREVIEW")
        self.assertEqual(EngineeringDocumentVersion.objects.count(), 1)

    def test_predecessor_record_hash_change_after_preview_is_rejected(self):
        preview = Service.preview_version_continuation(**self.args())
        EngineeringDocumentVersion.objects.filter(pk=self.previous.pk).update(document_name="changed fixture")
        self.rejected(lambda: self.apply(preview=preview), "DOCUMENT_CONTINUATION_STALE_PREVIEW")
        self.assertEqual(EngineeringDocumentVersion.objects.count(), 1)

    def test_cross_company_predecessor_is_rejected_even_with_actor_stub(self):
        outsider = NS(pk=999, username="foreign-fixture", company_id=self.company.pk + 999,
            is_authenticated=True, is_active=True, is_superuser=False)
        with patch("pde.order_engineering_document_registration_service.AuthorizationService.decide", return_value={"allowed": True}), \
                patch("pde.order_engineering_document_registration_service._actor_chain", return_value={"account": outsider.username}):
            self.rejected(lambda: self.apply(user=outsider), "DOCUMENT_CONTINUATION_PREDECESSOR_INVALID")

    def test_multiple_same_source_versions_are_never_silently_selected(self):
        self.apply()
        EngineeringDocumentVersion.objects.create(document=self.previous.document, document_name=self.previous.document_name,
            document_version="V3.0", release_subject_type="ORDER_ENGINEERED_PRODUCT",
            order_engineering_instance=self.instance, order_engineering_baseline=self.new_baseline,
            engineering_calculation=self.current, related_bom=self.new_bom, related_routing=self.routing_version)
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_TARGET_AMBIGUOUS")

    def test_legal_independent_route_version_does_not_require_old_step_migration(self):
        route = RoutingVersion.objects.create(routing=self.routing, routing_version="V2.0", revision=2)
        operation = Process.objects.create(company=self.company, code="INDEPENDENT-DOC-OP", name="新来源正式工序")
        RoutingStep.objects.create(routing_version=route, sequence=20, operation=operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}})
        key = f"OEI:{self.instance.pk}|BASELINE:{self.new_baseline.pk}|CALC:{self.current.pk}|BOM:{self.new_bom.pk}"
        route.applicability = {"manualStepApplicability": {
            "contractVersion": "PCE-ROUTING-MANUAL-APPLICABILITY-V1.0", "contexts": {key: {"context": {
                "contextKey": key, "organizationId": self.company.pk, "salesOrderItemId": self.order_item.pk,
                "orderEngineeringInstanceId": self.instance.pk, "orderEngineeringBaselineId": self.new_baseline.pk,
                "engineeringCalculationId": self.current.pk, "bomVersionId": self.new_bom.pk,
                "routingId": self.routing.pk, "routingVersionId": route.pk}}}}}
        route.status = "released"
        route.save(update_fields=["applicability", "status"])
        result = self.apply(routing_version_id=route.pk)
        self.assertEqual(result["readback"]["engineeringDocumentVersion"]["routingVersionId"], route.pk)
        self.assertEqual(result["readback"]["engineeringDocumentVersion"]["status"], "draft")

    def test_native_predecessor_content_and_release_proof_are_required(self):
        self.patches["project_release_content_integrity"].return_value = {"valid": False}
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_PREDECESSOR_UNPROVEN")

    def test_native_0046_proof_failure_is_not_replaced_by_supersedes(self):
        from .engineering_calculation_continuation_service import EngineeringCalculationContinuationError
        self.patches["continuation_proof"].side_effect = EngineeringCalculationContinuationError("BAD_PROOF", "changed")
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_MAIN_UNPROVEN")

    def test_missing_native_0046_lineage_is_rejected(self):
        self.continuations.select_related.return_value.filter.return_value.first.return_value = None
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_LINEAGE_REQUIRED")

    def test_cross_head_route_or_bom_or_oei_is_rejected(self):
        chain = Service.resolve_chain(user=self.user, order_no=self.order.order_no, line_no=1,
            baseline_id=self.new_baseline.pk, calculation_id=self.current.pk,
            bom_version_id=self.new_bom.pk, routing_version_id=self.routing_version.pk)
        for field, value in (("routing", NS(pk=999)), ("instance", NS(pk=999)),
                ("bom_version", NS(bom_id=999))):
            with self.subTest(field=field), patch.object(Service, "resolve_chain", return_value=replace(chain, **{field: value})):
                self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_SOURCE_MISMATCH")

    def test_new_material_source_and_unreleased_bom_fail_closed(self):
        self.patches["_saved_requirement_integrity"].side_effect = ValidationError("wrong source")
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_MATERIAL_SOURCE_UNPROVEN")
        self.patches["release_readback"].return_value = {"released": False}
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_BOM_UNRELEASED")

    def test_matching_unproven_existing_candidate_is_rejected(self):
        EngineeringDocumentVersion.objects.create(document=self.previous.document, document_name=self.previous.document_name,
            document_version="V2.0", release_subject_type="ORDER_ENGINEERED_PRODUCT",
            order_engineering_instance=self.instance, order_engineering_baseline=self.new_baseline,
            engineering_calculation=self.current, related_bom=self.new_bom, related_routing=self.routing_version)
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN")

    def test_tampered_source_fingerprint_and_request_hash_are_rejected(self):
        result = self.apply()
        proof = result["creationProof"]
        original = ExternalIdentity.objects.get(pk=proof["sourceIdentityId"]).source_fingerprint
        ExternalIdentity.objects.filter(pk=proof["sourceIdentityId"]).update(source_fingerprint="wrong")
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN")
        ExternalIdentity.objects.filter(pk=proof["sourceIdentityId"]).update(source_fingerprint=original)
        MasterDataWriteRequest.objects.filter(pk=proof["actionRequestId"]).update(request_hash="wrong")
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN")

    def test_existing_version_non_lifecycle_fields_must_match_creation_audit(self):
        result = self.apply()
        version_id = result["readback"]["engineeringDocumentVersion"]["id"]
        EngineeringDocumentVersion.objects.filter(pk=version_id).update(effective_date=date.today())
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN")

    def test_revoked_permission_or_superuser_cannot_replay(self):
        self.apply()
        RolePermission.objects.filter(pk=self.permission_row.pk).delete()
        with self.assertRaises(OrderEngineeringDocumentRegistrationError):
            self.apply()
        self.user.is_superuser = True
        self.rejected(lambda: self.apply(), "DOCUMENT_CONTINUATION_BUSINESS_ACTOR_REQUIRED")

    def test_writer_failure_rolls_back_new_version_and_native_support_rows(self):
        before = self.counts()
        native = ProductionFoundationService.write
        def fail_after_write(*args, **kwargs):
            native(*args, **kwargs)
            raise ProductionFoundationError("FIXTURE_AFTER_WRITE", "rollback")
        with patch.object(ProductionFoundationService, "write", side_effect=fail_after_write):
            self.rejected(lambda: self.apply(), "FIXTURE_AFTER_WRITE")
        self.assertEqual(self.counts(), before)

    def test_explicit_wrong_route_version_is_rejected_by_original_resolver(self):
        with self.assertRaises(OrderEngineeringDocumentRegistrationError):
            self.apply(routing_version_id=self.routing_version.pk + 999)

    def test_callers_cannot_provide_version_or_status(self):
        with self.assertRaises(TypeError):
            Service.preview_version_continuation(**self.args(), document_version="V99.0")
        with self.assertRaises(TypeError):
            Service.preview_version_continuation(**self.args(), status="released")
