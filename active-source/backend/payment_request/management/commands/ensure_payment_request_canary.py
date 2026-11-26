import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payment_request_prepare.models import PaymentRequestPrepare
from purchase_canary.models import PurchaseCanaryBatch
from reconciliation.services import canonical_hash
from workflow_runtime.models import (
    ApprovalPolicyAuthority,
    ApprovalRouteAuthority,
    SegregationOfDutiesAuthority,
    UserOrganizationRoleAuthority,
)

from payment_request.models import PaymentRequest, PaymentRequestCanaryScenario
from payment_request.services import (
    VERSION,
    decide_payment_request,
    generate_payment_request,
    submit_payment_request,
)


BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"
BLOCKED_SCENARIOS = (
    ("SOURCE_NOT_FOUND", "PAYREQ_GATE_SOURCE_EXISTS"),
    ("SOURCE_NOT_PREPARED", "PAYREQ_GATE_PREPARE_PREPARED"),
    ("SOURCE_STALE", "PAYREQ_GATE_SOURCE_VERSIONS_CURRENT"),
    ("EXISTING_TARGET", "PAYREQ_GATE_NO_EXISTING_TARGET"),
    ("PAYMENT_HOLD_ACTIVE", "PAYREQ_GATE_NO_PAYMENT_HOLD"),
    ("APPROVAL_POLICY_MISSING", "PAYREQ_SUBMIT_APPROVAL_POLICY_FOUND"),
    ("APPROVAL_ROUTE_INVALID", "PAYREQ_SUBMIT_APPROVAL_ROUTE_VALID"),
    ("SELF_APPROVAL_BLOCKED", "PAYREQ_APPROVE_SELF_APPROVAL_BLOCKED"),
    ("APPROVER_UNAUTHORIZED", "PAYREQ_APPROVE_ACTOR_AUTHORIZED"),
    ("APPROVER_SCOPE_MISMATCH", "PAYREQ_APPROVE_ACTOR_SCOPE_VALID"),
    ("APPROVAL_STEP_OUT_OF_ORDER", "PAYREQ_APPROVE_STEP_CURRENT"),
    ("APPROVAL_TASK_ALREADY_COMPLETED", "PAYREQ_APPROVE_TASK_PENDING"),
    ("VERSION_CONFLICT", "PAYREQ_APPROVE_VERSION_CURRENT"),
    ("AMOUNT_MISMATCH", "PAYREQ_GATE_AMOUNT_MATCH"),
    ("CURRENCY_MISMATCH", "PAYREQ_GATE_CURRENCY_MATCH"),
    ("REJECTED", "PAYREQ_ELIGIBILITY_STATUS_APPROVED"),
)


def ensure_user(username, company_id=1):
    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_superuser(
            username=username, real_name=username, email=f"{username}@example.invalid",
            password=None, company_id=company_id,
        )
    return user


def ensure_role(user, role_code, legal_entity_id):
    payload = {
        "userId": user.pk, "roleCode": role_code,
        "legalEntityId": legal_entity_id, "active": True, "version": 1,
    }
    UserOrganizationRoleAuthority.objects.get_or_create(
        user=user, role_code=role_code, legal_entity_id=legal_entity_id,
        defaults={
            "department_id": "", "active": True, "version": 1,
            "business_hash": canonical_hash(payload),
        },
    )


def ensure_policy(source, index):
    steps = 1 if index == 1 else 3 if index == 3 else 2
    code = f"PAYREQ-{source.legal_entity_id}-{source.pk}"
    policy_payload = {
        "policyCode": code, "documentType": "payment_request",
        "legalEntityId": source.legal_entity_id,
        "amountMin": str(source.payment_amount), "amountMax": str(source.payment_amount),
        "currency": source.currency, "stepCount": steps, "version": 1,
    }
    policy, _ = ApprovalPolicyAuthority.objects.get_or_create(
        policy_code=code,
        defaults={
            "document_type": "payment_request",
            "legal_entity_id": source.legal_entity_id,
            "amount_min": source.payment_amount,
            "amount_max": source.payment_amount,
            "currency": source.currency, "active": True,
            "step_count": steps, "version": 1,
            "business_hash": canonical_hash(policy_payload),
        },
    )
    route_steps = [{
        "stepNo": step, "roleCode": f"PAYREQ_APPROVER_L{step}",
        "minimumApprovals": 1, "allowParallel": False,
    } for step in range(1, steps + 1)]
    route_payload = {"policyId": policy.pk, "steps": route_steps, "version": 1}
    ApprovalRouteAuthority.objects.get_or_create(
        route_code=f"ROUTE-{code}", policy=policy,
        defaults={
            "steps": route_steps, "active": True, "version": 1,
            "business_hash": canonical_hash(route_payload),
        },
    )
    return policy, route_steps


class Command(BaseCommand):
    help = "Idempotently ensure eight approved V48 payment-request canary chains"

    def handle(self, *args, **options):
        batch = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).first()
        if not batch:
            raise CommandError(f"Missing prerequisite batch: {BATCH_ID}")
        lineages = list(batch.lineages.order_by("scenario_code"))
        if len(lineages) < 8:
            raise CommandError("V47 prerequisite has fewer than eight lineages")
        sources = []
        for lineage in lineages[:8]:
            source = PaymentRequestPrepare.objects.filter(
                prepare_no=lineage.current_object_no, tenant_id=TENANT_ID
            ).first()
            if not source:
                source = PaymentRequestPrepare.objects.filter(
                    prepare_no__in=lineage.upstream_object_nos, tenant_id=TENANT_ID
                ).first()
            if not source:
                raise CommandError(f"Missing V47 source for {lineage.scenario_code}")
            if source.status != "prepared":
                raise CommandError(f"V47 source is not prepared: {source.prepare_no}")
            sources.append((lineage, source))

        sod_payload = {
            "documentType": "payment_request", "applicantCannotApprove": True,
            "sameDepartmentRestriction": False, "sameUserRestriction": True,
            "requiredRoleSeparation": True, "version": 1,
        }
        SegregationOfDutiesAuthority.objects.get_or_create(
            document_type="payment_request",
            defaults={
                "applicant_cannot_approve": True,
                "same_department_restriction": False,
                "same_user_restriction": True,
                "required_role_separation": True,
                "version": 1, "business_hash": canonical_hash(sod_payload),
            },
        )

        changed = False
        results = []
        with transaction.atomic():
            for index, (lineage, source) in enumerate(sources, 1):
                applicant = ensure_user(f"pce-v48-applicant-{index}", source.company_id)
                _, route_steps = ensure_policy(source, index)
                approvers = []
                for step in route_steps:
                    approver = ensure_user(f"pce-v48-approver-l{step['stepNo']}-{index}", source.company_id)
                    ensure_role(approver, step["roleCode"], source.legal_entity_id)
                    approvers.append(approver)
                target = PaymentRequest.objects.filter(
                    source_payment_request_prepare=source
                ).first()
                if not target:
                    outcome = generate_payment_request(
                        user=applicant, source=source,
                        idempotency_key=f"payreq-v48-generate-{lineage.scenario_code.lower()}",
                        expected_source_version=source.version,
                        explicit_user_action=True,
                    )
                    target = PaymentRequest.objects.get(pk=outcome["data"]["id"])
                    changed = True
                if target.status == "prepared":
                    submit_payment_request(
                        user=applicant, obj=target,
                        idempotency_key=f"payreq-v48-submit-{lineage.scenario_code.lower()}",
                        expected_version=target.version,
                        expected_source_prepare_version=source.version,
                        expected_payment_data_version=source.current_payment_data_version,
                        expected_source_validation_version=source.current_validation_version,
                        explicit_user_action=True,
                        application_reason=f"采购付款申请 {lineage.scenario_code}",
                    )
                    target.refresh_from_db()
                    changed = True
                while target.status == "submitted":
                    task = target.workflow_instance.tasks.get(status="pending")
                    approver = approvers[task.step_no - 1]
                    decide_payment_request(
                        user=approver, obj=target, task=task, decision="approved",
                        idempotency_key=f"payreq-v48-approve-{lineage.scenario_code.lower()}-{task.step_no}",
                        expected_payment_request_version=target.version,
                        expected_workflow_version=target.workflow_instance.version,
                        expected_task_version=task.version, explicit_user_action=True,
                        decision_comment=f"V48 canary approval step {task.step_no}",
                    )
                    target.refresh_from_db()
                    changed = True
                if target.status != "approved":
                    raise CommandError(f"Payment request not approved: {target.request_no}")
                upstream = list(lineage.upstream_object_nos)
                for number in (source.prepare_no, target.request_no):
                    if number not in upstream:
                        upstream.append(number)
                values = {
                    "current_module_code": "payment-request",
                    "current_object_type": "paymentRequest",
                    "current_object_id": target.pk,
                    "current_object_no": target.request_no,
                    "downstream_eligible": True,
                    "reserved_for_next_module": "payment_instruction_prepare",
                    "next_stage_consumed": False,
                    "upstream_object_nos": upstream,
                    "source_relation_hash": canonical_hash({
                        "source": source.prepare_no, "target": target.request_no,
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
                    "sourcePrepareNo": source.prepare_no,
                    "requestNo": target.request_no,
                    "applicant": applicant.username,
                    "approvalSteps": target.total_approval_steps,
                    "approvers": [user.username for user in approvers],
                    "status": target.status,
                })

            for code, rule in BLOCKED_SCENARIOS:
                payload = {
                    "batchId": BATCH_ID, "scenarioCode": code,
                    "rule": rule, "formalObjectCount": 0,
                }
                _, created = PaymentRequestCanaryScenario.objects.get_or_create(
                    batch_id=BATCH_ID, scenario_code=code,
                    defaults={
                        "scenario_class": "blocked", "scenario_role": code.lower(),
                        "blocking_module": "payment_request",
                        "blocking_rule_code": rule,
                        "blocking_reason": f"V48 isolated scenario blocked by {rule}",
                        "current_last_valid_object_no": "",
                        "formal_object_count": 0, "next_step_allowed": False,
                        "scenario_hash": canonical_hash(payload),
                    },
                )
                changed = changed or created

        output = {
            "result": "passed", "version": VERSION, "changed": changed,
            "formalPaymentRequestCount": PaymentRequest.objects.filter(tenant_id=TENANT_ID).count(),
            "approvedPaymentRequestCount": PaymentRequest.objects.filter(
                tenant_id=TENANT_ID, status="approved"
            ).count(),
            "blockedScenarioCount": PaymentRequestCanaryScenario.objects.filter(batch_id=BATCH_ID).count(),
            "results": results, "paymentInstructionPrepareCreated": False,
            "productionRolloutEnabled": False,
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
