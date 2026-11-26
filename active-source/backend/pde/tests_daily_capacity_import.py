"""Isolated tests for true-source parsing and governed daily capacity imports."""

from datetime import date
from pathlib import Path
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from django.test import SimpleTestCase, TestCase

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Process, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment, Workshop,
)
from .daily_capacity_import_service import DailyCapacityImportError, DailyCapacityImportService
from .models import CapacityProductType, ManufacturingProcessType, ProductCategory, Routing, StandardCapacity, WorkCenter, WorkCenterOperationCapability
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


def temporary_source_directory():
    workspace = Path(__file__).resolve().parents[2]
    target = (workspace / "work" / "pde-order-calc-bom-isolated-daily-capacity" / "fixtures").resolve()
    if not target.is_relative_to(workspace):
        raise RuntimeError("隔离来源夹具必须保留在明确工作区中")
    target.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=target)


def source_fixture(directory, *, formula=False, duplicate=False):
    """Tiny synthetic business matrix only for isolated test assertions."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = ET.Element("worksheet", xmlns=ns)
    data = ET.SubElement(sheet, "sheetData")
    rows = [["序号", "半成品编码", "半成品名称", "开料产能", "加工后封边产能"],
            [1, "MQ/FM", "免漆房门", 99, 0],
            [1, "MQ/FM" if duplicate else "BTKF/FM", "半透开放房门", 100, None]]
    for number, values in enumerate(rows, 1):
        row = ET.SubElement(data, "row", r=str(number))
        for col, value in zip("ABCDE", values):
            if value is None:
                continue
            cell = ET.SubElement(row, "c", r=f"{col}{number}")
            if isinstance(value, str):
                cell.set("t", "inlineStr")
                ET.SubElement(ET.SubElement(cell, "is"), "t").text = value
            else:
                if formula and col == "D" and number == 2:
                    ET.SubElement(cell, "f").text = "98+1"
                ET.SubElement(cell, "v").text = str(value)
    path = Path(directory) / "source.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="标准产能" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet))
    return path


class DailyCapacityParserTests(SimpleTestCase):
    def test_wide_source_preserves_zero_and_distinguishes_blank(self):
        with temporary_source_directory() as directory:
            path = source_fixture(directory)
            before = path.read_bytes()
            result = DailyCapacityImportService.parse(path)
            self.assertEqual(result["counts"], {"products": 2, "processColumns": 2, "positive": 2, "zero": 1, "nonblank": 3, "blank": 1})
            self.assertEqual(result["capacities"][0]["sourceValue"], "99")
            self.assertEqual(result["capacities"][1]["sourceStatus"], "ZERO_CAPACITY")
            self.assertEqual(result["missingCells"][0]["sourceCell"], "E3")
            self.assertEqual(path.read_bytes(), before)

    def test_formula_and_duplicate_source_are_rejected(self):
        with temporary_source_directory() as directory:
            for kwargs, expected in (({"formula": True}, "SOURCE_FORMULA_UNSUPPORTED"),
                                     ({"duplicate": True}, "SOURCE_PRODUCT_DUPLICATE")):
                with self.assertRaises(DailyCapacityImportError) as caught:
                    DailyCapacityImportService.parse(source_fixture(directory, **kwargs))
                self.assertEqual(caught.exception.code, expected)


class DailyCapacityImportTests(TestCase):
    def setUp(self):
        self.directory = temporary_source_directory()
        self.addCleanup(self.directory.cleanup)
        self.path = source_fixture(self.directory.name)
        self.source_sha = DailyCapacityImportService.parse(self.path)["sourceSha256"]
        self.company = Company.objects.create(code="DAILY-TEST", name="日产能隔离测试公司")
        self.department = Department.objects.create(company=self.company, code="DAILY-ENG", name="工程部")
        self.workshop = Workshop.objects.create(company=self.company, department=self.department, code="DAILY-WS", name="木工")
        self.user = User.objects.create_user(username="daily_capacity_operator", company_id=self.company.pk)
        role = Role.objects.create(code="DAILY-ROLE", name="日产能维护角色")
        for code in ("production.master_data.resource.maintain", "production.master_data.capacity.maintain"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", active=True, business_hash="daily-test-authority")
        responsibility = Responsibility.objects.create(code="DAILY-RESP", name="制造产能资料维护", status="ACTIVE", is_active=True)
        position = Position.objects.create(company=self.company, department=self.department, code="DAILY-POS", name="产能维护岗位", default_role=role)
        PositionResponsibility.objects.create(position=position, responsibility=responsibility, is_primary=True, active=True)
        Employee.objects.create(user=self.user, employee_no="DAILY-E001", full_name="隔离测试操作人",
                                department_ref=self.department, position_ref=position, status="active")
        self.uom = UnitOfMeasure.objects.create(company_id=self.company.pk, code="DAILY-PCS", name="件")
        self.category = ProductCategory.objects.create(company=self.company, code="FM", name="房门")
        for code, name in (("MQ", "免漆"), ("BTKF", "半透开放")):
            kind = ManufacturingProcessType.objects.create(company=self.company, code=code, name=name)
            Routing.objects.create(company=self.company, routing_code=f"{code}/FM", name=f"{name}房门",
                applicability_scope="PRODUCT_CATEGORY", product_category=self.category, manufacturing_process_type=kind)
        self.cut = Process.objects.create(company=self.company, workshop=self.workshop, code="DAILY-CUT", name="开料")
        self.edge = Process.objects.create(company=self.company, workshop=self.workshop, code="DAILY-EDGE", name="加工后封边")
        self.veneer = Process.objects.create(company=self.company, workshop=self.workshop, code="DAILY-VENEER", name="拼皮")
        self.old_wc = WorkCenter.objects.create(company=self.company, workshop=self.workshop, department=self.department,
            code="WC202610000001", name="开料工作中心")
        self.old_veneer_wc = WorkCenter.objects.create(company=self.company, workshop=self.workshop, department=self.department,
            code="WC202610000002", name="拼皮工作中心")
        WorkCenterOperationCapability.objects.create(work_center=self.old_wc, operation=self.cut, assignment_role="primary")
        WorkCenterOperationCapability.objects.create(work_center=self.old_veneer_wc, operation=self.veneer, assignment_role="primary")
        self.rule = CodeRule.objects.create(company_id=self.company.pk, entity_type="production_work_center",
            prefix="WC", date_format="%Y%m", seq_length=6, current_seq=2)
        CodeRule.objects.create(company_id=self.company.pk, entity_type="production_standard_capacity", prefix="CAP", seq_length=6)

    def apply(self, **kwargs):
        return DailyCapacityImportService.apply(self.path, user=kwargs.pop("user", self.user), company_id=self.company.pk,
            expected_source_sha256=kwargs.pop("expected_source_sha256", self.source_sha), reason="隔离测试来源导入", **kwargs)

    def test_preview_reads_exact_relations_without_writing(self):
        before = OrganizationOperatingAuditRecord.objects.count()
        result = DailyCapacityImportService.preview(self.path, company_id=self.company.pk)
        self.assertTrue(result["centresReady"])
        self.assertFalse(result["capacityImportReady"])
        self.assertEqual(len(result["productTypePlans"]), 2)
        self.assertEqual(result["remainingMissing"], {"preparationDays": 3, "transferDays": 3})
        self.assertEqual(result["processesOutsideSource"][0]["name"], "拼皮")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.current_seq, 2)

    def test_exact_routing_fk_maps_automatically_numbered_category_and_process_type(self):
        self.category.code = "CAT202609000001"
        self.category.save(update_fields=("code",))
        for number, kind in enumerate(ManufacturingProcessType.objects.filter(company=self.company).order_by("pk"), 1):
            kind.code = f"MPT202609{number:06d}"
            kind.save(update_fields=("code",))
        routes_before = list(Routing.objects.values())
        preview = DailyCapacityImportService.preview(self.path, company_id=self.company.pk,
            field_facts={"capacityUomId": self.uom.pk, "effectiveDate": "2026-10-13"})
        self.assertEqual(preview["productTypeBlockers"], [])
        self.assertTrue(preview["capacityImportReady"])
        self.assertEqual({p["productCategoryId"] for p in preview["productTypePlans"]}, {self.category.pk})
        self.apply(mode="all", field_facts={"capacityUomId": self.uom.pk, "effectiveDate": "2026-10-13"})
        self.assertEqual(CapacityProductType.objects.count(), 2)
        self.assertEqual(StandardCapacity.objects.count(), 3)
        self.assertEqual(list(Routing.objects.values()), routes_before)

    def test_inactive_routing_fk_master_data_blocks_product_type_mapping(self):
        self.category.is_active = False
        self.category.save(update_fields=("is_active",))
        preview = DailyCapacityImportService.preview(self.path, company_id=self.company.pk)
        self.assertEqual(len(preview["productTypeBlockers"]), 2)
        self.category.is_active = True
        self.category.save(update_fields=("is_active",))
        kind = ManufacturingProcessType.objects.filter(company=self.company, code="MQ").get()
        kind.is_active = False
        kind.save(update_fields=("is_active",))
        preview = DailyCapacityImportService.preview(self.path, company_id=self.company.pk)
        self.assertEqual(preview["productTypeBlockers"], [{"code": "ROUTING_PRODUCT_TYPE_RELATION_INVALID", "productTypeCode": "MQ/FM"}])

    def test_centres_only_preserves_existing_identities_and_replays_without_writes(self):
        routes = list(Routing.objects.values())
        processes = list(Process.objects.filter(company=self.company).values())
        first = self.apply()
        self.assertEqual(first["createdWorkCenters"][0]["code"], "WC001")
        self.assertEqual(WorkCenter.objects.count(), 3)
        self.assertEqual(WorkCenterOperationCapability.objects.count(), 3)
        self.assertEqual(StandardCapacity.objects.count(), 0)
        self.assertEqual(CapacityProductType.objects.count(), 0)
        self.old_wc.refresh_from_db()
        self.assertEqual(self.old_wc.code, "WC202610000001")
        self.assertEqual(list(Routing.objects.values()), routes)
        self.assertEqual(list(Process.objects.filter(company=self.company).values()), processes)
        counts = (OrganizationOperatingAuditRecord.objects.count(), MasterDataWriteRequest.objects.count())
        second = self.apply()
        self.assertEqual(second["businessWriteCount"], 0)
        self.assertEqual((OrganizationOperatingAuditRecord.objects.count(), MasterDataWriteRequest.objects.count()), counts)

    def test_missing_units_or_date_block_all_before_any_write(self):
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(mode="all")
        self.assertEqual(caught.exception.code, "IMPORT_BLOCKED")
        self.assertEqual(WorkCenter.objects.count(), 2)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.date_format, "%Y%m")

    def test_confirmed_quantity_unit_date_preserve_zero_and_unknown_day_times(self):
        fields = {"capacityUomId": self.uom.pk, "effectiveDate": "2026-10-13", "businessFactReference": "TEST-ONLY"}
        result = self.apply(mode="all", field_facts=fields)
        self.assertEqual(len(result["createdCapacities"]), 3)
        self.assertEqual(CapacityProductType.objects.count(), 2)
        self.assertFalse(result["planningReady"])
        zero = StandardCapacity.objects.get(measurement_status="zero_capacity")
        self.assertEqual(zero.quantity, 0)
        self.assertEqual(zero.time_unit, "DAY")
        self.assertEqual(zero.effective_from, date(2026, 10, 13))
        self.assertIsNone(zero.preparation_days)
        self.assertIsNone(zero.transfer_days)
        self.assertIsNone(zero.standard_hours)
        second = self.apply(mode="all", field_facts=fields)
        self.assertEqual(second["businessWriteCount"], 0)
        self.assertEqual(len(second["reusedCapacities"]), 3)
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(mode="all", field_facts={**fields, "preparationDays": "1"})
        self.assertEqual(caught.exception.code, "CAPACITY_EXISTING_CONFLICT")
        self.assertEqual(StandardCapacity.objects.count(), 3)

    def test_permission_and_source_hash_fail_without_writes(self):
        outsider = User.objects.create_user(username="daily_unprivileged", company_id=self.company.pk)
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(user=outsider)
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(expected_source_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "SOURCE_CHANGED")
        self.assertEqual(WorkCenter.objects.count(), 2)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_late_write_failure_rolls_back_code_rule_centres_and_audits(self):
        original = ProductionFoundationService.write
        calls = []
        def fail_capability(entity, **kwargs):
            calls.append(entity)
            if entity == "work-center-operation-capabilities":
                raise ProductionFoundationError("INJECTED_TEST_FAILURE", "隔离测试事务回退")
            return original(entity, **kwargs)
        with patch.object(ProductionFoundationService, "write", side_effect=fail_capability):
            with self.assertRaises(ProductionFoundationError):
                self.apply()
        self.assertEqual(calls, ["work-centers", "work-center-operation-capabilities"])
        self.assertEqual(WorkCenter.objects.count(), 2)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
        self.rule.refresh_from_db()
        self.assertEqual((self.rule.date_format, self.rule.seq_length, self.rule.current_seq), ("%Y%m", 6, 2))

    def test_duplicate_normalized_name_blocks_merge_without_changes(self):
        for number, name in enumerate(("加工后封边工作中心", " 加工后封边工作中心 "), 1):
            WorkCenter.objects.create(company=self.company, workshop=self.workshop, code=f"TEST-DUP-{number}", name=name)
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "IMPORT_BLOCKED")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_field_fact_conflict_does_not_block_centres_only(self):
        self.apply(field_facts={"capacityUomId": self.uom.pk, "capacityUomIdByCell": {"D2": self.uom.pk + 1000}})
        self.assertEqual(WorkCenter.objects.count(), 3)
        self.assertEqual(StandardCapacity.objects.count(), 0)

    def test_source_identity_must_not_replay_a_different_work_centre(self):
        ExternalIdentity.objects.create(organization_id=self.company.pk, source_system="PCE_APS_CAPACITY_XLSX",
            source_type="BUSINESS_SOURCE", source_object_type="work-centers",
            external_id=f"workshop:{self.workshop.pk}:process:{self.edge.pk}", target_entity_type="work-centers",
            target_entity_id=str(self.old_veneer_wc.pk), mapping_status="MATCH", source_fingerprint=self.source_sha)
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "SOURCE_TARGET_PAYLOAD_CONFLICT")
        self.assertEqual(WorkCenter.objects.count(), 2)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
