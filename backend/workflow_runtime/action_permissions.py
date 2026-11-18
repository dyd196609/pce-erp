from dataclasses import asdict, dataclass

from django.apps import apps
from django.conf import settings

from system.models import RolePermission
from system.authorization import AuthorizationService

from .models import UserOrganizationRoleAuthority


CONTRACT_VERSION = "PCE-BUSINESS-ACTION-PERMISSION-V1.0"
SERVER_VALIDATOR = "workflow_runtime.ActionPermissionValidator"
ORGANIZATION_SCOPE = "legal_entity"

VIEWER_ROLE = "pce_business_viewer"
OPERATOR_ROLE = "pce_business_operator"
BATCH_OPERATOR_ROLE = "pce_business_batch_operator"
ADMIN_ROLE = "pce_business_admin"
BANK_OPERATOR_ROLE = "pce_bank_operator"
BANK_SEND_BUSINESS_REVIEWER_ROLE = "bank_send_business_reviewer"
BANK_SEND_FUND_OWNER_ROLE = "bank_send_fund_owner"
BANK_SEND_BUSINESS_OWNER_ROLE = "bank_send_business_owner"
BANK_SEND_SECURITY_OWNER_ROLE = "bank_send_security_owner"
SCM_PAYABLE_BUYER_ROLE = "scm_payable_buyer"
SCM_PAYABLE_SUPERVISOR_ROLE = "scm_payable_supervisor"
SCM_PAYMENT_REQUEST_APPLICANT_ROLE = "scm_payment_request_applicant"
SCM_PAYMENT_REQUEST_OWNER_ROLE = "scm_payment_request_owner"

SINGLE_ROLES = (OPERATOR_ROLE, BATCH_OPERATOR_ROLE, ADMIN_ROLE)
BANK_TASK_SINGLE_ROLES = (OPERATOR_ROLE, BANK_OPERATOR_ROLE, ADMIN_ROLE)
BATCH_ROLES = (BATCH_OPERATOR_ROLE, ADMIN_ROLE)
VIEW_ROLES = (VIEWER_ROLE, OPERATOR_ROLE, BATCH_OPERATOR_ROLE, ADMIN_ROLE)


MODULE_ACTIONS = {
    "supplier-payable-confirmation": (
        ("SCM_PAYABLE_SUBMIT_REVIEW", ("draft",)),
        ("SCM_PAYABLE_APPROVE", ("internal_review",)),
        ("SCM_PAYABLE_CREATE_PAYMENT_REQUEST", ("confirmed",)),
    ),
    "supplier-payment-request": (
        ("SCM_PAYMENT_REQUEST_SUBMIT", ("draft",)),
        ("SCM_PAYMENT_REQUEST_APPROVE", ("submitted",)),
        ("SCM_PAYMENT_REQUEST_RETURN", ("submitted",)),
    ),
    "payable-prepare": (
        ("generate-payable-prepare", ("not_created", "source_ready")),
        ("generate-payable-check-from-prepare", ("prepared", "payable_prepared")),
        ("batch-generate-payable-prepare", ("not_created", "source_ready")),
        ("enter-payable-check", ("prepared", "payable_prepared", "checked")),
        ("batch-enter-payable-check", ("prepared", "payable_prepared", "checked")),
    ),
    "payable-check": (
        ("generate-payable-check", ("not_created", "source_ready")),
        ("complete-payable-check", ("draft", "checking")),
        (
            "enter-supplier-settlement",
            ("checked", "matched", "invoicePrepareReady", "invoicePrepared"),
        ),
        ("batch-complete-payable-check", ("draft", "checking")),
        (
            "batch-enter-supplier-settlement",
            ("checked", "matched", "invoicePrepareReady", "invoicePrepared"),
        ),
    ),
    "supplier-settlement": (
        (
            "generate-supplier-settlement",
            ("checked", "source_ready", "not_created"),
        ),
        (
            "batch-generate-supplier-settlement",
            ("checked", "source_ready", "not_created"),
        ),
        (
            "enter-purchase-reconciliation",
            (
                "prepared",
                "payable_prepared",
                "settlement_ready",
                "reconciling",
                "reconciliation_ready",
                "matched",
            ),
        ),
        (
            "batch-enter-purchase-reconciliation",
            (
                "prepared",
                "payable_prepared",
                "settlement_ready",
                "reconciling",
                "reconciliation_ready",
                "matched",
            ),
        ),
    ),
    "purchase-reconciliation": (
        ("generate-purchase-invoice-prepare", ("matched",)),
        ("complete-purchase-reconciliation", ("draft",)),
        ("batch-complete-purchase-reconciliation", ("draft",)),
        ("enter-purchase-invoice-prepare", ("matched",)),
        ("batch-enter-purchase-invoice-prepare", ("matched",)),
    ),
    "purchase-invoice-prepare": (
        ("save-purchase-invoice-data", ("draft",)),
        ("validate-purchase-invoice-data", ("draft",)),
        ("enter-accounts-payable-draft", ("draft", "prepared", "validated")),
        (
            "batch-enter-accounts-payable-draft",
            ("draft", "prepared", "validated"),
        ),
    ),
    "accounts-payable-draft": (
        (
            "generate-purchase-accounts-payable-draft",
            ("prepared",),
        ),
        (
            "enter-payable-confirmation-prepare",
            ("draft", "prepared", "validated"),
        ),
        (
            "batch-enter-payable-confirmation-prepare",
            ("draft", "prepared", "validated"),
        ),
    ),
    "payable-confirmation-prepare": (
        ("enter-payment-request-prepare", ("prepared",)),
        ("batch-enter-payment-request-prepare", ("prepared",)),
    ),
    "payment-request-prepare": (
        ("enter-payment-request", ("prepared",)),
        ("batch-enter-payment-request", ("prepared",)),
    ),
    "payment-request": (
        ("enter-payment-instruction-prepare", ("approved",)),
        ("batch-enter-payment-instruction-prepare", ("approved",)),
    ),
    "payment-instruction-prepare": (
        ("enter-payment-order-prepare", ("validated",)),
        ("batch-enter-payment-order-prepare", ("validated",)),
    ),
    "payment-order-prepare": (
        ("enter-payment-order-draft", ("submitted",)),
        ("batch-enter-payment-order-draft", ("submitted",)),
    ),
    "payment-order-draft": (
        ("enter-payment-risk-review", ("reviewed",)),
        ("batch-enter-payment-risk-review", ("reviewed",)),
    ),
    "bank-send-preparation": (
        ("view-bank-send-eligibility", ("prepared",)),
        ("view-bank-send-gate", ("prepared",)),
        ("generate-bank-message-preview", ("prepared",)),
    ),
    "bank-send-task": (
        (
            "view-bank-send-task",
            ("prepared", "queued", "ready_to_send"),
        ),
        (
            "view-bank-send-task-status",
            ("prepared", "queued", "ready_to_send"),
        ),
        (
            "view-bank-message-binding",
            ("prepared", "queued", "ready_to_send"),
        ),
        ("create-bank-send-task", ("prepared",)),
    ),
    "bank-send-execution-gate": (
        (
            "view-bank-send-execution-gate",
            ("pending_review", "approved", "ready_for_execution"),
        ),
        (
            "view-bank-send-execution-gate-conditions",
            ("pending_review", "approved", "ready_for_execution"),
        ),
        (
            "submit-bank-send-final-authorization-review",
            ("ready_to_send",),
        ),
    ),
    "bank-send-request": (
        ("view-bank-send-request", ("draft", "validated", "ready_to_dispatch")),
        (
            "view-bank-send-pre-dispatch-validation",
            ("draft", "validated", "ready_to_dispatch"),
        ),
        ("create-bank-send-request", ("ready_for_execution",)),
        (
            "rerun-bank-send-pre-dispatch-validation",
            ("draft", "validated", "ready_to_dispatch"),
        ),
    ),
    "bank-send-simulation": (
        (
            "create-bank-send-execution-simulation",
            ("ready_to_dispatch",),
        ),
        (
            "view-bank-send-execution-simulation-result",
            (
                "created", "validated", "simulation_running",
                "simulation_success", "simulation_failed",
            ),
        ),
        (
            "view-bank-send-execution-recovery",
            ("simulation_failed",),
        ),
    ),
    "bank-send-simulation-audit": (
        (
            "view-bank-send-simulation-audit",
            (
                "simulation_created", "simulation_validated",
                "simulation_started", "simulation_completed",
                "simulation_failed", "simulation_recovered",
            ),
        ),
    ),
    "bank-send-isolation-gate": (
        (
            "view-bank-send-production-isolation",
            ("created", "checked", "isolated"),
        ),
    ),
    "bank-send-chain-trace": (
        ("view-bank-send-chain-trace", ("*",)),
    ),
    "bank-send-final-approval": (
        (
            "view-bank-send-final-approval-conditions",
            ("pending", "first_approved", "second_approved", "final_locked"),
        ),
        ("submit-bank-send-first-approval", ("pending",)),
        ("submit-bank-send-second-approval", ("first_approved",)),
    ),
    "bank-send-dual-isolation-check": (
        ("view-bank-send-dual-isolation-check", ("passed", "failed")),
    ),
    "bank-send-production-release-review": (
        (
            "view-bank-send-production-release-review",
            ("draft", "reviewing", "review_passed", "locked"),
        ),
        ("submit-production-business-review", ("draft",)),
        ("submit-production-fund-review", ("reviewing",)),
        ("submit-production-security-review", ("review_passed",)),
    ),
    "bank-send-execution-framework-review": (
        (
            "view-bank-send-execution-framework",
            ("draft", "designed", "security_reviewed"),
        ),
        (
            "view-bank-send-request-signature",
            ("security_reviewed",),
        ),
        (
            "view-bank-send-failure-model",
            ("security_reviewed",),
        ),
    ),
    "bank-connector-adapter-review": (
        ("view-bank-connector-adapter", ("simulation_only",)),
    ),
}


READ_ONLY_SINGLE_ACTIONS = {
    "view-bank-send-eligibility",
    "view-bank-send-gate",
    "view-bank-send-task",
    "view-bank-send-task-status",
    "view-bank-message-binding",
    "view-bank-send-execution-gate",
    "view-bank-send-execution-gate-conditions",
    "view-bank-send-request",
    "view-bank-send-pre-dispatch-validation",
    "view-bank-send-execution-simulation-result",
    "view-bank-send-execution-recovery",
    "view-bank-send-simulation-audit",
    "view-bank-send-production-isolation",
    "view-bank-send-chain-trace",
    "view-bank-send-final-approval-conditions",
    "view-bank-send-dual-isolation-check",
    "view-bank-send-production-release-review",
    "view-bank-send-execution-framework",
    "view-bank-send-request-signature",
    "view-bank-send-failure-model",
    "view-bank-connector-adapter",
}


OBJECT_FACT_SOURCES = {
    "supplier-payable-confirmation": (
        "supplier_performance",
        "SupplierPayableConfirmation",
        "status",
    ),
    "supplier-payment-request": (
        "supplier_performance",
        "SupplierPaymentRequest",
        "status",
    ),
    "payable-prepare": (
        "reconciliation",
        "PurchaseReconciliationSourceSnapshot",
        "payable_status",
    ),
    "payable-check": (
        "reconciliation",
        "PayableCheckAuthorityRecord",
        "business_status",
    ),
    "supplier-settlement": (
        "reconciliation",
        "SupplierSettlementAuthorityRecord",
        "business_status",
    ),
    "purchase-reconciliation": (
        "reconciliation",
        "PurchaseReconciliation",
        "status",
    ),
    "purchase-invoice-prepare": (
        "purchase_invoice_prepare",
        "PurchaseInvoicePrepare",
        "status",
    ),
    "accounts-payable-draft": (
        "purchase_accounts_payable_draft",
        "PurchaseAccountsPayableDraft",
        "status",
    ),
    "payable-confirmation-prepare": (
        "payable_confirmation_prepare",
        "PayableConfirmationPrepare",
        "status",
    ),
    "payment-request-prepare": (
        "payment_request_prepare",
        "PaymentRequestPrepare",
        "status",
    ),
    "payment-request": ("payment_request", "PaymentRequest", "status"),
    "payment-instruction-prepare": (
        "payment_instruction_prepare",
        "PaymentInstructionPrepare",
        "status",
    ),
    "payment-order-prepare": (
        "payment_order_prepare",
        "PaymentOrderPrepare",
        "status",
    ),
    "payment-order-draft": (
        "payment_order_draft",
        "PaymentOrderDraft",
        "status",
    ),
    "bank-send-preparation": (
        "bank_send_preparation",
        "BankSendPreparation",
        "status",
    ),
    "bank-send-task": ("bank_send_task", "BankSendTask", "status"),
    "bank-send-execution-gate": (
        "bank_send_execution_gate",
        "BankSendExecutionGate",
        "status",
    ),
    "bank-send-request": ("bank_send_request", "BankSendRequest", "status"),
    "bank-send-simulation": (
        "bank_send_execution_simulation",
        "BankSendExecutionSimulation",
        "status",
    ),
    "bank-send-chain-trace": (
        "bank_send_execution_simulation",
        "BankSendChainTrace",
        "trace_source",
    ),
    "bank-send-final-approval": (
        "bank_send_execution_simulation",
        "BankSendFinalApproval",
        "status",
    ),
    "bank-send-dual-isolation-check": (
        "bank_send_execution_simulation",
        "BankSendDualIsolationCheck",
        "result",
    ),
    "bank-send-production-release-review": (
        "bank_send_execution_simulation",
        "BankSendProductionReleaseReview",
        "status",
    ),
    "bank-send-execution-framework-review": (
        "bank_send_execution_simulation",
        "BankSendExecutionFramework",
        "status",
    ),
    "bank-connector-adapter-review": (
        "bank_send_execution_simulation",
        "BankSendExecutionFramework",
        "interface_mode",
    ),
}


def required_permission_code(module_code, action_code):
    return f"pce.action.{module_code}.{action_code}"


@dataclass(frozen=True)
class ActionPermissionPolicy:
    actionCode: str
    moduleCode: str
    requiredPermission: str
    role: tuple
    organizationScope: str
    serverValidator: str
    allowedStatuses: tuple
    scope: str

    def serialize(self):
        data = asdict(self)
        data["role"] = list(self.role)
        data["allowedStatuses"] = list(self.allowedStatuses)
        return data


def _build_policies():
    policies = {}
    for module_code, actions in MODULE_ACTIONS.items():
        view_action = f"view-{module_code}"
        view_policy = ActionPermissionPolicy(
            actionCode=view_action,
            moduleCode=module_code,
            requiredPermission=required_permission_code(module_code, view_action),
            role=VIEW_ROLES,
            organizationScope=ORGANIZATION_SCOPE,
            serverValidator=SERVER_VALIDATOR,
            allowedStatuses=("*",),
            scope="view",
        )
        policies[(module_code, view_action)] = view_policy
        for action_code, allowed_statuses in actions:
            is_batch = action_code.startswith("batch-")
            is_read_only = action_code in READ_ONLY_SINGLE_ACTIONS
            action_roles = (
                (SCM_PAYABLE_BUYER_ROLE,)
                if (
                    module_code == "supplier-payable-confirmation"
                    and action_code == "SCM_PAYABLE_SUBMIT_REVIEW"
                )
                else (SCM_PAYABLE_SUPERVISOR_ROLE,)
                if (
                    module_code == "supplier-payable-confirmation"
                    and action_code in {
                        "SCM_PAYABLE_APPROVE",
                        "SCM_PAYABLE_CREATE_PAYMENT_REQUEST",
                    }
                )
                else (SCM_PAYMENT_REQUEST_APPLICANT_ROLE,)
                if (
                    module_code == "supplier-payment-request"
                    and action_code == "SCM_PAYMENT_REQUEST_SUBMIT"
                )
                else (SCM_PAYMENT_REQUEST_OWNER_ROLE,)
                if (
                    module_code == "supplier-payment-request"
                    and action_code in {
                        "SCM_PAYMENT_REQUEST_APPROVE",
                        "SCM_PAYMENT_REQUEST_RETURN",
                    }
                )
                else
                (BANK_SEND_BUSINESS_OWNER_ROLE,)
                if (
                    module_code == "bank-send-production-release-review"
                    and action_code == "submit-production-business-review"
                )
                else (BANK_SEND_FUND_OWNER_ROLE,)
                if (
                    module_code == "bank-send-production-release-review"
                    and action_code == "submit-production-fund-review"
                )
                else (BANK_SEND_SECURITY_OWNER_ROLE,)
                if (
                    module_code == "bank-send-production-release-review"
                    and action_code == "submit-production-security-review"
                )
                else
                (BANK_SEND_BUSINESS_REVIEWER_ROLE,)
                if (
                    module_code == "bank-send-final-approval"
                    and action_code == "submit-bank-send-first-approval"
                )
                else (BANK_SEND_FUND_OWNER_ROLE,)
                if (
                    module_code == "bank-send-final-approval"
                    and action_code == "submit-bank-send-second-approval"
                )
                else
                BANK_TASK_SINGLE_ROLES
                if (
                    (
                        module_code == "bank-send-task"
                        and action_code == "create-bank-send-task"
                    )
                    or (
                        module_code == "bank-send-execution-gate"
                        and action_code
                        == "submit-bank-send-final-authorization-review"
                    )
                    or (
                        module_code == "bank-send-request"
                        and action_code == "create-bank-send-request"
                    )
                )
                else BATCH_ROLES
                if is_batch
                else VIEW_ROLES
                if is_read_only
                else SINGLE_ROLES
            )
            policy = ActionPermissionPolicy(
                actionCode=action_code,
                moduleCode=module_code,
                requiredPermission=required_permission_code(
                    module_code, action_code
                ),
                role=action_roles,
                organizationScope=ORGANIZATION_SCOPE,
                serverValidator=SERVER_VALIDATOR,
                allowedStatuses=allowed_statuses,
                scope="batch" if is_batch else "single",
            )
            policies[(module_code, action_code)] = policy
    return policies


POLICIES = _build_policies()

# Native formal schedule actions: registration only, no user or role grant.
for _schedule_action, _schedule_permission, _schedule_states in (
    ('commit', 'planning.schedule.commit', ('confirmed',)),
    ('cancel', 'planning.schedule.cancel', ('saved', 'cancelled')),
    ('authorize-capacity-scope', 'planning.schedule.capacity_scope.authorize', ('confirmed',)),
):
    POLICIES[('formal-production-schedule', _schedule_action)] = ActionPermissionPolicy(
        actionCode=_schedule_action, moduleCode='formal-production-schedule',
        requiredPermission=_schedule_permission, role=('superadmin',), organizationScope=ORGANIZATION_SCOPE,
        serverValidator=SERVER_VALIDATOR, allowedStatuses=_schedule_states, scope='single')


class ActionPermissionRepository:
    def role_codes_for_user(self, user_id, legal_entity_id):
        return set(
            UserOrganizationRoleAuthority.objects.filter(
                user_id=user_id,
                legal_entity_id=legal_entity_id,
                active=True,
            ).values_list("role_code", flat=True)
        )

    def permission_codes_for_roles(self, role_codes):
        if not role_codes:
            return set()
        return set(
            RolePermission.objects.filter(
                role__code__in=role_codes,
            ).values_list("permission__code", flat=True)
        )

    def legal_entity_ids_for_user(self, user_id):
        return set(
            UserOrganizationRoleAuthority.objects.filter(
                user_id=user_id,
                active=True,
            ).values_list("legal_entity_id", flat=True)
        )


class ActionPermissionProvider:
    provider_code = "business_action_permission_authority_provider"
    repository_code = "business_action_permission_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository

    def read(self, user, legal_entity_id):
        if self.repository is not None:
            role_codes = self.repository.role_codes_for_user(
                user.pk, legal_entity_id
            )
            permission_codes = self.repository.permission_codes_for_roles(role_codes)
            authority_source = "workflow_runtime.UserOrganizationRoleAuthority"
        else:
            evidence = AuthorizationService.authority_evidence(
                user, legal_entity_id
            )
            role_codes = {row.role_code for row in evidence}
            permission_codes = AuthorizationService.permission_codes_for_user(user, role_codes)
            authority_source = (
                evidence[0].source
                if evidence
                else "system.UserRoleScopeAssignment"
            )
        return {
            "provider": self.provider_code,
            "repository": authority_source,
            "authorityObjects": [
                "UserOrganizationRoleAuthority",
                "Role",
                "Permission",
                "RolePermission",
            ],
            "userId": user.pk,
            "legalEntityId": legal_entity_id,
            "roleCodes": sorted(role_codes),
            "permissionCodes": sorted(permission_codes),
            "serverDerived": True,
        }


class BusinessObjectFactProvider:
    provider_code = "business_action_object_fact_provider"
    repository_code = "django_business_object_repository"

    def read(self, module_code, object_ids):
        if (
            module_code == "payable-check"
            and getattr(
                settings,
                "PCE_CANARY_OPERATION_DATA_ENABLED",
                False,
            )
        ):
            from purchase_canary.operation_data import (
                operation_legal_entity_id,
                payable_check_operation_rows,
            )

            normalized_ids = []
            for value in object_ids:
                try:
                    normalized_ids.append(int(value))
                except (TypeError, ValueError):
                    return {
                        "found": False,
                        "objectIds": [],
                        "statuses": [],
                        "legalEntityIds": [],
                        "currentStateSource": "server",
                        "reason": "object_id_invalid",
                    }
            row_by_id = {
                item["id"]: item for item in payable_check_operation_rows()
            }
            rows = [
                row_by_id[item_id]
                for item_id in normalized_ids
                if item_id in row_by_id
            ]
            if rows:
                return {
                    "provider": self.provider_code,
                    "repository": "pce_canary_operation_data_repository",
                    "authorityObject": (
                        "purchase_canary.PurchaseCanaryModuleObject"
                    ),
                    "found": len(rows) == len(normalized_ids),
                    "objectIds": [item["id"] for item in rows],
                    "statuses": [
                        item["registryStatus"] for item in rows
                    ],
                    "legalEntityIds": [operation_legal_entity_id()],
                    "currentStateSource": "server",
                    "reason": (
                        ""
                        if len(rows) == len(normalized_ids)
                        else "object_not_found"
                    ),
                }
        source = OBJECT_FACT_SOURCES.get(module_code)
        if not source:
            return {
                "found": False,
                "objectIds": [],
                "statuses": [],
                "legalEntityIds": [],
                "currentStateSource": "server",
                "reason": "module_fact_source_missing",
            }
        app_label, model_name, status_field = source
        model = apps.get_model(app_label, model_name)
        normalized_ids = []
        for value in object_ids:
            try:
                normalized_ids.append(int(value))
            except (TypeError, ValueError):
                return {
                    "found": False,
                    "objectIds": [],
                    "statuses": [],
                    "legalEntityIds": [],
                    "currentStateSource": "server",
                    "reason": "object_id_invalid",
                }
        rows = list(model.objects.filter(pk__in=normalized_ids).order_by("pk"))
        return {
            "provider": self.provider_code,
            "repository": self.repository_code,
            "authorityObject": f"{app_label}.{model_name}",
            "found": len(rows) == len(normalized_ids),
            "objectIds": [row.pk for row in rows],
            "statuses": [str(getattr(row, status_field, "")) for row in rows],
            "legalEntityIds": sorted(
                {
                    str(getattr(row, "legal_entity_id", ""))
                    for row in rows
                    if getattr(row, "legal_entity_id", "")
                }
            ),
            "currentStateSource": "server",
            "reason": "" if len(rows) == len(normalized_ids) else "object_not_found",
        }


class ActionPermissionValidator:
    def __init__(self, permission_provider=None, fact_provider=None):
        self.permission_provider = permission_provider or ActionPermissionProvider()
        self.fact_provider = fact_provider or BusinessObjectFactProvider()

    def evaluate(
        self,
        *,
        user,
        module_code,
        action_code,
        object_ids=(),
        selection_count=0,
        requested_legal_entity_id="",
    ):
        policy = POLICIES.get((module_code, action_code))
        if not policy:
            return self._decision(
                None, False, "action_not_registered", "业务动作未注册。"
            )
        if not user or not user.is_authenticated:
            return self._decision(
                policy, False, "authentication_required", "必须先登录。"
            )

        normalized_ids = [str(value) for value in object_ids if str(value)]
        selection_count = int(selection_count or 0)
        if policy.scope == "batch" and selection_count < 2:
            return self._decision(
                policy,
                False,
                "batch_selection_insufficient",
                "批量动作至少需要两个对象。",
            )
        if policy.scope == "single" and selection_count != 1:
            return self._decision(
                policy,
                False,
                "single_selection_required",
                "单条动作必须且只能选择一个对象。",
            )
        if policy.scope != "view" and len(normalized_ids) != selection_count:
            return self._decision(
                policy,
                False,
                "selection_object_mismatch",
                "选择数量与服务端复核对象数量不一致。",
            )

        if policy.scope == "view" and not normalized_ids:
            legal_entity_ids = [requested_legal_entity_id] if requested_legal_entity_id else []
            facts = {
                "found": bool(legal_entity_ids),
                "objectIds": [],
                "statuses": [],
                "legalEntityIds": legal_entity_ids,
                "currentStateSource": "server",
                "reason": "" if legal_entity_ids else "organization_scope_required",
            }
        else:
            fact_module_code = (
                "purchase-invoice-prepare"
                if (
                    module_code == "accounts-payable-draft"
                    and action_code
                    == "generate-purchase-accounts-payable-draft"
                )
                else "bank-send-preparation"
                if (
                    module_code == "bank-send-task"
                    and action_code == "create-bank-send-task"
                )
                else "bank-send-task"
                if (
                    module_code == "bank-send-execution-gate"
                    and action_code
                    == "submit-bank-send-final-authorization-review"
                )
                else "bank-send-execution-gate"
                if (
                    module_code == "bank-send-request"
                    and action_code == "create-bank-send-request"
                )
                else module_code
            )
            facts = self.fact_provider.read(fact_module_code, normalized_ids)
            if fact_module_code != module_code:
                facts = {
                    **facts,
                    "sourceModuleCode": fact_module_code,
                    "targetModuleCode": module_code,
                }
            legal_entity_ids = facts["legalEntityIds"]

        if not facts["found"]:
            return self._decision(
                policy,
                False,
                facts.get("reason") or "server_fact_missing",
                "服务端业务对象事实不存在或不完整。",
                server_facts=facts,
            )
        if not legal_entity_ids:
            return self._decision(
                policy,
                False,
                "organization_scope_missing",
                "业务对象缺少法人组织范围。",
                server_facts=facts,
            )
        if (
            policy.allowedStatuses != ("*",)
            and not all(
                status in policy.allowedStatuses for status in facts["statuses"]
            )
        ):
            return self._decision(
                policy,
                False,
                "business_state_denied",
                "服务端当前业务状态不允许执行该动作。",
                server_facts=facts,
            )

        if user.is_superuser:
            authority_evidence = [
                {
                    "provider": "django_superuser_authority",
                    "repository": "system.User",
                    "legalEntityId": legal_entity_id,
                    "roleCodes": ["superuser"],
                    "permissionCodes": [policy.requiredPermission],
                    "serverDerived": True,
                }
                for legal_entity_id in legal_entity_ids
            ]
            return self._decision(
                policy,
                True,
                "granted",
                "超级管理员权限通过服务端校验。",
                server_facts=facts,
                authority_evidence=authority_evidence,
            )

        authority_evidence = [
            self.permission_provider.read(user, legal_entity_id)
            for legal_entity_id in legal_entity_ids
        ]
        for evidence in authority_evidence:
            if not set(evidence["roleCodes"]).intersection(policy.role):
                return self._decision(
                    policy,
                    False,
                    "role_denied",
                    "当前用户角色不允许执行该动作。",
                    server_facts=facts,
                    authority_evidence=authority_evidence,
                )
            if policy.requiredPermission not in evidence["permissionCodes"]:
                return self._decision(
                    policy,
                    False,
                    "permission_denied",
                    "当前角色未获得该业务动作权限。",
                    server_facts=facts,
                    authority_evidence=authority_evidence,
                )

        return self._decision(
            policy,
            True,
            "granted",
            "角色、组织范围、业务状态和流程阶段均通过服务端校验。",
            server_facts=facts,
            authority_evidence=authority_evidence,
        )

    def _decision(
        self,
        policy,
        granted,
        decision_code,
        reason,
        *,
        server_facts=None,
        authority_evidence=None,
    ):
        return {
            "contractVersion": CONTRACT_VERSION,
            "action": policy.serialize() if policy else None,
            "granted": bool(granted),
            "decisionCode": decision_code,
            "reason": reason,
            "currentStateSource": "server",
            "frontendVisibilityIsAuthority": False,
            "serverValidationRequired": True,
            "serverFacts": server_facts or {
                "currentStateSource": "server",
                "objectIds": [],
                "statuses": [],
                "legalEntityIds": [],
            },
            "authorityEvidence": authority_evidence or [],
        }


def list_module_policies(module_code):
    return [
        policy
        for (registered_module, _), policy in POLICIES.items()
        if registered_module == module_code
    ]


def authorized_view_legal_entities(user, module_code):
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return None
    view_action = f"view-{module_code}"
    policy = POLICIES[(module_code, view_action)]
    allowed = set()
    authority_rows = AuthorizationService.authority_evidence(user)
    for legal_entity_id in {row.organization_id for row in authority_rows}:
        evidence = ActionPermissionProvider().read(
            user, legal_entity_id
        )
        if (
            set(evidence["roleCodes"]).intersection(policy.role)
            and policy.requiredPermission in evidence["permissionCodes"]
        ):
            allowed.add(legal_entity_id)
    return allowed


def serialize_permission_matrix():
    return [
        policy.serialize()
        for policy in sorted(
            POLICIES.values(),
            key=lambda item: (item.moduleCode, item.actionCode),
        )
    ]
