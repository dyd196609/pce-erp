from datetime import date, datetime
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from masterdata.models import Material, UnitOfMeasure
from sales.development_contract_sample import EXPECTED_SOURCE_CONTENT_HASH
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, Permission, Position, Role, RolePermission,
    User, UserRoleScopeAssignment,
)
from pfm.models import Employee
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, ProcessDefinition, WorkflowInstance,
)
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import (
    EngineeringBreakdownOption, EngineeringDocument, EngineeringSourceRecord,
    ManufacturingProcessType, OrderCrossFunctionalReview,
    OrderCrossFunctionalReviewItem, OrderEngineeringInstance, ProductBOM,
    ProductDesignCompletionRecord, ProductDesignItem, ProductDesignPlanRevision,
    ProductDesignRevision,
    ProductCategory, ProductDefinition, ProductManufacturingOutput, ProductRequirement,
    ProductVersion, Routing,
)
from .order_demand_preparation_service import (
    OrderDemandPreparationError, prepare_order_demand, preparation_facts,
    requirement_facts,
)
from .product_design_service import (
    ProductDesignError, add_product_design_item, delete_product_design_item,
    initialize_product_design_items, product_design_facts,
    record_design_completion, save_design_content, save_design_plan,
    save_product_design_draft,
)
from .product_design_import_service import (
    HEADERS, build_product_design_import_template, commit_product_design_import,
    parse_product_design_import,
)
from .product_design_export_service import export_product_design_excel


class OrderDemandPreparationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(id=1, code="COMP001", name="掌云智造科技有限公司")
        department = Department.objects.create(company=self.company, code="JHWKB", name="计划物控部")
        position = Position.objects.create(company=self.company, department=department, code="JHWKB-PLAN", name="计划员")
        self.user = User.objects.create_user(username="planner", password="test-only", company_id=1, real_name="计划员")
        employee = Employee.objects.create(
            user=self.user, employee_no="EMP107", full_name="计划员", status="active",
            department_ref=department, position_ref=position,
        )
        self.employee = employee
        permission, _ = Permission.objects.get_or_create(
            code="production.engineering.readiness.maintain",
            defaults={"name": "维护工程准备", "module": "PDE"},
        )
        role = Role.objects.create(code="PLAN_OPERATOR_V1", name="计划运行验收角色")
        RolePermission.objects.create(role=role, permission=permission)
        design_permission, _ = Permission.objects.get_or_create(
            code="production.engineering.source.maintain",
            defaults={"name": "维护工程来源与产品设计草稿", "module": "PDE"},
        )
        RolePermission.objects.create(role=role, permission=design_permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="test",
        )
        customer = Customer.objects.create(company=self.company, code="DLR-S07-002", name="上海王燕")
        unit = UnitOfMeasure.objects.create(company_id=self.company.pk, code="套", name="套", dimension="count")
        material = Material.objects.create(
            company_id=self.company.pk, code="DEV-SC-LINE", name="开发产品", unit="套",
            base_uom=unit, unit_status="confirmed", material_type="finished", price=0,
        )
        self.order = create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft",
            company=self.company, department=department, customer=customer,
            order_no="SO202609180001", order_date=date(2026, 9, 15),
            required_delivery_date=date(2026, 10, 30), currency="CNY",
            order_type="project", order_source="import", project_reference="上海 大居苑",
            contract_reference="PCE-DEV-SC-20260915-001", external_source_no="1-4-正",
            delivery_information={"developmentContract": {"developmentOnly": True}},
            version=1, acceptance_marker="DEVELOPMENT_ONLY",
            sales_owner=employee, created_by=self.user,
        )
        self.items = []
        for line_no in range(1, 5):
            item = SalesOrderItem.objects.create(
                sales_order=self.order, line_no=line_no, material=material,
                engineering_mode="ORDER_ENGINEERED", quantity=line_no, uom=unit,
                unit_price=100, tax_rate="0.13", price_tax_mode="tax_inclusive",
                required_date=date(2026, 10, 20), customer_product_name=f"开发产品{line_no}",
                external_line_no=f"DEV-L{line_no:02d}",
            )
            self.items.append(item)
            SalesOrderItemEngineeringAttribute.objects.create(
                sales_order_item=item, sequence=1, raw_source="1-4-正",
                raw_sheet="三合一生产单", external_source=f"三合一生产单!{67 + line_no}",
                raw_field="controlled_engineering_row",
                raw_value={
                    "id": f"三合一生产单!{67 + line_no}", "sourceRow": 67 + line_no,
                    "space": f"空间{line_no}", "product": f"开发产品{line_no}",
                    "component": "L型木饰面", "length": 2300 + line_no,
                    "width": 800, "thickness": 18, "quantity": line_no,
                    "unitName": "套", "materialProcessCode": "WOOD-18",
                    "visibleCondition": "单", "edgeMode": "四边",
                    "sourceEvidence": {
                        "I": {"value": "半透工艺"}, "AD": {"value": "暖灰"},
                    },
                },
                canonical_field="controlled_engineering_row",
                normalized_value={"lineNo": line_no}, value_type="json", unit=unit,
                source_type="ENGINEERING_INPUT", created_by=self.user,
            )
        source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="1-4-正", source_name="1-4-正",
            source_type="controlled_import", source_version="R20260915144257758338",
            content_hash=EXPECTED_SOURCE_CONTENT_HASH,
            source_payload={
                "engineeringRows": [],
                "confirmedResponsibilityFacts": {
                    "designer": {"employeeId": employee.pk},
                    "breakdownOwner": {"employeeId": employee.pk},
                },
                "businessOrderReference": {"projectName": "上海 大居苑"},
            },
        )
        crm_review = OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=source,
            review_type="CRM_ORDER_REVIEW", source_order_no="1-4-正",
            source_version="R20260915144257758338", source_content_hash=EXPECTED_SOURCE_CONTENT_HASH,
            review_version=1, conclusion="", reviewer=self.user,
            idempotency_key="crm-review-v1", audit_hash="c" * 64,
            record_status="SUBMITTED", submitted_at=datetime(2026, 9, 18, 11, 0, 0),
        )
        crm_process = ProcessDefinition.objects.create(
            definition_code="CRM_ORDER_REVIEW_FINAL_APPROVAL_TEST",
            definition_name="订单评审最终审批", business_domain="CRM",
            document_type="CRMOrderReview", version=1,
            active=True, definition_hash="crm-process",
        )
        crm_workflow = WorkflowInstance.objects.create(
            instance_no="CRM-APPROVAL-1", process_definition=crm_process,
            document_type="CRMOrderReview", document_id=crm_review.pk,
            status="approved", current_step=1, total_steps=1, version=2,
        )
        crm_task = ApprovalTask.objects.create(
            task_no="CRM-TASK-1", workflow_instance=crm_workflow, step_no=1,
            required_role_code="", status="approved", version=2,
        )
        ApprovalDecision.objects.create(
            task=crm_task, decision_sequence=1, actor=self.user, decision="approved",
            comment="通过", action_id="crm-approve-1", idempotency_key="crm-approve-1",
            decision_hash="crm-decision",
        )
        review = OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=source,
            review_type="PDE_PRODUCTION_FEASIBILITY", source_order_no="1-4-正",
            source_version="R20260915144257758338", source_content_hash=EXPECTED_SOURCE_CONTENT_HASH,
            review_version=2, conclusion="ACCEPT", reviewer=self.user,
            idempotency_key="review-v2", audit_hash="a" * 64,
            record_status="SUBMITTED", submitted_at=datetime(2026, 9, 18, 12, 0, 0),
        )
        for index in range(10):
            OrderCrossFunctionalReviewItem.objects.create(
                review=review, stable_key=f"ITEM-{index}", item_kind="FIXED",
                item_code=f"{index + 1:02d}", item_text=f"事项{index + 1}",
                responsible_employee=employee, signature_status="SIGNED",
                signed_by_user=self.user, signed_employee_id_snapshot=employee.pk,
                signed_employee_no_snapshot=employee.employee_no,
                signed_employee_name_snapshot=employee.full_name,
                signed_at=datetime(2026, 9, 18, 12, 0, 0), signature_content_hash=f"{index + 1:064x}",
                display_order=index + 1,
            )
        process = ProcessDefinition.objects.create(
            definition_code="PDE_PRODUCTION_FEASIBILITY_FINAL_APPROVAL",
            definition_name="生产可行性评审最终审批", business_domain="PDE",
            document_type="PDEProductionFeasibilityReview", version=1,
            active=True, definition_hash="process",
        )
        workflow = WorkflowInstance.objects.create(
            instance_no="PDE-APPROVAL-1", process_definition=process,
            document_type="PDEProductionFeasibilityReview", document_id=review.pk,
            status="approved", current_step=1, total_steps=1, version=2,
        )
        task = ApprovalTask.objects.create(
            task_no="PDE-TASK-1", workflow_instance=workflow, step_no=1,
            required_role_code="", status="approved", version=2,
        )
        ApprovalDecision.objects.create(
            task=task, decision_sequence=1, actor=self.user, decision="approved",
            comment="通过", action_id="approve-1", idempotency_key="approve-1",
            decision_hash="decision",
        )
        self.client.force_authenticate(self.user)

    def test_prepare_persists_four_requirements_and_stops_before_design(self):
        facts, replayed = prepare_order_demand(user=self.user, idempotency_key="prepare-1")
        self.assertFalse(replayed)
        self.assertEqual(ProductRequirement.objects.count(), 4)
        self.assertEqual(len(requirement_facts(self.company.pk)), 4)
        self.assertEqual(len(facts["rows"]), 4)
        self.assertTrue(all(row["engineeringStatusLabel"] == "工程输入已准备，待产品设计" for row in facts["rows"]))
        self.assertTrue(all(row["mrpReadyStatusLabel"] == "未准备" for row in facts["rows"]))
        replay_facts, replayed = prepare_order_demand(user=self.user, idempotency_key="prepare-1")
        self.assertTrue(replayed)
        self.assertEqual(len(replay_facts["requirements"]), 4)
        self.assertEqual(ProductRequirement.objects.count(), 4)

    def test_explicit_crm_reject_blocks_without_changing_historical_objects(self):
        source = EngineeringSourceRecord.objects.get(source_no="1-4-正")
        OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=source,
            review_type="CRM_ORDER_REVIEW", source_order_no="1-4-正",
            source_version=source.source_version, source_content_hash=source.content_hash,
            review_version=2, conclusion="REJECT", reviewer=self.user,
            idempotency_key="crm-reject-v2", audit_hash="d" * 64,
            record_status="SUBMITTED", submitted_at=datetime(2026, 9, 18, 13, 0, 0),
        )
        before = {
            "orders": SalesOrder.objects.count(),
            "instances": OrderEngineeringInstance.objects.count(),
            "requirements": ProductRequirement.objects.count(),
        }
        with self.assertRaises(OrderDemandPreparationError) as caught:
            prepare_order_demand(user=self.user, idempotency_key="blocked-reject")
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED")
        self.assertEqual(before, {
            "orders": SalesOrder.objects.count(),
            "instances": OrderEngineeringInstance.objects.count(),
            "requirements": ProductRequirement.objects.count(),
        })
    def test_missing_maintain_permission_is_rejected_without_partial_write(self):
        RolePermission.objects.all().delete()
        with self.assertRaises(OrderDemandPreparationError) as raised:
            prepare_order_demand(user=self.user, idempotency_key="prepare-denied")
        self.assertEqual(raised.exception.code, "PERMISSION_DENIED")
        self.assertEqual(ProductRequirement.objects.count(), 0)

    def test_read_projection_uses_approved_review_and_has_no_downstream_objects(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-read")
        facts = preparation_facts(self.company.pk)
        self.assertEqual(facts["review"].review_version, 2)
        self.assertEqual(facts["approval"].decision, "approved")
        self.assertEqual({row["nextActionLabel"] for row in facts["rows"]}, {"等待用户确认后进入产品设计"})

    def test_normal_pages_share_the_same_server_authority(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-pages")
        requirements = self.client.get("/api/pde/product-requirements/")
        readiness = self.client.get("/api/pde/engineering-readiness/")
        self.assertEqual(requirements.status_code, 200)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(requirements.data["strictFacts"]["customerOrderDemandCount"], 4)
        self.assertEqual(readiness.data["strictFacts"]["requirementCount"], 4)
        self.assertEqual(readiness.data["strictFacts"]["approvalStatus"], "APPROVED")
        self.assertEqual(readiness.data["strictFacts"]["nextStage"], "WAITING_USER_CONFIRMATION_FOR_PRODUCT_DESIGN")
        self.assertEqual(requirements.data["factLoadFacts"]["factLoadStatus"], "loaded")
        self.assertEqual(readiness.data["factLoadFacts"]["factLoadStatus"], "loaded")
        self.assertEqual(requirements.data["factLoadFacts"]["apiUrl"], "/api/pde/product-requirements/")
        self.assertEqual(readiness.data["factLoadFacts"]["apiUrl"], "/api/pde/engineering-readiness/")

    def test_unauthenticated_read_is_not_reported_as_empty(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/pde/product-requirements/")
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(response.data["factLoadFacts"]["factLoadStatus"], "read_failed")
        self.assertNotEqual(response.data.get("rows"), [])

    def _design_payload(self, item=None, expected_revision=0):
        item = item or self.items[-1]
        return {
            "salesOrderItemId": item.pk,
            "expectedRevision": expected_revision,
            "ownerEmployeeId": self.employee.pk,
            "designSolution": {
                "length": "2325", "width": "800", "thickness": "18",
                "material": "模拟方案：18mm多层板基材", "finish": "半透工艺",
                "color": "暖灰", "configurationNotes": "SIMULATED_FOR_TEST",
                "designNotes": "首轮产品设计草稿，仅验证保存与回读。",
                "hardware": "", "glass": "",
            },
            "reason": "自动化验收产品设计草稿",
        }

    def test_product_design_projects_four_objects_and_source_values(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-read")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-read", expected_count=4,
        )
        facts = product_design_facts(self.company.pk, user=self.user)
        self.assertEqual(facts["recordCount"], 4)
        self.assertEqual(facts["actualSourceCounts"]["total"], 4)
        self.assertEqual([group["productItemCount"] for group in facts["groups"]], [1, 1, 1, 1])
        self.assertEqual(facts["rows"][-1]["designDataNature"], "EXISTING_DESIGN_IMPORTED")
        self.assertEqual(facts["rows"][-1]["existingDesign"]["designThickness"], 18)
        self.assertEqual(facts["completedFactCount"], 4)
        self.assertEqual(facts["datedCompletionCount"], 0)
        self.assertEqual(facts["performanceIncludedCount"], 0)
        self.assertEqual(facts["sourceContext"]["sourceVersion"], "R20260915144257758338")

    def test_product_design_save_readback_idempotency_and_isolation(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-save")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-save", expected_count=4,
        )
        facts, replayed = save_product_design_draft(
            user=self.user, payload=self._design_payload(), idempotency_key="design-save-1",
        )
        self.assertFalse(replayed)
        selected = next(row for row in facts["rows"] if row["orderLineNo"] == self.items[-1].line_no)
        self.assertEqual(selected["designRevision"]["revision"], 1)
        self.assertEqual(selected["designRevision"]["designNature"], "SIMULATED_FOR_TEST")
        replay_facts, replayed = save_product_design_draft(
            user=self.user, payload=self._design_payload(), idempotency_key="design-save-1",
        )
        self.assertTrue(replayed)
        self.assertEqual(replay_facts["designRevisionCount"], 1)
        self.assertEqual(ProductDesignRevision.objects.count(), 1)
        prep = preparation_facts(self.company.pk)
        statuses = {row["id"]: row["engineeringStatusLabel"] for row in prep["rows"]}
        self.assertTrue(all(status == "已有设计完成·历史日期待补（1/1）" for status in statuses.values()))

    def test_simulated_revision_is_preserved_when_real_source_becomes_formal_revision(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-formalize")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-formalize", expected_count=4,
        )
        simulated_facts, replayed = save_product_design_draft(
            user=self.user, payload=self._design_payload(), idempotency_key="design-simulated-r1",
        )
        self.assertFalse(replayed)
        simulated_row = next(
            row for row in simulated_facts["rows"]
            if row["orderLineNo"] == self.items[-1].line_no
        )
        item = ProductDesignItem.objects.get(pk=simulated_row["id"])
        simulated_revision = item.design_revisions.get(revision=1)

        category = ProductCategory.objects.create(
            company=self.company, code="FINISH", name="饰面", is_active=True,
        )
        millimeter = UnitOfMeasure.objects.create(
            company_id=self.company.pk, code="mm", name="毫米", dimension="length",
        )
        material = Material.objects.create(
            company_id=self.company.pk, code="MAT-FORMAL-BTKF", name="半透开放实木多层板",
            specification="半透开放", unit="张", base_uom=millimeter,
            unit_status="confirmed", material_type="semi", price=0,
        )
        paint = ManufacturingProcessType.objects.create(
            company=self.company, code="BTKF", name="半透开放", is_active=True,
        )
        route = Routing.objects.create(
            company=self.company, applicability_scope="PRODUCT_CATEGORY",
            product_category=category, manufacturing_process_type=paint,
            routing_code="BTKF/SM", name="半透开放饰面", status="released", is_active=True,
        )
        edge = EngineeringBreakdownOption.objects.create(
            company=self.company,
            option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
            code="EDGE-FOUR-SIDES", name="四边", is_active=True,
        )
        item.product_category = category
        item.save(update_fields=["product_category"])
        facts = product_design_facts(self.company.pk, user=self.user)
        configuration = next(
            option for option in facts["masterOptions"]["processConfigurations"]
            if option["routeId"] == route.pk
        )
        color = next(
            option for option in facts["masterOptions"]["colorVersionOptions"]
            if option["name"] == "暖灰"
        )
        formal_facts, replayed = save_design_content(
            user=self.user,
            payload={
                "designItemIds": [item.pk],
                "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL",
                "reason": "依据真实来源和受控主数据建立正式修订",
                "designData": {
                    "productCategoryId": category.pk,
                    "physicalUomId": self.items[-1].uom_id,
                    "designUomId": millimeter.pk,
                    "designLength": "2325", "designWidth": "800", "designThickness": "18",
                    "materialId": material.pk,
                    "processConfigurationId": configuration["id"],
                    "paintProcessTypeId": paint.pk,
                    "edgeMethodId": edge.pk,
                    "visibleConditionCode": "SINGLE_FACE",
                    "colorVersionOptionId": color["id"],
                },
            },
            idempotency_key="design-formal-r2",
        )
        self.assertFalse(replayed)
        formal_row = next(row for row in formal_facts["rows"] if row["id"] == item.pk)
        self.assertEqual(formal_row["designRevision"]["revision"], 2)
        self.assertEqual(formal_row["designRevision"]["designNature"], "FORMAL")
        self.assertEqual(formal_row["designRevision"]["materialId"], material.pk)
        self.assertEqual(formal_row["designRevision"]["processConfigurationCode"], "BTKF/SM")
        self.assertEqual(formal_row["designRevision"]["visibleConditionCode"], "SINGLE_FACE")
        self.assertEqual(item.design_revisions.count(), 2)
        simulated_revision.refresh_from_db()
        self.assertEqual(simulated_revision.design_nature, "SIMULATED_FOR_TEST")
        self.assertEqual(simulated_revision.revision, 1)
        self.assertEqual(ProductVersion.objects.count(), 0)
        self.assertEqual(ProductBOM.objects.count(), 0)
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)

    def test_product_design_guards_permission_validation_concurrency_and_downstream(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-guards")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-guards", expected_count=4,
        )
        downstream_before = {
            "products": ProductDefinition.objects.count(), "versions": ProductVersion.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(), "boms": ProductBOM.objects.count(),
            "routings": Routing.objects.count(), "documents": EngineeringDocument.objects.count(),
            "outputs": ProductManufacturingOutput.objects.count(),
        }
        with self.assertRaises(ProductDesignError) as invalid:
            item = ProductDesignItem.objects.first()
            save_design_content(user=self.user, payload={
                "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL", "reason": "非法字段验证",
                "designData": {"uncontrolledField": "x"},
            }, idempotency_key="design-invalid")
        self.assertEqual(invalid.exception.code, "DESIGN_FIELD_NOT_ALLOWED")
        item = ProductDesignItem.objects.first()
        save_design_content(user=self.user, payload={
            "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
            "designNature": "FORMAL", "reason": "并发前正常保存",
            "designData": {"designNotes": "受控设计内容"},
        }, idempotency_key="design-guard-save",
        )
        with self.assertRaises(ProductDesignError) as stale:
            save_design_content(user=self.user, payload={
                "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL", "reason": "旧版本覆盖验证",
                "designData": {"designNotes": "不得覆盖"},
            }, idempotency_key="design-stale",
            )
        self.assertEqual(stale.exception.code, "DESIGN_ITEM_VERSION_CONFLICT")
        downstream_after = {
            "products": ProductDefinition.objects.count(), "versions": ProductVersion.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(), "boms": ProductBOM.objects.count(),
            "routings": Routing.objects.count(), "documents": EngineeringDocument.objects.count(),
            "outputs": ProductManufacturingOutput.objects.count(),
        }
        self.assertEqual(downstream_before, downstream_after)

    def test_product_design_row_dropdowns_preserve_other_rows_and_normalize_visible_condition(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-dropdowns")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-dropdowns", expected_count=4,
        )
        category = ProductCategory.objects.create(
            company=self.company, code="DOOR", name="门类", is_active=True,
        )
        process = ManufacturingProcessType.objects.create(
            company=self.company, code="BTKF", name="半透工艺", is_active=True,
        )
        edge = EngineeringBreakdownOption.objects.create(
            company=self.company, option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
            code="EDGE-4", name="四边", is_active=True,
        )
        selected = ProductDesignItem.objects.order_by("pk").first()
        selected.existing_design_data = {
            **selected.existing_design_data, "routingProcessCode": "WOOD-18", "paintProcess": "半透工艺",
        }
        selected.product_category = category
        selected.save(update_fields=["existing_design_data", "product_category"])
        route = Routing.objects.create(
            company=self.company, applicability_scope="PRODUCT_CATEGORY",
            product_category=category, manufacturing_process_type=process,
            routing_code="WOOD-18", name="半透工艺正式路线", status="released", is_active=True,
        )
        other_process = ManufacturingProcessType.objects.create(
            company=self.company, code="QSFB", name="清水封闭", is_active=True,
        )
        Routing.objects.create(
            company=self.company, applicability_scope="PRODUCT_CATEGORY",
            product_category=category, manufacturing_process_type=other_process,
            routing_code="QSFB/FM", name="清水封闭房门正式路线", status="released", is_active=True,
        )
        facts = product_design_facts(self.company.pk, user=self.user)
        self.assertEqual([row["code"] for row in facts["masterOptions"]["visibleConditions"]], [
            "SINGLE_FACE", "DOUBLE_FACE", "UNFINISHED", "EXPLICIT_NONE", "NOT_APPLICABLE", "UNKNOWN",
        ])
        color_option = next(
            row for row in facts["masterOptions"]["colorVersionOptions"] if row["name"] == "暖灰"
        )
        untouched = ProductDesignItem.objects.order_by("pk")[1]
        untouched_version = untouched.version
        configuration = next(
            row for row in facts["masterOptions"]["processConfigurations"]
            if row["code"] == selected.existing_design_data["routingProcessCode"]
        )
        self.assertEqual(configuration["routeId"], route.pk)
        self.assertEqual(configuration["source"], "pde.Routing")
        self.assertEqual(configuration["paintProcessTypeId"], process.pk)
        self.assertTrue(configuration["selectable"])
        self.assertEqual(
            {row["code"] for row in facts["masterOptions"]["processConfigurations"] if row["source"] == "pde.Routing"},
            {"WOOD-18", "QSFB/FM"},
        )
        saved, replayed = save_design_content(user=self.user, payload={
            "designItemIds": [selected.pk],
            "expectedVersions": {str(selected.pk): selected.version},
            "designNature": "FORMAL",
            "reason": "验证本行正式下拉及语义归一",
            "designData": {
                "productCategoryId": category.pk,
                "physicalUomId": self.items[0].uom_id,
                "processConfigurationId": configuration["id"],
                "paintProcessTypeId": process.pk,
                "edgeMethodId": edge.pk,
                "visibleConditionCode": "SINGLE_FACE",
                "colorVersionOptionId": color_option["id"],
            },
        }, idempotency_key="design-dropdown-save")
        self.assertFalse(replayed)
        saved_row = next(row for row in saved["rows"] if row["id"] == selected.pk)
        self.assertEqual(saved_row["designRevision"]["visibleConditionCode"], "SINGLE_FACE")
        self.assertEqual(saved_row["designRevision"]["visibleCondition"], "单")
        self.assertEqual(saved_row["designRevision"]["finishOrColor"], "暖灰")
        self.assertEqual(saved_row["designRevision"]["edgeMethodId"], edge.pk)
        self.assertEqual(saved_row["designRevision"]["processConfigurationCode"], "WOOD-18")
        self.assertEqual(saved_row["designRevision"]["paintProcessTypeId"], process.pk)
        self.assertEqual(saved_row["listValues"]["processConfigurationCode"], "WOOD-18")
        self.assertEqual(saved_row["listValues"]["processConfigurationName"], "半透工艺正式路线")
        self.assertEqual(saved_row["listValues"]["paintProcessCode"], "BTKF")
        self.assertEqual(saved_row["listValues"]["paintProcessName"], "半透工艺")
        untouched.refresh_from_db()
        self.assertEqual(untouched.version, untouched_version)
        self.assertEqual(ProductDesignRevision.objects.count(), 1)
        selected.refresh_from_db()
        with self.assertRaises(ProductDesignError) as wrong_type:
            save_design_content(user=self.user, payload={
                "designItemIds": [selected.pk],
                "expectedVersions": {str(selected.pk): selected.version},
                "designNature": "FORMAL", "reason": "错误类型ID必须拒绝",
                "designData": {"materialProcessTypeId": process.pk},
            }, idempotency_key="design-wrong-process-type")
        self.assertEqual(wrong_type.exception.code, "PROCESS_CONFIGURATION_TYPE_INVALID")

        selected.refresh_from_db()
        with self.assertRaises(ProductDesignError) as incompatible_paint:
            save_design_content(user=self.user, payload={
                "designItemIds": [selected.pk],
                "expectedVersions": {str(selected.pk): selected.version},
                "designNature": "FORMAL", "reason": "验证只改油漆时仍检查当前完整配置",
                "designData": {"paintProcessTypeId": other_process.pk},
            }, idempotency_key="design-paint-incompatible-with-current-configuration")
        self.assertEqual(incompatible_paint.exception.code, "PROCESS_CONFIGURATION_PAINT_INCOMPATIBLE")

    def test_unresolved_source_configuration_is_preserved_without_blocking_unrelated_edit(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-unresolved-config")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-unresolved-config", expected_count=4,
        )
        process = ManufacturingProcessType.objects.create(
            company=self.company, code="BTKF", name="半透开放", is_active=True,
        )
        selected = ProductDesignItem.objects.order_by("pk").first()
        selected.existing_design_data = {
            **selected.existing_design_data,
            "routingProcessCode": "BTKF/GT", "paintProcess": "半透工艺",
        }
        selected.save(update_fields=["existing_design_data"])
        facts = product_design_facts(self.company.pk, user=self.user)
        configuration = next(
            row for row in facts["masterOptions"]["processConfigurations"]
            if row["code"] == "BTKF/GT"
        )
        self.assertFalse(configuration["selectable"])
        self.assertEqual(configuration["paintLinkStatus"], "NO_FORMAL_ROUTING")
        source_row = next(row for row in facts["rows"] if row["id"] == selected.pk)
        self.assertEqual(source_row["listValues"]["processConfigurationCode"], "BTKF/GT")
        self.assertEqual(source_row["listValues"]["processConfigurationName"], "未匹配正式工艺路线，保留来源值")

        saved, replayed = save_design_content(user=self.user, payload={
            "designItemIds": [selected.pk],
            "expectedVersions": {str(selected.pk): selected.version},
            "designNature": "FORMAL", "reason": "只修改设计说明并保留来源配置",
            "designData": {"designNotes": "不触碰未唯一匹配的工艺关系"},
        }, idempotency_key="design-preserve-unresolved-configuration")
        self.assertFalse(replayed)
        saved_row = next(row for row in saved["rows"] if row["id"] == selected.pk)
        self.assertEqual(saved_row["designRevision"]["processConfigurationCode"], "BTKF/GT")
        self.assertIsNone(saved_row["designRevision"]["paintProcessTypeId"])

        selected.refresh_from_db()
        with self.assertRaises(ProductDesignError) as unresolved_paint:
            save_design_content(user=self.user, payload={
                "designItemIds": [selected.pk],
                "expectedVersions": {str(selected.pk): selected.version},
                "designNature": "FORMAL", "reason": "不得猜测油漆关系",
                "designData": {"paintProcessTypeId": process.pk},
            }, idempotency_key="design-unresolved-paint-rejected")
        self.assertEqual(unresolved_paint.exception.code, "PROCESS_CONFIGURATION_PAINT_UNRESOLVED")

    def test_source_name_does_not_create_formal_product_link_and_design_still_saves(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-existing-design-edit")
        category = ProductCategory.objects.create(
            company=self.company, code="FORMAL-DOOR", name="正式门类", is_active=True,
        )
        order_material = self.items[0].material
        product = ProductDefinition.objects.create(
            company=self.company, category=category, material=order_material,
            product_code="FORMAL-PRODUCT-01", product_name="开发产品1",
            specification="单开门", emd_material_code=order_material.code,
            status="released", is_active=True,
        )
        design_material = Material.objects.create(
            company_id=self.company.pk, code="MAT-WOOD-18", name="胡桃木板",
            specification="18mm", unit="套", base_uom=self.items[0].uom,
            unit_status="confirmed", material_type="raw", price=0,
        )
        paint = ManufacturingProcessType.objects.create(
            company=self.company, code="PAINT-BTKF", name="半透开放漆", is_active=True,
        )
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-existing-design-edit", expected_count=4,
        )
        item = ProductDesignItem.objects.order_by("pk").first()
        self.assertIsNone((item.match_results["productDefinition"])["matchedId"])
        self.assertEqual((item.match_results["productDefinition"])["status"], "SOURCE_IDENTITY_ONLY")
        self.assertIsNone(item.product_definition_id)

        before = product_design_facts(self.company.pk, user=self.user)
        row = next(value for value in before["rows"] if value["id"] == item.pk)
        self.assertIsNone(row["productDefinitionId"])
        self.assertFalse(row["productDefinitionPersisted"])
        self.assertEqual(row["productDefinitionBindingSource"], "unlinked")
        self.assertEqual(row["engineeringIdentityStatusCode"], "SOURCE_PRODUCT_UNFORMALIZED")
        self.assertEqual(row["engineeringIdentityStatusLabel"], "来源产品待正式化")
        self.assertTrue(row["engineeringIdentityFacts"]["orderEngineeringAllowed"])
        self.assertTrue(row["engineeringIdentityFacts"]["standardBomBlocked"])
        self.assertEqual(
            next(value for value in before["masterOptions"]["products"] if value["id"] == product.pk)["category_id"],
            category.pk,
        )

        saved, replayed = save_design_content(
            user=self.user,
            payload={
                "designItemIds": [item.pk],
                "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL",
                "reason": "已有设计直接修改尺寸，不强制重新选择产品",
                "designData": {
                    "designLength": "2302", "designWidth": "801", "designThickness": "18",
                    "materialId": design_material.pk, "paintProcessTypeId": paint.pk,
                },
            },
            idempotency_key="existing-design-save-without-product-selection",
        )
        self.assertFalse(replayed)
        saved_row = next(value for value in saved["rows"] if value["id"] == item.pk)
        self.assertEqual(saved_row["designRevision"]["revision"], 1)
        self.assertEqual(saved_row["designRevision"]["designLength"], "2302.000000")
        self.assertEqual(saved_row["listValues"]["materialCode"], "MAT-WOOD-18")
        self.assertEqual(saved_row["listValues"]["materialName"], "胡桃木板")
        self.assertEqual(saved_row["listValues"]["materialSpecification"], "18mm")
        self.assertEqual(saved_row["listValues"]["paintProcessCode"], "PAINT-BTKF")
        self.assertEqual(saved_row["listValues"]["paintProcessName"], "半透开放漆")
        self.assertNotEqual(
            saved_row["listValues"]["materialSpecification"],
            saved_row["listValues"]["paintProcessName"],
        )
        item.refresh_from_db()
        self.assertIsNone(item.product_definition_id)
        self.assertEqual(ProductDefinition.objects.count(), 1)

        explicitly_linked, replayed = save_design_content(
            user=self.user,
            payload={
                "designItemIds": [item.pk],
                "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL", "reason": "人工明确关联正式产品",
                "designData": {"productCategoryId": category.pk, "productDefinitionId": product.pk},
            },
            idempotency_key="existing-design-explicit-product-link",
        )
        self.assertFalse(replayed)
        linked_row = next(value for value in explicitly_linked["rows"] if value["id"] == item.pk)
        self.assertEqual(linked_row["engineeringIdentityStatusCode"], "FORMAL_PRODUCT_LINKED")
        self.assertEqual(linked_row["productDefinitionLabel"], "开发产品1")

    def test_product_design_permission_denied_and_api_readback(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-api")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-api", expected_count=4,
        )
        RolePermission.objects.filter(permission__code="production.engineering.source.maintain").delete()
        with self.assertRaises(ProductDesignError) as denied:
            save_product_design_draft(
                user=self.user, payload=self._design_payload(), idempotency_key="design-denied",
            )
        self.assertEqual(denied.exception.http_status, 403)
        response = self.client.get("/api/pde/product-definitions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["strictFacts"]["recordCount"], 4)

    def test_user_added_design_item_can_be_deleted_before_history_exists(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-user-item")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-user-item", expected_count=4,
        )
        category = ProductCategory.objects.create(
            company=self.company, code="CUSTOM-CABINET", name="定制柜体", is_active=True,
        )
        unit = UnitOfMeasure.objects.get(company_id=self.company.pk, code="套")
        facts, replayed = add_product_design_item(
            user=self.user,
            payload={
                "orderLineNo": 1, "itemName": "用户补录柜门",
                "installationPosition": "测试位置", "physicalQuantity": "1",
                "physicalUomId": unit.pk, "productCategoryId": category.pk,
                "designLength": "900", "designWidth": "450", "designThickness": "18",
                "dimensionSemantic": "部件厚", "reason": "隔离测试新增",
            },
            idempotency_key="design-user-item-add",
        )
        self.assertFalse(replayed)
        self.assertEqual(facts["recordCount"], 5)
        added = ProductDesignItem.objects.get(item_name="用户补录柜门")
        source_attribute_id = added.source_attribute_id
        facts, replayed = delete_product_design_item(
            user=self.user,
            payload={
                "designItemIds": [added.pk],
                "expectedVersions": {str(added.pk): added.version},
                "reason": "隔离测试撤销未引用新增项",
            },
            idempotency_key="design-user-item-delete",
        )
        self.assertFalse(replayed)
        self.assertEqual(facts["recordCount"], 4)
        self.assertFalse(ProductDesignItem.objects.filter(pk=added.pk).exists())
        self.assertFalse(SalesOrderItemEngineeringAttribute.objects.filter(pk=source_attribute_id).exists())

    def test_source_backed_design_item_delete_is_protected(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-delete-protected")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-delete-protected", expected_count=4,
        )
        item = ProductDesignItem.objects.order_by("pk").first()
        with self.assertRaises(ProductDesignError) as protected:
            delete_product_design_item(
                user=self.user,
                payload={
                    "designItemIds": [item.pk],
                    "expectedVersions": {str(item.pk): item.version},
                    "reason": "验证来源历史保护",
                },
                idempotency_key="design-delete-protected",
            )
        self.assertEqual(protected.exception.code, "DESIGN_ITEM_DELETE_PROTECTED")
        self.assertTrue(ProductDesignItem.objects.filter(pk=item.pk).exists())

    def test_product_design_import_requires_preview_and_creates_one_formal_revision(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-import")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-import", expected_count=4,
        )
        category = ProductCategory.objects.create(
            company=self.company, code="IMPORT-CABINET", name="导入柜体", is_active=True,
        )
        item = ProductDesignItem.objects.order_by("pk").first()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "产品设计导入"
        for column, header in enumerate(HEADERS, 1):
            sheet.cell(5, column, header)
        values = {
            "操作": "更新", "产品标识": item.item_no,
            "订单行号": item.sales_order_item.line_no, "来源名称": item.item_name,
            "空间/安装位置": item.installation_position_snapshot, "实物数量": "1",
            "单位": "套", "设计长度": "1200", "设计宽度": "600",
            "第三尺寸": "18", "第三尺寸语义": "部件厚",
            "产品分类": category.code, "设计说明": "隔离导入测试",
            "修订原因": "验证预览后单次提交",
        }
        for column, header in enumerate(HEADERS, 1):
            sheet.cell(6, column, values.get(header, ""))
        buffer = BytesIO()
        workbook.save(buffer)
        content = buffer.getvalue()
        preview_file = SimpleUploadedFile("product-design.xlsx", content)
        preview = parse_product_design_import(preview_file, self.company.pk)
        self.assertEqual(preview["validCount"], 1)
        self.assertEqual(preview["errorCount"], 0)
        result = commit_product_design_import(
            uploaded_file=SimpleUploadedFile("product-design.xlsx", content),
            user=self.user, preview_fingerprint=preview["previewFingerprint"],
            idempotency_key="design-import-commit", confirmed=True,
        )
        self.assertEqual(result["committedCount"], 1)
        item.refresh_from_db()
        self.assertEqual(item.design_revisions.count(), 1)
        self.assertEqual(item.design_revisions.get().design_data["designNotes"], "隔离导入测试")

    def test_product_design_plan_completion_dates_and_no_change_revision(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-plan")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-plan", expected_count=4,
        )
        payload = {
            "designGroups": ["DES-01", "DES-02"],
            "designerEmployeeId": self.employee.pk, "plannedStartDate": "2026-09-20",
            "plannedFinishDate": "2026-09-30", "planType": "FORMAL",
            "adjustmentReason": "建立首版设计计划",
        }
        save_design_plan(user=self.user, payload=payload, idempotency_key="plan-v1")
        self.assertEqual(ProductDesignPlanRevision.objects.count(), 2)
        save_design_plan(user=self.user, payload=payload, idempotency_key="plan-no-change")
        self.assertEqual(ProductDesignPlanRevision.objects.count(), 2)

        first = ProductDesignItem.objects.order_by("pk").first()
        first.refresh_from_db()
        completion_payload = {
            "designItemIds": [first.pk], "expectedVersions": {str(first.pk): first.version},
            "completionNature": "SIMULATED_FOR_TEST", "actualCompletionDate": "2026-09-28",
            "designerEmployeeId": self.employee.pk, "completionBasis": "仅自动化验收，不计绩效",
        }
        facts, _ = record_design_completion(
            user=self.user, payload=completion_payload, idempotency_key="completion-simulated",
        )
        row = next(value for value in facts["rows"] if value["id"] == first.pk)
        self.assertEqual(row["completion"]["actualCompletionDate"], "2026-09-28")
        self.assertNotEqual(row["completion"]["registeredAt"][:10], "2026-09-28")
        self.assertFalse(row["completion"]["performanceIncluded"])
        self.assertEqual(ProductDesignCompletionRecord.objects.filter(design_item=first).count(), 2)
        first.refresh_from_db()
        completion_payload["expectedVersions"] = {str(first.pk): first.version}
        record_design_completion(
            user=self.user, payload=completion_payload, idempotency_key="completion-simulated-no-change",
        )
        self.assertEqual(ProductDesignCompletionRecord.objects.filter(design_item=first).count(), 2)

    def test_product_design_plan_requires_design_group_not_product_selection(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-plan-scope-required")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-plan-scope-required", expected_count=4,
        )
        with self.assertRaises(ProductDesignError) as blocked:
            save_design_plan(
                user=self.user,
                payload={
                    "designerEmployeeId": self.employee.pk,
                    "plannedStartDate": "2026-09-21",
                    "plannedFinishDate": "2026-09-30",
                    "planType": "FORMAL",
                },
                idempotency_key="plan-without-group",
            )
        self.assertEqual(blocked.exception.code, "DESIGN_GROUP_SELECTION_REQUIRED")
        self.assertEqual(blocked.exception.message, "请选择需要安排计划的产品设计分组。")
        self.assertEqual(ProductDesignPlanRevision.objects.count(), 0)

    def test_product_design_plan_saves_order_group_fields_and_reads_back(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-plan-group")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-plan-group", expected_count=4,
        )
        facts, replayed = save_design_plan(
            user=self.user,
            payload={
                "designGroups": ["DES-03"],
                "designerEmployeeId": self.employee.pk,
                "plannedStartDate": "2026-09-21",
                "plannedFinishDate": "2026-10-02",
                "planType": "FORMAL",
                "adjustmentReason": "柜体配套部件包设计计划",
            },
            idempotency_key="plan-group-des-03",
        )
        self.assertFalse(replayed)
        revision = ProductDesignPlanRevision.objects.get()
        self.assertEqual(revision.order_id, self.order.pk)
        self.assertEqual(revision.design_group, "DES-03")
        self.assertEqual(revision.designer_employee_id, self.employee.pk)
        self.assertEqual(revision.plan_type, "FORMAL")
        self.assertEqual(revision.adjustment_reason, "柜体配套部件包设计计划")
        self.assertIsNone(revision.design_item_id)
        group = next(row for row in facts["groups"] if row["designGroup"] == "DES-03")
        self.assertEqual(group["plan"]["id"], revision.pk)
        self.assertEqual(group["planStatusLabel"], "已完成")
        affected = [row for row in facts["rows"] if row["designGroup"] == "DES-03"]
        self.assertTrue(affected)
        self.assertTrue(all(row["plan"]["id"] == revision.pk for row in affected))

    def test_product_design_plan_multi_group_is_idempotent_and_preserves_design_history(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-plan-multi")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-plan-multi", expected_count=4,
        )
        item_ids_before = list(ProductDesignItem.objects.order_by("pk").values_list("pk", flat=True))
        design_revision_count_before = ProductDesignRevision.objects.count()
        payload = {
            "designGroups": ["DES-01", "DES-04"],
            "designerEmployeeId": self.employee.pk,
            "plannedStartDate": "2026-09-21",
            "plannedFinishDate": "2026-09-30",
            "planType": "FORMAL",
            "adjustmentReason": "门与饰面同步安排",
        }
        _, replayed = save_design_plan(
            user=self.user, payload=payload, idempotency_key="plan-multi-idempotent",
        )
        self.assertFalse(replayed)
        _, replayed = save_design_plan(
            user=self.user, payload=payload, idempotency_key="plan-multi-idempotent",
        )
        self.assertTrue(replayed)
        self.assertEqual(ProductDesignPlanRevision.objects.count(), 2)
        self.assertEqual(
            set(ProductDesignPlanRevision.objects.values_list("design_group", flat=True)),
            {"DES-01", "DES-04"},
        )
        self.assertEqual(
            list(ProductDesignItem.objects.order_by("pk").values_list("pk", flat=True)),
            item_ids_before,
        )
        self.assertEqual(ProductDesignRevision.objects.count(), design_revision_count_before)
        self.assertEqual(ProductBOM.objects.count(), 0)

    def test_product_design_plan_requires_server_permission(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-plan-permission")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-plan-permission", expected_count=4,
        )
        RolePermission.objects.filter(
            permission__code="production.engineering.source.maintain",
        ).delete()
        with self.assertRaises(ProductDesignError) as denied:
            save_design_plan(
                user=self.user,
                payload={
                    "designGroups": ["DES-01"],
                    "designerEmployeeId": self.employee.pk,
                    "plannedStartDate": "2026-09-21",
                    "plannedFinishDate": "2026-09-30",
                    "planType": "FORMAL",
                },
                idempotency_key="plan-permission-denied",
            )
        self.assertEqual(denied.exception.http_status, 403)
        self.assertEqual(ProductDesignPlanRevision.objects.count(), 0)

    def test_product_design_excel_export_uses_current_ordered_server_facts(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-export")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-export", expected_count=4,
        )
        selected = list(ProductDesignItem.objects.order_by("-pk")[:2])
        content, audit = export_product_design_excel(
            user=self.user,
            payload={
                "designItemIds": [row.pk for row in selected],
                "expectedVersions": {str(row.pk): row.version for row in selected},
                "filterSummary": {"groupNo": "DES-04"},
                "sortSummary": "产品标识 降序",
            },
        )
        workbook = load_workbook(BytesIO(content), data_only=True)
        sheet = workbook["产品设计当前结果"]
        headers = [cell.value for cell in sheet[1]]
        expected_headers = [
            "产品标识", "所属订单行", "设计分组", "来源名称", "空间/安装位置",
            "来源位置", "实物数量", "商业数量", "实物单位", "产品分类", "正式产品定义", "工程对象状态", "材料编码",
            "材料名称", "物料规格", "Routing编码", "Routing名称", "油漆工艺编码",
            "油漆工艺名称", "封边方式", "见光条件", "颜色/版号", "设计尺寸单位", "设计长度", "设计宽度",
            "第三尺寸", "第三尺寸语义", "配置说明", "设计说明", "五金要求", "玻璃要求",
            "资料引用", "设计资料性质", "当前修订原因", "设计负责人", "设计计划开工日期", "设计计划完工日期", "设计状态", "设计修订号", "完成状态",
        ]
        self.assertEqual(sheet.max_row, 3)
        self.assertEqual(headers, expected_headers)
        self.assertEqual(sheet.cell(2, 1).value, selected[0].item_no)
        self.assertEqual(workbook.sheetnames, ["产品设计当前结果", "字段说明"])
        field_sheet = workbook["字段说明"]
        self.assertEqual(
            [cell.value for cell in field_sheet[1]],
            ["字段名称", "业务含义", "数据来源", "是否允许编辑", "是否允许导入", "主数据来源"],
        )
        self.assertTrue(all(field_sheet.cell(row, 2).value for row in range(2, len(expected_headers) + 2)))
        self.assertEqual([field_sheet.cell(row, 1).value for row in range(2, len(expected_headers) + 2)], expected_headers)
        exported_text = "\n".join(str(cell.value or "") for row in workbook for line in row.iter_rows() for cell in line)
        self.assertNotIn("[object Object]", exported_text)
        facts = product_design_facts(self.company.pk, user=self.user)
        expected_row = next(row for row in facts["rows"] if row["id"] == selected[0].pk)
        self.assertEqual(
            [str(sheet.cell(2, column).value or "") for column in range(1, len(expected_headers) + 1)],
            [str(expected_row["listValues"].get(field["key"]) or "") for field in facts["listFieldContract"]],
        )
        self.assertEqual(audit.action_code, "production.product_design.export")
        self.assertEqual(audit.after_snapshot["recordCount"], 2)

        template = load_workbook(BytesIO(build_product_design_import_template()), data_only=True)
        self.assertEqual(template.sheetnames, ["产品设计导入", "字段说明"])
        template_headers = [template["产品设计导入"].cell(5, column).value for column in range(1, len(HEADERS) + 1)]
        self.assertEqual(template_headers, list(HEADERS))
        shared_business_labels = [field["label"] for field in facts["listFieldContract"]]
        self.assertEqual(template_headers[:len(shared_business_labels)], shared_business_labels)
        self.assertEqual(
            template_headers[len(shared_business_labels):],
            ["操作", "订单行号", "修订原因"],
        )

        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/pde/product-definitions/export/",
            {
                "designItemIds": [row.pk for row in selected],
                "expectedVersions": {str(row.pk): row.version for row in selected},
                "filterSummary": {"groupNo": "DES-04"},
                "sortSummary": "产品设计编号 降序",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))
        transported = load_workbook(BytesIO(response.content), data_only=True)
        self.assertEqual(transported["产品设计当前结果"].max_row, 3)

    def test_design_number_error_identifies_field_value_reason_and_action(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-design-number-error")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-design-number-error", expected_count=4,
        )
        item = ProductDesignItem.objects.order_by("pk").first()
        with self.assertRaises(ProductDesignError) as captured:
            save_design_content(
                user=self.user,
                payload={
                    "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
                    "designNature": "FORMAL", "designData": {"designLength": "0"},
                    "reason": "验证错误契约",
                },
                idempotency_key="design-number-error",
            )
        self.assertEqual(captured.exception.details["field"], "designLength")
        self.assertEqual(captured.exception.details["currentValue"], "0")
        self.assertEqual(captured.exception.details["reason"], "MUST_BE_GREATER_THAN_ZERO")
        self.assertTrue(captured.exception.details["suggestedAction"])

    def test_single_row_visible_dimensions_and_notes_are_persisted_on_that_item_only(self):
        prepare_order_demand(user=self.user, idempotency_key="prepare-single-row-visible-dimensions")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-single-row-visible-dimensions", expected_count=4,
        )
        selected = ProductDesignItem.objects.order_by("pk").first()
        untouched = ProductDesignItem.objects.order_by("pk")[1]
        untouched_version = untouched.version
        facts, replayed = save_design_content(
            user=self.user,
            payload={
                "designItemIds": [selected.pk],
                "expectedVersions": {str(selected.pk): selected.version},
                "designNature": "FORMAL",
                "designData": {
                    "designLength": "2045", "designWidth": "939",
                    "designThickness": "265", "designNotes": "单行说明保存回读",
                },
                "reason": "验证页面可见尺寸与请求体一致",
            },
            idempotency_key="single-row-visible-dimensions",
        )
        self.assertFalse(replayed)
        row = next(value for value in facts["rows"] if value["id"] == selected.pk)
        self.assertEqual(row["designRevision"]["designLength"], "2045.000000")
        self.assertEqual(row["designRevision"]["designWidth"], "939.000000")
        self.assertEqual(row["designRevision"]["designThickness"], "265.000000")
        self.assertEqual(row["designRevision"]["designNotes"], "单行说明保存回读")
        untouched.refresh_from_db()
        self.assertEqual(untouched.version, untouched_version)
