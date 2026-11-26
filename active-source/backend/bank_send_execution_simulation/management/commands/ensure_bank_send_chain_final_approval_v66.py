import hashlib
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from workflow_runtime.models import UserOrganizationRoleAuthority

from bank_send_execution_simulation.models import (
    BankSendChainTrace,
    BankSendExecutionSimulation,
    BankSendFinalApproval,
)
from bank_send_execution_simulation.v66 import (
    BUSINESS_REVIEWER_ROLE,
    FUND_OWNER_ROLE,
    create_final_approval,
    ensure_chain_traces,
    protection_counts,
    submit_first_approval,
    submit_second_approval,
)


class Command(BaseCommand):
    help = "Create V66 isolated chain traces and dual-role final approval"

    def handle(self, *args, **options):
        database_name = str(settings.DATABASES["default"]["NAME"])
        if (
            not getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            or "v66-isolated" not in database_name.lower()
        ):
            raise CommandError("V66 command requires the isolated V66 database")
        user_model = get_user_model()
        owner = user_model.objects.get(
            username=getattr(
                settings, "PCE_CANARY_USERNAME", "purchase-canary-demo"
            )
        )
        ensure_chain_traces(
            user=owner,
            queryset=BankSendExecutionSimulation.objects.order_by("pk"),
        )
        success_trace = BankSendChainTrace.objects.select_related(
            "source_simulation__source_request"
        ).filter(
            source_simulation__status="simulation_success"
        ).first()
        if not success_trace:
            raise CommandError("No successful simulation trace exists")
        approval = create_final_approval(trace=success_trace, user=owner)
        legal_entity = (
            success_trace.source_simulation.source_request.legal_entity_id
        )
        reviewer, _ = user_model.objects.get_or_create(
            username="v66-business-reviewer",
            defaults={
                "real_name": "V66业务审核人",
                "company_id": owner.company_id,
                "is_active": True,
            },
        )
        fund_owner, _ = user_model.objects.get_or_create(
            username="v66-fund-owner",
            defaults={
                "real_name": "V66资金负责人",
                "company_id": owner.company_id,
                "is_active": True,
            },
        )
        for user, role in (
            (reviewer, BUSINESS_REVIEWER_ROLE),
            (fund_owner, FUND_OWNER_ROLE),
        ):
            UserOrganizationRoleAuthority.objects.get_or_create(
                user=user,
                role_code=role,
                legal_entity_id=legal_entity,
                defaults={
                    "department_id": "V66-CANARY",
                    "active": True,
                    "version": 1,
                    "business_hash": hashlib.sha256(
                        f"{user.username}:{role}:{legal_entity}".encode()
                    ).hexdigest(),
                },
            )
        if approval.status == "pending":
            approval = submit_first_approval(
                approval=approval,
                user=reviewer,
                reason="业务审核人确认发送前资料完整",
            )
        if approval.status == "first_approved":
            approval = submit_second_approval(
                approval=approval,
                user=fund_owner,
                reason="资金负责人确认最终审批条件通过",
            )
        result = {
            "result": "passed",
            "version": "V1.14.2.8.4.7.66",
            "chainTraceWriteCount": BankSendChainTrace.objects.count(),
            "finalApprovalWriteCount": BankSendFinalApproval.objects.count(),
            "finalApprovalStatus": approval.status,
            "firstApprover": reviewer.username,
            "secondApprover": fund_owner.username,
            **protection_counts(),
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
