from datetime import date
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import Material
from sales.models import Customer, SalesOrder, SalesOrderItem
from system.models import Company, Department, User

from .manufacturing_structure_service import (
    ManufacturingStructureError,
    ManufacturingStructureService,
)
from .models import (
    BOMVersion,
    EngineeringSourceRecord,
    ManufacturingApplicabilityScope,
    ManufacturingProcessType,
    OrderEngineeringInstance,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingVersion,
)


class ManufacturingDefinitionApplicabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="G3", name="G3隔离测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="D1", name="销售部",
        )
        cls.user = User.objects.create_user(
            username="g3-test", password="x", real_name="G3测试",
            company_id=cls.company.pk,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="C1", name="隔离客户",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="M1", name="订单工程占位物料",
            unit="件", unit_status="confirmed", material_type="finished",
            is_produced=True,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="DOOR", name="房门",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="CLEAR", name="清水开放",
        )
        cls.order = SalesOrder(
            company=cls.company, department=cls.department, customer=cls.customer,
            order_no="SO-G3-1", order_date=date.today(),
            required_delivery_date=date.today(), status="draft", created_by=cls.user,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.order_item = SalesOrderItem.objects.create(
            sales_order=cls.order, line_no=1, material=cls.material,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="客制房门",
            quantity=1, required_date=date.today(),
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="SRC-G3-1", source_name="隔离来源",
            source_type="order_input", source_version="1", source_payload={},
            content_hash="0" * 64, status="confirmed",
        )

    def _category_route(self, code="R-CATEGORY"):
        route = Routing(
            company=self.company, routing_code=code, name=code,
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
            product_category=self.category,
            manufacturing_process_type=self.process_type,
            status="released",
        )
        route.full_clean()
        route.save()
        version = RoutingVersion(
            routing=route, routing_version="V1", status="released",
            approval_state="workflow_approved",
        )
        version.full_clean()
        version.save()
        return route, version

    def _order_instance(self):
        instance = OrderEngineeringInstance(
            company=self.company, instance_no="OEI-G3-1",
            sales_order_item=self.order_item, product_category=self.category,
            selected_process_type=self.process_type, source_record=self.source,
            status="source_confirmed",
        )
        instance.full_clean()
        instance.save()
        return instance

    def test_exactly_one_target_is_required(self):
        invalid = Routing(
            company=self.company, routing_code="INVALID", name="INVALID",
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
            manufacturing_process_type=self.process_type,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_order_engineered_instance_resolves_category_route(self):
        route, version = self._category_route()
        result = ManufacturingStructureService.resolve_effective_routing(
            self._order_instance(),
        )
        self.assertEqual(result["routing"], route)
        self.assertEqual(result["routing_version"], version)
        self.assertEqual(result["resolved_scope"], "PRODUCT_CATEGORY")
        self.assertEqual(ProductDefinition.objects.count(), 0)
        self.assertEqual(ProductVersion.objects.count(), 0)

    def test_zero_match_is_explicitly_blocked(self):
        instance = self._order_instance()
        with self.assertRaises(ManufacturingStructureError) as raised:
            ManufacturingStructureService.resolve_effective_routing(instance)
        self.assertEqual(raised.exception.code, "NO_EFFECTIVE_ROUTING")

    def test_duplicate_category_process_route_is_blocked_before_resolution(self):
        self._category_route("R-CATEGORY-1")
        with self.assertRaises(ValidationError):
            self._category_route("R-CATEGORY-2")

    def test_order_specific_route_has_priority(self):
        self._category_route()
        instance = self._order_instance()
        route = Routing(
            company=self.company, routing_code="R-ORDER", name="订单专用",
            applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
            order_engineering_instance=instance, status="released",
        )
        route.full_clean()
        route.save()
        version = RoutingVersion(
            routing=route, routing_version="V1", status="released",
            approval_state="workflow_approved",
        )
        version.full_clean()
        version.save()
        result = ManufacturingStructureService.resolve_effective_routing(instance)
        self.assertEqual(result["routing"], route)
        self.assertEqual(result["resolved_scope"], "ORDER_ENGINEERING")

    def test_standard_product_route_remains_compatible_and_drift_is_rejected(self):
        product = ProductDefinition.objects.create(
            company=self.company, category=self.category, material=self.material,
            product_code="P1", product_name="标准房门", emd_material_code="M1",
            manufacturing_definition_mode="standard",
        )
        product_version = ProductVersion.objects.create(product=product, version_no="V1")
        route = Routing(
            company=self.company, routing_code="R-PRODUCT", name="标准产品路线",
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
            product=product, manufacturing_process_type=self.process_type,
            status="released",
        )
        route.full_clean()
        route.save()
        version = RoutingVersion(
            routing=route, product=product, product_version=product_version,
            routing_version="V1", status="released", approval_state="workflow_approved",
        )
        version.full_clean()
        version.save()
        result = ManufacturingStructureService.resolve_effective_routing(SimpleNamespace(
            pk=None, company_id=self.company.pk, product_id=product.pk,
            product=product, product_category_id=self.category.pk,
            selected_process_type_id=self.process_type.pk,
        ))
        self.assertEqual(result["resolved_scope"], "PRODUCT_DEFINITION")
        drift = RoutingVersion(
            routing=route, routing_version="V2", status="draft",
        )
        with self.assertRaises(ValidationError):
            drift.full_clean()

    def test_bom_uses_same_header_applicability_contract(self):
        bom = ProductBOM(
            company=self.company, bom_code="B-CATEGORY", name="分类BOM",
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
            product_category=self.category,
        )
        bom.full_clean()
        bom.save()
        version = BOMVersion(bom=bom, bom_version="V1", status="draft")
        version.full_clean()
        version.save()
        self.assertIsNone(version.product_id)
        self.assertIsNone(version.product_version_id)

    def test_standard_product_can_be_customer_engineering_baseline(self):
        product = ProductDefinition.objects.create(
            company=self.company, category=self.category, material=self.material,
            product_code="P-STANDARD-BASE", product_name="标准产品基线",
            emd_material_code=self.material.code,
            manufacturing_definition_mode="standard", status="released",
        )
        version = ProductVersion.objects.create(
            product=product, version_no="V1", version_status="released",
        )
        instance = OrderEngineeringInstance(
            company=self.company, instance_no="OEI-STANDARD-BASE",
            sales_order_item=self.order_item, product=product,
            baseline_product_version=version, product_category=self.category,
            source_record=self.source, status="source_confirmed",
        )
        instance.full_clean()
        instance.save()
        self.assertEqual(instance.product_id, product.pk)
        self.assertEqual(instance.baseline_product_version_id, version.pk)

    def test_standard_and_order_configured_bom_scopes_cannot_cross(self):
        product = ProductDefinition.objects.create(
            company=self.company, category=self.category, material=self.material,
            product_code="P-BOM-BOUNDARY", product_name="BOM边界产品",
            emd_material_code=self.material.code, status="released",
        )
        product_version = ProductVersion.objects.create(
            product=product, version_no="V1", version_status="released",
        )
        standard_header = ProductBOM(
            company=self.company, bom_code="B-STANDARD", name="标准BOM",
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
            product=product,
        )
        standard_header.full_clean()
        standard_header.save()
        standard_version = BOMVersion(
            bom=standard_header, product=product, product_version=product_version,
            bom_version="V1", bom_scope="standard", status="draft",
        )
        standard_version.full_clean()
        standard_version.save()

        instance = self._order_instance()
        order_header = ProductBOM(
            company=self.company, bom_code="B-ORDER", name="订单配置BOM",
            applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
            order_engineering_instance=instance,
        )
        order_header.full_clean()
        order_header.save()
        order_version = BOMVersion(
            bom=order_header, bom_version="O1", bom_scope="order_specific",
            order_engineering_instance=instance, status="draft",
        )
        order_version.full_clean()
        order_version.save()

        invalid_cross_scope = BOMVersion(
            bom=standard_header, product=product, product_version=product_version,
            bom_version="INVALID", bom_scope="order_specific",
            order_engineering_instance=instance, status="draft",
        )
        with self.assertRaises(ValidationError):
            invalid_cross_scope.full_clean()
        self.assertEqual(standard_header.versions.count(), 1)
        self.assertEqual(order_header.versions.count(), 1)
