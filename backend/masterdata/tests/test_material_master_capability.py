from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import (
    CodeRule, ExternalIdentity, MasterDataWriteRequest, Material,
    MaterialCategory, UnitOfMeasure,
)
from masterdata.serializers import MaterialSerializer
from masterdata.uom_governance import convert_uom_quantity
from pde.production_foundation_service import (
    ProductionFoundationError, ProductionFoundationService,
)
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)


class MaterialMasterCapabilityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="MM1", name="Material能力测试公司")
        self.department = Department.objects.create(
            code="MM-D", name="企业主数据部", company=self.company,
            department_type=Department.DepartmentType.FUNCTIONAL,
        )
        self.user = User.objects.create_user(
            username="material_maintainer", password="test-only",
            real_name="物料维护员", company_id=self.company.pk,
        )
        self.role, _ = Role.objects.get_or_create(
            code="enterprise_master_data_maintainer",
            defaults={"name": "企业主数据维护员"},
        )
        for code in (
            "production.master_data.material.maintain",
            "production.master_data.unit.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "PRODUCTION"},
            )
            RolePermission.objects.get_or_create(role=self.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=self.role, organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            business_hash="material-master-capability-test",
        )
        responsibility, _ = Responsibility.objects.get_or_create(
            code="ENTERPRISE_MASTER_DATA_MAINTAINER",
            defaults={
                "name": "企业主数据维护职责",
                "status": Responsibility.Status.ACTIVE,
                "is_active": True,
            },
        )
        position = Position.objects.create(
            code="MM-POS", name="企业主数据维护岗", company=self.company,
            department=self.department, default_role=self.role,
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility,
            is_primary=True, active=True,
        )
        Employee.objects.create(
            user=self.user, employee_no="MM-E001", full_name="物料维护员",
            department_ref=self.department, position_ref=position, status="active",
        )
        CodeRule.objects.update_or_create(
            company_id=self.company.pk, entity_type="production_material",
            defaults={
                "prefix": "MAT", "date_format": "", "seq_length": 6,
                "current_seq": 0,
            },
        )
        self.category = MaterialCategory.objects.create(
            code="SOLID", name="通用实材", company_id=self.company.pk,
            is_active=True,
        )
        self.meter = UnitOfMeasure.objects.update_or_create(
            code="m", company_id=self.company.pk,
            defaults={
                "name": "米", "symbol": "m", "dimension": "length",
                "conversion_base": None, "conversion_factor": Decimal("1"),
                "decimal_places": 4, "is_active": True,
            },
        )[0]
        self.millimeter = UnitOfMeasure.objects.update_or_create(
            code="mm", company_id=self.company.pk,
            defaults={
                "name": "毫米", "symbol": "mm", "dimension": "length",
                "conversion_base": self.meter,
                "conversion_factor": Decimal("0.001"),
                "decimal_places": 0, "is_active": True,
            },
        )[0]

    def source(self, external_id):
        return {
            "sourceSystem": "MATERIAL_CAPABILITY_TEST",
            "sourceType": "MANUAL",
            "sourceObjectType": "MATERIAL",
            "externalId": external_id,
            "auditMetadata": {"test": True},
        }

    def payload(self, **overrides):
        payload = {
            "company_id": self.company.pk,
            "name": "通用结构材料",
            "category_id": self.category.pk,
            "purpose": "结构 / 骨架材料",
            "specification": "30×40 mm",
            "application_notes": "通用外部结构",
            "unit": "",
            "unit_status": "confirmed",
            "base_uom_id": self.meter.pk,
            "purchase_uom_id": self.meter.pk,
            "material_type": "raw",
            "is_purchased": True,
            "is_produced": False,
            "is_active": True,
            "reason": "Material能力隔离测试",
        }
        payload.update(overrides)
        return payload

    def create_material(self, suffix="1", **overrides):
        return ProductionFoundationService.write(
            "materials", user=self.user, payload=self.payload(**overrides),
            idempotency_key=f"MM-CREATE-{suffix}",
            source_identity=self.source(f"ROW-{suffix}"),
        )

    def test_01_purpose_application_notes_and_category_name_readback(self):
        result = self.create_material()
        row = Material.objects.get(pk=result["row"]["id"])
        self.assertEqual(row.purpose, "结构 / 骨架材料")
        self.assertEqual(row.application_notes, "通用外部结构")
        self.assertEqual(result["row"]["category_name"], self.category.name)
        self.assertEqual(result["row"]["base_uom_name"], "米")

    def test_02_specification_remains_arbitrary_text(self):
        result = self.create_material(specification="φ12 / 定制截面 A-7")
        self.assertEqual(result["row"]["specification"], "φ12 / 定制截面 A-7")

    def test_03_category_must_exist_be_active_and_share_company(self):
        inactive = MaterialCategory.objects.create(
            code="INACTIVE", name="停用类别", company_id=self.company.pk,
            is_active=False,
        )
        with self.assertRaises(ProductionFoundationError) as inactive_error:
            self.create_material("inactive-category", category_id=inactive.pk)
        self.assertEqual(inactive_error.exception.code, "INACTIVE_REFERENCE")

        other_company = Company.objects.create(code="MM2", name="其他公司")
        other = MaterialCategory.objects.create(
            code="OTHER", name="其他类别", company_id=other_company.pk,
        )
        with self.assertRaises(ProductionFoundationError) as company_error:
            self.create_material("cross-category", category_id=other.pk)
        self.assertEqual(company_error.exception.code, "VALIDATION_FAILED")

        with self.assertRaises(ProductionFoundationError) as missing_error:
            self.create_material("missing-category", category_id=999999)
        self.assertEqual(missing_error.exception.code, "REFERENCE_NOT_FOUND")

    def test_04_meter_is_a_legal_formal_base_uom(self):
        result = self.create_material()
        self.assertEqual(result["row"]["base_uom_id"], self.meter.pk)

    def test_05_uom_converts_1000_mm_to_1_m_and_back(self):
        self.assertEqual(
            convert_uom_quantity(
                Decimal("1000"), source_uom=self.millimeter,
                target_uom=self.meter,
            ),
            Decimal("1.000"),
        )
        self.assertEqual(
            convert_uom_quantity(
                Decimal("1"), source_uom=self.meter,
                target_uom=self.millimeter,
            ),
            Decimal("1E+3"),
        )

    def test_06_code_rule_generates_code_and_manual_code_is_preserved(self):
        generated = self.create_material("generated")
        manual = self.create_material(
            "manual", code="CUSTOM-MAT-001", specification="30×50 mm",
        )
        self.assertEqual(generated["row"]["code"], "MAT000001")
        self.assertEqual(manual["row"]["code"], "CUSTOM-MAT-001")

    def test_07_same_name_different_specifications_are_allowed(self):
        first = self.create_material("spec-a", specification="30×40 mm")
        second = self.create_material("spec-b", specification="30×50 mm")
        self.assertNotEqual(first["row"]["id"], second["row"]["id"])
        self.assertNotEqual(first["row"]["code"], second["row"]["code"])

    def test_08_exact_active_duplicate_is_blocked_after_basic_normalization(self):
        first = self.create_material("dup-a")
        with self.assertRaises(ProductionFoundationError) as caught:
            self.create_material(
                "dup-b", code="ANOTHER-CODE", name="  通用结构材料  ",
                purpose="结构   / 骨架材料", specification="３０×４０ mm",
                application_notes="不同说明不参与Canonical身份",
            )
        self.assertEqual(caught.exception.code, "DUPLICATE_ACTIVE_MATERIAL")
        self.assertEqual(
            caught.exception.details["canonicalMaterial"]["id"],
            first["row"]["id"],
        )
        self.assertEqual(Material.objects.count(), 1)

    def test_09_inactive_duplicate_returns_candidate_and_needs_explicit_decision(self):
        existing = Material.objects.create(
            code="OLD-MAT", name="通用结构材料", category=self.category,
            purpose="结构 / 骨架材料", specification="30×40 mm",
            application_notes="历史", unit_status="confirmed", base_uom=self.meter,
            purchase_uom=self.meter, material_type="raw", is_purchased=True,
            company_id=self.company.pk, is_active=False,
        )
        with self.assertRaises(ProductionFoundationError) as caught:
            self.create_material("inactive-candidate")
        self.assertEqual(
            caught.exception.code,
            "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
        )
        self.assertEqual(
            caught.exception.details["inactiveCandidates"][0]["id"], existing.pk,
        )

    def test_10_create_new_with_justification_and_reactivate_are_explicit(self):
        existing = Material.objects.create(
            code="OLD-MAT", name="通用结构材料", category=self.category,
            purpose="结构 / 骨架材料", specification="30×40 mm",
            unit_status="confirmed", base_uom=self.meter, material_type="raw",
            is_purchased=True, company_id=self.company.pk, is_active=False,
        )
        created = self.create_material(
            "justified", materialAction="CREATE_NEW_WITH_JUSTIFICATION",
            justification="历史记录编码已永久封存，受控建立新身份。",
        )
        self.assertNotEqual(created["row"]["id"], existing.pk)

        created_id = created["row"]["id"]
        ProductionFoundationService.write(
            "materials", user=self.user,
            payload={"is_active": False, "reason": "隔离停用测试"},
            idempotency_key="MM-DEACTIVATE",
            source_identity=None, object_id=created_id,
        )
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "materials", user=self.user,
                payload={"is_active": True, "reason": "缺少显式动作"},
                idempotency_key="MM-REACTIVATE-MISSING",
                source_identity=None, object_id=created_id,
            )
        self.assertEqual(caught.exception.code, "REACTIVATE_ACTION_REQUIRED")
        reactivated = ProductionFoundationService.write(
            "materials", user=self.user,
            payload={
                "is_active": True,
                "materialAction": "REACTIVATE",
                "reason": "显式重新启用隔离测试",
            },
            idempotency_key="MM-REACTIVATE",
            source_identity=None, object_id=created_id,
        )
        self.assertTrue(reactivated["row"]["is_active"])
        reactivate_audit = OrganizationOperatingAuditRecord.objects.get(
            pk=reactivated["auditId"],
        )
        self.assertEqual(
            reactivate_audit.after_snapshot["importContext"]
            ["materialCanonicalGate"]["decision"],
            "REACTIVATE",
        )

    def test_11_different_purpose_and_category_are_distinct(self):
        other_category = MaterialCategory.objects.create(
            code="OTHER-SOLID", name="其他实材", company_id=self.company.pk,
        )
        first = self.create_material("purpose-a")
        purpose = self.create_material("purpose-b", purpose="装饰线条")
        category = self.create_material(
            "category-b", category_id=other_category.pk,
        )
        self.assertEqual({first["row"]["id"], purpose["row"]["id"], category["row"]["id"]}, set(Material.objects.values_list("id", flat=True)))

    def test_12_pending_supply_is_allowed_but_conflicting_flags_fail(self):
        pending = self.create_material(
            "pending", is_purchased=False, is_produced=False,
        )
        self.assertEqual(pending["row"]["supply_type"], "pending_confirmation")
        serializer_payload = self.payload(
            code="SERIAL-PENDING", is_purchased=False, is_produced=False,
        )
        serializer_payload["category"] = serializer_payload.pop("category_id")
        serializer_payload["base_uom"] = serializer_payload.pop("base_uom_id")
        serializer_payload["purchase_uom"] = serializer_payload.pop("purchase_uom_id")
        serializer = MaterialSerializer(data=serializer_payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ProductionFoundationError) as caught:
            self.create_material(
                "conflicting", specification="40×50 mm",
                is_purchased=True, is_produced=True,
            )
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_13_unauthorized_or_non_employee_account_fails_closed(self):
        denied = User.objects.create_user(
            username="material_denied", password="test-only",
            company_id=self.company.pk,
        )
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "materials", user=denied, payload=self.payload(),
                idempotency_key="MM-DENIED", source_identity=self.source("DENIED"),
            )
        self.assertIn(caught.exception.code, {"PERMISSION_DENIED", "FORMAL_EXECUTION_CHAIN_REQUIRED"})
        self.assertEqual(Material.objects.count(), 0)

    def test_14_audit_idempotency_and_update_ledger_are_complete(self):
        first = self.create_material("idem")
        replay = self.create_material("idem")
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(first["row"]["id"], replay["row"]["id"])
        updated = ProductionFoundationService.write(
            "materials", user=self.user,
            payload={"application_notes": "更新说明", "reason": "更新隔离测试"},
            idempotency_key="MM-UPDATE-IDEM", source_identity=None,
            object_id=first["row"]["id"],
        )
        update_replay = ProductionFoundationService.write(
            "materials", user=self.user,
            payload={"application_notes": "更新说明", "reason": "更新隔离测试"},
            idempotency_key="MM-UPDATE-IDEM", source_identity=None,
            object_id=first["row"]["id"],
        )
        self.assertFalse(updated["idempotentReplay"])
        self.assertTrue(update_replay["idempotentReplay"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 2)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 2)
        self.assertTrue(all(row.status == "COMMITTED" for row in MasterDataWriteRequest.objects.all()))

    def test_15_category_and_uom_use_formal_write_chain(self):
        category = ProductionFoundationService.write(
            "material-categories", user=self.user,
            payload={
                "code": "FORMAL-CATEGORY", "name": "正式类别",
                "company_id": self.company.pk, "is_active": True,
                "reason": "类别能力隔离测试",
            },
            idempotency_key="MM-CATEGORY-CREATE",
            source_identity={
                **self.source("CATEGORY-1"),
                "sourceObjectType": "MATERIAL_CATEGORY",
            },
        )
        self.assertEqual(category["row"]["name"], "正式类别")
        update = ProductionFoundationService.write(
            "units", user=self.user,
            payload={
                "conversion_base_id": self.meter.pk,
                "conversion_factor": "0.001",
                "reason": "UOM换算能力隔离测试",
            },
            idempotency_key="MM-UOM-UPDATE", source_identity=None,
            object_id=self.millimeter.pk,
        )
        replay = ProductionFoundationService.write(
            "units", user=self.user,
            payload={
                "conversion_base_id": self.meter.pk,
                "conversion_factor": "0.001",
                "reason": "UOM换算能力隔离测试",
            },
            idempotency_key="MM-UOM-UPDATE", source_identity=None,
            object_id=self.millimeter.pk,
        )
        self.assertEqual(update["row"]["conversion_base_name"], "米")
        self.assertTrue(replay["idempotentReplay"])

    def test_16_legacy_api_uses_same_canonical_gate_and_import_is_closed(self):
        client = APIClient()
        client.force_authenticate(self.user)
        api_payload = self.payload()
        api_payload.update({
            "category": api_payload.pop("category_id"),
            "base_uom": api_payload.pop("base_uom_id"),
            "purchase_uom": api_payload.pop("purchase_uom_id"),
            "idempotencyKey": "MM-LEGACY-1",
        })
        first = client.post("/api/masterdata/materials/", api_payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        api_payload["idempotencyKey"] = "MM-LEGACY-2"
        duplicate = client.post("/api/masterdata/materials/", api_payload, format="json")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data["code"], "DUPLICATE_ACTIVE_MATERIAL")
        blocked_import = client.post(
            "/api/masterdata/materials/import_excel/", {}, format="multipart",
        )
        self.assertEqual(blocked_import.status_code, 409)
        self.assertEqual(blocked_import.data["code"], "LEGACY_MATERIAL_IMPORT_WRITE_CLOSED")

    def test_17_existing_material_fields_remain_empty_without_backfill(self):
        historical = Material.objects.create(
            code="HISTORICAL", name="历史物料", specification="历史规格",
            unit="件", company_id=self.company.pk,
        )
        historical.refresh_from_db()
        self.assertEqual(historical.purpose, "")
        self.assertEqual(historical.application_notes, "")

    def test_18_formal_ui_contract_exposes_business_fields_without_internal_ids(self):
        root = Path(settings.BASE_DIR).parent
        component = (root / "frontend/src/meta/components/ProductionFoundationMaintenance.vue").read_text(encoding="utf-8")
        registry = (root / "frontend/src/meta/master-data/foundationEntryUnificationRegistry.js").read_text(encoding="utf-8")
        for label in (
            "物料编码", "物料名称", "物料类别", "用途", "规格",
            "正式基本单位", "采购单位", "采购件", "自制件", "适用部位/说明",
        ):
            self.assertIn(label, component)
        self.assertIn("可留空；保存时由服务端正式编码规则自动生成", component)
        self.assertIn("material-categories", registry)
        self.assertIn("/foundation/master-data/materials", registry)
        self.assertNotIn("canonical_identity_hash", component)

    def test_19_no_industry_specific_identity_logic(self):
        service = Path(__file__).resolve().parents[2] / "masterdata/material_identity.py"
        text = service.read_text(encoding="utf-8").casefold()
        for forbidden in ("pine", "30×40", "30×50", "门套木方"):
            self.assertNotIn(forbidden.casefold(), text)
