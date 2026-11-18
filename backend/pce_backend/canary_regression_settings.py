import os
from pathlib import Path

from .settings import *  # noqa: F401,F403

_actual_text = os.environ.get("PCE_CANARY_DATABASE_PATH", "").strip()
_expected_text = os.environ.get("PCE_CANARY_EXPECTED_CLONE_PATH", "").strip()
if not _actual_text or not _expected_text:
    raise RuntimeError("canary regression requires actual and expected clone paths")

_actual = Path(_actual_text).resolve()
_expected = Path(_expected_text).resolve()
if _actual != _expected:
    raise RuntimeError("canary regression database does not match the expected clone")
if "test-results" not in {part.lower() for part in _actual.parts}:
    raise RuntimeError("canary regression clone must be isolated under test-results")
if not _actual.exists():
    raise RuntimeError("canary regression clone must already exist")

DATABASES["default"]["NAME"] = str(_actual)  # noqa: F405
PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED = True
PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED = True
PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED = True
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED = True
PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED = True
PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED = True
PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS = {"tenant-canary-demo"}
PCE_PAYMENT_REQUEST_PREPARE_FAILURE_INJECTION_ENABLED = True
PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED = True
PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS = {"tenant-canary-demo"}
MIGRATION_MODULES = {
    "masterdata": None,
    "procurement": None,
    "purchase": None,
    "pfm": None,
}
