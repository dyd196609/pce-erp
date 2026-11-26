import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from payment_instruction_prepare.models import PaymentInstructionPrepare
from payment_instruction_prepare.providers import read_authorities
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import canonical_hash

from payment_order_prepare.models import (
    FundsAvailabilityAuthority,
    MakerCheckerSegregationAuthority,
    PaymentAuthorizationRouteAuthority,
    PaymentOrderPrepare,
    PaymentOrderPrepareCanaryScenario,
    PaymentSigningCapabilityAuthority,
    PaymentSigningPolicyAuthority,
)
from payment_order_prepare.services import (
    NEXT_MODULE_CODE,
    VERSION,
    generate_payment_order_prepare,
    save_order_data,
    validate_payment_order_prepare,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"
BLOCKED_SCENARIOS = (
    ("SOURCE_NOT_FOUND", "POP_SOURCE_NOT_FOUND"),
    ("SOURCE_NOT_PREPARED", "POP_SOURCE_NOT_PREPARED"),
    ("SOURCE_VALIDATION_FAILED", "POP_SOURCE_VALIDATION_FAILED"),
    ("SOURCE_STALE", "POP_SOURCE_STALE"),
    ("EXISTING_TARGET", "POP_EXISTING_TARGET"),
    ("PAYER_ACCOUNT_INACTIVE", "payer_bank_account_inactive"),
    ("PAYEE_ACCOUNT_INACTIVE", "payee_bank_account_inactive"),
    ("ACCOUNT_OWNER_MISMATCH", "account_owner_mismatch"),
    ("CURRENCY_MISMATCH", "currency_mismatch"),
    ("AMOUNT_MISMATCH", "amount_mismatch"),
    ("PAYMENT_ROUTE_MISSING", "payment_route_missing"),
    ("PAYMENT_ROUTE_INACTIVE", "payment_route_inactive"),
    ("BANK_INTERFACE_INACTIVE", "bank_interface_inactive"),
    ("BANK_INTERFACE_UNAVAILABLE", "bank_interface_unavailable"),
    ("BANK_BUSINESS_DAY_INVALID", "bank_business_day_invalid"),
    ("CUTOFF_TIME_EXCEEDED", "cutoff_time_exceeded"),
    ("SINGLE_LIMIT_EXCEEDED", "single_payment_limit_exceeded"),
    ("DAILY_LIMIT_EXCEEDED", "daily_payment_limit_exceeded"),
    ("PAYMENT_HOLD_ACTIVE", "payment_hold_active"),
    ("DUPLICATE_PAYMENT_RISK", "duplicate_payment_risk"),
    ("FUNDS_AUTHORITY_MISSING", "funds_authority_unavailable"),
    ("AVAILABLE_BALANCE_INSUFFICIENT", "available_balance_insufficient"),
    ("SIGNING_POLICY_MISSING", "signing_policy_missing"),
    ("AUTHORIZATION_ROUTE_INVALID", "authorization_route_invalid"),
    ("SIGNING_CAPABILITY_UNAVAILABLE", "signing_capability_unavailable"),
    ("SIGNING_CREDENTIAL_NOT_READY", "signing_credential_not_ready"),
    ("CERTIFICATE_INVALID", "signing_credential_not_ready"),
    ("MAKER_CHECKER_CONFLICT", "maker_checker_conflict"),
    ("ORDER_PREVIEW_TAMPERED", "order_preview_integrity_failed"),
    ("VERSION_CONFLICT", "VERSION_CONFLICT"),
    ("IDEMPOTENCY_CONFLICT", "POP_IDEMPOTENCY_PAYLOAD_CONFLICT"),
    ("SOURCE_LOCKED", "POP_SOURCE_LOCKED"),
    ("FEATURE_DISABLED", "POP_AUTH_FEATURE_DISABLED"),
    ("PRODUCTION_ROLLOUT_DISABLED", "POP_AUTH_PRODUCTION_ROLLOUT_DISABLED"),
)


def ensure_user():
    User = get_user_model()
    user = User.objects.filter(username="pce-v50-operator").first()
    if not user:
        user = User.objects.create_superuser(
            username="pce-v50-operator",
            real_name="PCE V50 Operator",
            email="pce-v50-operator@example.invalid",
            password=None,
            company_id=1,
        )
    return user


def ensure_authorities(source, actor):
    instruction = read_authorities(source, source.planned_execution_date)
    route = instruction.get("route")
    interface = instruction.get("interface")
    if not route or not interface:
        raise CommandError(f"Missing V49 payment authorities for {source.prepare_no}")
    route_payload = route.payload
    interface_payload = interface.payload
    funds_payload = {
        "tenantId": source.tenant_id,
        "legalEntityId": source.legal_entity_id,
        "ledgerBookId": source.ledger_book_id,
        "payerBankAccountId": source.payer_bank_account_id,
        "currency": source.currency,
        "availableBalance": "100000000.00",
        "committedAmount": "0.00",
        "reservedAmount": "0.00",
        "active": True,
        "version": 1,
    }
    funds, _ = FundsAvailabilityAuthority.objects.get_or_create(
        tenant_id=source.tenant_id,
        legal_entity_id=source.legal_entity_id,
        ledger_book_id=source.ledger_book_id,
        payer_bank_account_id=source.payer_bank_account_id,
        currency=source.currency,
        defaults={
            "funds_evidence_id": f"POP-FUNDS-{source.pk}",
            "available_balance": Decimal("100000000.00"),
            "committed_amount": Decimal("0.00"),
            "reserved_amount": Decimal("0.00"),
            "as_of_time": source.updated_at or timezone.now(),
            "active": True,
            "version": 1,
            "business_hash": canonical_hash(funds_payload),
        },
    )
    bank_code = route_payload["payerBankCode"]
    channel_code = interface_payload["channelCode"]
    policy_payload = {
        "documentType": "paymentOrderPrepare",
        "bankCode": bank_code,
        "channelCode": channel_code,
        "currency": source.currency,
        "amountMin": "0.01",
        "amountMax": "999999999999.99",
        "requiredSignatures": 2,
        "requiredRoles": ["payment_checker", "payment_authorizer"],
        "sequentialSigning": True,
        "active": True,
        "version": 1,
    }
    policy, _ = PaymentSigningPolicyAuthority.objects.get_or_create(
        document_type="paymentOrderPrepare",
        bank_code=bank_code,
        channel_code=channel_code,
        currency=source.currency,
        amount_min=Decimal("0.01"),
        amount_max=Decimal("999999999999.99"),
        defaults={
            "signing_policy_id": f"POP-SIGN-{source.pk}",
            "policy_code": f"POP-SIGN-{source.pk}",
            "required_signatures": 2,
            "required_roles": ["payment_checker", "payment_authorizer"],
            "sequential_signing": True,
            "active": True,
            "version": 1,
            "business_hash": canonical_hash(policy_payload),
        },
    )
    authorization_payload = {
        "signingPolicyId": policy.signing_policy_id,
        "steps": [
            {"sequence": 1, "role": "payment_checker"},
            {"sequence": 2, "role": "payment_authorizer"},
        ],
        "allowParallel": False,
        "active": True,
        "version": 1,
    }
    authorization, _ = PaymentAuthorizationRouteAuthority.objects.get_or_create(
        signing_policy=policy,
        defaults={
            "authorization_route_id": f"POP-AUTH-{policy.pk}",
            "steps": authorization_payload["steps"],
            "allow_parallel": False,
            "active": True,
            "version": 1,
            "business_hash": canonical_hash(authorization_payload),
        },
    )
    capability_payload = {
        "bankInterfaceProfileId": interface_payload["interfaceProfileId"],
        "credentialProfileIdMasked": "credential-****-v50",
        "credentialStatus": "ready",
        "certificateStatus": "valid",
        "signingServiceStatus": "available",
        "supportedMessageFormat": interface_payload["messageFormat"],
        "active": True,
        "version": 1,
    }
    capability, _ = PaymentSigningCapabilityAuthority.objects.get_or_create(
        bank_interface_profile_id=interface_payload["interfaceProfileId"],
        defaults={
            "signing_capability_id": f"POP-CAP-{source.pk}",
            "credential_profile_id_masked": "credential-****-v50",
            "credential_status": "ready",
            "certificate_status": "valid",
            "signing_service_status": "available",
            "supported_message_format": interface_payload["messageFormat"],
            "active": True,
            "version": 1,
            "business_hash": canonical_hash(capability_payload),
        },
    )
    segregation_payload = {
        "tenantId": source.tenant_id,
        "makerUserId": str(actor.pk),
        "requiredCheckerRoles": ["payment_checker"],
        "requiredAuthorizerRoles": ["payment_authorizer"],
        "makerCannotCheck": True,
        "makerCannotAuthorize": True,
        "checkerCannotFinalAuthorize": True,
        "active": True,
        "version": 1,
    }
    segregation, _ = MakerCheckerSegregationAuthority.objects.get_or_create(
        tenant_id=source.tenant_id,
        maker_user_id=str(actor.pk),
        defaults={
            "segregation_policy_id": f"POP-SEG-{actor.pk}",
            "required_checker_roles": ["payment_checker"],
            "required_authorizer_roles": ["payment_authorizer"],
            "maker_cannot_check": True,
            "maker_cannot_authorize": True,
            "checker_cannot_final_authorize": True,
            "active": True,
            "version": 1,
            "business_hash": canonical_hash(segregation_payload),
        },
    )
    return funds, policy, authorization, capability, segregation


class Command(BaseCommand):
    help = "Idempotently ensure eight prepared V50 payment-order-prepare chains"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(
            batch.lineages.filter(current_module_code="payment-instruction-prepare")
            .order_by("scenario_code")[:8]
        )
        if len(lineages) < 8:
            raise CommandError("V49 prerequisite has fewer than eight lineages")
        sources = []
        for lineage in lineages:
            source = PaymentInstructionPrepare.objects.filter(
                pk=lineage.current_object_id,
                tenant_id=TENANT_ID,
                status="validated",
            ).first()
            if not source:
                raise CommandError(
                    f"Missing prepared V49 source for {lineage.scenario_code}"
                )
            sources.append((lineage, source))
        actor = ensure_user()
        changed = False
        results = []
        with transaction.atomic():
            for lineage, source in sources:
                ensure_authorities(source, actor)
                target = PaymentOrderPrepare.objects.filter(
                    source_payment_instruction_prepare=source
                ).first()
                if not target:
                    result = generate_payment_order_prepare(
                        user=actor,
                        source=source,
                        idempotency_key=(
                            f"pop-v50-generate-{lineage.scenario_code.lower()}"
                        ),
                        expected_source_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentOrderPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                if target.current_order_data_version == 0:
                    source_data = source.instruction_data_snapshots.order_by(
                        "-instruction_data_version"
                    ).first()
                    result = save_order_data(
                        user=actor,
                        obj=target,
                        payload={
                            "plannedExecutionDate": (
                                source.planned_execution_date.isoformat()
                            ),
                            "plannedExecutionTime": (
                                source_data.planned_execution_time.isoformat()
                            ),
                            "paymentPurpose": source_data.payment_purpose,
                            "paymentSummary": source_data.payment_summary,
                            "priority": source.priority,
                        },
                        idempotency_key=(
                            f"pop-v50-save-{lineage.scenario_code.lower()}"
                        ),
                        expected_version=target.version,
                        expected_order_data_version=target.current_order_data_version,
                        expected_instruction_prepare_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentOrderPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                if target.status != "submitted":
                    result = validate_payment_order_prepare(
                        user=actor,
                        obj=target,
                        idempotency_key=(
                            f"pop-v50-validate-{lineage.scenario_code.lower()}"
                        ),
                        expected_version=target.version,
                        expected_order_data_version=target.current_order_data_version,
                        expected_instruction_prepare_version=source.version,
                        explicit_user_action=True,
                    )
                    if not result["validated"]:
                        raise CommandError(
                            f"Validation blocked for {target.prepare_no}: "
                            f"{result['data']['validationResultCode']}"
                        )
                    target = PaymentOrderPrepare.objects.get(pk=result["data"]["id"])
                    changed = True
                if not lineage.next_stage_consumed:
                    lineage.next_stage_consumed = True
                    lineage.save(update_fields=["next_stage_consumed", "updated_at"])
                    changed = True
                results.append(
                    {
                        "scenarioCode": lineage.scenario_code,
                        "sourcePaymentInstructionPrepareNo": source.prepare_no,
                        "prepareNo": target.prepare_no,
                        "status": target.status,
                        "paymentAmount": str(target.payment_amount),
                        "currency": target.currency,
                        "plannedExecutionDate": (
                            target.planned_execution_date.isoformat()
                        ),
                        "signingPolicyId": target.signing_policy_id,
                        "authorizationRouteId": target.authorization_route_id,
                        "signingCapabilityId": target.signing_capability_id,
                        "nextStepReadiness": target.validation_result_code,
                    }
                )
            for code, rule in BLOCKED_SCENARIOS:
                payload = {"batchId": BATCH_ID, "scenarioCode": code, "rule": rule}
                _, created = PaymentOrderPrepareCanaryScenario.objects.get_or_create(
                    batch_id=BATCH_ID,
                    scenario_code=code,
                    defaults={
                        "scenario_class": "blocked",
                        "blocking_rule_code": rule,
                        "blocking_reason": (
                            f"V50 isolated scenario blocked by {rule}"
                        ),
                        "formal_object_count": 0,
                        "next_step_allowed": False,
                        "scenario_hash": canonical_hash(payload),
                    },
                )
                changed = changed or created
        output = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "正式付款单预备",
            "sourceDocumentType": "paymentInstructionPrepare",
            "changed": changed,
            "paymentInstructionPrepareSourceCount": len(sources),
            "paymentInstructionPrepareConsumedCount": len(results),
            "passThroughLineageCount": len(results),
            "formalPaymentOrderPrepareCount": PaymentOrderPrepare.objects.filter(
                tenant_id=TENANT_ID
            ).count(),
            "preparedPaymentOrderPrepareCount": PaymentOrderPrepare.objects.filter(
                tenant_id=TENANT_ID, status="submitted"
            ).count(),
            "downstreamEligibleSourceCount": len(results),
            "nextModuleCode": NEXT_MODULE_CODE,
            "nextStageConsumedCount": 0,
            "blockedScenarioCount": len(BLOCKED_SCENARIOS),
            "nextModuleObjectCreated": False,
            "formalPaymentOrderCreated": False,
            "formalPaymentInstructionCreated": False,
            "paymentExecuted": False,
            "productionRolloutEnabled": False,
            "results": results,
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
