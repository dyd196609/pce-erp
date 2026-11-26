import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import canonical_hash

from payment_request_prepare.models import (
    PayeeBankAccountAuthority,
    PayerBankAccountAuthority,
    PaymentCalendarAuthority,
    PaymentHoldAuthority,
    PaymentMethodAuthority,
    PaymentRequestPrepare,
    PaymentRequestPrepareCanaryScenario,
)
from payment_request_prepare.services import (
    VERSION,
    generate_payment_request_prepare,
    save_payment_request_prepare_data,
    validate_payment_request_prepare,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"

BLOCKED_SCENARIOS = (
    ("PAYEE_ACCOUNT_MISSING", "payee_account_missing", "PRP_DATA_PAYEE_ACCOUNT_REQUIRED"),
    ("PAYEE_ACCOUNT_INACTIVE", "payee_account_inactive", "PRP_VALIDATE_PAYEE_ACCOUNT_ACTIVE"),
    ("PAYEE_OWNER_MISMATCH", "payee_owner_mismatch", "PRP_VALIDATE_PAYEE_OWNER_MATCH"),
    ("PAYER_ACCOUNT_MISSING", "payer_account_missing", "PRP_DATA_PAYER_ACCOUNT_REQUIRED"),
    ("PAYER_ACCOUNT_INACTIVE", "payer_account_inactive", "PRP_VALIDATE_PAYER_ACCOUNT_ACTIVE"),
    ("PAYER_SCOPE_MISMATCH", "payer_scope_mismatch", "PRP_VALIDATE_PAYER_SCOPE_MATCH"),
    ("ACCOUNT_CURRENCY_MISMATCH", "account_currency_mismatch", "PRP_VALIDATE_ACCOUNT_CURRENCY"),
    ("PAYMENT_METHOD_INVALID", "payment_method_invalid", "PRP_VALIDATE_PAYMENT_METHOD"),
    ("PAYMENT_DATE_INVALID", "payment_date_invalid", "PRP_VALIDATE_PAYMENT_DATE"),
    ("PAYMENT_HOLD_ACTIVE", "payment_hold_active", "PRP_VALIDATE_PAYMENT_HOLD"),
    ("PAYMENT_AMOUNT_MISMATCH", "payment_amount_mismatch", "PRP_VALIDATE_AMOUNT"),
    ("SOURCE_STALE", "source_stale", "PRP_VALIDATE_SOURCE_CURRENT"),
)


def update_if_changed(obj, values):
    changed = []
    for field, value in values.items():
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed.append(field)
    if changed:
        obj.save(update_fields=changed)
    return bool(changed)


def authority_defaults(source, planned_date, index):
    payee_id = f"PAYEE-{source.supplier_id}"
    payer_id = f"PAYER-{source.legal_entity_id}-{source.ledger_book_id}"
    payee_payload = {
        "tenant_id": TENANT_ID,
        "supplier_id": source.supplier_id,
        "account_name": source.supplier_name,
        "masked_account_no": f"**** **** **** {1100 + index:04d}",
        "bank_name": "采购金丝雀收款银行",
        "bank_branch": "演示支行",
        "bank_code": "PCE-DEMO-BANK",
        "currency": source.currency,
        "active": True,
        "payment_enabled": True,
        "version": 1,
    }
    payee_payload["business_hash"] = canonical_hash(payee_payload)
    PayeeBankAccountAuthority.objects.get_or_create(
        bank_account_id=payee_id,
        defaults=payee_payload,
    )
    payer_payload = {
        "tenant_id": TENANT_ID,
        "legal_entity_id": source.legal_entity_id,
        "ledger_book_id": source.ledger_book_id,
        "account_name": source.legal_entity_name,
        "masked_account_no": f"**** **** **** {2200 + index:04d}",
        "bank_name": "采购金丝雀付款银行",
        "currency": source.currency,
        "available_for_payment": True,
        "active": True,
        "version": 1,
    }
    payer_payload["business_hash"] = canonical_hash(payer_payload)
    PayerBankAccountAuthority.objects.get_or_create(
        bank_account_id=payer_id,
        defaults=payer_payload,
    )
    method_payload = {
        "payment_method_name": "银行转账",
        "active": True,
        "supported_currency": [source.currency],
        "requires_bank_account": True,
        "requires_approval": True,
        "version": 1,
    }
    method_payload["business_hash"] = canonical_hash(method_payload)
    PaymentMethodAuthority.objects.get_or_create(
        payment_method_code="BANK_TRANSFER",
        defaults=method_payload,
    )
    calendar_payload = {
        "business_day": True,
        "payment_allowed": True,
        "holiday_code": "",
        "version": 1,
    }
    calendar_payload["business_hash"] = canonical_hash({
        **calendar_payload,
        "date": planned_date.isoformat(),
    })
    PaymentCalendarAuthority.objects.get_or_create(
        calendar_date=planned_date,
        defaults=calendar_payload,
    )
    hold_payload = {
        "hold_status": "released",
        "hold_reason": "",
        "release_required": False,
        "version": 1,
    }
    hold_payload["business_hash"] = canonical_hash({
        **hold_payload,
        "sourceObjectId": str(source.pk),
    })
    PaymentHoldAuthority.objects.get_or_create(
        source_object_id=str(source.pk),
        defaults=hold_payload,
    )
    return payee_id, payer_id


class Command(BaseCommand):
    help = "Idempotently ensure the V47 payment request prepare canary pool"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(batch.lineages.order_by("scenario_code"))
        if len(lineages) < 8:
            raise CommandError("V46 prerequisite has fewer than eight lineages")
        sources = []
        for lineage in lineages:
            confirmation_no = next(
                (
                    number for number in lineage.upstream_object_nos
                    if str(number).startswith("PCP")
                ),
                lineage.current_object_no
                if lineage.current_object_no.startswith("PCP")
                else "",
            )
            source = PayableConfirmationPrepare.objects.select_related(
                "source_purchase_accounts_payable_draft__source_purchase_invoice_prepare",
                "source_purchase_accounts_payable_draft__source_purchase_reconciliation",
                "accounting_snapshot",
                "audit_record",
            ).filter(
                prepare_no=confirmation_no,
                tenant_id=TENANT_ID,
            ).first()
            if not source:
                raise CommandError(
                    f"Missing formal V46 source for {lineage.scenario_code}: {confirmation_no}"
                )
            sources.append((lineage, source))

        User = get_user_model()
        actor = User.objects.filter(username="pce-v47-canary").first()
        if not actor:
            actor = User.objects.create_superuser(
                username="pce-v47-canary",
                email="pce-v47-canary@example.invalid",
                password=None,
            )

        before_count = PaymentRequestPrepare.objects.filter(tenant_id=TENANT_ID).count()
        results = []
        changed = False
        for index, (lineage, source) in enumerate(sources, 1):
            planned_date = source.due_date
            payee_id, payer_id = authority_defaults(source, planned_date, index)
            generate_key = f"prp-v47-generate-{lineage.scenario_code.lower()}"
            target = PaymentRequestPrepare.objects.filter(
                source_payable_confirmation_prepare=source
            ).first()
            if not target:
                outcome = generate_payment_request_prepare(
                    user=actor,
                    source=source,
                    idempotency_key=generate_key,
                    expected_source_version=source.version,
                    explicit_user_action=True,
                )
                target = PaymentRequestPrepare.objects.get(pk=outcome["data"]["id"])
                changed = True
            if target.current_payment_data_version == 0:
                save_payment_request_prepare_data(
                    user=actor,
                    obj=target,
                    payload={
                        "payeeBankAccountId": payee_id,
                        "payerBankAccountId": payer_id,
                        "paymentMethodCode": "BANK_TRANSFER",
                        "plannedPaymentDate": planned_date.isoformat(),
                        "paymentAmount": str(source.payable_amount),
                        "paymentPurpose": "采购应付款项",
                        "paymentSummary": f"来源应付确认准备 {source.prepare_no}",
                    },
                    idempotency_key=f"prp-v47-save-{lineage.scenario_code.lower()}",
                    expected_version=target.version,
                    expected_payment_data_version=0,
                    explicit_user_action=True,
                )
                target.refresh_from_db()
                changed = True
            if target.status != "prepared":
                validate_payment_request_prepare(
                    user=actor,
                    obj=target,
                    idempotency_key=f"prp-v47-validate-{lineage.scenario_code.lower()}",
                    expected_version=target.version,
                    expected_payment_data_version=target.current_payment_data_version,
                    expected_confirmation_version=source.version,
                    expected_accounting_data_version=source.accounting_data_version,
                    expected_confirmation_validation_version=source.validation_version,
                    explicit_user_action=True,
                )
                target.refresh_from_db()
                changed = True
            upstream = list(lineage.upstream_object_nos)
            if target.prepare_no not in upstream:
                upstream.append(target.prepare_no)
            relation_hash = canonical_hash({
                "canaryLineageId": lineage.canary_lineage_id,
                "upstreamObjectNos": upstream,
                "sourceKey": target.source_key,
                "sourceSnapshotHash": target.source_snapshot.source_confirmation_hash,
                "paymentDataHash": target.payment_data_snapshots.get(
                    payment_data_version=target.current_payment_data_version
                ).data_hash,
            })
            values = {
                "scenario_class": "pass_through",
                "scenario_role": f"payment_request_prepare_{lineage.scenario_code.lower()}",
                "current_module_code": "payment-request-prepare",
                "current_object_type": "paymentRequestPrepare",
                "current_object_id": target.pk,
                "current_object_no": target.prepare_no,
                "downstream_eligible": True,
                "reserved_for_next_module": "payment_request",
                "next_stage_consumed": False,
                "upstream_object_nos": upstream,
                "source_relation_hash": relation_hash,
                "blocking_module": "",
                "blocking_rule_code": "",
                "blocking_reason": "",
            }
            changed = update_if_changed(lineage, values) or changed
            serialized = target.payment_data_snapshots.get(
                payment_data_version=target.current_payment_data_version
            )
            results.append({
                "canaryLineageId": lineage.canary_lineage_id,
                "scenarioCode": lineage.scenario_code,
                "sourcePayableConfirmationPrepareNo": source.prepare_no,
                "prepareNo": target.prepare_no,
                "status": target.status,
                "paymentDataStatus": target.payment_data_status,
                "validationStatus": target.validation_status,
                "validationResultCode": target.validation_result_code,
                "paymentDataVersion": target.current_payment_data_version,
                "validationVersion": target.current_validation_version,
                "payeeAccountMasked": serialized.payee_account_no_masked,
                "payerAccountMasked": serialized.payer_account_no_masked,
                "numberReservationStatus": target.number_reservation.status,
                "transactionStatus": target.business_transaction.commit_status,
                "auditStatus": target.audit_record.result,
                "sourceRelationHash": relation_hash,
            })

        with transaction.atomic():
            first_source = sources[0][1]
            for code, role, rule in BLOCKED_SCENARIOS:
                values = {
                    "scenario_class": "blocked",
                    "scenario_role": role,
                    "blocking_module": "payment-request-prepare",
                    "blocking_rule_code": rule,
                    "blocking_reason": code,
                    "current_last_valid_object_no": first_source.prepare_no,
                    "formal_object_count": 0,
                    "next_step_allowed": False,
                    "scenario_hash": canonical_hash({
                        "version": VERSION,
                        "scenarioCode": code,
                        "blockingRuleCode": rule,
                    }),
                }
                row = PaymentRequestPrepareCanaryScenario.objects.filter(
                    batch_id=BATCH_ID,
                    scenario_code=code,
                ).first()
                if row:
                    changed = update_if_changed(row, values) or changed
                else:
                    PaymentRequestPrepareCanaryScenario.objects.create(
                        batch_id=BATCH_ID,
                        scenario_code=code,
                        **values,
                    )
                    changed = True

        after_count = PaymentRequestPrepare.objects.filter(tenant_id=TENANT_ID).count()
        eligible_count = PaymentRequestPrepare.objects.filter(
            tenant_id=TENANT_ID,
            status="prepared",
            payment_data_status="complete",
            validation_status="passed",
            validation_result_code="validated",
            validation_issue_count=0,
        ).count()
        production_count = PaymentRequestPrepare.objects.exclude(tenant_id=TENANT_ID).count()
        payload = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "付款申请准备",
            "sourceDocumentType": "payableConfirmationPrepare",
            "canaryBatchId": BATCH_ID,
            "beforeFormalCount": before_count,
            "formalPaymentRequestPrepareCount": after_count,
            "downstreamEligibleSourceCount": eligible_count,
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": len(BLOCKED_SCENARIOS),
            "nextModuleCode": "payment_request",
            "paymentRequestCreated": False,
            "productionTenantFormalObjectCount": production_count,
            "changed": changed or before_count != after_count,
            "lineages": results,
        }
        if after_count < 8 or eligible_count < 8 or production_count != 0:
            raise CommandError(json.dumps(payload, ensure_ascii=False))
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
