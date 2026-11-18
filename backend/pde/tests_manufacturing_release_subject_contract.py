from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from masterdata.models import Material, UnitOfMeasure
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import Company, Department, User

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
    ProductDefinition,
    ProductDesignItem,
    ProductManufacturingOutput,
    ProductVersion,
    Routing,
    RoutingVersion,
)
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationError
from .views import EngineeringDocumentListView


class ManufacturingReleaseSubjectContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="RSC", name="发布主体合同公司")
        cls.department = Department.objects.create(
            company=cls.company, code="RSC-PDE", name="工程部",
        )
        cls.user = User.objects.create_superuser(
            username="release_subject_tester", password="test-only",
            real_name="发布主体测试员", company_id=cls.company.pk,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="RSC-C", name="发布主体客户",
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS-RSC", name="件",
        )
        cls.finished = Material.objects.create(
            company_id=cls.company.pk, code="RSC-FG", name="订单工程产品",
            unit="件", base_uom=cls.uom, material_type="finished",
            is_produced=True, is_purchased=False,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="RSC-CAT", name="通用订单工程分类",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="RSC-PROC", name="通用制造过程",
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="RSC-SOURCE", source_name="订单工程来源",
            source_type="order_input", source_version="R1", source_payload={"source": "test"},
            content_hash="a" * 64, status="confirmed",
        )

        cls.order = SalesOrder(
            company=cls.company, department=cls.department, customer=cls.customer,
            order_no="SO-RSC-ORDER", order_date=date.today(),
            required_delivery_date=date.today(), status="engineering",
            created_by=cls.user,
            delivery_information={"businessPurpose": "DEVELOPMENT_VALIDATION"},
            external_source_no="RSC-CRM-ORDER",
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.order_item = SalesOrderItem.objects.create(
            sales_order=cls.order, line_no=1, material=cls.finished,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="订单专属产品",
            quantity=1, uom=cls.uom, required_date=date.today(),
        )
        cls.attribute = SalesOrderItemEngineeringAttribute.objects.create(
            sales_order_item=cls.order_item, sequence=1, raw_source="受控测试来源",
            raw_field="specification", raw_value={"value": "RSC"},
            canonical_field="specification", normalized_value={"value": "RSC"},
            value_type="json", source_type="ENGINEERING_INPUT", created_by=cls.user,
        )
        cls.design_item = ProductDesignItem.objects.create(
            company=cls.company, sales_order_item=cls.order_item, source_record=cls.source,
            source_attribute=cls.attribute, item_no="RSC-DES-001", item_name="订单工程设计项",
            product_category=cls.category, original_requirement={"value": "RSC"},
            existing_design_data={"value": "RSC"}, source_version="R1",
            source_content_hash="b" * 64, match_results={},
        )
        cls.instance = OrderEngineeringInstance.objects.create(
            company=cls.company, instance_no="RSC-OEI-001",
            sales_order_item=cls.order_item, product_category=cls.category,
            selected_process_type=cls.process_type, source_record=cls.source,
            status="calculated",
        )
        cls.calculation = EngineeringCalculationRecord.objects.create(
            company=cls.company, source_record=cls.source, sales_order_item=cls.order_item,
            engineering_instance=cls.instance, calculation_no="RSC-CALC-001",
            rule_set_version="RSC-RULE-V1", revision=1, result_hash="c" * 64,
            status="completed",
        )
        cls.baseline = OrderEngineeringBaseline(
            company=cls.company, sales_order=cls.order, baseline_no="RSC-BASELINE-001",
            sequence=1, status="draft", reason="发布主体合同测试",
            candidate_hash="d" * 64, snapshot_hash="e" * 64,
            scope_item_count=1, confirmable_item_count=1, blocker_count=0,
            blocker_summary={}, created_by=cls.user,
        )
        cls.baseline._business_state_initialization_authorized = True
        cls.baseline.save()
        OrderEngineeringBaselineItem.objects.create(
            baseline=cls.baseline, design_item=cls.design_item, source_record=cls.source,
            source_attribute=cls.attribute, source_type="SOURCE_CONTENT",
            item_no_snapshot=cls.design_item.item_no,
            item_name_snapshot=cls.design_item.item_name, design_item_version=1,
            source_version_snapshot="R1", source_content_hash_snapshot="b" * 64,
            content_snapshot={"value": "RSC"}, content_hash="f" * 64,
            confirmable=True,
        )
        cls.baseline.status = "confirmed"
        cls.baseline.confirmed_by = cls.user
        cls.baseline.confirmed_at = timezone.now()
        cls.baseline._business_state_transition_authorized = True
        cls.baseline._baseline_confirmation_metadata_authorized = True
        cls.baseline.save()

        cls.order_bom = ProductBOM.objects.create(
            applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
            order_engineering_instance=cls.instance, company=cls.company,
            bom_code="RSC-ORDER-BOM", name="订单工程BOM",
        )
        cls.order_bom_version = BOMVersion.objects.create(
            bom=cls.order_bom, bom_version="R1", bom_scope="order_specific",
            order_engineering_instance=cls.instance, source_calculation=cls.calculation,
        )
        cls.category_routing = Routing.objects.create(
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
            product_category=cls.category, manufacturing_process_type=cls.process_type,
            company=cls.company, routing_code="RSC-ROUTE", name="通用分类工艺",
        )
        cls.category_routing_version = RoutingVersion.objects.create(
            routing=cls.category_routing, routing_version="R1",
        )
        cls.order_document = EngineeringDocument(
            document_no="RSC-ORDER-DOC", document_name="订单工程资料",
            document_type="technical",
            release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            order_engineering_instance=cls.instance,
            product_bom=cls.order_bom, routing=cls.category_routing,
        )
        cls.order_document.full_clean()
        cls.order_document.save()
        cls.order_document_version = EngineeringDocumentVersion(
            document=cls.order_document, document_name="订单工程资料",
            document_version="R1",
            release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            order_engineering_instance=cls.instance,
            order_engineering_baseline=cls.baseline,
            engineering_calculation=cls.calculation,
            related_bom=cls.order_bom_version,
            related_routing=cls.category_routing_version,
        )
        cls.order_document_version.full_clean()
        cls.order_document_version.save()

        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.finished,
            product_code="RSC-PRODUCT", product_name="长期产品",
            emd_material_code=cls.finished.code,
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="V1",
        )
        cls.standard_bom = ProductBOM.objects.create(
            company=cls.company, product=cls.product,
            bom_code="RSC-STANDARD-BOM", name="长期产品BOM",
        )
        cls.standard_bom_version = BOMVersion.objects.create(
            bom=cls.standard_bom, product=cls.product,
            product_version=cls.product_version, bom_version="V1",
        )
        cls.standard_routing = Routing.objects.create(
            company=cls.company, product=cls.product,
            routing_code="RSC-STANDARD-ROUTE", name="长期产品工艺",
        )
        cls.standard_routing_version = RoutingVersion.objects.create(
            routing=cls.standard_routing, product=cls.product,
            product_version=cls.product_version, routing_version="V1",
        )
        cls.standard_document = EngineeringDocument.objects.create(
            document_no="RSC-STANDARD-DOC", document_name="长期产品资料",
            document_type="technical", product=cls.product,
            product_bom=cls.standard_bom, routing=cls.standard_routing,
        )
        cls.standard_document_version = EngineeringDocumentVersion.objects.create(
            document=cls.standard_document, document_name="长期产品资料",
            document_version="V1", product_version=cls.product_version,
            related_product=cls.product, related_bom=cls.standard_bom_version,
            related_routing=cls.standard_routing_version,
        )

    def _order_output(self, **overrides):
        values = {
            "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            "definition_mode": "order_specific",
            "order_engineering_instance": self.instance,
            "order_engineering_baseline": self.baseline,
            "engineering_calculation": self.calculation,
            "bom_version": self.order_bom_version,
            "routing_version": self.category_routing_version,
            "engineering_document_version": self.order_document_version,
            "engineering_status": "ready",
        }
        values.update(overrides)
        return ProductManufacturingOutput(**values)

    def _long_term_output(self, **overrides):
        values = {
            "release_subject_type": ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
            "definition_mode": "standard",
            "product": self.product,
            "product_version": self.product_version,
            "bom_version": self.standard_bom_version,
            "routing_version": self.standard_routing_version,
            "engineering_document_version": self.standard_document_version,
            "engineering_status": "ready",
        }
        values.update(overrides)
        return ProductManufacturingOutput(**values)

    def test_a_long_term_product_subject_remains_valid(self):
        self._long_term_output().full_clean()

    def test_b_category_only_oei_with_frozen_baseline_and_revision_is_valid(self):
        output = self._order_output()
        output.full_clean()
        self.assertIsNone(output.product_id)
        self.assertIsNone(output.product_version_id)

    def test_c_category_only_without_oei_is_rejected_by_database_contract(self):
        output = self._order_output(order_engineering_instance=None)
        with self.assertRaises(ValidationError):
            output.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            output.save()

    def test_d_both_release_subjects_are_rejected(self):
        output = self._order_output(product=self.product, product_version=self.product_version)
        with self.assertRaises(ValidationError):
            output.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            output.save()

    def test_e_missing_release_subject_is_rejected(self):
        output = self._long_term_output(product=None, product_version=None)
        with self.assertRaises(ValidationError):
            output.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            output.save()

    def test_f_cross_company_version_reference_is_rejected(self):
        other_company = Company.objects.create(code="RSC2", name="跨公司引用测试")
        other_uom = UnitOfMeasure.objects.create(
            company_id=other_company.pk, code="PCS-RSC2", name="件",
        )
        other_material = Material.objects.create(
            company_id=other_company.pk, code="RSC2-FG", name="跨公司产品",
            unit="件", base_uom=other_uom, material_type="finished",
            is_produced=True, is_purchased=False,
        )
        other_product = ProductDefinition.objects.create(
            company=other_company, material=other_material,
            product_code="RSC2-P", product_name="跨公司产品",
            emd_material_code=other_material.code,
        )
        other_version = ProductVersion.objects.create(product=other_product, version_no="V1")
        output = self._long_term_output(product_version=other_version)
        with self.assertRaises(ValidationError):
            output.full_clean()

    def test_g_bom_routing_document_or_baseline_mismatch_is_rejected(self):
        output = self._order_output(engineering_calculation=None)
        with self.assertRaises(ValidationError):
            output.full_clean()
        long_output = self._long_term_output(bom_version=self.order_bom_version)
        with self.assertRaises(ValidationError):
            long_output.full_clean()

    def test_h_development_validation_identity_is_valid_but_formal_review_is_blocked(self):
        output = self._order_output()
        output.full_clean()
        output.save()
        with self.assertRaises(ProductionFoundationError) as caught:
            EngineeringLifecycleService.transition(
                "manufacturing-outputs", object_id=output.pk,
                target_status="engineering_review", user=self.user,
            )
        self.assertEqual(
            caught.exception.code,
            "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
        )

    def test_i_inactive_order_engineering_instance_is_rejected(self):
        OrderEngineeringInstance.objects.filter(pk=self.instance.pk).update(status="inactive")
        self.instance.refresh_from_db()
        with self.assertRaises(ValidationError):
            self._order_output(order_engineering_instance=self.instance).full_clean()

    def test_j_released_record_cannot_change_subject_or_versions_in_place(self):
        output = self._order_output()
        output.full_clean()
        output.save()
        ProductManufacturingOutput.objects.filter(pk=output.pk).update(
            release_status="released_to_manufacturing",
        )
        output.refresh_from_db()
        output.release_subject_type = ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT
        with self.assertRaises(ValidationError):
            output.save()

    def test_k_node11_document_scope_counts_only_traceable_versions(self):
        facts = EngineeringDocumentListView._document_scope_facts(self.instance)
        self.assertEqual(len(facts["documents"]), 1)
        self.assertEqual(len(facts["versionCandidates"]), 1)
        self.assertEqual(len(facts["traceableVersions"]), 1)
        self.assertEqual(len(facts["publishableVersions"]), 0)
        self.assertEqual(len(facts["releasedVersions"]), 0)
        self.assertEqual(facts["ownershipConflicts"], [])

    def test_l_node11_document_ownership_conflict_fails_closed(self):
        EngineeringDocumentVersion.objects.filter(
            pk=self.order_document_version.pk,
        ).update(document=self.standard_document)

        facts = EngineeringDocumentListView._document_scope_facts(self.instance)

        self.assertEqual(len(facts["versionCandidates"]), 1)
        self.assertEqual(len(facts["traceableVersions"]), 0)
        self.assertEqual(len(facts["publishableVersions"]), 0)
        self.assertEqual(len(facts["releasedVersions"]), 0)
        self.assertEqual(len(facts["ownershipConflicts"]), 1)
        self.assertIn("冲突", facts["ownershipConflicts"][0])
