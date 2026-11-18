"""APS daily-capacity integrity checks, run only in Django's isolated test DB."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from masterdata.models import UnitOfMeasure
from system.models import Company, Process

from .models import (
    CapacityProductType,
    ManufacturingProcessType,
    ProductCategory,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
    WorkCenter,
)


class DailyCapacityModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DAILY-CAP", name="日产能模型测试公司")
        cls.other_company = Company.objects.create(code="DAILY-OTHER", name="其他测试公司")
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="DAILY-CAT", name="测试半成品分类",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="DAILY-TYPE", name="测试工艺类型",
        )
        cls.product_type = CapacityProductType.objects.create(
            company=cls.company, code="DAILY/SEMI", name="测试半成品类型",
            product_category=cls.category, manufacturing_process_type=cls.process_type,
        )
        cls.work_center = WorkCenter.objects.create(
            company=cls.company, code="WC001", name="测试能力中心",
        )
        cls.operation = Process.objects.create(
            company=cls.company, code="DAILY-OP", name="测试工序",
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="DAILY-PCS", name="件", dimension="count",
        )
        cls.routing = Routing.objects.create(
            company=cls.company, routing_code="DAILY/ROUTE", name="测试路线",
            applicability_scope="PRODUCT_CATEGORY", product_category=cls.category,
            manufacturing_process_type=cls.process_type,
        )
        cls.version = RoutingVersion.objects.create(
            routing=cls.routing, routing_version="V1", status="draft",
        )

    def capacity(self, **overrides):
        values = {
            "company": self.company,
            "code": "DAILY-CAPACITY",
            "name": "测试日产能",
            "resource_scope": StandardCapacity.ResourceScope.COMPOSITE,
            "work_center": self.work_center,
            "operation": self.operation,
            "product_type": self.product_type,
            "measurement_status": StandardCapacity.MeasurementStatus.MEASURED,
            "quantity": Decimal("99"),
            "uom": self.uom,
            "time_basis": StandardCapacity.TimeBasis.DAY,
            "time_basis_quantity": Decimal("1"),
            "effective_from": date(2026, 10, 13),
        }
        values.update(overrides)
        return StandardCapacity(**values)

    def test_daily_capacity_does_not_require_or_generate_standard_hours(self):
        row = self.capacity(preparation_days=Decimal("0.25"), transfer_days=Decimal("1"))
        row.full_clean()
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.quantity, Decimal("99"))
        self.assertEqual(row.time_basis_quantity, Decimal("1"))
        self.assertEqual(row.time_unit, "DAY")
        self.assertIsNone(row.standard_hours)
        self.assertEqual(row.preparation_days, Decimal("0.25"))
        self.assertEqual(row.transfer_days, Decimal("1"))

    def test_zero_source_fact_is_preserved_without_becoming_unknown(self):
        row = self.capacity(
            measurement_status=StandardCapacity.MeasurementStatus.ZERO_CAPACITY,
            quantity=Decimal("0"),
        )
        row.full_clean()
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.quantity, Decimal("0"))
        self.assertEqual(row.measurement_status, "zero_capacity")
        self.assertNotEqual(row.measurement_status, "not_determinable")

    def test_zero_unknown_and_positive_measurements_have_distinct_domains(self):
        for measurement_status, quantity in (
            (StandardCapacity.MeasurementStatus.ZERO_CAPACITY, None),
            (StandardCapacity.MeasurementStatus.ZERO_CAPACITY, Decimal("1")),
            (StandardCapacity.MeasurementStatus.MEASURED, Decimal("0")),
            (StandardCapacity.MeasurementStatus.NOT_DETERMINABLE, Decimal("0")),
        ):
            with self.subTest(status=measurement_status, quantity=quantity):
                with self.assertRaises(ValidationError):
                    self.capacity(measurement_status=measurement_status, quantity=quantity).full_clean()

    def test_database_rejects_null_quantity_for_measured_and_zero_status(self):
        # SQL CHECK must reject NULL, not accept SQLite's UNKNOWN expression.
        for status in ("measured", "zero_capacity"):
            with self.subTest(status=status):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.capacity(measurement_status=status, quantity=None).save()

    def test_missing_daily_times_stay_unknown_and_legacy_hours_are_not_converted(self):
        row = self.capacity(standard_hours=Decimal("24"))
        row.full_clean()
        row.save()
        row.refresh_from_db()
        self.assertIsNone(row.preparation_days)
        self.assertIsNone(row.transfer_days)
        self.assertEqual(row.standard_hours, Decimal("24"))

    def test_legacy_hour_capacity_can_be_preserved_without_becoming_typed_aps_fact(self):
        row = self.capacity(product_type=None, time_basis="hour", standard_hours=Decimal("2"))
        row.full_clean()
        row.save()
        row.refresh_from_db()
        self.assertIsNone(row.product_type_id)
        self.assertEqual(row.time_basis, "hour")

    def test_typed_capacity_requires_one_day_and_both_formal_resource_references(self):
        for overrides, error_key in (
            ({"time_basis": "hour"}, "time_basis"),
            ({"time_basis_quantity": Decimal("2")}, "time_basis_quantity"),
            ({"time_basis_quantity": None}, "time_basis_quantity"),
            ({"work_center": None}, "work_center"),
            ({"operation": None}, "operation"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError) as caught:
                    self.capacity(**overrides).clean()
                self.assertIn(error_key, caught.exception.message_dict)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.capacity(**overrides).save()

    def test_day_unit_and_nonnegative_times_are_enforced_without_model_validation(self):
        for overrides in (
            {"time_unit": "HOUR"},
            {"preparation_days": Decimal("-0.01")},
            {"transfer_days": Decimal("-0.01")},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    self.capacity(**overrides).clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.capacity(**overrides).save()

    def test_product_type_cannot_join_foreign_company_dimensions(self):
        foreign_category = ProductCategory.objects.create(
            company=self.other_company, code="FOREIGN-CAT", name="其他公司分类",
        )
        foreign_process_type = ManufacturingProcessType.objects.create(
            company=self.other_company, code="FOREIGN-TYPE", name="其他公司工艺",
        )
        row = CapacityProductType(
            company=self.company, code="INVALID", name="错误跨公司类型",
            product_category=foreign_category, manufacturing_process_type=foreign_process_type,
        )
        with self.assertRaises(ValidationError) as caught:
            row.clean()
        self.assertEqual(set(caught.exception.message_dict), {
            "product_category", "manufacturing_process_type",
        })

    def test_capacity_type_company_and_valid_dates_are_required(self):
        foreign_type = CapacityProductType(
            id=999, company=self.other_company, code="FOREIGN", name="其他公司类型",
            product_category=self.category, manufacturing_process_type=self.process_type,
        )
        with self.assertRaises(ValidationError) as caught:
            self.capacity(product_type=foreign_type).clean()
        self.assertIn("product_type", caught.exception.message_dict)
        self.product_type.effective_from = date(2026, 10, 13)
        self.product_type.effective_to = date(2026, 10, 12)
        with self.assertRaises(ValidationError):
            self.product_type.clean()

    def test_product_type_code_is_unique_within_company(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CapacityProductType.objects.create(
                company=self.company, code=self.product_type.code, name="重复类型",
                product_category=self.category, manufacturing_process_type=self.process_type,
            )

    def test_routing_day_fields_remain_unknown_and_frozen_steps_remain_immutable(self):
        step = RoutingStep.objects.create(
            routing_version=self.version, sequence=1, operation=self.operation,
            setup_hours=Decimal("10"), transfer_hours=Decimal("2"),
        )
        self.assertIsNone(step.preparation_days)
        self.assertIsNone(step.transfer_days)
        for field in ("preparation_days", "transfer_days"):
            setattr(step, field, Decimal("-1"))
            with self.assertRaises(ValidationError):
                step.clean()
            setattr(step, field, None)
        self.version.status = "released"
        self.version.save(update_fields=["status"])
        step.preparation_days = Decimal("1")
        with self.assertRaises(ValidationError):
            step.save(update_fields=["preparation_days"])
        with self.assertRaises(ValidationError):
            RoutingStep.objects.filter(pk=step.pk).update(transfer_days=Decimal("1"))
        step.refresh_from_db()
        self.assertIsNone(step.preparation_days)
        self.assertIsNone(step.transfer_days)
        self.assertEqual(step.setup_hours, Decimal("10"))
        self.assertEqual(step.transfer_hours, Decimal("2"))
