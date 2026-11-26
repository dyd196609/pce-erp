from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from purchase_invoice_prepare.services import (
    build_purchase_invoice_prepare_state_facts,
)
from purchase_invoice_prepare.tests.test_controlled_generation import (
    make_matched_reconciliation,
)
from reconciliation.checking import build_reconciliation_state_facts
from reconciliation.models import PurchaseReconciliation
from reconciliation.tests.test_production_persistence import make_user

from workflow_runtime.state_models import BusinessStateManagedModel


@override_settings(
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED=True,
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED=False,
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS={"tenant-v57"},
)
class PurchaseUpstreamGovernanceV57Tests(TestCase):
    def test_priority_models_use_common_state_guard(self):
        for model in (
            PayableConfirmationPrepare,
            PurchaseInvoicePrepare,
            PurchaseAccountsPayableDraft,
            PurchaseReconciliation,
        ):
            with self.subTest(model=model.__name__):
                self.assertTrue(issubclass(model, BusinessStateManagedModel))
                with self.assertRaises(ValidationError):
                    model.objects.filter(pk=-1).update(status="invalid")

    def test_matched_reconciliation_fixture_has_authoritative_transition(self):
        user = make_user("v57-state-fact-user", company_id=57)
        reconciliation = make_matched_reconciliation(
            user,
            "v57-state-facts",
            tenant_id="tenant-v57",
            company_id=57,
        )
        facts = build_reconciliation_state_facts(reconciliation)
        self.assertTrue(facts["stateMachineConsistent"])
        self.assertEqual(facts["statusTransitionCount"], 1)
        self.assertEqual(
            facts["statusTransitionCount"],
            len(facts["statusTransitionHistory"]),
        )
        self.assertEqual(
            facts["statusTransitionHistory"][0]["sourceState"],
            PurchaseReconciliation.Status.DRAFT,
        )
        self.assertEqual(
            facts["statusTransitionHistory"][0]["targetState"],
            PurchaseReconciliation.Status.MATCHED,
        )

    def test_invoice_initial_state_uses_zero_persisted_transitions(self):
        user = make_user("v57-invoice-fact-user", company_id=57)
        reconciliation = make_matched_reconciliation(
            user,
            "v57-invoice-facts",
            tenant_id="tenant-v57",
            company_id=57,
        )
        from purchase_invoice_prepare.services import (
            generate_purchase_invoice_prepare,
        )

        result = generate_purchase_invoice_prepare(
            user=user,
            reconciliation_id=reconciliation.pk,
            idempotency_key="v57-invoice-initial-state",
            expected_reconciliation_version=reconciliation.version,
            expected_check_version=reconciliation.version,
            explicit_user_action=True,
        )
        prepare = PurchaseInvoicePrepare.objects.get(pk=result["data"]["id"])
        facts = build_purchase_invoice_prepare_state_facts(prepare)
        self.assertTrue(facts["stateMachineConsistent"])
        self.assertEqual(facts["statusTransitionCount"], 0)
        self.assertEqual(facts["statusTransitionHistory"], [])
