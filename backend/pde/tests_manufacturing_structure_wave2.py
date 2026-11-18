from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import (
    ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure,
)
from system.models import Company, Department, Process, User, Workshop

from .manufacturing_structure_service import (
    ManufacturingStructureError,
    ManufacturingStructureService,
)
from .models import (
    BOMCompletenessRule,
    BOMItem,
    BOMItemRoutingAssignment,
    BOMItemSubstitute,
    BOMVersion,
    ConfiguredProduct,
    ProductBOM,
    ProductCategory,
    ProductConfiguration,
    ProductDefinition,
    ProductTemplate,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
    WorkCenter,
)


class ManufacturingStructureWave2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="W2", name="Wave2隔离测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="W2-MFG", name="制造部",
            department_type="PRODUCTION",
        )
        cls.workshop = Workshop.objects.create(
            company=cls.company, department=cls.department,
            code="W2-WS", name="隔离测试车间",
        )
        cls.work_center = WorkCenter.objects.create(
            company=cls.company, department=cls.department, workshop=cls.workshop,
            code="W2-WC", name="隔离测试工作中心",
            resource_capabilities={"processes": ["cut", "edge", "assemble"]},
            capacity_policy={"calendarBoundary": True, "shiftBoundary": True},
        )
        cls.operation = Process.objects.create(
            company=cls.company, workshop=cls.workshop,
            code="W2-OP", name="通用加工作业", standard_hours=None,
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS-W2", name="件",
        )
        cls.user = User.objects.create_superuser(
            username="wave2-reviewer", password="test-only", real_name="Wave2验收员",
            company_id=cls.company.pk,
        )

    @classmethod
    def material(cls, code, name, *, material_type="raw", supply="BUY", cost="1"):
        return Material.objects.create(
            company_id=cls.company.pk, code=code, name=name, unit="件",
            base_uom=cls.uom, material_type=material_type,
            is_produced=supply == "MAKE", is_purchased=supply == "BUY",
            standard_cost=Decimal(cost),
        )

    def build_case(self, code, name, *, family, with_glass=True, subcontract=False):
        category = ProductCategory.objects.create(
            company=self.company, code=f"{code}-CAT", name=family,
            industry_type="wholeHouseWood",
        )
        template = ProductTemplate.objects.create(
            company=self.company, category=category, template_code=f"{code}-TPL",
            name=f"{name}模板", product_mode="configurable",
            parameter_schema={
                "width": {"type": "decimal", "uom": "mm", "required": True},
                "height": {"type": "decimal", "uom": "mm", "required": True},
                "door_count": {"type": "integer", "minimum": 1},
            },
            attribute_schema={"finish": {}, "grainDirection": {"optional": True}},
            status="released",
        )
        configuration = ProductConfiguration.objects.create(
            template=template, configuration_no=f"{code}-CFG-001",
            parameters={"width": 2387, "height": 2783, "door_count": 2},
            design_specification={"width": 2387, "height": 2783},
            delivery_context={
                "customerOrder": "SO-W2-001", "project": "P-W2",
                "space": "主卧", "installationLocation": "A-01",
            },
            input_hash=f"{code.lower()}-input", idempotency_key=f"{code.lower()}-idem",
            status="resolved",
        )
        finished = self.material(f"{code}-FG", name, material_type="finished", supply="MAKE", cost="10")
        assembly = self.material(f"{code}-ASM", f"{name}自制总成", material_type="semi", supply="MAKE", cost="5")
        board = self.material(f"{code}-BOARD", "板材/实木", supply="BUY", cost="20")
        hardware = self.material(f"{code}-HW", "铰链/门锁/合页", supply="BUY", cost="3")
        packaging = self.material(f"{code}-PKG", "包装材料", material_type="auxiliary", supply="BUY", cost="1")
        installation = self.material(f"{code}-INSTALL", "安装辅料", material_type="auxiliary", supply="BUY", cost="1")
        glass = self.material(f"{code}-GLASS", "按单尺寸玻璃", supply="BUY", cost="8") if with_glass else None
        outsourced = self.material(f"{code}-SUB", "委外饰面件", material_type="semi", supply="pending", cost="6") if subcontract else None

        product = ProductDefinition.objects.create(
            company=self.company, category=category, material=finished,
            product_code=f"{code}-PRODUCT", product_name=name,
            emd_material_code=finished.code,
        )
        product_version = ProductVersion.objects.create(
            product=product, version_no="V1", version_status="released",
            effective_date=date.today() - timedelta(days=1),
        )
        configured = ConfiguredProduct.objects.create(
            configuration=configuration, instance_no=f"{code}-INSTANCE-001",
            product_definition=product,
            manufacturing_specification={
                "designWidth": 2387, "manufacturingWidth": 2383,
                "calculationRule": "EDGE_CLEARANCE-V1",
            },
            resolution_hash=f"{code.lower()}-resolved", status="resolved",
        )
        bom = ProductBOM.objects.create(
            company=self.company, product=product, bom_code=f"{code}-BOM",
            name=f"{name}制造BOM", bom_type="manufacturing", status="released",
        )
        bom_version = BOMVersion.objects.create(
            product=product, product_version=product_version, bom=bom,
            bom_version="V1", revision=1, status="released",
            effective_date=date.today() - timedelta(days=1),
            applicability={"plant": "W2"}, approval_state="workflow_approved",
        )
        root = BOMItem.objects.create(
            bom_version=bom_version, line_no=10, material=assembly,
            quantity=1, uom=self.uom, item_role="assembly",
            requirement_type="manufacturing", supply_type="MAKE",
            scrap_rate_status="maintained", scrap_rate=0,
            manufacturing_attributes={"finish": "configured", "grainDirection": "optional"},
        )
        BOMItem.objects.create(
            bom_version=bom_version, parent_item=root, line_no=20, material=board,
            quantity=2, uom=self.uom, item_role="material",
            requirement_type="manufacturing", supply_type="BUY",
            scrap_rate_status="maintained", scrap_rate=Decimal("0.05"),
            manufacturing_attributes={"edge": {"visible": True, "affectsSize": True}},
        )
        BOMItem.objects.create(
            bom_version=bom_version, parent_item=root, line_no=30, material=hardware,
            quantity=1, uom=self.uom, item_role="component",
            requirement_type="manufacturing", supply_type="BUY",
            quantity_rule={"kind": "multiply_parameter", "parameter": "door_count", "factor": 2},
            scrap_rate_status="maintained", scrap_rate=0,
        )
        if glass:
            BOMItem.objects.create(
                bom_version=bom_version, parent_item=root, line_no=40, material=glass,
                quantity=1, uom=self.uom, item_role="component",
                requirement_type="manufacturing", supply_type="BUY",
                order_specification={"width": "resolved", "height": "resolved", "tempered": True},
                scrap_rate_status="maintained", scrap_rate=0,
            )
        BOMItem.objects.create(
            bom_version=bom_version, line_no=80, material=packaging,
            quantity=1, uom=self.uom, item_role="material",
            requirement_type="packaging", supply_type="BUY",
            scrap_rate_status="maintained", scrap_rate=0,
        )
        BOMItem.objects.create(
            bom_version=bom_version, line_no=90, material=installation,
            quantity=1, uom=self.uom, item_role="material",
            requirement_type="installation", supply_type="BUY",
            scrap_rate_status="maintained", scrap_rate=0,
        )
        subcontract_item = None
        if outsourced:
            subcontract_item = BOMItem.objects.create(
                bom_version=bom_version, parent_item=root, line_no=50, material=outsourced,
                quantity=1, uom=self.uom, item_role="component",
                requirement_type="manufacturing", supply_type="SUBCONTRACT",
                scrap_rate_status="maintained", scrap_rate=0,
            )

        routing = Routing.objects.create(
            company=self.company, product=product,
            routing_code=f"{code}-ROUTE", name=f"{name}工艺路线", status="released",
        )
        routing_version = RoutingVersion.objects.create(
            product=product, product_version=product_version, routing=routing,
            routing_version="V1", revision=1, status="draft",
            effective_date=date.today() - timedelta(days=1),
            applicability={"plant": "W2"}, approval_state="workflow_approved",
        )
        RoutingStep.objects.create(
            routing_version=routing_version, sequence=10, operation=self.operation,
            workshop=self.workshop, work_center=self.work_center, applies_to_item=root,
            predecessor_sequences=[], operation_parameters={"dimensionSource": "configuration", "applicability": {"mode": "MANDATORY"}},
            resource_selection_rule={"capability": "cut"},
        )
        RoutingStep.objects.create(
            routing_version=routing_version, sequence=20, operation=self.operation,
            workshop=self.workshop, applies_to_item=root,
            predecessor_sequences=[10], resource_selection_rule={"capability": "assemble"},
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        routing_version.status = "released"
        routing_version.save(update_fields=("status", "updated_at"))
        BOMItemRoutingAssignment.objects.create(
            bom_item=root, routing_version=routing_version,
            priority=1, selection_rule={"plant": "W2"},
        )
        if subcontract_item:
            BOMItemRoutingAssignment.objects.create(
                bom_item=subcontract_item, routing_version=routing_version,
                priority=1, selection_rule={"plant": "W2"},
            )
        BOMCompletenessRule.objects.create(
            template=template, rule_code=f"{code}-PACKAGING", severity="block",
            predicate={}, requirement={"requirementType": "packaging"},
        )
        BOMCompletenessRule.objects.create(
            template=template, rule_code=f"{code}-PURCHASED", severity="block",
            predicate={}, requirement={"supplyType": "BUY"},
        )
        return {
            "template": template, "configuration": configuration,
            "configured": configured, "product": product,
            "bom": bom, "bom_version": bom_version,
            "routing": routing, "routing_version": routing_version,
        }

    def assert_case_consumable(self, case):
        rows = ManufacturingStructureService.explode_bom(
            case["bom_version"], parameters=case["configuration"].parameters,
        )
        self.assertGreaterEqual(max(row["level"] for row in rows), 1)
        self.assertIn("BUY", {row["supplyType"] for row in rows})
        self.assertIn("MAKE", {row["supplyType"] for row in rows})
        completeness = ManufacturingStructureService.validate_completeness(
            case["template"], case["configuration"], rows,
        )
        self.assertEqual(completeness["status"], "PASS")
        routes = ManufacturingStructureService.resolve_routings(rows, context={"plant": "W2"})
        snapshot = ManufacturingStructureService.production_order_snapshot(
            case["configured"], case["bom_version"], case["routing_version"], rows, routes,
        )
        self.assertEqual(snapshot["frozenBomVersionId"], case["bom_version"].pk)
        self.assertEqual(snapshot["frozenRoutingVersionId"], case["routing_version"].pk)
        channels = {row["demandChannel"] for row in snapshot["requirements"]}
        self.assertIn("PROCUREMENT", channels)
        self.assertIn("PRODUCTION", channels)
        rollup = ManufacturingStructureService.cost_rollup(rows)
        self.assertGreater(rollup["total"], 0)
        return rows, snapshot

    def test_01_cabinet_complete_product_fixture(self):
        case = self.build_case("CAB", "全屋定制柜类产品", family="柜类", with_glass=True)
        rows, _snapshot = self.assert_case_consumable(case)
        glass = next(row for row in rows if "玻璃" in row["materialName"])
        self.assertEqual(glass["orderSpecification"]["width"], "resolved")
        hinge = next(row for row in rows if "铰链" in row["materialName"])
        self.assertEqual(hinge["netQuantity"], Decimal("4"))

    def test_02_timber_door_fixture_uses_same_core_and_subcontract(self):
        case = self.build_case(
            "DOOR", "整木木门类产品", family="木门/门套/套线",
            with_glass=True, subcontract=True,
        )
        _rows, snapshot = self.assert_case_consumable(case)
        self.assertIn("SUBCONTRACT", {row["demandChannel"] for row in snapshot["requirements"]})
        self.assertFalse(hasattr(case["bom"], "door_bom"))

    def test_03_current_version_is_lifecycle_effectivity_and_scope_not_max(self):
        case = self.build_case("VER", "版本治理产品", family="通用")
        selected = ManufacturingStructureService.resolve_current_version(
            BOMVersion.objects.filter(bom=case["bom"]),
            on_date=date.today(), context={"plant": "W2"},
        )
        self.assertEqual(selected.pk, case["bom_version"].pk)
        BOMVersion.objects.create(
            product=case["product"], product_version=case["bom_version"].product_version,
            bom=case["bom"], bom_version="V999", status="draft",
            effective_date=date.today(), applicability={"plant": "W2"},
        )
        selected = ManufacturingStructureService.resolve_current_version(
            BOMVersion.objects.filter(bom=case["bom"]), context={"plant": "W2"},
        )
        self.assertEqual(selected.bom_version, "V1")

    def test_04_ambiguous_effective_versions_are_blocked(self):
        case = self.build_case("AMB", "冲突版本产品", family="通用")
        BOMVersion.objects.create(
            product=case["product"], product_version=case["bom_version"].product_version,
            bom=case["bom"], bom_version="V2", status="released",
            effective_date=date.today() - timedelta(days=1), applicability={"plant": "W2"},
        )
        with self.assertRaises(ManufacturingStructureError) as caught:
            ManufacturingStructureService.resolve_current_version(
                BOMVersion.objects.filter(bom=case["bom"]), context={"plant": "W2"},
            )
        self.assertEqual(caught.exception.code, "AMBIGUOUS_EFFECTIVE_VERSION")

    def test_05_released_versions_are_not_overwritten(self):
        case = self.build_case("HIST", "历史保护产品", family="通用")
        case["bom_version"].revision = 2
        with self.assertRaises(ValidationError):
            case["bom_version"].save()
        case["routing_version"].revision = 2
        with self.assertRaises(ValidationError):
            case["routing_version"].save()

    def test_06_workshop_workcenter_equipment_boundary_and_step_validation(self):
        case = self.build_case("RES", "资源边界产品", family="通用")
        step = RoutingStep(
            routing_version=case["routing_version"], sequence=20,
            operation=self.operation, workshop=self.workshop,
            predecessor_sequences=[20],
        )
        with self.assertRaises(ValidationError):
            step.full_clean()
        self.assertEqual(self.work_center.workshop_id, self.workshop.pk)
        self.assertTrue(self.work_center.resource_capabilities)

    def test_07_wave2_api_is_read_only_and_server_backed(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/pde/wave2-manufacturing-foundation/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["factSource"], "Django ORM / formal service")
        self.assertTrue(response.data["data"]["formalWriteButtonDisabled"])
        state = response.data["data"]["migrationState"]
        self.assertEqual(state["applyStatus"], "APPLIED")
        self.assertEqual(state["schemaAvailability"], "AVAILABLE")
        self.assertEqual(state["authorization"], "COMPLETE")
        self.assertEqual(state["formalWriteAuthorization"], "NOT_AUTHORIZED")
        denied = client.post("/api/pde/wave2-manufacturing-foundation/", {})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data["code"], "FORMAL_WRITE_NOT_AUTHORIZED")

    def test_07a_migration_state_truth_matrix_a_to_d(self):
        resolve = ManufacturingStructureService.resolve_migration_state
        case_a = resolve(migration_applied=False, schema_available=False)
        self.assertEqual((case_a["applyStatus"], case_a["authorization"]),
                         ("NOT_APPLIED", "NOT_AUTHORIZED"))

        case_b = resolve(
            migration_applied=False, schema_available=False, migration_authorized=True,
        )
        self.assertEqual((case_b["authorization"], case_b["applyStatus"]),
                         ("AUTHORIZED", "PENDING_APPLY"))

        case_c = resolve(migration_applied=True, schema_available=True)
        self.assertEqual((case_c["applyStatus"], case_c["schemaAvailability"]),
                         ("APPLIED", "AVAILABLE"))
        self.assertNotEqual(case_c["authorization"], "NOT_GRANTED")

        case_d = resolve(migration_applied=True, schema_available=True)
        self.assertEqual(case_d["schemaAvailability"], "AVAILABLE")
        self.assertEqual(case_d["formalWriteAuthorization"], "NOT_AUTHORIZED")
        self.assertFalse(case_d["formalWriteEnabled"])

    def test_07b_migration_state_api_requires_authentication_cases_e_and_f(self):
        anonymous = APIClient().get("/api/pde/wave2-manufacturing-foundation/")
        self.assertIn(anonymous.status_code, {401, 403})

        authorized = APIClient()
        authorized.force_authenticate(self.user)
        response = authorized.get("/api/pde/wave2-manufacturing-foundation/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["factSource"], "Django ORM / formal service")

    def test_08_completeness_block_is_template_rule_driven(self):
        case = self.build_case("CMP", "完整性规则产品", family="通用")
        BOMCompletenessRule.objects.create(
            template=case["template"], rule_code="CMP-NONEXISTENT",
            severity="block", predicate={"door_count": 2},
            requirement={"supplyType": "MAKE_OR_BUY"},
        )
        rows = ManufacturingStructureService.explode_bom(
            case["bom_version"], parameters=case["configuration"].parameters,
        )
        result = ManufacturingStructureService.validate_completeness(
            case["template"], case["configuration"], rows,
        )
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["findings"][0]["ruleCode"], "CMP-NONEXISTENT")

    def test_09_alternative_component_has_scope_approval_cost_and_quality_boundaries(self):
        case = self.build_case("ALT", "替代料治理产品", family="通用")
        item = case["bom_version"].items.filter(supply_type="BUY").first()
        substitute = self.material("ALT-SUBSTITUTE", "批准替代材料", supply="BUY", cost="2")
        relation = BOMItemSubstitute.objects.create(
            bom_item=item, substitute_material=substitute, priority=1,
            conversion_rate=Decimal("1.1"), approval_state="workflow_approved",
            applicability={"plant": "W2"}, cost_impact={"reviewRequired": True},
            quality_impact={"inspectionRequired": True},
        )
        self.assertEqual(relation.approval_state, "workflow_approved")
        self.assertTrue(relation.quality_impact["inspectionRequired"])

    def test_10_buy_component_cannot_receive_internal_route(self):
        case = self.build_case("BUY", "外购边界产品", family="通用")
        buy_item = case["bom_version"].items.filter(supply_type="BUY").first()
        invalid = BOMItemRoutingAssignment(
            bom_item=buy_item, routing_version=case["routing_version"], priority=1,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_11_external_identity_idempotency_and_transaction_rollback_are_reused(self):
        case = self.build_case("ID", "身份治理产品", family="通用")
        before_identity = ExternalIdentity.objects.count()
        before_requests = MasterDataWriteRequest.objects.count()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                identity = ExternalIdentity.objects.create(
                    organization_id=self.company.pk, source_system="W2_FIXTURE",
                    source_type="controlled_fixture", source_object_type="ProductTemplate",
                    external_id="ID-TEMPLATE", target_entity_type="pde.ProductTemplate",
                    target_entity_id=str(case["template"].pk), mapping_status="MATCH",
                    source_fingerprint="fixture-only",
                )
                MasterDataWriteRequest.objects.create(
                    organization_id=self.company.pk, action_code="wave2.fixture.replay",
                    entity_type="pde.ProductTemplate", idempotency_key="IDEMPOTENT-1",
                    request_hash="hash-1", source_identity=identity,
                )
                raise RuntimeError("forced rollback")
        self.assertEqual(ExternalIdentity.objects.count(), before_identity)
        self.assertEqual(MasterDataWriteRequest.objects.count(), before_requests)

        identity = ExternalIdentity.objects.create(
            organization_id=self.company.pk, source_system="W2_FIXTURE",
            source_type="controlled_fixture", source_object_type="ProductTemplate",
            external_id="ID-TEMPLATE", target_entity_type="pde.ProductTemplate",
            target_entity_id=str(case["template"].pk), mapping_status="MATCH",
            source_fingerprint="fixture-only",
        )
        MasterDataWriteRequest.objects.create(
            organization_id=self.company.pk, action_code="wave2.fixture.replay",
            entity_type="pde.ProductTemplate", idempotency_key="IDEMPOTENT-1",
            request_hash="hash-1", source_identity=identity,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MasterDataWriteRequest.objects.create(
                    organization_id=self.company.pk, action_code="wave2.fixture.replay",
                    entity_type="pde.ProductTemplate", idempotency_key="IDEMPOTENT-1",
                    request_hash="hash-1", source_identity=identity,
                )

    def test_12_effectivity_overlap_validator_blocks_same_scope(self):
        case = self.build_case("EFF", "有效期治理产品", family="通用")
        with self.assertRaises(ValidationError):
            ManufacturingStructureService.validate_effectivity_conflict(
                BOMVersion.objects.filter(bom=case["bom"]),
                effective_date=date.today(), expire_date=None,
                applicability={"plant": "W2"},
            )

    def test_13_same_configuration_idempotency_key_cannot_replay_as_duplicate(self):
        case = self.build_case("REPLAY", "确定性重放产品", family="通用")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductConfiguration.objects.create(
                    template=case["template"], configuration_no="REPLAY-CFG-OTHER",
                    parameters=case["configuration"].parameters,
                    input_hash=case["configuration"].input_hash,
                    idempotency_key=case["configuration"].idempotency_key,
                )
