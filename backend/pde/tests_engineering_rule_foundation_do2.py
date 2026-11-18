from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from pfm.models import Employee
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)

from .engineering_rule_foundation import (
    EngineeringRuleError,
    SOURCE_TYPES,
    evaluate_specification,
    execute_released_package,
    specification_hash,
    stable_topological_order,
    validate_specification,
)
from .formal_engineering_continuation_service import formal_rule_blueprints
from .models import (
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringRuleDefinition,
)
from .production_foundation_service import (
    EngineeringLifecycleService,
    ProductionFoundationError,
    ProductionFoundationService,
)


DO2_PERMISSION_CODES = (
    "production.engineering.rule.view",
    "production.engineering.rule.create",
    "production.engineering.rule.update_draft",
    "production.engineering.rule.release",
)


def rule_spec(
    *,
    expression="opening_height - 10",
    inputs=None,
    output="casing_height",
    output_dimension="length",
    output_domain="DERIVED_FACT",
    dependencies=None,
    priority=100,
    package_code="G1_FOUNDATION",
    package_version="V1.0",
    precision=18,
    scale=2,
    rounding="ROUND_HALF_UP",
):
    return {
        "description": "DO-2隔离规则验收",
        "rulePackage": {"code": package_code, "version": package_version},
        "expression": expression,
        "inputs": inputs or [{
            "canonicalName": "opening_height",
            "valueType": "decimal",
            "unitDimension": "length",
            "unitRequired": False,
            "required": True,
            "sourceType": "SITE_MEASUREMENT",
            "description": "规范洞高",
        }],
        "outputs": [{
            "canonicalName": output,
            "valueType": "decimal",
            "unitDimension": output_dimension,
            "unit": "mm" if output_dimension == "length" else None,
            "resultDomain": output_domain,
            "description": "规则输出",
        }],
        "dependencies": dependencies or [],
        "applicability": {"productCategoryCodes": [], "condition": "controlled-data"},
        "decimalPrecision": precision,
        "outputScale": scale,
        "roundingMode": rounding,
        "priority": priority,
        "sourceEvidence": {
            "reference": "PCM-PDE-009 / Production L7 V1.5",
            "documentVersion": "V1.5",
            "evidenceHash": "test-evidence",
        },
    }


def transient_rule(code, spec, *, status="released", version="V1.0"):
    return SimpleNamespace(
        rule_code=code, specification=spec, status=status, version=version,
    )


class EngineeringRuleFoundationDO2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DO2", name="DO-2验收公司")
        cls.department = Department.objects.create(
            code="DO2-ENG", name="工程技术部", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="DO2-ENGINEER", name="工程规则岗", company=cls.company,
            department=cls.department,
        )
        cls.responsibility = Responsibility.objects.create(
            code="RESP_DO2_RULE", name="工程规则治理",
            status="ACTIVE", is_active=True,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility,
            is_primary=True, active=True,
        )
        cls.user = User.objects.create_user(
            username="do2_engineer", password="test-only", real_name="DO-2工程员",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.user, employee_no="DO2-E001", full_name="DO-2工程员",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        cls.role = Role.objects.create(code="DO2_RULE_ROLE", name="DO-2工程规则角色")
        for code in DO2_PERMISSION_CODES:
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": code, "module": "PRODUCTION"},
            )
            RolePermission.objects.create(role=cls.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do2-authorized",
        )

        cls.denied_user = User.objects.create_user(
            username="do2_denied", password="test-only", real_name="无规则权限用户",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.denied_user, employee_no="DO2-E002", full_name="无规则权限用户",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        cls.denied_role = Role.objects.create(code="DO2_DENIED_ROLE", name="无规则权限角色")
        UserRoleScopeAssignment.objects.create(
            user=cls.denied_user, role=cls.denied_role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do2-denied",
        )
        cls.technical_admin = User.objects.create_user(
            username="do2_technical_admin", password="test-only",
            real_name="DO-2技术管理员", company_id=cls.company.pk,
            is_staff=True, is_superuser=True,
        )

    def _create(self, code="G1_CASING_HEIGHT", version="V1.0", specification=None):
        return ProductionFoundationService.save(
            "engineering-rule-definitions",
            user=self.user,
            payload={
                "company_id": self.company.pk,
                "rule_code": code,
                "rule_name": "通用安全公式",
                "version": version,
                "rule_kind": "formula",
                "specification": specification or rule_spec(),
                "effective_from": date.today().isoformat(),
                "reason": "DO-2正式规则草稿验收",
            },
        )

    def _release(self, rule):
        EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="reviewed", user=self.user, reason="DO-2规则评审",
        )
        return EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="released", user=self.user, reason="DO-2规则发布",
        )

    def test_01_existing_rule_model_is_reused_without_parallel_v2(self):
        self.assertEqual(EngineeringRuleDefinition._meta.db_table, "pde_engineering_rule_definition")
        self.assertEqual(
            EngineeringRuleDefinition.objects.filter(company=self.company).count(), 0,
        )

    def test_02_create_draft_uses_dedicated_permission_and_audit(self):
        result = self._create()
        rule = EngineeringRuleDefinition.objects.get(pk=result["row"]["id"])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(rule.status, "draft")
        self.assertEqual(audit.action_code, "production.engineering.rule.create")
        self.assertEqual(audit.after_snapshot["state"]["specification_hash"], specification_hash(rule.specification))
        self.assertEqual(audit.after_snapshot["state"]["operator"], self.user.username)
        self.assertTrue(audit.after_snapshot["authorization"]["allowed"])

    def test_03_update_draft_uses_dedicated_permission(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create()["row"]["id"])
        spec = deepcopy(rule.specification)
        spec["description"] = "修订后的草稿说明"
        result = ProductionFoundationService.save(
            "engineering-rule-definitions", user=self.user, object_id=rule.pk,
            payload={"specification": spec, "reason": "更新草稿"},
        )
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(audit.action_code, "production.engineering.rule.update_draft")

    def test_04_non_draft_rule_cannot_be_updated(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create()["row"]["id"])
        EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="reviewed", user=self.user,
        )
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.save(
                "engineering-rule-definitions", user=self.user, object_id=rule.pk,
                payload={"rule_name": "禁止修改"},
            )
        self.assertEqual(caught.exception.code, "RELEASED_RULE_IMMUTABLE")

    def test_05_release_lifecycle_and_release_audit(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create()["row"]["id"])
        result = self._release(rule)
        rule.refresh_from_db()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(rule.status, "released")
        self.assertEqual(audit.action_code, "production.engineering.rule.release")
        self.assertEqual(audit.after_snapshot["state"]["rule_version"], "V1.0")

    def test_06_release_is_idempotent(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create()["row"]["id"])
        self._release(rule)
        result = EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="released", user=self.user,
        )
        self.assertTrue(result["idempotent"])
        self.assertIsNone(result["auditId"])

    def test_07_only_released_rule_is_executable(self):
        draft = transient_rule("DRAFT_RULE", rule_spec(), status="draft")
        with self.assertRaises(EngineeringRuleError) as caught:
            execute_released_package([draft], {"opening_height": "2035"})
        self.assertEqual(caught.exception.code, "RULE_NOT_RELEASED")

    def test_08_released_core_definition_is_immutable(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create()["row"]["id"])
        self._release(rule)
        rule.refresh_from_db()
        rule.rule_name = "禁止原位修改"
        with self.assertRaises(ValidationError):
            rule.save()

    def test_09_same_rule_code_supports_new_version_but_rejects_duplicate_version(self):
        self._create(code="VERSIONED_RULE", version="V1.0")
        self._create(code="VERSIONED_RULE", version="V1.1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EngineeringRuleDefinition.objects.create(
                    company=self.company, rule_code="VERSIONED_RULE", rule_name="重复版本",
                    version="V1.1", rule_kind="formula", specification=rule_spec(),
                )

    def test_10_invalid_expression_is_rejected(self):
        spec = rule_spec(expression="opening_height -")
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "INVALID_EXPRESSION")

    def test_11_eval_and_function_calls_are_forbidden(self):
        spec = rule_spec(expression="eval(opening_height)")
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "INVALID_EXPRESSION")

    def test_12_attribute_access_is_forbidden(self):
        spec = rule_spec(expression="opening_height.real")
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "INVALID_EXPRESSION")

    def test_13_unsupported_operator_is_classified(self):
        spec = rule_spec(expression="opening_height ** 2")
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_OPERATOR")

    def test_14_unknown_variable_is_classified(self):
        spec = rule_spec(expression="opening_height - mystery")
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "UNKNOWN_VARIABLE")

    def test_15_division_by_zero_is_classified(self):
        spec = rule_spec(expression="opening_height / 0")
        with self.assertRaises(EngineeringRuleError) as caught:
            evaluate_specification(spec, {"opening_height": "2035"})
        self.assertEqual(caught.exception.code, "DIVISION_BY_ZERO")

    def test_16_binary_float_input_is_rejected(self):
        with self.assertRaises(EngineeringRuleError) as caught:
            evaluate_specification(rule_spec(), {"opening_height": 2035.0})
        self.assertEqual(caught.exception.code, "INVALID_DECIMAL")

    def test_17_decimal_precision_and_rounding_are_deterministic(self):
        inputs = [{
            "canonicalName": "quantity", "valueType": "decimal",
            "unitDimension": "count", "unitRequired": False,
            "required": True, "sourceType": "ENGINEERING_INPUT",
        }]
        spec = rule_spec(
            expression="quantity / 3", inputs=inputs, output="share",
            output_dimension="count", scale=3, rounding="ROUND_HALF_UP",
        )
        result = evaluate_specification(spec, {"quantity": "1"})
        self.assertEqual(result["value"], "0.333")

    def test_18_required_unit_metadata_is_enforced(self):
        spec = rule_spec()
        spec["inputs"][0]["unitRequired"] = True
        with self.assertRaises(EngineeringRuleError) as caught:
            evaluate_specification(spec, {"opening_height": "2035"})
        self.assertEqual(caught.exception.code, "UNIT_MISMATCH")

    def test_19_input_unit_dimension_mismatch_is_rejected(self):
        with self.assertRaises(EngineeringRuleError) as caught:
            evaluate_specification(rule_spec(), {
                "opening_height": {"value": "2035", "unit": "kg", "unitDimension": "mass"},
            })
        self.assertEqual(caught.exception.code, "UNIT_MISMATCH")

    def test_20_output_dimension_mismatch_is_rejected(self):
        spec = rule_spec(output_dimension="mass")
        with self.assertRaises(EngineeringRuleError) as caught:
            evaluate_specification(spec, {"opening_height": "2035"})
        self.assertEqual(caught.exception.code, "UNIT_MISMATCH")

    def test_21_frozen_nine_source_types_are_exact(self):
        self.assertEqual(SOURCE_TYPES, {
            "CUSTOMER", "SITE_MEASUREMENT", "SALES", "DESIGN", "ENGINEERING_INPUT",
            "ENGINEERING_DERIVED", "MASTER_DATA", "RULE_PARAMETER", "AGGREGATED",
        })

    def test_22_three_output_domains_are_accepted_without_persistence(self):
        for domain in ("DERIVED_FACT", "MATERIAL_REQUIREMENT", "OPERATION_REQUIREMENT"):
            result = evaluate_specification(
                rule_spec(output_domain=domain), {"opening_height": "2035"},
            )
            self.assertEqual(result["resultDomain"], domain)

    def test_23_unknown_dependency_is_rejected(self):
        rule = transient_rule("RULE_A", rule_spec(dependencies=["RULE_MISSING"]))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([rule])
        self.assertEqual(caught.exception.code, "UNKNOWN_DEPENDENCY")

    def test_24_duplicate_output_is_rejected(self):
        first = transient_rule("RULE_A", rule_spec())
        second = transient_rule("RULE_B", rule_spec(expression="opening_height - 20"))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([first, second])
        self.assertEqual(caught.exception.code, "DUPLICATE_OUTPUT")

    def test_25_dependency_cycle_is_rejected(self):
        input_a = [{
            "canonicalName": "output_b", "valueType": "decimal",
            "unitDimension": "length", "unitRequired": False,
            "required": True, "sourceType": "ENGINEERING_DERIVED",
        }]
        input_b = [{
            "canonicalName": "output_a", "valueType": "decimal",
            "unitDimension": "length", "unitRequired": False,
            "required": True, "sourceType": "ENGINEERING_DERIVED",
        }]
        first = transient_rule("RULE_A", rule_spec(
            expression="output_b - 1", inputs=input_a, output="output_a", dependencies=["RULE_B"],
        ))
        second = transient_rule("RULE_B", rule_spec(
            expression="output_a - 1", inputs=input_b, output="output_b", dependencies=["RULE_A"],
        ))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([first, second])
        self.assertEqual(caught.exception.code, "DEPENDENCY_CYCLE")

    def test_26_missing_derived_producer_is_rejected(self):
        inputs = [{
            "canonicalName": "unknown_fact", "valueType": "decimal",
            "unitDimension": "length", "unitRequired": False,
            "required": True, "sourceType": "ENGINEERING_DERIVED",
        }]
        rule = transient_rule("RULE_A", rule_spec(
            expression="unknown_fact - 1", inputs=inputs, output="result",
        ))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([rule])
        self.assertEqual(caught.exception.code, "MISSING_PRODUCER")

    def test_27_unreachable_rule_is_rejected_for_declared_target(self):
        first = transient_rule("RULE_A", rule_spec(output="target_a"))
        second = transient_rule("RULE_B", rule_spec(
            expression="opening_height - 20", output="unused_b",
        ))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([first, second], target_outputs=["target_a"])
        self.assertEqual(caught.exception.code, "UNREACHABLE_RULE")

    def test_28_stable_topological_order_uses_priority_then_rule_code(self):
        rules = [
            transient_rule("RULE_C", rule_spec(output="out_c", priority=20)),
            transient_rule("RULE_B", rule_spec(output="out_b", priority=10)),
            transient_rule("RULE_A", rule_spec(output="out_a", priority=10)),
        ]
        ordered = stable_topological_order(rules, target_outputs=["out_a", "out_b", "out_c"])
        self.assertEqual([rule.rule_code for rule in ordered], ["RULE_A", "RULE_B", "RULE_C"])

    def test_29_dependency_precedes_priority(self):
        first = transient_rule("RULE_SOURCE", rule_spec(output="base", priority=100))
        inputs = [{
            "canonicalName": "base", "valueType": "decimal", "unitDimension": "length",
            "unitRequired": False, "required": True, "sourceType": "ENGINEERING_DERIVED",
        }]
        second = transient_rule("RULE_TARGET", rule_spec(
            expression="base - 1", inputs=inputs, output="target",
            dependencies=["RULE_SOURCE"], priority=1,
        ))
        ordered = stable_topological_order([second, first], target_outputs=["target"])
        self.assertEqual([rule.rule_code for rule in ordered], ["RULE_SOURCE", "RULE_TARGET"])

    def test_30_non_wood_industry_weight_formula_proves_neutrality(self):
        inputs = [
            {
                "canonicalName": "length", "valueType": "decimal",
                "unitDimension": "length", "unitRequired": False,
                "required": True, "sourceType": "ENGINEERING_INPUT",
            },
            {
                "canonicalName": "unit_weight", "valueType": "decimal",
                "unitDimension": "mass_per_length", "unitRequired": False,
                "required": True, "sourceType": "MASTER_DATA",
            },
        ]
        spec = rule_spec(
            expression="length * unit_weight", inputs=inputs,
            output="theoretical_weight", output_dimension="mass", scale=3,
        )
        result = evaluate_specification(spec, {"length": "12.5", "unit_weight": "2.4"})
        self.assertEqual(result["value"], "30.000")

    def test_31_source_evidence_is_mandatory(self):
        spec = rule_spec()
        spec["sourceEvidence"] = {}
        with self.assertRaises(EngineeringRuleError) as caught:
            validate_specification(spec)
        self.assertEqual(caught.exception.code, "INVALID_SPECIFICATION")

    def test_32_package_version_mismatch_is_rejected(self):
        first = transient_rule("RULE_A", rule_spec(output="out_a", package_version="V1.0"))
        second = transient_rule("RULE_B", rule_spec(
            expression="opening_height - 20", output="out_b", package_version="V1.1",
        ))
        with self.assertRaises(EngineeringRuleError) as caught:
            stable_topological_order([first, second])
        self.assertEqual(caught.exception.code, "RULE_PACKAGE_MISMATCH")

    def test_33_isolated_execution_persists_no_do3_results(self):
        before = (EngineeringCalculationRecord.objects.count(), EngineeringDerivedFact.objects.count())
        rule = transient_rule("G1_CASING_HEIGHT", rule_spec())
        result = execute_released_package([rule], {"opening_height": "2035"})
        after = (EngineeringCalculationRecord.objects.count(), EngineeringDerivedFact.objects.count())
        self.assertEqual(result["outputs"]["casing_height"]["value"], "2025.00")
        self.assertFalse(result["persisted"])
        self.assertEqual(before, after)

    def test_34_authorization_denies_create_without_formal_permission(self):
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.save(
                "engineering-rule-definitions", user=self.denied_user,
                payload={
                    "company_id": self.company.pk, "rule_code": "DENIED_RULE",
                    "rule_name": "拒绝规则", "version": "V1.0",
                    "rule_kind": "formula", "specification": rule_spec(),
                },
            )
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")

    def test_35_rule_api_view_permission_is_distinct(self):
        client = APIClient()
        url = reverse("pde-a1-foundation-entity", kwargs={"entity": "engineering-rule-definitions"})
        client.force_authenticate(self.denied_user)
        denied = client.get(url)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data["message"], "当前账号没有“查看工程规则定义”权限。")
        client.force_authenticate(self.user)
        rule_count_before = EngineeringRuleDefinition.objects.count()
        allowed = client.get(url)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data["factSource"], "server")
        self.assertIn("engineering-rule-definitions", allowed.data["facts"])
        self.assertTrue(allowed.data["currentUserAuthorization"]["production.engineering.rule.view"]["allowed"])
        candidates = allowed.data["engineeringRuleRegistrationCandidates"]
        self.assertEqual(
            [row["ruleCode"] for row in candidates],
            ["APPROVED_SOURCE_NET", "SOURCE_LINEAR_CONTINUATION"],
        )
        self.assertTrue(all(row["registrationStatus"] == "NOT_REGISTERED_MATERIAL" for row in candidates))
        self.assertTrue(all(len(row["specificationHash"]) == 64 for row in candidates))
        self.assertTrue(all(row["businessExplanation"]["purpose"] for row in candidates))
        self.assertTrue(all(row["businessExplanation"]["inputs"] for row in candidates))
        self.assertTrue(all(row["businessExplanation"]["outputs"] for row in candidates))
        self.assertEqual(candidates[0]["version"], "V1")
        self.assertNotIn("orderNo", candidates[0])
        self.assertNotIn("sourceRecord", candidates[0])
        self.assertEqual(EngineeringRuleDefinition.objects.count(), rule_count_before)

    def test_36_legacy_draft_rule_remains_readable(self):
        legacy = EngineeringRuleDefinition.objects.create(
            company=self.company, rule_code="LEGACY-A17", rule_name="历史映射规则",
            version="V1", rule_kind="mapping", specification={"input": "quantity"},
        )
        self.assertEqual(
            EngineeringRuleDefinition.objects.get(pk=legacy.pk).specification,
            {"input": "quantity"},
        )

    def test_37_core_schema_contains_no_wood_industry_fields(self):
        fields = {field.name.lower() for field in EngineeringRuleDefinition._meta.fields}
        for forbidden in ("door", "cabinet", "wall_panel", "wood_type", "洞高", "洞宽", "墙厚"):
            self.assertFalse(any(forbidden in field for field in fields))

    def test_38_rule_view_does_not_grant_calculation_readiness(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-engineering-calculation-readiness"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_39_governed_candidate_keeps_v1_through_formal_service_and_lifecycle(self):
        blueprint = deepcopy(formal_rule_blueprints()[0])
        blueprint["company_id"] = self.company.pk
        blueprint["reason"] = "隔离库验证受治理方案V1登记"
        result = ProductionFoundationService.save(
            "engineering-rule-definitions", user=self.user, payload=blueprint,
        )
        rule = EngineeringRuleDefinition.objects.get(pk=result["row"]["id"])
        self.assertEqual(rule.version, "V1")
        self.assertEqual(rule.status, "draft")
        reviewed = EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="reviewed", user=self.user, reason="隔离库评审",
        )
        released = EngineeringLifecycleService.transition(
            "engineering-rule-definitions", object_id=rule.pk,
            target_status="released", user=self.user, reason="隔离库发布",
        )
        rule.refresh_from_db()
        self.assertEqual(reviewed["row"]["status"], "reviewed")
        self.assertEqual(released["row"]["status"], "released")
        self.assertEqual(rule.version, "V1")

    def _released_effectivity_rule(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self._create(
            code="EFFECTIVITY_CORRECTION", version="V1",
        )["row"]["id"])
        ProductionFoundationService.save(
            "engineering-rule-definitions", user=self.user, object_id=rule.pk,
            payload={
                "effective_to": "2030-09-25",
                "reason": "隔离测试设置原失效日期",
            },
        )
        self._release(rule)
        rule.refresh_from_db()
        return rule

    def _effectivity_correction_kwargs(self, rule, **overrides):
        values = {
            "user": self.technical_admin,
            "object_id": rule.pk,
            "expected_company_id": self.company.pk,
            "expected_rule_code": rule.rule_code,
            "expected_version": rule.version,
            "expected_status": "released",
            "expected_effective_from": rule.effective_from.isoformat(),
            "expected_effective_to": rule.effective_to.isoformat(),
            "expected_specification_hash": specification_hash(rule.specification),
            "expected_updated_at": rule.updated_at.isoformat(),
            "corrected_effective_to": None,
            "reason": "用户批准将已发布规则失效日期纠正为空",
            "approval_reference": "DO2-EFFECTIVITY-CORRECTION-APPROVAL",
            "idempotency_key": "do2-effectivity-correction-once",
        }
        values.update(overrides)
        return values

    def test_40_approved_released_effectivity_correction_is_audited(self):
        rule = self._released_effectivity_rule()
        before = {
            "code": rule.rule_code, "version": rule.version,
            "status": rule.status, "effective_from": rule.effective_from,
            "specification": deepcopy(rule.specification),
        }
        result = ProductionFoundationService.correct_released_rule_effectivity(
            **self._effectivity_correction_kwargs(rule)
        )
        rule.refresh_from_db()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertIsNone(rule.effective_to)
        self.assertEqual(rule.rule_code, before["code"])
        self.assertEqual(rule.version, before["version"])
        self.assertEqual(rule.status, before["status"])
        self.assertEqual(rule.effective_from, before["effective_from"])
        self.assertEqual(rule.specification, before["specification"])
        self.assertEqual(audit.action_code, "production.engineering.rule.correct_effectivity")
        self.assertEqual(audit.actor, self.technical_admin)
        self.assertEqual(audit.before_snapshot["state"]["effective_to"], "2030-09-25")
        self.assertIsNone(audit.after_snapshot["state"]["effective_to"])

    def test_41_release_permission_without_technical_authority_is_denied(self):
        rule = self._released_effectivity_rule()
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.correct_released_rule_effectivity(
                **self._effectivity_correction_kwargs(rule, user=self.user)
            )
        self.assertEqual(caught.exception.code, "TECHNICAL_CORRECTION_AUTHORITY_REQUIRED")
        rule.refresh_from_db()
        self.assertEqual(rule.effective_to.isoformat(), "2030-09-25")

    def test_42_wrong_approved_identity_or_old_value_is_denied(self):
        rule = self._released_effectivity_rule()
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.correct_released_rule_effectivity(
                **self._effectivity_correction_kwargs(
                    rule, expected_rule_code="OTHER_RULE",
                    expected_effective_to="2029-09-25",
                )
            )
        self.assertEqual(caught.exception.code, "CORRECTION_SCOPE_MISMATCH")
        rule.refresh_from_db()
        self.assertEqual(rule.effective_to.isoformat(), "2030-09-25")

    def test_43_audit_failure_rolls_back_date_correction(self):
        rule = self._released_effectivity_rule()
        with patch("pde.production_foundation_service._audit", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                ProductionFoundationService.correct_released_rule_effectivity(
                    **self._effectivity_correction_kwargs(rule)
                )
        rule.refresh_from_db()
        self.assertEqual(rule.effective_to.isoformat(), "2030-09-25")

    def test_44_repeated_correction_reuses_one_audit(self):
        rule = self._released_effectivity_rule()
        kwargs = self._effectivity_correction_kwargs(rule)
        first = ProductionFoundationService.correct_released_rule_effectivity(**kwargs)
        second = ProductionFoundationService.correct_released_rule_effectivity(**kwargs)
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["auditId"], first["auditId"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code="production.engineering.rule.correct_effectivity",
            target_id=rule.pk,
        ).count(), 1)

    def test_45_api_rejects_unknown_fields_and_non_null_correction(self):
        rule = self._released_effectivity_rule()
        kwargs = self._effectivity_correction_kwargs(rule)
        payload = {
            "expectedCompanyId": kwargs["expected_company_id"],
            "expectedRuleCode": kwargs["expected_rule_code"],
            "expectedVersion": kwargs["expected_version"],
            "expectedStatus": kwargs["expected_status"],
            "expectedEffectiveFrom": kwargs["expected_effective_from"],
            "expectedEffectiveTo": kwargs["expected_effective_to"],
            "expectedSpecificationHash": kwargs["expected_specification_hash"],
            "expectedUpdatedAt": kwargs["expected_updated_at"],
            "correctedEffectiveTo": None,
            "reason": kwargs["reason"],
            "approvalReference": kwargs["approval_reference"],
            "idempotencyKey": kwargs["idempotency_key"],
            "status": "draft",
        }
        client = APIClient()
        client.force_authenticate(self.technical_admin)
        url = reverse("pde-engineering-rule-effectivity-correction", args=[rule.pk])
        denied = client.post(url, payload, format="json")
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(denied.data["code"], "CORRECTION_FIELDS_DENIED")
        payload.pop("status")
        payload["correctedEffectiveTo"] = "2099-12-31"
        denied_value = client.post(url, payload, format="json")
        self.assertEqual(denied_value.status_code, 400)
        self.assertEqual(denied_value.data["code"], "CORRECTION_VALUE_DENIED")

    def test_46_released_rule_normal_patch_remains_denied(self):
        rule = self._released_effectivity_rule()
        client = APIClient()
        client.force_authenticate(self.technical_admin)
        response = client.patch(
            reverse("pde-a1-foundation-object", args=["engineering-rule-definitions", rule.pk]),
            {"effective_to": None, "reason": "禁止通过普通编辑纠正"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "RELEASED_RULE_IMMUTABLE")
