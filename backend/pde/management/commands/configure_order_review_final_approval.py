import json

from django.core.management.base import BaseCommand, CommandError

from pde.models import OrderCrossFunctionalReview
from pde.order_review_approval import (
    OrderReviewApprovalError,
    ensure_order_review_approval_configuration,
    reconcile_legacy_submitted_review,
)
from pde.review_permission_catalog import ensure_review_permission_catalog
from system.models import OrganizationOperatingAuditRecord, User


class Command(BaseCommand):
    help = (
        "Register an itemized-review final-approval permission/process without "
        "assigning an approver; optionally reconcile one eligible legacy submission."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--review-type",
            choices=("CRM_ORDER_REVIEW", "PDE_PRODUCTION_FEASIBILITY"),
            default="CRM_ORDER_REVIEW",
        )
        parser.add_argument("--reconcile-review-id", type=int)
        parser.add_argument("--actor")
        parser.add_argument("--reason")
        parser.add_argument("--expected-review-version", type=int)
        parser.add_argument("--expected-source-order-no")
        parser.add_argument("--expected-source-version")
        parser.add_argument("--authorization-audit-id", type=int)

    def handle(self, *args, **options):
        review_type = options["review_type"]
        review_id = options.get("reconcile_review_id")
        result = {
            "permissionCatalog": (
                {"mode": "UNCHANGED_FOR_PRECISE_RECONCILIATION"}
                if review_id else ensure_review_permission_catalog()
            ),
            "approvalConfiguration": (
                {"mode": "REUSE_EXISTING_CONFIGURATION"}
                if review_id else ensure_order_review_approval_configuration(review_type)
            ),
            "reviewType": review_type,
            "approverAssignmentsCreated": 0,
            "approvalDecisionsCreated": 0,
        }
        if review_id:
            username = str(options.get("actor") or "").strip()
            reason = str(options.get("reason") or "").strip()
            expected_version = options.get("expected_review_version")
            expected_order = str(options.get("expected_source_order_no") or "").strip()
            expected_source_version = str(options.get("expected_source_version") or "").strip()
            authorization_audit_id = options.get("authorization_audit_id")
            if not all((username, reason, expected_version, expected_order, expected_source_version)):
                raise CommandError(
                    "--actor, --reason, --expected-review-version, --expected-source-order-no "
                    "and --expected-source-version are required with --reconcile-review-id"
                )
            review = OrderCrossFunctionalReview.objects.filter(pk=review_id).first()
            actor = User.objects.filter(username=username, is_active=True).first()
            if not review:
                raise CommandError("Review not found")
            if not actor:
                raise CommandError("Active actor not found")
            if review_type == "PDE_PRODUCTION_FEASIBILITY":
                authorization_audit = OrganizationOperatingAuditRecord.objects.filter(
                    pk=authorization_audit_id,
                    actor=actor,
                    organization_id=review.company_id,
                    action_code="SET_ROLE_PERMISSIONS",
                ).first()
                if not authorization_audit:
                    raise CommandError(
                        "PDE reconciliation requires the exact administrator SET_ROLE_PERMISSIONS audit."
                    )
            try:
                result["legacyReconciliation"] = reconcile_legacy_submitted_review(
                    review=review,
                    actor=actor,
                    reason=reason,
                    expected_review_type=review_type,
                    expected_review_version=expected_version,
                    expected_source_order_no=expected_order,
                    expected_source_version=expected_source_version,
                    authorization_audit_id=authorization_audit_id,
                )
            except OrderReviewApprovalError as exc:
                raise CommandError(f"{exc.code}: {exc.message}") from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
