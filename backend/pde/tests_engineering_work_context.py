from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, Permission, Position, PositionResponsibility,
    Process, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)

from . import calculation_batch_reuse
from .calculation_batch_views import EngineeringCalculationBatchView
from .engineering_calculation_service import EngineeringCalculationError
from .engineering_work_context import (
    build_engineering_input_options, build_production_plan_projection,
    normalize_confirmed_business_facts, normalize_draft_context,
)
from .models import (
    EngineeringBreakdownOption, EngineeringSourceRecord, OrderEngineeringInstance, ProductCategory,
    ProductDefinition, ProductDesignItem, ProductVersion, Routing, RoutingStep, RoutingVersion,
)
from .production_foundation_service import ProductionFoundationService


class ProductDesignCalculationAdapterTests(SimpleTestCase):
    def test_confirmed_baseline_match_is_explicit_but_does_not_invent_formal_binding(self):
        relationship = calculation_batch_reuse._baseline_relationship_from_facts({
            "candidateBaseline": {
                "candidateId": "candidate-002", "orderNo": "SO-002", "designItemCount": 71,
            },
            "savedBaselines": [{
                "baselineId": 2, "baselineNo": "EB-SO-002-002", "candidateId": "candidate-002",
                "statusCode": "confirmed", "statusLabel": "已确认",
            }],
            "diffFacts": {
                "statusCode": "NO_CHANGE", "comparedBaselineId": 2,
                "comparedBaselineNo": "EB-SO-002-002", "added": [], "changed": [], "removed": [],
            },
        })

        self.assertEqual(relationship["statusCode"], "MATCHES_CONFIRMED_BASELINE")
        self.assertTrue(relationship["inputMatchesConfirmedBaseline"])
        self.assertFalse(relationship["formalCalculationBaselineBound"])
        self.assertIn("71项", relationship["statusLabel"])
        self.assertIn("不等于", relationship["bindingStatusLabel"])

    def test_changed_current_input_keeps_baseline_and_lists_changed_objects(self):
        relationship = calculation_batch_reuse._baseline_relationship_from_facts({
            "candidateBaseline": {"candidateId": "candidate-new", "orderNo": "SO-002"},
            "savedBaselines": [{
                "baselineId": 2, "baselineNo": "EB-SO-002-002", "candidateId": "candidate-002",
                "statusCode": "confirmed", "statusLabel": "已确认",
            }],
            "diffFacts": {
                "statusCode": "CHANGED", "comparedBaselineId": 2,
                "comparedBaselineNo": "EB-SO-002-002", "added": [],
                "changed": ["SO-DES-01"], "removed": [],
            },
        })

        self.assertEqual(relationship["statusCode"], "CURRENT_INPUT_CHANGED_AFTER_BASELINE")
        self.assertEqual(relationship["changedItemNos"], ["SO-DES-01"])
        self.assertFalse(relationship["inputMatchesConfirmedBaseline"])

    def test_work_order_projection_uses_design_facts_and_keeps_room_door_wall_thickness_semantics(self):
        source = [{
            "id": "SOURCE-XLSX-房门单-11", "sourceSheet": "房门单", "sourceRow": 11,
            "product": "房门", "component": "单开门", "quantity": 1, "unit": "",
            "length": 2045, "width": 938, "thickness": 265,
            "materialProcessCode": "QSFB4601001", "routingProcessCode": "QSFB/FM",
        }]
        design = [{
            "sourceKey": "房门单:11", "sourceSheet": "房门单", "sourceRow": 11,
            "designItemId": 1, "designItemNo": "SO-DES-01", "itemName": "单开门",
            "productCategoryName": "房门", "physicalQuantity": 1,
            "physicalUomName": "扇", "physicalUomMatchStatus": "EXACT",
            "designLength": 2045, "designWidth": 938, "designThickness": 265,
            "dimensionSemantics": [
                {"key": "designLength", "label": "门洞/门套高", "value": 2045},
                {"key": "designWidth", "label": "门洞/门套宽", "value": 938},
                {"key": "designThickness", "label": "墙厚", "value": 265},
            ],
            "sourceMaterialCode": "QSFB4601001", "materialId": None,
            "sourceRoutingProcessCode": "QSFB/FM", "inputAuthority": "ProductDesignItem 已有设计资料",
        }]

        projected = calculation_batch_reuse._work_order_rows(source, design)[0]

        self.assertEqual(projected["unit"], "扇")
        self.assertEqual(projected["dimensionSemantics"][2]["label"], "墙厚")
        self.assertEqual(projected["edgeStatusLabel"], "本业务不适用")
        self.assertEqual(projected["visibleStatusLabel"], "本业务不适用")
        self.assertIn("来源材料编码尚未匹配正式材料主数据", projected["remainingConfirmations"])
        self.assertNotIn("封边方式", projected["remainingConfirmations"])

    def test_one_design_input_change_only_changes_its_current_results_and_preserves_baseline(self):
        keys = ["三合一生产单:7", "三合一生产单:8"]
        source = calculation_batch_reuse.load_source()
        available = {f"{row['sheet']}:{row['row']}": row for row in source["realRows"]}
        row = available[keys[0]]
        design_input = {
            "designItemId": 7001,
            "designItemNo": "ISOLATED-DESIGN-7001",
            "sourceKey": keys[0],
            "designLength": calculation_batch_reuse.cell_value(row, "J"),
            "designWidth": calculation_batch_reuse.cell_value(row, "K"),
            "designThickness": calculation_batch_reuse.cell_value(row, "L"),
            "physicalQuantity": calculation_batch_reuse.cell_value(row, "M"),
            "visibleCondition": calculation_batch_reuse.cell_value(row, "O"),
            "edgeMethod": calculation_batch_reuse.cell_value(row, "P"),
        }

        baseline_before = calculation_batch_reuse.run_batch(keys)
        current_before = calculation_batch_reuse.run_batch(keys, design_inputs=[design_input])
        changed_input = {**design_input, "designLength": design_input["designLength"] + 1}
        current_after = calculation_batch_reuse.run_batch(keys, design_inputs=[changed_input])
        baseline_after = calculation_batch_reuse.run_batch(keys)

        self.assertEqual(
            [(item["id"], item["value"]) for item in baseline_before["rows"]],
            [(item["id"], item["value"]) for item in current_before["rows"]],
        )
        self.assertEqual(
            [(item["id"], item["value"]) for item in baseline_before["rows"]],
            [(item["id"], item["value"]) for item in baseline_after["rows"]],
        )
        before = {item["id"]: item for item in current_before["rows"]}
        after = {item["id"]: item for item in current_after["rows"]}
        changed_ids = [key for key in before if before[key]["value"] != after[key]["value"]]
        self.assertTrue(changed_ids)
        self.assertTrue(all(after[key]["sourceKey"] == keys[0] for key in changed_ids))
        self.assertEqual(
            [item["value"] for item in current_before["rows"] if item["sourceKey"] == keys[1]],
            [item["value"] for item in current_after["rows"] if item["sourceKey"] == keys[1]],
        )
        self.assertNotEqual(current_before["inputSnapshotHash"], current_after["inputSnapshotHash"])
        self.assertEqual(current_after["inputSnapshotVersion"], "PRODUCT-DESIGN-CALCULATION-INPUT-V1")


class EngineeringCalculationReadBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = type("Reader", (), {"is_authenticated": True, "company_id": 17})()

    def request(self):
        request = self.factory.get(
            "/api/pde/a1-engineering/calculations/batch-reuse/",
            {"action": "designCalculationContext"},
        )
        force_authenticate(request, user=self.user)
        return request

    def test_get_requires_business_read_authorization_after_environment_isolation(self):
        with patch.object(calculation_batch_reuse, "verify_read_isolation", return_value={"verified": True}) as isolation, patch.object(
            calculation_batch_reuse, "authorize_read", return_value={"allowed": True},
        ) as authorization, patch.object(
            calculation_batch_reuse, "design_calculation_context",
            return_value={"draft": {}, "businessWriteSideEffectCount": 0},
        ):
            response = EngineeringCalculationBatchView.as_view()(self.request())

        self.assertEqual(response.status_code, 200)
        isolation.assert_called_once_with()
        authorization.assert_called_once_with(self.user)
        self.assertEqual(response.data["businessWriteSideEffectCount"], 0)

    def test_environment_failure_is_not_reported_as_permission_failure(self):
        error = EngineeringCalculationError(
            "NON_PRODUCTION_ISOLATION_REQUIRED", "验收环境隔离失败。", {},
        )
        with patch.object(calculation_batch_reuse, "verify_read_isolation", side_effect=error), patch.object(
            calculation_batch_reuse, "authorize_read",
        ) as authorization:
            response = EngineeringCalculationBatchView.as_view()(self.request())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["errorCode"], "NON_PRODUCTION_ISOLATION_REQUIRED")
        authorization.assert_not_called()

    def test_denied_business_reader_receives_permission_403(self):
        error = EngineeringCalculationError("PERMISSION_DENIED", "没有查看权限。", {})
        with patch.object(calculation_batch_reuse, "verify_read_isolation", return_value={"verified": True}), patch.object(
            calculation_batch_reuse, "authorize_read", side_effect=error,
        ):
            response = EngineeringCalculationBatchView.as_view()(self.request())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["errorCode"], "PERMISSION_DENIED")


class EngineeringWorkContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="EWC", name="工程上下文隔离公司")
        cls.department = Department.objects.create(
            company=cls.company, code="EWC-ENG", name="工程部",
        )
        cls.user = User.objects.create_user(
            username="ewc_operator", password="test-only", real_name="工程录入员",
            company_id=cls.company.pk,
        )
        role = Role.objects.create(code="EWC_ROLE", name="工程上下文隔离角色")
        for code in (
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.master_data.product.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "production"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="ewc",
        )

        cls.salesperson = cls._employee("EWC-SALES", "隔离业务员", "RESP_SALES_ORDER_002")
        cls.designer = cls._employee("EWC-DESIGN", "隔离设计师", "RESP_TECH_DESIGN_004")
        cls.breakdown_owner = cls._employee("EWC-BREAK", "隔离拆单员", "RESP_TECH_PROCESS_001")
        cls.breakdown_owner.user = cls.user
        cls.breakdown_owner.save(update_fields=["user"])
        maintainer, _ = Responsibility.objects.get_or_create(
            code="ENTERPRISE_MASTER_DATA_MAINTAINER",
            defaults={"name": "企业基础资料维护", "status": "ACTIVE", "is_active": True},
        )
        PositionResponsibility.objects.create(
            position=cls.breakdown_owner.position_ref, responsibility=maintainer,
            active=True, is_primary=False,
        )
        cls.inactive_salesperson = cls._employee(
            "EWC-INACTIVE", "停用业务员", "RESP_SALES_CUSTOMER_001", status="inactive",
        )

        cls.pcs = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS", name="件", dimension="count", decimal_places=3,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="FM", name="房门", industry_type="wholeHouseWood",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="EWC-FG", name="隔离房门", unit="件",
            base_uom=cls.pcs, material_type="finished", is_produced=True,
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.material,
            product_code="EWC-DOOR", product_name="隔离房门",
            emd_material_code=cls.material.code,
            manufacturing_definition_mode="order_engineered", status="released",
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="V1", version_status="released",
        )
        customer = Customer.objects.create(company=cls.company, code="EWC-C", name="隔离客户")
        cls.order = SalesOrder(
            company=cls.company, department=cls.department, customer=customer,
            order_no="SO-EWC", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=10),
            status="engineering", created_by=cls.user,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.item = SalesOrderItem.objects.create(
            sales_order=cls.order, line_no=1, material=cls.material,
            product_definition=cls.product, product_version=cls.product_version,
            engineering_mode="ORDER_ENGINEERED", quantity="2", uom=cls.pcs,
            required_date=cls.order.required_delivery_date,
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="EWC-SOURCE", source_name="隔离工程来源",
            source_type="order_input", source_version="V1", source_payload={},
            content_hash="e" * 64, status="confirmed",
        )
        cls.instance = OrderEngineeringInstance.objects.create(
            company=cls.company, instance_no="OEI-EWC", sales_order_item=cls.item,
            product=cls.product, baseline_product_version=cls.product_version,
            source_record=cls.source, status="source_confirmed",
        )
        cls.operation = Process.objects.create(
            company=cls.company, code="EWC-CUT", name="开料",
            calculation_basis="count", calculation_uom=cls.pcs,
        )
        cls.routing = Routing.objects.create(
            company=cls.company, product=cls.product, routing_code="EWC-ROUTE",
            name="隔离房门路线", status="released",
        )
        cls.routing_version = RoutingVersion.objects.create(
            product=cls.product, product_version=cls.product_version,
            routing=cls.routing, routing_version="V1", status="draft",
            effective_date=date.today() - timedelta(days=1),
        )
        cls.routing_step = RoutingStep.objects.create(
            routing_version=cls.routing_version, sequence=10, operation=cls.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        cls.routing_version.status = "released"
        cls.routing_version.save(update_fields=("status", "updated_at"))

    @classmethod
    def _employee(cls, no, name, responsibility_code, status="active"):
        position = Position.objects.create(
            company=cls.company, department=cls.department,
            code=f"POS-{no}", name=f"{name}岗位",
        )
        responsibility = Responsibility.objects.create(
            code=responsibility_code, name=f"{name}职责", status="ACTIVE", is_active=True,
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility, active=True, is_primary=True,
        )
        return Employee.objects.create(
            employee_no=no, full_name=name, department_ref=cls.department,
            position_ref=position, status=status,
        )

    @classmethod
    def order_projection_input(cls):
        return [{
            "salesOrderItemId": cls.item.pk,
            "orderEngineeringInstanceId": cls.instance.pk,
            "sourceVersion": cls.source.source_version,
        }]

    def test_formal_options_use_stable_employee_ids_and_do_not_import_packaging(self):
        result = build_engineering_input_options(self.user)

        self.assertEqual(result["source"], "server-formal-master-data")
        self.assertEqual(result["productCategories"][0]["id"], self.category.pk)
        self.assertEqual(result["units"][0]["id"], self.pcs.pk)
        self.assertEqual(
            [row["employeeId"] for row in result["employeeRoles"]["salesperson"]["options"]],
            [self.salesperson.pk],
        )
        self.assertEqual(
            [row["employeeId"] for row in result["employeeRoles"]["designer"]["options"]],
            [self.designer.pk],
        )
        self.assertEqual(
            [row["employeeId"] for row in result["employeeRoles"]["breakdownOwner"]["options"]],
            [self.breakdown_owner.pk],
        )
        self.assertEqual(result["packagingMethods"], [])
        self.assertFalse(result["packagingMethodState"]["sourceWorkbookValuesImported"])

    def test_responsibility_validation_rejects_wrong_role_inactive_and_packaging_guess(self):
        valid = normalize_draft_context(self.user, {
            "responsibilityAssignments": {
                "salesperson": {"employeeId": self.salesperson.pk},
                "designer": {"employeeId": self.designer.pk},
                "breakdownOwner": {"employeeId": self.breakdown_owner.pk},
            },
            "packagingMethod": {"id": None},
        })
        self.assertEqual(valid["responsibilityAssignments"]["designer"]["employeeId"], self.designer.pk)
        self.assertFalse(valid["packagingMethod"]["sourceWorkbookValueImported"])

        with self.assertRaisesRegex(ValueError, "ROLE_OR_SCOPE_MISMATCH"):
            normalize_draft_context(self.user, {
                "responsibilityAssignments": {"designer": {"employeeId": self.salesperson.pk}},
            })
        with self.assertRaisesRegex(ValueError, "INACTIVE"):
            normalize_draft_context(self.user, {
                "responsibilityAssignments": {"salesperson": {"employeeId": self.inactive_salesperson.pk}},
            })
        with self.assertRaisesRegex(ValueError, "PACKAGING_METHOD_INVALID"):
            normalize_draft_context(self.user, {"packagingMethod": {"id": "workbook-white"}})

    def test_engineering_options_use_formal_service_save_readback_and_audit(self):
        payload = {
            "option_type": "edge_method", "code": "EDGE-FOUR", "name": "四边",
            "description": "四条边均封边", "source_reference": "拆单基础数据!L2:L46",
            "is_active": True, "reason": "隔离测试正式维护与保存回读",
        }
        saved = ProductionFoundationService.write(
            "engineering-breakdown-options", user=self.user, payload=payload,
            idempotency_key="ewc-edge-four", source_identity={
                "sourceSystem": "TEST", "sourceType": "ISOLATED",
                "sourceObjectType": "engineering-option", "externalId": "edge-four",
            },
        )
        replay = ProductionFoundationService.write(
            "engineering-breakdown-options", user=self.user, payload=payload,
            idempotency_key="ewc-edge-four", source_identity={
                "sourceSystem": "TEST", "sourceType": "ISOLATED",
                "sourceObjectType": "engineering-option", "externalId": "edge-four",
            },
        )
        options = build_engineering_input_options(self.user)
        self.assertEqual(saved["row"]["name"], "四边")
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(options["edgeMethods"][0]["id"], saved["row"]["id"])

    def test_confirmed_cross_company_people_are_facts_not_operative_assignments(self):
        other_company = Company.objects.create(code="EWC-OTHER", name="来源作用域外公司")
        other_department = Department.objects.create(company=other_company, code="OTHER-ENG", name="工程部")
        other_position = Position.objects.create(company=other_company, department=other_department, code="OTHER-DES", name="设计师")
        responsibility = Responsibility.objects.get(code="RESP_TECH_DESIGN_004")
        PositionResponsibility.objects.create(position=other_position, responsibility=responsibility, active=True)
        employee = Employee.objects.create(employee_no="OTHER-001", full_name="作用域外设计师", status="active", department_ref=other_department, position_ref=other_position)
        facts = normalize_confirmed_business_facts(self.user, {
            "confirmedResponsibilityFacts": {"designer": {"employeeId": employee.pk}},
            "businessOrderReference": {"sourceOrderNo": "1-4-正", "sameWorkbookOrderConfirmed": True},
        })
        self.assertEqual(facts["confirmedResponsibilityFacts"]["designer"]["referenceStatus"], "CONFIRMED_CROSS_COMPANY_NOT_OPERATIVE")
        self.assertEqual(facts["businessOrderReference"]["stableOrderLinkStatus"], "SOURCE_ORDER_NOT_ESTABLISHED")

    def test_draft_save_readback_rebuilds_formal_snapshots_and_preserves_history(self):
        payload = {
            "orderEngineeringInstanceId": self.instance.pk,
            "salesOrderItemId": self.item.pk,
            "sourceName": "隔离工程草稿",
            "revisionReason": "选择、保存、服务端回读及历史回显隔离测试",
            "responsibilityAssignments": {
                "salesperson": {"employeeId": self.salesperson.pk},
                "designer": {"employeeId": self.designer.pk},
                "breakdownOwner": {"employeeId": self.breakdown_owner.pk},
            },
            "packagingMethod": {"id": None},
            "rows": [{
                "id": "EWC-ROW-1", "sourceType": "房门单", "product": "隔离房门",
                "component": "门扇", "quantity": "2",
                "productCategoryId": self.category.pk, "productCategoryCode": "TAMPERED",
                "unitId": self.pcs.pk, "unit": "TAMPERED",
            }],
        }
        with patch.object(calculation_batch_reuse, "authorize", return_value={"verified": True}):
            first = calculation_batch_reuse.save_draft(self.user, payload)
            second = calculation_batch_reuse.save_draft(
                self.user, {**payload, "revisionReason": "第二次追加修订"},
            )
            catalog = calculation_batch_reuse.draft_catalog(self.user, self.instance.pk)

        self.assertFalse(first["previousSourceOverwritten"])
        self.assertEqual(first["businessWriteSideEffectCount"], 1)
        self.assertEqual(catalog["draftCount"], 2)
        reopened = next(row for row in catalog["drafts"] if row["id"] == second["draft"]["id"])
        self.assertEqual(reopened["rows"][0]["productCategoryCode"], self.category.code)
        self.assertEqual(reopened["rows"][0]["unit"], self.pcs.code)
        self.assertEqual(
            reopened["responsibilityAssignments"]["breakdownOwner"]["employeeId"],
            self.breakdown_owner.pk,
        )
        self.assertIsNone(reopened["packagingMethod"]["id"])
        self.assertEqual(
            EngineeringSourceRecord.objects.filter(source_no__startswith="PCE-ENGINEERING-DRAFT-").count(),
            2,
        )

    def test_engineering_draft_rejects_duplicate_design_fields_when_product_design_is_authority(self):
        attribute = SalesOrderItemEngineeringAttribute.objects.create(
            sales_order_item=self.item, sequence=1, raw_source="TEST", raw_sheet="房门单",
            raw_field="controlled_engineering_row", raw_value={"sourceRow": 11},
            canonical_field="controlled_engineering_row", normalized_value={}, value_type="json",
            source_type="DESIGN", created_by=self.user,
        )
        ProductDesignItem.objects.create(
            company=self.company, sales_order_item=self.item, source_record=self.source,
            source_attribute=attribute, item_no="SO-EWC-DES-01", item_name="隔离房门",
            original_requirement={}, existing_design_data={"designLength": "2045"},
            source_version=self.source.source_version, source_content_hash=self.source.content_hash,
            match_results={},
        )
        payload = {
            "orderEngineeringInstanceId": self.instance.pk, "salesOrderItemId": self.item.pk,
            "sourceRecordId": self.source.pk, "rows": [{
                "id": "DUPLICATE-DESIGN", "sourceType": "房门单", "product": "隔离房门",
                "component": "门扇", "quantity": "1", "length": "9999",
            }],
        }
        before = EngineeringSourceRecord.objects.count()
        with patch.object(calculation_batch_reuse, "authorize", return_value={"verified": True}):
            with self.assertRaises(ValueError) as captured:
                calculation_batch_reuse.save_draft(self.user, payload)
        self.assertEqual(captured.exception.code, "ENGINEERING_DESIGN_FACT_READ_ONLY")
        self.assertEqual(captured.exception.details["factAuthority"], "ProductDesignItem/ProductDesignRevision")
        self.assertEqual(EngineeringSourceRecord.objects.count(), before)

    def test_true_source_trial_saves_unbound_and_never_appears_in_order_drafts(self):
        payload = {
            "orderEngineeringInstanceId": None,
            "salesOrderItemId": None,
            "sourceName": "真实来源试录 · 三合一生产单第36行",
            "revisionReason": "订单与客户关系待确认；封边、见光待补",
            "responsibilityAssignments": {},
            "packagingMethod": {"id": None},
            "rows": [{
                "id": "SOURCE-XLSX-R36", "sourceType": "三合一单",
                "sourceSheet": "三合一生产单", "sourceRow": 36,
                "space": "图7餐边柜", "product": "格栅屏风", "component": "格栅屏风",
                "componentCode": "BTKF2601001", "quantity": "1", "unit": "组",
                "length": "1425", "width": "1040", "thickness": "25",
                "materialProcessCode": "BTKF2601001", "routingProcessCode": "BTKF/GT",
            }],
        }
        with patch.object(calculation_batch_reuse, "authorize", return_value={"verified": True}):
            saved = calculation_batch_reuse.save_draft(self.user, payload)
            unbound = calculation_batch_reuse.draft_catalog(self.user, "UNBOUND")
            order_bound = calculation_batch_reuse.draft_catalog(self.user, self.instance.pk)

        self.assertEqual(saved["draft"]["orderEngineeringInstanceId"], None)
        self.assertEqual(saved["draft"]["salesOrderItemId"], None)
        self.assertEqual(unbound["draftCount"], 1)
        self.assertEqual(unbound["drafts"][0]["rows"][0]["sourceRow"], 36)
        self.assertEqual(order_bound["draftCount"], 0)
        self.assertFalse(saved["draft"]["packagingMethod"]["sourceWorkbookValueImported"])

    def test_registered_71_row_scope_is_stable_idempotent_and_recomputes_on_readback(self):
        with patch.object(calculation_batch_reuse, "authorize", return_value={"verified": True}):
            first = calculation_batch_reuse.save_registered_source_draft(self.user, {})
            second = calculation_batch_reuse.save_registered_source_draft(self.user, {})
            catalog = calculation_batch_reuse.draft_catalog(self.user, "UNBOUND")

        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["draft"]["registeredSourceScope"]["sourceCount"], 71)
        self.assertEqual(len(first["draft"]["rows"]), 71)
        self.assertEqual(first["draft"]["rows"][0]["sourceSheet"], "房门单")
        self.assertEqual(first["draft"]["rows"][0]["sourceRow"], 11)
        self.assertEqual(first["draft"]["rows"][0]["length"], 2045)
        self.assertEqual(first["draft"]["rows"][0]["routingProcessCode"], "QSFB/FM")
        self.assertEqual(first["draft"]["rows"][8]["sourceSheet"], "三合一生产单")
        self.assertEqual(first["draft"]["rows"][8]["sourceRow"], 7)
        self.assertEqual(first["draft"]["rows"][8]["edgeMode"], "四边")
        self.assertEqual(first["draft"]["rows"][8]["visibleCondition"], "单")
        self.assertEqual(catalog["draftCount"], 1)
        self.assertEqual(catalog["drafts"][0]["sourceCalculation"]["sourceCount"], 71)
        self.assertEqual(len(catalog["drafts"][0]["sourceCalculation"]["rows"]), 388)
        self.assertEqual(catalog["drafts"][0]["sourceCalculation"]["counts"]["对账一致"], 383)
        self.assertEqual(catalog["drafts"][0]["sourceCalculation"]["segments"][0]["missingCount"], 5)
        self.assertFalse(catalog["drafts"][0]["sourceCalculation"]["formalResultsCreated"])
        self.assertEqual(
            EngineeringSourceRecord.objects.filter(
                source_no__contains="REGISTERED-XLSX",
            ).count(),
            1,
        )

    def test_operation_plan_projection_distinguishes_no_plan_from_missing_operation_dates(self):
        unplanned = build_production_plan_projection(
            self.company.pk, self.order_projection_input(),
        )[str(self.item.pk)]
        self.assertEqual(unplanned["statusLabel"], "未排计划")
        self.assertEqual(unplanned["rows"][0]["operationId"], self.operation.pk)
        self.assertEqual(unplanned["rows"][0]["plannedStartDate"], None)
        self.assertEqual(unplanned["rows"][0]["plannedFinishDate"], None)

        demand = Demand.objects.create(
            demand_no="D-EWC", source_type="sales_order",
            source_document_type="SalesOrder", source_document_id=str(self.order.pk),
            source_document_no=self.order.order_no, sales_order_item=self.item,
            material=self.material, required_qty="2", required_date=self.order.required_delivery_date,
            department=self.department, reason="隔离测试", status="confirmed", created_by=self.user,
        )
        requirement = PlanningRequirement.objects.create(
            requirement_no="PR-EWC", demand=demand, material=self.material,
            demand_qty="2", available_qty="0", net_required_qty="2",
            required_date=self.order.required_delivery_date, supply_type="production",
            status="confirmed", created_by=self.user,
        )
        plan = ProductionPlan.objects.create(
            plan_no="PP-EWC", planning_requirement=requirement, material=self.material,
            planned_qty="2", required_date=self.order.required_delivery_date,
            source_id=str(requirement.pk), run_batch="BATCH-EWC", status="confirmed",
            confirmed_by=self.user,
        )

        projected = build_production_plan_projection(
            self.company.pk, self.order_projection_input(),
        )[str(self.item.pk)]
        self.assertEqual(projected["planId"], plan.pk)
        self.assertEqual(projected["statusLabel"], "计划已建立，工序计划日期未维护")
        self.assertEqual(projected["rows"][0]["statusLabel"], "计划日期未维护")
        self.assertIsNone(projected["rows"][0]["plannedStartDate"])
        self.assertIsNone(projected["rows"][0]["plannedFinishDate"])
        self.assertNotEqual(str(plan.required_date), projected["rows"][0]["plannedStartDate"])
