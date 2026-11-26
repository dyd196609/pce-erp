"""SIMULATED_FOR_TEST: native immutable object decisions in an isolated DB.

The shared fixture uses real completed source facts and a released output.
Neither source proofs, authorization nor the applicability resolver is mocked.
Explicit corruption below is limited to Django's disposable test database.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, Permission, RolePermission, User
from . import routing_object_applicability_service as service
from . import tests_calc4_routing_correction as source_fixture
from . import tests_plan_legal_extension_admission as plan_fixture
from .engineering_rule_foundation import specification_hash
from .models import RoutingStepObjectApplicability
from .routing_version_successor_service import ROUTING_PERMISSION, RoutingVersionChangeError


REASON = "SIMULATED_FOR_TEST object applicability"


def make_object_applicability_fixture(*, f=None, plan=None):
    """Reusable native three-object fixture; no setup executes at import time."""
    if f is None:
        f = source_fixture.Calc4RoutingCorrectionTests(methodName="runTest")
        f.setUp()
    permission, _ = Permission.objects.get_or_create(code=ROUTING_PERMISSION,
        defaults={"name": ROUTING_PERMISSION, "module": "PRODUCTION"})
    RolePermission.objects.get_or_create(role=f.role, permission=permission)
    if plan is None:
        plan = plan_fixture.PlanLegalExtensionAdmissionTests.make_plan(SimpleNamespace(f=f))
    contributions = []
    for obj in f.baseline_items:
        context = service.build_context(plan.pk, f.step.pk, obj.pk)
        fact = next(row for row in f.facts if row.trace["baselineItemId"] == obj.pk)
        proof = next(row for row in context["sourceProofs"] if row["id"] == fact.pk)
        basis = {"contractVersion": service.BASIS_CONTRACT_VERSION,
            "decisionReference": {"code": "SIMULATED_DECISION", "statement": "Authorized fixture decision",
                "reference": "SIMULATED_FOR_TEST", "referenceSha256": "a" * 64},
            "sourceFact": {"id": fact.pk, "sourceSnapshotHash": proof["sourceSnapshotHash"]},
            "rules": [{"id": f.producer.pk, "version": f.producer.version,
                "specificationHash": specification_hash(f.producer.specification)}],
            "execution": {"mode": "AUTHORIZED_CODEX_AGENT", "humanBusinessAcceptanceClaimed": False}}
        contributions.append({"baselineItemId": obj.pk, "decision": service.NOT_APPLICABLE,
            "contextHash": context["contextHash"], "idempotencyKey": context["suggestedIdempotencyKey"], "basis": basis})
    return SimpleNamespace(f=f, plan=plan, contributions=contributions)


class RoutingObjectApplicabilityServiceTests(TestCase):
    def setUp(self):
        self.fixture = make_object_applicability_fixture()
        self.f, self.plan = self.fixture.f, self.fixture.plan
        self.contributions = self.fixture.contributions

    def save(self, contributions=None, user=None):
        return service.confirm_group(user or self.f.user, self.plan.pk, self.f.step.pk,
            self.contributions if contributions is None else contributions, REASON)

    def read(self):
        return service.resolve_for_step(self.f.step, production_plan=self.plan,
            manufacturing_output=self.f.output, engineering_calculation=self.f.source_calc,
            order_engineering_instance=self.f.instance, order_engineering_baseline=self.f.baseline,
            bom_version=self.f.bom_version)

    def snapshot(self):
        return self.f.full_database_snapshot()

    def assert_no_write(self, action):
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = action()
        writes = [row["sql"] for row in queries if row["sql"].lstrip().split()[0].upper()
            in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}]
        self.assertEqual(writes, [])
        self.assertFalse(any("password" in row["sql"].lower() for row in queries),
            "Object applicability readers/replay must never fetch User credentials")
        self.assertEqual(self.snapshot(), before)
        return result

    def raw_fault(self, obj, field, value):
        column = obj._meta.get_field(field).column
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {connection.ops.quote_name(obj._meta.db_table)} "
                f"SET {connection.ops.quote_name(column)} = %s WHERE id = %s", [value, obj.pk])

    def test_native_group_four_table_writes_and_immutable_records(self):
        before = self.snapshot()
        result = self.save()
        self.assertEqual((result["createdCount"], result["replayedCount"]), (3, 0))
        rows = list(RoutingStepObjectApplicability.objects.order_by("baseline_item_id"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=service.ACTION).count(), 3)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=service.ACTION,
            status=MasterDataWriteRequest.Status.COMMITTED).count(), 3)
        self.assertEqual(ExternalIdentity.objects.filter(source_object_type=service.SOURCE_OBJECT_TYPE).count(), 3)
        after = self.snapshot()
        changed = {table for table in before if before[table] != after[table]}
        self.assertEqual(changed, {"pde_routing_step_object_applicability", "masterdata_external_identity",
            "masterdata_write_request", "system_organization_operating_audits"})
        payload = self.assert_no_write(self.read)
        self.assertEqual(payload["result"], service.NOT_APPLICABLE)
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["excludedBaselineItemIds"], sorted(row.baseline_item_id for row in rows))
        self.assertEqual(payload["excludedDesignItemIds"], sorted(row.design_item_id for row in rows))
        for row in rows:
            with self.assertRaises(ValidationError):
                row.save()
            with self.assertRaises(ValidationError):
                row.delete()
        for action in (lambda: RoutingStepObjectApplicability.objects.all().update(reason="overwrite"),
                       lambda: RoutingStepObjectApplicability.objects.all().delete(),
                       lambda: RoutingStepObjectApplicability.objects.bulk_update(rows, ["reason"]),
                       lambda: RoutingStepObjectApplicability.objects.bulk_create([])):
            with self.assertRaises(ValidationError):
                action()

    def test_exact_key_replay_zero_write_and_conflicting_alias_refused(self):
        first = self.save()
        replay = self.assert_no_write(self.save)
        self.assertEqual((replay["createdCount"], replay["replayedCount"]), (0, 3))
        self.assertEqual([r["recordId"] for r in first["objects"]], [r["recordId"] for r in replay["objects"]])
        self.assertTrue(all(row["idempotentReplay"] for row in replay["objects"]))
        for field, value in (("idempotencyKey", "SIMULATED_ALIAS"), ("decision", service.REQUIRED)):
            changed = deepcopy(self.contributions)
            changed[0][field] = value
            before = self.snapshot()
            with self.assertRaises(RoutingVersionChangeError):
                self.save(changed)
            self.assertEqual(self.snapshot(), before)

    def test_partial_group_unknown_then_exact_existing_recovery(self):
        self.save(self.contributions[:1])
        partial = self.assert_no_write(self.read)
        self.assertEqual(partial["result"], service.PENDING)
        self.assertFalse(partial["complete"])
        self.assertEqual(len(partial["excludedDesignItemIds"]), 1)
        self.assertEqual(len(partial["unknownDesignItemIds"]), 2)
        recovered = self.save()
        self.assertEqual((recovered["createdCount"], recovered["replayedCount"]), (2, 1))
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)

    def test_mixed_required_and_excluded_is_required(self):
        mixed = deepcopy(self.contributions)
        mixed[0]["decision"] = service.REQUIRED
        self.save(mixed)
        payload = self.assert_no_write(self.read)
        self.assertEqual(payload["result"], service.REQUIRED)
        self.assertTrue(payload["complete"])
        self.assertEqual(len(payload["requiredDesignItemIds"]), 1)
        self.assertEqual(len(payload["excludedDesignItemIds"]), 2)
        self.assertEqual(payload["unknownDesignItemIds"], [])

    def test_late_audit_failure_rolls_back_the_whole_group(self):
        original, calls = service._audit, []

        def fail_second(**kwargs):
            calls.append(kwargs["instance"].baseline_item_id)
            if len(calls) == 2:
                raise RuntimeError("SIMULATED_FOR_TEST injected second native audit failure")
            return original(**kwargs)

        before = self.snapshot()
        with patch.object(service, "_audit", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)

    def test_source_audit_and_committed_ledger_revalidated_on_new_reads(self):
        self.save()
        fact = self.f.facts[0]
        self.raw_fault(fact, "status", "inactive")
        invalid_source = self.assert_no_write(self.read)
        self.assertEqual(invalid_source["result"], service.PENDING)
        self.assertEqual(invalid_source["unknownDesignItemIds"], [fact.trace["designItemId"]])
        self.raw_fault(fact, "status", "active")
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)
        record = RoutingStepObjectApplicability.objects.get(baseline_item_id=fact.trace["baselineItemId"])
        audit = OrganizationOperatingAuditRecord.objects.get(action_code=service.ACTION, target_id=record.pk)
        self.raw_fault(audit, "reason", "SIMULATED_FOR_TEST conflicting audit")
        self.assertEqual(self.assert_no_write(self.read)["result"], service.PENDING)
        self.raw_fault(audit, "reason", REASON)
        ledger = record.write_request
        self.raw_fault(ledger, "status", MasterDataWriteRequest.Status.RESERVED)
        self.assertEqual(self.assert_no_write(self.read)["result"], service.PENDING)
        self.raw_fault(ledger, "status", MasterDataWriteRequest.Status.COMMITTED)
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)

    def test_current_hash_and_consumer_scope_drift_cannot_reuse_decisions(self):
        self.save()
        original = self.f.source_calc.input_hash
        self.raw_fault(self.f.source_calc, "input_hash", "b" * 64)
        payload = self.assert_no_write(self.read)
        self.assertEqual(payload["result"], service.PENDING)
        self.assertEqual(payload["excludedDesignItemIds"], [])
        self.raw_fault(self.f.source_calc, "input_hash", original)
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)
        wrong = self.assert_no_write(lambda: service.resolve_for_step(self.f.step, production_plan=self.plan,
            manufacturing_output=self.f.output, engineering_calculation=self.f.source_calc,
            order_engineering_baseline=self.f.baseline, bom_version=self.f.bom_version.pk + 10000))
        self.assertEqual(wrong["result"], service.PENDING)

    def test_audit_permission_organization_account_and_positive_chain_are_bound(self):
        self.save()
        record = RoutingStepObjectApplicability.objects.first()
        audit = OrganizationOperatingAuditRecord.objects.get(action_code=service.ACTION, target_id=record.pk)
        original_before, original_after = deepcopy(audit.before_snapshot), deepcopy(audit.after_snapshot)
        faults = (("authorization", "actionCode", "SIMULATED_WRONG_ACTION"),
            ("authorization", "organizationId", self.f.company.pk + 10000),
            ("authorization", "organizationId", True),
            ("authorization", "organizationId", "0" + str(self.f.company.pk)),
            ("executionChain", "account", "SIMULATED_DIFFERENT_ACTOR"),
            ("executionChain", "employeeId", 0),
            ("executionChain", "positionId", -1),
            ("executionChain", "responsibilityId", True))
        for section, field, value in faults:
            with self.subTest(section=section, field=field):
                before, after = deepcopy(original_before), deepcopy(original_after)
                # Corrupt both envelopes consistently so rejection proves the
                # native permission/actor guard, not only envelope inequality.
                before[section][field] = after[section][field] = value
                self.raw_fault(audit, "before_snapshot", json.dumps(before))
                self.raw_fault(audit, "after_snapshot", json.dumps(after))
                payload = self.assert_no_write(self.read)
                self.assertEqual(payload["result"], service.PENDING)
                self.assertEqual(payload["unknownDesignItemIds"], [record.design_item_id])
                self.assertEqual(payload["reasons"][0]["code"], "OBJECT_APPLICABILITY_AUDIT_MISMATCH")
                snapshot = self.snapshot()
                with self.assertRaises(RoutingVersionChangeError) as caught:
                    self.save()
                self.assertEqual(caught.exception.code, "OBJECT_APPLICABILITY_AUDIT_MISMATCH")
                self.assertEqual(self.snapshot(), snapshot)
                self.raw_fault(audit, "before_snapshot", json.dumps(original_before))
                self.raw_fault(audit, "after_snapshot", json.dumps(original_after))
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)

    def test_native_authorization_decimal_string_and_integer_are_both_exact(self):
        self.save()
        record = RoutingStepObjectApplicability.objects.first()
        audit = OrganizationOperatingAuditRecord.objects.get(action_code=service.ACTION, target_id=record.pk)
        self.assertEqual(audit.after_snapshot["authorization"]["organizationId"], str(self.f.company.pk))
        original_before, original_after = deepcopy(audit.before_snapshot), deepcopy(audit.after_snapshot)
        for value in (self.f.company.pk, str(self.f.company.pk)):
            before, after = deepcopy(original_before), deepcopy(original_after)
            before["authorization"]["organizationId"] = after["authorization"]["organizationId"] = value
            self.raw_fault(audit, "before_snapshot", json.dumps(before))
            self.raw_fault(audit, "after_snapshot", json.dumps(after))
            self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)
            replay = self.assert_no_write(self.save)
            self.assertEqual((replay["createdCount"], replay["replayedCount"]), (0, 3))
        for value in (True, False, "", "0" + str(self.f.company.pk), " " + str(self.f.company.pk),
                      "+" + str(self.f.company.pk), str(self.f.company.pk) + ".0", None):
            self.assertFalse(service._organization_matches(value, self.f.company.pk))

    def test_native_record_identity_and_hash_boundaries_reject_each_drift(self):
        self.save()
        record = RoutingStepObjectApplicability.objects.first()
        other = next(obj for obj in self.f.baseline_items if obj.pk != record.baseline_item_id)
        foreign = Company.objects.create(code="SIM-OBJECT-DRIFT", name="SIMULATED_FOR_TEST object drift company")
        faults = (("company", foreign.pk),
            ("production_plan", self.plan.pk + 10000),
            ("manufacturing_output", self.f.output.pk + 10000),
            ("main_calculation", self.f.source_calc.pk + 10000),
            ("engineering_baseline", self.f.baseline.pk + 10000),
            ("routing_version", self.f.wrong_version.pk),
            ("routing_step", self.f.wrong_step.pk),
            ("baseline_item", other.pk), ("design_item", other.design_item_id),
            ("source_record", self.f.source.pk + 10000),
            ("source_version", "SIM-OTHER-SOURCE-VERSION"),
            ("source_content_hash", "d" * 64), ("baseline_snapshot_hash", "e" * 64),
            ("object_content_hash", "f" * 64), ("calculation_input_hash", "1" * 64),
            ("calculation_rule_graph_hash", "2" * 64), ("calculation_result_hash", "3" * 64),
            ("context_hash", "4" * 64))
        for field, changed in faults:
            with self.subTest(field=field):
                original = getattr(record, record._meta.get_field(field).attname)
                self.assertNotEqual(changed, original)
                # Deliberate raw faults exist only in the disposable test DB.
                # Deferred FK faults are always restored before test teardown.
                self.raw_fault(record, field, changed)
                try:
                    payload = self.assert_no_write(self.read)
                    self.assertIsNotNone(payload)
                    self.assertEqual(payload["result"], service.PENDING)
                    self.assertFalse(payload["complete"])
                finally:
                    self.raw_fault(record, field, original)
                self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)
        self.assertIsNone(self.assert_no_write(lambda: service.resolve_for_step(
            self.f.step, production_plan=self.plan.pk + 10000, manufacturing_output=self.f.output)))
        self.assertIsNone(self.assert_no_write(lambda: service.resolve_for_step(
            self.f.wrong_step, production_plan=self.plan, manufacturing_output=self.f.output)))
        wrong_version_step = deepcopy(self.f.step)
        wrong_version_step.routing_version_id = self.f.wrong_version.pk
        wrong = self.assert_no_write(lambda: service.resolve_for_step(wrong_version_step,
            production_plan=self.plan, manufacturing_output=self.f.output))
        self.assertEqual(wrong["result"], service.PENDING)
        self.assertEqual(wrong["excludedDesignItemIds"], [])
        self.assertEqual(self.assert_no_write(self.read)["result"], service.NOT_APPLICABLE)

    def test_no_context_no_record_and_unauthorized_writes_preserve_old_contract(self):
        self.assertIsNone(self.assert_no_write(lambda: service.resolve_for_step(self.f.step)))
        self.assertIsNone(self.assert_no_write(self.read))
        foreign = Company.objects.create(code="SIM-OBJECT-OTHER", name="SIMULATED_FOR_TEST other object company")
        user = User.objects.create_user(username="sim_object_other", company_id=foreign.pk)
        before = self.snapshot()
        with self.assertRaises(RoutingVersionChangeError):
            self.save(user=user)
        self.assertEqual(self.snapshot(), before)
        broken = deepcopy(self.contributions)
        broken[-1]["basis"]["sourceFact"]["sourceSnapshotHash"] = "c" * 64
        with self.assertRaises(RoutingVersionChangeError):
            self.save(broken)
        self.assertEqual(self.snapshot(), before)
