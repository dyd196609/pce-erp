from .settings import *  # noqa: F403

# The historical masterdata migration chain assumes a pre-existing legacy
# table. V84 tests synchronize that unrelated app directly so the isolated
# supplier-settlement suite can validate its own migrations from an empty DB.
MIGRATION_MODULES = {
    "masterdata": None,
    "pfm": None,
    "procurement": None,
    "purchase": None,
    "reconciliation": None,
    "workflow_runtime": None,
    "purchase_invoice_prepare": None,
    "purchase_accounts_payable_draft": None,
    "payable_confirmation_prepare": None,
    "payment_request_prepare": None,
    "payment_request": None,
    "payment_instruction_prepare": None,
    "payment_order_prepare": None,
    "payment_order_draft": None,
    "payment_risk_review": None,
    "formal_payment_order": None,
    "bank_send_preparation": None,
    "bank_send_task": None,
    "bank_send_execution_gate": None,
    "bank_send_request": None,
    "bank_send_execution_simulation": None,
    "purchase_canary": None,
}
