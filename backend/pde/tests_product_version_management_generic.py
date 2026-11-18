from datetime import date

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import MasterDataWriteRequest, Material, UnitOfMeasure
from pfm.models import Employee
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import (
    EngineeringSourceRecord, ProductCategory, ProductDefinition, ProductDesignItem,
    OrderEngineeringBaseline, OrderEngineeringBaselineItem, ProductDesignRevision,
    ProductVersion,
)
from .order_demand_preparation_service import engineering_readiness_facts
from .product_version_management_service import (
    ProductVersionManagementError,
    confirm_order_engineering_baseline,
    product_version_management_facts,
    save_order_engineering_baseline_draft,
)
from .views import ProductVersionManagementView


class GenericProductVersionManagementTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.company = Company.objects.create(code="GEN", name="通用工业测试公司")
        self.department = Department.objects.create(company=self.company, code="ENG", name="工程部")
        self.user = User.objects.create_user(
            username="generic-engineer", password="test-only", company_id=self.company.pk,
            real_name="账号显示名",
        )
        Employee.objects.create(
            user=self.user, employee_no="GEN-E001", full_name="通用工程师",
            department_ref=self.department, status="active",
        )
        self.customer = Customer.objects.create(company=self.company, code="C001", name="工业客户")
        self.count_uom = UnitOfMeasure.objects.create(company_id=self.company.pk, code="EA", name="件", dimension="count")
        self.length_uom = UnitOfMeasure.objects.create(company_id=self.company.pk, code="MM", name="毫米", dimension="length")
        self.category = ProductCategory.objects.create(company=self.company, code="ASM", name="工业装配件", industry_type="general")
        self.source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="SRC-GENERIC-A", source_name="客户工程资料A",
            source_type="order_input", source_version="REV-A", source_payload={}, content_hash="a" * 64,
        )
        role = Role.objects.create(code="engineering-baseline-operator", name="工程基线办理人")
        for code, name in (
            ("production.engineering.baseline.save", "保存订单工程基线草稿"),
            ("production.engineering.baseline.confirm", "确认订单工程基线"),
        ):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": name, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", business_hash="b" * 64,
        )

    def _material(self, code, *, purchased=False):
        return Material.objects.create(
            company_id=self.company.pk, code=code, name=code,
            material_type="finished", is_purchased=purchased, is_produced=not purchased,
            base_uom=self.count_uom, unit="件", unit_status="confirmed",
        )

    def _order(self, no, material, mode):
        order = create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft", company=self.company,
            department=self.department, customer=self.customer, order_no=no,
            order_date=date(2026, 9, 1), required_delivery_date=date(2026, 10, 1),
            order_type="standard", order_source="manual", created_by=self.user,
        )
        item = SalesOrderItem.objects.create(
            sales_order=order, line_no=1, material=material, engineering_mode=mode,
            quantity=1, uom=self.count_uom, required_date=date(2026, 10, 1),
            customer_product_name=material.name,
        )
        return order, item

    def _design(
        self, order_item, suffix, product=None, semantic="实际厚度", create_revision=True,
        design_nature="EXISTING_DESIGN_IMPORTED", revision_nature="FORMAL",
    ):
        attribute = SalesOrderItemEngineeringAttribute.objects.create(
            sales_order_item=order_item,
            sequence=SalesOrderItemEngineeringAttribute.objects.filter(sales_order_item=order_item).count() + 1,
            raw_source="客户资料",
            raw_sheet="工程输入", external_source=f"GENERIC:{suffix}", raw_field="design",
            raw_value={"component": suffix, "dimensionSemantic": semantic},
            canonical_field="product_design_item", normalized_value={}, value_type="json",
            unit=self.count_uom, source_type="DESIGN", created_by=self.user,
        )
        design = ProductDesignItem.objects.create(
            company=self.company, sales_order_item=order_item, source_record=self.source,
            source_attribute=attribute, item_no=f"{order_item.sales_order.order_no}-DES-01-{suffix}",
            item_name=suffix, physical_quantity=1, physical_uom=self.count_uom,
            physical_uom_snapshot="件", product_category=self.category,
            product_definition=product, original_requirement={},
            existing_design_data={"dimensionSemantic": semantic, "designLength": 100, "designWidth": 50, "designThickness": 2},
            design_data_nature=design_nature,
            source_version=self.source.source_version, source_content_hash=self.source.content_hash,
        )
        if create_revision:
            ProductDesignRevision.objects.create(
                design_item=design, revision=1, design_nature=revision_nature,
                design_length=100, design_width=50, design_thickness=2,
                design_uom=self.length_uom, design_data={"dimensionSemantic": semantic},
                source_provenance={"sourceType": "CUSTOMER_ENGINEERING"},
                master_match_results={}, change_reason="初始工程设计", created_by=self.user,
            )
        return design

    def test_four_industrial_paths_are_distinguished_without_sample_names(self):
        standard_material = self._material("STD-ASM")
        standard_order, standard_line = self._order("SO-STD-ASSEMBLY", standard_material, "STANDARD")
        product = ProductDefinition.objects.create(
            company=self.company, category=self.category, material=standard_material,
            product_code="P-STD-ASM", product_name="标准工业装配件",
            emd_material_code=standard_material.code, status="released",
        )
        version = ProductVersion.objects.create(product=product, version_no="2.1", version_status="released")
        standard_line.product_definition = product
        standard_line.product_version = version
        standard_line.save(update_fields=["product_definition", "product_version"])
        self._design(standard_line, "ASM-001", product=product)

        custom_material = self._material("CUSTOM-SHEET")
        custom_order, custom_line = self._order("SO-CUSTOM-SHEET", custom_material, "ORDER_ENGINEERED")
        self._design(custom_line, "SHEET-001")

        wood_material = self._material("WOOD-CASE")
        wood_order, wood_line = self._order("SO-WOOD-CASE", wood_material, "ORDER_ENGINEERED")
        self._design(wood_line, "WOOD-001", semantic="墙厚")

        purchased_material = self._material("PURCHASED-FG", purchased=True)
        purchased_order, _ = self._order("SO-PURCHASED-FG", purchased_material, "STANDARD")

        standard = product_version_management_facts(self.company.pk, standard_order.order_no)
        custom = product_version_management_facts(self.company.pk, custom_order.order_no)
        wood = product_version_management_facts(self.company.pk, wood_order.order_no)
        purchased = product_version_management_facts(self.company.pk, purchased_order.order_no)

        self.assertEqual(standard["candidateRows"][0]["identityCode"], "FORMAL_PRODUCT")
        self.assertEqual(standard["candidateRows"][0]["formalProductVersionNo"], "2.1")
        self.assertEqual(custom["candidateRows"][0]["identityCode"], "CUSTOMER_ENGINEERING")
        self.assertEqual(wood["candidateRows"][0]["designRevisionLabel"], "R1")
        self.assertEqual(purchased["candidateBaseline"]["statusCode"], "PURCHASED_FINISHED_GOOD_BYPASS")
        self.assertEqual(purchased["candidateRows"], [])
        for facts in (standard, custom, wood, purchased):
            self.assertEqual(facts["savedBaselineStatus"], "尚未建立")
            self.assertEqual(facts["savedBaselines"], [])
            self.assertFalse(facts["persistenceCapability"]["confirmAllowed"])

    def test_read_paths_are_company_scoped_name_independent_and_zero_write(self):
        material = self._material("MECH-001")
        order, line = self._order("SO-MECH-001", material, "ORDER_ENGINEERED")
        self._design(line, "MECH-DESIGN")
        before = {
            "orders": SalesOrder.objects.count(),
            "items": ProductDesignItem.objects.count(),
            "revisions": ProductDesignRevision.objects.count(),
            "versions": ProductVersion.objects.count(),
        }
        first = product_version_management_facts(self.company.pk, order.order_no)
        self.source.source_name = "来源名称已变化但稳定关系不变"
        self.source.save(update_fields=["source_name"])
        second = product_version_management_facts(self.company.pk, order.order_no)
        readiness = engineering_readiness_facts(self.company.pk, order.order_no)
        after = {
            "orders": SalesOrder.objects.count(),
            "items": ProductDesignItem.objects.count(),
            "revisions": ProductDesignRevision.objects.count(),
            "versions": ProductVersion.objects.count(),
        }
        self.assertEqual(first["candidateBaseline"]["candidateId"], second["candidateBaseline"]["candidateId"])
        self.assertEqual(len(readiness["rows"]), 1)
        self.assertEqual(readiness["rows"][0]["orderNo"], "SO-MECH-001")
        self.assertEqual(before, after)

    def test_persisted_content_without_revision_can_form_first_controlled_baseline(self):
        order, line = self._order("SO-DRAFT-CONTENT", self._material("DRAFT-CONTENT"), "ORDER_ENGINEERED")
        self._design(line, "CONTENT-001", create_revision=False)
        facts = product_version_management_facts(self.company.pk, order.order_no, user=self.user)
        row = facts["candidateRows"][0]
        self.assertEqual(row["snapshotSourceType"], "PERSISTED_DESIGN_CONTENT")
        self.assertTrue(row["draftSaveAllowed"])
        self.assertTrue(row["confirmable"])
        self.assertEqual(row["confirmBlockerCode"], "")
        self.assertEqual(row["baselineEligibilityCode"], "CONFIRMABLE_FIRST_CONTROLLED_BASELINE")
        self.assertIsNone(row["designRevision"])
        self.assertEqual(facts["candidateBaseline"]["draftSnapshotItemCount"], 1)

    def test_save_is_idempotent_and_simulated_content_blocks_whole_scope_confirmation(self):
        order, line = self._order("SO-IDEMPOTENT-DRAFT", self._material("IDEMPOTENT-DRAFT"), "ORDER_ENGINEERED")
        self._design(line, "CONTENT-001", create_revision=False)
        self._design(
            line, "SIMULATED-002", create_revision=False,
            design_nature="SIMULATED_FOR_TEST",
        )
        candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        payload = {"orderNo": order.order_no, "candidateId": candidate["candidateId"], "reason": "保存当前真实工程内容"}
        first, replayed = save_order_engineering_baseline_draft(user=self.user, payload=payload, idempotency_key="draft-retry-1")
        second, replayed_second = save_order_engineering_baseline_draft(user=self.user, payload=payload, idempotency_key="draft-retry-1")
        self.assertFalse(replayed)
        self.assertTrue(replayed_second)
        self.assertEqual(OrderEngineeringBaseline.objects.filter(sales_order=order).count(), 1)
        baseline = OrderEngineeringBaseline.objects.get(pk=first["selectedBaseline"]["baselineId"])
        self.assertEqual(baseline.items.count(), 2)
        self.assertEqual(baseline.items.filter(confirmable=True).count(), 1)
        self.assertEqual(baseline.items.filter(blocker_code="SIMULATED_CONTENT_NOT_CONFIRMABLE").count(), 1)
        self.assertEqual(first["selectedBaseline"]["snapshotHash"], second["selectedBaseline"]["snapshotHash"])
        with self.assertRaisesMessage(ProductVersionManagementError, "当前草稿仍包含"):
            confirm_order_engineering_baseline(
                user=self.user,
                payload={"baselineId": baseline.pk, "expectedVersion": baseline.version, "reason": "尝试确认"},
                idempotency_key="confirm-blocked-1",
            )

    def test_confirmed_history_is_immutable_after_current_design_changes(self):
        order, line = self._order("SO-CONFIRMABLE", self._material("CONFIRMABLE"), "ORDER_ENGINEERED")
        design = self._design(line, "FORMAL-001")
        candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        saved, _ = save_order_engineering_baseline_draft(
            user=self.user,
            payload={"orderNo": order.order_no, "candidateId": candidate["candidateId"], "reason": "保存正式修订快照"},
            idempotency_key="save-confirmable-1",
        )
        baseline_id = saved["selectedBaseline"]["baselineId"]
        confirmed, replayed = confirm_order_engineering_baseline(
            user=self.user,
            payload={"baselineId": baseline_id, "expectedVersion": 1, "reason": "确认当前整单工程依据"},
            idempotency_key="confirm-formal-1",
        )
        self.assertFalse(replayed)
        baseline = OrderEngineeringBaseline.objects.get(pk=baseline_id)
        old_hash = baseline.items.get().content_hash
        self.assertEqual(baseline.status, "confirmed")
        self.assertEqual(confirmed["selectedBaseline"]["statusTransitionCount"], 1)
        self.assertEqual(confirmed["selectedBaseline"]["createdByName"], "通用工程师")
        self.assertEqual(confirmed["selectedBaseline"]["confirmedByName"], "通用工程师")
        self.assertTrue(confirmed["selectedBaseline"]["confirmedAt"])
        ProductDesignRevision.objects.create(
            design_item=design, revision=2, design_nature="FORMAL",
            design_length=120, design_width=50, design_thickness=2,
            design_uom=self.length_uom, design_data={"dimensionSemantic": "实际厚度"},
            source_provenance={"sourceType": "CUSTOMER_ENGINEERING"}, master_match_results={},
            change_reason="后续设计变化", created_by=self.user,
        )
        current = product_version_management_facts(self.company.pk, order.order_no, user=self.user, baseline_id=baseline_id)
        self.assertEqual(current["diffFacts"]["statusCode"], "CHANGED")
        self.assertEqual(OrderEngineeringBaselineItem.objects.get(baseline=baseline).content_hash, old_hash)
        item = OrderEngineeringBaselineItem.objects.get(baseline=baseline)
        item.item_name_snapshot = "不允许覆盖"
        with self.assertRaises(ValidationError):
            item.save()

    def test_saved_snapshot_comparison_exposes_real_business_fields_and_read_is_zero_write(self):
        order, line = self._order("SO-HISTORY-DIFF", self._material("HISTORY-DIFF"), "ORDER_ENGINEERED")
        design = self._design(line, "HISTORY-001", semantic="旧版尺寸口径")
        first_candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        first, _ = save_order_engineering_baseline_draft(
            user=self.user,
            payload={"orderNo": order.order_no, "candidateId": first_candidate["candidateId"], "reason": "第一版历史快照"},
            idempotency_key="history-diff-save-1",
        )
        ProductDesignRevision.objects.create(
            design_item=design, revision=2, design_nature="FORMAL",
            design_length=120, design_width=55, design_thickness=3,
            design_uom=self.length_uom, design_data={"dimensionSemantic": "新版尺寸口径"},
            source_provenance={"sourceType": "CUSTOMER_ENGINEERING"}, master_match_results={},
            change_reason="调整尺寸", created_by=self.user,
        )
        second_candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        second, _ = save_order_engineering_baseline_draft(
            user=self.user,
            payload={"orderNo": order.order_no, "candidateId": second_candidate["candidateId"], "reason": "第二版历史快照"},
            idempotency_key="history-diff-save-2",
        )
        before_read = {
            "baselines": OrderEngineeringBaseline.objects.count(),
            "items": OrderEngineeringBaselineItem.objects.count(),
            "writeRequests": MasterDataWriteRequest.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
            "revisions": ProductDesignRevision.objects.count(),
        }
        facts = product_version_management_facts(
            self.company.pk, order.order_no, user=self.user,
            baseline_id=second["selectedBaseline"]["baselineId"],
        )
        comparison = facts["historyComparison"]
        self.assertTrue(comparison["available"])
        self.assertEqual(comparison["olderBaseline"]["baselineId"], first["selectedBaseline"]["baselineId"])
        self.assertEqual(comparison["newerBaseline"]["baselineId"], second["selectedBaseline"]["baselineId"])
        self.assertEqual(comparison["summary"], {"added": 0, "removed": 0, "changed": 1, "same": 0})
        changed = comparison["items"][0]
        field_codes = {row["fieldCode"] for row in changed["changedFields"]}
        self.assertIn("revision.revision", field_codes)
        self.assertIn("revision.designLength", field_codes)
        self.assertIn("revision.designData", field_codes)
        history_item = facts["selectedBaseline"]["items"][0]
        fields = {row["fieldCode"]: row for row in history_item["snapshotDisplayFields"]}
        self.assertEqual(fields["revision.designLength"]["displayValue"], "120.000000")
        self.assertEqual(fields["revision.materialId"]["displayValue"], "该版未记录")
        self.assertEqual(before_read, {
            "baselines": OrderEngineeringBaseline.objects.count(),
            "items": OrderEngineeringBaselineItem.objects.count(),
            "writeRequests": MasterDataWriteRequest.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
            "revisions": ProductDesignRevision.objects.count(),
        })

    def test_stale_candidate_version_conflict_and_transaction_failure_are_safe(self):
        order, line = self._order("SO-CONCURRENCY", self._material("CONCURRENCY"), "ORDER_ENGINEERED")
        self._design(line, "FORMAL-001")
        candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        with self.assertRaisesMessage(ProductVersionManagementError, "已变化"):
            save_order_engineering_baseline_draft(
                user=self.user,
                payload={"orderNo": order.order_no, "candidateId": "0" * 64, "reason": "过期候选"},
                idempotency_key="stale-save-1",
            )
        with patch("pde.product_version_management_service.OrganizationOperatingAuditRecord.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                save_order_engineering_baseline_draft(
                    user=self.user,
                    payload={"orderNo": order.order_no, "candidateId": candidate["candidateId"], "reason": "事务失败演练"},
                    idempotency_key="rollback-save-1",
                )
        self.assertEqual(OrderEngineeringBaseline.objects.filter(sales_order=order).count(), 0)
        saved, _ = save_order_engineering_baseline_draft(
            user=self.user,
            payload={"orderNo": order.order_no, "candidateId": candidate["candidateId"], "reason": "并发版本演练"},
            idempotency_key="concurrency-save-1",
        )
        with self.assertRaisesMessage(ProductVersionManagementError, "其他人员更新"):
            confirm_order_engineering_baseline(
                user=self.user,
                payload={"baselineId": saved["selectedBaseline"]["baselineId"], "expectedVersion": 99, "reason": "过期版本"},
                idempotency_key="version-conflict-1",
            )

    def test_post_api_saves_and_reads_back_the_same_baseline(self):
        order, line = self._order("SO-API-ROUNDTRIP", self._material("API-ROUNDTRIP"), "ORDER_ENGINEERED")
        self._design(line, "FORMAL-001")
        candidate = product_version_management_facts(self.company.pk, order.order_no, user=self.user)["candidateBaseline"]
        request = APIRequestFactory().post(
            "/api/pde/product-version-management/",
            {
                "action": "saveDraft",
                "orderNo": order.order_no,
                "candidateId": candidate["candidateId"],
                "reason": "接口保存与读回测试",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-save-roundtrip-1",
        )
        force_authenticate(request, user=self.user)
        response = ProductVersionManagementView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["idempotentReplay"])
        selected = response.data["selectedBaseline"]
        self.assertEqual(selected["statusCode"], "draft")
        self.assertEqual(selected["scopeItemCount"], 1)
        self.assertEqual(len(selected["items"]), 1)
        self.assertEqual(selected["items"][0]["itemNo"], f"{order.order_no}-DES-01-FORMAL-001")

    def test_save_permission_is_denied_without_explicit_role_grant(self):
        denied_user = User.objects.create_user(
            username="baseline-readonly-user",
            password="test-only",
            company_id=self.company.pk,
        )
        order, line = self._order("SO-PERMISSION-DENIED", self._material("PERMISSION-DENIED"), "ORDER_ENGINEERED")
        self._design(line, "FORMAL-001")
        facts = product_version_management_facts(self.company.pk, order.order_no, user=denied_user)
        self.assertFalse(facts["persistenceCapability"]["saveDraftAllowed"])
        with self.assertRaises(ProductVersionManagementError) as raised:
            save_order_engineering_baseline_draft(
                user=denied_user,
                payload={
                    "orderNo": order.order_no,
                    "candidateId": facts["candidateBaseline"]["candidateId"],
                    "reason": "无授权用户尝试保存",
                },
                idempotency_key="permission-denied-1",
            )
        self.assertEqual(raised.exception.code, "PERMISSION_DENIED")
