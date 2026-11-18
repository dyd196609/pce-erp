from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import MasterDataWriteRequest
from system.models import Company, Process, User

from .models import (
    EngineeringDerivedFact,
    ManufacturingProcessType,
    ProductCategory,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
)
from .routing_planning_readiness_service import RoutingPlanningReadinessService
from .routing_step_applicability_service import (
    CONDITIONAL,
    CONTRACT_VERSION,
    MANDATORY,
    NOT_APPLICABLE,
    PENDING,
    REQUIRED,
    RoutingStepApplicabilityResolver,
)
from .routing_version_successor_service import (
    RoutingVersionChangeError,
    RoutingVersionSuccessorService,
)
from .routing_manual_applicability_service import (
    MANUAL_SOURCE_TYPE,
    RoutingManualApplicabilityService,
)


class _FakeRows(list):
    def order_by(self, *args):
        return self


class RoutingStepApplicabilityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="APP", name="适用性合同测试公司")
        self.user = User.objects.create_user(
            username="routing_applicability_tester",
            password="test-only",
            real_name="路线适用性测试员",
            company_id=self.company.pk,
        )
        self.category = ProductCategory.objects.create(
            company=self.company, code="APP-CAT", name="适用性测试分类",
        )
        self.process_type = ManufacturingProcessType.objects.create(
            company=self.company, code="APP-PROC", name="适用性测试工艺",
        )
        self.routing = Routing.objects.create(
            company=self.company,
            applicability_scope="PRODUCT_CATEGORY",
            product_category=self.category,
            manufacturing_process_type=self.process_type,
            routing_code="APP/ROUTE",
            name="包含雕刻文字但不得据此推断的路线",
            status="released",
        )
        self.operation = Process.objects.create(
            company=self.company, code="APP-OP", name="雕刻文字不构成正式事实",
        )

    def _version(self, *, status="draft", number="V1.0", revision=1):
        return RoutingVersion.objects.create(
            routing=self.routing,
            routing_version=number,
            revision=revision,
            status=status,
        )

    def _step(self, version, *, parameters=None, sequence=10):
        return RoutingStep.objects.create(
            routing_version=version,
            sequence=sequence,
            operation=self.operation,
            operation_parameters=parameters or {},
        )

    def _release(self, version):
        version.status = "released"
        version.save(update_fields=("status", "updated_at"))
        return version

    def test_mandatory_contract_resolves_required(self):
        step = self._step(self._version(), parameters={"applicability": {"mode": MANDATORY}})
        result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], REQUIRED)
        self.assertEqual(result["modeLabel"], "必经工序")
        self.assertEqual(result["contractVersion"], CONTRACT_VERSION)

    def test_missing_draft_contract_is_pending(self):
        step = self._step(self._version())
        result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "APPLICABILITY_CONTRACT_MISSING")

    def test_operation_and_route_names_never_infer_condition(self):
        step = self._step(self._version())
        self.assertEqual(RoutingStepApplicabilityResolver.resolve(step)["result"], PENDING)

    def test_conditional_without_exact_document_is_pending(self):
        step = self._step(self._version(), parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "FORMAL_OR_MANUAL_CONDITION_REQUIRED")

    def test_authorized_manual_yes_resolves_required_without_document(self):
        step = self._step(self._version(), parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        manual = {
            "status": "RESOLVED", "decision": "YES", "decisionLabel": "是",
            "result": REQUIRED, "sourceLabel": "授权业务人员人工确认",
            "confirmedByUsername": "authorized-user", "confirmedAt": "2026-10-09T20:00:00+08:00",
            "auditId": 91,
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual):
            result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], REQUIRED)
        self.assertEqual(result["manualDecision"], "YES")
        self.assertEqual(result["formalSourceLabel"], "授权业务人员人工确认")

    def test_authorized_manual_no_resolves_not_applicable_without_document(self):
        step = self._step(self._version(), parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        manual = {
            "status": "RESOLVED", "decision": "NO", "decisionLabel": "否",
            "result": NOT_APPLICABLE, "sourceLabel": "授权业务人员人工确认",
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual):
            result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], NOT_APPLICABLE)

    def test_authorized_manual_pending_stays_pending(self):
        step = self._step(self._version(), parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        manual = {
            "status": "PENDING", "decision": "PENDING", "decisionLabel": "待确认",
            "result": PENDING, "sourceLabel": "授权业务人员人工确认",
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual):
            result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "MANUAL_DECISION_PENDING")

    def test_manual_and_formal_fact_conflict_fails_closed(self):
        step, calculation, document, facts = self._conditional_context(False)
        manual = {
            "status": "RESOLVED", "decision": "YES", "decisionLabel": "是",
            "result": REQUIRED, "sourceLabel": "授权业务人员人工确认",
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual), patch.object(
            EngineeringDerivedFact.objects, "filter", return_value=facts,
        ):
            result = RoutingStepApplicabilityResolver.resolve(
                step, engineering_document_version=document, engineering_calculation=calculation,
            )
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "MANUAL_AND_FORMAL_FACT_CONFLICT")

    def test_invalid_manual_identity_fails_closed(self):
        step = self._step(self._version(), parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        manual = {
            "status": "INVALID", "pendingCode": "MANUAL_DECISION_IDENTITY_DRIFT",
            "pendingReason": "人工判断绑定的订单工程身份与当前正式事实不一致。",
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual):
            result = RoutingStepApplicabilityResolver.resolve(step)
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "MANUAL_DECISION_IDENTITY_DRIFT")

    def test_unknown_condition_is_rejected(self):
        step = RoutingStep(
            routing_version=self._version(), sequence=10, operation=self.operation,
            operation_parameters={
                "applicability": {"mode": CONDITIONAL, "conditionCode": "GUESSED_FROM_NAME"},
            },
        )
        with self.assertRaises(ValidationError):
            step.full_clean()

    def _conditional_context(self, value, *, value_type="boolean", duplicate=False):
        version = self._version()
        step = self._step(version, parameters={
            "applicability": {
                "mode": CONDITIONAL,
                "conditionCode": "DRAWING_ENGRAVING_REQUIRED",
            },
        })
        calculation = SimpleNamespace(pk=71, status="completed", engineering_instance_id=91)
        document = SimpleNamespace(
            pk=81,
            status="released",
            related_routing_id=version.pk,
            engineering_calculation_id=71,
            engineering_calculation=calculation,
            order_engineering_instance_id=91,
            order_engineering_baseline_id=101,
            order_engineering_baseline=SimpleNamespace(status="confirmed"),
            related_bom_id=111,
            document_version="V1.0",
        )
        facts = _FakeRows([
            SimpleNamespace(pk=121, value=value, value_type=value_type),
        ])
        if duplicate:
            facts.append(SimpleNamespace(pk=122, value=value, value_type=value_type))
        return step, calculation, document, facts

    def test_true_formal_boolean_resolves_required(self):
        step, calculation, document, facts = self._conditional_context(True)
        with patch.object(EngineeringDerivedFact.objects, "filter", return_value=facts):
            result = RoutingStepApplicabilityResolver.resolve(
                step, engineering_document_version=document,
                engineering_calculation=calculation,
            )
        self.assertEqual(result["result"], REQUIRED)
        self.assertEqual(result["engineeringDerivedFactId"], 121)

    def test_false_formal_boolean_resolves_not_applicable(self):
        step, calculation, document, facts = self._conditional_context(False)
        with patch.object(EngineeringDerivedFact.objects, "filter", return_value=facts):
            result = RoutingStepApplicabilityResolver.resolve(
                step, engineering_document_version=document,
                engineering_calculation=calculation,
            )
        self.assertEqual(result["result"], NOT_APPLICABLE)

    def test_duplicate_formal_fact_fails_closed(self):
        step, calculation, document, facts = self._conditional_context(True, duplicate=True)
        with patch.object(EngineeringDerivedFact.objects, "filter", return_value=facts):
            result = RoutingStepApplicabilityResolver.resolve(
                step, engineering_document_version=document,
                engineering_calculation=calculation,
            )
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "FORMAL_CONDITION_FACT_NOT_UNIQUE")

    def test_invalid_formal_fact_type_fails_closed(self):
        step, calculation, document, facts = self._conditional_context("true", value_type="string")
        with patch.object(EngineeringDerivedFact.objects, "filter", return_value=facts):
            result = RoutingStepApplicabilityResolver.resolve(
                step, engineering_document_version=document,
                engineering_calculation=calculation,
            )
        self.assertEqual(result["result"], PENDING)
        self.assertEqual(result["pendingCode"], "FORMAL_CONDITION_FACT_INVALID")

    def test_pending_planning_step_does_not_evaluate_capacity(self):
        version = self._version()
        self._step(version, parameters={
            "applicability": {
                "mode": CONDITIONAL,
                "conditionCode": "DRAWING_ENGRAVING_REQUIRED",
            },
        })
        with patch.object(StandardCapacity.objects, "filter") as capacity_filter:
            result = RoutingPlanningReadinessService.assess(version)
        capacity_filter.assert_not_called()
        self.assertEqual(result["pendingApplicabilityStepCount"], 1)
        self.assertFalse(result["planningReady"])
        self.assertFalse(result["steps"][0]["capacityDemandEvaluated"])

    def test_not_applicable_planning_step_is_skipped_without_capacity_demand(self):
        version = self._version()
        self._step(version, parameters={"applicability": {"mode": MANDATORY}})
        projection = {
            "contractVersion": CONTRACT_VERSION,
            "result": NOT_APPLICABLE,
            "resultLabel": "本次不适用",
        }
        with patch.object(RoutingStepApplicabilityResolver, "resolve", return_value=projection), patch.object(
            StandardCapacity.objects, "filter",
        ) as capacity_filter:
            result = RoutingPlanningReadinessService.assess(version)
        capacity_filter.assert_not_called()
        self.assertEqual(result["notApplicableStepCount"], 1)
        self.assertTrue(result["steps"][0]["planningReady"])
        self.assertFalse(result["steps"][0]["capacityDemandEvaluated"])

    def test_terminal_parent_blocks_step_save(self):
        version = self._version()
        step = self._step(version, parameters={"applicability": {"mode": MANDATORY}})
        self._release(version)
        step.instruction = "不得原地修改"
        with self.assertRaises(ValidationError):
            step.save()

    def test_terminal_parent_blocks_step_create(self):
        version = self._release(self._version())
        with self.assertRaises(ValidationError):
            self._step(version, parameters={"applicability": {"mode": MANDATORY}})

    def test_terminal_parent_blocks_queryset_update_delete_and_bulk(self):
        version = self._version()
        step = self._step(version, parameters={"applicability": {"mode": MANDATORY}})
        self._release(version)
        with self.assertRaises(ValidationError):
            RoutingStep.objects.filter(pk=step.pk).update(instruction="禁止")
        with self.assertRaises(ValidationError):
            RoutingStep.objects.filter(pk=step.pk).delete()
        with self.assertRaises(ValidationError):
            RoutingStep.objects.bulk_create([
                RoutingStep(
                    routing_version=version, sequence=20, operation=self.operation,
                    operation_parameters={"applicability": {"mode": MANDATORY}},
                ),
            ])

    def test_draft_parent_allows_controlled_step_update(self):
        version = self._version()
        step = self._step(version, parameters={"applicability": {"mode": MANDATORY}})
        step.instruction = "草稿可维护"
        step.save()
        self.assertEqual(RoutingStep.objects.get(pk=step.pk).instruction, "草稿可维护")

    def _terminal_source(self):
        source = self._version(status="draft", number="SYSTEM_INITIAL_VERSION")
        self._step(source, parameters={"applicability": {"mode": MANDATORY}})
        return self._release(source)

    def _authorization(self):
        return (
            self.company.pk,
            {"allowed": True, "decisionCode": "ALLOWED"},
            {"account": self.user.username, "employeeId": 1, "positionId": 1, "responsibilityId": 1},
        )

    def test_successor_copies_steps_as_draft_and_preserves_source(self):
        source = self._terminal_source()
        with patch("pde.routing_version_successor_service._authorize", return_value=self._authorization()):
            result = RoutingVersionSuccessorService.create(
                source_id=source.pk, user=self.user,
                idempotency_key="successor-copy", reason="承接单步适用性合同",
            )
        target = RoutingVersion.objects.get(pk=result["routingVersionId"])
        source.refresh_from_db()
        self.assertEqual(source.status, "released")
        self.assertEqual(source.steps.count(), 1)
        self.assertEqual(target.status, "draft")
        self.assertEqual(target.steps.count(), 1)
        self.assertEqual(
            target.steps.get().operation_parameters["applicability"]["contractVersion"],
            CONTRACT_VERSION,
        )

    def test_successor_is_idempotent(self):
        source = self._terminal_source()
        kwargs = {
            "source_id": source.pk, "user": self.user,
            "idempotency_key": "successor-replay", "reason": "幂等承接",
        }
        with patch("pde.routing_version_successor_service._authorize", return_value=self._authorization()):
            first = RoutingVersionSuccessorService.create(**kwargs)
            second = RoutingVersionSuccessorService.create(**kwargs)
        self.assertEqual(first["routingVersionId"], second["routingVersionId"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(RoutingVersion.objects.filter(routing=self.routing).count(), 2)
        self.assertEqual(MasterDataWriteRequest.objects.filter(idempotency_key="successor-replay").count(), 1)

    def test_successor_rejects_new_key_after_successor_exists(self):
        source = self._terminal_source()
        with patch("pde.routing_version_successor_service._authorize", return_value=self._authorization()):
            first = RoutingVersionSuccessorService.create(
                source_id=source.pk, user=self.user,
                idempotency_key="successor-first", reason="首次承接",
            )
            with self.assertRaises(RoutingVersionChangeError) as raised:
                RoutingVersionSuccessorService.create(
                    source_id=source.pk, user=self.user,
                    idempotency_key="successor-second", reason="禁止重复承接",
                )
        self.assertEqual(raised.exception.code, "SUCCESSOR_ALREADY_CREATED")
        self.assertEqual(raised.exception.details["routingVersionId"], first["routingVersionId"])
        self.assertEqual(RoutingVersion.objects.filter(routing=self.routing).count(), 2)
        self.assertFalse(MasterDataWriteRequest.objects.filter(idempotency_key="successor-second").exists())

    def test_successor_rejects_nonterminal_source(self):
        source = self._version(status="draft")
        with patch("pde.routing_version_successor_service._authorize", return_value=self._authorization()):
            with self.assertRaises(RoutingVersionChangeError) as raised:
                RoutingVersionSuccessorService.create(
                    source_id=source.pk, user=self.user,
                    idempotency_key="successor-invalid", reason="不合法来源",
                )
        self.assertEqual(raised.exception.code, "SUCCESSOR_SOURCE_STATUS_INVALID")

    def test_successor_rolls_back_every_write_on_copy_failure(self):
        source = self._terminal_source()
        with patch("pde.routing_version_successor_service._authorize", return_value=self._authorization()), patch(
            "pde.routing_version_successor_service.successor_contract",
            side_effect=RuntimeError("simulated copy failure"),
        ):
            with self.assertRaises(RuntimeError):
                RoutingVersionSuccessorService.create(
                    source_id=source.pk, user=self.user,
                    idempotency_key="successor-rollback", reason="回滚验证",
                )
        self.assertEqual(RoutingVersion.objects.filter(routing=self.routing).count(), 1)
        self.assertFalse(MasterDataWriteRequest.objects.filter(idempotency_key="successor-rollback").exists())

    def _manual_context(self, version):
        snapshot = {
            "organizationId": self.company.pk,
            "salesOrderId": 301,
            "salesOrderNo": "SO-MANUAL-001",
            "salesOrderItemId": 302,
            "salesOrderLineNo": 1,
            "orderEngineeringInstanceId": 303,
            "orderEngineeringInstanceNo": "OEI-MANUAL-001",
            "orderEngineeringBaselineId": 304,
            "orderEngineeringBaselineNo": "EB-MANUAL-001",
            "engineeringCalculationId": 305,
            "engineeringCalculationNo": "EC-MANUAL-001",
            "engineeringCalculationRevision": 1,
            "bomVersionId": 306,
            "bomVersionNo": "CALC-MANUAL-001",
            "bomVersionRevision": 1,
            "routingId": self.routing.pk,
            "routingVersionId": version.pk,
            "routingVersionNo": version.routing_version,
            "routingVersionRevision": version.revision,
        }
        snapshot["contextKey"] = "OEI:303|BASELINE:304|CALC:305|BOM:306"
        import hashlib
        import json
        snapshot["identityHash"] = hashlib.sha256(json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")).hexdigest()
        return {"snapshot": snapshot}

    def test_manual_decision_write_is_structured_audited_and_idempotent(self):
        version = self._version()
        step = self._step(version, parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        context = self._manual_context(version)
        kwargs = {
            "version_id": version.pk,
            "user": self.user,
            "context_key": context["snapshot"]["contextKey"],
            "condition_code": "DRAWING_ENGRAVING_REQUIRED",
            "decision": "YES",
            "note": "授权业务人员确认本次订单工程对象需要雕刻纹路",
            "idempotency_key": "manual-decision-yes",
            "expected_audit_id": None,
        }
        with patch(
            "pde.routing_manual_applicability_service._authorize",
            return_value=self._authorization(),
        ), patch(
            "pde.routing_manual_applicability_service.exact_contexts_for_version",
            return_value=[context],
        ):
            first = RoutingManualApplicabilityService.confirm(**kwargs)
            second = RoutingManualApplicabilityService.confirm(**kwargs)
            step = RoutingStep.objects.select_related("routing_version").get(pk=step.pk)
            projection = RoutingManualApplicabilityService.resolve_for_step(step)
        version.refresh_from_db()
        self.assertEqual(first["decision"], "YES")
        self.assertEqual(first["sourceType"], MANUAL_SOURCE_TYPE)
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(projection["result"], REQUIRED)
        stored = version.applicability["manualStepApplicability"]["contexts"]
        decision = stored[context["snapshot"]["contextKey"]]["decisions"]["DRAWING_ENGRAVING_REQUIRED"]
        self.assertEqual(decision["confirmedByUserId"], self.user.pk)
        self.assertEqual(decision["writeRequestId"], first["writeRequestId"])
        self.assertEqual(MasterDataWriteRequest.objects.filter(idempotency_key="manual-decision-yes").count(), 1)

    def test_manual_decision_audit_snapshot_mismatch_fails_closed(self):
        version = self._version()
        step = self._step(version, parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        context = self._manual_context(version)
        with patch(
            "pde.routing_manual_applicability_service._authorize",
            return_value=self._authorization(),
        ), patch(
            "pde.routing_manual_applicability_service.exact_contexts_for_version",
            return_value=[context],
        ):
            RoutingManualApplicabilityService.confirm(
                version_id=version.pk,
                user=self.user,
                context_key=context["snapshot"]["contextKey"],
                condition_code="DRAWING_ENGRAVING_REQUIRED",
                decision="YES",
                note="授权业务人员确认本次订单工程对象需要雕刻纹路",
                idempotency_key="manual-decision-audit-mismatch",
            )
        version.refresh_from_db()
        tampered = deepcopy(version.applicability)
        tampered["manualStepApplicability"]["contexts"][context["snapshot"]["contextKey"]]["decisions"][
            "DRAWING_ENGRAVING_REQUIRED"
        ]["decision"] = "NO"
        version.applicability = tampered
        version.save(update_fields=("applicability", "updated_at"))
        step = RoutingStep.objects.select_related("routing_version").get(pk=step.pk)
        with patch(
            "pde.routing_manual_applicability_service.exact_contexts_for_version",
            return_value=[context],
        ):
            projection = RoutingManualApplicabilityService.resolve_for_step(step)
        self.assertEqual(projection["status"], "INVALID")
        self.assertEqual(projection["pendingCode"], "MANUAL_DECISION_AUDIT_MISMATCH")

    def test_manual_decision_rejects_stale_update(self):
        version = self._version()
        self._step(version, parameters={
            "applicability": {"mode": CONDITIONAL, "conditionCode": "DRAWING_ENGRAVING_REQUIRED"},
        })
        context = self._manual_context(version)
        common = {
            "version_id": version.pk,
            "user": self.user,
            "context_key": context["snapshot"]["contextKey"],
            "condition_code": "DRAWING_ENGRAVING_REQUIRED",
            "note": "正式人工判断说明",
        }
        with patch(
            "pde.routing_manual_applicability_service._authorize",
            return_value=self._authorization(),
        ), patch(
            "pde.routing_manual_applicability_service.exact_contexts_for_version",
            return_value=[context],
        ):
            RoutingManualApplicabilityService.confirm(
                **common, decision="YES", idempotency_key="manual-first", expected_audit_id=None,
            )
            with self.assertRaises(RoutingVersionChangeError) as raised:
                RoutingManualApplicabilityService.confirm(
                    **common, decision="NO", idempotency_key="manual-stale", expected_audit_id=None,
                )
        self.assertEqual(raised.exception.code, "MANUAL_DECISION_STALE")
        self.assertFalse(MasterDataWriteRequest.objects.filter(idempotency_key="manual-stale").exists())
