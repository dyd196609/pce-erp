from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from pde.models import EngineeringBreakdownOption

from .authorization import AuthorizationService
from .models import Company, OrganizationOperatingAuditRecord, OrganizationUnit, User
from .single_company_convergence import (
    SingleCompanyConvergenceError,
    _deactivate_blocked_example_company,
    _delete_empty_example_company,
    _delete_approved_example_company_with_code_rules,
    _rows_business_hash,
)


class InactiveCompanyWriteGuardTests(TestCase):
    def test_superuser_is_denied_when_target_company_is_inactive(self):
        company = Company.objects.create(
            id=3, code="PDEACCEPT", name="PDE非生产页面验收", is_active=False,
        )
        actor = User.objects.create_superuser(
            username="inactive-scope-admin", password="unused", company_id=company.pk,
        )

        decision = AuthorizationService.decide(
            user=actor,
            action_code="system.organization.structure.manage",
            organization_id=company.pk,
        )

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["decisionCode"], "ORGANIZATION_INACTIVE")


class EmptyExampleCompanyDeletionTests(TestCase):
    def setUp(self):
        self.target = Company.objects.create(
            id=1, code="COMP001", name="掌云智造科技有限公司", is_active=True,
        )
        self.actor = User.objects.create_superuser(
            username="admin", password="unused", company_id=self.target.pk,
        )

    def test_exact_empty_example_and_its_only_unit_are_physically_deleted(self):
        example = Company.objects.create(
            id=2, code="COMP002", name="示例制造有限公司", is_active=True,
        )
        unit = OrganizationUnit.objects.create(
            company=example,
            code="COMP-COMP002",
            name=example.name,
            unit_type=OrganizationUnit.UnitType.COMPANY,
        )

        result = _delete_empty_example_company(self.actor)

        self.assertEqual(result["mode"], "PHYSICALLY_DELETED")
        self.assertEqual(result["deletedOrganizationUnitIds"], [unit.pk])
        self.assertFalse(Company.objects.filter(pk=2).exists())
        self.assertFalse(OrganizationUnit.objects.filter(pk=unit.pk).exists())
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(audit.organization_id, 1)
        self.assertTrue(audit.after_snapshot["companyDeleted"])

    def test_unexpected_reference_blocks_delete(self):
        example = Company.objects.create(
            id=2, code="COMP002", name="示例制造有限公司", is_active=True,
        )
        OrganizationUnit.objects.create(
            company=example,
            code="COMP-COMP002",
            name=example.name,
            unit_type=OrganizationUnit.UnitType.COMPANY,
        )
        OrganizationUnit.objects.create(
            company=example,
            code="COMP-COMP002-EXTRA",
            name="额外组织",
            unit_type=OrganizationUnit.UnitType.DEPARTMENT,
        )

        with self.assertRaisesRegex(Exception, "COMP002出现非预期引用"):
            _delete_empty_example_company(self.actor)

        self.assertTrue(Company.objects.filter(pk=2).exists())

    def test_blocked_example_is_deactivated_without_claiming_deletion(self):
        Company.objects.create(
            id=2, code="COMP002", name="示例制造有限公司", is_active=True,
        )
        blocker = SingleCompanyConvergenceError(
            "EXAMPLE_COMPANY_UNEXPECTED_REFERENCES",
            "COMP002出现非预期引用，已停止删除。",
            {"references": [{"table": "code_rule", "count": 4}]},
        )

        result = _deactivate_blocked_example_company(self.actor, blocker)

        self.assertEqual(result["mode"], "DELETE_BLOCKED_DEACTIVATED")
        self.assertFalse(Company.objects.get(pk=2).is_active)
        self.assertTrue(Company.objects.filter(pk=2).exists())

    def _create_approved_code_rules(self, *, wrong_prefix=False):
        rows = (
            (13, "production_standard_capacity", "WRONG" if wrong_prefix else "CAP"),
            (14, "production_engineering_source", "ENGSRC"),
            (15, "production_order_engineering", "OEI"),
            (17, "production_engineering_calculation", "EC"),
        )
        with connection.cursor() as cursor:
            for pk, entity_type, prefix in rows:
                cursor.execute(
                    "INSERT INTO code_rule "
                    "(id, entity_type, prefix, date_format, seq_length, current_seq, company_id, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    [pk, entity_type, prefix, "%Y%m", 6, 0, 2],
                )

    def test_explicitly_approved_rules_unit_and_company_are_exactly_deleted(self):
        example = Company.objects.create(
            id=2, code="COMP002", name="示例制造有限公司", is_active=False,
        )
        OrganizationUnit.objects.create(
            id=2, company=example, code="COMP-COMP002", name=example.name,
            unit_type=OrganizationUnit.UnitType.COMPANY,
        )
        self._create_approved_code_rules()
        protected_option = EngineeringBreakdownOption.objects.create(
            id=13, company=self.target, option_type="edge_method",
            code="EDGE-TWO-LONG", name="两长", is_active=True,
        )

        with patch("system.single_company_convergence._database_guard", return_value={"nonProduction": True}):
            result = _delete_approved_example_company_with_code_rules(self.actor)

        self.assertEqual(result["deletedCompanyIds"], [2])
        self.assertEqual(result["deletedOrganizationUnitIds"], [2])
        self.assertEqual(result["deletedCodeRuleIds"], [13, 14, 15, 17])
        self.assertFalse(Company.objects.filter(pk=2).exists())
        self.assertFalse(OrganizationUnit.objects.filter(pk=2).exists())
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM code_rule WHERE id IN (13, 14, 15, 17)")
            self.assertEqual(cursor.fetchone()[0], 0)
        self.assertTrue(EngineeringBreakdownOption.objects.filter(pk=protected_option.pk).exists())

    def test_approved_delete_rolls_back_when_one_rule_identity_changed(self):
        example = Company.objects.create(
            id=2, code="COMP002", name="示例制造有限公司", is_active=False,
        )
        OrganizationUnit.objects.create(
            id=2, company=example, code="COMP-COMP002", name=example.name,
            unit_type=OrganizationUnit.UnitType.COMPANY,
        )
        self._create_approved_code_rules(wrong_prefix=True)

        with patch("system.single_company_convergence._database_guard", return_value={"nonProduction": True}):
            with self.assertRaisesRegex(Exception, "已停止删除"):
                _delete_approved_example_company_with_code_rules(self.actor)

        self.assertTrue(Company.objects.filter(pk=2).exists())
        self.assertTrue(OrganizationUnit.objects.filter(pk=2).exists())
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM code_rule WHERE id IN (13, 14, 15, 17)")
            self.assertEqual(cursor.fetchone()[0], 4)


class SourceBusinessHashTests(TestCase):
    def test_reference_remap_does_not_change_business_row_hash(self):
        before = [{"id": "ROW-1", "product": "柜体", "quantity": "1", "productCategoryId": 4, "productCategoryCode": "PDE-DOOR", "edgeMethodOptionId": None}]
        after = [{"id": "ROW-1", "product": "柜体", "quantity": "1", "productCategoryId": 1, "productCategoryCode": "CAT202609000001", "edgeMethodOptionId": 9, "edgeMethodOptionCode": "EDGE-FOUR-SIDES", "edgeMethodOptionName": "四边"}]

        self.assertEqual(_rows_business_hash(before), _rows_business_hash(after))
