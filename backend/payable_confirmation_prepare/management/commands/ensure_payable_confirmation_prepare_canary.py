import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_canary.models import PurchaseCanaryBatch, PurchaseCanaryLineage
from reconciliation.services import canonical_hash

from payable_confirmation_prepare.models import (
    PayableConfirmationCanaryScenario,
    PayableConfirmationPrepare,
)
from payable_confirmation_prepare.services import (
    generate_payable_confirmation_prepare,
)


VERSION = "V1.14.2.8.4.7.46"
BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"

SUCCESS_ROLES = {
    "SUCCESS_STANDARD_01": "payment_request_standard_path",
    "SUCCESS_STANDARD_02": "accounting_dimensions_complete_path",
    "SUCCESS_SECOND_SUPPLIER": "next_module_subject_missing_boundary",
    "SUCCESS_MULTI_LINE": "next_module_payment_terms_missing_boundary",
    "SUCCESS_HIGH_AMOUNT": "next_module_due_date_boundary",
    "SUCCESS_LOW_AMOUNT": "next_module_tax_dimension_validation",
    "SUCCESS_ALTERNATE_VALID_TAX_PROFILE": "next_module_idempotency_concurrency",
    "SUCCESS_IDEMPOTENCY_RECOVERY": "next_module_rollback_cross_process_recovery",
}

BLOCKED_SCENARIOS = (
    (
        "PCP_AP_ACCOUNT_MISSING",
        "missing_accounts_payable_account",
        "PCP_AP_ACCOUNT_REQUIRED",
        "应付科目缺失",
    ),
    (
        "PCP_INPUT_TAX_ACCOUNT_MISSING",
        "missing_input_tax_account",
        "PCP_INPUT_TAX_ACCOUNT_REQUIRED",
        "税额科目缺失",
    ),
    (
        "PCP_SUPPLIER_AUXILIARY_MISMATCH",
        "supplier_auxiliary_mismatch",
        "PCP_SUPPLIER_AUXILIARY_MISMATCH",
        "供应商辅助核算与来源不一致",
    ),
    (
        "PCP_ACCOUNTING_DIMENSION_MISSING",
        "accounting_dimension_missing",
        "PCP_COST_CENTER_REQUIRED",
        "部门、成本中心或项目维度缺失",
    ),
    (
        "PCP_PAYMENT_TERMS_MISSING",
        "payment_terms_missing",
        "PCP_PAYMENT_TERMS_REQUIRED",
        "付款条件缺失",
    ),
    (
        "PCP_ACCOUNTING_PERIOD_CLOSED",
        "accounting_period_closed",
        "PCP_ACCOUNTING_PERIOD_CLOSED",
        "会计期间未开放",
    ),
    (
        "PCP_DEBIT_CREDIT_UNBALANCED",
        "debit_credit_unbalanced",
        "PCP_DEBIT_CREDIT_UNBALANCED",
        "Decimal借贷预检查不平衡",
    ),
    (
        "PCP_SOURCE_VERSION_CONFLICT",
        "source_version_conflict",
        "PCP_SOURCE_VERSION_CONFLICT",
        "来源采购应付账款草稿版本冲突",
    ),
)


def accounting_data(source, index):
    terms_days = (15, 30, 45, 60, 90, 7, 20, 35)[index - 1]
    accounting_date = date.fromisoformat(
        f"{source.source_purchase_reconciliation.accounting_period}-15"
    )
    debit = (
        source.amount_excluding_tax + source.tax_amount
    ).quantize(Decimal("0.01"))
    return {
        "accountsPayableAccount": f"2202.{(index % 3) + 1:02d}",
        "inputTaxAccount": (
            "22210101" if source.invoice_type == "vat_special" else "22210109"
        ),
        "counterpartyAccount": f"1403.{(index % 4) + 1:02d}",
        "supplierAuxiliaryId": source.supplier_id,
        "departmentId": f"DEPT-{(index % 3) + 1:02d}",
        "costCenterId": f"CC-{index:02d}",
        "projectId": f"PRJ-PURCHASE-{index:02d}",
        "paymentTermsCode": f"NET{terms_days}",
        "paymentTermsDays": terms_days,
        "dueDate": (source.invoice_date + timedelta(days=terms_days)).isoformat(),
        "accountingDate": accounting_date.isoformat(),
        "accountingPeriod": source.source_purchase_reconciliation.accounting_period,
        "periodStatus": "open",
        "debitTotal": str(debit),
        "creditTotal": str(source.payable_amount),
        "sourceDraftVersion": source.version,
    }


def save_if_changed(obj, values):
    changed = []
    for field, value in values.items():
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed.append(field)
    if changed:
        obj.save(update_fields=changed)
    return bool(changed)


class Command(BaseCommand):
    help = "Idempotently ensure the V46 payable confirmation prepare canary pool"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite canary batch: {BATCH_ID}")
        source_lineages = list(batch.lineages.order_by("scenario_code"))
        if len(source_lineages) < 8:
            raise CommandError("V45.3 prerequisite has fewer than eight lineages")
        sources = []
        for lineage in source_lineages:
            draft_no = next(
                (
                    number
                    for number in lineage.upstream_object_nos
                    if str(number).startswith("APD")
                ),
                lineage.current_object_no
                if lineage.current_object_no.startswith("APD")
                else "",
            )
            source = PurchaseAccountsPayableDraft.objects.select_related(
                "source_purchase_reconciliation"
            ).filter(draft_no=draft_no, tenant_id=TENANT_ID).first()
            if not source:
                raise CommandError(
                    f"Missing formal AP draft for {lineage.scenario_code}: {draft_no}"
                )
            sources.append((lineage, source))
        User = get_user_model()
        actor = User.objects.filter(username="pce-v46-canary").first()
        if not actor:
            actor = User.objects.create_superuser(
                username="pce-v46-canary",
                email="pce-v46-canary@example.invalid",
                password=None,
            )
        before_count = PayableConfirmationPrepare.objects.filter(
            tenant_id=TENANT_ID
        ).count()
        results = []
        changed = False
        for index, (lineage, source) in enumerate(sources, 1):
            idem_key = f"pcp-canary-{lineage.scenario_code.lower().replace('_', '-')}"
            outcome = generate_payable_confirmation_prepare(
                user=actor,
                source=source,
                accounting_data=accounting_data(source, index),
                idempotency_key=idem_key,
                expected_source_version=source.version,
            )
            obj = PayableConfirmationPrepare.objects.select_related(
                "accounting_snapshot", "audit_record", "number_reservation",
                "business_transaction",
            ).get(pk=outcome["data"]["id"])
            upstream = list(lineage.upstream_object_nos)
            if obj.prepare_no not in upstream:
                upstream.append(obj.prepare_no)
            relation_hash = canonical_hash({
                "canaryLineageId": lineage.canary_lineage_id,
                "upstreamObjectNos": upstream,
                "sourceKey": obj.source_key,
                "sourceSnapshotHash": obj.source_snapshot_hash,
                "accountingSnapshotHash": obj.accounting_snapshot.snapshot_hash,
            })
            lineage_values = {
                "scenario_class": "pass_through",
                "scenario_role": SUCCESS_ROLES[lineage.scenario_code],
                "current_module_code": "payable-confirmation-prepare",
                "current_object_type": "payableConfirmationPrepare",
                "current_object_id": obj.pk,
                "current_object_no": obj.prepare_no,
                "downstream_eligible": True,
                "reserved_for_next_module": "payment_request_prepare",
                "next_stage_consumed": False,
                "upstream_object_nos": upstream,
                "source_relation_hash": relation_hash,
                "blocking_module": "",
                "blocking_rule_code": "",
                "blocking_reason": "",
            }
            changed = save_if_changed(lineage, lineage_values) or changed
            results.append({
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "scenarioRole": lineage_values["scenario_role"],
                "sourceDraftNo": source.draft_no,
                "prepareNo": obj.prepare_no,
                "accountingSnapshotId": obj.accounting_snapshot.pk,
                "accountingSnapshotHash": obj.accounting_snapshot.snapshot_hash,
                "validationExecutionId": obj.validation_executions.get(
                    validation_version=1
                ).pk,
                "idempotencyKey": obj.idempotency_key,
                "numberReservationStatus": obj.number_reservation.status,
                "transactionId": obj.business_transaction.transaction_id,
                "transactionStatus": obj.business_transaction.commit_status,
                "auditRecordId": obj.audit_record_id,
                "auditStatus": obj.audit_record.result,
                "sourceRelationHash": relation_hash,
                "eligibility": outcome["data"]["eligibility"],
            })
        with transaction.atomic():
            first_source = sources[0][1]
            for code, role, rule, reason in BLOCKED_SCENARIOS:
                values = {
                    "scenario_class": "blocked",
                    "scenario_role": role,
                    "blocking_module": "payable-confirmation-prepare",
                    "blocking_rule_code": rule,
                    "blocking_reason": reason,
                    "current_last_valid_object_no": first_source.draft_no,
                    "formal_object_count": 0,
                    "next_step_allowed": False,
                    "scenario_hash": canonical_hash({
                        "version": VERSION,
                        "scenarioCode": code,
                        "blockingRuleCode": rule,
                        "blockingReason": reason,
                    }),
                }
                row = PayableConfirmationCanaryScenario.objects.filter(
                    batch_id=BATCH_ID, scenario_code=code
                ).first()
                if row:
                    changed = save_if_changed(row, values) or changed
                else:
                    PayableConfirmationCanaryScenario.objects.create(
                        batch_id=BATCH_ID,
                        scenario_code=code,
                        **values,
                    )
                    changed = True
        after_count = PayableConfirmationPrepare.objects.filter(
            tenant_id=TENANT_ID
        ).count()
        production_count = PayableConfirmationPrepare.objects.exclude(
            tenant_id=TENANT_ID
        ).count()
        payload = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "应付确认准备",
            "sourceDocumentType": "purchaseAccountsPayableDraft",
            "canaryBatchId": BATCH_ID,
            "beforeFormalCount": before_count,
            "formalPayableConfirmationPrepareCount": after_count,
            "downstreamEligibleSourceCount": sum(
                1 for row in results if row["eligibility"]["eligible"]
            ),
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": len(BLOCKED_SCENARIOS),
            "nextModuleCode": "payment_request_prepare",
            "paymentRequestPrepareCreated": False,
            "productionTenantFormalObjectCount": production_count,
            "changed": changed or before_count != after_count,
            "lineages": results,
        }
        if (
            after_count < 8
            or payload["downstreamEligibleSourceCount"] < 8
            or production_count != 0
        ):
            raise CommandError(json.dumps(payload, ensure_ascii=False))
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
