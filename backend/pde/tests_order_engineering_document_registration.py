from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure
from pfm.models import Employee
from sales.models import (
    Customer,
    SalesOrder,
    SalesOrderItem,
    SalesOrderItemEngineeringAttribute,
)
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Position,
    PositionResponsibility,
    Process,
    Responsibility,
    User,
)

from .models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocument,
    EngineeringDocumentVersion,
    EngineeringSourceRecord,
    ManufacturingApplicabilityScope,
    ManufacturingProcessType,
    ManufacturingReleaseSubjectType,
    OrderEngineeringBaseline,
    OrderEngineeringBaselineItem,
    OrderEngineeringInstance,
    ProductBOM,
    ProductCategory,
    ProductDesignItem,
    ProductManufacturingOutput,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from .order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationError,
    OrderEngineeringDocumentRegistrationService,
)
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationError
from .views import EngineeringDocumentListView


class OrderEngineeringDocumentRegistrationTests(TestCase):
    document_no = "ED-REG-ORDER-001"
    document_name = "订单工程工艺技术资料"

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="EDREG", name="工程资料登记测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="EDREG-PDE", name="工程部",
        )
        cls.user = User.objects.create_superuser(
            username="ed_registration_engineer",
            password="test-only",
            real_name="工程资料登记员",
            company_id=cls.company.pk,
        )
        responsibility = Responsibility.objects.create(
            code="RESP_ED_REGISTRATION", name="工程资料登记职责",
            status="ACTIVE", is_active=True,
        )
        position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="EDREG-ENGINEER", name="工程资料登记岗",
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility,
            is_primary=True, active=True,
        )
        Employee.objects.create(
            user=cls.user, employee_no="EDREG-E001", full_name="工程资料登记员",
            department_ref=cls.department, position_ref=position, status="active",
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="EDREG-C", name="工程资料客户",
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS-EDREG", name="件",
        )
        cls.finished = Material.objects.create(
            company_id=cls.company.pk, code="EDREG-FG", name="订单工程成品",
            unit="件", base_uom=cls.uom, material_type="finished",
            is_produced=True, is_purchased=False,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="EDREG-CAT", name="订单工程产品分类",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="EDREG-PROC", name="订单工程工艺类型",
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="EDREG-SOURCE", source_name="工程来源",
            source_type="order_input", source_version="R1",
            source_payload={"source": "test"}, content_hash="a" * 64,
            status="confirmed",
        )
        cls.order = SalesOrder(
            company=cls.company, department=cls.department, customer=cls.customer,
            order_no="SO-ED-REG-001", order_date=date.today(),
            required_delivery_date=date.today(), status="engineering",
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            created_by=cls.user,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.order_item = SalesOrderItem.objects.create(
            sales_order=cls.order, line_no=1, material=cls.finished,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="订单工程产品",
            quantity=1, uom=cls.uom, required_date=date.today(),
        )
        cls.attribute = SalesOrderItemEngineeringAttribute.objects.create(
            sales_order_item=cls.order_item, sequence=1, raw_source="受控测试来源",
            raw_field="specification", raw_value={"value": "EDREG"},
            canonical_field="specification", normalized_value={"value": "EDREG"},
            value_type="json", source_type="ENGINEERING_INPUT", created_by=cls.user,
        )
        cls.design_item = ProductDesignItem.objects.create(
            company=cls.company, sales_order_item=cls.order_item,
            source_record=cls.source, source_attribute=cls.attribute,
            item_no="EDREG-DES-001", item_name="订单工程设计项",
            product_category=cls.category,
            original_requirement={"value": "EDREG"},
            existing_design_data={"value": "EDREG"},
            source_version="R1", source_content_hash="b" * 64,
            match_results={},
        )
        cls.instance = OrderEngineeringInstance.objects.create(
            company=cls.company, instance_no="EDREG-OEI-001",
            sales_order_item=cls.order_item, product_category=cls.category,
            selected_process_type=cls.process_type, source_record=cls.source,
            status="calculated",
        )
        cls.calculation = EngineeringCalculationRecord.objects.create(
            company=cls.company, source_record=cls.source,
            sales_order_item=cls.order_item, engineering_instance=cls.instance,
            calculation_no="EDREG-CALC-001", rule_set_version="EDREG-RULE-V1",
            revision=1, result_hash="c" * 64, status="completed",
        )
        cls.baseline = OrderEngineeringBaseline(
            company=cls.company, sales_order=cls.order,
            baseline_no="EDREG-BASELINE-001", sequence=1, status="draft",
            reason="工程资料登记测试", candidate_hash="d" * 64,
            snapshot_hash="e" * 64, scope_item_count=1,
            confirmable_item_count=1, blocker_count=0, blocker_summary={},
            created_by=cls.user,
        )
        cls.baseline._business_state_initialization_authorized = True
        cls.baseline.save()
        OrderEngineeringBaselineItem.objects.create(
            baseline=cls.baseline, design_item=cls.design_item,
            source_record=cls.source, source_attribute=cls.attribute,
            source_type="SOURCE_CONTENT", item_no_snapshot=cls.design_item.item_no,
            item_name_snapshot=cls.design_item.item_name, design_item_version=1,
            source_version_snapshot="R1", source_content_hash_snapshot="b" * 64,
            content_snapshot={"value": "EDREG"}, content_hash="f" * 64,
            confirmable=True,
        )
        cls.baseline.status = "confirmed"
        cls.baseline.confirmed_by = cls.user
        cls.baseline.confirmed_at = timezone.now()
        cls.baseline._business_state_transition_authorized = True
        cls.baseline._baseline_confirmation_metadata_authorized = True
        cls.baseline.save()
        cls.bom = ProductBOM.objects.create(
            applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
            order_engineering_instance=cls.instance, company=cls.company,
            bom_code="EDREG-OBOM", name="按单BOM",
        )
        cls.bom_version = BOMVersion.objects.create(
            bom=cls.bom, bom_version="CALC-EDREG", revision=1,
            bom_scope="order_specific", order_engineering_instance=cls.instance,
            source_calculation=cls.calculation, status="draft",
        )
        cls.routing = Routing.objects.create(
            applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
            order_engineering_instance=cls.instance, company=cls.company,
            routing_code="EDREG/ROUTE", name="订单工程工艺路线",
            status="released", is_active=True,
        )
        cls.routing_version = RoutingVersion.objects.create(
            routing=cls.routing, routing_version="SYSTEM_INITIAL_VERSION",
            revision=1, status="draft",
        )
        cls.operation = Process.objects.create(
            company=cls.company, code="EDREG-OP", name="工程资料登记工序",
        )
        RoutingStep.objects.create(
            routing_version=cls.routing_version, sequence=10,
            operation=cls.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        cls.routing_version.status = "released"
        cls.routing_version.save(update_fields=("status", "updated_at"))

    def setUp(self):
        admission_patcher = patch(
            "pde.order_engineering_document_registration_service.require_current_order_admission",
            return_value=SimpleNamespace(mode="TEST_FORMAL_ADMISSION"),
        )
        self.addCleanup(admission_patcher.stop)
        admission_patcher.start()

    def _common(self, **overrides):
        values = {
            "user": self.user,
            "order_no": self.order.order_no,
            "line_no": 1,
            "document_no": self.document_no,
            "document_name": self.document_name,
            "document_type": "technical",
        }
        values.update(overrides)
        return values

    def _register(self, key="ed-registration-request-001"):
        return OrderEngineeringDocumentRegistrationService.register(
            **self._common(), idempotency_key=key,
            reason="用户确认的订单工程资料主表与首版草稿正式登记",
        )

    def test_01_preflight_resolves_unique_chain_and_order_subject(self):
        result = OrderEngineeringDocumentRegistrationService.preflight(**self._common())
        self.assertEqual(result["chain"]["orderEngineeringInstance"]["id"], self.instance.pk)
        self.assertEqual(result["chain"]["engineeringBaseline"]["id"], self.baseline.pk)
        self.assertEqual(result["chain"]["engineeringCalculation"]["id"], self.calculation.pk)
        self.assertEqual(result["chain"]["bomVersion"]["id"], self.bom_version.pk)
        self.assertEqual(result["chain"]["routingVersion"]["id"], self.routing_version.pk)
        self.assertEqual(
            result["chain"]["releaseSubjectType"],
            ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
        )

    def test_02_registers_exact_engineering_document_header(self):
        result = self._register()
        document = EngineeringDocument.objects.get(document_no=self.document_no)
        self.assertEqual(result["outcome"], "PASS")
        self.assertEqual(document.document_name, self.document_name)
        self.assertEqual(document.document_type, "technical")
        self.assertEqual(document.release_subject_type, "ORDER_ENGINEERED_PRODUCT")
        self.assertEqual(document.order_engineering_instance_id, self.instance.pk)
        self.assertEqual(document.product_bom_id, self.bom.pk)
        self.assertEqual(document.routing_id, self.routing.pk)
        self.assertEqual(document.status, "draft")

    def test_03_canonical_service_generates_v10_draft_with_exact_bindings(self):
        self._register()
        version = EngineeringDocumentVersion.objects.get(document__document_no=self.document_no)
        self.assertEqual(version.document_version, "V1.0")
        self.assertEqual(version.status, "draft")
        self.assertEqual(version.order_engineering_instance_id, self.instance.pk)
        self.assertEqual(version.order_engineering_baseline_id, self.baseline.pk)
        self.assertEqual(version.engineering_calculation_id, self.calculation.pk)
        self.assertEqual(version.related_bom_id, self.bom_version.pk)
        self.assertEqual(version.related_routing_id, self.routing_version.pk)

    def test_04_document_number_collision_fails_closed_before_write(self):
        EngineeringDocument.objects.create(
            document_no=self.document_no, document_name="冲突资料",
            document_type="technical",
            release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            order_engineering_instance=self.instance,
            product_bom=self.bom, routing=self.routing,
        )
        with self.assertRaises(OrderEngineeringDocumentRegistrationError) as caught:
            self._register()
        self.assertEqual(caught.exception.outcome, "BLOCKED_BEFORE_WRITE")
        self.assertEqual(caught.exception.code, "DOCUMENT_NUMBER_CONFLICT")
        self.assertEqual(EngineeringDocument.objects.filter(document_no=self.document_no).count(), 1)
        self.assertEqual(EngineeringDocumentVersion.objects.count(), 0)

    def test_05_repeat_request_is_idempotent(self):
        first = self._register()
        second = self._register()
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(EngineeringDocument.objects.filter(document_no=self.document_no).count(), 1)
        self.assertEqual(EngineeringDocumentVersion.objects.filter(document__document_no=self.document_no).count(), 1)
        self.assertEqual(ExternalIdentity.objects.count(), 2)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 2)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 2)

    def test_06_bom_draft_and_released_routing_are_unchanged(self):
        self._register()
        self.bom_version.refresh_from_db()
        self.routing.refresh_from_db()
        self.routing_version.refresh_from_db()
        self.assertEqual(self.bom_version.status, "draft")
        self.assertEqual(self.routing.status, "released")
        self.assertEqual(self.routing_version.status, "released")
        self.assertEqual(self.routing_version.steps.count(), 1)

    def test_07_registration_never_calls_review_or_release_transition(self):
        with patch.object(EngineeringLifecycleService, "transition") as transition:
            result = self._register()
        transition.assert_not_called()
        self.assertFalse(result["readback"]["reviewExecuted"])
        self.assertFalse(result["readback"]["publicationExecuted"])
        self.assertFalse(result["readback"]["ecnEntered"])

    def test_08_registration_never_creates_manufacturing_output(self):
        before = ProductManufacturingOutput.objects.count()
        result = self._register()
        self.assertEqual(ProductManufacturingOutput.objects.count(), before)
        self.assertEqual(result["beforeCounts"]["productManufacturingOutput"], 0)
        self.assertEqual(result["afterCounts"]["productManufacturingOutput"], 0)
        self.assertFalse(result["readback"]["manufacturingPublicationExecuted"])

    def test_09_node11_readback_exposes_registered_draft_not_publication(self):
        self._register()
        with patch(
            "pde.views.FormalManufacturingEligibilityService.resolve",
            return_value={
                "formalManufacturingEligible": True,
                "message": "",
                "businessPurposeLabel": "正式销售订单",
                "statusLabel": "正式制造资格已具备",
            },
        ):
            row = EngineeringDocumentListView._serialize_release_candidate(
                self.instance,
                release_subject_schema_available=True,
                admission={"status": "valid"},
            )
        self.assertEqual(row["engineeringDocumentCount"], 1)
        self.assertEqual(row["engineeringDocumentVersionCount"], 1)
        self.assertEqual(row["documentNo"], self.document_no)
        self.assertEqual(row["documentName"], self.document_name)
        self.assertEqual(row["documentTypeLabel"], "技术资料")
        self.assertEqual(row["version"], "V1.0")
        self.assertEqual(row["documentVersionStatusLabel"], "草稿")
        self.assertEqual(row["publishableEngineeringDocumentCount"], 0)
        self.assertEqual(row["releasedEngineeringDocumentCount"], 0)
        self.assertFalse(row["publicationExecutedThisRound"])

    def test_10_version_failure_retains_header_and_reports_partial_write(self):
        from .production_foundation_service import ProductionFoundationService

        canonical_write = ProductionFoundationService.write
        calls = {"count": 0}

        def fail_second(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise ProductionFoundationError("VERSION_WRITE_FAILED", "首版写入测试失败")
            return canonical_write(*args, **kwargs)

        with patch.object(ProductionFoundationService, "write", side_effect=fail_second):
            with self.assertRaises(OrderEngineeringDocumentRegistrationError) as caught:
                self._register()
        self.assertEqual(caught.exception.outcome, "PARTIAL_WRITE")
        self.assertEqual(EngineeringDocument.objects.filter(document_no=self.document_no).count(), 1)
        self.assertEqual(EngineeringDocumentVersion.objects.count(), 0)

    def test_11_non_released_route_fails_before_target_write(self):
        RoutingVersion.objects.filter(pk=self.routing_version.pk).update(status="draft")
        with self.assertRaises(OrderEngineeringDocumentRegistrationError) as caught:
            self._register()
        self.assertEqual(caught.exception.outcome, "BLOCKED_BEFORE_WRITE")
        self.assertEqual(EngineeringDocument.objects.count(), 0)
        self.assertEqual(EngineeringDocumentVersion.objects.count(), 0)

    def test_12_exact_context_selects_released_successor_and_reports_stale_draft_binding(self):
        BOMVersion.objects.filter(pk=self.bom_version.pk).update(status="released")
        self.bom_version.refresh_from_db()
        self._register()
        historical_document_version = EngineeringDocumentVersion.objects.get(
            document__document_no=self.document_no,
        )
        self.assertEqual(historical_document_version.related_routing_id, self.routing_version.pk)

        successor = RoutingVersion.objects.create(
            routing=self.routing, routing_version="V2.0", revision=2,
            status="draft", applicability={},
        )
        RoutingStep.objects.create(
            routing_version=successor, sequence=10, operation=self.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        context_key = (
            f"OEI:{self.instance.pk}|BASELINE:{self.baseline.pk}|"
            f"CALC:{self.calculation.pk}|BOM:{self.bom_version.pk}"
        )
        snapshot = {
            "contextKey": context_key,
            "organizationId": self.company.pk,
            "salesOrderItemId": self.order_item.pk,
            "orderEngineeringInstanceId": self.instance.pk,
            "orderEngineeringBaselineId": self.baseline.pk,
            "engineeringCalculationId": self.calculation.pk,
            "bomVersionId": self.bom_version.pk,
            "routingId": self.routing.pk,
            "routingVersionId": successor.pk,
        }
        successor.applicability = {
            "manualStepApplicability": {
                "contractVersion": "PCE-ROUTING-MANUAL-APPLICABILITY-V1.0",
                "contexts": {
                    context_key: {"context": snapshot, "decisions": {}},
                },
            },
        }
        successor.save(update_fields=("applicability", "updated_at"))
        RoutingVersion.objects.filter(pk=successor.pk).update(status="released")
        successor.refresh_from_db()

        chain = OrderEngineeringDocumentRegistrationService.resolve_chain(
            user=self.user, order_no=self.order.order_no, line_no=1,
        )
        self.assertEqual(chain.routing_version.pk, successor.pk)

        with patch(
            "pde.views.FormalManufacturingEligibilityService.resolve",
            return_value={
                "formalManufacturingEligible": True,
                "message": "",
                "businessPurposeLabel": "正式销售订单",
                "statusLabel": "正式制造资格已具备",
            },
        ):
            row = EngineeringDocumentListView._serialize_release_candidate(
                self.instance,
                release_subject_schema_available=True,
                admission={"status": "valid"},
            )
        self.assertEqual(row["routingVersionId"], successor.pk)
        self.assertEqual(row["routingVersionNo"], "V2.0")
        self.assertIn(
            f"工程资料版本ID {historical_document_version.pk}仍绑定历史工艺路线版本ID "
            f"{self.routing_version.pk}；当前准确已发布版本为ID {successor.pk}",
            row["formalMissingConditions"],
        )
        self.assertFalse(row["publicationExecutedThisRound"])

