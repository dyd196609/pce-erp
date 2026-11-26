import hashlib
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from workflow_runtime.models import UserOrganizationRoleAuthority

from bank_send_execution_simulation.models import BankSendFinalApproval
from bank_send_execution_simulation.v67 import (
    BUSINESS_OWNER_ROLE,
    FUND_OWNER_ROLE,
    SECURITY_OWNER_ROLE,
    create_dual_isolation_check,
    create_release_review,
    protection_counts,
    submit_release_decision,
)


class Command(BaseCommand):
    help = "Create V67 isolated dual check and production release review"

    def handle(self, *args, **options):
        database_name = str(settings.DATABASES["default"]["NAME"])
        if (
            not getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            or "v67-isolated" not in database_name.lower()
        ):
            raise CommandError("V67 command requires the isolated V67 database")
        user_model = get_user_model()
        owner = user_model.objects.get(
            username=getattr(
                settings, "PCE_CANARY_USERNAME", "purchase-canary-demo"
            )
        )
        approval = BankSendFinalApproval.objects.select_related(
            "trace__source_simulation__source_request",
            "trace__isolation_gate",
        ).get(status="final_locked")
        isolation_check = create_dual_isolation_check(
            approval=approval, user=owner
        )
        review = create_release_review(
            approval=approval,
            isolation_check=isolation_check,
            user=owner,
        )
        legal_entity = approval.trace.source_simulation.source_request.legal_entity_id
        reviewers = []
        for username, real_name, role in (
            (
                "v67-business-owner",
                "V67业务负责人",
                BUSINESS_OWNER_ROLE,
            ),
            ("v67-fund-owner", "V67资金负责人", FUND_OWNER_ROLE),
            (
                "v67-security-owner",
                "V67系统安全负责人",
                SECURITY_OWNER_ROLE,
            ),
        ):
            user, _ = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "real_name": real_name,
                    "company_id": owner.company_id,
                    "is_active": True,
                },
            )
            UserOrganizationRoleAuthority.objects.get_or_create(
                user=user,
                role_code=role,
                legal_entity_id=legal_entity,
                defaults={
                    "department_id": "V67-CANARY",
                    "active": True,
                    "version": 1,
                    "business_hash": hashlib.sha256(
                        f"{username}:{role}:{legal_entity}".encode()
                    ).hexdigest(),
                },
            )
            reviewers.append(user)
        for stage, user, reason in (
            ("business", reviewers[0], "业务负责人确认生产放行评审资料完整"),
            ("fund", reviewers[1], "资金负责人确认资金与付款权限保持关闭"),
            ("security", reviewers[2], "系统安全负责人确认双重隔离持续有效"),
        ):
            if review.status == {
                "business": "draft",
                "fund": "reviewing",
                "security": "review_passed",
            }[stage]:
                review = submit_release_decision(
                    review=review,
                    user=user,
                    stage=stage,
                    reason=reason,
                )
        result = {
            "result": "passed",
            "version": "V1.14.2.8.4.7.67",
            "reviewStatus": review.status,
            "reviewers": [row.username for row in reviewers],
            **protection_counts(),
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
