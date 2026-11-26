from pathlib import Path

from django.test import SimpleTestCase

from workflow_runtime.facts import (
    StateTransitionFactError,
    assert_status_transition_count_matches_history,
    status_transition_facts,
)
from workflow_runtime.state_models import BusinessStateManagedModel

from payment_instruction_prepare.models import PaymentInstructionPrepare
from payment_order_draft.models import PaymentOrderDraft
from payment_order_prepare.models import PaymentOrderPrepare
from payment_request.models import PaymentRequest
from payment_request_prepare.models import PaymentRequestPrepare


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


class PaymentChainStateMachineV55ContractTests(SimpleTestCase):
    def test_server_fact_count_is_derived_from_history(self):
        history = [{"version": 1}, {"version": 2}]
        facts = status_transition_facts(
            history=history,
            state_machine_consistent=True,
        )
        self.assertEqual(facts["statusTransitionCount"], len(history))
        self.assertTrue(facts["stateMachineConsistent"])

    def test_server_fact_guard_rejects_count_mismatch(self):
        with self.assertRaises(StateTransitionFactError):
            assert_status_transition_count_matches_history(
                {
                    "statusTransitionHistory": [{"version": 1}],
                    "statusTransitionCount": 0,
                }
            )

    def test_all_five_payment_chain_models_use_managed_state_base(self):
        for model in (
            PaymentRequestPrepare,
            PaymentRequest,
            PaymentInstructionPrepare,
            PaymentOrderPrepare,
            PaymentOrderDraft,
        ):
            self.assertTrue(issubclass(model, BusinessStateManagedModel))

    def test_common_model_guard_blocks_all_orm_status_shortcuts(self):
        source = (BACKEND / "workflow_runtime" / "state_models.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('if "status" in kwargs:', source)
        self.assertIn('if "status" in fields:', source)
        self.assertIn("initial status must use state initialization service", source)

    def test_each_payment_chain_service_uses_common_transition_services(self):
        for module in (
            "payment_request_prepare",
            "payment_request",
            "payment_instruction_prepare",
            "payment_order_prepare",
            "payment_order_draft",
        ):
            source = (BACKEND / module / "services.py").read_text(encoding="utf-8")
            self.assertIn("create_business_object_with_initial_state(", source)
            self.assertIn("transition_business_object(", source)
            self.assertIn("business_state_transition_facts(", source)

    def test_required_payment_chain_transitions_are_declared(self):
        expected = {
            "payment_request_prepare": (("draft", "prepared"),),
            "payment_request": (
                ("prepared", "submitted"),
                ("submitted", "approved"),
            ),
            "payment_instruction_prepare": (("prepared", "validated"),),
            "payment_order_prepare": (("prepared", "submitted"),),
            "payment_order_draft": (("created", "reviewed"),),
        }
        for module, pairs in expected.items():
            source = (BACKEND / module / "services.py").read_text(encoding="utf-8")
            for source_state, target_state in pairs:
                self.assertIn(f'"{source_state}"', source)
                self.assertIn(f'"{target_state}"', source)

    def test_strict_pages_use_server_fact_contract_without_default_zero(self):
        pages = (
            "PaymentApplicationPage.vue",
            "PaymentRequestPage.vue",
            "PaymentInstructionPreparePage.vue",
            "PaymentOrderPreparePage.vue",
            "PaymentOrderDraftPage.vue",
        )
        for page in pages:
            source = (FRONTEND / "src" / "meta" / "pages" / page).read_text(
                encoding="utf-8"
            )
            self.assertIn("stateMachineFactsFromServer(", source)
            self.assertNotIn("Number(row.statusTransitionCount || 0)", source)
            self.assertNotIn("statusTransitionHistory.length,", source)

    def test_long_term_standards_contain_v55_rules(self):
        sources = (
            (ROOT.parent / "AGENTS.md").read_text(encoding="utf-8"),
            (
                ROOT
                / "docs"
                / "standards"
                / "PCE-STATE-MACHINE-CONTRACT-V1.1.md"
            ).read_text(encoding="utf-8"),
            (
                ROOT
                / "docs"
                / "standards"
                / "PCE-WEB-ACCEPTANCE-V1.1.md"
            ).read_text(encoding="utf-8"),
        )
        for source in sources:
            self.assertIn("所有业务状态必须经过统一状态转换服务。", source)
            self.assertIn("五表面事实必须一致", source)
