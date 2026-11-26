import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payment_order_prepare.models import PaymentOrderPrepare
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import canonical_hash

from payment_order_draft.models import (
    PaymentOrderDraft,
    PaymentOrderDraftCanaryScenario,
)
from payment_order_draft.services import (
    CANONICAL_NAME,
    NEXT_CANONICAL_NAME,
    NEXT_MODULE_CODE,
    NEXT_ROUTE,
    SOURCE_DOCUMENT_TYPE,
    VERSION,
    eligibility,
    generate_payment_order_draft,
    review_payment_order_draft,
    save_draft_data,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"
BLOCKED_SCENARIOS = (
    ("SOURCE_NOT_FOUND", "POD_SOURCE_NOT_FOUND"),
    ("SOURCE_NOT_PREPARED", "POD_SOURCE_NOT_PREPARED"),
    ("SOURCE_VALIDATION_FAILED", "POD_SOURCE_VALIDATION_FAILED"),
    ("SOURCE_STALE", "POD_SOURCE_STALE"),
    ("EXISTING_TARGET", "POD_EXISTING_TARGET"),
    ("APPROVAL_EVIDENCE_INCOMPLETE", "POD_APPROVAL_EVIDENCE_INCOMPLETE"),
    ("PAYER_ACCOUNT_INACTIVE", "POD_REVIEW_PAYER_ACCOUNT_INACTIVE"),
    ("PAYEE_ACCOUNT_INACTIVE", "POD_REVIEW_PAYEE_ACCOUNT_INACTIVE"),
    ("ACCOUNT_OWNER_MISMATCH", "POD_REVIEW_ACCOUNT_OWNER_MISMATCH"),
    ("CURRENCY_MISMATCH", "POD_REVIEW_CURRENCY_MISMATCH"),
    ("AMOUNT_MISMATCH", "POD_REVIEW_AMOUNT_MISMATCH"),
    ("EXECUTION_DATE_INVALID", "POD_REVIEW_EXECUTION_DATE_INVALID"),
    ("PAYMENT_ROUTE_INVALID", "POD_REVIEW_PAYMENT_ROUTE_INVALID"),
    ("BANK_INTERFACE_UNAVAILABLE", "POD_REVIEW_BANK_INTERFACE_UNAVAILABLE"),
    ("BANK_BUSINESS_DAY_INVALID", "POD_REVIEW_BANK_BUSINESS_DAY_INVALID"),
    ("CUTOFF_TIME_EXCEEDED", "POD_REVIEW_CUTOFF_TIME_EXCEEDED"),
    ("SINGLE_LIMIT_EXCEEDED", "POD_REVIEW_SINGLE_LIMIT_EXCEEDED"),
    ("DAILY_LIMIT_EXCEEDED", "POD_REVIEW_DAILY_LIMIT_EXCEEDED"),
    ("PAYMENT_HOLD_ACTIVE", "POD_REVIEW_PAYMENT_HOLD_ACTIVE"),
    ("DUPLICATE_PAYMENT_RISK", "POD_REVIEW_DUPLICATE_PAYMENT_RISK"),
    ("AVAILABLE_BALANCE_INSUFFICIENT", "POD_REVIEW_AVAILABLE_BALANCE_INSUFFICIENT"),
    ("FUNDS_AUTHORITY_UNAVAILABLE", "POD_REVIEW_FUNDS_AUTHORITY_UNAVAILABLE"),
    ("SIGNING_POLICY_INVALID", "POD_REVIEW_SIGNING_POLICY_INVALID"),
    ("AUTHORIZATION_ROUTE_INVALID", "POD_REVIEW_AUTHORIZATION_ROUTE_INVALID"),
    ("SIGNING_CAPABILITY_UNAVAILABLE", "POD_REVIEW_SIGNING_CAPABILITY_UNAVAILABLE"),
    ("SIGNING_CREDENTIAL_NOT_READY", "POD_REVIEW_SIGNING_CREDENTIAL_NOT_READY"),
    ("MAKER_CHECKER_CONFLICT", "POD_REVIEW_MAKER_CHECKER_CONFLICT"),
    ("PAYMENT_REFERENCE_MISSING", "POD_DATA_PAYMENT_REFERENCE_REQUIRED"),
    ("DRAFT_PAYLOAD_MISMATCH", "POD_REVIEW_DRAFT_PAYLOAD_INTEGRITY"),
    ("DRAFT_HASH_MISMATCH", "POD_REVIEW_DRAFT_PAYLOAD_INTEGRITY"),
    ("SOURCE_PREVIEW_HASH_MISMATCH", "POD_REVIEW_SOURCE_PREVIEW_INTEGRITY"),
    ("CREATION_PREVIEW_INTEGRITY_FAILED", "POD_REVIEW_CREATION_PREVIEW_INTEGRITY"),
    ("VERSION_CONFLICT", "VERSION_CONFLICT"),
)


def ensure_user():
    User = get_user_model()
    user = User.objects.filter(username="pce-v51-operator").first()
    if not user:
        user = User.objects.create_superuser(
            username="pce-v51-operator",
            real_name="PCE V51 Operator",
            email="pce-v51-operator@example.invalid",
            password=None,
            company_id=1,
        )
    return user


class Command(BaseCommand):
    help = "Idempotently ensure eight reviewed V51 formal payment-order drafts"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(
            batch.lineages.filter(
                scenario_class="pass_through",
                current_module_code__in=[
                    "payment-instruction-prepare",
                    "payment-order-prepare",
                    "payment-order-draft",
                ],
            ).order_by("scenario_code")[:8]
        )
        if len(lineages) < 8:
            raise CommandError("V50 prerequisite has fewer than eight legal lineages")

        actor = ensure_user()
        changed = False
        results = []
        with transaction.atomic():
            for lineage in lineages:
                if lineage.current_module_code == "payment-order-draft":
                    target = PaymentOrderDraft.objects.filter(
                        pk=lineage.current_object_id,
                        tenant_id=TENANT_ID,
                    ).first()
                    source = target.source_payment_order_prepare if target else None
                elif lineage.current_module_code == "payment-order-prepare":
                    source = PaymentOrderPrepare.objects.filter(
                        pk=lineage.current_object_id,
                        tenant_id=TENANT_ID,
                        status="submitted",
                    ).first()
                    target = (
                        PaymentOrderDraft.objects.filter(
                            source_payment_order_prepare=source
                        ).first()
                        if source
                        else None
                    )
                else:
                    source = PaymentOrderPrepare.objects.filter(
                        source_payment_instruction_prepare_id=lineage.current_object_id,
                        tenant_id=TENANT_ID,
                        status="submitted",
                    ).first()
                    target = (
                        PaymentOrderDraft.objects.filter(
                            source_payment_order_prepare=source
                        ).first()
                        if source
                        else None
                    )
                if not source:
                    raise CommandError(
                        f"Missing prepared V50 source for {lineage.scenario_code}"
                    )
                if not target:
                    outcome = generate_payment_order_draft(
                        user=actor,
                        source=source,
                        idempotency_key=f"pod-v51-generate-{lineage.scenario_code.lower()}",
                        expected_source_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentOrderDraft.objects.get(pk=outcome["data"]["id"])
                    changed = True
                if target.current_draft_data_version == 0:
                    source_data = source.order_data_snapshots.order_by(
                        "-order_data_version"
                    ).first()
                    outcome = save_draft_data(
                        user=actor,
                        obj=target,
                        payload={
                            "plannedExecutionDate": target.planned_execution_date.isoformat(),
                            "plannedExecutionTime": target.planned_execution_time.isoformat(),
                            "paymentPurpose": source_data.payment_purpose,
                            "paymentSummary": f"V51最终草稿复核-{lineage.scenario_code}",
                            "priority": target.priority,
                        },
                        idempotency_key=f"pod-v51-save-{lineage.scenario_code.lower()}",
                        expected_version=target.version,
                        expected_draft_data_version=target.current_draft_data_version,
                        expected_payment_order_prepare_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentOrderDraft.objects.get(pk=outcome["data"]["id"])
                    changed = True
                if target.status != "reviewed":
                    outcome = review_payment_order_draft(
                        user=actor,
                        obj=target,
                        idempotency_key=f"pod-v51-review-{lineage.scenario_code.lower()}",
                        expected_version=target.version,
                        expected_draft_data_version=target.current_draft_data_version,
                        expected_payment_order_prepare_version=source.version,
                        explicit_user_action=True,
                    )
                    if not outcome["reviewed"]:
                        raise CommandError(
                            f"Review blocked for {target.draft_no}: "
                            f"{outcome['data']['reviewResultCode']}"
                        )
                    target = PaymentOrderDraft.objects.get(pk=outcome["data"]["id"])
                    changed = True

                ready = eligibility(target)
                if not ready["eligible"]:
                    raise CommandError(
                        f"Eligibility blocked for {target.draft_no}: "
                        f"{ready['blockingReasons']}"
                    )
                upstream = list(lineage.upstream_object_nos or [])
                if source.prepare_no not in upstream:
                    upstream.append(source.prepare_no)
                lineage_values = {
                    "current_module_code": "payment-order-draft",
                    "current_object_id": target.pk,
                    "current_object_no": target.draft_no,
                    "upstream_object_nos": upstream,
                    "downstream_eligible": True,
                    "reserved_for_next_module": NEXT_MODULE_CODE,
                    "next_stage_consumed": False,
                }
                changed_fields = [
                    field
                    for field, value in lineage_values.items()
                    if getattr(lineage, field) != value
                ]
                if changed_fields:
                    for field, value in lineage_values.items():
                        setattr(lineage, field, value)
                    lineage.save(update_fields=[*changed_fields, "updated_at"])
                    changed = True
                results.append(
                    {
                        "scenarioCode": lineage.scenario_code,
                        "sourcePaymentOrderPrepareNo": source.prepare_no,
                        "draftNo": target.draft_no,
                        "status": target.status,
                        "draftDataStatus": target.draft_data_status,
                        "reviewStatus": target.review_status,
                        "reviewResultCode": target.review_result_code,
                        "reviewIssueCount": target.review_issue_count,
                        "paymentAmount": str(target.payment_amount),
                        "currency": target.currency,
                        "plannedExecutionDate": target.planned_execution_date.isoformat(),
                        "paymentRouteId": target.payment_route_id,
                        "bankInterfaceProfileId": target.bank_interface_profile_id,
                        "signingPolicyId": target.signing_policy_id,
                        "nextStepReadiness": ready["nextStepReadiness"],
                    }
                )

            for code, rule in BLOCKED_SCENARIOS:
                payload = {"batchId": BATCH_ID, "scenarioCode": code, "rule": rule}
                _, created = PaymentOrderDraftCanaryScenario.objects.get_or_create(
                    batch_id=BATCH_ID,
                    scenario_code=code,
                    defaults={
                        "scenario_class": "blocked",
                        "blocking_rule_code": rule,
                        "blocking_reason": f"V51 isolated scenario blocked by {rule}",
                        "formal_object_count": 0,
                        "next_step_allowed": False,
                        "scenario_hash": canonical_hash(payload),
                    },
                )
                changed = changed or created

        queryset = PaymentOrderDraft.objects.filter(tenant_id=TENANT_ID)
        reviewed = queryset.filter(
            status="reviewed",
            draft_data_status="complete",
            review_status="passed",
            review_result_code="reviewed",
            review_issue_count=0,
        ).count()
        output = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": CANONICAL_NAME,
            "sourceDocumentType": SOURCE_DOCUMENT_TYPE,
            "changed": changed,
            "paymentOrderPrepareSourceCount": len(results),
            "paymentOrderPrepareConsumedCount": len(results),
            "passThroughLineageCount": len(results),
            "formalPaymentOrderDraftCount": queryset.count(),
            "reviewedPaymentOrderDraftCount": reviewed,
            "downstreamEligibleSourceCount": sum(
                1 for row in results if row["nextStepReadiness"] != "blocked"
            ),
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextCanonicalName": NEXT_CANONICAL_NAME,
            "nextRoute": NEXT_ROUTE,
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": len(BLOCKED_SCENARIOS),
            "formalPaymentOrderNumberConsumed": False,
            "nextModuleObjectCreated": False,
            "formalPaymentOrderCreated": False,
            "formalPaymentInstructionCreated": False,
            "paymentExecuted": False,
            "productionRolloutEnabled": False,
            "results": results,
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
