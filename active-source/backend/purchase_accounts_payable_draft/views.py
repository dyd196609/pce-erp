import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from purchase_invoice_prepare.v44_services import (
    build_ap_draft_eligibility,
    current_execution,
    current_snapshot,
)
from reconciliation.services import ReconciliationError
from workflow_runtime.facts import business_state_collection_facts
from purchase_canary.models import PurchaseCanaryBatch, PurchaseCanaryLineage

from .models import PurchaseAccountsPayableDraft
from .services import (
    build_business_gate,
    build_current_state,
    generate_purchase_accounts_payable_draft,
    recover_generation_result,
    serialize_draft,
)


def error_response(exc):
    classification = {
        "APD_AUTH_PERMISSION_DENIED": "permission_denied",
        "APD_AUTH_SCOPE_DENIED": "permission_denied",
        "APD_AUTH_FEATURE_DISABLED": "feature_disabled",
        "APD_AUTH_PRODUCTION_ROLLOUT_DISABLED": "permission_denied",
        "APD_VERSION_CONFLICT": "version_conflict",
        "APD_EXISTING_TARGET": "existing_target",
        "APD_TARGET_CONFLICT": "conflict",
        "APD_IN_PROGRESS": "in_progress",
        "APD_COMMIT_UNKNOWN": "commit_unknown",
        "APD_RECOVERY_REQUIRED": "recovery_required",
    }.get(exc.code, "blocked")
    return Response(
        {
            "result": "blocked",
            "classification": classification,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        },
        status=exc.http_status,
    )


def serialize_source(source):
    snapshot = current_snapshot(source)
    execution = current_execution(source)
    claim = source.invoice_identity_claims.filter(status="active").first()
    eligibility = build_ap_draft_eligibility(source)
    reconciliation = source.source_purchase_reconciliation
    return {
        "id": source.pk,
        "prepareNo": source.prepare_no,
        "status": source.status,
        "invoiceDataStatus": source.invoice_data_status,
        "validationStatus": source.validation_status,
        "validationResultCode": source.validation_result_code,
        "validationIssueCount": source.validation_issue_count,
        "prepareVersion": source.version,
        "invoiceDataVersion": source.current_data_version,
        "validationVersion": source.current_validation_version,
        "invoiceIdentityClaimId": claim.pk if claim else None,
        "invoiceIdentityStatus": claim.status if claim else "missing",
        "invoiceIdentityKey": claim.invoice_identity_key if claim else "",
        "invoiceDataSnapshotId": snapshot.pk if snapshot else None,
        "validationExecutionId": execution.pk if execution else None,
        "sourcePurchaseReconciliationId": reconciliation.pk,
        "sourcePurchaseReconciliationNo": reconciliation.reconciliation_no,
        "sourcePurchaseReconciliationStatus": reconciliation.status,
        "sourceReconciliationVersion": reconciliation.version,
        "sourceCheckVersion": source.source_check_version,
        "nextStepReadiness": eligibility["nextStepReadiness"],
        "eligible": eligibility["eligible"],
    }


class ScopedMixin:
    def get_permissions(self):
        permission = AllowAny if getattr(settings, "PCE_CANARY_DEMO_MODE", False) else IsAuthenticated
        return [permission()]

    def queryset(self, request):
        queryset = PurchaseAccountsPayableDraft.objects.select_related(
            "source_purchase_invoice_prepare",
            "number_reservation",
            "business_transaction",
            "audit_record",
        ).order_by("-created_at")
        canary_tenant = getattr(settings, "PCE_CANARY_TENANT_ID", "")
        if getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            queryset = queryset.filter(tenant_id=canary_tenant)
        elif not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        return queryset


def canary_runtime():
    database_path = str(connection.settings_dict["NAME"])
    digest = hashlib.sha256()
    database_file = Path(database_path)
    if database_file.is_file():
        with database_file.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return {
        "backendPid": os.getpid(),
        "settingsModule": os.environ.get("DJANGO_SETTINGS_MODULE", ""),
        "databasePath": database_path,
        "databaseSha256": digest.hexdigest() if database_file.is_file() else "in_memory_test_database",
        "tenantId": getattr(settings, "PCE_CANARY_TENANT_ID", ""),
        "canaryBatchId": getattr(settings, "PCE_CANARY_BATCH_ID", ""),
        "tenantContextSource": "server_local_demo_config",
        "databasePurpose": "persistent_demonstration",
    }


def pre_action_gate_snapshot(source, targets):
    gate = build_business_gate(source)
    if len(targets) == 1 and targets[0].audit_record:
        audit_rules = (
            targets[0].audit_record.evidence or {}
        ).get("preActionBusinessGate", [])
        return {
            "passed": bool(audit_rules)
            and all(rule.get("status") == "passed" for rule in audit_rules),
            "ruleCount": len(audit_rules),
            "rules": audit_rules,
            "label": "动作前业务门禁快照",
        }
    return {
        "passed": gate["passed"],
        "ruleCount": gate["ruleCount"],
        "rules": gate["rules"],
        "label": "动作前业务门禁快照",
    }


class DraftListView(ScopedMixin, APIView):
    def get(self, request):
        scenario_code = request.query_params.get("scenarioCode") or ""
        scenario_class = request.query_params.get("scenarioClass") or "all"
        batch_id = request.query_params.get("canaryBatchId") or getattr(
            settings, "PCE_CANARY_BATCH_ID", ""
        )
        batch = PurchaseCanaryBatch.objects.filter(batch_id=batch_id).first()
        lineages = PurchaseCanaryLineage.objects.none()
        if batch:
            lineages = batch.lineages.filter(
                current_module_code="account-payable-draft"
            ).order_by("scenario_code")
        if scenario_code in {"HAPPY_PATH", "EXISTING_TARGET"}:
            lineages = lineages.filter(scenario_code="SUCCESS_STANDARD_01")
        elif scenario_code.startswith("SUCCESS_"):
            lineages = lineages.filter(scenario_code=scenario_code)
        elif scenario_code:
            lineages = lineages.none()
        elif scenario_class == "blocked":
            lineages = lineages.none()
        lineage_rows = list(lineages)
        lineage_by_id = {row.current_object_id: row for row in lineage_rows}
        items = list(self.queryset(request).filter(pk__in=lineage_by_id))
        serialized_items = []
        for item in items:
            lineage = lineage_by_id[item.pk]
            serialized_items.append({
                **serialize_draft(item),
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "scenarioClass": lineage.scenario_class,
                "scenarioRole": lineage.scenario_role,
                "downstreamEligible": lineage.downstream_eligible,
                "reservedForNextModule": lineage.reserved_for_next_module,
                "nextStageConsumed": lineage.next_stage_consumed,
                "sourceRelationHash": lineage.source_relation_hash,
                "upstreamObjectNos": lineage.upstream_object_nos,
            })
        blocked = []
        if batch:
            for scenario in batch.scenarios.filter(
                expected_outcome__startswith="blocked_"
            ).order_by("code"):
                module = "purchase-reconciliation" if "reconciliation" in scenario.expected_outcome else "invoice-prepare"
                blocked.append({
                    "scenarioCode": scenario.code,
                    "scenarioClass": "blocked",
                    "scenarioRole": "negative_boundary",
                    "currentModuleCode": module,
                    "currentObjectType": "",
                    "currentObjectId": None,
                    "currentObjectNo": "",
                    "currentStatus": "blocked",
                    "formalApDraftCreated": False,
                    "downstreamEligible": False,
                    "reservedForNextModule": "",
                    "nextStageConsumed": False,
                    "blockingModule": module,
                    "blockingRuleCode": scenario.code,
                    "blockingReason": scenario.block_reason,
                    "sourceRelationHash": scenario.scenario_hash,
                })
        pass_through = [{
            "canaryLineageId": row.canary_lineage_id,
            "scenarioCode": row.scenario_code,
            "scenarioClass": row.scenario_class,
            "scenarioRole": row.scenario_role,
            "currentModuleCode": row.current_module_code,
            "currentObjectType": row.current_object_type,
            "currentObjectId": row.current_object_id,
            "currentObjectNo": row.current_object_no,
            "currentStatus": "draft",
            "formalApDraftCreated": True,
            "downstreamEligible": row.downstream_eligible,
            "reservedForNextModule": row.reserved_for_next_module,
            "nextStageConsumed": row.next_stage_consumed,
            "blockingModule": row.blocking_module,
            "blockingRuleCode": row.blocking_rule_code,
            "blockingReason": row.blocking_reason,
            "upstreamObjectNos": row.upstream_object_nos,
            "sourceRelationHash": row.source_relation_hash,
        } for row in PurchaseCanaryLineage.objects.filter(batch=batch).order_by("scenario_code")] if batch else []
        overview = pass_through + blocked
        if scenario_class == "success":
            overview = pass_through
        elif scenario_class == "blocked":
            overview = blocked
        if scenario_code:
            mapped_code = "SUCCESS_STANDARD_01" if scenario_code in {"HAPPY_PATH", "EXISTING_TARGET"} else scenario_code
            overview = [row for row in overview if row["scenarioCode"] == mapped_code]
        current_state = None
        source = None
        if len(items) == 1:
            source_obj = items[0].source_purchase_invoice_prepare
            current_state = build_current_state(source_obj, items)
            source = serialize_source(source_obj)
        return Response({
            "result": "passed",
            "data": {
                "currentStateSource": "server",
                "count": len(items),
                "results": serialized_items,
                "strictFacts": business_state_collection_facts(serialized_items),
                "scenarioCode": scenario_code or "ALL",
                "scenarioClass": scenario_class,
                "scenarioReadOnly": True,
                "capacity": {
                    "canaryBatchId": batch_id,
                    "successLineageCount": len(pass_through),
                    "blockedScenarioCount": len(blocked),
                    "formalDraftCount": len(pass_through),
                    "downstreamEligibleLineageCount": sum(
                        1 for row in pass_through if row["downstreamEligible"]
                    ),
                    "reservedForNextModuleCount": sum(
                        1 for row in pass_through
                        if row["reservedForNextModule"] == "payable_confirmation_prepare"
                    ),
                    "nextStageConsumedCount": sum(
                        1 for row in pass_through if row["nextStageConsumed"]
                    ),
                    "unconsumedAvailableCount": sum(
                        1 for row in pass_through
                        if row["downstreamEligible"] and not row["nextStageConsumed"]
                    ),
                    "nextModule": "payable_confirmation_prepare",
                    "passed": len(pass_through) >= 8
                    and not any(row["nextStageConsumed"] for row in pass_through),
                },
                "scenarioOverview": overview,
                "source": source,
                "currentState": current_state,
                "preActionBusinessGate": pre_action_gate_snapshot(
                    items[0].source_purchase_invoice_prepare, items
                ) if len(items) == 1 else None,
                "downstreamCounts": {
                    "confirmationPrepares": 0, "paymentApplications": 0,
                    "payments": 0, "paymentVouchers": 0, "writeoffs": 0,
                    "ledgerEntries": 0, "postings": 0, "bankTransactions": 0,
                    "localStorageBusinessWrites": 0, "productionNetworkWrites": 0,
                },
                "serverRuntime": canary_runtime() if getattr(settings, "PCE_CANARY_DEMO_MODE", False) else {},
            },
        })


class DraftDetailView(ScopedMixin, APIView):
    def get(self, request, draft_id):
        obj = self.queryset(request).filter(pk=draft_id).first()
        if not obj:
            return error_response(
                ReconciliationError("APD_TARGET_CONFLICT", "Draft not found", 404)
            )
        return Response({
            "result": "passed",
            "data": {
                **serialize_draft(obj),
                "source": serialize_source(obj.source_purchase_invoice_prepare),
                "currentState": build_current_state(
                    obj.source_purchase_invoice_prepare, [obj]
                ),
            },
        })


class DraftBySourceView(ScopedMixin, APIView):
    def get(self, request, prepare_id):
        source = PurchaseInvoicePrepare.objects.select_related(
            "source_purchase_reconciliation"
        ).filter(pk=prepare_id).first()
        if not source:
            return error_response(
                ReconciliationError("APD_SOURCE_NOT_FOUND", "Source not found", 404)
            )
        if (
            not getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            and not request.user.is_superuser
            and request.user.company_id != source.company_id
        ):
            return error_response(
                ReconciliationError("APD_AUTH_SCOPE_DENIED", "Source outside actor scope", 403)
            )
        targets = list(
            self.queryset(request).filter(source_purchase_invoice_prepare=source)
        )
        pre_action_gate = pre_action_gate_snapshot(source, targets)
        return Response({
            "result": "passed",
            "data": {
                "source": serialize_source(source),
                "count": len(targets),
                "results": [serialize_draft(item) for item in targets],
                **build_current_state(source, targets),
                "preActionBusinessGate": pre_action_gate,
            },
        })


class GenerateView(APIView):
    forbidden = {
        "draftNo", "status", "supplier", "supplierId", "currency",
        "amountExcludingTax", "taxAmount", "amountIncludingTax", "payableAmount",
        "sourceEligibility", "sourceValidationStatus", "existingTargetCount",
        "eligible", "nextStepReadiness", "validationStatus",
        "validationResultCode", "validationIssueCount", "invoiceIdentityStatus",
    }

    def post(self, request):
        data = request.data
        if self.forbidden.intersection(data.keys()):
            return error_response(ReconciliationError(
                "APD_CLIENT_DERIVED_FIELD_FORBIDDEN",
                "Server-derived fields cannot be submitted",
                400,
            ))
        try:
            result = generate_purchase_accounts_payable_draft(
                user=request.user,
                source_prepare_id=data.get("sourcePurchaseInvoicePrepareId"),
                idempotency_key=data.get("idempotencyKey", ""),
                expected_prepare_version=data.get("expectedPrepareVersion"),
                expected_invoice_data_version=data.get("expectedInvoiceDataVersion"),
                expected_validation_version=data.get("expectedValidationVersion"),
                expected_reconciliation_version=data.get("expectedReconciliationVersion"),
                expected_check_version=data.get("expectedCheckVersion"),
                explicit_user_action=data.get("explicitUserAction") is True,
                failure_step=request.headers.get("X-PCE-Failure-Step", ""),
            )
            return Response(
                {"result": "passed", **result},
                status=201 if result["created"] else 200,
            )
        except ReconciliationError as exc:
            return error_response(exc)


class GenerationResultView(APIView):
    def get(self, request, idempotency_key):
        try:
            return Response({
                "result": "passed",
                **recover_generation_result(idempotency_key, request.user),
            })
        except ReconciliationError as exc:
            return error_response(exc)
