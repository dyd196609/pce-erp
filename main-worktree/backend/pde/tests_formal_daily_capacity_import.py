"""Memory-database tests for the authorized narrow capacity import boundary."""

from decimal import Decimal
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from django.test import TestCase

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from system.models import OrganizationOperatingAuditRecord, Process, User
from . import tests_daily_capacity_import as source_fixtures
from .daily_capacity_import_service import DailyCapacityImportError, DailyCapacityImportService
from .formal_daily_capacity_import_service import FormalDailyCapacityImportService
from .models import CapacityProductType, Routing, StandardCapacity, WorkCenter, WorkCenterOperationCapability
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


def formal_source_fixture(path, *, room=False):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = ET.Element("worksheet", xmlns=ns)
    data = ET.SubElement(sheet, "sheetData")
    rows = [["序号", "半成品编码", "半成品名称", "开料产能", "贴皮产能", "加工后封边产能"],
            [1, "MQ/FM", "免漆房门", 99, 80, 0], [2, "BTKF/FM", "半透开放房门", 100, None, 0]]
    if room:
        rows[0].append("房门组装产能")
        rows[1].append(12)
        rows[2].append(12)
    for number, values in enumerate(rows, 1):
        row = ET.SubElement(data, "row", r=str(number))
        for col, value in zip("ABCDEFG", values):
            if value is None:
                continue
            cell = ET.SubElement(row, "c", r=f"{col}{number}")
            if isinstance(value, str):
                cell.set("t", "inlineStr")
                ET.SubElement(ET.SubElement(cell, "is"), "t").text = value
            else:
                ET.SubElement(cell, "v").text = str(value)
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="标准产能" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet))


class FormalDailyCapacityImportTests(TestCase):
    def setUp(self):
        source_fixtures.DailyCapacityImportTests.setUp(self)
        self.uom.code, self.uom.name, self.uom.dimension = "m2", "平方米", "area"
        self.uom.save(update_fields=("code", "name", "dimension"))
        self.veneering = Process.objects.create(company=self.company, workshop=self.workshop,
                                               code="FORMAL-TEPI", name="贴皮")
        for operation in (self.cut, self.edge, self.veneer, self.veneering):
            operation.calculation_uom = self.uom
            operation.save(update_fields=("calculation_uom",))
        for operation in (self.edge, self.veneering):
            wc = WorkCenter.objects.create(company=self.company, workshop=self.workshop,
                department=self.department, code=f"EXISTING-{operation.pk}", name=f"{operation.name}工作中心")
            WorkCenterOperationCapability.objects.create(work_center=wc, operation=operation, assignment_role="primary")
        formal_source_fixture(self.path)
        self.source_sha = DailyCapacityImportService.parse(self.path)["sourceSha256"]
        self.facts = {"capacityUomIdByProcess": {p.code: self.uom.pk for p in (self.cut, self.edge, self.veneer, self.veneering)},
            "effectiveDate": "2026-10-13", "preparationDays": "0.1", "transferDays": "0.1",
            "businessFactReference": {"userConfirmed": "TEST-ONLY", "productTypeCreationAuthorization": "TEST-ONLY"}}

    def preview(self, **kwargs):
        return FormalDailyCapacityImportService.preview(self.path, company_id=self.company.pk,
            expected_source_sha256=kwargs.pop("expected_source_sha256", self.source_sha),
            field_facts=kwargs.pop("field_facts", self.facts), allow_product_type_creation=kwargs.pop("allow_product_type_creation", True), **kwargs)

    def apply(self, **kwargs):
        return FormalDailyCapacityImportService.apply(self.path, user=kwargs.pop("user", self.user), company_id=self.company.pk,
            expected_source_sha256=kwargs.pop("expected_source_sha256", self.source_sha),
            field_facts=kwargs.pop("field_facts", self.facts), allow_product_type_creation=kwargs.pop("allow_product_type_creation", True),
            reason="TEST-ONLY正式容量范围测试", **kwargs)

    def test_preview_scope_zero_blank_and_supplement_are_explicit_and_read_only(self):
        result = self.preview()
        self.assertEqual(result["standardCapacityCounts"], {"total": 6, "positive": 4, "zero": 2, "supplement": 1, "blankNotApplicable": 1})
        mq, bt = result["ruleManifests"]["MQ/FM"], result["ruleManifests"]["BTKF/FM"]
        self.assertIn(self.veneer.pk, mq["applicableOperationIds"])
        self.assertIn(self.veneer.pk, bt["nonApplicableOperationIds"])
        self.assertIn(self.veneering.pk, bt["nonApplicableOperationIds"])
        self.assertEqual(mq["auxiliaryOperationIds"], [self.edge.pk])
        supplement = [p for p in result["capacityPlans"] if p["sourceKind"] == "USER_CONFIRMED_SUPPLEMENT"]
        self.assertEqual(len(supplement), 1)
        self.assertIsNone(supplement[0]["sourceCell"])
        self.assertEqual(supplement[0]["payload"]["quantity"], "60")
        self.assertEqual(CapacityProductType.objects.count(), 0)
        self.assertEqual(StandardCapacity.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_narrow_apply_preserves_resources_processes_routes_and_wc_code_rule(self):
        before = {model.__name__: list(model.objects.values()) for model in (WorkCenter, WorkCenterOperationCapability, Process, Routing)}
        self.rule.refresh_from_db()
        wc_rule = (self.rule.prefix, self.rule.date_format, self.rule.seq_length, self.rule.current_seq)
        result = self.apply()
        self.assertEqual((len(result["createdProductTypes"]), len(result["createdCapacities"])), (2, 6))
        self.assertEqual(result["businessWriteCount"], 8)
        self.assertEqual(len(result["auditIds"]), 8)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 8)
        self.assertEqual(ExternalIdentity.objects.count(), 8)
        for model in (WorkCenter, WorkCenterOperationCapability, Process, Routing):
            self.assertEqual(list(model.objects.values()), before[model.__name__])
        self.rule.refresh_from_db()
        self.assertEqual((self.rule.prefix, self.rule.date_format, self.rule.seq_length, self.rule.current_seq), wc_rule)
        for row in StandardCapacity.objects.all():
            self.assertEqual((row.preparation_days, row.transfer_days), (Decimal("0.1"), Decimal("0.1")))
            self.assertIsNone(row.standard_hours)
            self.assertEqual(row.conditions["apsSourceRules"], result["ruleManifests"][row.product_type.code])
        self.assertEqual(StandardCapacity.objects.filter(measurement_status="zero_capacity").count(), 2)

    def test_exact_replay_performs_zero_writes_including_ledgers_audits_and_sequences(self):
        self.apply()
        before = {model.__name__: list(model.objects.values()) for model in (CapacityProductType, StandardCapacity, MasterDataWriteRequest, ExternalIdentity, OrganizationOperatingAuditRecord, CodeRule)}
        result = self.apply(allow_product_type_creation=False)
        self.assertEqual(result["businessWriteCount"], 0)
        self.assertEqual(result["auditIds"], [])
        self.assertEqual(len(result["reusedCapacities"]), 6)
        for model in (CapacityProductType, StandardCapacity, MasterDataWriteRequest, ExternalIdentity, OrganizationOperatingAuditRecord, CodeRule):
            self.assertEqual(list(model.objects.values()), before[model.__name__])

    def test_missing_product_types_require_explicit_creation_authorization(self):
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(allow_product_type_creation=False)
        self.assertEqual(caught.exception.code, "PCT_AUTHORIZATION_REQUIRED")
        self.assertEqual(CapacityProductType.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_missing_date_or_unit_or_wrong_confirmed_unit_stops_before_writes(self):
        missing_date = {k: v for k, v in self.facts.items() if k != "effectiveDate"}
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(field_facts=missing_date)
        self.assertEqual(caught.exception.code, "EFFECTIVE_DATE_REQUIRED")
        wrong = {**self.facts, "capacityUomIdByProcess": {**self.facts["capacityUomIdByProcess"], self.cut.code: self.uom.pk + 1000}}
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(field_facts=wrong)
        self.assertEqual(caught.exception.code, "CONFIRMED_UOM_MISMATCH")
        self.cut.calculation_uom = None
        self.cut.save(update_fields=("calculation_uom",))
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "PROCESS_UOM_REQUIRED")
        self.assertEqual(CapacityProductType.objects.count(), 0)
        self.assertEqual(StandardCapacity.objects.count(), 0)

    def test_missing_capability_is_blocked_and_never_created(self):
        WorkCenterOperationCapability.objects.filter(operation=self.edge).delete()
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "EXISTING_RESOURCE_REQUIRED")
        self.assertEqual(WorkCenterOperationCapability.objects.count(), 3)
        self.assertEqual(CapacityProductType.objects.count(), 0)

    def test_late_capacity_failure_rolls_back_product_types_capacity_ledgers_and_audits(self):
        original = ProductionFoundationService.write
        calls = []
        def fail_second_capacity(entity, **kwargs):
            calls.append(entity)
            if calls.count("standard-capacities") == 2:
                raise ProductionFoundationError("TEST_ONLY_FAILURE", "隔离测试回退")
            return original(entity, **kwargs)
        with patch.object(ProductionFoundationService, "write", side_effect=fail_second_capacity):
            with self.assertRaises(ProductionFoundationError):
                self.apply()
        self.assertEqual(set(calls), {"capacity-product-types", "standard-capacities"})
        for model in (CapacityProductType, StandardCapacity, MasterDataWriteRequest, ExternalIdentity, OrganizationOperatingAuditRecord):
            self.assertEqual(model.objects.count(), 0)
        self.assertEqual(CodeRule.objects.get(company_id=self.company.pk, entity_type="production_standard_capacity").current_seq, 0)

    def test_existing_conflict_cannot_be_overwritten(self):
        self.apply()
        row = StandardCapacity.objects.get(operation=self.cut, product_type__code="MQ/FM")
        row.quantity = Decimal("98")
        row.save(update_fields=("quantity",))
        before = OrganizationOperatingAuditRecord.objects.count()
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "CAPACITY_EXISTING_CONFLICT")
        row.refresh_from_db()
        self.assertEqual(row.quantity, 98)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)

    def test_changed_preview_fingerprint_is_rejected_without_writes(self):
        reviewed = self.preview()
        changed = {**reviewed, "previewFingerprint": "changed"}
        with patch.object(FormalDailyCapacityImportService, "preview", side_effect=[reviewed, changed]):
            with self.assertRaises(DailyCapacityImportError) as caught:
                self.apply()
        self.assertEqual(caught.exception.code, "PREVIEW_CHANGED")
        self.assertEqual(CapacityProductType.objects.count(), 0)

    def test_permission_source_hash_and_missing_day_times_are_fail_closed(self):
        outsider = User.objects.create_user(username="formal_capacity_read_only", company_id=self.company.pk)
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(user=outsider)
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(expected_source_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "SOURCE_CHANGED")
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply(field_facts={**self.facts, "preparationDays": "0"})
        self.assertEqual(caught.exception.code, "CONFIRMED_DAY_TIME_REQUIRED")
        self.assertEqual(CapacityProductType.objects.count(), 0)

    def test_room_assembly_uses_current_count_uom_and_other_operations_use_area(self):
        count_uom = UnitOfMeasure.objects.create(company_id=self.company.pk, code="套", name="套", dimension="count")
        room = Process.objects.create(company=self.company, workshop=self.workshop, code="FORMAL-ROOM", name="房门组装", calculation_uom=count_uom)
        wc = WorkCenter.objects.create(company=self.company, workshop=self.workshop, code="EXISTING-ROOM", name="房门组装工作中心")
        WorkCenterOperationCapability.objects.create(work_center=wc, operation=room, assignment_role="primary")
        formal_source_fixture(self.path, room=True)
        self.source_sha = DailyCapacityImportService.parse(self.path)["sourceSha256"]
        self.facts["capacityUomIdByProcess"][room.code] = count_uom.pk
        self.apply()
        self.assertEqual(StandardCapacity.objects.filter(operation=room, uom=count_uom).count(), 2)
        self.assertEqual(StandardCapacity.objects.exclude(operation=room).exclude(uom=self.uom).count(), 0)

    def test_process_effective_period_must_cover_confirmed_capacity_date(self):
        from datetime import date
        self.cut.effective_from = date(2026, 10, 14)
        self.cut.save(update_fields=("effective_from",))
        with self.assertRaises(DailyCapacityImportError) as caught:
            self.apply()
        self.assertEqual(caught.exception.code, "EXISTING_RESOURCE_INACTIVE_OR_SCOPE_INVALID")
        self.assertEqual(CapacityProductType.objects.count(), 0)
        self.assertEqual(StandardCapacity.objects.count(), 0)

    def test_equivalent_point_one_day_values_are_canonicalized(self):
        result = self.apply(field_facts={**self.facts, "preparationDays": "0.10", "transferDays": Decimal("0.100")})
        self.assertEqual(result["businessWriteCount"], 8)
        self.assertEqual(result["ruleManifests"]["MQ/FM"]["preparationDays"], "0.1")
        self.assertEqual(result["ruleManifests"]["MQ/FM"]["transferDays"], "0.1")
