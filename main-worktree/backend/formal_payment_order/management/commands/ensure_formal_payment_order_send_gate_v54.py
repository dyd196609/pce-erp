import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from formal_payment_order.facts import build_execution_gate_facts
from formal_payment_order.models import (
    FormalPaymentOrder,
    FormalPaymentOrderSendGateCanaryScenario,
)
from formal_payment_order.services import (
    APPROVAL_ROLES,
    DOCUMENT_TYPE,
    SEND_GATE_BATCH_ID,
    VERSION,
    approve_formal_payment_order,
    freeze_formal_payment_order,
    submit_formal_payment_order,
)
from reconciliation.services import canonical_hash
from workflow_runtime.models import (
    ApprovalPolicyAuthority,
    ApprovalRouteAuthority,
    SegregationOfDutiesAuthority,
    UserOrganizationRoleAuthority,
)


SUCCESS_SCENARIOS = (
    "SUCCESS_STANDARD",
    "SUCCESS_SECOND_SUPPLIER",
    "SUCCESS_HIGH_AMOUNT",
    "SUCCESS_LOW_AMOUNT",
    "SUCCESS_MULTI_LINE",
    "SUCCESS_MULTI_SUPPLIER",
    "SUCCESS_IDEMPOTENCY",
    "SUCCESS_ROUTE_VALID",
)

BLOCKED_SCENARIOS = (
    ("APPROVAL_MISSING", "approvalPassed", "审批不存在"),
    ("APPROVAL_REJECTED", "approvalPassed", "审批已拒绝"),
    ("APPROVER_CONFLICT", "segregationPassed", "审批人与制单人冲突"),
    ("FREEZE_HASH_CHANGED", "freezePassed", "冻结哈希不一致"),
    ("FUNDS_CHANGED", "fundsPassed", "资金事实已变化"),
    ("BANK_INTERFACE_DOWN", "bankPassed", "银行接口不可用"),
    ("SIGNATURE_EXPIRED", "signaturePassed", "签署凭据或证书失效"),
    ("SEGREGATION_FAILED", "segregationPassed", "职责分离失败"),
    ("RISK_REVIEW_EXPIRED", "riskPassed", "风险评审已过期"),
    ("SOURCE_VERSION_CHANGED", "riskPassed", "来源版本已变化"),
    ("ACCOUNT_CHANGED", "freezePassed", "冻结账户已变化"),
    ("LIMIT_CHANGED", "fundsPassed", "支付限额已变化"),
    ("DATE_CHANGED", "freezePassed", "计划执行日期已变化"),
    ("PERMISSION_DENIED", "approvalPassed", "操作权限不足"),
    ("DUPLICATE_SEND_ATTEMPT", "freezePassed", "重复发送尝试被阻断"),
)


def _user(username):
    user, _ = get_user_model().objects.get_or_create(
        username=username,
        defaults={
            "real_name": username,
            "email": f"{username}@example.invalid",
            "company_id": 1,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        },
    )
    changed = False
    for field in ("is_active", "is_staff", "is_superuser"):
        if not getattr(user, field):
            setattr(user, field, True)
            changed = True
    if changed:
        user.save(update_fields=["is_active", "is_staff", "is_superuser"])
    return user


def _ensure_authorities(orders, checker, authorizer):
    legal_entities = sorted({order.legal_entity for order in orders})
    for legal_entity in legal_entities:
        policy_code = f"FPO-APPROVAL-{canonical_hash(legal_entity)[:12].upper()}"
        policy, _ = ApprovalPolicyAuthority.objects.update_or_create(
            policy_code=policy_code,
            defaults={
                "document_type": DOCUMENT_TYPE,
                "legal_entity_id": legal_entity,
                "amount_min": "0.01",
                "amount_max": "999999999999.99",
                "currency": "CNY",
                "active": True,
                "step_count": 2,
                "version": 1,
                "business_hash": canonical_hash(
                    {
                        "documentType": DOCUMENT_TYPE,
                        "legalEntity": legal_entity,
                        "roles": APPROVAL_ROLES,
                    }
                ),
            },
        )
        steps = [
            {
                "stepNo": 1,
                "roleCode": APPROVAL_ROLES[0],
                "minimumApprovals": 1,
                "allowParallel": False,
            },
            {
                "stepNo": 2,
                "roleCode": APPROVAL_ROLES[1],
                "minimumApprovals": 1,
                "allowParallel": False,
            },
        ]
        ApprovalRouteAuthority.objects.update_or_create(
            route_code=f"ROUTE-{policy_code}",
            defaults={
                "policy": policy,
                "steps": steps,
                "active": True,
                "version": 1,
                "business_hash": canonical_hash(
                    {"policyCode": policy_code, "steps": steps}
                ),
            },
        )
        for actor, role in (
            (checker, APPROVAL_ROLES[0]),
            (authorizer, APPROVAL_ROLES[1]),
        ):
            UserOrganizationRoleAuthority.objects.update_or_create(
                user=actor,
                role_code=role,
                legal_entity_id=legal_entity,
                defaults={
                    "department_id": (
                        "V54-CHECKER" if role == APPROVAL_ROLES[0] else "V54-AUTHORIZER"
                    ),
                    "active": True,
                    "version": 1,
                    "business_hash": canonical_hash(
                        {
                            "userId": actor.pk,
                            "roleCode": role,
                            "legalEntity": legal_entity,
                        }
                    ),
                },
            )
    SegregationOfDutiesAuthority.objects.update_or_create(
        document_type=DOCUMENT_TYPE,
        defaults={
            "applicant_cannot_approve": True,
            "same_department_restriction": False,
            "same_user_restriction": True,
            "required_role_separation": True,
            "version": 1,
            "business_hash": canonical_hash(
                {
                    "documentType": DOCUMENT_TYPE,
                    "makerCannotApprove": True,
                    "checkerCannotAuthorize": True,
                }
            ),
        },
    )


def _advance(order, maker, checker, authorizer, freezer):
    order.refresh_from_db()
    if order.status == "prepared":
        submit_formal_payment_order(
            user=maker,
            order=order,
            idempotency_key=f"V54-SUBMIT-{order.order_no}",
            expected_version=order.version,
            explicit_user_action=True,
        )
        order.refresh_from_db()
    if order.status == "submitted":
        approval = order.approval
        workflow = approval.workflow_instance
        task = workflow.tasks.filter(status="pending").order_by("step_no").first()
        while task:
            actor = checker if task.required_role_code == APPROVAL_ROLES[0] else authorizer
            approve_formal_payment_order(
                user=actor,
                order=order,
                task_id=task.pk,
                idempotency_key=f"V54-APPROVE-{order.order_no}-{task.step_no}",
                expected_order_version=order.version,
                expected_workflow_version=workflow.version,
                expected_task_version=task.version,
                explicit_user_action=True,
                comment=f"V54 canary {task.required_role_code} approved",
            )
            order.refresh_from_db()
            if order.status != "submitted":
                break
            approval = order.approval
            workflow = approval.workflow_instance
            task = workflow.tasks.filter(status="pending").order_by("step_no").first()
    if order.status == "approved":
        approval = order.approval
        freeze_formal_payment_order(
            user=freezer,
            order=order,
            idempotency_key=f"V54-FREEZE-{order.order_no}",
            expected_order_version=order.version,
            expected_approval_version=approval.version,
            explicit_user_action=True,
        )
        order.refresh_from_db()
    if order.status != "frozen_for_execution":
        raise CommandError(f"{order.order_no} did not reach frozen_for_execution")
    return order


class Command(BaseCommand):
    help = "Create the V54 approval/freeze/send-gate canary facts without bank sending"

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V54 canary command requires PCE_CANARY_DEMO_MODE")
        orders = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
            .select_related(
                "source_risk_review__source_payment_order_draft",
                "created_by",
            )
            .order_by("order_no")
        )
        if len(orders) != 8:
            raise CommandError(f"Expected exactly 8 formal payment orders, got {len(orders)}")
        maker = _user("pce-v54-submitter")
        checker = _user("pce-v54-payment-checker")
        authorizer = _user("pce-v54-payment-authorizer")
        freezer = _user("pce-v54-freezer")
        if len({maker.pk, checker.pk, authorizer.pk, freezer.pk}) != 4:
            raise CommandError("V54 canary actors must be distinct")
        _ensure_authorities(orders, checker, authorizer)
        finalized = [
            _advance(order, maker, checker, authorizer, freezer)
            for order in orders
        ]
        facts = [build_execution_gate_facts(order) for order in finalized]
        if not all(fact.bank_send_eligibility.ready_for_bank_send for fact in facts):
            raise CommandError("At least one V54 success object is not bank-send eligible")
        first = finalized[0]
        for scenario_code, blocking_fact, reason in BLOCKED_SCENARIOS:
            eligibility = build_execution_gate_facts(
                first,
                overrides={blocking_fact: False},
            ).bank_send_eligibility
            if eligibility.ready_for_bank_send:
                raise CommandError(f"{scenario_code} was not blocked")
            FormalPaymentOrderSendGateCanaryScenario.objects.update_or_create(
                batch_id=SEND_GATE_BATCH_ID,
                scenario_code=scenario_code,
                defaults={
                    "scenario_class": "blocked",
                    "blocking_fact": blocking_fact,
                    "blocking_reason": reason,
                    "bank_send_eligible": False,
                    "bank_message_count": 0,
                    "payment_execution_count": 0,
                    "scenario_hash": canonical_hash(
                        {
                            "scenarioCode": scenario_code,
                            "blockingFact": blocking_fact,
                            "bankSendEligible": False,
                            "bankMessageCount": 0,
                        }
                    ),
                },
            )
        result = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "正式付款单审批冻结与银行发送前最终门禁",
            "formalPaymentOrderCount": len(finalized),
            "successScenarios": [
                {
                    "scenarioCode": code,
                    "orderNo": order.order_no,
                    "approvalStatus": fact.approval_status,
                    "approvalNodeCount": len(fact.approval_history),
                    "freezeStatus": fact.freeze_status,
                    "bankSendEligible": fact.bank_send_eligibility.ready_for_bank_send,
                }
                for code, order, fact in zip(SUCCESS_SCENARIOS, finalized, facts)
            ],
            "approvedCount": sum(
                fact.approval_status == "approved" for fact in facts
            ),
            "frozenCount": sum(fact.freeze_status == "frozen" for fact in facts),
            "bankSendEligibleCount": sum(
                fact.bank_send_eligibility.ready_for_bank_send for fact in facts
            ),
            "blockedScenarioCount": FormalPaymentOrderSendGateCanaryScenario.objects.filter(
                batch_id=SEND_GATE_BATCH_ID,
                bank_send_eligible=False,
            ).count(),
            "bankMessageCreated": False,
            "paymentExecuted": False,
            "ledgerCreated": False,
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
