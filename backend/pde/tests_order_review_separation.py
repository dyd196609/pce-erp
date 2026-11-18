from django.test import TestCase

from system.models import Company, User

from .models import EngineeringSourceRecord, OrderCrossFunctionalReview
from .order_review_service import ReviewBusinessError, append_review, build_review_facts


class OrderReviewSeparationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="REVIEW", name="评审隔离测试公司")
        self.user = User.objects.create_user(
            username="review_admin", password="unused", real_name="评审测试人",
            company_id=self.company.pk, is_superuser=True,
        )
        self.source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="SOURCE-1-4", source_name="1-4-正工程来源",
            source_type="controlled_import", source_version="R1", content_hash="a" * 64,
            status="confirmed", source_payload={
                "businessOrderReference": {"sourceOrderNo": "1-4-正", "customer": "上海王燕", "project": "上海 大居苑"},
                "registeredSourceScope": {"sourceCount": 71},
            },
        )

    def save(self, review_type, conclusion, key):
        return append_review(
            user=self.user, review_type=review_type, source_record_id=self.source.pk,
            idempotency_key=key, data={
                "expectedSourceVersion": "R1", "expectedContentHash": "a" * 64,
                "reviewOpinion": f"{review_type}独立意见", "conclusion": conclusion,
                "missingConditions": ["独立待补条件"], "responsibilityFeedback": {"statement": "独立责任"},
            },
        )

    def test_two_reviews_have_independent_history_and_conclusion(self):
        self.save("CRM_ORDER_REVIEW", "CONDITIONAL", "crm-1")
        self.save("PDE_PRODUCTION_FEASIBILITY", "RETURN_FOR_COMPLETION", "pde-1")
        crm = build_review_facts(user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        pde = build_review_facts(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk)
        self.assertEqual(crm["review"]["latest"]["conclusionLabel"], "有条件通过")
        self.assertEqual(pde["review"]["latest"]["conclusionLabel"], "退回补充")
        self.assertEqual(len(crm["review"]["history"]), 1)
        self.assertEqual(len(pde["review"]["history"]), 1)
        self.assertTrue(crm["separationFacts"]["crossReviewDoesNotChangeThisReview"])
        self.assertEqual(OrderCrossFunctionalReview.objects.count(), 2)

    def test_idempotency_does_not_duplicate_review(self):
        self.save("CRM_ORDER_REVIEW", "CONDITIONAL", "crm-same")
        self.save("CRM_ORDER_REVIEW", "CONDITIONAL", "crm-same")
        self.assertEqual(OrderCrossFunctionalReview.objects.count(), 1)

    def test_source_version_change_blocks_stale_save(self):
        with self.assertRaises(ReviewBusinessError) as caught:
            append_review(
                user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
                idempotency_key="stale", data={
                    "expectedSourceVersion": "OLD", "expectedContentHash": "a" * 64,
                    "reviewOpinion": "旧依据", "conclusion": "ACCEPT",
                },
            )
        self.assertEqual(caught.exception.code, "REVIEW_BASIS_CHANGED")

    def test_history_is_immutable(self):
        self.save("CRM_ORDER_REVIEW", "CONDITIONAL", "crm-immutable")
        row = OrderCrossFunctionalReview.objects.get()
        row.review_opinion = "覆盖历史"
        with self.assertRaises(Exception):
            row.save()
