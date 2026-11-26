"""SIMULATED_FOR_TEST: exact saved preparation ruling, real formal consumers.

Only the task's named disposable SQLite runner may execute this module. Existing
fixture TestCases are composed, not inherited or rediscovered. Only the source
matrix is controlled below; preparation, permissions, object proofs and Daily
readiness are never replaced with successful mock results.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from system.models import Company, Permission, RolePermission, User
from . import daily_capacity_service as daily
from . import operation_input_preparation_service as preparation
from . import operation_workload_source_service as workload
from . import routing_object_applicability_service as object_applicability
from . import tests_operation_input_preparation as preparation_fixtures
from .engineering_rule_foundation import specification_hash
from .models import OperationInputPreparationDraft, RoutingStepObjectApplicability, StandardCapacity
from .operation_requirement_service import OperationRequirementError
from .production_foundation_service import ProductionFoundationError
from .routing_version_successor_service import ROUTING_PERMISSION


class PreparationRulingCapacityConsumptionTests(TestCase):
    def setUp(self):
        self.case = preparation_fixtures.OperationInputPreparationTests(methodName="runTest")
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan
        self.step, self.operation, self.user = self.case.step, self.case.operation, self.case.user
        permission, _ = Permission.objects.get_or_create(code=ROUTING_PERMISSION,
            defaults={"name": ROUTING_PERMISSION, "module": "PRODUCTION"})
        RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        # Formal REQUIRED decisions are saved through the original writer; the
        # native resolver must expose the blank-vs-required conflict itself.
        contributions = []
        for obj in self.f.baseline_items:
            context = object_applicability.build_context(self.plan.pk, self.step.pk, obj.pk)
            fact = next(row for row in self.f.facts if row.trace["baselineItemId"] == obj.pk)
            proof = next(row for row in context["sourceProofs"] if row["id"] == fact.pk)
            basis = {"contractVersion": object_applicability.BASIS_CONTRACT_VERSION,
                "decisionReference": {"code": "SIM-EXACT-ZERO-CONSUMPTION", "statement": "This exact object must pass",
                    "reference": "SIMULATED_FOR_TEST", "referenceSha256": "d" * 64},
                "sourceFact": {"id": fact.pk, "sourceSnapshotHash": proof["sourceSnapshotHash"]},
                "rules": [{"id": self.f.producer.pk, "version": self.f.producer.version,
                    "specificationHash": specification_hash(self.f.producer.specification)}],
                "execution": {"mode": "AUTHORIZED_CODEX_AGENT", "humanBusinessAcceptanceClaimed": False}}
            contributions.append({"baselineItemId": obj.pk, "decision": "REQUIRED", "basis": basis,
                "contextHash": context["contextHash"], "idempotencyKey": context["suggestedIdempotencyKey"]})
        object_applicability.confirm_group(self.user, self.plan.pk, self.step.pk, contributions,
            "SIMULATED_FOR_TEST formal object decisions before preparation")
        self.case.prepared = self.case.read()
        self.case.basis["entries"][0]["objectCoverage"] = deepcopy(self.case.prepared["objectCoverage"])

    def source_rules(self, mode="BLANK"):
        operation_ids = list(self.f.version.steps.values_list("operation_id", flat=True))
        target_id = self.operation.pk
        manifest = {"contractVersion": daily.SOURCE_RULES_CONTRACT, "sourceSha256": "e" * 64,
            "productTypeCode": self.f.product_type.code, "effectiveDate": date.today().isoformat(),
            "applicableOperationIds": [value for value in operation_ids if value != target_id],
            "nonApplicableOperationIds": [target_id] if mode == "BLANK" else [],
            "auxiliaryOperationIds": [target_id] if mode == "AUXILIARY" else [],
            "preparationDays": "0.1", "transferDays": "0.1", "businessFactReference": "SIMULATED_FOR_TEST"}
        if mode in {"POSITIVE", "AUXILIARY"}:
            manifest["applicableOperationIds"].append(target_id)
        status = "MISSING" if mode == "MISSING" else "VALID"
        if mode == "MISSING":
            manifest = {}
        return {"status": status, "manifest": manifest,
            "fact": {"contractVersion": daily.SOURCE_RULES_CONTRACT, "status": status,
                "statusLabel": "SIMULATED_FOR_TEST controlled source matrix", "manifest": deepcopy(manifest)},
            "capacityRows": list(StandardCapacity.objects.filter(company=self.f.company,
                product_type=self.f.product_type).select_related("operation", "work_center", "product_type", "uom"))}

    def assess(self, *, actor=True, mode="BLANK", single=True, version=None):
        kwargs = {"bom_version": self.f.output.bom_version, "on_date": date.today(),
            "engineering_calculation": self.f.output.engineering_calculation,
            "engineering_document_version": self.f.output.engineering_document_version,
            "order_engineering_instance": self.f.output.order_engineering_instance,
            "order_engineering_baseline": self.f.output.order_engineering_baseline,
            "production_plan": self.plan, "manufacturing_output": self.f.output}
        if actor is not False:
            kwargs["user"] = self.user if actor is True else actor
        if single:
            kwargs["routing_step_id"] = self.step.pk
        before = self.f.full_database_snapshot()
        try:
            with patch.object(daily, "capacity_source_rules", return_value=self.source_rules(mode)):
                with CaptureQueriesContext(connection) as queries:
                    result = daily.DailyCapacityReadinessService.assess(version or self.f.version, **kwargs)
            self.assertFalse(any(row["sql"].lstrip().upper().startswith(
                ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")) for row in queries))
            return result
        finally:
            self.assertEqual(self.f.full_database_snapshot(), before)

    def target(self, result):
        return next(row for row in result["steps"] if row["stepId"] == self.step.pk)

    def confirm_zero(self):
        self.case.save_no_capacity_preparation()
        self.case.correct_capacity()
        current = self.case.read()
        self.assertEqual(current["capacityResolution"]["code"], "CONFIRMED_ZERO")
        self.assertTrue(current["capacityResolution"]["valid"])
        return current

    def assert_original_conflict(self, row):
        self.assertEqual(row["applicability"]["result"], "PENDING")
        self.assertIn("SOURCE_OBJECT_APPLICABILITY_CONFLICT", row["blockerCodes"])
        self.assertIn("ROUTING_STEP_APPLICABILITY_PENDING", row["blockerCodes"])
        self.assertFalse(row["capacitySemantics"].get("preparationRulingOnly", False))

    def test_real_non804_ruling_is_consumed_without_dropping_formal_input_gates(self):
        current = self.confirm_zero()
        self.assertNotEqual(self.step.pk, 804)
        self.assertNotEqual(self.operation.name, "拉丝/打磨")
        row = self.target(self.assess())
        source = row["preparationSourceRead"]
        self.assertEqual(row["applicability"]["result"], "REQUIRED")
        self.assertEqual(row["routingApplicability"]["result"], "REQUIRED")
        self.assertEqual(row["capacityDateMode"], daily.AUXILIARY_DATE_MODE)
        self.assertTrue(row["capacitySemantics"]["preparationRulingOnly"])
        self.assertEqual(row["capacitySemantics"]["meaningCode"], "NON_QUANTIFIED")
        self.assertEqual(row["inputPreparation"]["recordId"], current["recordId"])
        self.assertEqual(row["inputPreparation"]["revision"], 2)
        self.assertEqual(row["inputPreparation"]["exactScope"], self.case.scope)
        self.assertEqual(set(row["blockerCodes"]), {item["code"] for item in source["blockers"]})
        self.assertTrue({"OPERATION_RULE_MAPPING_MISSING", "OPERATION_REQUIREMENT_NOT_GENERATED",
            "PROCESS_DEMAND_PLAN_ALLOCATION_MISSING"} <= set(row["blockerCodes"]))
        self.assertFalse(row["planningReady"])
        self.assertFalse(row["capacityDemandEvaluated"])
        self.assertEqual(row["dailyCapacity"], [])
        self.assertEqual(row["capacities"], [])
        self.assertIsNone(row["preparationDays"])
        self.assertIsNone(row["transferDays"])
        self.assertNotIn("durationDays", row)
        self.assertFalse(source["inputPreparation"]["readyForGeneration"])
        self.assertFalse(source["inputPreparation"]["readyForAllocation"])
        self.assertFalse(source["inputPreparation"]["readyForScheduling"])
        self.assertEqual(row["sourceRulesFact"]["manifest"]["nonApplicableOperationIds"], [self.operation.pk])

    def test_no_actor_does_not_consume_ruling_and_other_steps_are_unchanged(self):
        self.confirm_zero()
        original = self.assess(actor=False, single=False)
        consumed = self.assess(single=False)
        self.assert_original_conflict(self.target(original))
        other_before = [row for row in original["steps"] if row["stepId"] != self.step.pk]
        other_after = [row for row in consumed["steps"] if row["stepId"] != self.step.pk]
        self.assertTrue(other_before)
        self.assertEqual(other_after, other_before)

    def test_native_revocation_preserves_original_conflict(self):
        self.confirm_zero()
        self.case.correct_capacity(confirmed_zero=False, revision=2, key="sim-withdraw-exact-zero")
        self.assertFalse(self.case.read()["capacityResolution"]["valid"])
        self.assert_original_conflict(self.target(self.assess()))

    def test_later_positive_capacity_conflict_prevents_zero_consumption(self):
        self.confirm_zero()
        self.f.make_capacity(self.operation, self.f.area, "SIM-ZERO-LATER-POSITIVE",
            measurement_status="measured", quantity=Decimal("7"))
        current = self.case.read()
        self.assertFalse(current["capacityResolution"]["valid"])
        self.assertEqual(current["capacitySemantics"]["conflictCode"], "CAPACITY_SOURCE_RULING_CONFLICT")
        self.assert_original_conflict(self.target(self.assess()))

    def test_saved_version_object_or_revision_tampering_is_rejected(self):
        self.confirm_zero()
        row = OperationInputPreparationDraft.objects.get()
        cases = (("routing_version_id", self.f.wrong_version.pk),
            ("object_coverage", json.dumps(row.object_coverage[:-1])), ("revision", row.revision + 1))
        for name, value in cases:
            with self.subTest(field=name):
                with transaction.atomic():
                    column = connection.ops.quote_name(row._meta.get_field(name).column)
                    table = connection.ops.quote_name(row._meta.db_table)
                    with connection.cursor() as cursor:
                        cursor.execute(f"UPDATE {table} SET {column}=%s WHERE id=%s", (value, row.pk))
                    with self.assertRaises(ProductionFoundationError):
                        self.assess()
                    transaction.set_rollback(True)

    def test_foreign_company_and_other_version_cannot_consume_saved_ruling(self):
        self.confirm_zero()
        foreign = Company.objects.create(code="SIM-ZERO-FOREIGN", name="SIMULATED_FOR_TEST zero consumption foreign company")
        outsider = User.objects.create_user(username="sim_zero_foreign", company_id=foreign.pk)
        with self.assertRaises(daily.DailyCapacityError):
            self.assess(actor=outsider)
        with self.assertRaises(daily.DailyCapacityError):
            self.assess(version=self.f.wrong_version)

    def test_existing_preparation_reader_permission_is_not_bypassed(self):
        self.confirm_zero()
        RolePermission.objects.filter(role=self.f.role, permission__code=preparation.VIEW).delete()
        with self.assertRaises((ProductionFoundationError, OperationRequirementError)) as caught:
            self.assess()
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")

    def test_pending_object_proof_is_not_restored_to_required_by_saved_zero(self):
        self.confirm_zero()
        record = RoutingStepObjectApplicability.objects.filter(
            production_plan=self.plan, routing_step=self.step).order_by("pk").first()
        # Deliberate isolated proof damage makes the real object resolver return
        # PENDING. The saved preparation itself remains present; no final
        # resolver/preparation/readiness return is mocked.
        table = connection.ops.quote_name(record._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET context_hash=%s WHERE id=%s", ("f" * 64, record.pk))
        row = self.target(self.assess())
        self.assertEqual(row["routingApplicability"]["result"], "PENDING")
        self.assertEqual(row["applicability"]["result"], "PENDING")
        self.assertIn("ROUTING_STEP_APPLICABILITY_PENDING", row["blockerCodes"])
        self.assertFalse(row["capacitySemantics"].get("preparationRulingOnly", False))
        self.assertNotIn("preparationSourceRead", row)
        self.assertTrue(OperationInputPreparationDraft.objects.exists())

    def test_real_whole_plan_consumer_passes_actor_and_preserves_preparation_blockers(self):
        current = self.confirm_zero()
        before = self.f.full_database_snapshot()
        with patch.object(daily, "capacity_source_rules", return_value=self.source_rules()):
            with CaptureQueriesContext(connection) as queries:
                result = daily.AllocatedLoadCapacityReadinessService.assess(
                    user=self.user, production_plan_id=self.plan.pk)
        self.assertEqual(self.f.full_database_snapshot(), before)
        self.assertFalse(any(row["sql"].lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")) for row in queries))
        inner = self.target(result["readiness"])
        outer = self.target(result)
        self.assertEqual(inner["inputPreparation"]["recordId"], current["recordId"])
        self.assertTrue(inner["capacitySemantics"]["preparationRulingOnly"])
        self.assertEqual(outer["inputPreparation"], inner["inputPreparation"])
        self.assertEqual(outer["preparationSourceRead"], inner["preparationSourceRead"])
        expected = {item["code"] for item in inner["preparationSourceRead"]["blockers"]}
        self.assertTrue(expected <= {item["code"] for item in outer["blockers"]})
        self.assertIn("OPERATION_RULE_MAPPING_MISSING", expected)
        self.assertFalse(result["noDateReady"])
        self.assertEqual(outer["capacityMatches"], [])
        self.assertIsNone(outer["processDemand"])

    def test_no_preparation_positive_blank_and_missing_matrix_keep_original_behavior(self):
        self.assertFalse(OperationInputPreparationDraft.objects.exists())
        for mode in ("POSITIVE", "BLANK", "MISSING"):
            with self.subTest(source=mode):
                original = self.assess(actor=False, mode=mode)
                current = self.assess(mode=mode)
                self.assertEqual(current, original)
                self.assertFalse(self.target(current)["capacitySemantics"].get("preparationRulingOnly", False))
                if mode == "BLANK":
                    self.assert_original_conflict(self.target(current))

    def test_manifest_auxiliary_zero_keeps_its_original_exemption(self):
        self.f.source_capacity.delete()
        self.f.make_capacity(self.operation, self.f.area, "SIM-MANIFEST-AUXILIARY-ZERO",
            measurement_status="zero_capacity", quantity=Decimal("0"),
            preparation_days=Decimal(".1"), transfer_days=Decimal(".1"))
        original = self.assess(actor=False, mode="AUXILIARY")
        current = self.assess(mode="AUXILIARY")
        self.assertEqual(current, original)
        row = self.target(current)
        self.assertEqual(row["capacityDateMode"], daily.AUXILIARY_DATE_MODE)
        self.assertNotIn("OPERATION_RULE_MAPPING_MISSING", row["blockerCodes"])
        self.assertFalse(row["capacitySemantics"].get("preparationRulingOnly", False))
        self.assertEqual(row["capacitySemantics"]["meaningCode"], "NON_QUANTIFIED")
