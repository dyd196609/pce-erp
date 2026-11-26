"""SIMULATED_FOR_TEST: exact-plan preparation, using real native fixtures.

Execute only with this task's guarded disposable SQLite runner. Corruption and
conflict cases never connect to the acceptance database. Fixture builders are
composed rather than inherited, so old generation/allocation tests are not run.
"""
from copy import deepcopy
from datetime import date
import hashlib
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, Permission, RolePermission, User
from workflow_runtime.models import BusinessStateTransition
from . import operation_input_preparation_service as service
from . import operation_workload_source_service as workload
from . import operation_requirement_service as requirements
from .models import OperationInputPreparationDraft, StandardCapacity
from .production_foundation_service import ProductionFoundationError
from . import tests_operation_workload_source_service as source_fixtures
from .views import ProductionFoundationA1View


class OperationInputPreparationTests(TestCase):
    def setUp(self):
        self.case = source_fixtures.OperationWorkloadSourceTests(methodName="runTest")
        self.case.setUp()
        self.f, self.plan = self.case.f, self.case.plan
        self.user, self.step, self.operation = self.f.user, self.case.step, self.case.operation
        for code in ("production.engineering.rule.create", "production.engineering.rule.update_draft",
                "production.master_data.capacity.maintain", "production.engineering.rule.view"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.scope = {"companyId": self.f.company.pk, "productionPlanId": self.plan.pk,
            "manufacturingOutputId": self.f.output.pk, "mainCalculationId": self.f.source_calc.pk,
            "salesOrderItemId": self.f.item.pk, "baselineId": self.f.baseline.pk,
            "routingVersionId": self.f.version.pk, "routingStepId": self.step.pk,
            "operationId": self.operation.pk, "productTypeId": self.f.product_type.pk}
        self.prepared = self.read()
        self.basis = {"contractVersion": "PCE-OPERATION-INPUT-PREPARATION-BASIS-V1", "entries": [{
            "reference": "SIMULATED_FOR_TEST/user-answer/804", "referenceSha256": hashlib.sha256(b"SIMULATED_FOR_TEST/user-answer/804").hexdigest(),
            "exactStatement": "投入标准待确认；产能尚未测定；来源、投入数量及产能数量未知。",
            "scope": deepcopy(self.scope), "objectCoverage": deepcopy(self.prepared["objectCoverage"])}]}
        self.factory = APIRequestFactory()

    def snapshot(self):
        return self.f.full_database_snapshot()

    def read(self, **overrides):
        return service.read_preparation(user=overrides.get("user", self.user),
            exact_scope=overrides.get("exact_scope", self.scope))

    def save(self, **overrides):
        args = {"user": self.user, "exact_scope": deepcopy(self.scope), "draft_selection": None,
            "business_basis": deepcopy(self.basis), "idempotency_key": "sim-preparation-one",
            "expected_revision": None, "expected_context_hash": self.prepared["contextHash"],
            "reason": "SIMULATED_FOR_TEST exact engineering preparation"}
        args.update(overrides)
        return service.save_preparation(**args)

    def rejected(self, action, code=None, *, exception=ProductionFoundationError):
        before = self.snapshot()
        with self.assertRaises(exception) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.snapshot(), before)
        return caught.exception

    def request(self, method, payload, *, user=None):
        request = getattr(self.factory, method)("/api/pde/a1-foundation/operations/", payload,
            **({"format": "json"} if method == "post" else {}))
        force_authenticate(request, user=user or self.user)
        return ProductionFoundationA1View.as_view()(request, entity="operations")

    def post_payload(self, **overrides):
        data = {"action": "saveOperationInputPreparation", "exactScope": deepcopy(self.scope),
            "draftSelection": None, "businessBasis": deepcopy(self.basis),
            "idempotencyKey": "sim-preparation-http", "expectedRevision": None,
            "expectedContextHash": self.prepared["contextHash"], "reason": "SIMULATED_FOR_TEST HTTP preparation"}
        data.update(overrides)
        return data

    def test_absence_is_not_recorded_and_read_is_zero_write(self):
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = self.read()
        self.assertEqual(result["recordStatus"], "NOT_RECORDED")
        self.assertIsNone(result["recordId"])
        self.assertIsNone(result.get("capacityMeasurementStatus"))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))

    def test_absent_preparation_does_not_add_its_stricter_quantity_gate_to_old_reader(self):
        original = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        self.assertIsNone(original["inputPreparation"])
        requirement = self.plan.planning_requirement
        requirement.net_required_qty -= 1
        requirement.save(update_fields=("net_required_qty",))
        # This quantity drift is forbidden for preparation, while the existing
        # source reader still shows the same missing source/demand/load facts.
        self.rejected(self.read)
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        self.assertEqual(result, original)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))

    def test_absent_preparation_does_not_add_rule_view_permission_to_old_reader(self):
        original = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        RolePermission.objects.filter(role=self.f.role, permission__code="production.engineering.rule.view").delete()
        self.rejected(self.read, "PERMISSION_DENIED")
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        self.assertEqual(result, original)
        self.assertIsNone(result["inputPreparation"])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))

    def test_existing_preparation_fk_drift_cannot_be_filtered_into_absence(self):
        self.save()
        row = OperationInputPreparationDraft.objects.get()
        table = connection.ops.quote_name(row._meta.db_table)
        # A valid alternative formal FK keeps SQL integrity, but does not belong
        # to this row's step. Both readers must expose the broken proof.
        self.assertNotEqual(self.f.op_area.pk, self.operation.pk)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET operation_id=%s WHERE id=%s", (self.f.op_area.pk, row.pk))
        self.rejected(self.read, "PREPARATION_CONTEXT_DRIFT")
        self.rejected(lambda: workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk,
            routing_step_id=self.step.pk), "PREPARATION_CONTEXT_DRIFT")

    def test_missing_selections_save_real_row_with_native_support_and_preserve_old_tables(self):
        before = self.snapshot()
        counts = {m: m.objects.count() for m in (ExternalIdentity, MasterDataWriteRequest,
            OrganizationOperatingAuditRecord, BusinessStateTransition)}
        self.save()
        row = OperationInputPreparationDraft.objects.get()
        self.assertEqual((row.status, row.input_standard_status, row.capacity_measurement_status),
            ("draft", "PENDING_CONFIRMATION", "UNMEASURED"))
        self.assertEqual(row.business_basis, self.basis)
        self.assertIsNone(row.draft_selection)
        self.assertEqual((row.producer_rule_id, row.manufacturing_mode_id, row.work_center_id, row.standard_capacity_id),
            (None, None, None, None))
        self.assertEqual(row.object_coverage, self.prepared["objectCoverage"])
        self.assertEqual((row.created_by_id, row.updated_by_id, row.revision), (self.user.pk, self.user.pk, 1))
        request = row.creation_write_request
        self.assertEqual(request.status, "COMMITTED")
        self.assertEqual(request.target_entity_id, str(row.pk))
        self.assertEqual(request.source_identity.mapping_status, "MATCH")
        self.assertEqual(request.source_identity.target_entity_id, str(row.pk))
        transitions = BusinessStateTransition.objects.filter(object_type="OperationInputPreparationDraft", object_id=row.pk)
        self.assertEqual(transitions.count(), 1)
        transition = transitions.get()
        self.assertEqual((transition.source_state, transition.target_state, transition.operator_id), ("", "draft", self.user.pk))
        audit_id = int(transition.audit_reference.rsplit(":", 1)[1])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
        self.assertEqual((audit.actor_id, audit.target_type, audit.target_id),
            (self.user.pk, "OperationInputPreparationDraft", row.pk))
        for model, count in counts.items():
            self.assertEqual(model.objects.count(), count + 1, model.__name__)
        after = self.snapshot()
        allowed = {m._meta.db_table for m in (*counts, OperationInputPreparationDraft)}
        self.assertEqual({table for table in before if before[table] != after[table]}, allowed)

    def test_audit_failure_rolls_back_draft_identity_ledger_and_initial_state(self):
        with patch.object(service, "_audit", side_effect=RuntimeError("SIMULATED_FOR_TEST injected audit failure")):
            self.rejected(self.save, exception=RuntimeError)
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_initial_state_failure_after_audit_rolls_back_entire_write_set(self):
        with patch.object(service, "record_projected_business_transition",
                side_effect=RuntimeError("SIMULATED_FOR_TEST injected state failure")):
            self.rejected(self.save, exception=RuntimeError)
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 0)

    def test_same_key_same_payload_replay_has_zero_sql_business_writes(self):
        first = self.save()
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            replay = self.save()
        for field in ("recordId", "contextHash", "contentHash", "revision", "writeRequestId", "sourceIdentityId", "auditId"):
            self.assertEqual(replay[field], first[field])
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual((replay["businessWriteCount"], replay["auditWriteCount"],
            replay["stateTransitionWriteCount"], replay["supportWriteCount"]), (0, 0, 0, 0))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))

    def test_same_key_changed_payload_is_rejected_with_zero_commit(self):
        self.save()
        self.rejected(lambda: self.save(reason="SIMULATED_FOR_TEST changed payload"), "PREPARATION_IDEMPOTENCY_CONFLICT")

    def test_same_scope_new_key_cannot_create_alias_draft(self):
        self.save()
        self.rejected(lambda: self.save(idempotency_key="sim-preparation-another-key"), "PREPARATION_REVISION_CONFLICT")
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 1)

    def test_revision_update_requires_current_version_and_preserves_original_basis(self):
        self.save()
        initial = OperationInputPreparationDraft.objects.get()
        initial_transition_count = BusinessStateTransition.objects.count()
        identity_before = list(ExternalIdentity.objects.order_by("pk").values())
        self.save(idempotency_key="sim-preparation-update", expected_revision=1, work_center_id=self.f.center.pk)
        row = OperationInputPreparationDraft.objects.get()
        self.assertEqual(row.pk, initial.pk)
        self.assertEqual(row.revision, 2)
        self.assertEqual(row.work_center_id, self.f.center.pk)
        self.assertEqual(row.business_basis, self.basis)
        self.assertEqual(BusinessStateTransition.objects.count(), initial_transition_count)
        self.assertEqual(list(ExternalIdentity.objects.order_by("pk").values()), identity_before)
        self.rejected(lambda: self.save(idempotency_key="sim-preparation-stale", expected_revision=1), "PREPARATION_REVISION_CONFLICT")

    def test_original_basis_cannot_be_replaced_deleted_or_rewritten(self):
        self.save()
        for mutate in (lambda value: value["entries"].clear(),
                lambda value: value["entries"][0].update(exactStatement="Changed original answer"),
                lambda value: value["entries"][0].update(referenceSha256="a" * 64)):
            basis = deepcopy(self.basis)
            mutate(basis)
            self.rejected(lambda: self.save(idempotency_key="sim-basis-rewrite", expected_revision=1,
                business_basis=basis))
        self.assertEqual(OperationInputPreparationDraft.objects.get().business_basis, self.basis)

    def test_original_basis_can_only_be_appended_under_same_exact_scope(self):
        self.save()
        basis = deepcopy(self.basis)
        entry = deepcopy(basis["entries"][0])
        entry.update(reference="SIMULATED_FOR_TEST/addendum", referenceSha256="b" * 64,
            exactStatement="来源仍待确认，未取得产能实测记录。")
        basis["entries"].append(entry)
        self.save(idempotency_key="sim-basis-append", expected_revision=1, business_basis=basis)
        self.assertEqual(OperationInputPreparationDraft.objects.get().business_basis, basis)

    def test_context_hash_and_each_supplied_scope_identity_are_verified(self):
        self.rejected(lambda: self.save(expected_context_hash="0" * 64), "PREPARATION_CONTEXT_DRIFT")
        for field in self.scope:
            with self.subTest(field=field):
                wrong = {**self.scope, field: self.scope[field] + 10000}
                self.rejected(lambda: self.save(exact_scope=wrong))

    def test_basis_object_set_hash_and_scope_are_not_client_summaries(self):
        cases = []
        missing = deepcopy(self.basis)
        missing["entries"][0]["objectCoverage"].pop()
        cases.append(missing)
        changed = deepcopy(self.basis)
        changed["entries"][0]["objectCoverage"][0]["objectContentHash"] = "0" * 64
        cases.append(changed)
        wrong = deepcopy(self.basis)
        wrong["entries"][0]["scope"]["salesOrderItemId"] += 10000
        cases.append(wrong)
        for basis in cases:
            with self.subTest(basis=basis):
                self.rejected(lambda: self.save(business_basis=basis), "PREPARATION_BASIS_INVALID")

    def test_persisted_source_hash_drift_blocks_read_and_replay_without_new_writes(self):
        self.save()
        self.f.source.content_hash = "a" * 64
        self.f.source.save(update_fields=("content_hash",))
        self.rejected(self.read)
        self.rejected(self.save)

    def test_object_snapshot_drift_blocks_save_without_new_support_rows(self):
        obj = self.f.baseline_items[0]
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pde_order_engineering_baseline_item SET content_hash=%s WHERE id=%s", ("c" * 64, obj.pk))
        self.rejected(self.save)

    def test_permission_company_and_real_employee_chain_remain_mandatory(self):
        denied = User.objects.create_user(username="sim_preparation_denied", company_id=self.f.company.pk)
        self.rejected(lambda: self.save(user=denied), "PERMISSION_DENIED")
        admin = User.objects.create_superuser(username="sim_preparation_admin", company_id=self.f.company.pk)
        self.rejected(lambda: self.save(user=admin), "FORMAL_EXECUTION_CHAIN_REQUIRED")
        foreign = Company.objects.create(code="SIM-PREPARATION-FOREIGN", name="SIMULATED_FOR_TEST foreign scope")
        wrong = {**self.scope, "companyId": foreign.pk}
        self.rejected(lambda: self.save(exact_scope=wrong))

    def test_capacity_maintain_permission_is_required_in_addition_to_rule_create(self):
        RolePermission.objects.filter(role=self.f.role, permission__code="production.master_data.capacity.maintain").delete()
        self.rejected(self.save, "PERMISSION_DENIED")

    def test_update_requires_its_existing_dedicated_permission(self):
        self.save()
        RolePermission.objects.filter(role=self.f.role, permission__code="production.engineering.rule.update_draft").delete()
        self.rejected(lambda: self.save(idempotency_key="sim-update-denied", expected_revision=1), "PERMISSION_DENIED")

    def test_partial_formal_directory_selections_preserve_unknown_quantity(self):
        self.save(producer_rule_id=self.case.producer.pk, manufacturing_mode_id=self.f.mode.pk,
            work_center_id=self.f.center.pk, draft_selection={"expression": "source_quantity / 2"})
        row = OperationInputPreparationDraft.objects.get()
        self.assertEqual(row.producer_rule_id, self.case.producer.pk)
        self.assertIsNone(row.standard_capacity_id)
        read = self.read()
        self.assertIsNone(read.get("inputQuantity"))
        self.assertIsNone(read.get("capacityQuantity"))
        self.assertIsNone(read["capacityMeasurementStatus"])
        self.assertEqual(read["legacyCapacityMeasurementStatus"], "UNMEASURED")
        self.assertFalse(read["capacitySemantics"]["valid"])

    def test_selected_producer_version_drift_is_not_silently_adopted(self):
        self.save(producer_rule_id=self.case.producer.pk)
        table = connection.ops.quote_name(self.case.producer._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET version=%s WHERE id=%s", ("SIM-DRIFTED", self.case.producer.pk))
        self.rejected(self.read)

    def test_selected_mode_version_drift_is_not_silently_adopted(self):
        self.save(manufacturing_mode_id=self.f.mode.pk)
        table = connection.ops.quote_name(self.f.mode._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET version=%s WHERE id=%s", ("SIM-DRIFTED", self.f.mode.pk))
        self.rejected(self.read)

    def test_selected_resource_content_drift_is_not_silently_adopted(self):
        self.save(work_center_id=self.f.center.pk)
        table = connection.ops.quote_name(self.f.center._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET name=%s WHERE id=%s", ("SIMULATED_FOR_TEST changed resource", self.f.center.pk))
        self.rejected(self.read)

    def test_invalid_catalog_options_unsafe_expression_and_unknown_fields_are_rejected(self):
        for values in ({"producer_rule_id": 999999}, {"producer_rule_id": self.f.correct_rule.pk},
                {"manufacturing_mode_id": 999999}, {"work_center_id": 999999},
                {"draft_selection": {"basisUomId": 999999}},
                {"draft_selection": {"expression": "__import__('os').system('anything')"}},
                {"draft_selection": {"expression": "different_alias + 1"}},
                {"draft_selection": {"arbitrarySource": "free text"}},
                {"draft_selection": {"basisQuantity": "-1"}},
                {"draft_selection": {"quantityBasis": "PER_BASIS_QUANTITY", "basisUomId": self.f.area.pk}}):
            with self.subTest(values=values):
                self.rejected(lambda: self.save(**values))

    def test_legacy_unmeasured_does_not_become_a_current_fourth_capacity_meaning(self):
        self.assertEqual(self.read()["recordStatus"], "NOT_RECORDED")
        self.rejected(lambda: self.save(standard_capacity_id=self.f.source_capacity.pk),
            "PREPARATION_UNMEASURED_CAPACITY_CONFLICT")
        for status, quantity, suffix in (("zero_capacity", 0, "ZERO"), ("not_determinable", None, "UNDETERMINABLE")):
            capacity = self.f.make_capacity(self.operation, self.f.area, "SIM-PREPARATION-" + suffix,
                measurement_status=status, quantity=quantity)
            self.rejected(lambda: self.save(standard_capacity_id=capacity.pk), "PREPARATION_UNMEASURED_CAPACITY_CONFLICT")
        before = StandardCapacity.objects.count()
        self.save()
        self.assertEqual(StandardCapacity.objects.count(), before)
        read = self.read()
        self.assertIsNone(read["capacityMeasurementStatus"])
        self.assertEqual(read["legacyCapacityMeasurementStatus"], "UNMEASURED")
        self.assertFalse(read["capacityResolution"]["valid"])
        self.assertIsNone(read["capacitySemantics"]["meaningCode"])
        self.assertIsNone(read.get("capacityQuantity"))
        self.assertNotEqual(read["capacityMeasurementStatus"], "zero_capacity")
        self.assertNotEqual(read["capacityMeasurementStatus"], "not_determinable")

    def test_model_instance_queryset_bulk_and_delete_bypasses_are_blocked(self):
        self.save()
        row = OperationInputPreparationDraft.objects.get()
        actions = (lambda: row.save(), lambda: row.delete(),
            lambda: OperationInputPreparationDraft.objects.filter(pk=row.pk).update(revision=9),
            lambda: OperationInputPreparationDraft.objects.all().delete(),
            lambda: OperationInputPreparationDraft.objects.bulk_update([row], ["revision"]),
            lambda: OperationInputPreparationDraft.objects.bulk_create([row]))
        for action in actions:
            self.rejected(action, exception=ValidationError)

    def test_database_scope_uniqueness_cannot_be_bypassed_by_new_context_digest(self):
        self.save()
        table = connection.ops.quote_name(OperationInputPreparationDraft._meta.db_table)
        fields = [field for field in OperationInputPreparationDraft._meta.local_fields if not field.primary_key]
        names = ", ".join(connection.ops.quote_name(field.column) for field in fields)
        select = ", ".join("%s" if field.name in {"context_hash", "creation_write_request"} else connection.ops.quote_name(field.column)
            for field in fields)
        row = OperationInputPreparationDraft.objects.get()
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, OperationInputPreparationDraft._meta.db_table)
        real = constraints["pde_opprep_real_scope_uniq"]
        self.assertTrue(real["unique"])
        self.assertEqual(set(real["columns"]), {"company_id", "operation_id", "product_type_id", "production_plan_id",
            "manufacturing_output_id", "main_calculation_id", "engineering_baseline_id", "routing_version_id", "routing_step_id"})
        before = self.snapshot()
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            ledger = MasterDataWriteRequest.objects.get(pk=row.creation_write_request_id)
            ledger.pk = None
            ledger.idempotency_key = "SIMULATED_FOR_TEST duplicate-scope-only"
            ledger.save(force_insert=True)
            with connection.cursor() as cursor:
                cursor.execute(f"INSERT INTO {table} ({names}) SELECT {select} FROM {table} WHERE id=%s",
                    ("d" * 64, ledger.pk, row.pk))
        self.assertIn("company_id", str(caught.exception))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 1)

    def test_initial_state_or_audit_history_missing_blocks_native_read(self):
        self.save()
        row = OperationInputPreparationDraft.objects.get()
        BusinessStateTransition.objects.filter(object_type="OperationInputPreparationDraft", object_id=row.pk).delete()
        self.rejected(self.read, "PREPARATION_HISTORY_INVALID")

    def test_uncommitted_ledger_blocks_native_read_without_repair_writes(self):
        self.save()
        row = OperationInputPreparationDraft.objects.get()
        request = row.creation_write_request
        request.status = "RESERVED"
        request.save(update_fields=("status",))
        self.rejected(self.read, "PREPARATION_HISTORY_INVALID")

    def test_saved_preparation_keeps_rule_matching_demand_load_duration_and_dates_blocked(self):
        from .daily_capacity_service import AllocatedLoadCapacityReadinessService
        from .daily_capacity_views import production_plan_date_preview
        before = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        capacity_before = AllocatedLoadCapacityReadinessService.assess(user=self.user, production_plan_id=self.plan.pk)
        dates_before = production_plan_date_preview(self.plan, start_date=date.today(), company_id=self.f.company.pk)
        self.save()
        saved = self.snapshot()
        with (patch.object(requirements.OperationRequirementService, "generate", side_effect=AssertionError("must not generate")),
                patch.object(requirements.OperationRequirementService, "allocate", side_effect=AssertionError("must not allocate"))):
            after = workload.read_for_plan(user=self.user, production_plan_id=self.plan.pk, routing_step_id=self.step.pk)
        for key in ("sourceConfiguration", "sourceCandidates", "formalRequirements", "savedAllocations"):
            self.assertEqual(after[key], before[key], key)
        self.assertFalse(after["sourceConfiguration"]["hasValidSourceConfiguration"])
        self.assertEqual(after["formalRequirements"]["items"], [])
        self.assertIsNone(after["savedAllocations"]["quantity"])
        self.assertEqual(after["inputPreparation"]["recordStatus"], "RECORDED")
        capacity_after = AllocatedLoadCapacityReadinessService.assess(user=self.user, production_plan_id=self.plan.pk)
        dates_after = production_plan_date_preview(self.plan, start_date=date.today(), company_id=self.f.company.pk)
        self.assertEqual(capacity_after, capacity_before)
        self.assertFalse(capacity_after["noDateReady"])
        self.assertEqual(dates_after, dates_before)
        self.assertFalse(dates_after["previewReady"])
        self.assertEqual(dates_after["dates"], [])
        self.assertEqual(self.snapshot(), saved)

    def test_existing_http_action_saves_then_get_returns_same_authority_with_zero_writes(self):
        response = self.request("post", self.post_payload())
        self.assertEqual(response.status_code, 200, response.data)
        row = OperationInputPreparationDraft.objects.get()
        before = self.snapshot()
        response = self.request("get", {"action": "operationWorkloadSources", "operationId": self.operation.pk,
            "productionPlanId": self.plan.pk, "routingStepId": self.step.pk})
        self.assertEqual(response.status_code, 200, response.data)
        read = response.data["context"]["inputPreparation"]
        self.assertEqual(read, self.read())
        self.assertEqual(read["recordStatus"], "RECORDED")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(OperationInputPreparationDraft.objects.count(), 1)
        self.assertEqual(row.pk, OperationInputPreparationDraft.objects.get().pk)

    def test_existing_http_action_preserves_native_context_conflict_and_permission_errors(self):
        response = self.request("post", self.post_payload(expectedContextHash="f" * 64))
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "PREPARATION_CONTEXT_DRIFT")
        denied = User.objects.create_user(username="sim_preparation_http_denied", company_id=self.f.company.pk)
        denied_before = self.snapshot()
        response = self.request("post", self.post_payload(), user=denied)
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")
        self.assertEqual(self.snapshot(), denied_before)

    def ruling_basis(self, *, confirmed_zero=True):
        current = self.read()
        source = {'contractVersion': service.CAPACITY_SOURCE_PROOF_CONTRACT,
            'sourcePath': 'SIMULATED_FOR_TEST/original-capacity.xlsx', 'sourceSha256': 'a' * 64,
            'sheetName': '标准产能', 'sourceCell': 'F12',
            'productTypeCode': self.f.product_type.code, 'processName': self.operation.name,
            'rawValue': None, 'rawValueKind': 'BLANK', 'currentApplicability': 'REQUIRED',
            'evidenceReference': 'SIMULATED_FOR_TEST/read-only-source-proof.json', 'evidenceSha256': 'b' * 64}
        return service.build_capacity_ruling_basis(current_preparation=current,
            reference='SIMULATED_FOR_TEST/latest-exact-user-ruling', reference_sha256='c' * 64,
            exact_statement='确认本次工序按0语义承接' if confirmed_zero else '撤销原未测表述，当前三态依据仍冲突',
            reason='SIMULATED_FOR_TEST exact scope correction; preserve raw blank',
            source_proof=source, confirmed_zero=confirmed_zero)

    def correct_capacity(self, *, confirmed_zero=True, basis=None, revision=1, key='sim-tristate-correction'):
        return self.save(business_basis=basis or self.ruling_basis(confirmed_zero=confirmed_zero),
            expected_revision=revision, idempotency_key=key)

    def save_no_capacity_preparation(self):
        # The shared fixture has an unused positive capacity for publication
        # tests. The customer's 804 case has no SC: prepare that isolated case
        # before taking the correction's protected database baseline.
        self.f.source_capacity.delete()
        return self.save()

    def test_typed_zero_correction_updates_same_row_and_only_native_revision_support(self):
        self.save_no_capacity_preparation()
        before = self.snapshot()
        identity_before = list(ExternalIdentity.objects.order_by('pk').values())
        bst_before = list(BusinessStateTransition.objects.order_by('pk').values())
        old_basis = deepcopy(self.read()['businessBasis'])
        row_before = OperationInputPreparationDraft.objects.get()
        result = self.correct_capacity()
        row = OperationInputPreparationDraft.objects.get()
        read = self.read()
        self.assertEqual((row.pk, row.revision, row.creation_write_request_id),
            (row_before.pk, 2, row_before.creation_write_request_id))
        self.assertEqual(row.capacity_measurement_status, 'UNMEASURED')
        self.assertEqual(read['legacyCapacityMeasurementStatus'], 'UNMEASURED')
        self.assertEqual((read['capacityMeasurementStatus'], read['capacityBusinessValue']), ('zero_capacity', 0))
        self.assertTrue(read['capacityResolution']['valid'])
        self.assertTrue(read['capacityResolution']['originalConclusionRevoked'])
        self.assertFalse(read['capacityResolution']['formalStandardCapacityPresent'])
        self.assertEqual(read['capacitySemantics']['meaningCode'], 'NON_QUANTIFIED')
        self.assertEqual(read['capacitySemantics']['statusLabel'], '经过但无法准确核算，不计定量产能占用')
        self.assertFalse(read['capacitySemantics']['quantitativeOccupancyAllowed'])
        self.assertFalse(read['capacitySemantics']['independentDurationAllowed'])
        self.assertTrue(read['capacitySemantics']['passesOperation'])
        self.assertEqual(row.business_basis['entries'][:len(old_basis['entries'])], old_basis['entries'])
        ruling = row.business_basis['entries'][-1]['capacityRuling']
        self.assertEqual((ruling['rulingType'], ruling['supersedesRevision']), ('CONFIRM_ZERO', 1))
        self.assertIsNone(ruling['sourceProof']['rawValue'])
        self.assertEqual(ruling['sourceProof']['rawValueKind'], 'BLANK')
        self.assertEqual(list(ExternalIdentity.objects.order_by('pk').values()), identity_before)
        self.assertEqual(list(BusinessStateTransition.objects.order_by('pk').values()), bst_before)
        after = self.snapshot()
        self.assertEqual({name for name in before if before[name] != after[name]}, {
            row._meta.db_table, MasterDataWriteRequest._meta.db_table, OrganizationOperatingAuditRecord._meta.db_table})
        self.assertEqual((result['businessWriteCount'], result['auditWriteCount'],
            result['stateTransitionWriteCount'], result['supportWriteCount']), (1, 1, 0, 2))
        self.assertEqual(read['businessBasisPresentation'][-1]['statusLabel'], '当前产能纠正依据')
        self.assertIn('历史依据', read['businessBasisPresentation'][0]['statusLabel'])

    def test_revocation_without_zero_answer_is_invalid_resolution_not_a_fourth_meaning(self):
        self.save_no_capacity_preparation()
        self.correct_capacity(confirmed_zero=False)
        read = self.read()
        self.assertEqual(read['capacityResolution']['code'], 'UNRESOLVED_CONFLICT')
        self.assertFalse(read['capacityResolution']['valid'])
        self.assertTrue(read['capacityResolution']['originalConclusionRevoked'])
        self.assertIsNone(read['capacityMeasurementStatus'])
        self.assertIsNone(read['capacityBusinessValue'])
        self.assertIsNone(read['capacitySemantics']['meaningCode'])
        self.assertNotEqual(read['capacitySemantics']['meaningCode'], 'NOT_APPLICABLE')

    def test_prior_creation_key_replay_preserves_historical_result_and_returns_current_ruling(self):
        self.save_no_capacity_preparation()
        row = OperationInputPreparationDraft.objects.get()
        # Simulate the immutable V1 ledger response already present before this
        # semantic correction. Its old value remains only in historicalResult.
        ledger = row.creation_write_request
        ledger.result['capacityMeasurementStatus'] = 'UNMEASURED'
        ledger.save(update_fields=('result',))
        historical_result = deepcopy(ledger.result)
        self.correct_capacity()
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            replay = self.save()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for item in queries))
        self.assertEqual(replay['revision'], 2)
        self.assertEqual(replay['historicalResultRevision'], 1)
        self.assertEqual(replay['capacityMeasurementStatus'], 'zero_capacity')
        self.assertEqual(replay['historicalResult']['capacityMeasurementStatus'], 'UNMEASURED')
        self.assertEqual(replay['historicalResult']['resultSemantics'], 'HISTORICAL_COMMITTED_RESULT')
        self.assertEqual({k: v for k, v in replay['historicalResult'].items() if k != 'resultSemantics'}, historical_result)

    def test_correction_replay_is_same_record_same_revision_and_zero_write(self):
        self.save_no_capacity_preparation()
        basis = self.ruling_basis()
        self.correct_capacity(basis=basis)
        before = self.snapshot()
        result = self.correct_capacity(basis=basis)
        self.assertTrue(result['idempotentReplay'])
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['historicalResultRevision'], 2)
        self.assertEqual(result['capacityBusinessValue'], 0)
        self.assertEqual(self.snapshot(), before)

    def test_capacity_ruling_requires_exact_source_scope_policy_and_explicit_answer(self):
        self.save_no_capacity_preparation()
        changes = [lambda r: r.update(userDecision=None),
            lambda r: r.update(principles={'contractVersion': 'PCE-CAPACITY-TRISTATE-V1'}),
            lambda r: r['sourceProof'].update(productTypeCode='foreign/product'),
            lambda r: r['sourceProof'].update(processName='another process'),
            lambda r: r['sourceProof'].update(rawValue='0'),
            lambda r: r['sourceProof'].update(currentApplicability='NOT_APPLICABLE'),
            lambda r: r.update(rulingType='UNMEASURED')]
        for change in changes:
            basis = self.ruling_basis()
            change(basis['entries'][-1]['capacityRuling'])
            self.rejected(lambda: self.correct_capacity(basis=basis), 'PREPARATION_CAPACITY_RULING_INVALID')

    def test_capacity_ruling_stale_revision_and_creation_bypass_are_rejected(self):
        self.save_no_capacity_preparation()
        valid_basis = self.ruling_basis()
        basis = deepcopy(valid_basis)
        basis['entries'][-1]['capacityRuling']['supersedesRevision'] = 2
        self.rejected(lambda: self.correct_capacity(basis=basis), 'PREPARATION_CAPACITY_RULING_REVISION_CONFLICT')
        self.correct_capacity(basis=valid_basis)
        self.rejected(lambda: self.correct_capacity(basis=valid_basis, revision=1, key='sim-stale-ruling'), 'PREPARATION_REVISION_CONFLICT')

    def test_saved_ruling_cannot_be_removed_or_rewritten_by_followup_update(self):
        self.save_no_capacity_preparation()
        self.correct_capacity()
        for change in (lambda b: b['entries'].pop(),
                lambda b: b['entries'][-1]['capacityRuling'].update(reason='rewritten reason')):
            basis = deepcopy(self.read()['businessBasis'])
            change(basis)
            self.rejected(lambda: self.correct_capacity(basis=basis, revision=2, key='sim-rewrite-ruling'),
                'PREPARATION_BASIS_IMMUTABLE')

    def test_ruling_audit_failure_rolls_back_only_new_revision_and_support(self):
        self.save_no_capacity_preparation()
        basis = self.ruling_basis()
        with patch.object(service, '_audit', side_effect=RuntimeError('SIMULATED_FOR_TEST correction audit failure')):
            self.rejected(lambda: self.correct_capacity(basis=basis), exception=RuntimeError)
        self.assertEqual(OperationInputPreparationDraft.objects.get().revision, 1)

    def test_zero_ruling_read_is_zero_write_and_preserves_unknowns_and_all_gates(self):
        self.save_no_capacity_preparation()
        self.correct_capacity()
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = self.read()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for item in queries))
        self.assertEqual(result['inputStandardStatus'], 'PENDING_CONFIRMATION')
        self.assertTrue(all(result[field] is None for field in ('sourceQuantity', 'inputQuantity', 'capacityQuantity')))
        self.assertFalse(any(result[field] for field in ('formalRulePublished', 'readyForGeneration',
            'readyForAllocation', 'readyForScheduling')))

    def test_zero_ruling_does_not_hide_later_positive_standard_capacity(self):
        self.save_no_capacity_preparation()
        self.correct_capacity()
        self.f.make_capacity(self.operation, self.f.area, 'SIM-LATER-POSITIVE-CAPACITY',
            measurement_status='measured', quantity=10)
        before = self.snapshot()
        current = self.read()
        self.assertEqual(current['rulingBusinessValue'], 0)
        self.assertIsNone(current['capacityBusinessValue'])
        self.assertFalse(current['capacityResolution']['valid'])
        self.assertEqual(current['capacitySemantics']['conflictCode'], 'CAPACITY_SOURCE_RULING_CONFLICT')
        self.assertIsNone(current['capacitySemantics']['meaningCode'])
        self.assertEqual(self.snapshot(), before)


class OperationInputPreparationDispatchTests(SimpleTestCase):
    def test_action_only_delegates_supported_fields_to_native_preparation_writer(self):
        from types import SimpleNamespace
        user = SimpleNamespace(pk=17, company_id=9, is_authenticated=True, is_active=True)
        payload = {"action": "saveOperationInputPreparation", "exactScope": {"companyId": 9},
            "businessBasis": {"entries": []}, "idempotencyKey": "test-key", "expectedContextHash": "0" * 64,
            "reason": "SIMULATED_FOR_TEST", "producerRuleId": 12, "manufacturingModeId": 4,
            "workCenterId": 5, "standardCapacityId": None, "draftSelection": None, "expectedRevision": 2}
        request = APIRequestFactory().post("/api/pde/a1-foundation/operations/", payload, format="json")
        force_authenticate(request, user=user)
        with (patch.object(service, "save_preparation", return_value={"isPersisted": True}) as save,
                patch("pde.views.ProductionFoundationService.write", side_effect=AssertionError("no generic write"))):
            response = ProductionFoundationA1View.as_view()(request, entity="operations")
        self.assertEqual(response.status_code, 200)
        save.assert_called_once_with(user=user, exact_scope={"companyId": 9}, draft_selection=None,
            business_basis={"entries": []}, idempotency_key="test-key", expected_revision=2,
            expected_context_hash="0" * 64, reason="SIMULATED_FOR_TEST", producer_rule_id=12,
            manufacturing_mode_id=4, work_center_id=5, standard_capacity_id=None)
