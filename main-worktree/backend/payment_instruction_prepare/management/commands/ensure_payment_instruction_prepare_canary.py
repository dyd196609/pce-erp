import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payment_request.models import PaymentRequest
from payment_request_prepare.models import (
    PayeeBankAccountAuthority,
    PayerBankAccountAuthority,
)
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import canonical_hash

from payment_instruction_prepare.models import (
    BankInterfaceProfileAuthority,
    BankPaymentCalendarAuthority,
    PaymentInstructionPrepare,
    PaymentInstructionPrepareCanaryScenario,
    PaymentLimitAuthority,
    PaymentRouteAuthority,
)
from payment_instruction_prepare.services import (
    NEXT_MODULE_CODE,
    VERSION,
    generate_payment_instruction_prepare,
    save_instruction_data,
    validate_instruction_prepare,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"
BLOCKED_SCENARIOS = (
    ("SOURCE_NOT_FOUND", "PIP_SOURCE_NOT_FOUND"),
    ("SOURCE_NOT_APPROVED", "PIP_SOURCE_NOT_APPROVED"),
    ("APPROVAL_EVIDENCE_INCOMPLETE", "PIP_APPROVAL_EVIDENCE_INCOMPLETE"),
    ("SOURCE_STALE", "PIP_SOURCE_STALE"),
    ("EXISTING_TARGET", "PIP_EXISTING_TARGET"),
    ("PAYER_ACCOUNT_INACTIVE", "payer_bank_account_inactive"),
    ("PAYEE_ACCOUNT_INACTIVE", "payee_bank_account_inactive"),
    ("ACCOUNT_OWNER_MISMATCH", "account_owner_mismatch"),
    ("CURRENCY_MISMATCH", "currency_mismatch"),
    ("AMOUNT_MISMATCH", "amount_mismatch"),
    ("PAYMENT_ROUTE_MISSING", "payment_route_missing"),
    ("PAYMENT_ROUTE_INACTIVE", "payment_route_inactive"),
    ("PAYMENT_ROUTE_NOT_SUPPORTED", "payment_route_not_supported"),
    ("BANK_INTERFACE_INACTIVE", "bank_interface_inactive"),
    ("BANK_INTERFACE_UNAVAILABLE", "bank_interface_not_available"),
    ("BANK_BUSINESS_DAY_INVALID", "bank_business_day_invalid"),
    ("CUTOFF_TIME_EXCEEDED", "cutoff_time_exceeded"),
    ("SINGLE_LIMIT_EXCEEDED", "single_payment_limit_exceeded"),
    ("DAILY_LIMIT_EXCEEDED", "daily_payment_limit_exceeded"),
    ("PAYMENT_HOLD_ACTIVE", "payment_hold_active"),
    ("DUPLICATE_PAYMENT_RISK", "duplicate_payment_risk"),
    ("VERSION_CONFLICT", "VERSION_CONFLICT"),
)


def ensure_user():
    User = get_user_model()
    user = User.objects.filter(username="pce-v49-operator").first()
    if not user:
        user = User.objects.create_superuser(
            username="pce-v49-operator", real_name="PCE V49 Operator",
            email="pce-v49-operator@example.invalid", password=None, company_id=1,
        )
    return user


def ensure_authorities(source):
    payer = PayerBankAccountAuthority.objects.filter(
        bank_account_id=source.payer_bank_account_id
    ).first()
    payee = PayeeBankAccountAuthority.objects.filter(
        bank_account_id=source.payee_bank_account_id
    ).first()
    if not payer or not payee:
        raise CommandError(f"Missing V47 bank authority for {source.request_no}")
    route_code = f"ROUTE-{payer.bank_account_id}-{payee.bank_account_id}"
    route_payload = {
        "routeCode": route_code, "paymentMethodCode": source.payment_method_code,
        "payerBankCode": payer.bank_name, "payeeBankCode": payee.bank_code,
        "currency": source.currency, "version": 1,
    }
    route, _ = PaymentRouteAuthority.objects.get_or_create(
        route_code=route_code,
        defaults={
            "route_id": f"PIP-ROUTE-{source.pk}",
            "payment_method_code": source.payment_method_code,
            "payer_bank_code": payer.bank_name, "payee_bank_code": payee.bank_code,
            "currency": source.currency, "amount_min": Decimal("0.01"),
            "amount_max": Decimal("999999999999.99"), "priority": source.pk,
            "active": True, "version": 1,
            "business_hash": canonical_hash(route_payload),
        },
    )
    interface_payload = {
        "bankCode": payer.bank_name, "channelCode": "PCE_CANARY_BANK_API",
        "currencies": [source.currency],
        "methods": [source.payment_method_code], "version": 1,
    }
    interface, _ = BankInterfaceProfileAuthority.objects.get_or_create(
        bank_code=payer.bank_name, channel_code="PCE_CANARY_BANK_API",
        defaults={
            "interface_profile_id": f"PIP-IF-{source.pk}",
            "supported_currencies": [source.currency],
            "supported_payment_methods": [source.payment_method_code],
            "message_format": "ISO20022-preview-only",
            "connection_status": "available", "payment_enabled": True,
            "active": True, "version": 1,
            "business_hash": canonical_hash(interface_payload),
        },
    )
    calendar_payload = {
        "bankCode": payer.bank_name,
        "date": source.planned_payment_date.isoformat(),
        "businessDay": True, "cutoffTime": "23:59:00", "version": 1,
    }
    BankPaymentCalendarAuthority.objects.get_or_create(
        bank_code=payer.bank_name, calendar_date=source.planned_payment_date,
        defaults={
            "business_day": True, "payment_allowed": True,
            "cutoff_time": "23:59:00", "timezone": "Asia/Shanghai",
            "version": 1, "business_hash": canonical_hash(calendar_payload),
        },
    )
    limit_payload = {
        "legalEntityId": source.legal_entity_id,
        "payerBankAccountId": source.payer_bank_account_id,
        "currency": source.currency, "single": "999999999999.99",
        "daily": "999999999999.99", "version": 1,
    }
    PaymentLimitAuthority.objects.get_or_create(
        legal_entity_id=source.legal_entity_id,
        payer_bank_account_id=source.payer_bank_account_id,
        currency=source.currency,
        defaults={
            "single_payment_limit": Decimal("999999999999.99"),
            "daily_payment_limit": Decimal("999999999999.99"),
            "current_daily_committed_amount": Decimal("0.00"),
            "active": True, "version": 1,
            "business_hash": canonical_hash(limit_payload),
        },
    )
    return route, interface


class Command(BaseCommand):
    help = "Idempotently ensure eight prepared V49 payment-instruction-prepare chains"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(batch.lineages.order_by("scenario_code"))
        if len(lineages) < 8:
            raise CommandError("V48 prerequisite has fewer than eight lineages")
        sources = []
        for lineage in lineages[:8]:
            source = PaymentRequest.objects.filter(
                request_no=lineage.current_object_no, tenant_id=TENANT_ID
            ).first()
            if not source:
                source = PaymentRequest.objects.filter(
                    request_no__in=lineage.upstream_object_nos, tenant_id=TENANT_ID
                ).first()
            if not source or source.status != "approved":
                raise CommandError(f"Missing approved V48 source for {lineage.scenario_code}")
            sources.append((lineage, source))
        actor = ensure_user()
        changed = False
        results = []
        with transaction.atomic():
            for lineage, source in sources:
                route, interface = ensure_authorities(source)
                target = PaymentInstructionPrepare.objects.filter(
                    source_payment_request=source
                ).first()
                if not target:
                    result = generate_payment_instruction_prepare(
                        user=actor, source=source,
                        idempotency_key=f"pip-v49-generate-{lineage.scenario_code.lower()}",
                        expected_source_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentInstructionPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                if target.current_instruction_data_version == 0:
                    result = save_instruction_data(
                        user=actor, obj=target,
                        payload={
                            "plannedExecutionDate": source.planned_payment_date.isoformat(),
                            "plannedExecutionTime": "10:00:00",
                            "paymentAmount": str(source.payment_amount),
                            "currency": source.currency,
                            "paymentPurpose": source.payment_purpose,
                            "paymentSummary": source.payment_summary,
                            "priority": "normal",
                            "instructionReference": target.prepare_no,
                        },
                        idempotency_key=f"pip-v49-save-{lineage.scenario_code.lower()}",
                        expected_version=target.version, explicit_user_action=True,
                    )
                    target = PaymentInstructionPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                if target.status != "validated":
                    result = validate_instruction_prepare(
                        user=actor, obj=target,
                        idempotency_key=f"pip-v49-validate-{lineage.scenario_code.lower()}",
                        expected_version=target.version,
                        expected_instruction_data_version=target.current_instruction_data_version,
                        expected_source_version=source.version,
                        explicit_user_action=True,
                    )
                    if not result["validated"]:
                        raise CommandError(
                            f"Validation blocked for {target.prepare_no}: "
                            f"{result['data']['validationResultCode']}"
                        )
                    target = PaymentInstructionPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                upstream = list(lineage.upstream_object_nos)
                for number in (source.request_no, target.prepare_no):
                    if number not in upstream:
                        upstream.append(number)
                values = {
                    "current_module_code": "payment-instruction-prepare",
                    "current_object_type": "paymentInstructionPrepare",
                    "current_object_id": target.pk,
                    "current_object_no": target.prepare_no,
                    "downstream_eligible": True,
                    "reserved_for_next_module": NEXT_MODULE_CODE,
                    "next_stage_consumed": False,
                    "upstream_object_nos": upstream,
                    "source_relation_hash": canonical_hash({
                        "source": source.request_no, "target": target.prepare_no,
                        "relationship": "generated_from",
                    }),
                }
                dirty = []
                for field, value in values.items():
                    if getattr(lineage, field) != value:
                        setattr(lineage, field, value)
                        dirty.append(field)
                if dirty:
                    lineage.save(update_fields=dirty + ["updated_at"])
                    changed = True
                results.append({
                    "scenarioCode": lineage.scenario_code,
                    "sourcePaymentRequestNo": source.request_no,
                    "prepareNo": target.prepare_no, "status": target.status,
                    "paymentAmount": str(target.payment_amount),
                    "currency": target.currency,
                    "plannedExecutionDate": target.planned_execution_date.isoformat(),
                    "paymentRouteCode": route.route_code,
                    "bankInterfaceProfileId": interface.interface_profile_id,
                })
            for code, rule in BLOCKED_SCENARIOS:
                payload = {"batchId": BATCH_ID, "scenarioCode": code, "rule": rule}
                _, created = PaymentInstructionPrepareCanaryScenario.objects.get_or_create(
                    batch_id=BATCH_ID, scenario_code=code,
                    defaults={
                        "scenario_class": "blocked", "blocking_rule_code": rule,
                        "blocking_reason": f"V49 isolated scenario blocked by {rule}",
                        "formal_object_count": 0, "next_step_allowed": False,
                        "scenario_hash": canonical_hash(payload),
                    },
                )
                changed = changed or created
        output = {
            "result": "passed", "version": VERSION, "changed": changed,
            "paymentRequestSourceCount": len(sources),
            "paymentRequestConsumedCount": len(results),
            "passThroughLineageCount": len(results),
            "formalPaymentInstructionPrepareCount": PaymentInstructionPrepare.objects.filter(
                tenant_id=TENANT_ID
            ).count(),
            "preparedPaymentInstructionPrepareCount": PaymentInstructionPrepare.objects.filter(
                tenant_id=TENANT_ID, status="prepared"
            ).count(),
            "downstreamEligibleSourceCount": len(results),
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": len(BLOCKED_SCENARIOS),
            "nextModuleObjectCreated": False,
            "formalPaymentInstructionCreated": False,
            "paymentExecuted": False,
            "productionRolloutEnabled": False,
            "results": results,
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
